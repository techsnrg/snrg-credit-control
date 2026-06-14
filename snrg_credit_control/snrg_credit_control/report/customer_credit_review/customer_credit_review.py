from __future__ import annotations

import frappe
from frappe.utils import flt

from snrg_credit_control.recommended_credit_limit import get_credit_review_rows


def execute(filters=None):
    filters = frappe._dict(filters or {})
    _validate_filters(filters)

    rows = get_credit_review_rows(filters.company, customer=filters.get("customer"))
    rows = _apply_search(rows, filters.get("search"))
    return _get_columns(), rows, None, None, _get_summary(rows)


def _validate_filters(filters):
    if not filters.get("company"):
        frappe.throw("Company is required.")


def _get_columns():
    return [
        {"fieldname": "customer_code", "label": "Customer Code", "fieldtype": "Link", "options": "Customer", "width": 145},
        {"fieldname": "customer_name", "label": "Customer Name", "fieldtype": "Data", "width": 220},
        {"fieldname": "customer_group", "label": "Customer Group", "fieldtype": "Data", "width": 160},
        {"fieldname": "security_cheque_available", "label": "Security Cheque", "fieldtype": "Data", "width": 125},
        {"fieldname": "current_outstanding", "label": "Current Outstanding", "fieldtype": "Currency", "width": 160},
        {"fieldname": "current_credit_limit", "label": "Current Credit Limit", "fieldtype": "Currency", "width": 160},
        {"fieldname": "recommended_credit_limit", "label": "Recommended Limit", "fieldtype": "Currency", "width": 165},
        {"fieldname": "gap_vs_recommended", "label": "Gap vs Recommended", "fieldtype": "Currency", "width": 165},
        {"fieldname": "remaining_limit", "label": "Remaining Limit", "fieldtype": "Currency", "width": 150},
        {"fieldname": "over_limit_amount", "label": "Over Limit Amount", "fieldtype": "Currency", "width": 155},
        {"fieldname": "credit_utilization", "label": "Credit Utilization %", "fieldtype": "Percent", "width": 150},
        {"fieldname": "overdue_outstanding", "label": "Overdue Outstanding", "fieldtype": "Currency", "width": 165},
        {"fieldname": "not_yet_due_outstanding", "label": "Not Yet Due", "fieldtype": "Currency", "width": 150},
        {"fieldname": "open_invoice_count", "label": "Open Invoices", "fieldtype": "Int", "width": 120},
        {"fieldname": "max_days_of_ar", "label": "Max Days of AR", "fieldtype": "Int", "width": 125},
        {"fieldname": "sales_last_6m", "label": "Sales (Last 6M)", "fieldtype": "Currency", "width": 150},
        {"fieldname": "payment_last_6m", "label": "Payment (Last 6M)", "fieldtype": "Currency", "width": 155},
        {"fieldname": "collection_ratio", "label": "Collection Ratio %", "fieldtype": "Percent", "width": 145},
        {"fieldname": "avg_monthly_payment", "label": "Avg Monthly Payment", "fieldtype": "Currency", "width": 175},
        {"fieldname": "months_used", "label": "Months Used", "fieldtype": "Float", "width": 115},
        {"fieldname": "days_since_cutoff", "label": "Days Since Cutoff", "fieldtype": "Int", "width": 135},
        {"fieldname": "last_sales_date", "label": "Last Sales Date", "fieldtype": "Date", "width": 125},
        {"fieldname": "days_since_last_invoice", "label": "Days Since Last Invoice", "fieldtype": "Int", "width": 155},
        {"fieldname": "last_payment_date", "label": "Last Payment Date", "fieldtype": "Date", "width": 135},
        {"fieldname": "days_since_last_payment", "label": "Days Since Last Payment", "fieldtype": "Int", "width": 160},
    ]


def _apply_search(rows, search_text):
    if not search_text:
        return rows

    needle = search_text.strip().lower()
    if not needle:
        return rows

    searchable_fields = (
        "customer_code",
        "customer_name",
        "customer_group",
        "security_cheque_available",
    )
    return [
        row
        for row in rows
        if any(needle in str(row.get(field) or "").lower() for field in searchable_fields)
    ]


def _get_summary(rows):
    customer_count = len(rows)
    total_outstanding = sum(flt(row.get("current_outstanding")) for row in rows)
    total_overdue = sum(flt(row.get("overdue_outstanding")) for row in rows)
    total_over_limit = sum(flt(row.get("over_limit_amount")) for row in rows)
    total_payments = sum(flt(row.get("payment_last_6m")) for row in rows)
    total_sales = sum(flt(row.get("sales_last_6m")) for row in rows)

    return [
        {"label": "Customers In Scope", "value": customer_count, "indicator": "Blue", "datatype": "Int"},
        {"label": "Current Outstanding", "value": round(total_outstanding, 2), "indicator": "Blue", "datatype": "Currency"},
        {"label": "Overdue Outstanding", "value": round(total_overdue, 2), "indicator": "Orange", "datatype": "Currency"},
        {"label": "Over Limit Amount", "value": round(total_over_limit, 2), "indicator": "Red" if total_over_limit else "Green", "datatype": "Currency"},
        {"label": "Payments (Last 6M)", "value": round(total_payments, 2), "indicator": "Green", "datatype": "Currency"},
        {"label": "Sales (Last 6M)", "value": round(total_sales, 2), "indicator": "Purple", "datatype": "Currency"},
    ]
