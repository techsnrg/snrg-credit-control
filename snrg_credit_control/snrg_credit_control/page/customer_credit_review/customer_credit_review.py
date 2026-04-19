from __future__ import annotations

import frappe
from frappe.utils import flt, now_datetime
from snrg_credit_control.recommended_credit_limit import get_credit_review_rows, sync_recommended_credit_limits as run_credit_limit_sync


def get_context(context):
    context.no_cache = 1
    return context


@frappe.whitelist()
def get_page_data(company: str):
    if not company:
        frappe.throw("Company is required.")

    rows = get_credit_review_rows(company)
    columns = _get_columns()
    summary = _build_summary(rows)

    return {
        "generated_on": str(now_datetime()),
        "company": company,
        "currency": _get_currency(company),
        "columns": columns,
        "rows": rows,
        "summary": summary,
    }


@frappe.whitelist()
def get_customer_detail(company: str, customer: str):
    if not company:
        frappe.throw("Company is required.")
    if not customer:
        frappe.throw("Customer is required.")

    rows = get_credit_review_rows(company, customer=customer)
    if not rows:
        frappe.throw(f"Customer {customer} was not found for the selected company scope.")

    detail = rows[0]
    detail["recent_invoices"] = _get_recent_invoices(company, customer)
    detail["recent_payments"] = _get_recent_payments(company, customer)
    detail["generated_on"] = str(now_datetime())
    detail["company"] = company
    detail["currency"] = _get_currency(company)

    return detail


@frappe.whitelist()
def sync_recommended_limits(company: str):
    return run_credit_limit_sync(company)


def _get_currency(company: str) -> str:
    return frappe.db.get_value("Company", company, "default_currency") or "INR"


def _get_columns():
    return [
        {"fieldname": "customer_code", "label": "Customer Code", "fieldtype": "Link", "options": "Customer", "width": 140},
        {"fieldname": "customer_name", "label": "Customer Name", "fieldtype": "Data", "width": 220},
        {"fieldname": "customer_group", "label": "Customer Group", "fieldtype": "Data", "width": 160},
        {"fieldname": "security_cheque_available", "label": "Security Cheque", "fieldtype": "Data", "width": 120},
        {"fieldname": "sales_last_6m", "label": "Sales (Last 6M)", "fieldtype": "Currency", "width": 150},
        {"fieldname": "payment_last_6m", "label": "Payment (Last 6M)", "fieldtype": "Currency", "width": 150},
        {"fieldname": "collection_ratio", "label": "Collection Ratio %", "fieldtype": "Percent", "width": 130},
        {"fieldname": "avg_monthly_payment", "label": "Avg Monthly Payment", "fieldtype": "Currency", "width": 170},
        {"fieldname": "months_used", "label": "Months Used", "fieldtype": "Float", "width": 110},
        {"fieldname": "days_since_cutoff", "label": "Days Since Cutoff", "fieldtype": "Int", "width": 130},
        {"fieldname": "current_outstanding", "label": "Current Outstanding", "fieldtype": "Currency", "width": 160},
        {"fieldname": "current_credit_limit", "label": "Current Credit Limit", "fieldtype": "Currency", "width": 160},
        {"fieldname": "remaining_limit", "label": "Remaining Limit", "fieldtype": "Currency", "width": 150},
        {"fieldname": "over_limit_amount", "label": "Over Limit Amount", "fieldtype": "Currency", "width": 150},
        {"fieldname": "open_invoice_count", "label": "Open Invoices", "fieldtype": "Int", "width": 120},
        {"fieldname": "overdue_outstanding", "label": "Overdue Outstanding", "fieldtype": "Currency", "width": 160},
        {"fieldname": "not_yet_due_outstanding", "label": "Not Yet Due", "fieldtype": "Currency", "width": 150},
        {"fieldname": "max_days_of_ar", "label": "Max Days of AR", "fieldtype": "Int", "width": 120},
        {"fieldname": "credit_utilization", "label": "Credit Utilization %", "fieldtype": "Percent", "width": 145},
        {"fieldname": "recommended_credit_limit", "label": "Recommended Limit", "fieldtype": "Currency", "width": 165},
        {"fieldname": "gap_vs_recommended", "label": "Gap vs Recommended", "fieldtype": "Currency", "width": 160},
        {"fieldname": "last_sales_date", "label": "Last Sales Date", "fieldtype": "Date", "width": 120},
        {"fieldname": "days_since_last_invoice", "label": "Days Since Last Invoice", "fieldtype": "Int", "width": 150},
        {"fieldname": "last_payment_date", "label": "Last Payment Date", "fieldtype": "Date", "width": 125},
        {"fieldname": "days_since_last_payment", "label": "Days Since Last Payment", "fieldtype": "Int", "width": 155},
        {"fieldname": "actions", "label": "Actions", "fieldtype": "HTML", "width": 180},
    ]


