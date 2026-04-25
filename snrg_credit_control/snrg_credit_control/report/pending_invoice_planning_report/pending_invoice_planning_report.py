import frappe

from snrg_credit_control.pending_invoice_planning import get_pending_invoice_planning_rows


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
            "label": "Company",
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 140,
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
            "label": "Quotation Open Qty",
            "fieldname": "quotation_open_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 130,
        },
        {
            "label": "Quotation Open Value",
            "fieldname": "quotation_open_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 140,
        },
        {
            "label": "Draft SO Qty",
            "fieldname": "draft_so_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 110,
        },
        {
            "label": "Draft SO Value",
            "fieldname": "draft_so_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": "Submitted SO Qty",
            "fieldname": "submitted_so_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 130,
        },
        {
            "label": "Submitted SO Value",
            "fieldname": "submitted_so_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 140,
        },
        {
            "label": "Submitted SO Uninvoiced Qty",
            "fieldname": "submitted_so_uninvoiced_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 170,
        },
        {
            "label": "Submitted SO Uninvoiced Value",
            "fieldname": "submitted_so_uninvoiced_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 180,
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
            "label": "Total Uninvoiced Qty",
            "fieldname": "total_uninvoiced_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 150,
        },
        {
            "label": "Total Uninvoiced Value",
            "fieldname": "total_uninvoiced_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 160,
        },
        {
            "label": "Quotation Status",
            "fieldname": "quotation_status",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": "Sales Order Status",
            "fieldname": "sales_order_status",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": "Planning Stage",
            "fieldname": "planning_stage_summary",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": "Sales Order Count",
            "fieldname": "sales_order_count",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": "Latest Sales Order",
            "fieldname": "latest_sales_order",
            "fieldtype": "Link",
            "options": "Sales Order",
            "width": 150,
        },
        {
            "label": "Latest Invoice Date",
            "fieldname": "latest_invoice_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Currency",
            "fieldname": "currency",
            "fieldtype": "Link",
            "options": "Currency",
            "width": 90,
        },
    ]
