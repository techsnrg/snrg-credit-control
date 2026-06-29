from __future__ import annotations

import calendar
from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, get_first_day, get_last_day, getdate, nowdate


class MonthlySalesPlan(Document):
    def validate(self):
        self._normalize_month()
        self._set_revision_defaults()
        self._set_customer_details()
        self._set_achievement_amounts()
        self._set_totals()

    def before_submit(self):
        self.status = "Frozen"
        self.is_current_plan = 1

    def on_submit(self):
        self._supersede_previous_plans()

    def on_cancel(self):
        self.db_set("status", "Cancelled", update_modified=False)
        self.db_set("is_current_plan", 0, update_modified=False)
        _activate_latest_plan(self.company, self.plan_month, self.sales_person, exclude=self.name)

    def _normalize_month(self):
        if self.plan_month:
            self.plan_month = get_first_day(getdate(self.plan_month))

    def _set_revision_defaults(self):
        if not self.revision_no:
            self.revision_no = 1
        if self.previous_plan and not self.revision_date:
            self.revision_date = nowdate()

    def _set_customer_details(self):
        for row in self.customers:
            if not row.customer:
                continue

            customer = frappe.db.get_value(
                "Customer",
                row.customer,
                ["customer_name", "customer_group", "territory"],
                as_dict=True,
            )
            if not customer:
                frappe.throw(_("Customer {0} was not found.").format(row.customer))

            row.customer_name = customer.customer_name or row.customer_name or row.customer
            row.customer_group = customer.customer_group
            row.territory = customer.territory

    def _set_achievement_amounts(self):
        actuals = get_sales_invoice_actuals(self.company, self.plan_month, self.sales_person)
        for row in self.customers:
            row.achieved_amount = flt(actuals.get(row.customer, 0), 2) if row.customer else 0
            row.variance_amount = flt(row.achieved_amount - flt(row.planned_amount), 2)
            row.achievement_percent = (
                flt(row.achieved_amount) * 100 / flt(row.planned_amount)
                if flt(row.planned_amount)
                else 0
            )

    def _set_totals(self):
        self.total_planned_amount = flt(sum(flt(row.planned_amount) for row in self.customers), 2)
        self.total_achieved_amount = flt(sum(flt(row.achieved_amount) for row in self.customers), 2)
        self.total_variance_amount = flt(self.total_achieved_amount - self.total_planned_amount, 2)
        self.achievement_percent = (
            flt(self.total_achieved_amount) * 100 / flt(self.total_planned_amount)
            if flt(self.total_planned_amount)
            else 0
        )

    def _supersede_previous_plans(self):
        previous_plans = frappe.get_all(
            "Monthly Sales Plan",
            filters={
                "company": self.company,
                "plan_month": self.plan_month,
                "sales_person": self.sales_person,
                "docstatus": 1,
                "name": ["!=", self.name],
            },
            pluck="name",
        )
        for plan_name in previous_plans:
            frappe.db.set_value(
                "Monthly Sales Plan",
                plan_name,
                {"status": "Superseded", "is_current_plan": 0},
                update_modified=False,
            )


@frappe.whitelist()
def fetch_customers(company, plan_month, sales_person):
    if not company:
        frappe.throw(_("Please select a Company."))
    if not plan_month:
        frappe.throw(_("Please select a Plan Month."))
    if not sales_person:
        frappe.throw(_("Please select a Sales Person."))

    rows = frappe.db.sql(
        """
        SELECT
            c.name AS customer,
            c.customer_name,
            c.customer_group,
            c.territory
        FROM `tabCustomer` c
        INNER JOIN `tabSales Team` st
            ON st.parent = c.name
            AND st.parenttype = 'Customer'
            AND st.parentfield = 'sales_team'
        WHERE IFNULL(c.disabled, 0) = 0
          AND st.sales_person = %(sales_person)s
          AND LOWER(IFNULL(c.customer_group, '')) NOT IN ('vendor', 'vendors')
        ORDER BY c.customer_name ASC, c.name ASC
        """,
        {"sales_person": sales_person},
        as_dict=True,
    )
    return rows


@frappe.whitelist()
def make_revision(source_name):
    source = frappe.get_doc("Monthly Sales Plan", source_name)
    if source.docstatus != 1:
        frappe.throw(_("Only a submitted plan can be revised."))
    if source.status == "Cancelled":
        frappe.throw(_("Cancelled plans cannot be revised."))

    revision = frappe.new_doc("Monthly Sales Plan")
    revision.company = source.company
    revision.plan_month = source.plan_month
    revision.sales_person = source.sales_person
    revision.sales_person_name = source.sales_person_name
    revision.status = "Draft"
    revision.is_current_plan = 0
    revision.revision_no = cint(source.revision_no) + 1
    revision.previous_plan = source.name
    revision.revision_date = nowdate()
    revision.revision_reason = source.revision_reason

    for row in source.customers:
        revision.append(
            "customers",
            {
                "customer": row.customer,
                "customer_name": row.customer_name,
                "customer_group": row.customer_group,
                "territory": row.territory,
                "planned_amount": row.planned_amount,
                "remarks": row.remarks,
            },
        )

    revision.insert()
    return revision.name


def get_sales_invoice_actuals(company, plan_month, sales_person=None):
    if not company or not plan_month:
        return {}

    values = {
        "company": company,
        "from_date": get_first_day(getdate(plan_month)),
        "to_date": get_last_day(getdate(plan_month)),
    }
    salesperson_condition = ""
    if sales_person:
        values["sales_person"] = sales_person
        salesperson_condition = "AND st.sales_person = %(sales_person)s"

    rows = frappe.db.sql(
        """
        SELECT
            si.name AS sales_invoice,
            si.customer,
            si.base_net_total,
            st.sales_person,
            st.allocated_percentage
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Team` st
            ON st.parent = si.name
            AND st.parenttype = 'Sales Invoice'
            AND st.parentfield = 'sales_team'
            {salesperson_condition}
        LEFT JOIN `tabCustomer` c ON c.name = si.customer
        WHERE si.docstatus = 1
          AND si.company = %(company)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND LOWER(IFNULL(c.customer_group, '')) NOT IN ('vendor', 'vendors')
        ORDER BY si.name ASC, st.idx ASC
        """.format(salesperson_condition=salesperson_condition),
        values,
        as_dict=True,
    )

    actuals = defaultdict(float)
    for row in rows:
        percentage = flt(row.allocated_percentage)
        actuals[row.customer] += flt(row.base_net_total) * percentage / 100

    return {customer: flt(amount, 2) for customer, amount in actuals.items()}


def get_month_label(plan_month):
    if not plan_month:
        return ""
    date_value = getdate(plan_month)
    return f"{calendar.month_name[date_value.month]} {date_value.year}"


def _activate_latest_plan(company, plan_month, sales_person, exclude=None):
    filters = {
        "company": company,
        "plan_month": plan_month,
        "sales_person": sales_person,
        "docstatus": 1,
        "status": ["!=", "Cancelled"],
    }
    if exclude:
        filters["name"] = ["!=", exclude]

    latest = frappe.get_all(
        "Monthly Sales Plan",
        filters=filters,
        fields=["name"],
        order_by="revision_no desc, modified desc",
        limit=1,
    )
    if not latest:
        return

    frappe.db.set_value(
        "Monthly Sales Plan",
        latest[0].name,
        {"status": "Frozen", "is_current_plan": 1},
        update_modified=False,
    )
