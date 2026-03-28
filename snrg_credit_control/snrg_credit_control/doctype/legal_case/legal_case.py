import frappe
from frappe.model.document import Document
from frappe.utils import flt

from snrg_credit_control.legal_case import (
    ACTIVE_LEGAL_STATUSES,
    get_active_legal_case,
    sync_customer_legal_marker,
)


class LegalCase(Document):
    def validate(self):
        self._set_defaults()
        self._validate_unique_active_case()
        self._recalculate_balance()

    def on_update(self):
        self._sync_customer()

    def on_trash(self):
        self._sync_customer()

    def _set_defaults(self):
        if not self.marked_by:
            self.marked_by = frappe.session.user
        if not self.case_title and self.customer:
            customer_name = frappe.db.get_value("Customer", self.customer, "customer_name") or self.customer
            self.case_title = customer_name if not self.case_type else f"{customer_name} - {self.case_type}"

    def _validate_unique_active_case(self):
        if not self.customer or self.status not in ACTIVE_LEGAL_STATUSES:
            return

        existing = get_active_legal_case(
            self.customer,
            self.company or None,
            exclude_name=self.name,
        )
        if existing:
            frappe.throw(
                f"Customer {self.customer} already has an active Legal Case: {existing}."
            )

    def _recalculate_balance(self):
        self.total_claim_amount = flt(self.total_claim_amount)
        self.amount_recovered = flt(self.amount_recovered)
        self.balance_to_recover = round(self.total_claim_amount - self.amount_recovered, 2)

    def _sync_customer(self):
        if self.customer:
            sync_customer_legal_marker(self.customer)
