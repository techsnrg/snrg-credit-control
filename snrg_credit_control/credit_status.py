import frappe
from frappe.utils import add_days, fmt_money, getdate, today


DEFAULT_THRESHOLD_DAYS = 75


def zero(value):
    return value or 0


def get_threshold(customer):
    days = frappe.db.get_value("Customer", customer, "custom_credit_lock_days")
    try:
        return int(days) if days else DEFAULT_THRESHOLD_DAYS
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLD_DAYS


def get_overdue_invoices(customer, company, cutoff):
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


def get_credit_limit(customer, company):
    return frappe.db.get_value(
        "Customer Credit Limit",
        {"parent": customer, "company": company},
        "credit_limit",
    ) or 0


def get_total_outstanding(customer, company):
    value = frappe.db.sql(
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
    return value or 0


def get_advance_balance(customer, company):
    value = frappe.db.sql(
        """
        SELECT ABS(COALESCE(SUM(outstanding_amount), 0))
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND is_return  = 0
          AND customer   = %s
          AND company    = %s
          AND outstanding_amount < 0
        """,
        (customer, company),
    )[0][0]
    return value or 0


def build_credit_snapshot(customer, company, amount=0, currency=None, detail_limit=15, more_prefix="..."):
    today_date = getdate(today())
    threshold = get_threshold(customer)
    cutoff = add_days(today_date, -threshold)
    resolved_currency = (
        currency
        or frappe.db.get_value("Company", company, "default_currency")
        or "INR"
    )

    rows = get_overdue_invoices(customer, company, cutoff)
    overdue_count = len(rows)
    total_overdue = sum(row.outstanding_amount for row in rows) if rows else 0
    credit_limit = get_credit_limit(customer, company)
    total_outstanding = get_total_outstanding(customer, company)
    effective_ar = max(total_outstanding, 0)
    current_amount = zero(amount)
    limit_breach = bool(credit_limit and (effective_ar + current_amount) > credit_limit)
    advances = get_advance_balance(customer, company)

    detail_lines = []
    for row in rows[:detail_limit]:
        age = (today_date - getdate(row.posting_date)).days
        detail_lines.append(
            f"{row.name} ({fmt_money(row.outstanding_amount, currency=resolved_currency)}, {age}d)"
        )
    if overdue_count > detail_limit:
        detail_lines.append(f"{more_prefix} +{overdue_count - detail_limit} more")

    if overdue_count > 0:
        status = "Credit Hold"
        reason_code = "Overdue>Terms"
    elif limit_breach:
        status = "Credit Hold"
        reason_code = "Over-Limit"
    else:
        status = "Credit OK"
        reason_code = ""

    return {
        "today_date": today_date,
        "threshold": threshold,
        "cutoff": cutoff,
        "currency": resolved_currency,
        "rows": rows,
        "overdue_count": overdue_count,
        "total_overdue": total_overdue,
        "credit_limit": credit_limit,
        "total_outstanding": total_outstanding,
        "effective_ar": effective_ar,
        "amount": current_amount,
        "limit_breach": limit_breach,
        "needs_review": overdue_count > 0 or limit_breach,
        "advances": advances,
        "detail_lines": detail_lines,
        "details": "; ".join(detail_lines),
        "status": status,
        "reason_code": reason_code,
    }


def stamp_credit_fields(doc, snapshot):
    doc.custom_snrg_overdue_count_terms = snapshot["overdue_count"]
    doc.custom_snrg_overdue_amount_terms = snapshot["total_overdue"]
    doc.custom_snrg_exposure_at_check = snapshot["effective_ar"]
    doc.custom_snrg_credit_limit_at_check = snapshot["credit_limit"]
    doc.custom_snrg_credit_check_details = snapshot["details"]
    doc.custom_snrg_credit_check_status = snapshot["status"]
    doc.custom_snrg_credit_check_reason_code = snapshot["reason_code"]


def reset_credit_fields(doc):
    doc.custom_snrg_credit_check_status = "Not Run"
    doc.custom_snrg_credit_check_reason_code = ""
    doc.custom_snrg_overdue_count_terms = 0
    doc.custom_snrg_overdue_amount_terms = 0
    doc.custom_snrg_exposure_at_check = 0
    doc.custom_snrg_credit_limit_at_check = 0
    doc.custom_snrg_credit_check_details = ""
