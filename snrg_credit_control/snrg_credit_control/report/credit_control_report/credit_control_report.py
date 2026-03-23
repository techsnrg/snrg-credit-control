"""
Credit Control Report
=====================
Shows all draft/open Sales Orders with credit risk or pending approval.

Filters : Company (reqd), Status, Customer, Date From, Date To
Columns : SO, Date, Customer, Order Amount, Credit Status, Reason,
          Overdue Count, Overdue Amount, Request Time,
          Latest PTP (by / payment date / committed amount / mode),
          Approval Status, Approved Cap, Valid Till, Approver
"""

import frappe
from frappe.utils import getdate, today


def execute(filters=None):
    filters = filters or {}
    validate_filters(filters)
    columns = get_columns()
    data    = get_data(filters)
    return columns, data


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------

def get_columns():
    return [
        {
            "label": "Sales Order",
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Sales Order",
            "width": 150,
        },
        {
            "label": "SO Date",
            "fieldname": "transaction_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 120,
        },
        {
            "label": "Customer Name",
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": "Order Amount",
            "fieldname": "grand_total",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": "Credit Status",
            "fieldname": "custom_snrg_credit_check_status",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": "Reason",
            "fieldname": "custom_snrg_credit_check_reason_code",
            "fieldtype": "Data",
            "width": 110,
        },
        {
            "label": "Overdue #",
            "fieldname": "custom_snrg_overdue_count_terms",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": "Overdue Amount",
            "fieldname": "custom_snrg_overdue_amount_terms",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": "Request Time",
            "fieldname": "custom_snrg_request_time",
            "fieldtype": "Datetime",
            "width": 140,
        },
        {
            "label": "PTP By",
            "fieldname": "ptp_by_name",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": "PTP Payment Date",
            "fieldname": "ptp_commitment_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "PTP Amount",
            "fieldname": "ptp_committed_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": "PTP Received",
            "fieldname": "ptp_received_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": "PTP Difference",
            "fieldname": "ptp_difference_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": "PTP Status",
            "fieldname": "ptp_status",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": "PTP Mode",
            "fieldname": "ptp_payment_mode",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "label": "Payment Entries",
            "fieldname": "ptp_payment_entries",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": "Approval Status",
            "fieldname": "custom_credit_approval_status",
            "fieldtype": "Data",
            "width": 110,
        },
        {
            "label": "Approved Cap",
            "fieldname": "custom_snrg_override_cap_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": "Valid Till",
            "fieldname": "custom_snrg_override_valid_till",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": "Approver",
            "fieldname": "custom_snrg_approver",
            "fieldtype": "Link",
            "options": "User",
            "width": 130,
        },
    ]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def get_data(filters):
    conditions, values = build_conditions(filters)

    so_list = frappe.db.sql(
        f"""
        SELECT
            so.name,
            so.transaction_date,
            so.customer,
            so.customer_name,
            so.grand_total,
            so.rounded_total,
            so.currency,
            so.custom_snrg_credit_check_status,
            so.custom_snrg_credit_check_reason_code,
            so.custom_snrg_overdue_count_terms,
            so.custom_snrg_overdue_amount_terms,
            so.custom_snrg_request_time,
            so.custom_credit_approval_status,
            so.custom_snrg_override_cap_amount,
            so.custom_snrg_override_valid_till,
            so.custom_snrg_approver
        FROM `tabSales Order` so
        WHERE so.docstatus = 0
          {conditions}
        ORDER BY
            FIELD(so.custom_snrg_credit_check_status, 'Credit Hold', 'Not Run', 'Credit OK'),
            so.custom_snrg_request_time DESC,
            so.transaction_date DESC
        """,
        values,
        as_dict=True,
    )

    if not so_list:
        return []

    # Fetch latest PTP entry per SO in one query
    so_names = [r.name for r in so_list]
    placeholders = ", ".join(["%s"] * len(so_names))
    ptp_rows = frappe.db.sql(
        f"""
        SELECT
            p.parent,
            p.name,
            p.ptp_by_name,
            p.commitment_date,
            p.committed_amount,
            p.received_amount,
            p.difference_amount,
            p.status,
            p.linked_payment_entries,
            p.payment_mode,
            p.modified
        FROM `tabCredit PTP Entry` p
        INNER JOIN (
            SELECT parent, MAX(modified) AS latest
            FROM `tabCredit PTP Entry`
            WHERE parent IN ({placeholders})
            GROUP BY parent
        ) latest ON latest.parent = p.parent AND latest.latest = p.modified
        """,
        so_names,
        as_dict=True,
    )
    ptp_map = {r.parent: r for r in ptp_rows}

    today_date = getdate(today())
    data = []
    for so in so_list:
        ptp = ptp_map.get(so.name) or {}
        approval_status = (so.custom_credit_approval_status or "").strip()
        vt = so.custom_snrg_override_valid_till

        # Compute display status (for JS colour coding)
        if so.custom_snrg_credit_check_status == "Credit Hold":
            if approval_status.lower() == "approved":
                if vt and getdate(vt) >= today_date:
                    display_status = "Approved"
                else:
                    display_status = "Expired"
            elif so.custom_snrg_request_time:
                display_status = "Pending Approval"
            else:
                display_status = "Credit Hold"
        else:
            display_status = so.custom_snrg_credit_check_status or "Not Run"

        data.append(
            {
                "name":                               so.name,
                "transaction_date":                   so.transaction_date,
                "customer":                           so.customer,
                "customer_name":                      so.customer_name,
                "grand_total":                        so.grand_total or so.rounded_total or 0,
                "currency":                           so.currency,
                "custom_snrg_credit_check_status":    display_status,
                "custom_snrg_credit_check_reason_code": so.custom_snrg_credit_check_reason_code or "",
                "custom_snrg_overdue_count_terms":    so.custom_snrg_overdue_count_terms or 0,
                "custom_snrg_overdue_amount_terms":   so.custom_snrg_overdue_amount_terms or 0,
                "custom_snrg_request_time":           so.custom_snrg_request_time,
                "ptp_by_name":                        ptp.get("ptp_by_name") or "",
                "ptp_commitment_date":                ptp.get("commitment_date"),
                "ptp_committed_amount":               ptp.get("committed_amount") or 0,
                "ptp_received_amount":                ptp.get("received_amount") or 0,
                "ptp_difference_amount":              ptp.get("difference_amount") or 0,
                "ptp_status":                         ptp.get("status") or "",
                "ptp_payment_mode":                   ptp.get("payment_mode") or "",
                "ptp_payment_entries":                ptp.get("linked_payment_entries") or "",
                "custom_credit_approval_status":      approval_status,
                "custom_snrg_override_cap_amount":    so.custom_snrg_override_cap_amount or 0,
                "custom_snrg_override_valid_till":    vt,
                "custom_snrg_approver":               so.custom_snrg_approver or "",
            }
        )
    return data


# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------

def validate_filters(filters):
    if not filters.get("company"):
        frappe.throw("Please select a Company.")


def build_conditions(filters):
    conditions = "AND so.company = %(company)s"
    values = {"company": filters["company"]}

    if filters.get("customer"):
        conditions += " AND so.customer = %(customer)s"
        values["customer"] = filters["customer"]

    if filters.get("from_date"):
        conditions += " AND so.transaction_date >= %(from_date)s"
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions += " AND so.transaction_date <= %(to_date)s"
        values["to_date"] = filters["to_date"]

    status_filter = filters.get("status")
    if status_filter and status_filter != "All":
        if status_filter == "Credit Hold":
            conditions += (
                " AND so.custom_snrg_credit_check_status = 'Credit Hold'"
                " AND (so.custom_credit_approval_status IS NULL"
                "       OR so.custom_credit_approval_status NOT IN ('Approved', 'Pending'))"
            )
        elif status_filter == "Pending Approval":
            conditions += (
                " AND so.custom_snrg_credit_check_status = 'Credit Hold'"
                " AND so.custom_snrg_request_time IS NOT NULL"
                " AND (so.custom_credit_approval_status IS NULL"
                "       OR so.custom_credit_approval_status != 'Approved')"
            )
        elif status_filter == "Approved":
            conditions += " AND so.custom_credit_approval_status = 'Approved'"
        elif status_filter == "Expired":
            conditions += (
                " AND so.custom_credit_approval_status = 'Approved'"
                " AND so.custom_snrg_override_valid_till < CURDATE()"
            )

    return conditions, values
