"""Exercise assignment delivery locally without sending WhatsApp messages."""
import importlib.util
import sys
import unittest
from datetime import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch


class AssignmentWhatsAppTest(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe.conf = {
            "teamspace_whatsapp_template": "teamspace_task_assignment",
            "teamspace_whatsapp_base_url": "https://example.test",
            "teamspace_whatsapp_recipients": {"assignee": "+919000000000"},
        }
        self.frappe.enqueue = Mock()
        self.task = SimpleNamespace(name="CA/1", assigned_to="assignee", whatsapp_assignment_revision="current",
                                    status="Open", subject="File GST return", due_date="2026-11-20",
                                    due_time="14:30:00", whatsapp_summary=" November\n return ")
        self.frappe.db = SimpleNamespace(get_value=Mock(return_value=self.task))
        self.requests = ModuleType("requests")
        self.requests.post = Mock()
        self.whatsapp = ModuleType("snrg_whatsapp")
        self.whatsapp.api = Mock()
        self.whatsapp.api._find_or_create_chatwoot_conversation.return_value = {"id": 23}
        self.whatsapp.api._chatwoot_url.side_effect = lambda config, path: path
        self.internal = Mock(return_value=True)
        modules = {
            "frappe": self.frappe, "requests": self.requests, "snrg_whatsapp": self.whatsapp,
            "frappe.utils": SimpleNamespace(formatdate=lambda value, fmt: "20 Nov 2026",
                                           get_time=time.fromisoformat, get_fullname=str.title),
            "snrg_credit_control.customer_workspace.api": SimpleNamespace(ACTION="Customer Action", internal=self.internal),
        }
        mocks = patch.dict(sys.modules, modules)
        mocks.start()
        self.addCleanup(mocks.stop)
        file = Path(__file__).resolve().parents[1] / "snrg_credit_control/customer_workspace/assignment_whatsapp.py"
        spec = importlib.util.spec_from_file_location("assignment_whatsapp", file)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_commit_queue_captures_assigner_and_revision(self):
        self.module.enqueue_assignment(self.task, "manager")
        self.frappe.enqueue.assert_called_once_with(
            self.module.JOB, enqueue_after_commit=True, name="CA/1",
            assignee="assignee", revision="current", actor="manager",
        )

    def test_payload_with_dynamic_button(self):
        self.module.deliver("CA/1", "assignee", "current", "manager")
        request = self.requests.post.call_args
        self.assertEqual(request.args[0], "conversations/23/messages")
        params = request.kwargs["json"]["template_params"]["processed_params"]
        self.assertEqual(list(params["body"].values()),
                         ["File GST return", "Manager", "20 Nov 2026", "14:30", "November return"])
        self.assertEqual(params["buttons"][0]["parameter"], "CA%2F1")
        self.assertEqual(params["buttons"][0]["url"], "https://example.test/teamspace?task={{1}}")

    def test_no_delivery_for_old_assignment_or_opt_out(self):
        self.module.deliver("CA/1", "assignee", "old", "manager")
        self.frappe.conf["teamspace_whatsapp_recipients"] = {}
        self.module.enqueue_assignment(self.task, "manager")
        self.module.deliver("CA/1", "assignee", "current", "manager")
        self.frappe.enqueue.assert_not_called()
        self.requests.post.assert_not_called()

    def test_optional_fields(self):
        self.task.whatsapp_summary = ""
        self.task.due_time = None
        self.module.deliver("CA/1", "assignee", "current", "manager")
        body = self.requests.post.call_args.kwargs["json"]["template_params"]["processed_params"]["body"]
        self.assertEqual(body["4"], "No time set")
        self.assertEqual(body["5"], "See task for details.")


class TaskLinkTest(unittest.TestCase):
    def test_guest_redirect_retains_task(self):
        frappe = SimpleNamespace(
            request=SimpleNamespace(args={"task": "CA/1 & test"}),
            session=SimpleNamespace(user="Guest"),
            redirect=Mock(side_effect=RuntimeError("redirect")),
        )
        desk_context = Mock()
        with patch.dict(sys.modules, {"frappe": frappe, "frappe.www.desk": SimpleNamespace(get_context=desk_context)}):
            file = Path(__file__).resolve().parents[1] / "snrg_credit_control/www/teamspace.py"
            spec = importlib.util.spec_from_file_location("teamspace", file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with self.assertRaisesRegex(RuntimeError, "redirect"):
                module.get_context({})
            target = parse_qs(urlsplit(frappe.redirect.call_args.args[0]).query)["redirect-to"][0]
            self.assertEqual(urlsplit(target).path, "/teamspace")
            self.assertEqual(parse_qs(urlsplit(target).query), {"task": ["CA/1 & test"]})
            frappe.session.user = "staff@example.test"
            self.assertIs(module.get_context({}), desk_context.return_value)


if __name__ == "__main__":
    unittest.main()
