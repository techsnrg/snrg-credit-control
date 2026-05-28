import frappe
from frappe.utils import flt

from erpnext.accounts.doctype.journal_entry.journal_entry import JournalEntry


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
