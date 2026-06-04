from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, formatdate


UNASSIGNED_KEY = "__unassigned__"


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    employees = get_sales_employees(filters)
    totals = defaultdict(lambda: {"sales": 0.0, "collection": 0.0})

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
        for allocation in allocations:
            if allocation.employee:
                key = allocation.employee
                percentage = flt(allocation.allocated_percentage)
            else:
                key = UNASSIGNED_KEY
                percentage = 100 if len(allocations) == 1 else flt(allocation.allocated_percentage)
            totals[key]["sales"] += invoice_total * percentage / 100


def add_collection_totals(totals, filters):
    rows = frappe.db.sql(
        """
        SELECT
            IFNULL(pe.custom_incentive_sales_person_name, '') AS employee,
            COALESCE(SUM(pe.base_paid_amount), 0) AS collection
        FROM `tabPayment Entry` pe
        WHERE pe.docstatus = 1
          AND pe.payment_type = 'Receive'
          AND pe.party_type = 'Customer'
          AND pe.company = %(company)s
          AND pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY pe.custom_incentive_sales_person_name
        """,
        get_query_values(filters),
        as_dict=True,
    )

    for row in rows:
        totals[row.employee or UNASSIGNED_KEY]["collection"] += flt(row.collection)


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
    }


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
    ]
