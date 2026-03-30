import frappe

from snrg_credit_control.credit_status import (
    build_credit_snapshot,
    render_credit_details_html,
    reset_credit_fields,
    stamp_credit_fields,
)


def validate(doc, method=None):
    if not (doc.get("party_name") and doc.get("company")):
        reset_credit_fields(doc)
        return

    if doc.quotation_to != "Customer":
        reset_credit_fields(doc)
        return

    snapshot = build_credit_snapshot(
        customer=doc.party_name,
        company=doc.company,
        amount=doc.grand_total or doc.rounded_total,
        currency=doc.currency,
    )
    stamp_credit_fields(doc, snapshot)


@frappe.whitelist()
def get_credit_preview(customer, company, currency=None):
    if not customer or not company:
        return {}

    snapshot = build_credit_snapshot(
        customer=customer,
        company=company,
        amount=0,
        currency=currency,
    )

    return {
        "status": snapshot["status"],
        "reason_code": snapshot["reason_code"],
        "overdue_count": snapshot["overdue_count"],
        "total_overdue": snapshot["total_overdue"],
        "effective_ar": snapshot["effective_ar"],
        "credit_limit": snapshot["credit_limit"],
        "currency": snapshot["currency"],
    }


@frappe.whitelist()
def get_credit_details(customer, company, customer_name=None, currency=None, amount=0):
    if not customer or not company:
        return {}

    snapshot = build_credit_snapshot(
        customer=customer,
        company=company,
        amount=amount,
        currency=currency,
    )

    html = render_credit_details_html(
        snapshot=snapshot,
        customer=customer,
        customer_name=customer_name or customer,
    )

    return {
        "title": "Customer Credit Details",
        "html": html,
    }
