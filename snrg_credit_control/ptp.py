import frappe
from frappe.utils import fmt_money, get_datetime, get_url_to_form, getdate, today

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
        fields=["name", "calendar_event"],
        order_by="creation desc",
    )
    for row in others:
        frappe.db.set_value("Credit PTP", row.name, "status", "Superseded", update_modified=False)
        if row.get("calendar_event") and frappe.db.exists("Event", row.calendar_event):
            _update_ptp_event_status(row.calendar_event, "Cancelled")


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


def get_employee_notification_target(employee):
    if not employee:
        return {}

    row = frappe.db.get_value(
        "Employee",
        employee,
        ["employee_name", "user_id", "company_email", "personal_email"],
        as_dict=True,
    ) or {}

    user_id = row.get("user_id")
    email = (user_id if user_id and "@" in user_id else None) or row.get("company_email") or row.get("personal_email")

    return {
        "employee": employee,
        "employee_name": row.get("employee_name") or employee,
        "user_id": user_id,
        "email": email,
    }


def sync_ptp_calendar_event(doc):
    event_name = doc.get("calendar_event")
    target = get_employee_notification_target(doc.get("ptp_by"))
    target_user = target.get("user_id")

    if not target_user or not doc.get("commitment_date"):
        if event_name and frappe.db.exists("Event", event_name):
            _update_ptp_event_status(event_name, "Cancelled")
        if doc.get("calendar_event"):
            frappe.db.set_value("Credit PTP", doc.name, "calendar_event", "", update_modified=False)
            doc.calendar_event = ""
        return

    event_doc = _build_ptp_event_doc(doc, target)

    if event_name and frappe.db.exists("Event", event_name):
        event = frappe.get_doc("Event", event_name)
        for fieldname, value in event_doc.items():
            event.set(fieldname, value)
        event.save(ignore_permissions=True)
        frappe.db.set_value("Event", event.name, "owner", target_user, update_modified=False)
        return

    event = frappe.get_doc(event_doc).insert(ignore_permissions=True)
    frappe.db.set_value("Event", event.name, "owner", target_user, update_modified=False)
    frappe.db.set_value("Credit PTP", doc.name, "calendar_event", event.name, update_modified=False)
    frappe.share.add_docshare("Event", event.name, target_user, read=1, write=1, share=0, notify=0)
    doc.calendar_event = event.name


def clear_ptp_calendar_event(doc):
    event_name = doc.get("calendar_event")
    if event_name and frappe.db.exists("Event", event_name):
        _update_ptp_event_status(event_name, "Cancelled")


def _build_ptp_event_doc(doc, target):
    customer_label = doc.get("customer_name") or doc.get("customer") or "Customer"
    subject = f"PTP Follow-up: {customer_label}"
    if doc.get("sales_order"):
        subject = f"{subject} / {doc.sales_order}"

    status = "Open" if doc.get("status") in ACTIVE_PTP_STATUSES or doc.get("status") == "Broken" else "Closed"
    start_dt = get_datetime(f"{doc.commitment_date} 09:00:00")
    description = (
        f"Credit PTP: {doc.name}\n"
        f"Sales Order: {doc.get('sales_order') or '—'}\n"
        f"Customer: {customer_label}\n"
        f"Committed By: {target.get('employee_name') or doc.get('ptp_by') or '—'}\n"
        f"Committed Amount: {fmt_money(val(doc.get('committed_amount')), currency=doc.get('currency') or 'INR')}\n"
        f"Status: {doc.get('status') or 'Pending'}\n"
        f"Open PTP: {get_url_to_form('Credit PTP', doc.name)}"
    )

    return {
        "doctype": "Event",
        "subject": subject,
        "event_type": "Private",
        "event_category": "Event",
        "status": status,
        "starts_on": start_dt,
        "all_day": 1,
        "description": description,
        "reference_doctype": "Credit PTP",
        "reference_docname": doc.name,
        "event_participants": _build_ptp_event_participants(target),
    }


def _update_ptp_event_status(event_name, status):
    event = frappe.get_doc("Event", event_name)
    if event.status == status:
        return
    event.status = status
    event.save(ignore_permissions=True)


def _build_ptp_event_participants(target):
    if not target:
        return []

    participant_id = target.get("user_id") or target.get("employee")
    if not participant_id:
        return []

    return [
        {
            "reference_doctype": "User" if target.get("user_id") else "Employee",
            "reference_docname": participant_id,
            "email": target.get("email"),
        }
    ]
