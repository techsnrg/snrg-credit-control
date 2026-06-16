import frappe
from frappe import _
from frappe.utils import flt

import erpnext
from erpnext.accounts.doctype.journal_entry.journal_entry import (
    JournalEntry,
    get_outstanding as erpnext_get_outstanding,
)

VALUE_EPSILON = 0.01


class CustomJournalEntry(JournalEntry):
    def check_credit_limit(self):
        customers = self._get_customers_with_increased_receivable()

        if not customers:
            return

        from erpnext.selling.doctype.customer.customer import check_credit_limit

        customer_details = frappe._dict(
            frappe.db.get_all(
                "Customer Credit Limit",
                filters={
                    "parent": ["in", customers],
                    "parenttype": ["=", "Customer"],
                    "company": ["=", self.company],
                },
                fields=["parent", "bypass_credit_limit_check"],
                as_list=True,
            )
        )

        for customer in customers:
            ignore_outstanding_sales_order = bool(customer_details.get(customer))
            check_credit_limit(customer, self.company, ignore_outstanding_sales_order)

    def _get_customers_with_increased_receivable(self):
        receivable_by_customer = {}

        for row in self.get("accounts"):
            if row.party_type != "Customer" or not row.party:
                continue

            receivable_by_customer.setdefault(row.party, 0)
            receivable_by_customer[row.party] += flt(row.debit) - flt(row.credit)

        return [
            customer
            for customer, net_receivable in receivable_by_customer.items()
            if flt(net_receivable, self.precision("total_debit")) > 0
        ]


@frappe.whitelist()
def get_outstanding(args):
    if isinstance(args, str):
        args = frappe.parse_json(args)

    if args.get("doctype") not in ("Sales Invoice", "Purchase Invoice"):
        return erpnext_get_outstanding(args)

    if not frappe.has_permission("Account"):
        frappe.throw(_("No Permission"), frappe.PermissionError)

    party_type = "Customer" if args.get("doctype") == "Sales Invoice" else "Supplier"
    party_field = party_type.lower()
    invoice = frappe.db.get_value(
        args.get("doctype"),
        args.get("docname"),
        ["outstanding_amount", "conversion_rate", party_field, "due_date"],
        as_dict=True,
    )

    if not invoice:
        frappe.throw(_("{0} {1} was not found.").format(args.get("doctype"), args.get("docname")))

    outstanding_amount = flt(invoice.outstanding_amount)
    if abs(outstanding_amount) <= VALUE_EPSILON:
        frappe.throw(
            _("{0} {1} is already fully adjusted.").format(args.get("doctype"), args.get("docname"))
        )

    company_currency = erpnext.get_company_currency(args.get("company"))
    exchange_rate = invoice.conversion_rate if args.get("account_currency") != company_currency else 1

    if args.get("doctype") == "Sales Invoice":
        amount_field = "credit_in_account_currency" if outstanding_amount > 0 else "debit_in_account_currency"
    else:
        amount_field = "debit_in_account_currency" if outstanding_amount > 0 else "credit_in_account_currency"

    return {
        amount_field: abs(outstanding_amount),
        "exchange_rate": exchange_rate,
        "party_type": party_type,
        "party": invoice.get(party_field),
        "reference_due_date": invoice.get("due_date"),
    }
