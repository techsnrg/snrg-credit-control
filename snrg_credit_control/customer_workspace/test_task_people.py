"""Transactional task-recipient regression. Isolated staging only, no outbound notifications."""
from unittest.mock import patch
import frappe
from frappe.utils import today
from snrg_credit_control.customer_workspace import api


def run():
    if not any(word in frappe.local.site for word in ("staging", "test")):
        raise RuntimeError("Run only on isolated staging")
    original = frappe.session.user
    try:
        frappe.set_user("Administrator")
        staff = []
        for i in range(3):
            user = f"task-people-{frappe.generate_hash(length=8)}@example.invalid"
            frappe.get_doc({"doctype": "User", "email": user, "first_name": f"Recipient {i}", "enabled": 1, "user_type": "System User", "send_welcome_email": 0, "roles": [{"role": "Employee"}]}).insert(ignore_permissions=True)
            employee = frappe.get_doc({"doctype": "Employee", "first_name": f"Recipient {i}", "employee_name": f"Recipient {i}", "user_id": user, "status": "Active", "company": frappe.db.get_value("Company", {}, "name"), "date_of_joining": today()})
            employee.flags.ignore_mandatory = True
            employee.insert(ignore_permissions=True)
            staff.append((user, employee.name, employee.employee_name))
        sent = []
        def notify(users, subject, doctype, name, **kwargs):
            sent.append((list(users), kwargs.get("kind", "Assignment")))
        with patch("snrg_credit_control.customer_workspace.api.notify", side_effect=notify), patch("snrg_credit_control.customer_workspace.controllers.notify", side_effect=notify):
            result = api.create_action({"subject": "File GST return", "assigned_users": [staff[0][0], staff[1][0], staff[0][0]], "due_date": today(), "due_time": "10:30:00", "description": "Coordinate with @" + staff[2][2] + " and @" + staff[0][2], "mentions": [staff[2][1], staff[0][1]]})
            assert len(result["actions"]) == 2
            docs = [frappe.get_doc(api.ACTION, name) for name in result["actions"]]
            assert docs[0].assignment_group and docs[0].assignment_group == docs[1].assignment_group
            assert {d.assigned_to for d in docs} == {staff[0][0], staff[1][0]}
            assert all(not d.customer and not d.supplier and d.event for d in docs)
            assert len(api.linked_actions(docs[0].name)) == 1
            assert [users for users, kind in sent if kind == "Mention"] == [[staff[2][0]]]
            assert len([kind for users, kind in sent if kind == "Assignment"]) == 2
            frappe.db.set_value("Employee", staff[2][1], {"employee_name": "Renamed FYI", "status": "Left"})
            frappe.set_user(staff[0][0])
            assert api.permission(docs[0], permission_type="write") and not api.permission(docs[1], permission_type="write")
            api.update_action(docs[0].name, {"status": "Completed", "update": "Filed"}, str(docs[0].modified))
            assert frappe.db.get_value(api.ACTION, docs[1].name, "status") == "Open"
            frappe.set_user("Administrator")
            count = frappe.db.count(api.ACTION)
            try:
                api.create_action({"subject": "Invalid", "assigned_users": [staff[0][0], "Guest"], "due_date": today()})
            except frappe.ValidationError:
                pass
            else:
                raise AssertionError("Guest accepted")
            assert frappe.db.count(api.ACTION) == count
        return {"passed": ["deduplicated recipients", "independent linked tasks and calendar events", "single mention notification excluding assignees", "owner/assignee mutation permissions", "independent completion", "invalid recipient rejection without partial creation"]}
    finally:
        frappe.db.rollback()
        frappe.set_user(original)
