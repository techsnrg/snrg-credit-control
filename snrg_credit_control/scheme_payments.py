"""Payment-based scheme qualification and in-app reminder previews."""
from collections import defaultdict
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate


def payment_rules(scheme):
    if not cint(scheme.get("require_payment_clearance")):
        return None
    soft = cint(scheme.payment_soft_days)
    hard = scheme.payment_hard_deadline
    if soft <= 0 or not hard or getdate(hard) < getdate(scheme.valid_from):
        frappe.throw(_("Set a positive payment soft deadline and a hard deadline on or after the scheme start."))
    try:
        days = sorted({int(day.strip()) for day in (scheme.payment_reminder_days or "").split(",") if day.strip()})
    except ValueError:
        frappe.throw(_("Enter reminder days as comma-separated whole numbers."))
    if not days or any(day <= 0 or day > soft for day in days):
        frappe.throw(_("Set reminder days between day 1 and the soft deadline."))
    return {"soft_days": soft, "hard_deadline": getdate(hard), "reminder_days": days}


def invoice_clearance(invoice_names, as_on_date):
    if not invoice_names:
        return {}
    rows = frappe.db.sql(
        """
        select invoice.name as invoice, invoice.posting_date as invoice_date, invoice.is_return,
               invoice.return_against, ple.posting_date, ple.voucher_type, ple.voucher_no,
               ple.account_currency, ple.amount_in_account_currency as amount
        from `tabSales Invoice` invoice
        left join `tabPayment Ledger Entry` ple
          on ple.against_voucher_type = 'Sales Invoice' and ple.against_voucher_no = invoice.name
          and ple.party_type = 'Customer' and ple.party = invoice.customer
          and ple.company = invoice.company and ple.account = invoice.debit_to
          and ple.delinked = 0 and ple.posting_date <= %(as_on)s
        where invoice.name in %(names)s and invoice.docstatus = 1
        order by invoice.name, ple.posting_date
        """, {"as_on": as_on_date, "names": tuple(invoice_names)}, as_dict=True,
    )
    invoices = {}
    for row in rows:
        data = invoices.setdefault(row.invoice, {
            "invoice": row.invoice, "invoice_date": row.invoice_date, "return_against": row.return_against,
            "is_return": row.is_return, "currency": None, "opening": Decimal(0),
            "movements": defaultdict(Decimal),
        })
        if not row.posting_date:
            continue
        amount = Decimal(str(row.amount or 0))
        data["currency"] = row.account_currency
        data["movements"][max(row.posting_date, row.invoice_date)] += amount
        if row.voucher_type == "Sales Invoice" and row.voucher_no == row.invoice:
            data["opening"] += amount

    precision = cint(frappe.db.get_single_value("System Settings", "currency_precision")) or 2
    fraction = Decimal(1).scaleb(-precision)
    for data in invoices.values():
        balance = Decimal(0)
        cleared = None
        for date, amount in sorted(data.pop("movements").items()):
            balance += amount
            if balance.quantize(fraction) <= 0:
                cleared = cleared or date
            else:
                cleared = None
        opening = data.pop("opening")
        verified = opening > 0 and not data["is_return"]
        data.update(
            outstanding=float(max(balance, 0).quantize(fraction)) if verified else None,
            clearance_date=cleared if verified else None,
            opening=float(opening) if verified else None,
        )
    return invoices


def _payment(data, rules, date):
    hard = rules["hard_deadline"]
    cleared = data.get("clearance_date")
    outstanding = data.get("outstanding")
    soft = add_days(data["invoice_date"], rules["soft_days"])
    soft = getdate(soft)
    if outstanding is None:
        status = "Unverified"
    elif cleared and cleared <= hard:
        status = "Cleared"
    elif cleared:
        status = "Cleared after deadline"
    else:
        partly_paid = outstanding < data["opening"]
        if date > hard:
            status = "Partly paid · deadline missed" if partly_paid else "Unpaid · deadline missed"
        else:
            status = "Partly paid" if partly_paid else "Unpaid"
    scheduled = {min(getdate(add_days(data["invoice_date"], day)), hard) for day in rules["reminder_days"]}
    scheduled.add(hard)
    return {
        "invoice": data["invoice"], "currency": data["currency"], "outstanding": outstanding,
        "soft_deadline": soft, "hard_deadline": hard, "clearance_date": cleared,
        "status": status, "counts_for_reward": status == "Cleared",
        "reminder_due": bool(outstanding and date in scheduled and data["invoice_date"] <= date <= hard),
    }


def attach_qualification(config, customers, rules, date):
    from snrg_credit_control import scheme_engine as engine

    all_lines = [line for customer in customers for line in customer.get("eligible_rows", [])]
    invoices = invoice_clearance({line["sales_invoice"] for line in all_lines}, date)
    # A credit note reduces the eligible value of the original invoice. Its settlement is
    # already represented in the original invoice's payment ledger.
    returns_by_origin = defaultdict(list)
    for line in all_lines:
        original = invoices.get(line["sales_invoice"], {}).get("return_against")
        if line.get("is_return") and original:
            returns_by_origin[original].append(line)
    missing = set(returns_by_origin).difference(invoices)
    invoices.update(invoice_clearance(missing, date))
    states = {name: _payment(invoice, rules, date) for name, invoice in invoices.items() if not invoice["is_return"]}
    per_invoice = config.scheme_type == engine.INVOICE_AMOUNT_SLAB
    for customer in customers:
        lines = customer.get("eligible_rows", [])
        if per_invoice and customer.get("invoice") in returns_by_origin:
            lines = [*lines, *returns_by_origin[customer["invoice"]]]
        totals = defaultdict(float)
        categories = defaultdict(float)
        for line in lines:
            name = line["sales_invoice"]
            original = invoices.get(name, {}).get("return_against") if line.get("is_return") else name
            payment = states.get(original)
            if payment:
                line["payment"] = payment
                if not (per_invoice and customer.get("invoice") == name and line.get("is_return")):
                    totals[original] += flt(line["amount"])
                if payment["counts_for_reward"] and not (per_invoice and customer.get("invoice") == name and line.get("is_return")):
                    categories[line.get("category") or ""] += flt(line["amount"])

        cleared = max(0, sum(value for invoice, value in totals.items() if states[invoice]["counts_for_reward"]))
        if config.scheme_type == engine.CATEGORY_TARGET_SLAB:
            achieved, next_slab = engine._get_category_slab_progress(config.category_slabs, categories, cleared)
            category_shortfalls = engine._get_category_shortfalls(next_slab, categories)
        else:
            achieved, _, next_slab = engine._get_slab_progress(config.slabs, cleared)
            category_shortfalls = {}
        customer.update(
            eligible_cleared=cleared, claimable_rewards=engine._get_scheme_rewards(achieved, config.reward_policy),
            clearance_gap=max(0, flt(next_slab["amount"]) - cleared) if next_slab else 0,
            clearance_next_slab=next_slab, clearance_category_shortfalls=category_shortfalls,
            payment_invoices=[dict(states[invoice], scheme_eligible=total) for invoice, total in totals.items() if total > 0],
        )
