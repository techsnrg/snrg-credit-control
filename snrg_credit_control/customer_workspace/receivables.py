"""Compact AR presentation over ERPNext's permission-checked Payment Ledger report."""
import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today, date_diff
from snrg_credit_control.customer_workspace.api import guard
from snrg_credit_control.customer_workspace.directory import customer_cards

REPORT = "Accounts Receivable Summary"


def can_read():
    if not frappe.db.exists("Report", REPORT):
        return False
    report = frappe.get_doc("Report", REPORT)
    return not report.disabled and bool(report.is_permitted() and frappe.has_permission(report.ref_doctype, "report"))


def allowed_companies():
    if not can_read():
        return []
    return frappe.get_list("Company", fields=["name", "default_currency"], order_by="name", limit_page_length=0)


@frappe.whitelist()
def customer_ar(company, report_date=None, search="", territory=None, customer_group=None, balance="outstanding", customer=None, start=0):
    guard()
    if not can_read():
        frappe.throw(_("Accounts Receivable report access is required."), frappe.PermissionError)
    companies = {row.name: row.default_currency for row in allowed_companies()}
    if company not in companies:
        frappe.throw(_("Choose a company you have access to."), frappe.PermissionError)
    if balance not in ("all", "outstanding", "due", "credit"):
        frappe.throw(_("Choose a valid balance filter."))
    from frappe.desk.query_report import run
    filters = {"company": company, "report_date": str(getdate(report_date or today())), "ageing_based_on": "Due Date", "age_as_on": "Report Date", "range": "30,60,90,120", "in_party_currency": 0}
    if territory:
        filters["territory"] = territory
    if customer_group:
        filters["customer_group"] = customer_group
    if customer:
        filters["party"] = [customer]
    # Preserve ERPNext Report roles, Sales Invoice report permission, company and
    # user-permission filters. Do not read Sales Invoice balances with get_all.
    result = run(REPORT, filters=filters, ignore_prepared_report=True)
    aged_result = run(REPORT, filters={**filters, "ageing_based_on": "Posting Date"}, ignore_prepared_report=True)
    aged_rows = {row["party"]: row for row in aged_result.get("result", []) if isinstance(row, dict) and row.get("party") and not row.get("is_total_row")}
    native = [row for row in result.get("result", []) if isinstance(row, dict) and row.get("party") and not row.get("is_total_row")]
    identities = customer_cards([row["party"] for row in native])
    rows = []
    query = str(search or "").strip().casefold()
    for source in native:
        identity = identities.get(source["party"])
        if not identity:  # skip report totals/non-Customer rows
            continue
        aged = aged_rows.get(source["party"], {})
        outstanding, due = flt(source.get("outstanding")), flt(source.get("total_due"))
        if balance == "outstanding" and outstanding <= 0:
            continue
        if balance == "due" and due <= 0:
            continue
        if balance == "credit" and outstanding >= 0:
            continue
        if query and query not in " ".join(str(identity.get(key) or "") for key in ("name", "customer_name", "mobile_number")).casefold():
            continue
        rows.append({**identity, "outstanding": outstanding, "due_now": due,
                     "not_yet_due": flt(source.get("range0")), "advance": flt(source.get("advance")),
                     "age_0_30": flt(aged.get("range1")), "age_31_60": flt(aged.get("range2")),
                     "age_61_90": flt(aged.get("range3")),
                     "age_91_120": flt(aged.get("range4")), "age_over_120": flt(aged.get("range5")),
                     "currency": companies[company]})
    rows.sort(key=lambda row: (-row["due_now"], -row["outstanding"], row["customer_name"]))
    totals = {key: sum(row[key] for row in rows) for key in ("outstanding", "due_now", "advance", "not_yet_due")}
    start = max(0, cint(start))
    return {"rows": rows[start:start + 50], "count": len(rows), "has_more": len(rows) > start + 50,
            "totals": totals, "currency": companies[company], "report_date": filters["report_date"],
            "company": company, "due_note": _("Due now includes balances due on the selected date. Amounts use company currency.")}


@frappe.whitelist()
def customer_ar_invoices(company, customer, report_date=None, balance="all", start=0):
    guard()
    if not can_read() or company not in {row.name for row in allowed_companies()}:
        frappe.throw(_("Accounts Receivable report access is required."), frappe.PermissionError)
    if balance not in ("all", "outstanding", "due", "credit"):
        frappe.throw(_("Choose a valid balance filter."))
    from frappe.desk.query_report import run
    result = run("Accounts Receivable", filters={"company": company, "party": [customer], "report_date": str(getdate(report_date or today())), "ageing_based_on": "Due Date", "age_as_on": "Report Date", "range": "30,60,90,120", "in_party_currency": 0}, ignore_prepared_report=True)
    rows = []
    for row in result.get("result", []):
        if not isinstance(row, dict) or not row.get("voucher_no") or row.get("is_total_row"):
            continue
        outstanding = flt(row.get("outstanding"))
        if balance == "outstanding" and outstanding <= 0 or balance == "credit" and outstanding >= 0 or balance == "due" and flt(row.get("total_due")) <= 0:
            continue
        item = {key: row.get(key) for key in ("voucher_type", "voucher_no", "posting_date", "due_date", "outstanding", "currency")}
        basis = row.get("posting_date")
        item["age_days"] = date_diff(report_date or today(), basis) if basis else None
        item["age_basis"] = "posting_date" if basis else None
        rows.append(item)
    rows.sort(key=lambda row: str(row.get("due_date") or row.get("posting_date") or ""))
    start = max(0, cint(start))
    return {"rows": rows[start:start + 50], "count": len(rows), "has_more": len(rows) > start + 50}
