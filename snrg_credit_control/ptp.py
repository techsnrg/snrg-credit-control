import frappe
from frappe.utils import fmt_money, getdate, get_url_to_form, today

from snrg_credit_control.credit_status import zero


ACTIVE_PTP_STATUSES = {"Pending", "Partially Cleared"}


def val(value):
    return zero(value)


def build_ptp_reference_label(doc):
    parts = []
    if doc.get("ptp_by_name"):
        parts.append(doc.ptp_by_name)
    if doc.get("commitment_date"):
        parts.append(str(doc.commitment_date))
    if doc.get("committed_amount"):
        parts.append(fmt_money(val(doc.committed_amount), currency=doc.get("currency") or "INR"))
    return " | ".join(parts) or (doc.get("name") or "PTP")


def sync_credit_ptp(doc):
    payment_totals = {}
    payment_amount_totals = {}
    links = list(doc.get("payment_links") or [])

    for link in links:
        pe = frappe.db.get_value(
            "Payment Entry",
            link.payment_entry,
            ["posting_date", "paid_amount", "docstatus", "party_type", "party", "company"],
            as_dict=True,
        ) or {}
        if not pe:
            frappe.throw(f"Payment Entry {link.payment_entry} was not found.")
        if pe.get("docstatus") != 1:
            frappe.throw(f"Payment Entry {link.payment_entry} must be submitted before it can be linked to a PTP.")
        if pe.get("party_type") != "Customer" or pe.get("party") != doc.customer:
            frappe.throw(f"Payment Entry {link.payment_entry} must belong to customer {doc.customer}.")
        if pe.get("company") != doc.company:
            frappe.throw(f"Payment Entry {link.payment_entry} must belong to company {doc.company}.")

        link.posting_date = pe.get("posting_date")
        link.payment_entry_amount = val(pe.get("paid_amount"))
        link.allocated_amount = val(link.allocated_amount or link.payment_entry_amount)

        if link.allocated_amount <= 0:
            frappe.throw(f"Allocated amount for Payment Entry {link.payment_entry} must be greater than zero.")
        if link.allocated_amount > link.payment_entry_amount:
            frappe.throw(
                f"Allocated amount for Payment Entry {link.payment_entry} cannot exceed the Payment Entry amount."
            )

        payment_amount_totals[link.payment_entry] = payment_amount_totals.get(link.payment_entry, 0) + link.allocated_amount
        if payment_amount_totals[link.payment_entry] > link.payment_entry_amount:
            frappe.throw(
                f"Total allocated amount for Payment Entry {link.payment_entry} across this PTP "
                "cannot exceed the Payment Entry amount."
            )

        payment_totals.setdefault("received", 0)
        payment_totals["received"] += link.allocated_amount

    received = val(payment_totals.get("received"))
    committed = val(doc.committed_amount)
    difference = committed - received

    doc.received_amount = received
    doc.difference_amount = difference
    doc.linked_payment_entries = ", ".join(sorted({link.payment_entry for link in links if link.payment_entry}))

    if committed and received >= committed:
        doc.status = "Cleared"
    elif received > 0:
        doc.status = "Partially Cleared"
    elif doc.commitment_date and getdate(doc.commitment_date) < getdate(today()):
        doc.status = "Broken"
    elif doc.status == "Superseded":
        pass
    else:
        doc.status = "Pending"


def supersede_previous_ptps(current_doc):
    if current_doc.get("status") not in ACTIVE_PTP_STATUSES:
        return

    others = frappe.get_all(
        "Credit PTP",
        filters={
            "sales_order": current_doc.sales_order,
            "name": ["!=", current_doc.name],
            "status": ["in", list(ACTIVE_PTP_STATUSES)],
        },
        fields=["name"],
        order_by="creation desc",
    )
    for row in others:
        frappe.db.set_value("Credit PTP", row.name, "status", "Superseded", update_modified=False)


def get_ptp_references_for_sales_order(sales_order, actionable_only=False):
    filters = {"sales_order": sales_order}
    if actionable_only:
        filters["status"] = ["in", list(ACTIVE_PTP_STATUSES)]
    else:
        filters["status"] = ["!=", "Superseded"]

    rows = frappe.get_all(
        "Credit PTP",
        filters=filters,
        fields=[
            "name",
            "ptp_by_name",
            "commitment_date",
            "committed_amount",
            "received_amount",
            "difference_amount",
            "status",
            "currency",
        ],
        order_by="creation desc",
    )

    refs = []
    for row in rows:
        row_doc = frappe._dict(row)
        refs.append(
            {
                "ptp_entry_id": row.name,
                "label": build_ptp_reference_label(row_doc),
                "committed_amount": val(row.committed_amount),
                "received_amount": val(row.received_amount),
                "difference_amount": val(row.difference_amount or row.committed_amount),
                "status": row.status or "Pending",
            }
        )
    return refs


def get_sales_order_ptp_docs(sales_order, include_superseded=False):
    filters = {"sales_order": sales_order}
    if not include_superseded:
        filters["status"] = ["!=", "Superseded"]
    return frappe.get_all(
        "Credit PTP",
        filters=filters,
        fields=[
            "name",
            "ptp_by_name",
            "ptp_date",
            "commitment_date",
            "committed_amount",
            "received_amount",
            "difference_amount",
            "payment_mode",
            "status",
            "remarks",
            "linked_payment_entries",
        ],
        order_by="creation desc",
    )


