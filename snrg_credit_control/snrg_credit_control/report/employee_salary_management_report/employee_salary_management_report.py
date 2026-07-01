from collections import defaultdict
from datetime import datetime

import frappe
from frappe import _
from frappe.utils import cint, flt, formatdate, get_first_day, get_last_day, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    from_date, to_date = get_month_range(filters.month)
    data = get_data(filters, from_date, to_date)
    message = get_print_header(filters.company, from_date, to_date)
    report_summary = get_report_summary(data)

    return get_columns(filters), data, message, None, report_summary


def validate_filters(filters):
    if not filters.get("company"):
        frappe.throw(_("Please select a Company."))
    if not filters.get("month"):
        frappe.throw(_("Please select a Month."))


def get_columns(filters):
    if filters.get("basic_report"):
        return [
            {
                "label": _("Employee Name"),
                "fieldname": "employee_name",
                "fieldtype": "Data",
                "width": 280,
            },
            {
                "label": _("Salary Amount"),
                "fieldname": "salary_amount",
                "fieldtype": "Currency",
                "options": "currency",
                "width": 150,
            },
        ]

    return [
        {
            "label": _("Sr No"),
            "fieldname": "sr_no",
            "fieldtype": "Int",
            "width": 60,
        },
        {
            "label": _("Posting Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 105,
        },
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 140,
        },
        {
            "label": _("Employee Name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": _("Salary Amount"),
            "fieldname": "salary_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 135,
        },
        {
            "label": _("Net Payable"),
            "fieldname": "net_payable",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 125,
        },
        {
            "label": _("Deductions / Adjustments"),
            "fieldname": "deductions",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 155,
        },
        {
            "label": _("Journal Entry"),
            "fieldname": "voucher_no",
            "fieldtype": "Link",
            "options": "Journal Entry",
            "width": 160,
        },
        {
            "label": _("User Remark"),
            "fieldname": "user_remark",
            "fieldtype": "Data",
            "width": 260,
        },
    ]


def get_data(filters, from_date, to_date):
    values = {
        "company": filters.company,
        "from_date": from_date,
        "to_date": to_date,
        "salary_account": filters.get("salary_account"),
        "employee": filters.get("employee"),
    }

    salary_rows = get_salary_rows(values)
    if not salary_rows:
        return []

    voucher_names = [row.voucher_no for row in salary_rows]
    all_employee_rows = get_employee_rows(voucher_names)
    employee_rows = [
        row
        for row in all_employee_rows
        if not filters.get("employee") or row.employee == filters.get("employee")
    ]
    if not employee_rows:
        return []

    salary_by_voucher = {row.voucher_no: row for row in salary_rows}
    employee_count_by_voucher = defaultdict(int)
    for row in all_employee_rows:
        employee_count_by_voucher[row.voucher_no] += 1

    rows = []
    for employee_row in employee_rows:
        salary_row = salary_by_voucher.get(employee_row.voucher_no)
        if not salary_row:
            continue

        salary_amount = flt(salary_row.salary_amount)
        if employee_count_by_voucher[employee_row.voucher_no] > 1:
            salary_amount = flt(employee_row.net_payable)

        rows.append(
            frappe._dict(
                {
                    "posting_date": salary_row.posting_date,
                    "employee": employee_row.employee,
                    "employee_name": employee_row.employee_name,
                    "salary_amount": salary_amount,
                    "net_payable": flt(employee_row.net_payable),
                    "deductions": salary_amount - flt(employee_row.net_payable),
                    "voucher_no": employee_row.voucher_no,
                    "user_remark": salary_row.user_remark,
                    "currency": salary_row.currency,
                }
            )
        )

    rows.sort(key=lambda row: (row.posting_date, row.employee_name or row.employee or "", row.voucher_no))
    for idx, row in enumerate(rows, start=1):
        row.sr_no = idx

    return rows


def get_salary_rows(values):
    salary_account_condition = "jea.account = %(salary_account)s"
    if not values.get("salary_account"):
        salary_account_condition = """
            jea.account IN (
                SELECT name
                FROM `tabAccount`
                WHERE company = %(company)s
                  AND is_group = 0
                  AND root_type = 'Expense'
                  AND account_name LIKE 'Salary%%'
            )
        """

    return frappe.db.sql(
        f"""
        SELECT
            je.name AS voucher_no,
            je.posting_date,
            je.user_remark,
            je.company,
            company.default_currency AS currency,
            SUM(jea.debit_in_account_currency - jea.credit_in_account_currency) AS salary_amount
        FROM `tabJournal Entry` je
        INNER JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
        INNER JOIN `tabCompany` company ON company.name = je.company
        WHERE je.docstatus = 1
          AND je.company = %(company)s
          AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND {salary_account_condition}
        GROUP BY je.name, je.posting_date, je.user_remark, je.company, company.default_currency
        HAVING salary_amount > 0
        ORDER BY je.posting_date ASC, je.name ASC
        """,
        values,
        as_dict=True,
    )


def get_employee_rows(voucher_names):
    if not voucher_names:
        return []

    values = {}
    placeholders = []
    for idx, voucher_name in enumerate(voucher_names):
        key = f"voucher_{idx}"
        placeholders.append(f"%({key})s")
        values[key] = voucher_name

    return frappe.db.sql(
        f"""
        SELECT
            jea.parent AS voucher_no,
            jea.party AS employee,
            COALESCE(emp.employee_name, jea.party) AS employee_name,
            SUM(jea.credit_in_account_currency - jea.debit_in_account_currency) AS net_payable
        FROM `tabJournal Entry Account` jea
        LEFT JOIN `tabEmployee` emp ON emp.name = jea.party
        WHERE jea.parent IN ({", ".join(placeholders)})
          AND jea.party_type = 'Employee'
          AND IFNULL(jea.party, '') != ''
        GROUP BY jea.parent, jea.party, emp.employee_name
        HAVING net_payable > 0
        ORDER BY employee_name ASC, employee ASC
        """,
        values,
        as_dict=True,
    )


def get_month_range(month_value):
    value = str(month_value)
    if len(value) == 7:
        parsed = datetime.strptime(value, "%Y-%m").date()
    else:
        parsed = getdate(value)

    return get_first_day(parsed), get_last_day(parsed)


def get_print_header(company, from_date, to_date):
    company_doc = frappe.get_cached_doc("Company", company)
    address = get_company_address(company)
    period = _("{0} to {1}").format(
        formatdate(from_date, "dd-MM-yyyy"),
        formatdate(to_date, "dd-MM-yyyy"),
    )

    address_html = f"<div>{frappe.utils.escape_html(address)}</div>" if address else ""
    return f"""
        <style>
            .salary-report-print-header {{
                margin: 0 0 12px;
                padding: 10px 0 12px;
                border-bottom: 1px solid #d9d9d9;
                text-align: center;
            }}
            .salary-report-print-header h2 {{
                margin: 0 0 4px;
                font-size: 18px;
                font-weight: 700;
            }}
            .salary-report-print-header .company-address {{
                color: #555;
                font-size: 11px;
                line-height: 1.4;
                white-space: pre-line;
            }}
            .salary-report-print-header .period {{
                margin-top: 8px;
                font-size: 13px;
                font-weight: 600;
            }}
            @media print {{
                .salary-report-print-header {{
                    margin-top: -8px;
                }}
            }}
        </style>
        <div class="salary-report-print-header">
            <h2>{frappe.utils.escape_html(company_doc.company_name or company)}</h2>
            <div class="company-address">{address_html}</div>
            <div class="period">{_("Employee Salary Management Report")} - {period}</div>
        </div>
    """


def get_company_address(company):
    address = frappe.db.sql(
        """
        SELECT
            address.address_line1,
            address.address_line2,
            address.city,
            address.state,
            address.pincode,
            address.country
        FROM `tabAddress` address
        INNER JOIN `tabDynamic Link` link
            ON link.parent = address.name
            AND link.parenttype = 'Address'
        WHERE link.link_doctype = 'Company'
          AND link.link_name = %s
          AND IFNULL(address.disabled, 0) = 0
        ORDER BY
            IFNULL(address.is_primary_address, 0) DESC,
            IFNULL(address.is_your_company_address, 0) DESC,
            address.creation ASC
        LIMIT 1
        """,
        (company,),
        as_dict=True,
    )
    if not address:
        return ""

    row = address[0]
    parts = [
        row.address_line1,
        row.address_line2,
        ", ".join(filter(None, [row.city, row.state, row.pincode])),
        row.country,
    ]
    return "\n".join(part for part in parts if part)


def get_report_summary(data):
    total_salary = sum(flt(row.salary_amount) for row in data)
    total_net_payable = sum(flt(row.net_payable) for row in data)
    total_deductions = sum(flt(row.deductions) for row in data)

    return [
        {
            "value": total_salary,
            "label": _("Total Salary"),
            "datatype": "Currency",
            "indicator": "Blue",
        },
        {
            "value": total_net_payable,
            "label": _("Net Payable"),
            "datatype": "Currency",
            "indicator": "Green",
        },
        {
            "value": total_deductions,
            "label": _("Deductions"),
            "datatype": "Currency",
            "indicator": "Orange" if cint(total_deductions) else "Grey",
        },
    ]
