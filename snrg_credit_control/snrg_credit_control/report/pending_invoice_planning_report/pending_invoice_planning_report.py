import frappe

from snrg_credit_control.snrg_credit_control.pending_invoice_planning import (
    get_pending_invoice_planning_rows,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)
    columns = get_columns()
    data = get_pending_invoice_planning_rows(filters=filters, pending_only=True)
    return columns, data


def validate_filters(filters):
    if not filters.get("company"):
        frappe.throw("Please select a Company.")


def get_columns():
    return [
        {
            "label": "Quotation",
            "fieldname": "quotation",
            "fieldtype": "Link",
            "options": "Quotation",
            "width": 150,
        },
        {
            "label": "Quotation Date",
            "fieldname": "quotation_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 150,
        },
        {
            "label": "Customer Name",
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": "Territory",
            "fieldname": "territory",
            "fieldtype": "Link",
            "options": "Territory",
            "width": 130,
        },
        {
            "label": "Item Code",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 130,
        },
        {
            "label": "Item Name",
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": "Quotation Qty",
            "fieldname": "quotation_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 110,
        },
        {
            "label": "Quotation Value",
            "fieldname": "quotation_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": "Order Qty",
            "fieldname": "order_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 130,
        },
        {
            "label": "Order Value",
            "fieldname": "order_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 140,
        },
        {
            "label": "Invoiced Qty",
            "fieldname": "invoiced_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 110,
        },
        {
            "label": "Invoiced Value",
            "fieldname": "invoiced_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": "Pending Qty",
            "fieldname": "total_uninvoiced_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 130,
        },
        {
            "label": "Pending Value",
            "fieldname": "total_uninvoiced_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 140,
        },
        {
            "label": "Status",
            "fieldname": "status_summary",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": "Production",
            "fieldname": "production_request_action",
            "fieldtype": "HTML",
            "width": 140,
        },
    ]
