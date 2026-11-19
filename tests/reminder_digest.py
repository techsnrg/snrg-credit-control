"""Digest regression tests with native delivery mocked; sends no real messages."""
from datetime import datetime
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock

frappe = types.ModuleType('frappe')
utils = types.ModuleType('frappe.utils')
api = types.ModuleType('snrg_credit_control.customer_workspace.api')
prefs = types.ModuleType('frappe.desk.doctype.notification_settings.notification_settings')
prefs.is_email_notifications_enabled_for_type = lambda user, kind: user != 'manager' or kind == 'Assignment'
prefs.is_notifications_enabled = lambda user: user != 'muted'
sys.modules[prefs.__name__] = prefs
api.ACTION = 'Customer Action'
api.internal = lambda user: user in ('junior', 'manager')
sys.modules.update({'frappe': frappe, 'frappe.utils': utils,
                    'snrg_credit_control.customer_workspace.api': api})
frappe.utils = utils
utils.get_url = lambda path: 'https://example.test' + path
utils.today = lambda: '2026-11-20'
utils.now_datetime = lambda: datetime(2026, 11, 20, 9)
spec = importlib.util.spec_from_file_location('reminders', Path(__file__).resolve().parents[1] / 'snrg_credit_control/customer_workspace/reminders.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def action(name, user='junior', date='2026-11-20', **extra):
    return types.SimpleNamespace(name=name, assigned_to=user, due_date=date,
        due_time=None, customer_name=None, supplier_name=None,
        subject=extra.pop('subject', name), last_reminder_on=extra.pop('last_reminder_on', None), **extra)


class DigestTests(unittest.TestCase):
    def setUp(self):
        utils.now_datetime = lambda: datetime(2026, 11, 20, 9)
        # Module imports bind these helpers directly.
        m.now_datetime = utils.now_datetime
        self.logs = []
        frappe.get_all = Mock(return_value=[])
        frappe.local = types.SimpleNamespace(site='example.test')
        frappe.db = types.SimpleNamespace(sql=Mock(), set_value=Mock(), exists=Mock(return_value=False),
            get_value=Mock(side_effect=lambda kind, name, field, **opts:
                name + '@example.test' if kind == 'User' else next(
                    (row['message_id'] for row in self.logs if row['message_id'] == name['message_id']), None)))
        frappe.sendmail = Mock(side_effect=lambda **data: self.logs.append(data))
        frappe.get_doc = Mock()

    def test_midnight_does_nothing(self):
        m.now_datetime = lambda: datetime(2026, 11, 20, 0)
        m.daily()
        frappe.get_all.assert_not_called()

    def test_one_digest_each_with_private_grouping_and_html_escaping(self):
        frappe.get_all.return_value = [action('Due <script>', subject='<script>alert(1)</script>'),
            action('Old', date='2026-11-18'), action('Manager only', user='manager'),
            action('Disabled user', user='disabled')]
        m.daily()
        self.assertEqual(len(self.logs), 2)
        junior = self.logs[0]
        self.assertEqual(junior['recipients'], ['junior@example.test'])
        self.assertIn('1 due today · 1 overdue', junior['message'])
        self.assertIn('&lt;script&gt;', junior['message'])
        self.assertNotIn('<script>', junior['message'])
        self.assertNotIn('Manager only', junior['message'])
        self.assertIn('General task', junior['message'])
        self.assertTrue(junior['delayed'])
        frappe.get_doc.assert_not_called()
        self.assertEqual(frappe.db.set_value.call_count, 3)
        self.assertEqual(frappe.get_all.call_args.kwargs['filters'], {
            'status': ['in', ['Open', 'In Progress']], 'due_date': ['<=', '2026-11-20']})

    def test_retry_and_later_new_tasks_do_not_send_second_digest(self):
        frappe.get_all.return_value = [action('First')]
        m.daily()
        frappe.get_all.return_value.append(action('Later'))
        m.daily()
        self.assertEqual(len(self.logs), 1)

    def test_legacy_midnight_markers_do_not_suppress_the_first_digest(self):
        m.daily()
        frappe.sendmail.assert_not_called()
        frappe.get_all.return_value = [action('Old system sent', last_reminder_on='2026-11-20')]
        m.daily()
        self.assertEqual(len(self.logs), 1)

    def test_insert_failure_does_not_mark_tasks(self):
        frappe.get_all.return_value = [action('Retry')]
        frappe.sendmail.side_effect = RuntimeError('Delivery transaction failed')
        with self.assertRaises(RuntimeError):
            m.daily()
        frappe.db.set_value.assert_not_called()

    def test_scheduler_is_nine_in_site_timezone(self):
        import ast
        source = (Path(__file__).resolve().parents[1] / 'snrg_credit_control/hooks.py').read_text()
        events = next(ast.literal_eval(node.value) for node in ast.parse(source).body
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'scheduler_events' for t in node.targets))
        self.assertEqual(events, {'cron': {'0 9 * * *': ['snrg_credit_control.customer_workspace.reminders.daily']}})


if __name__ == '__main__':
    unittest.main()
