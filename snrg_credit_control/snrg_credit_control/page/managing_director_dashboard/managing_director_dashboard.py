from __future__ import annotations

import frappe
from frappe.utils import flt, formatdate, getdate, now_datetime, today

from snrg_credit_control.credit_status import DEFAULT_THRESHOLD_DAYS


def get_context(context):
    context.no_cache = 1
    return context


@frappe.whitelist()
def get_dashboard_data(company=None):
    so_filter = []
    invoice_filter = []
    ptp_filter = []
    notice_filter = []
    values = {}

    if company:
        so_filter.append("so.company = %(company)s")
        invoice_filter.append("si.company = %(company)s")
        ptp_filter.append("p.company = %(company)s")
        notice_filter.append("dn.company = %(company)s")
        values["company"] = company

    return {
        "generated_on": str(now_datetime()),
        "company": company or "All Companies",
        "currency": _get_currency(company),
        "companies": _get_companies(),
        "summary": _get_summary(so_filter, invoice_filter, ptp_filter, notice_filter, values),
        "sales_mix": _get_sales_mix(so_filter, invoice_filter, values),
        "approval_mix": _get_approval_mix(so_filter, values),
        "risk_mix": _get_risk_mix(so_filter, values),
        "sales_trend": _get_sales_trend(invoice_filter, values),
        "sales_leaders": _get_sales_leaders(invoice_filter, values),
        "execution_watchlist": _get_execution_watchlist(so_filter, values),
        "approval_queue": _get_approval_queue(so_filter, values),
        "blocked_orders": _get_blocked_orders(so_filter, values),
        "overdue_customers": _get_overdue_customers(invoice_filter, values),
        "ptp_watchlist": _get_ptp_watchlist(ptp_filter, values),
        "demand_notices": _get_demand_notices(notice_filter, values),
    }


def _get_currency(company):
    if company:
        return frappe.db.get_value("Company", company, "default_currency") or "INR"
    return frappe.defaults.get_global_default("currency") or "INR"


def _get_companies():
    return frappe.get_all("Company", pluck="name", order_by="name asc")


