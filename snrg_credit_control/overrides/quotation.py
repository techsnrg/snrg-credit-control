import frappe
from frappe.utils import add_days, fmt_money, getdate, today


DEFAULT_THRESHOLD_DAYS = 75


def _get_threshold(customer):
    days = frappe.db.get_value("Customer", customer, "custom_credit_lock_days")
    try:
        return int(days) if days else DEFAULT_THRESHOLD_DAYS
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLD_DAYS


def _get_overdue_invoices(customer, company, cutoff):
    return frappe.get_all(
        "Sales Invoice",
        filters={
            "docstatus": 1,
            "is_return": 0,
            "customer": customer,
            "company": company,
            "outstanding_amount": (">", 0),
            "posting_date": ("<=", cutoff),
        },
        fields=["name", "posting_date", "outstanding_amount"],
        order_by="posting_date asc",
    )


def _get_credit_limit(customer, company):
    return frappe.db.get_value(
        "Customer Credit Limit",
        {"parent": customer, "company": company},
        "credit_limit",
    ) or 0


def _get_total_outstanding(customer, company):
    val = frappe.db.sql(
        """
        SELECT COALESCE(SUM(outstanding_amount), 0)
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND is_return  = 0
          AND customer   = %s
          AND company    = %s
        """,
        (customer, company),
    )[0][0]
    return val or 0


def _val(x):
    return x or 0


def validate(doc, method=None):
    if not (doc.get("party_name") and doc.get("company")):
        _reset_credit_fields(doc)
        return

    if doc.quotation_to != "Customer":
        _reset_credit_fields(doc)
        return

    _compute_credit_fields(doc)


def _reset_credit_fields(doc):
    doc.custom_snrg_credit_check_status = "Not Run"
    doc.custom_snrg_credit_check_reason_code = ""
    doc.custom_snrg_overdue_count_terms = 0
    doc.custom_snrg_overdue_amount_terms = 0
    doc.custom_snrg_exposure_at_check = 0
    doc.custom_snrg_credit_limit_at_check = 0
    doc.custom_snrg_credit_check_details = ""


def _compute_credit_fields(doc):
    today_date = getdate(today())
    threshold = _get_threshold(doc.party_name)
    cutoff = add_days(today_date, -threshold)
    currency = doc.currency or frappe.db.get_value("Company", doc.company, "default_currency") or "INR"

    rows = _get_overdue_invoices(doc.party_name, doc.company, cutoff)
    count = len(rows)
    total_overdue = sum(r.outstanding_amount for r in rows) if rows else 0
    credit_limit = _get_credit_limit(doc.party_name, doc.company)
    total_outstanding = _get_total_outstanding(doc.party_name, doc.company)
    effective_ar = max(total_outstanding, 0)
    quotation_amount = _val(doc.grand_total or doc.rounded_total)
    limit_breach = bool(credit_limit and (effective_ar + quotation_amount) > credit_limit)

    detail_lines = []
    for r in rows[:15]:
        age = (today_date - getdate(r.posting_date)).days
        detail_lines.append(
            f"{r.name} ({fmt_money(r.outstanding_amount, currency=currency)}, {age}d)"
        )
    if count > 15:
        detail_lines.append(f"... +{count - 15} more")

    doc.custom_snrg_overdue_count_terms = count
    doc.custom_snrg_overdue_amount_terms = total_overdue
    doc.custom_snrg_exposure_at_check = effective_ar
    doc.custom_snrg_credit_limit_at_check = credit_limit
    doc.custom_snrg_credit_check_details = "; ".join(detail_lines)

    if count > 0:
        doc.custom_snrg_credit_check_status = "Credit Hold"
        doc.custom_snrg_credit_check_reason_code = "Overdue>Terms"
    elif limit_breach:
        doc.custom_snrg_credit_check_status = "Credit Hold"
        doc.custom_snrg_credit_check_reason_code = "Over-Limit"
    else:
        doc.custom_snrg_credit_check_status = "Credit OK"
        doc.custom_snrg_credit_check_reason_code = ""
