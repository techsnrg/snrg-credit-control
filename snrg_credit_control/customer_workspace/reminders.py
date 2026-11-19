"""One personal digest of due and overdue work, at 09:00 in the site timezone."""
from collections import defaultdict
from hashlib import sha256
from html import escape

import frappe
from frappe.utils import now_datetime, today
from frappe.desk.doctype.notification_settings.notification_settings import (
    is_email_notifications_enabled_for_type, is_notifications_enabled,
)
from snrg_credit_control.customer_workspace.api import ACTION, internal


def daily():
    # Protect sites still carrying the old midnight Daily scheduler during rollout.
    if now_datetime().hour < 9:
        return
    date = today()
    grouped = defaultdict(list)
    for action in frappe.get_all(ACTION, filters={
        "status": ["in", ["Open", "In Progress"]], "due_date": ["<=", date],
    }, fields=["name", "subject", "assigned_to", "due_date", "due_time",
               "customer_name", "supplier_name", "last_reminder_on"],
        order_by="due_date asc, due_time asc, name asc", limit_page_length=0):
        grouped[action.assigned_to].append(action)

    for user, actions in grouped.items():
        if not internal(user) or not is_notifications_enabled(user) or not is_email_notifications_enabled_for_type(user, "Assignment"):
            continue
        subject = f"Teamspace daily summary · {date}"
        # Serialize retries for this recipient. Queueing and marking tasks commit together.
        frappe.db.sql("select name from `tabUser` where name=%s for update", (user,))
        digest_key = sha256(f"{frappe.local.site}:{date}:{user}".encode()).hexdigest()
        message_id = f"teamspace-digest-{digest_key}@teamspace.local"
        if frappe.db.get_value("Email Queue", {"message_id": message_id}, "name", for_update=True) or frappe.db.exists(
            "Notification Log", {"for_user": user, "subject": subject}
        ):
            continue
        email = frappe.db.get_value("User", user, "email")
        if not email:
            continue
        overdue = [row for row in actions if str(row.due_date) < date]
        due = [row for row in actions if str(row.due_date) == date]
        body = f"<p>{len(due)} due today · {len(overdue)} overdue</p>"
        for heading, rows in (("Due today", due), ("Overdue", overdue)):
            if not rows:
                continue
            body += f"<h3>{heading}</h3><ul>"
            for row in rows:
                party = row.customer_name or row.supplier_name or "General task"
                deadline = str(row.due_date) + (f" {row.due_time}" if row.due_time else "")
                body += (f"<li><strong>{escape(row.subject or '')}</strong>"
                         f"<br>{escape(party)} · {escape(deadline)}</li>")
            body += "</ul>"
        link = escape(frappe.utils.get_url("/teamspace"), quote=True)
        frappe.sendmail(
            recipients=[email], subject=subject, message=body + f'<p><a href="{link}">Open Teamspace</a></p>',
            message_id=message_id, delayed=True, is_notification=True,
            add_unsubscribe_link=False,
        )
        for row in actions:
            frappe.db.set_value(ACTION, row.name, "last_reminder_on", date, update_modified=False)
