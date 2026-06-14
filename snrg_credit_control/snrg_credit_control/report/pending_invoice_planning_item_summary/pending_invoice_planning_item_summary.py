import frappe

from snrg_credit_control.snrg_credit_control.pending_invoice_planning import (
    get_pending_invoice_planning_item_summary_rows,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)
    columns = get_columns(filters)
    data = get_pending_invoice_planning_item_summary_rows(filters=filters)
    return columns, data


def validate_filters(filters):
    if not filters.get("company"):
        frappe.throw("Please select a Company.")
    if not filters.get("default_warehouse"):
        frappe.throw("Please select a Default Warehouse.")


def get_columns(filters=None):
    filters = frappe._dict(filters or {})
    show_values = bool(filters.get("show_values"))

    columns = [
        {
            "label": "Item Code",
            "fieldname": "item_code",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": "Item Name",
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 230,
        },
        {
            "label": "Pending Qty",
            "fieldname": "total_uninvoiced_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 120,
        },
        {
            "label": "Warehouse Stock",
            "fieldname": "warehouse_stock_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 130,
        },
        {
            "label": "Shortage Qty",
            "fieldname": "shortage_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 120,
        },
        {
            "label": "Active Requested Qty",
            "fieldname": "production_active_requested_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 150,
        },
        {
            "label": "Remaining To Request",
            "fieldname": "remaining_to_request_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 160,
        },
        {
            "label": "Stock After Pending",
            "fieldname": "stock_after_pending_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 150,
        },
        {
            "label": "Production Status",
            "fieldname": "production_status_summary",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": "Planning Stage",
            "fieldname": "planning_stage_summary",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": "Quotations",
            "fieldname": "quotation_count",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": "Customers",
            "fieldname": "customer_count",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": "Sales Orders",
            "fieldname": "sales_order_count",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": "Latest Quotation Date",
            "fieldname": "latest_quotation_date",
            "fieldtype": "Date",
            "width": 140,
        },
        {
            "label": "Latest Sales Order",
            "fieldname": "latest_sales_order",
            "fieldtype": "Link",
            "options": "Sales Order",
            "width": 160,
        },
        {
            "label": "Latest Invoice Date",
            "fieldname": "latest_invoice_date",
            "fieldtype": "Date",
            "width": 140,
        },
    ]

    if show_values:
        columns[3:3] = [
            {
                "label": "Pending Value",
                "fieldname": "total_uninvoiced_value",
                "fieldtype": "Currency",
                "options": "currency",
                "width": 140,
            }
        ]

    return columns