def _get_summary(so_filter, invoice_filter, ptp_filter, notice_filter, values):
    sales_values = dict(values)
    sales_values["month_start"] = _month_start()
    sales_values["ninety_days_ago"] = frappe.utils.add_days(today(), -89)
    sales_values["thirty_days_ago"] = frappe.utils.add_days(today(), -29)

    so_where = _build_where(["so.docstatus = 0"] + so_filter)
    submitted_so_where = _build_where(["so.docstatus = 1"] + so_filter)
    execution_where = _build_where(
        [
            "so.docstatus = 1",
            "IFNULL(so.status, '') NOT IN ('Closed', 'Completed', 'Cancelled')",
        ]
        + so_filter
    )
    invoice_where = _build_where(
        [
            "si.docstatus = 1",
            "si.is_return = 0",
            "si.outstanding_amount > 0",
        ]
        + invoice_filter
    )
    current_month_invoice_where = _build_where(
        [
            "si.docstatus = 1",
            "si.is_return = 0",
            "si.posting_date BETWEEN %(month_start)s AND CURDATE()",
        ]
        + invoice_filter
    )
    overdue_where = _build_where(
        [
            "si.docstatus = 1",
            "si.is_return = 0",
            "si.outstanding_amount > 0",
            f"si.posting_date <= DATE_SUB(CURDATE(), INTERVAL {DEFAULT_THRESHOLD_DAYS} DAY)",
        ]
        + invoice_filter
    )
    ptp_where = _build_where(["1 = 1"] + ptp_filter)
    notice_where = _build_where(["1 = 1"] + notice_filter)

    so_summary = frappe.db.sql(
        f"""
        SELECT
            COUNT(*) AS open_orders,
            SUM(CASE WHEN COALESCE(so.custom_credit_approval_status, '') = 'Pending' THEN 1 ELSE 0 END) AS pending_approvals,
            SUM(CASE WHEN COALESCE(so.custom_snrg_credit_check_status, '') = 'Credit Hold' THEN 1 ELSE 0 END) AS credit_hold_orders,
            SUM(CASE WHEN COALESCE(so.custom_snrg_credit_check_status, '') = 'Credit Hold' THEN so.grand_total ELSE 0 END) AS credit_hold_amount
        FROM `tabSales Order` so
        WHERE {so_where}
        """,
        values,
        as_dict=True,
    )[0]

    submitted_so_summary = frappe.db.sql(
        f"""
        SELECT
            COALESCE(SUM(CASE WHEN so.transaction_date BETWEEN %(thirty_days_ago)s AND CURDATE() THEN so.grand_total ELSE 0 END), 0) AS sales_last_30_days,
            COALESCE(SUM(so.grand_total), 0) AS total_submitted_orders
        FROM `tabSales Order` so
        WHERE {submitted_so_where}
        """,
        sales_values,
        as_dict=True,
    )[0]

    execution_summary = frappe.db.sql(
        f"""
        SELECT
            COUNT(*) AS live_orders,
            COALESCE(SUM(so.grand_total), 0) AS open_order_book,
            COALESCE(SUM(so.grand_total * (100 - COALESCE(so.per_billed, 0)) / 100), 0) AS pending_billing,
            COALESCE(SUM(so.grand_total * (100 - COALESCE(so.per_delivered, 0)) / 100), 0) AS pending_delivery
        FROM `tabSales Order` so
        WHERE {execution_where}
        """,
        values,
        as_dict=True,
    )[0]

    invoice_summary = frappe.db.sql(
        f"""
        SELECT
            COUNT(*) AS overdue_invoices,
            COALESCE(SUM(si.outstanding_amount), 0) AS total_outstanding
        FROM `tabSales Invoice` si
        WHERE {invoice_where}
        """,
        values,
        as_dict=True,
    )[0]

    month_invoice_summary = frappe.db.sql(
        f"""
        SELECT
            COUNT(*) AS invoice_count,
            COALESCE(SUM(si.base_grand_total), 0) AS invoiced_this_month
        FROM `tabSales Invoice` si
        WHERE {current_month_invoice_where}
        """,
        sales_values,
        as_dict=True,
    )[0]

    overdue_summary = frappe.db.sql(
        f"""
        SELECT
            COUNT(*) AS aged_invoices,
            COALESCE(SUM(si.outstanding_amount), 0) AS aged_outstanding
        FROM `tabSales Invoice` si
        WHERE {overdue_where}
        """,
        values,
        as_dict=True,
    )[0]

    ptp_summary = frappe.db.sql(
        f"""
        SELECT
            SUM(CASE WHEN p.status IN ('Pending', 'Partially Cleared') THEN 1 ELSE 0 END) AS active_ptps,
            SUM(CASE WHEN p.status = 'Broken' THEN 1 ELSE 0 END) AS broken_ptps,
            COALESCE(SUM(CASE WHEN p.status IN ('Pending', 'Partially Cleared') THEN p.difference_amount ELSE 0 END), 0) AS ptp_gap
        FROM `tabCredit PTP` p
        WHERE {ptp_where}
        """,
        values,
        as_dict=True,
    )[0]

    notice_summary = frappe.db.sql(
        f"""
        SELECT
            SUM(CASE WHEN dn.docstatus = 0 THEN 1 ELSE 0 END) AS draft_notices,
            SUM(CASE WHEN dn.docstatus = 1 THEN 1 ELSE 0 END) AS issued_notices,
            COALESCE(SUM(CASE WHEN dn.docstatus = 1 THEN dn.grand_total_due ELSE 0 END), 0) AS issued_notice_value
        FROM `tabDemand Notice` dn
        WHERE {notice_where}
        """,
        values,
        as_dict=True,
    )[0]

    return [
        {
            "label": "Pending Approvals",
            "value": int(so_summary.pending_approvals or 0),
            "helper": f"{int(so_summary.open_orders or 0)} open draft orders",
            "tone": "amber",
        },
        {
            "label": "Invoiced This Month",
            "value": flt(month_invoice_summary.invoiced_this_month),
            "helper": f"{int(month_invoice_summary.invoice_count or 0)} submitted invoices",
            "datatype": "Currency",
            "tone": "blue",
        },
        {
            "label": "Sales Last 30 Days",
            "value": flt(submitted_so_summary.sales_last_30_days),
            "helper": "Submitted order intake",
            "datatype": "Currency",
            "tone": "teal",
        },
        {
            "label": "Orders On Credit Hold",
            "value": int(so_summary.credit_hold_orders or 0),
            "helper": "Orders needing intervention",
            "tone": "red",
        },
        {
            "label": "Credit Hold Value",
            "value": flt(so_summary.credit_hold_amount),
            "helper": "Draft order value at risk",
            "datatype": "Currency",
            "tone": "red",
        },
        {
            "label": f"Overdue Receivables > {DEFAULT_THRESHOLD_DAYS} Days",
            "value": flt(overdue_summary.aged_outstanding),
            "helper": f"{int(overdue_summary.aged_invoices or 0)} aged invoices",
            "datatype": "Currency",
            "tone": "rose",
        },
        {
            "label": "Total Outstanding",
            "value": flt(invoice_summary.total_outstanding),
            "helper": f"{int(invoice_summary.overdue_invoices or 0)} live receivable invoices",
            "datatype": "Currency",
            "tone": "blue",
        },
        {
            "label": "Open Order Book",
            "value": flt(execution_summary.open_order_book),
            "helper": f"{int(execution_summary.live_orders or 0)} submitted live orders",
            "datatype": "Currency",
            "tone": "teal",
        },
        {
            "label": "Pending Billing",
            "value": flt(execution_summary.pending_billing),
            "helper": "Order value not fully billed yet",
            "datatype": "Currency",
            "tone": "amber",
        },
        {
            "label": "Active PTP Gap",
            "value": flt(ptp_summary.ptp_gap),
            "helper": f"{int(ptp_summary.active_ptps or 0)} active PTPs, {int(ptp_summary.broken_ptps or 0)} broken",
            "datatype": "Currency",
            "tone": "teal",
        },
        {
            "label": "Pending Delivery",
            "value": flt(execution_summary.pending_delivery),
            "helper": "Order value not fully delivered yet",
            "datatype": "Currency",
            "tone": "amber",
        },
        {
            "label": "Issued Demand Notices",
            "value": int(notice_summary.issued_notices or 0),
            "helper": f"{int(notice_summary.draft_notices or 0)} draft notices pending release",
            "tone": "slate",
        },
        {
            "label": "Issued Notice Exposure",
            "value": flt(notice_summary.issued_notice_value),
            "helper": "Value covered by submitted notices",
            "datatype": "Currency",
            "tone": "purple",
        },
    ]


