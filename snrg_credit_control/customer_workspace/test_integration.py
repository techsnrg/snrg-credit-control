"""Transactional integration checks. Run only on an isolated test/staging site.
bench --site TEST_SITE execute snrg_credit_control.customer_workspace.test_integration.run
"""
from unittest.mock import patch
import frappe
from frappe.utils import today, add_days
from snrg_credit_control.customer_workspace import api


def run():
    if not ("staging" in frappe.local.site or "test" in frappe.local.site):
        raise RuntimeError("Integration fixtures are restricted to test/staging sites")
    original = frappe.session.user
    results = []
    try:
        frappe.set_user("Administrator")
        employees = []
        for suffix in ("owner", "assignee", "other"):
            user = f"cw-{frappe.generate_hash(length=8)}-{suffix}@example.invalid"
            frappe.get_doc({"doctype": "User", "email": user, "first_name": suffix, "enabled": 1, "user_type": "System User", "send_welcome_email": 0, "roles": [{"role": "Employee"}]}).insert(ignore_permissions=True)
            employee = frappe.get_doc({"doctype": "Employee", "first_name": suffix, "employee_name": suffix, "status": "Active", "user_id": user, "company": frappe.db.get_value("Company", {}, "name"), "date_of_joining": today()})
            employee.flags.ignore_mandatory = True
            employee.insert(ignore_permissions=True)
            employees.append((user, employee.name))
        owner, assignee, other = [p[0] for p in employees]
        customer = frappe.get_doc({"doctype": "Customer", "customer_name": "Workspace integration " + frappe.generate_hash(length=8), "customer_type": "Company"})
        customer.flags.ignore_mandatory = True
        customer.insert(ignore_permissions=True)
        frappe.set_user(owner)
        with patch("frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification") as notifications:
            result = api.log_interaction({"customer": customer.name, "summary": "Discussed damaged cartons. @assignee arrange collection.", "mentions": [employees[1][1]], "actions": [{"subject": "Collect cartons", "assigned_to": assignee, "due_date": today(), "due_time": "14:00", "action_type": "Return pickup"}]})
            assert len(result["actions"]) == 1
            action = frappe.get_doc(api.ACTION, result["actions"][0])
            assert action.customer_name == customer.customer_name
            assert action.event and frappe.db.get_value("Event", action.event, "reference_docname") == action.name
            assert notifications.call_count >= 2
            results.append("interaction + mention notification + assigned action + calendar creation")
            assert api.history(customer.name)["interactions"][0].mentions[0].employee == employees[1][1]
            assert len(api.actions(scope="assigned", customer=customer.name)) == 1
            try:
                api.actions(scope="team")
                raise AssertionError("Non-manager could read team work")
            except frappe.PermissionError:
                pass
            results.append("shared history and non-manager team access denied")
            frappe.set_user(other)
            assert api.permission(action, permission_type="read")
            assert frappe.has_permission(api.ACTION, "read", doc=action)
            assert not api.permission(action, permission_type="write")
            try:
                api.update_action(action.name, {"status": "Completed", "update": "unauthorized"}, str(action.modified))
                raise AssertionError("Unrelated employee could mutate action")
            except frappe.PermissionError:
                pass
            frappe.set_user(assignee)
            assert len(api.actions(customer=customer.name)) == 1
            rescheduled = api.update_action(action.name, {"due_date": add_days(today(), 1), "due_time": "15:00", "update": "Customer requested tomorrow."}, str(action.modified))
            assert str(frappe.db.get_value("Event", action.event, "starts_on")).endswith("15:00:00")
            action = frappe.get_doc(api.ACTION, action.name)
            updated = api.update_action(action.name, {"status": "Completed", "update": "Collected all cartons."}, str(action.modified))
            assert updated["status"] == "Completed"
            assert frappe.db.get_value("Event", action.event, "status") == "Completed"
            assert len(api.history(customer.name)["interactions"]) == 3
            try:
                api.update_action(action.name, {"status": "Open", "update": "stale"}, str(action.modified))
                raise AssertionError("Stale save accepted")
            except frappe.TimestampMismatchError:
                pass
            results.append("assignee completion + calendar synchronization + audit history + stale save rejected")
            event = frappe.get_doc("Event", action.event)
            event.subject = "Changed directly"
            try:
                event.save(ignore_permissions=True)
                raise AssertionError("Calendar projection could be edited directly")
            except frappe.ValidationError:
                pass
            frappe.set_user("Guest")
            try:
                api.bootstrap()
                raise AssertionError("Guest could access directory")
            except frappe.PermissionError:
                pass
            results.append("calendar projection protected and guest directory denied")
    finally:
        frappe.db.rollback()
        frappe.set_user(original)
    print({"passed": results, "fixtures": "rolled back"})
