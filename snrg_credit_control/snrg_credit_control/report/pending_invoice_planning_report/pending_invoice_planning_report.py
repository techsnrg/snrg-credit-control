import frappe

from snrg_credit_control.snrg_credit_control.pending_invoice_planning import (
    get_pending_invoice_planning_rows,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)
    columns = get_columns(filters)
    data = get_pending_invoice_planning_rows(filters=filters, pending_only=True)
    return columns, data


def validate_filters(filters):
    if not filters.get("company"):
        frappe.throw("Please select a Company.")


def get_columns(filters=None):
    filters = frappe._dict(filters or {})
    show_values = bool(filters.get("show_values"))

    columns = [
        {
            "label": "Quotation",
            "fieldname": "quotation",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Data",
            "width": 230,
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
            "fieldtype": "Data",
            "width": 150,
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
            "label": "Invoiced Qty",
            "fieldname": "invoiced_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 110,
        },
        {
            "label": "Pending Qty",
            "fieldname": "total_uninvoiced_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 130,
        },
        {
            "label": "Status",
            "fieldname": "status_summary",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": "Production Status",
            "fieldname": "production_request_status",
            "fieldtype": "Data",
            "width": 140,
        },
        {
            "label": "Required By",
            "fieldname": "production_required_by_date",
            "fieldtype": "Date",
            "width": 115,
        },
        {
            "label": "Production",
            "fieldname": "production_request_action",
            "fieldtype": "HTML",
            "width": 190,
        },
    ]

    if show_values:
        insert_after = next(
            index for index, column in enumerate(columns) if column["fieldname"] == "quotation_qty"
        ) + 1
        columns[insert_after:insert_after] = [
            {
                "label": "Quotation Value",
                "fieldname": "quotation_value",
                "fieldtype": "Currency",
                "options": "currency",
                "width": 130,
            }
        ]

        insert_after = next(
            index for index, column in enumerate(columns) if column["fieldname"] == "invoiced_qty"
        ) + 1
        columns[insert_after:insert_after] = [
            {
                "label": "Invoiced Value",
                "fieldname": "invoiced_value",
                "fieldtype": "Currency",
                "options": "currency",
                "width": 130,
            }
        ]

        insert_after = next(
            index for index, column in enumerate(columns) if column["fieldname"] == "total_uninvoiced_qty"
        ) + 1
        columns[insert_after:insert_after] = [
            {
                "label": "Pending Value",
                "fieldname": "total_uninvoiced_value",
                "fieldtype": "Currency",
                "options": "currency",
                "width": 140,
            }
        ]

    return columns