def _get_sales_mix(so_filter, invoice_filter, values):
    sales_values = dict(values)
    sales_values["month_start"] = _month_start()
    sales_values["thirty_days_ago"] = frappe.utils.add_days(today(), -29)

    submitted_so_where = _build_where(["so.docstatus = 1"] + so_filter)
    current_month_invoice_where = _build_where(
        [
            "si.docstatus = 1",
            "si.is_return = 0",
            "si.posting_date BETWEEN %(month_start)s AND CURDATE()",
        ]
        + invoice_filter
    )

    orders = frappe.db.sql(
        f"""
        SELECT
            COUNT(*) AS submitted_orders,
            COALESCE(SUM(CASE WHEN so.transaction_date BETWEEN %(thirty_days_ago)s AND CURDATE() THEN so.grand_total ELSE 0 END), 0) AS sales_last_30_days,
            COALESCE(AVG(CASE WHEN so.transaction_date BETWEEN %(thirty_days_ago)s AND CURDATE() THEN so.grand_total END), 0) AS avg_order_value_30d
        FROM `tabSales Order` so
        WHERE {submitted_so_where}
        """,
        sales_values,
        as_dict=True,
    )[0]

    invoices = frappe.db.sql(
        f"""
        SELECT
            COUNT(*) AS invoice_count,
            COALESCE(SUM(si.base_grand_total), 0) AS invoiced_this_month
        FROM `tabSales Invoice` si
        WHERE {current_month_invoice_where}
        """,
        sales_values,
        as_dict=True,
    )[0]

    return [
        {"label": "Submitted Orders", "count": int(orders.submitted_orders or 0), "amount": flt(orders.sales_last_30_days)},
        {"label": "Invoices This Month", "count": int(invoices.invoice_count or 0), "amount": flt(invoices.invoiced_this_month)},
        {"label": "Avg Order Value (30d)", "count": int(orders.submitted_orders or 0), "amount": flt(orders.avg_order_value_30d)},
    ]


