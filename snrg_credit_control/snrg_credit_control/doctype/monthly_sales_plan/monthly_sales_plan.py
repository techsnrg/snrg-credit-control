from __future__ import annotations

import calendar
from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, cint, flt, get_first_day, get_last_day, getdate, nowdate


class MonthlySalesPlan(Document):
    def validate(self):
        self._set_plan_date()
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

    def _set_plan_date(self):
        if not self.plan_date:
            self.plan_date = nowdate()

    def _normalize_month(self):
        if self.plan_month:
            self.plan_month = normalize_plan_month(self.plan_month)

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
        sales_people = get_plan_sales_people(self.sales_person, self.team_members)
        actuals = get_sales_invoice_actuals(self.company, self.plan_month, sales_people)
        metrics = get_customer_metrics(
            self.company,
            self.plan_month,
            sales_people,
            [row.customer for row in self.customers if row.customer],
        )
        for row in self.customers:
            row_metrics = metrics.get(row.customer, {}) if row.customer else {}
            row.last_month_sales = flt(row_metrics.get("last_month_sales"), 2)
            row.current_credit_limit = flt(row_metrics.get("current_credit_limit"), 2)
            row.credit_limit_available = flt(row_metrics.get("credit_limit_available"), 2)
            row.projected_75_plus_outstanding = flt(row_metrics.get("projected_75_plus_outstanding"), 2)
            row.achieved_amount = flt(actuals.get(row.customer, 0), 2) if row.customer else 0
            row.minimum_payment_required = flt(
                max(flt(row.planned_amount) - flt(row.credit_limit_available), 0),
                2,
            )
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
def fetch_customers(company, plan_month, sales_person, team_members=None):
    if not company:
        frappe.throw(_("Please select a Company."))
    if not plan_month:
        frappe.throw(_("Please select a Plan Month."))
    if not sales_person:
        frappe.throw(_("Please select a Sales Person."))

    sales_people = get_plan_sales_people(sales_person, team_members)
    rows = frappe.db.sql(
        """
        SELECT DISTINCT
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
          AND st.sales_person IN %(sales_people)s
          AND LOWER(IFNULL(c.customer_group, '')) NOT IN ('vendor', 'vendors')
        ORDER BY c.customer_name ASC, c.name ASC
        """,
        {"sales_people": tuple(sales_people)},
        as_dict=True,
    )
    metrics = get_customer_metrics(company, plan_month, sales_people, [row.customer for row in rows])
    for row in rows:
        row.update(metrics.get(row.customer, {}))

    return rows


def get_plan_sales_people(sales_person=None, team_members=None):
    sales_people = []
    if isinstance(sales_person, (list, tuple)):
        sales_people.extend(sales_person)
    elif sales_person:
        sales_people.append(sales_person)

    if isinstance(team_members, str) and team_members.strip().startswith(("[", "{")):
        team_members = frappe.parse_json(team_members) or []
    elif isinstance(team_members, str):
        team_members = [team_members]

    for row in team_members or []:
        member = row.get("sales_person") if isinstance(row, dict) else row
        if member:
            sales_people.append(member)

    return list(dict.fromkeys(sales_people))


@frappe.whitelist()
def make_revision(source_name):
    source = frappe.get_doc("Monthly Sales Plan", source_name)
    if source.docstatus != 1:
        frappe.throw(_("Only a submitted plan can be revised."))
    if source.status == "Cancelled":
        frappe.throw(_("Cancelled plans cannot be revised."))

    revision = frappe.new_doc("Monthly Sales Plan")
    revision.company = source.company
    revision.plan_date = nowdate()
    revision.plan_month = source.plan_month
    revision.sales_person = source.sales_person
    revision.sales_person_name = source.sales_person_name
    revision.status = "Draft"
    revision.is_current_plan = 0
    revision.revision_no = cint(source.revision_no) + 1
    revision.previous_plan = source.name
    revision.revision_date = nowdate()
    revision.revision_reason = source.revision_reason

    for row in source.team_members:
        revision.append("team_members", {"sales_person": row.sales_person})

    for row in source.customers:
        revision.append(
            "customers",
            {
                "customer": row.customer,
                "customer_name": row.customer_name,
                "customer_group": row.customer_group,
                "territory": row.territory,
                "last_month_sales": row.last_month_sales,
                "current_credit_limit": row.current_credit_limit,
                "credit_limit_available": row.credit_limit_available,
                "planned_amount": row.planned_amount,
                "minimum_payment_required": row.minimum_payment_required,
                "projected_75_plus_outstanding": row.projected_75_plus_outstanding,
                "remarks": row.remarks,
            },
        )

    revision.insert()
    return revision.name


