import frappe

from snrg_credit_control.snrg_credit_control.pending_invoice_planning import (
    get_pending_invoice_planning_customer_summary_rows,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)
    columns = get_columns()
    data = get_pending_invoice_planning_customer_summary_rows(filters=filters)
    return columns, data


def validate_filters(filters):
    if not filters.get("company"):
        frappe.throw("Please select a Company.")


def get_columns():
    return [
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
            "width": 220,
        },
        {
            "label": "Company",
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 150,
        },
        {
            "label": "Quotation Count",
            "fieldname": "quotation_count",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": "Item Count",
            "fieldname": "item_count",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": "Sales Order Count",
            "fieldname": "sales_order_count",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": "Latest Quotation Date",
            "fieldname": "latest_quotation_date",
            "fieldtype": "Date",
            "width": 130,
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
            "label": "Quotation Value",
            "fieldname": "quotation_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": "Quotation Open Value",
            "fieldname": "quotation_open_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 150,
        },
        {
            "label": "Draft SO Value",
            "fieldname": "draft_so_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": "Submitted SO Uninvoiced Value",
            "fieldname": "submitted_so_uninvoiced_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 200,
        },
        {
            "label": "Invoiced Value",
            "fieldname": "invoiced_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": "Total Uninvoiced Value",
            "fieldname": "total_uninvoiced_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 170,
        },
        {
            "label": "Planning Stage",
            "fieldname": "planning_stage_summary",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": "Currency",
            "fieldname": "currency",
            "fieldtype": "Link",
            "options": "Currency",
            "width": 90,
        },
    ]
