import frappe


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": "Legal Case",
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Legal Case",
            "width": 130,
        },
        {
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 130,
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
            "width": 180,
        },
        {
            "label": "Status",
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": "Assigned Counsel",
            "fieldname": "assigned_counsel",
            "fieldtype": "Link",
            "options": "User",
            "width": 150,
        },
        {
            "label": "Date Marked To Legal",
            "fieldname": "date_marked_legal",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Original Legal Amount",
            "fieldname": "original_legal_amount",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": "Current Outstanding",
            "fieldname": "current_outstanding_balance",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": "Amount Recovered",
            "fieldname": "amount_recovered",
            "fieldtype": "Currency",
            "width": 130,
        },
        {
            "label": "Action Due By",
            "fieldname": "next_action_due_by",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Action Due By Reason",
            "fieldname": "next_action_due_by_reason",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": "Action On Or After",
            "fieldname": "next_action_on_or_after",
            "fieldtype": "Date",
            "width": 130,
        },
        {
            "label": "Action On Or After Reason",
            "fieldname": "next_action_on_or_after_reason",
            "fieldtype": "Data",
            "width": 240,
        },
        {
            "label": "Last Notice Date",
            "fieldname": "last_notice_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Last Payment Date",
            "fieldname": "last_payment_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Last Activity Date",
            "fieldname": "last_activity_date",
            "fieldtype": "Date",
            "width": 120,
        },
    ]


def get_data(filters):
    conditions = []
    values = {}

    if filters.get("company"):
        conditions.append("lc.company = %(company)s")
        values["company"] = filters["company"]

    if filters.get("customer"):
        conditions.append("lc.customer = %(customer)s")
        values["customer"] = filters["customer"]

    if filters.get("status"):
        conditions.append("lc.status = %(status)s")
        values["status"] = filters["status"]
    elif not filters.get("show_closed"):
        conditions.append("lc.status != 'Closed'")

    if filters.get("assigned_counsel"):
        conditions.append("lc.assigned_counsel = %(assigned_counsel)s")
        values["assigned_counsel"] = filters["assigned_counsel"]

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    return frappe.db.sql(
        f"""
        SELECT
            lc.name,
            lc.customer,
            cust.customer_name,
            lc.company,
            lc.status,
            lc.assigned_counsel,
            lc.date_marked_legal,
            lc.original_legal_amount,
            lc.current_outstanding_balance,
            lc.amount_recovered,
            lc.next_action_due_by,
            lc.next_action_due_by_reason,
            lc.next_action_on_or_after,
            lc.next_action_on_or_after_reason,
            lc.last_notice_date,
            lc.last_payment_date,
            lc.last_activity_date
        FROM `tabLegal Case` lc
        LEFT JOIN `tabCustomer` cust ON cust.name = lc.customer
        {where_clause}
        ORDER BY
            CASE WHEN lc.next_action_due_by IS NULL THEN 1 ELSE 0 END,
            lc.next_action_due_by ASC,
            lc.date_marked_legal ASC
        """,
        values,
        as_dict=True,
    )
