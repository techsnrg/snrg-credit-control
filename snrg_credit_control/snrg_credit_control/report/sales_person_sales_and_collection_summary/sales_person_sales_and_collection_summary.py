from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, formatdate


UNASSIGNED_KEY = "__unassigned__"
UNASSIGNED_CUSTOMER_KEY = "__unassigned_customer__"


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    employees = get_sales_employees(filters)
    totals = defaultdict(make_total_bucket)

    add_sales_totals(totals, filters)
    add_collection_totals(totals, filters)

    rows = build_rows(employees, totals, filters)
    return get_columns(), rows


def validate_filters(filters):
    if not filters.get("company"):
        frappe.throw(_("Please select a Company."))
    if not filters.get("date_range") or len(filters.date_range) != 2:
        frappe.throw(_("Please select a Date Range."))

    required_fields = (
        ("Sales Person", "employee"),
        ("Employee", "custom_headquarter"),
        ("Payment Entry", "custom_incentive_sales_person_name"),
    )
    missing = [
        f"{doctype}.{fieldname}"
        for doctype, fieldname in required_fields
        if not frappe.get_meta(doctype).has_field(fieldname)
    ]
    if missing:
        frappe.throw(_("Required fields are missing: {0}").format(", ".join(missing)))


def get_sales_employees(filters):
    conditions = ["sp.enabled = 1", "sp.is_group = 0", "IFNULL(sp.employee, '') != ''"]
    values = {}

    if filters.get("employee"):
        conditions.append("sp.employee = %(employee)s")
        values["employee"] = filters.employee

    rows = frappe.db.sql(
        """
        SELECT
            sp.employee,
            MAX(e.employee_name) AS employee_name,
            MAX(e.custom_headquarter) AS headquarter
        FROM `tabSales Person` sp
        INNER JOIN `tabEmployee` e ON e.name = sp.employee
        WHERE {conditions}
        GROUP BY sp.employee
        ORDER BY employee_name ASC, sp.employee ASC
        """.format(conditions=" AND ".join(conditions)),
        values,
        as_dict=True,
    )
    return {row.employee: row for row in rows}


def add_sales_totals(totals, filters):
    rows = frappe.db.sql(
        """
        SELECT
            si.name AS sales_invoice,
            si.customer,
            si.customer_name,
            si.base_net_total,
            sp.employee,
            st.allocated_percentage
        FROM `tabSales Invoice` si
        LEFT JOIN `tabSales Team` st
            ON st.parent = si.name
            AND st.parenttype = 'Sales Invoice'
            AND st.parentfield = 'sales_team'
        LEFT JOIN `tabSales Person` sp ON sp.name = st.sales_person
        WHERE si.docstatus = 1
          AND si.company = %(company)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
        ORDER BY si.name ASC, st.idx ASC
        """,
        get_query_values(filters),
        as_dict=True,
    )

    invoice_rows = defaultdict(list)
    for row in rows:
        invoice_rows[row.sales_invoice].append(row)

    for allocations in invoice_rows.values():
        invoice_total = flt(allocations[0].base_net_total)
        customer = allocations[0].customer
        customer_name = allocations[0].customer_name
        for allocation in allocations:
            if allocation.employee:
                key = allocation.employee
                percentage = flt(allocation.allocated_percentage)
            else:
                key = UNASSIGNED_KEY
                percentage = 100 if len(allocations) == 1 else flt(allocation.allocated_percentage)
            sales_amount = invoice_total * percentage / 100
            totals[key]["sales"] += sales_amount
            add_customer_amount(totals[key], customer, customer_name, sales=sales_amount)


def add_collection_totals(totals, filters):
    rows = frappe.db.sql(
        """
        SELECT
            IFNULL(pe.custom_incentive_sales_person_name, '') AS employee,
            IFNULL(pe.party, '') AS customer,
            MAX(COALESCE(c.customer_name, pe.party, '')) AS customer_name,
            COALESCE(SUM(pe.base_paid_amount), 0) AS collection
        FROM `tabPayment Entry` pe
        LEFT JOIN `tabCustomer` c ON c.name = pe.party
        WHERE pe.docstatus = 1
          AND pe.payment_type = 'Receive'
          AND pe.party_type = 'Customer'
          AND pe.company = %(company)s
          AND pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY pe.custom_incentive_sales_person_name, pe.party
        """,
        get_query_values(filters),
        as_dict=True,
    )

    for row in rows:
        collection_amount = flt(row.collection)
        key = row.employee or UNASSIGNED_KEY
        totals[key]["collection"] += collection_amount
        add_customer_amount(totals[key], row.customer, row.customer_name, collection=collection_amount)