def _get_recent_invoices(company: str, customer: str):
    rows = frappe.db.sql(
        """
        SELECT
            si.name,
            si.posting_date,
            si.due_date,
            si.base_grand_total,
            si.outstanding_amount,
            DATEDIFF(CURDATE(), si.posting_date) AS age_days
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.is_return = 0
          AND si.company = %(company)s
          AND si.customer = %(customer)s
        ORDER BY si.posting_date DESC, si.name DESC
        LIMIT 8
        """,
        {"company": company, "customer": customer},
        as_dict=True,
    )

    return [
        {
            "name": row.name,
            "posting_date": str(row.posting_date) if row.posting_date else None,
            "due_date": str(row.due_date) if row.due_date else None,
            "invoice_amount": round(flt(row.base_grand_total), 2),
            "outstanding_amount": round(flt(row.outstanding_amount), 2),
            "age_days": int(row.age_days or 0) if row.age_days is not None else None,
        }
        for row in rows
    ]


def _get_recent_payments(company: str, customer: str):
    rows = frappe.db.sql(
        """
        SELECT
            pe.name,
            pe.posting_date,
            pe.mode_of_payment,
            pe.reference_no,
            pe.paid_amount
        FROM `tabPayment Entry` pe
        WHERE pe.docstatus = 1
          AND pe.party_type = 'Customer'
          AND pe.company = %(company)s
          AND pe.party = %(customer)s
        ORDER BY pe.posting_date DESC, pe.name DESC
        LIMIT 8
        """,
        {"company": company, "customer": customer},
        as_dict=True,
    )

    return [
        {
            "name": row.name,
            "posting_date": str(row.posting_date) if row.posting_date else None,
            "mode_of_payment": row.mode_of_payment,
            "reference_no": row.reference_no,
            "paid_amount": round(flt(row.paid_amount), 2),
        }
        for row in rows
    ]


def _build_summary(rows):
    customer_count = len(rows)
    total_outstanding = sum(flt(row.get("current_outstanding")) for row in rows)
    total_overdue = sum(flt(row.get("overdue_outstanding")) for row in rows)
    total_over_limit = sum(flt(row.get("over_limit_amount")) for row in rows)
    total_payments = sum(flt(row.get("payment_last_6m")) for row in rows)
    total_sales = sum(flt(row.get("sales_last_6m")) for row in rows)

    return [
        {"label": "Customers In Scope", "value": customer_count, "datatype": "Int", "tone": "slate"},
        {"label": "Current Outstanding", "value": round(total_outstanding, 2), "datatype": "Currency", "tone": "blue"},
        {"label": "Overdue Outstanding", "value": round(total_overdue, 2), "datatype": "Currency", "tone": "amber"},
        {"label": "Over Limit Amount", "value": round(total_over_limit, 2), "datatype": "Currency", "tone": "red"},
        {"label": "Payments (Last 6M)", "value": round(total_payments, 2), "datatype": "Currency", "tone": "teal"},
        {"label": "Sales (Last 6M)", "value": round(total_sales, 2), "datatype": "Currency", "tone": "purple"},
    ]
