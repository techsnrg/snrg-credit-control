"""Once-per-day in-app reminders for pending actions, including overdue work."""
import frappe
from frappe.utils import today
from snrg_credit_control.customer_workspace.api import ACTION, internal, notify


def daily():
    for action in frappe.get_all(ACTION, filters={"status": ["in", ["Open", "In Progress"]], "due_date": ["<=", today()]}, fields=["name", "subject", "assigned_to", "last_reminder_on"], limit_page_length=0):
        if str(action.last_reminder_on or "") == today() or not internal(action.assigned_to):
            continue
        notify([action.assigned_to], f"Follow-up due: {action.subject}", ACTION, action.name)
        frappe.db.set_value(ACTION, action.name, "last_reminder_on", today(), update_modified=False)
