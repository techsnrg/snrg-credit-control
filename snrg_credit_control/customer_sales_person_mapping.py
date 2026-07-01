from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, flt


def _as_list(value):
    if not value:
        return []
    if isinstance(value, str):
        return json.loads(value)
    return value


def _require_customer_read():
    if not frappe.has_permission("Customer", "read"):
        frappe.throw(_("Not permitted to read Customer records."), frappe.PermissionError)


def _require_customer_write():
    if not frappe.has_permission("Customer", "write"):
        frappe.throw(_("Not permitted to update Customer sales teams."), frappe.PermissionError)


def _validate_sales_person(sales_person):
    if not sales_person:
        frappe.throw(_("Please select a Sales Person."))
    if not frappe.db.exists("Sales Person", sales_person):
        frappe.throw(_("Sales Person {0} does not exist.").format(frappe.bold(sales_person)))


def _validate_customer(customer):
    if not customer:
        frappe.throw(_("Customer is required."))
    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer {0} does not exist.").format(frappe.bold(customer)))


@frappe.whitelist()
def get_mapped_customers(
    sales_person=None,
    search=None,
    customer=None,
    customer_group=None,
    territory=None,
    limit_start=0,
    limit_page_length=50,
):
    _require_customer_read()
    conditions = []
    values = {
        "sales_person": sales_person or "",
        "limit_start": cint(limit_start),
        "limit_page_length": min(cint(limit_page_length) or 50, 200),
    }
    sales_team_join_condition = "1 = 0"

    if sales_person:
        _validate_sales_person(sales_person)
        sales_team_join_condition = """
            st.parent = c.name
            AND st.parenttype = 'Customer'
            AND st.parentfield = 'sales_team'
            AND st.sales_person = %(sales_person)s
        """

    if search:
        values["search"] = f"%{search}%"
        conditions.append(
            """(
                c.name LIKE %(search)s
                OR c.customer_name LIKE %(search)s
                OR c.customer_group LIKE %(search)s
                OR c.territory LIKE %(search)s
            )"""
        )
    if customer:
        conditions.append("c.name = %(customer)s")
        values["customer"] = customer
    if customer_group:
        conditions.append("c.customer_group = %(customer_group)s")
        values["customer_group"] = customer_group
    if territory:
        conditions.append("c.territory = %(territory)s")
        values["territory"] = territory

    where_clause = " AND ".join(conditions) if conditions else "1 = 1"

    rows = frappe.db.sql(
        """
        SELECT
            st.name AS row_name,
            c.name AS customer,
            c.customer_name,
            c.customer_group,
            c.territory,
            c.disabled,
            st.sales_person,
            sp.sales_person_name,
            st.allocated_percentage,
            st.idx,
            CASE WHEN st.name IS NULL THEN 0 ELSE 1 END AS is_mapped
        FROM `tabCustomer` c
        LEFT JOIN `tabSales Team` st ON {sales_team_join_condition}
        LEFT JOIN `tabSales Person` sp ON sp.name = st.sales_person
        WHERE {where_clause}
        ORDER BY c.customer_name ASC, c.name ASC, st.idx ASC
        LIMIT %(limit_start)s, %(limit_page_length)s
        """.format(
            sales_team_join_condition=sales_team_join_condition,
            where_clause=where_clause,
        ),
        values,
        as_dict=True,
    )

    total = frappe.db.sql(
        """
        SELECT COUNT(*)
        FROM `tabCustomer` c
        LEFT JOIN `tabSales Team` st ON {sales_team_join_condition}
        WHERE {where_clause}
        """.format(
            sales_team_join_condition=sales_team_join_condition,
            where_clause=where_clause,
        ),
        values,
    )[0][0]

    return {"rows": rows, "total": total}