def get_active_credit_ptp(sales_order):
    return frappe.get_all(
        "Credit PTP",
        filters={"sales_order": sales_order, "status": ["in", list(ACTIVE_PTP_STATUSES)]},
        fields=["name"],
        order_by="creation desc",
        limit=1,
    )


def _get_employee_notification_target(employee):
    if not employee:
        return {}

    target = frappe.db.get_value(
        "Employee",
        employee,
        ["employee_name", "user_id", "company_email", "personal_email"],
        as_dict=True,
    ) or {}

    email = None
    user_id = target.get("user_id")
    if user_id and "@" in user_id:
        email = user_id
    email = email or target.get("company_email") or target.get("personal_email")

    return {
        "employee_name": target.get("employee_name") or employee,
        "user_id": user_id,
        "email": email,
    }


def _create_internal_notification(for_user, subject, html, document_name):
    if not for_user:
        return

    frappe.get_doc(
        {
            "doctype": "Notification Log",
            "for_user": for_user,
            "type": "Alert",
            "document_type": "Credit PTP",
            "document_name": document_name,
            "subject": subject,
            "email_content": html,
            "from_user": frappe.session.user if frappe.session.user and frappe.session.user != "Guest" else "Administrator",
        }
    ).insert(ignore_permissions=True)


def _build_ptp_reminder_message(doc, reminder_type):
    customer = doc.get("customer_name") or doc.get("customer") or "Customer"
    due_date = doc.get("commitment_date")
    committed = fmt_money(val(doc.get("committed_amount")), currency=doc.get("currency") or "INR")
    received = fmt_money(val(doc.get("received_amount")), currency=doc.get("currency") or "INR")
    difference = fmt_money(val(doc.get("difference_amount")), currency=doc.get("currency") or "INR")
    ptp_url = get_url_to_form("Credit PTP", doc.name)
    sales_order_url = get_url_to_form("Sales Order", doc.sales_order) if doc.get("sales_order") else None

    if reminder_type == "due_today":
        subject = f"[SNRG] PTP Due Today — {doc.name} ({customer})"
        intro = "This PTP is due today and needs follow-up."
    else:
        subject = f"[SNRG] PTP Overdue — {doc.name} ({customer})"
        intro = "This PTP is overdue and needs immediate follow-up."

    links = [f'<a href="{ptp_url}">Open Credit PTP</a>']
    if sales_order_url:
        links.append(f'<a href="{sales_order_url}">Open Sales Order</a>')

    html = (
        f"<p>{intro}</p>"
        f"<p><strong>Customer:</strong> {frappe.utils.escape_html(customer)}<br>"
        f"<strong>PTP:</strong> {frappe.utils.escape_html(doc.name)}<br>"
        f"<strong>Sales Order:</strong> {frappe.utils.escape_html(doc.get('sales_order') or '-')}<br>"
        f"<strong>Payment By Date:</strong> {frappe.utils.escape_html(str(due_date or '-'))}<br>"
        f"<strong>Committed Amount:</strong> {frappe.utils.escape_html(committed)}<br>"
        f"<strong>Received Amount:</strong> {frappe.utils.escape_html(received)}<br>"
        f"<strong>Difference Amount:</strong> {frappe.utils.escape_html(difference)}</p>"
        f"<p>{' | '.join(links)}</p>"
    )
    return subject, html


def _send_ptp_reminder(doc, reminder_type):
    target = _get_employee_notification_target(doc.get("ptp_by"))
    if not target:
        return False

    subject, html = _build_ptp_reminder_message(doc, reminder_type)
    sent = False

    if target.get("user_id"):
        _create_internal_notification(target.get("user_id"), subject, html, doc.name)
        sent = True

    if target.get("email"):
        frappe.sendmail(
            recipients=[target.get("email")],
            subject=subject,
            message=html,
            delayed=False,
        )
        sent = True

    return sent


def send_due_ptp_reminders():
    today_date = getdate(today())
    ptps = frappe.get_all(
        "Credit PTP",
        filters={
            "status": ["in", list(ACTIVE_PTP_STATUSES)],
            "commitment_date": ["is", "set"],
        },
        fields=[
            "name",
            "customer",
            "customer_name",
            "sales_order",
            "commitment_date",
            "committed_amount",
            "received_amount",
            "difference_amount",
            "currency",
            "ptp_by",
            "last_reminder_on",
            "last_reminder_type",
        ],
    )

    for row in ptps:
        commitment_date = getdate(row.commitment_date)
        reminder_type = None
        if commitment_date == today_date:
            reminder_type = "due_today"
        elif commitment_date < today_date:
            reminder_type = "overdue"

        if not reminder_type:
            continue

        if row.get("last_reminder_on") == today_date and row.get("last_reminder_type") == reminder_type:
            continue

        if _send_ptp_reminder(row, reminder_type):
            frappe.db.set_value(
                "Credit PTP",
                row.name,
                {
                    "last_reminder_on": today_date,
                    "last_reminder_type": reminder_type,
                },
                update_modified=False,
            )


@frappe.whitelist()
def run_due_ptp_reminders_now():
    if not frappe.has_permission("Credit PTP", "read"):
        frappe.throw("Not permitted.", frappe.PermissionError)
    send_due_ptp_reminders()
    return {"ok": True}
