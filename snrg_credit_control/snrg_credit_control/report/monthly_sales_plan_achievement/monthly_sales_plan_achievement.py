from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from snrg_credit_control.snrg_credit_control.doctype.monthly_sales_plan.monthly_sales_plan import (
    get_month_label,
    get_plan_sales_people,
    get_sales_invoice_actuals,
    normalize_plan_month,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    plans = get_plans(filters)
    rows = build_rows(plans, filters)
    return get_columns(), rows, None, None, get_report_summary(rows)


def validate_filters(filters):
    if not filters.get("company"):
        frappe.throw(_("Please select a Company."))
    if not filters.get("plan_month"):
        frappe.throw(_("Please select a Plan Month."))
    filters.plan_month = normalize_plan_month(filters.plan_month)


def get_plans(filters):
    plan_filters = {
        "company": filters.company,
        "plan_month": filters.plan_month,
        "docstatus": 1,
    }

    if filters.get("sales_person"):
        plan_filters["sales_person"] = filters.sales_person
    if not filters.get("include_superseded"):
        plan_filters["is_current_plan"] = 1
        plan_filters["status"] = "Frozen"
    elif filters.get("status"):
        plan_filters["status"] = filters.status
    else:
        plan_filters["status"] = ["in", ["Frozen", "Superseded"]]

    return frappe.get_all(
        "Monthly Sales Plan",
        filters=plan_filters,
        fields=[
            "name",
            "company",
            "plan_date",
            "plan_month",
            "sales_person",
            "sales_person_name",
            "status",
            "is_current_plan",
            "revision_no",
            "previous_plan",
            "revision_date",
            "total_planned_amount",
        ],
        order_by="sales_person_name asc, revision_no desc, name asc",
    )


def build_rows(plans, filters):
    rows = []
    customer_filter = filters.get("customer")
    customer_group_filter = filters.get("customer_group")
    territory_filter = filters.get("territory")
    team_members_by_plan = get_team_members_by_plan([plan.name for plan in plans])
    team_member_ids_by_plan = get_team_member_ids_by_plan([plan.name for plan in plans])

    for plan in plans:
        actuals = get_sales_invoice_actuals(
            plan.company,
            plan.plan_month,
            get_plan_sales_people(plan.sales_person, team_member_ids_by_plan.get(plan.name, [])),
        )
        previous_amounts = get_previous_plan_amounts(plan.previous_plan)
        child_rows = frappe.get_all(
            "Monthly Sales Plan Customer",
            filters={"parent": plan.name, "parenttype": "Monthly Sales Plan"},
            fields=[
                "customer",
                "customer_name",
                "responsible_sales_person",
                "customer_city",
                "customer_group",
                "territory",
                "last_month_sales",
                "current_credit_limit",
                "credit_limit_available",
                "planned_amount",
                "minimum_payment_required",
                "projected_75_plus_outstanding",
                "remarks",
                "idx",
            ],
            order_by="idx asc",
        )

        for child in child_rows:
            if customer_filter and child.customer != customer_filter:
                continue
            if customer_group_filter and child.customer_group != customer_group_filter:
                continue
            if territory_filter and child.territory != territory_filter:
                continue

            planned_amount = flt(child.planned_amount, 2)
            achieved_amount = flt(actuals.get(child.customer, 0), 2) if child.customer else 0
            original_amount = previous_amounts.get(make_previous_key(child), planned_amount)
            rows.append(
                {
                    "plan": plan.name,
                    "plan_date": plan.plan_date,
                    "plan_month": get_month_label(plan.plan_month),
                    "sales_person": plan.sales_person,
                    "sales_person_name": plan.sales_person_name,
                    "team_members": ", ".join(team_members_by_plan.get(plan.name, [])),
                    "customer": child.customer,
                    "customer_name": child.customer_name or child.customer,
                    "responsible_sales_person": child.responsible_sales_person,
                    "customer_city": child.customer_city,
                    "customer_group": child.customer_group,
                    "territory": child.territory,
                    "last_month_sales": child.last_month_sales,
                    "current_credit_limit": child.current_credit_limit,
                    "credit_limit_available": child.credit_limit_available,
                    "planned_amount": planned_amount,
                    "original_planned_amount": flt(original_amount, 2),
                    "minimum_payment_required": child.minimum_payment_required,
                    "projected_75_plus_outstanding": child.projected_75_plus_outstanding,
                    "achieved_amount": achieved_amount,
                    "variance_amount": flt(achieved_amount - planned_amount, 2),
                    "achievement_percent": flt(achieved_amount * 100 / planned_amount, 2)
                    if planned_amount
                    else 0,
                    "revision_no": plan.revision_no,
                    "revision_status": _("Revised") if flt(plan.revision_no) > 1 else _("Original"),
                    "plan_status": plan.status,
                    "is_current_plan": plan.is_current_plan,
                    "revision_date": plan.revision_date,
                    "remarks": child.remarks,
                }
            )

    return rows


def get_team_members_by_plan(plan_names):
    if not plan_names:
        return {}

    rows = frappe.db.sql(
        """
        SELECT team.parent, team.sales_person, sp.sales_person_name
        FROM `tabMonthly Sales Plan Team Member` team
        LEFT JOIN `tabSales Person` sp ON sp.name = team.sales_person
        WHERE team.parenttype = 'Monthly Sales Plan'
          AND team.parent IN %(plan_names)s
        ORDER BY team.parent, team.idx
        """,
        {"plan_names": tuple(plan_names)},
        as_dict=True,
    )

    team_members = {}
    for row in rows:
        team_members.setdefault(row.parent, []).append(row.sales_person_name or row.sales_person)
    return team_members


def get_team_member_ids_by_plan(plan_names):
    if not plan_names:
        return {}

    rows = frappe.get_all(
        "Monthly Sales Plan Team Member",
        filters={"parenttype": "Monthly Sales Plan", "parent": ["in", plan_names]},
        fields=["parent", "sales_person", "idx"],
        order_by="parent, idx",
    )

    team_members = {}
    for row in rows:
        team_members.setdefault(row.parent, []).append(row.sales_person)
    return team_members


def get_previous_plan_amounts(previous_plan):
    if not previous_plan:
        return {}

    rows = frappe.get_all(
        "Monthly Sales Plan Customer",
        filters={"parent": previous_plan, "parenttype": "Monthly Sales Plan"},
        fields=["customer", "customer_name", "planned_amount"],
    )
    return {make_previous_key(row): flt(row.planned_amount, 2) for row in rows}


def make_previous_key(row):
    if row.customer:
        return f"customer:{row.customer}"
    return f"lead:{(row.customer_name or '').strip().lower()}"


def get_report_summary(rows):
    planned = flt(sum(flt(row.get("planned_amount")) for row in rows), 2)
    original = flt(sum(flt(row.get("original_planned_amount")) for row in rows), 2)
    achieved = flt(sum(flt(row.get("achieved_amount")) for row in rows), 2)
    variance = flt(achieved - planned, 2)
    achievement = flt(achieved * 100 / planned, 2) if planned else 0

    return [
        {"value": planned, "label": _("Planned"), "datatype": "Currency"},
        {"value": original, "label": _("Original Plan"), "datatype": "Currency"},
        {"value": achieved, "label": _("Achieved"), "datatype": "Currency"},
        {"value": variance, "label": _("Variance"), "datatype": "Currency"},
        {"value": achievement, "label": _("Achievement %"), "datatype": "Percent"},
    ]


def get_columns():
    return [
        {"label": _("Plan"), "fieldname": "plan", "fieldtype": "Link", "options": "Monthly Sales Plan", "width": 150},
        {"label": _("Plan Date"), "fieldname": "plan_date", "fieldtype": "Date", "width": 110},
        {"label": _("Month"), "fieldname": "plan_month", "fieldtype": "Data", "width": 120},
        {
            "label": _("Sales Person"),
            "fieldname": "sales_person",
            "fieldtype": "Link",
            "options": "Sales Person",
            "width": 160,
        },
        {"label": _("Sales Person Name"), "fieldname": "sales_person_name", "fieldtype": "Data", "width": 170},
        {"label": _("Team Members"), "fieldname": "team_members", "fieldtype": "Data", "width": 220},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": _("Customer / New Lead"), "fieldname": "customer_name", "fieldtype": "Data", "width": 220},
        {
            "label": _("Responsible Sales Person"),
            "fieldname": "responsible_sales_person",
            "fieldtype": "Link",
            "options": "Sales Person",
            "width": 180,
        },
        {"label": _("City"), "fieldname": "customer_city", "fieldtype": "Data", "width": 120},
        {
            "label": _("Customer Group"),
            "fieldname": "customer_group",
            "fieldtype": "Link",
            "options": "Customer Group",
            "width": 140,
        },
        {"label": _("Territory"), "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 140},
        {"label": _("Last Month Sales"), "fieldname": "last_month_sales", "fieldtype": "Currency", "width": 135},
        {"label": _("Credit Limit"), "fieldname": "current_credit_limit", "fieldtype": "Currency", "width": 125},
        {
            "label": _("Credit Limit Available"),
            "fieldname": "credit_limit_available",
            "fieldtype": "Currency",
            "width": 150,
        },
        {"label": _("Original Plan"), "fieldname": "original_planned_amount", "fieldtype": "Currency", "width": 130},
        {"label": _("Planned"), "fieldname": "planned_amount", "fieldtype": "Currency", "width": 130},
        {
            "label": _("Minimum Payment Required"),
            "fieldname": "minimum_payment_required",
            "fieldtype": "Currency",
            "width": 165,
        },
        {
            "label": _("75+ Outstanding at Month End"),
            "fieldname": "projected_75_plus_outstanding",
            "fieldtype": "Currency",
            "width": 185,
        },
        {"label": _("Achieved"), "fieldname": "achieved_amount", "fieldtype": "Currency", "width": 130},
        {"label": _("Variance"), "fieldname": "variance_amount", "fieldtype": "Currency", "width": 130},
        {"label": _("Achievement %"), "fieldname": "achievement_percent", "fieldtype": "Percent", "width": 120},
        {"label": _("Revision"), "fieldname": "revision_no", "fieldtype": "Int", "width": 90},
        {"label": _("Revision Status"), "fieldname": "revision_status", "fieldtype": "Data", "width": 120},
        {"label": _("Plan Status"), "fieldname": "plan_status", "fieldtype": "Data", "width": 110},
        {"label": _("Current"), "fieldname": "is_current_plan", "fieldtype": "Check", "width": 80},
        {"label": _("Revision Date"), "fieldname": "revision_date", "fieldtype": "Date", "width": 120},
        {"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Small Text", "width": 220},
    ]