@frappe.whitelist()
def get_available_customers(sales_person, search=None, customer_group=None, territory=None, limit_page_length=50):
    _require_customer_read()
    _validate_sales_person(sales_person)

    conditions = [
        "IFNULL(c.disabled, 0) = 0",
        """NOT EXISTS (
            SELECT 1
            FROM `tabSales Team` st
            WHERE st.parent = c.name
              AND st.parenttype = 'Customer'
              AND st.parentfield = 'sales_team'
              AND st.sales_person = %(sales_person)s
        )""",
    ]
    values = {
        "sales_person": sales_person,
        "limit_page_length": min(cint(limit_page_length) or 50, 200),
    }

    if search:
        values["search"] = f"%{search}%"
        conditions.append(
            """(
                c.name LIKE %(search)s
                OR c.customer_name LIKE %(search)s
                OR c.customer_group LIKE %(search)s
                OR c.territory LIKE %(search)s
            )"""
        )
    if customer_group:
        conditions.append("c.customer_group = %(customer_group)s")
        values["customer_group"] = customer_group
    if territory:
        conditions.append("c.territory = %(territory)s")
        values["territory"] = territory

    return frappe.db.sql(
        """
        SELECT
            c.name AS customer,
            c.customer_name,
            c.customer_group,
            c.territory
        FROM `tabCustomer` c
        WHERE {conditions}
        ORDER BY c.customer_name ASC, c.name ASC
        LIMIT %(limit_page_length)s
        """.format(conditions=" AND ".join(conditions)),
        values,
        as_dict=True,
    )


@frappe.whitelist()
def add_sales_person_to_customers(sales_person, customers, allocated_percentage=None):
    _require_customer_write()
    _validate_sales_person(sales_person)
    customers = list(dict.fromkeys(_as_list(customers)))
    if not customers:
        frappe.throw(_("Please select at least one customer."))

    explicit_percentage = allocated_percentage not in (None, "")
    percentage = flt(allocated_percentage) if explicit_percentage else None
    if explicit_percentage and (percentage < 0 or percentage > 100):
        frappe.throw(_("Allocation percentage must be between 0 and 100."))

    added = []
    skipped = []
    failed = []

    for customer in customers:
        try:
            _validate_customer(customer)
            doc = frappe.get_doc("Customer", customer)
            existing = [row for row in doc.get("sales_team", []) if row.sales_person == sales_person]
            if existing:
                skipped.append({"customer": customer, "reason": _("Already mapped")})
                continue

            row_percentage = percentage
            if row_percentage is None:
                row_percentage = 100 if not doc.get("sales_team") else 0

            doc.append(
                "sales_team",
                {
                    "sales_person": sales_person,
                    "allocated_percentage": row_percentage,
                },
            )
            doc.save(ignore_permissions=True)
            added.append(customer)
        except Exception as exc:
            failed.append({"customer": customer, "reason": str(exc)})
            frappe.log_error(
                title="Customer Sales Person Mapping Add Failed",
                message=frappe.get_traceback(),
            )

    frappe.db.commit()
    return {"added": added, "skipped": skipped, "failed": failed}


@frappe.whitelist()
def remove_sales_person_from_customers(sales_person, customers):
    _require_customer_write()
    _validate_sales_person(sales_person)
    customers = list(dict.fromkeys(_as_list(customers)))
    if not customers:
        frappe.throw(_("Please select at least one customer."))

    removed = []
    skipped = []
    failed = []

    for customer in customers:
        try:
            _validate_customer(customer)
            doc = frappe.get_doc("Customer", customer)
            rows = doc.get("sales_team", [])
            matching_rows = [row for row in rows if row.sales_person == sales_person]
            if not matching_rows:
                skipped.append({"customer": customer, "reason": _("Not mapped")})
                continue

            for row in matching_rows:
                doc.remove(row)
            doc.save(ignore_permissions=True)
            removed.append(customer)
        except Exception as exc:
            failed.append({"customer": customer, "reason": str(exc)})
            frappe.log_error(
                title="Customer Sales Person Mapping Remove Failed",
                message=frappe.get_traceback(),
            )

    frappe.db.commit()
    return {"removed": removed, "skipped": skipped, "failed": failed}
