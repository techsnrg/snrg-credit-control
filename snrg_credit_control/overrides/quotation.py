import frappe

from snrg_credit_control.credit_status import (
    build_credit_snapshot,
    render_credit_details_html,
    reset_credit_fields,
    stamp_credit_clearance_date,
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
    previous_status = None
    if not doc.is_new():
        previous_status = frappe.db.get_value("Quotation", doc.name, "custom_snrg_credit_check_status")
    stamp_credit_fields(doc, snapshot)
    stamp_credit_clearance_date(doc, snapshot, previous_status=previous_status)


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
        "details": snapshot["details"],
        "currency": snapshot["currency"],
        "checked_on": snapshot["checked_on"],
    }


@frappe.whitelist()
def refresh_credit_status(customer, company, currency=None, amount=0, quotation_name=None):
    if not customer or not company:
        return {}

    quotation = None
    snapshot = build_credit_snapshot(
        customer=customer,
        company=company,
        amount=amount,
        currency=currency,
    )

    if quotation_name and frappe.db.exists("Quotation", quotation_name):
        quotation = frappe.get_doc("Quotation", quotation_name)
        previous_status = frappe.db.get_value("Quotation", quotation.name, "custom_snrg_credit_check_status")
        stamp_credit_fields(quotation, snapshot)
        stamp_credit_clearance_date(quotation, snapshot, previous_status=previous_status)

        fields_to_persist = [
            "custom_snrg_credit_check_status",
            "custom_snrg_credit_check_reason_code",
            "custom_snrg_overdue_count_terms",
            "custom_snrg_overdue_amount_terms",
            "custom_snrg_exposure_at_check",
            "custom_snrg_credit_limit_at_check",
            "custom_snrg_credit_check_details",
            "custom_snrg_credit_checked_on",
            "custom_credit_clearance_date",
        ]
        for fieldname in fields_to_persist:
            quotation.db_set(fieldname, quotation.get(fieldname), update_modified=False)

    return {
        "status": snapshot["status"],
        "reason_code": snapshot["reason_code"],
        "overdue_count": snapshot["overdue_count"],
        "total_overdue": snapshot["total_overdue"],
        "effective_ar": snapshot["effective_ar"],
        "credit_limit": snapshot["credit_limit"],
        "currency": snapshot["currency"],
        "details": snapshot["details"],
        "checked_on": snapshot["checked_on"],
        "credit_clearance_date": quotation.get("custom_credit_clearance_date") if quotation else None,
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