def _get_sales_trend(invoice_filter, values):
    where = _build_where(
        [
            "si.docstatus = 1",
            "si.is_return = 0",
            "si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 5 MONTH)",
        ]
        + invoice_filter
    )
    rows = frappe.db.sql(
        f"""
        SELECT
            DATE_FORMAT(si.posting_date, '%%b %%Y') AS label,
            DATE_FORMAT(si.posting_date, '%%Y-%%m') AS sort_key,
            COUNT(*) AS invoice_count,
            COALESCE(SUM(si.base_grand_total), 0) AS amount
        FROM `tabSales Invoice` si
        WHERE {where}
        GROUP BY sort_key, label
        ORDER BY sort_key ASC
        """,
        values,
        as_dict=True,
    )
    return [
        {
            "label": row.label,
            "invoice_count": int(row.invoice_count or 0),
            "amount": flt(row.amount),
        }
        for row in rows
    ]


def _get_sales_leaders(invoice_filter, values):
    where = _build_where(
        [
            "si.docstatus = 1",
            "si.is_return = 0",
            "si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 89 DAY)",
        ]
        + invoice_filter
    )
    rows = frappe.db.sql(
        f"""
        SELECT
            si.customer,
            MAX(si.customer_name) AS customer_name,
            COUNT(*) AS invoice_count,
            COALESCE(SUM(si.base_grand_total), 0) AS billed_amount,
            COALESCE(SUM(si.outstanding_amount), 0) AS outstanding_amount,
            MAX(si.posting_date) AS last_invoice_date
        FROM `tabSales Invoice` si
        WHERE {where}
        GROUP BY si.customer
        ORDER BY billed_amount DESC, invoice_count DESC
        LIMIT 6
        """,
        values,
        as_dict=True,
    )
    return [
        {
            "customer": row.customer,
            "customer_name": row.customer_name or row.customer,
            "invoice_count": int(row.invoice_count or 0),
            "billed_amount": flt(row.billed_amount),
            "outstanding_amount": flt(row.outstanding_amount),
            "last_invoice_date": row.last_invoice_date,
        }
        for row in rows
    ]


def _get_execution_watchlist(so_filter, values):
    where = _build_where(
        [
            "so.docstatus = 1",
            "IFNULL(so.status, '') NOT IN ('Closed', 'Completed', 'Cancelled')",
            "(COALESCE(so.per_billed, 0) < 100 OR COALESCE(so.per_delivered, 0) < 100)",
        ]
        + so_filter
    )
    rows = frappe.db.sql(
        f"""
        SELECT
            so.name,
            so.customer,
            so.customer_name,
            so.company,
            so.transaction_date,
            so.grand_total,
            so.status,
            COALESCE(so.per_billed, 0) AS per_billed,
            COALESCE(so.per_delivered, 0) AS per_delivered,
            (so.grand_total * (100 - COALESCE(so.per_billed, 0)) / 100) AS pending_billing_amount,
            (so.grand_total * (100 - COALESCE(so.per_delivered, 0)) / 100) AS pending_delivery_amount
        FROM `tabSales Order` so
        WHERE {where}
        ORDER BY
            pending_billing_amount DESC,
            pending_delivery_amount DESC,
            so.transaction_date ASC
        LIMIT 6
        """,
        values,
        as_dict=True,
    )
    return [
        {
            "name": row.name,
            "customer": row.customer,
            "customer_name": row.customer_name or row.customer,
            "company": row.company,
            "transaction_date": row.transaction_date,
            "grand_total": flt(row.grand_total),
            "status": row.status or "To Deliver and Bill",
            "per_billed": flt(row.per_billed),
            "per_delivered": flt(row.per_delivered),
            "pending_billing_amount": flt(row.pending_billing_amount),
            "pending_delivery_amount": flt(row.pending_delivery_amount),
        }
        for row in rows
    ]