def get_sales_invoice_actuals(company, plan_month, sales_person=None):
    if not company or not plan_month:
        return {}

    sales_people = get_plan_sales_people(team_members=sales_person)
    values = {
        "company": company,
        "from_date": get_plan_month_start(plan_month),
        "to_date": get_plan_month_end(plan_month),
    }
    salesperson_condition = ""
    if sales_people:
        values["sales_people"] = tuple(sales_people)
        salesperson_condition = "AND st.sales_person IN %(sales_people)s"

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


def get_customer_metrics(company, plan_month, sales_person=None, customers=None):
    if not company or not plan_month:
        return {}

    customer_list = [customer for customer in (customers or []) if customer]
    if not customer_list:
        return {}

    plan_month = get_plan_month_start(plan_month)
    previous_month = add_months(plan_month, -1)
    sales_people = get_plan_sales_people(team_members=sales_person)
    values = {
        "company": company,
        "previous_month_start": get_first_day(previous_month),
        "previous_month_end": get_last_day(previous_month),
        "plan_month_end": get_last_day(plan_month),
        "customers": tuple(customer_list),
    }

    sales_person_condition = ""
    if sales_people:
        values["sales_people"] = tuple(sales_people)
        sales_person_condition = "AND st.sales_person IN %(sales_people)s"

    last_month_sales = frappe.db.sql(
        """
        SELECT
            si.customer,
            SUM(si.base_net_total * IFNULL(st.allocated_percentage, 0) / 100) AS last_month_sales
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Team` st
            ON st.parent = si.name
            AND st.parenttype = 'Sales Invoice'
            AND st.parentfield = 'sales_team'
            {sales_person_condition}
        WHERE si.docstatus = 1
          AND si.is_return = 0
          AND si.company = %(company)s
          AND si.customer IN %(customers)s
          AND si.posting_date BETWEEN %(previous_month_start)s AND %(previous_month_end)s
        GROUP BY si.customer
        """.format(sales_person_condition=sales_person_condition),
        values,
        as_dict=True,
    )

    credit_rows = frappe.db.sql(
        """
        SELECT
            c.name AS customer,
            COALESCE(MAX(ccl.credit_limit), 0) AS current_credit_limit,
            COALESCE(SUM(CASE WHEN si.outstanding_amount > 0 THEN si.outstanding_amount ELSE 0 END), 0) AS current_outstanding,
            COALESCE(SUM(
                CASE
                    WHEN si.outstanding_amount > 0
                     AND DATEDIFF(%(plan_month_end)s, si.posting_date) > 75
                    THEN si.outstanding_amount
                    ELSE 0
                END
            ), 0) AS projected_75_plus_outstanding
        FROM `tabCustomer` c
        LEFT JOIN `tabCustomer Credit Limit` ccl
            ON ccl.parent = c.name
            AND ccl.company = %(company)s
        LEFT JOIN `tabSales Invoice` si
            ON si.customer = c.name
            AND si.docstatus = 1
            AND si.is_return = 0
            AND si.company = %(company)s
        WHERE c.name IN %(customers)s
        GROUP BY c.name
        """,
        values,
        as_dict=True,
    )

    metrics = {
        row.customer: {
            "last_month_sales": 0,
            "current_credit_limit": flt(row.current_credit_limit, 2),
            "credit_limit_available": flt(flt(row.current_credit_limit) - flt(row.current_outstanding), 2),
            "projected_75_plus_outstanding": flt(row.projected_75_plus_outstanding, 2),
        }
        for row in credit_rows
    }

    for row in last_month_sales:
        metrics.setdefault(row.customer, {})
        metrics[row.customer]["last_month_sales"] = flt(row.last_month_sales, 2)

    return metrics


def get_month_label(plan_month):
    if not plan_month:
        return ""
    date_value = get_plan_month_start(plan_month)
    return f"{calendar.month_name[date_value.month]} {date_value.year}"


def normalize_plan_month(plan_month):
    plan_month = str(plan_month or "").strip()
    if len(plan_month) == 7 and plan_month[4] == "-":
        return plan_month

    date_value = getdate(plan_month)
    return f"{date_value.year}-{date_value.month:02d}"


def get_plan_month_start(plan_month):
    plan_month = str(plan_month or "").strip()
    if len(plan_month) == 7 and plan_month[4] == "-":
        return getdate(f"{plan_month}-01")
    return get_first_day(getdate(plan_month))


def get_plan_month_end(plan_month):
    return get_last_day(get_plan_month_start(plan_month))


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
