from __future__ import annotations

import frappe
from frappe.utils import add_months, flt, getdate, now_datetime, today


ALLOWED_SYNC_ROLES = {"System Manager", "Credit Approver", "Accounts Manager"}


def get_credit_review_rows(company: str, customer: str | None = None):
    six_months_ago = add_months(getdate(today()), -6)
    customer_filter = "AND c.name = %(customer)s" if customer else ""
    security_cheque_join = _get_security_cheque_join()
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


@frappe.whitelist()
def sync_recommended_credit_limits(company: str):
    _require_sync_permission()
    if not company:
        frappe.throw("Company is required.")

    recommendation_rows = {
        row["customer_code"]: row for row in get_credit_review_rows(company)
    }
    active_customers = frappe.get_all("Customer", filters={"disabled": 0}, pluck="name")
    existing_rows = frappe.get_all(
        "Customer Credit Limit",
        filters={"company": company},
        fields=["name", "parent"],
        order_by="parent asc, idx asc",
    )

    row_by_customer = {}
    duplicate_rows = 0
    for row in existing_rows:
        if row.parent in row_by_customer:
            duplicate_rows += 1
            continue
        row_by_customer[row.parent] = row.name

    now = now_datetime()
    updated = 0
    created = 0
    zero_recommendations = 0

    for customer in active_customers:
        recommended_limit = flt(recommendation_rows.get(customer, {}).get("recommended_credit_limit"))
        if not recommended_limit:
            zero_recommendations += 1

        row_name = row_by_customer.get(customer)
        if row_name:
            frappe.db.set_value(
                "Customer Credit Limit",
                row_name,
                {
                    "custom_snrg_recommended_credit_limit": recommended_limit,
                    "custom_snrg_recommended_credit_limit_updated_on": now,
                },
                update_modified=False,
            )
            updated += 1
            continue

        customer_doc = frappe.get_doc("Customer", customer)
        customer_doc.append(
            "credit_limits",
            {
                "company": company,
                "custom_snrg_recommended_credit_limit": recommended_limit,
                "custom_snrg_recommended_credit_limit_updated_on": now,
            },
        )
        customer_doc.save(ignore_permissions=True)
        created += 1

    frappe.db.commit()

    return {
        "company": company,
        "processed": len(active_customers),
        "updated": updated,
        "created": created,
        "zero_recommendations": zero_recommendations,
        "duplicate_company_rows_skipped": duplicate_rows,
        "updated_on": str(now),
    }


def _require_sync_permission():
    if not ALLOWED_SYNC_ROLES.intersection(set(frappe.get_roles())):
        frappe.throw("You are not allowed to sync recommended credit limits.")


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