def _get_approval_mix(so_filter, values):
    where = _build_where(["so.docstatus = 0"] + so_filter)
    rows = frappe.db.sql(
        f"""
        SELECT
            CASE
                WHEN COALESCE(so.custom_credit_approval_status, '') = '' THEN 'Not Requested'
                ELSE so.custom_credit_approval_status
            END AS label,
            COUNT(*) AS count,
            COALESCE(SUM(so.grand_total), 0) AS amount
        FROM `tabSales Order` so
        WHERE {where}
        GROUP BY label
        ORDER BY amount DESC, count DESC
        """,
        values,
        as_dict=True,
    )
    return [dict(label=row.label, count=int(row.count or 0), amount=flt(row.amount)) for row in rows]


def _get_risk_mix(so_filter, values):
    where = _build_where(["so.docstatus = 0"] + so_filter)
    rows = frappe.db.sql(
        f"""
        SELECT
            CASE
                WHEN COALESCE(so.custom_snrg_credit_check_status, '') = '' THEN 'Not Run'
                ELSE so.custom_snrg_credit_check_status
            END AS label,
            COUNT(*) AS count,
            COALESCE(SUM(so.grand_total), 0) AS amount
        FROM `tabSales Order` so
        WHERE {where}
        GROUP BY label
        ORDER BY amount DESC, count DESC
        """,
        values,
        as_dict=True,
    )
    return [dict(label=row.label, count=int(row.count or 0), amount=flt(row.amount)) for row in rows]


def _get_approval_queue(so_filter, values):
    where = _build_where(["so.docstatus = 0", "so.custom_credit_approval_status = 'Pending'"] + so_filter)
    rows = frappe.db.sql(
        f"""
        SELECT
            so.name,
            so.customer,
            so.customer_name,
            so.company,
            so.transaction_date,
            so.grand_total,
            so.custom_snrg_overdue_amount_terms AS overdue_amount,
            so.custom_snrg_request_time AS requested_on,
            so.custom_snrg_requested_to_employee AS requested_to_employee
        FROM `tabSales Order` so
        WHERE {where}
        ORDER BY COALESCE(so.custom_snrg_request_time, so.modified) ASC
        LIMIT 6
        """,
        values,
        as_dict=True,
    )
    return [_normalize_sales_order_row(row) for row in rows]


def _get_blocked_orders(so_filter, values):
    where = _build_where(["so.docstatus = 0", "so.custom_snrg_credit_check_status = 'Credit Hold'"] + so_filter)
    rows = frappe.db.sql(
        f"""
        SELECT
            so.name,
            so.customer,
            so.customer_name,
            so.company,
            so.transaction_date,
            so.grand_total,
            so.custom_snrg_overdue_amount_terms AS overdue_amount,
            so.custom_snrg_overdue_count_terms AS overdue_count,
            so.custom_snrg_credit_check_reason_code AS reason_code,
            so.custom_credit_approval_status AS approval_status
        FROM `tabSales Order` so
        WHERE {where}
        ORDER BY so.custom_snrg_overdue_amount_terms DESC, so.transaction_date ASC
        LIMIT 6
        """,
        values,
        as_dict=True,
    )
    return [_normalize_sales_order_row(row) for row in rows]


def _get_overdue_customers(invoice_filter, values):
    where = _build_where(
        [
            "si.docstatus = 1",
            "si.is_return = 0",
            "si.outstanding_amount > 0",
            f"si.posting_date <= DATE_SUB(CURDATE(), INTERVAL {DEFAULT_THRESHOLD_DAYS} DAY)",
        ]
        + invoice_filter
    )
    rows = frappe.db.sql(
        f"""
        SELECT
            si.customer,
            MAX(si.customer_name) AS customer_name,
            COUNT(*) AS invoice_count,
            COALESCE(SUM(si.outstanding_amount), 0) AS overdue_amount,
            MIN(si.posting_date) AS oldest_invoice_date
        FROM `tabSales Invoice` si
        WHERE {where}
        GROUP BY si.customer
        ORDER BY overdue_amount DESC, oldest_invoice_date ASC
        LIMIT 6
        """,
        values,
        as_dict=True,
    )

    today_date = getdate(today())
    payload = []
    for row in rows:
        oldest_date = getdate(row.oldest_invoice_date) if row.oldest_invoice_date else None
        payload.append(
            {
                "customer": row.customer,
                "customer_name": row.customer_name or row.customer,
                "invoice_count": int(row.invoice_count or 0),
                "overdue_amount": flt(row.overdue_amount),
                "oldest_invoice_date": row.oldest_invoice_date,
                "oldest_age_days": (today_date - oldest_date).days if oldest_date else None,
            }
        )
    return payload


