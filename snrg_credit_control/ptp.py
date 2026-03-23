import frappe
from frappe.utils import fmt_money, getdate, today

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
