import frappe
from frappe.model.document import Document
from frappe.utils import add_days, getdate
from frappe.utils import flt

from snrg_credit_control.legal_case import (
    ACTIVE_LEGAL_STATUSES,
    add_legal_case_activity,
    get_legal_case_settings,
    get_active_legal_case,
    sync_customer_legal_marker,
)


class LegalCase(Document):
    def before_save(self):
        if self.name and not self.is_new():
            previous = frappe.db.get_value(
                "Legal Case",
                self.name,
                ["status", "amount_recovered"],
                as_dict=True,
            ) or {}
            self._previous_status = previous.get("status")
            self._previous_amount_recovered = flt(previous.get("amount_recovered"))
        else:
            self._previous_status = None
            self._previous_amount_recovered = 0

    def validate(self):
        self._set_defaults()
        self._validate_unique_active_case()
        self._recalculate_balance()

    def on_update(self):
        self._sync_customer()
        self._record_activity_updates()

    def on_trash(self):
        self._sync_customer()

    def _set_defaults(self):
        if not self.marked_by:
            self.marked_by = frappe.session.user
        if not self.case_title and self.customer:
            customer_name = frappe.db.get_value("Customer", self.customer, "customer_name") or self.customer
            self.case_title = customer_name if not self.case_type else f"{customer_name} - {self.case_type}"
        settings = get_legal_case_settings()
        if not self.notice_period_days:
            self.notice_period_days = settings.default_notice_period_days or 15
        if not self.payment_wait_days:
            self.payment_wait_days = settings.default_payment_wait_days or 15
        if not self.complaint_filing_days:
            self.complaint_filing_days = settings.default_complaint_filing_days or 30

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
        if self.return_memo_date and self.notice_period_days:
            self.notice_deadline = add_days(
                getdate(self.return_memo_date),
                int(self.notice_period_days),
            )
        if self.notice_sent_date and self.payment_wait_days:
            payment_due = add_days(
                getdate(self.notice_sent_date),
                int(self.payment_wait_days),
            )
            self.payment_due_date = payment_due
            if self.complaint_filing_days:
                self.complaint_filing_deadline = add_days(
                    payment_due,
                    int(self.complaint_filing_days),
                )

    def _sync_customer(self):
        if self.customer:
            sync_customer_legal_marker(self.customer)

    def _record_activity_updates(self):
        previous_status = getattr(self, "_previous_status", None)
        previous_amount = flt(getattr(self, "_previous_amount_recovered", 0))

        if previous_status and previous_status != self.status:
            activity_type = "Case Closed" if self.status == "Closed" else "Status Updated"
            add_legal_case_activity(
                self.name,
                activity_type,
                reference_doctype="Legal Case",
                reference_name=self.name,
                remarks=f"Status changed from {previous_status} to {self.status}.",
            )

        current_amount = flt(self.amount_recovered)
        if current_amount != previous_amount:
            delta = round(current_amount - previous_amount, 2)
            add_legal_case_activity(
                self.name,
                "Recovery Updated",
                reference_doctype="Legal Case",
                reference_name=self.name,
                amount=delta,
                remarks=f"Recovered amount updated from {previous_amount} to {current_amount}.",
            )