def _get_ptp_watchlist(ptp_filter, values):
    where = _build_where(["p.status IN ('Pending', 'Partially Cleared', 'Broken')"] + ptp_filter)
    rows = frappe.db.sql(
        f"""
        SELECT
            p.name,
            p.sales_order,
            p.customer,
            p.customer_name,
            p.company,
            p.ptp_by_name,
            p.commitment_date,
            p.status,
            p.committed_amount,
            p.received_amount,
            p.difference_amount,
            p.payment_mode
        FROM `tabCredit PTP` p
        WHERE {where}
        ORDER BY
            CASE WHEN p.status = 'Broken' THEN 0 WHEN p.status = 'Pending' THEN 1 ELSE 2 END,
            p.commitment_date ASC,
            p.modified DESC
        LIMIT 6
        """,
        values,
        as_dict=True,
    )

    today_date = getdate(today())
    payload = []
    for row in rows:
        commitment_date = getdate(row.commitment_date) if row.commitment_date else None
        payload.append(
            {
                "name": row.name,
                "sales_order": row.sales_order,
                "customer": row.customer,
                "customer_name": row.customer_name or row.customer,
                "company": row.company,
                "ptp_by_name": row.ptp_by_name,
                "commitment_date": row.commitment_date,
                "status": row.status,
                "committed_amount": flt(row.committed_amount),
                "received_amount": flt(row.received_amount),
                "difference_amount": flt(row.difference_amount),
                "payment_mode": row.payment_mode,
                "days_to_due": (commitment_date - today_date).days if commitment_date else None,
            }
        )
    return payload


def _get_demand_notices(notice_filter, values):
    where = _build_where(notice_filter or ["1 = 1"])
    rows = frappe.db.sql(
        f"""
        SELECT
            dn.name,
            dn.customer,
            dn.customer_name,
            dn.company,
            dn.notice_date,
            dn.payment_deadline,
            dn.status,
            dn.docstatus,
            dn.total_outstanding,
            dn.total_interest,
            dn.grand_total_due
        FROM `tabDemand Notice` dn
        WHERE {where}
        ORDER BY dn.modified DESC
        LIMIT 6
        """,
        values,
        as_dict=True,
    )
    return [
        {
            "name": row.name,
            "customer": row.customer,
            "customer_name": row.customer_name or row.customer,
            "company": row.company,
            "notice_date": row.notice_date,
            "payment_deadline": row.payment_deadline,
            "status": row.status or ("Issued" if row.docstatus == 1 else "Draft"),
            "grand_total_due": flt(row.grand_total_due),
            "total_outstanding": flt(row.total_outstanding),
            "total_interest": flt(row.total_interest),
        }
        for row in rows
    ]


def _normalize_sales_order_row(row):
    return {
        "name": row.name,
        "customer": row.customer,
        "customer_name": row.customer_name or row.customer,
        "company": row.company,
        "transaction_date": row.transaction_date,
        "grand_total": flt(row.grand_total),
        "overdue_amount": flt(row.get("overdue_amount")),
        "overdue_count": int(row.get("overdue_count") or 0),
        "reason_code": row.get("reason_code"),
        "approval_status": row.get("approval_status"),
        "requested_on": formatdate(row.get("requested_on")) if row.get("requested_on") else "",
        "requested_to_employee": row.get("requested_to_employee"),
    }


def _build_where(conditions):
    clean = [condition for condition in conditions if condition]
    return " AND ".join(clean) if clean else "1 = 1"


def _month_start():
    return f"{today()[:7]}-01"
