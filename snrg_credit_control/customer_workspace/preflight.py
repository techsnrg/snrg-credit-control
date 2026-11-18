"""Read-only native report reconciliation; never mutates ledger data."""
import frappe
from frappe.utils import today, flt, date_diff


def run():
    from frappe.desk.query_report import run as report
    from snrg_credit_control.customer_workspace import receivables as ar, payables as ap
    original = frappe.session.user
    results = []
    try:
        frappe.set_user("Administrator")
        for module, compact, detail, party_arg in ((ar, ar.customer_ar, ar.customer_ar_invoices, "customer"), (ap, ap.supplier_ap, ap.supplier_ap_invoices, "supplier")):
            for company in module.allowed_companies():
                filters = dict(company=company.name, report_date=today(), ageing_based_on="Due Date", age_as_on="Report Date", range="30,60,90,120", in_party_currency=0)
                native = {r["party"]: r for r in report(module.REPORT, filters=filters, ignore_prepared_report=True).get("result", []) if isinstance(r, dict) and r.get("party") and not r.get("is_total_row")}
                aged = {r["party"]: r for r in report(module.REPORT, filters={**filters, "ageing_based_on": "Posting Date"}, ignore_prepared_report=True).get("result", []) if isinstance(r, dict) and r.get("party") and not r.get("is_total_row")}
                rows, start = [], 0
                while True:
                    data = compact(company.name, balance="all", start=start)
                    rows.extend(data["rows"])
                    if not data["has_more"]:
                        break
                    start += 50
                for row in rows:
                    expected = native[row["name"]]
                    for field, source in (("outstanding", "outstanding"), ("due_now", "total_due"), ("advance", "advance"), ("not_yet_due", "range0")):
                        assert abs(flt(row[field])-flt(expected.get(source))) < .005, (module.REPORT, field)
                    for i, field in enumerate(("age_0_30", "age_31_60", "age_61_90", "age_91_120", "age_over_120"), 1):
                        assert abs(flt(row[field])-flt(aged.get(row["name"], {}).get("range"+str(i)))) < .005, (module.REPORT, field)
                    for invoice in detail(company.name, **{party_arg: row["name"]}, report_date=today(), balance="all")["rows"]:
                        assert invoice["age_days"] == date_diff(today(), invoice["posting_date"])
                assert abs(data["totals"]["outstanding"]-sum(r["outstanding"] for r in rows)) < .005
                results.append({"report": module.REPORT, "company": company.name, "parties_checked": len(rows), "totals_and_ageing": "matched native reports"})
        return results
    finally:
        frappe.set_user(original)
