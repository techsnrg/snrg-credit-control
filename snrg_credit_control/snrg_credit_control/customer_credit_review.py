from __future__ import annotations

import frappe
from frappe.utils import flt, now_datetime

from snrg_credit_control.recommended_credit_limit import get_credit_review_rows


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


def _get_currency(company: str) -> str:
    return frappe.db.get_value("Company", company, "default_currency") or "INR"


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
