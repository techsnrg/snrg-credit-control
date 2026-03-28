import frappe


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": "Payment Entry",
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Payment Entry",
            "width": 140,
        },
        {
            "label": "Posting Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Customer",
            "fieldname": "party",
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
            "label": "Payment Amount",
            "fieldname": "payment_amount",
            "fieldtype": "Currency",
            "width": 130,
        },
        {
            "label": "Mode Of Payment",
            "fieldname": "mode_of_payment",
            "fieldtype": "Link",
            "options": "Mode of Payment",
            "width": 140,
        },
        {
            "label": "Reference No",
            "fieldname": "reference_no",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": "Legal Case",
            "fieldname": "legal_case",
            "fieldtype": "Link",
            "options": "Legal Case",
            "width": 130,
        },
        {
            "label": "Legal Status",
            "fieldname": "legal_status",
            "fieldtype": "Data",
            "width": 140,
        },
        {
            "label": "Assigned Counsel",
            "fieldname": "assigned_counsel",
            "fieldtype": "Link",
            "options": "User",
            "width": 150,
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
    ]


def get_data(filters):
    conditions = [
        "pe.docstatus = 1",
        "pe.party_type = 'Customer'",
        "pe.payment_type = 'Receive'",
        "cust.custom_is_under_legal = 1",
        "cust.custom_active_legal_case IS NOT NULL",
        "cust.custom_active_legal_case != ''",
    ]
    values = {}

    if filters.get("company"):
        conditions.append("pe.company = %(company)s")
        values["company"] = filters["company"]

    if filters.get("customer"):
        conditions.append("pe.party = %(customer)s")
        values["customer"] = filters["customer"]

    if filters.get("from_date"):
        conditions.append("pe.posting_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("pe.posting_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("assigned_counsel"):
        conditions.append("lc.assigned_counsel = %(assigned_counsel)s")
        values["assigned_counsel"] = filters["assigned_counsel"]

    where_clause = " AND ".join(conditions)

    return frappe.db.sql(
        f"""
        SELECT
            pe.name,
            pe.posting_date,
            pe.party,
            cust.customer_name,
            pe.company,
            COALESCE(pe.received_amount, pe.paid_amount) AS payment_amount,
            pe.mode_of_payment,
            pe.reference_no,
            cust.custom_active_legal_case AS legal_case,
            lc.status AS legal_status,
            lc.assigned_counsel,
            lc.original_legal_amount,
            lc.current_outstanding_balance
        FROM `tabPayment Entry` pe
        INNER JOIN `tabCustomer` cust ON cust.name = pe.party
        INNER JOIN `tabLegal Case` lc ON lc.name = cust.custom_active_legal_case
        WHERE {where_clause}
        ORDER BY pe.posting_date DESC, pe.modified DESC
        """,
        values,
        as_dict=True,
    )
