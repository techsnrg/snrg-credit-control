from __future__ import annotations

import frappe
from frappe.utils import add_months, flt, getdate, now_datetime, today


def get_context(context):
    context.no_cache = 1
    return context


@frappe.whitelist()
def get_page_data(company: str):
    if not company:
        frappe.throw("Company is required.")

    rows = _get_rows(company)
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

    rows = _get_rows(company, customer=customer)
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


def _get_rows(company: str, customer: str | None = None):
    six_months_ago = add_months(getdate(today()), -6)
    customer_filter = "AND c.name = %(customer)s" if customer else ""
    values = {"company": company, "six_months_ago": six_months_ago}
    if customer:
        values["customer"] = customer

    rows = frappe.db.sql(
        f"""
        SELECT
            c.name AS customer_code,
            c.customer_name,
            c.customer_group,
            COALESCE(sec.has_security_cheque, 0) AS has_security_cheque,
            COALESCE(sales_6m.sales_last_6m, 0) AS sales_last_6m,
            COALESCE(payments_6m.payment_last_6m, 0) AS payment_last_6m,
            payments_6m.first_payment_date_6m,
            COALESCE(outstanding.current_outstanding, 0) AS current_outstanding,
            COALESCE(outstanding.open_invoice_count, 0) AS open_invoice_count,
            COALESCE(outstanding.overdue_outstanding, 0) AS overdue_outstanding,
            COALESCE(outstanding.not_yet_due_outstanding, 0) AS not_yet_due_outstanding,
            outstanding.max_days_of_ar,
            COALESCE(credit.credit_limit, 0) AS current_credit_limit,
            sales_all.last_sales_date,
            payments_all.last_payment_date
        FROM `tabCustomer` c
        LEFT JOIN (
            SELECT
                si.customer,
                SUM(si.base_grand_total) AS sales_last_6m
            FROM `tabSales Invoice` si
            WHERE si.docstatus = 1
              AND si.is_return = 0
              AND si.company = %(company)s
              AND si.posting_date BETWEEN %(six_months_ago)s AND CURDATE()
            GROUP BY si.customer
        ) sales_6m ON sales_6m.customer = c.name
        LEFT JOIN (
            SELECT
                si.customer,
                MAX(si.posting_date) AS last_sales_date
            FROM `tabSales Invoice` si
            WHERE si.docstatus = 1
              AND si.is_return = 0
              AND si.company = %(company)s
            GROUP BY si.customer
        ) sales_all ON sales_all.customer = c.name
        LEFT JOIN (
            SELECT
                pe.party AS customer,
                SUM(pe.paid_amount) AS payment_last_6m,
                MIN(pe.posting_date) AS first_payment_date_6m
            FROM `tabPayment Entry` pe
            WHERE pe.party_type = 'Customer'
              AND pe.docstatus = 1
              AND pe.company = %(company)s
              AND pe.posting_date BETWEEN %(six_months_ago)s AND CURDATE()
            GROUP BY pe.party
        ) payments_6m ON payments_6m.customer = c.name
        LEFT JOIN (
            SELECT
                pe.party AS customer,
                MAX(pe.posting_date) AS last_payment_date
            FROM `tabPayment Entry` pe
            WHERE pe.party_type = 'Customer'
              AND pe.docstatus = 1
              AND pe.company = %(company)s
            GROUP BY pe.party
        ) payments_all ON payments_all.customer = c.name
        LEFT JOIN (
            SELECT
                si.customer,
                SUM(CASE WHEN si.outstanding_amount > 0 THEN si.outstanding_amount ELSE 0 END) AS current_outstanding,
                SUM(CASE WHEN si.outstanding_amount > 0 AND si.due_date < CURDATE() THEN si.outstanding_amount ELSE 0 END) AS overdue_outstanding,
                SUM(CASE WHEN si.outstanding_amount > 0 AND (si.due_date >= CURDATE() OR si.due_date IS NULL) THEN si.outstanding_amount ELSE 0 END) AS not_yet_due_outstanding,
                COUNT(CASE WHEN si.outstanding_amount > 0 THEN 1 END) AS open_invoice_count,
                DATEDIFF(CURDATE(), MIN(CASE WHEN si.outstanding_amount > 0 THEN si.posting_date END)) AS max_days_of_ar
            FROM `tabSales Invoice` si
            WHERE si.docstatus = 1
              AND si.is_return = 0
              AND si.company = %(company)s
            GROUP BY si.customer
        ) outstanding ON outstanding.customer = c.name
        LEFT JOIN (
            SELECT
                ccl.parent AS customer,
                MAX(ccl.credit_limit) AS credit_limit
            FROM `tabCustomer Credit Limit` ccl
            WHERE ccl.company = %(company)s
            GROUP BY ccl.parent
        ) credit ON credit.customer = c.name
        LEFT JOIN (
            SELECT
                sca.parent AS customer,
                1 AS has_security_cheque
            FROM `tabSecurity Cheques - Active` sca
            WHERE sca.parenttype = 'Customer'
              AND COALESCE(sca.bank, '') != ''
            GROUP BY sca.parent
        ) sec ON sec.customer = c.name
        WHERE c.disabled = 0
          {customer_filter}
          AND (
              COALESCE(outstanding.current_outstanding, 0) > 0
              OR COALESCE(sales_6m.sales_last_6m, 0) > 0
              OR COALESCE(payments_6m.payment_last_6m, 0) > 0
              OR COALESCE(credit.credit_limit, 0) > 0
          )
        ORDER BY
            CASE
                WHEN COALESCE(credit.credit_limit, 0) > 0 THEN (COALESCE(outstanding.current_outstanding, 0) / credit.credit_limit)
                ELSE 0
            END DESC,
            COALESCE(outstanding.current_outstanding, 0) DESC,
            c.name ASC
        """,
        values,
        as_dict=True,
    )

    today_date = getdate(today())
    payload = []

    for row in rows:
        payment_last_6m = flt(row.payment_last_6m)
        sales_last_6m = flt(row.sales_last_6m)
        current_outstanding = flt(row.current_outstanding)
        current_credit_limit = flt(row.current_credit_limit)
        months_used = _get_months_used(row.first_payment_date_6m, today_date)
        avg_monthly_payment = round(payment_last_6m / months_used, 2) if months_used else 0
        collection_ratio = round((payment_last_6m / sales_last_6m) * 100, 2) if sales_last_6m else 0
        remaining_limit = round(current_credit_limit - current_outstanding, 2)
        over_limit_amount = round(max(current_outstanding - current_credit_limit, 0), 2)
        credit_utilization = round((current_outstanding / current_credit_limit) * 100, 2) if current_credit_limit else 0
        recommended_credit_limit = round(avg_monthly_payment * 2.5, 2) if row.has_security_cheque else 0
        gap_vs_recommended = round(recommended_credit_limit - current_credit_limit, 2)

        last_sales_date = row.last_sales_date
        last_payment_date = row.last_payment_date

        payload.append(
            {
                "customer_code": row.customer_code,
                "customer_name": row.customer_name or row.customer_code,
                "customer_group": row.customer_group,
                "security_cheque_available": "Yes" if row.has_security_cheque else "No",
                "sales_last_6m": round(sales_last_6m, 2),
                "payment_last_6m": round(payment_last_6m, 2),
                "collection_ratio": collection_ratio,
                "avg_monthly_payment": avg_monthly_payment,
                "months_used": round(months_used, 2) if months_used else 0,
                "days_since_cutoff": _days_since(row.first_payment_date_6m, today_date),
                "current_outstanding": round(current_outstanding, 2),
                "current_credit_limit": round(current_credit_limit, 2),
                "remaining_limit": remaining_limit,
                "over_limit_amount": over_limit_amount,
                "open_invoice_count": int(row.open_invoice_count or 0),
                "overdue_outstanding": round(flt(row.overdue_outstanding), 2),
                "not_yet_due_outstanding": round(flt(row.not_yet_due_outstanding), 2),
                "max_days_of_ar": int(row.max_days_of_ar or 0) if row.max_days_of_ar is not None else None,
                "credit_utilization": credit_utilization,
                "recommended_credit_limit": recommended_credit_limit,
                "gap_vs_recommended": gap_vs_recommended,
                "last_sales_date": str(last_sales_date) if last_sales_date else None,
                "days_since_last_invoice": _days_since(last_sales_date, today_date),
                "last_payment_date": str(last_payment_date) if last_payment_date else None,
                "days_since_last_payment": _days_since(last_payment_date, today_date),
            }
        )

    return payload


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


def _get_months_used(first_payment_date, today_date) -> float:
    if not first_payment_date:
        return 0
    return min(((today_date - getdate(first_payment_date)).days + 1) / 30, 6)


def _days_since(date_value, today_date):
    if not date_value:
        return None
    return (today_date - getdate(date_value)).days


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