def build_rows(employees, totals, filters):
    date_label = _("{0} to {1}").format(
        formatdate(filters.date_range[0], "d MMMM yyyy"),
        formatdate(filters.date_range[1], "d MMMM yyyy"),
    )
    employee_filter = filters.get("employee")
    keys = list(employees)

    for key in totals:
        if key != UNASSIGNED_KEY and key not in employees and (not employee_filter or employee_filter == key):
            employee = frappe.db.get_value(
                "Employee",
                key,
                ["employee_name", "custom_headquarter"],
                as_dict=True,
            )
            employees[key] = frappe._dict(
                {
                    "employee": key,
                    "employee_name": employee.employee_name if employee else key,
                    "headquarter": employee.custom_headquarter if employee else "",
                }
            )
            keys.append(key)

    keys.sort(key=lambda key: ((employees[key].employee_name or key).lower(), key))
    rows = [make_row(key, employees[key], totals[key], date_label) for key in keys]

    if not employee_filter and (totals[UNASSIGNED_KEY]["sales"] or totals[UNASSIGNED_KEY]["collection"]):
        rows.append(
            make_row(
                UNASSIGNED_KEY,
                frappe._dict({"employee": "", "employee_name": _("Unassigned"), "headquarter": _("Not Set")}),
                totals[UNASSIGNED_KEY],
                date_label,
            )
        )
    return rows


def make_total_bucket():
    return {
        "sales": 0.0,
        "collection": 0.0,
        "customers": defaultdict(make_customer_bucket),
    }


def make_customer_bucket():
    return {
        "customer": "",
        "customer_name": "",
        "sales": 0.0,
        "collection": 0.0,
    }


def add_customer_amount(bucket, customer, customer_name, sales=0.0, collection=0.0):
    customer_key = customer or UNASSIGNED_CUSTOMER_KEY
    customer_bucket = bucket["customers"][customer_key]
    customer_bucket["customer"] = customer or ""
    customer_bucket["customer_name"] = customer_name or customer or _("Unassigned Customer")
    customer_bucket["sales"] += flt(sales)
    customer_bucket["collection"] += flt(collection)


def make_row(key, employee, totals, date_label):
    sales = flt(totals["sales"], 2)
    collection = flt(totals["collection"], 2)
    employee_name = employee.employee_name or employee.employee or _("Not Set")
    headquarter = employee.headquarter or _("Not Set")

    return {
        "employee": employee.employee if key != UNASSIGNED_KEY else "",
        "employee_name": employee_name,
        "headquarter": headquarter,
        "sales": sales,
        "collection": collection,
        "whatsapp_message": "\n".join(
            [
                _("Name: {0}").format(employee_name),
                _("Headquarter: {0}").format(headquarter),
                _("Period: {0}").format(date_label),
                _("Sales: {0}").format(format_indian_currency(sales)),
                _("Collection: {0}").format(format_indian_currency(collection)),
            ]
        ),
        "detailed_whatsapp_message": build_detailed_message(
            employee_name,
            headquarter,
            date_label,
            sales,
            collection,
            totals["customers"],
        ),
    }


def build_detailed_message(employee_name, headquarter, date_label, sales, collection, customers):
    lines = [
        _("Name: {0}").format(employee_name),
        _("Headquarter: {0}").format(headquarter),
        _("Period: {0}").format(date_label),
        _("Sales: {0}").format(format_indian_currency(sales)),
        _("Collection: {0}").format(format_indian_currency(collection)),
        "",
        _("Customer Wise:"),
    ]

    customer_rows = [
        row
        for row in customers.values()
        if flt(row["sales"]) or flt(row["collection"])
    ]
    customer_rows.sort(
        key=lambda row: (
            -(abs(flt(row["sales"])) + abs(flt(row["collection"]))),
            (row["customer_name"] or row["customer"] or "").lower(),
        )
    )

    if not customer_rows:
        lines.append(_("No customer-wise sales or collection."))
        return "\n".join(lines)

    for row in customer_rows:
        lines.append(row["customer_name"] or row["customer"] or _("Unassigned Customer"))
        lines.append(_("Sales: {0}").format(format_indian_currency(row["sales"])))
        lines.append(_("Collection: {0}").format(format_indian_currency(row["collection"])))
        lines.append("")

    return "\n".join(lines).rstrip()


def format_indian_currency(value):
    value = flt(value, 2)
    sign = "-" if value < 0 else ""
    whole, decimal = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        last_three = whole[-3:]
        remaining = whole[:-3]
        pairs = []
        while remaining:
            pairs.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        whole = ",".join(pairs + [last_three])
    return f"{sign}₹{whole}.{decimal}"


def get_query_values(filters):
    return {
        "company": filters.company,
        "from_date": filters.date_range[0],
        "to_date": filters.date_range[1],
    }


def get_columns():
    return [
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 150,
        },
        {"label": _("Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
        {"label": _("Headquarter"), "fieldname": "headquarter", "fieldtype": "Data", "width": 150},
        {"label": _("Sales"), "fieldname": "sales", "fieldtype": "Currency", "width": 140},
        {"label": _("Collection"), "fieldname": "collection", "fieldtype": "Currency", "width": 140},
        {"label": _("WhatsApp"), "fieldname": "copy_message", "fieldtype": "Data", "width": 120},
        {
            "label": _("Detailed WhatsApp"),
            "fieldname": "copy_detailed_message",
            "fieldtype": "Data",
            "width": 150,
        },
    ]
