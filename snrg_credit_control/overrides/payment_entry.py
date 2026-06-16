import frappe
from frappe.utils import flt

from erpnext.accounts.doctype.payment_entry.payment_entry import (
    get_outstanding_reference_documents as erpnext_get_outstanding_reference_documents,
)

VALUE_EPSILON = 0.01


@frappe.whitelist()
def get_outstanding_reference_documents(args, validate=False):
    rows = erpnext_get_outstanding_reference_documents(args, validate=validate) or []
    return _sync_invoice_outstanding(rows)


def _sync_invoice_outstanding(rows):
    invoice_names = _get_invoice_names(rows)
    if not invoice_names:
        return rows

    invoice_details = _get_invoice_details(invoice_names)
    payment_schedule = _get_payment_schedule(invoice_names)
    filtered_rows = []

    for row in rows:
        voucher_type = row.get("voucher_type")
        voucher_no = row.get("voucher_no")

        if voucher_type not in invoice_names:
            filtered_rows.append(row)
            continue

        invoice = invoice_details.get(voucher_type, {}).get(voucher_no)
        if not invoice:
            continue

        outstanding_amount = _get_current_outstanding(row, invoice, payment_schedule)
        if abs(outstanding_amount) <= VALUE_EPSILON:
            continue

        row["outstanding_amount"] = outstanding_amount
        if row.get("payment_term"):
            row["payment_term_outstanding"] = outstanding_amount

        _cap_allocated_amount(row, outstanding_amount)
        filtered_rows.append(row)

    return filtered_rows


def _get_invoice_names(rows):
    invoice_names = {"Sales Invoice": set(), "Purchase Invoice": set()}

    for row in rows:
        voucher_type = row.get("voucher_type")
        if voucher_type in invoice_names and row.get("voucher_no"):
            invoice_names[voucher_type].add(row.get("voucher_no"))

    return {doctype: names for doctype, names in invoice_names.items() if names}


def _get_invoice_details(invoice_names):
    details = {}

    for doctype, names in invoice_names.items():
        details[doctype] = {
            row.name: row
            for row in frappe.get_all(
                doctype,
                filters={"name": ["in", list(names)]},
                fields=[
                    "name",
                    "company",
                    "currency",
                    "conversion_rate",
                    "party_account_currency",
                    "outstanding_amount",
                ],
                limit_page_length=len(names),
            )
        }

    return details


def _get_payment_schedule(invoice_names):
    names = []
    for doctype_names in invoice_names.values():
        names.extend(doctype_names)

    if not names:
        return {}

    schedule = {}
    for row in frappe.get_all(
        "Payment Schedule",
        filters={"parent": ["in", names]},
        fields=["parent", "payment_term", "outstanding"],
        limit_page_length=len(names) * 20,
    ):
        schedule[(row.parent, row.payment_term)] = flt(row.outstanding)

    return schedule


def _get_current_outstanding(row, invoice, payment_schedule):
    payment_term = row.get("payment_term")
    if not payment_term:
        return flt(invoice.outstanding_amount)

    term_outstanding = payment_schedule.get((row.get("voucher_no"), payment_term))
    if term_outstanding is None:
        return flt(invoice.outstanding_amount)

    company_currency = frappe.get_cached_value("Company", invoice.company, "default_currency")
    is_multi_currency_account = (
        invoice.currency != company_currency
        and invoice.party_account_currency != company_currency
    )

    if is_multi_currency_account:
        return flt(term_outstanding)

    return flt(term_outstanding) * flt(invoice.conversion_rate)


def _cap_allocated_amount(row, outstanding_amount):
    allocated_amount = flt(row.get("allocated_amount"))
    if not allocated_amount:
        return

    if outstanding_amount > 0 and allocated_amount > outstanding_amount:
        row["allocated_amount"] = outstanding_amount
    elif outstanding_amount < 0 and allocated_amount < outstanding_amount:
        row["allocated_amount"] = outstanding_amount
