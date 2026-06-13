from __future__ import annotations

import frappe
from frappe.utils import add_months, flt, getdate, now_datetime, today


ALLOWED_REFRESH_ROLES = {
    "System Manager",
    "Credit Approver",
    "Accounts Manager",
    "Sales Manager",
}


def get_credit_review_rows(company: str, customer: str | None = None):
    six_months_ago = add_months(getdate(today()), -6)
    customer_filter = "AND c.name = %(customer)s" if customer else ""
    security_cheque_join = _get_security_cheque_join()
    scope_filter = (
        ""
        if customer
        else """
          AND (
              COALESCE(outstanding.current_outstanding, 0) > 0
              OR COALESCE(sales_6m.sales_last_6m, 0) > 0
              OR COALESCE(payments_6m.payment_last_6m, 0) > 0
              OR COALESCE(credit.credit_limit, 0) > 0
          )
        """
    )
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
        {security_cheque_join}
        WHERE c.disabled = 0
          {customer_filter}
          {scope_filter}
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


@frappe.whitelist()
def refresh_customer_recommended_limits(customer: str):
    _require_refresh_permission()
    if not customer:
        frappe.throw("Customer is required.")

    customer_doc = frappe.get_doc("Customer", customer)
    rows = [row for row in (customer_doc.credit_limits or []) if row.company]
    if not rows:
        frappe.throw("Add at least one company row in the Credit Limit table first.")

    now = now_datetime()
    updated_rows = []

    for row in rows:
        review_rows = get_credit_review_rows(row.company, customer=customer)
        review = review_rows[0] if review_rows else {}
        recommended = flt(review.get("recommended_credit_limit"))
        row.custom_snrg_recommended_credit_limit = recommended
        row.custom_snrg_recommended_credit_limit_updated_on = now
        updated_rows.append(
            {
                "company": row.company,
                "recommended_credit_limit": recommended,
                "updated_on": str(now),
            }
        )

    customer_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "customer": customer,
        "updated_rows": updated_rows,
        "updated_on": str(now),
    }


def _require_refresh_permission():
    if ALLOWED_REFRESH_ROLES.intersection(set(frappe.get_roles())):
        return
    frappe.throw("You are not allowed to refresh recommended credit limits.")


def _get_security_cheque_join() -> str:
    if frappe.db.table_exists("Security Cheques - Active"):
        return """
        LEFT JOIN (
            SELECT
                sca.parent AS customer,
                1 AS has_security_cheque
            FROM `tabSecurity Cheques - Active` sca
            WHERE sca.parenttype = 'Customer'
              AND COALESCE(sca.bank, '') != ''
            GROUP BY sca.parent
        ) sec ON sec.customer = c.name
        """

    return """
    LEFT JOIN (
        SELECT
            NULL AS customer,
            0 AS has_security_cheque
    ) sec ON 1 = 0
    """


def _get_months_used(first_payment_date, today_date) -> float:
    if not first_payment_date:
        return 0
    return min(((today_date - getdate(first_payment_date)).days + 1) / 30, 6)


def _days_since(date_value, today_date):
    if not date_value:
        return None
    return (today_date - getdate(date_value)).days
