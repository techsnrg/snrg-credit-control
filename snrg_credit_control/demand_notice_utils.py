"""
demand_notice_utils.py — Pure utility functions for Demand Notice generation.

Deliberately kept separate from credit_status.py:
  - credit_status fetches invoices OLDER than a threshold (for credit hold decisions)
  - demand_notice_utils fetches ALL outstanding invoices (for legal demand totals)
"""

import frappe
from frappe.utils import flt, getdate, today


# ---------------------------------------------------------------------------
# Invoice Fetching
# ---------------------------------------------------------------------------

def get_overdue_invoices_for_notice(customer, company):
    """
    Fetch all submitted Sales Invoices with any outstanding balance for the
    given customer and company, ordered oldest first.

    No cutoff date is applied — a demand notice addresses the customer's
    total outstanding debt, not just invoices past a threshold age.

    Returns a list of dicts with keys:
        name, posting_date, due_date, outstanding_amount
    """
    return frappe.get_all(
        "Sales Invoice",
        filters={
            "docstatus": 1,
            "is_return": 0,
            "customer": customer,
            "company": company,
            "outstanding_amount": (">", 0),
        },
        fields=["name", "posting_date", "due_date", "outstanding_amount"],
        order_by="posting_date asc",
    )


# ---------------------------------------------------------------------------
# Interest Calculation
# ---------------------------------------------------------------------------

def calculate_interest(outstanding_amount, overdue_days, annual_rate, threshold_days=60):
    """
    Simple interest formula:  I = P × (R / 100) × (T / 365)

    Args:
        outstanding_amount (float): Principal — the unpaid invoice amount.
        overdue_days (int): Days elapsed since invoice posting_date.
        annual_rate (float): Annual interest rate as a percentage (e.g. 18.0).
        threshold_days (int): Grace period before interest starts accruing.

    Returns:
        float: Interest amount rounded to 2 decimal places.
               Returns 0.0 if any argument is missing or zero.
    """
    if not outstanding_amount or overdue_days is None or not annual_rate:
        return 0.0
    if overdue_days <= 0:
        return 0.0

    chargeable_days = max(0, int(overdue_days) - int(threshold_days or 0))
    if chargeable_days <= 0:
        return 0.0

    rate_decimal = flt(annual_rate) / 100.0
    time_fraction = flt(chargeable_days) / 365.0
    interest = flt(outstanding_amount) * rate_decimal * time_fraction
    return round(interest, 2)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def fetch_invoices_for_notice(customer, company, interest_rate, threshold_days=60):
    """
    Fetch overdue invoices for a customer, compute per-invoice interest,
    and return rows ready to populate the Demand Notice Invoice child table.

    Args:
        customer (str): Customer docname.
        company (str): Company docname.
        interest_rate (float): Annual interest rate % from Demand Notice Settings.
        threshold_days (int): Days to wait before interest begins to accrue.

    Returns:
        list of dicts, each matching Demand Notice Invoice fields:
            sales_invoice, posting_date, due_date, outstanding_amount,
            overdue_days, interest_amount, total_payable
    """
    today_date = getdate(today())
    invoices = get_overdue_invoices_for_notice(customer, company)

    rows = []
    for inv in invoices:
        posting_date = getdate(inv.posting_date)
        overdue_days = (today_date - posting_date).days
        interest = calculate_interest(
            flt(inv.outstanding_amount),
            overdue_days,
            flt(interest_rate),
            threshold_days,
        )
        rows.append({
            "sales_invoice": inv.name,
            "posting_date": inv.posting_date,
            "due_date": inv.due_date,
            "outstanding_amount": flt(inv.outstanding_amount),
            "overdue_days": overdue_days,
            "interest_amount": interest,
            "total_payable": round(flt(inv.outstanding_amount) + interest, 2),
        })

    return rows


# ---------------------------------------------------------------------------
# Signatory lookup
# ---------------------------------------------------------------------------

def get_employee_signatory_details(user):
    """
    Look up the Employee record linked to the given user and return
    signatory details for the Demand Notice.

    Args:
        user (str): Frappe User ID (e.g. 'nikhil@snrgindia.com').

    Returns:
        dict with keys: employee_name, designation, bar_council_number,
        official_mobile, signature_image. All values default to empty string
        if not found.
    """
    emp = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        [
            "employee_name",
            "designation",
            "custom_bar_council_number",
            "custom_official_mobile",
            "custom_signature_image",
        ],
        as_dict=True,
    )
    if not emp:
        return {
            "employee_name": "",
            "designation": "",
            "bar_council_number": "",
            "official_mobile": "",
            "signature_image": "",
        }
    return {
        "employee_name": emp.employee_name or "",
        "designation": emp.designation or "",
        "bar_council_number": emp.custom_bar_council_number or "",
        "official_mobile": emp.custom_official_mobile or "",
        "signature_image": emp.custom_signature_image or "",
    }
