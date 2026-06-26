from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, formatdate


UNASSIGNED_KEY = "__unassigned__"
UNASSIGNED_CUSTOMER_KEY = "__unassigned_customer__"


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    salespeople = get_salespeople(filters)
    employee_salesperson_map = get_employee_salesperson_map()
    totals = defaultdict(make_total_bucket)

    add_sales_totals(totals, filters)
    add_collection_totals(totals, filters, employee_salesperson_map)

    rows = build_rows(salespeople, totals, filters)
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


def get_salespeople(filters):
    conditions = ["sp.enabled = 1", "sp.is_group = 0"]
    values = {}

    if filters.get("sales_person"):
        conditions.append("sp.name = %(sales_person)s")
        values["sales_person"] = filters.sales_person

    rows = frappe.db.sql(
        """
        SELECT
            sp.name AS sales_person,
            sp.sales_person_name,
            sp.employee,
            e.employee_name,
            e.custom_headquarter AS headquarter
        FROM `tabSales Person` sp
        LEFT JOIN `tabEmployee` e ON e.name = sp.employee
        WHERE {conditions}
        ORDER BY sp.sales_person_name ASC, sp.name ASC
        """.format(conditions=" AND ".join(conditions)),
        values,
        as_dict=True,
    )
    return {row.sales_person: row for row in rows}


def get_employee_salesperson_map():
    rows = frappe.db.sql(
        """
        SELECT
            sp.employee,
            sp.name AS sales_person
        FROM `tabSales Person` sp
        WHERE sp.enabled = 1
          AND sp.is_group = 0
          AND IFNULL(sp.employee, '') != ''
        ORDER BY sp.sales_person_name ASC, sp.name ASC
        """,
        as_dict=True,
    )

    grouped = defaultdict(list)
    for row in rows:
        grouped[row.employee].append(row.sales_person)

    return {
        employee: salespeople[0]
        for employee, salespeople in grouped.items()
        if len(salespeople) == 1
    }


def add_sales_totals(totals, filters):
    rows = frappe.db.sql(
        """
        SELECT
            si.name AS sales_invoice,
            si.customer,
            si.customer_name,
            si.base_net_total,
            st.sales_person,
            st.allocated_percentage
        FROM `tabSales Invoice` si
        LEFT JOIN `tabSales Team` st
            ON st.parent = si.name
            AND st.parenttype = 'Sales Invoice'
            AND st.parentfield = 'sales_team'
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
            if allocation.sales_person:
                key = allocation.sales_person
                percentage = flt(allocation.allocated_percentage)
            else:
                key = UNASSIGNED_KEY
                percentage = 100 if len(allocations) == 1 else flt(allocation.allocated_percentage)
            sales_amount = invoice_total * percentage / 100
            totals[key]["sales"] += sales_amount
            add_customer_amount(totals[key], customer, customer_name, sales=sales_amount)


def add_collection_totals(totals, filters, employee_salesperson_map):
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
        key = employee_salesperson_map.get(row.employee) if row.employee else UNASSIGNED_KEY
        key = key or UNASSIGNED_KEY
        totals[key]["collection"] += collection_amount
        add_customer_amount(totals[key], row.customer, row.customer_name, collection=collection_amount)


def build_rows(salespeople, totals, filters):
    date_label = _("{0} to {1}").format(
        formatdate(filters.date_range[0], "d MMMM yyyy"),
        formatdate(filters.date_range[1], "d MMMM yyyy"),
    )
    sales_person_filter = filters.get("sales_person")
    keys = list(salespeople)

    for key in totals:
        if key != UNASSIGNED_KEY and key not in salespeople and (not sales_person_filter or sales_person_filter == key):
            sales_person = frappe.db.get_value(
                "Sales Person",
                key,
                ["name", "sales_person_name", "employee"],
                as_dict=True,
            )
            salespeople[key] = get_salesperson_display_row(sales_person, key)
            keys.append(key)

    keys.sort(key=lambda key: ((salespeople[key].sales_person_name or key).lower(), key))
    rows = [make_row(key, salespeople[key], totals[key], date_label) for key in keys]

    if not sales_person_filter and (totals[UNASSIGNED_KEY]["sales"] or totals[UNASSIGNED_KEY]["collection"]):
        rows.append(
            make_row(
                UNASSIGNED_KEY,
                frappe._dict(
                    {
                        "sales_person": "",
                        "sales_person_name": _("Unassigned"),
                        "employee": "",
                        "employee_name": "",
                        "headquarter": _("Not Set"),
                    }
                ),
                totals[UNASSIGNED_KEY],
                date_label,
            )
        )
    return rows


def get_salesperson_display_row(sales_person, fallback):
    if not sales_person:
        return frappe._dict(
            {
                "sales_person": fallback,
                "sales_person_name": fallback,
                "employee": "",
                "employee_name": "",
                "headquarter": "",
            }
        )

    employee = None
    if sales_person.employee:
        employee = frappe.db.get_value(
            "Employee",
            sales_person.employee,
            ["employee_name", "custom_headquarter"],
            as_dict=True,
        )

    return frappe._dict(
        {
            "sales_person": sales_person.name,
            "sales_person_name": sales_person.sales_person_name or sales_person.name,
            "employee": sales_person.employee or "",
            "employee_name": employee.employee_name if employee else "",
            "headquarter": employee.custom_headquarter if employee else "",
        }
    )


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


def make_row(key, sales_person, totals, date_label):
    sales = flt(totals["sales"], 2)
    collection = flt(totals["collection"], 2)
    sales_person_name = sales_person.sales_person_name or sales_person.sales_person or _("Not Set")
    headquarter = sales_person.headquarter or _("Not Set")

    return {
        "sales_person": sales_person.sales_person if key != UNASSIGNED_KEY else "",
        "sales_person_name": sales_person_name,
        "employee": sales_person.employee if key != UNASSIGNED_KEY else "",
        "employee_name": sales_person.employee_name if key != UNASSIGNED_KEY else "",
        "headquarter": headquarter,
        "sales": sales,
        "collection": collection,
        "whatsapp_message": "\n".join(
            [
                _("Name: {0}").format(sales_person_name),
                _("Headquarter: {0}").format(headquarter),
                _("Period: {0}").format(date_label),
                _("Sales: {0}").format(format_indian_currency(sales)),
                _("Collection: {0}").format(format_indian_currency(collection)),
            ]
        ),
        "detailed_whatsapp_message": build_detailed_message(
            sales_person_name,
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
            "label": _("Sales Person"),
            "fieldname": "sales_person",
            "fieldtype": "Link",
            "options": "Sales Person",
            "width": 180,
        },
        {"label": _("Name"), "fieldname": "sales_person_name", "fieldtype": "Data", "width": 180},
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 150},
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
