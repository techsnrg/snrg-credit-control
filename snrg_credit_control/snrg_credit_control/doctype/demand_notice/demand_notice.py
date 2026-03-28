import frappe
from frappe.model.document import Document
from frappe.utils import add_days, flt, getdate, today

from snrg_credit_control.demand_notice_utils import (
    fetch_invoices_for_notice,
    get_employee_signatory_details,
)


class DemandNotice(Document):

    def validate(self):
        self._set_defaults_on_new()
        self._set_signatory_details()
        self._set_customer_name()
        self._set_currency()
        self._set_prepared_by()
        self._recalculate_totals()

    def before_submit(self):
        self.notice_number = self.name
        self.status = "Issued"

    def on_cancel(self):
        self.status = "Cancelled"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_defaults_on_new(self):
        """Pre-fill interest rate, payment deadline, and signatory on first save."""
        if self.is_new():
            settings = frappe.get_single("Demand Notice Settings")

            if not self.interest_rate:
                self.interest_rate = flt(settings.default_interest_rate or 18)

            if not self.payment_deadline and self.notice_date:
                deadline_days = int(settings.payment_deadline_days or 7)
                self.payment_deadline = add_days(getdate(self.notice_date), deadline_days)

            if not self.legal_consequences_text and settings.default_legal_text:
                self.legal_consequences_text = settings.default_legal_text

    def _set_signatory_details(self):
        if (
            self.authorised_signatory
            and self.signatory_designation
            and self.bar_council_number
            and self.signature_image
        ):
            return

        signatory = get_employee_signatory_details(frappe.session.user)
        if not self.authorised_signatory:
            self.authorised_signatory = signatory["employee_name"]
        if not self.signatory_designation:
            self.signatory_designation = signatory["designation"]
        if not self.bar_council_number:
            self.bar_council_number = signatory["bar_council_number"]
        if not self.signature_image:
            self.signature_image = signatory["signature_image"]

    def _set_customer_name(self):
        if self.customer and not self.customer_name:
            self.customer_name = frappe.db.get_value(
                "Customer", self.customer, "customer_name"
            )

    def _set_currency(self):
        if self.company and not self.currency:
            self.currency = frappe.db.get_value(
                "Company", self.company, "default_currency"
            )

    def _set_prepared_by(self):
        if not self.prepared_by:
            self.prepared_by = frappe.session.user

    def _recalculate_totals(self):
        """Walk child rows and recompute summary totals."""
        total_outstanding = 0.0
        total_interest = 0.0

        for row in self.invoices or []:
            total_outstanding += flt(row.outstanding_amount)
            total_interest += flt(row.interest_amount)

        self.total_outstanding = round(total_outstanding, 2)
        self.total_interest = round(total_interest, 2)
        self.grand_total_due = round(total_outstanding + total_interest, 2)

    # ------------------------------------------------------------------
    # Whitelisted API — called from demand_notice.js
    # ------------------------------------------------------------------

    @frappe.whitelist()
    def get_overdue_invoices(self):
        """
        Fetch overdue invoices for this notice's customer/company and return
        rows ready to populate the child table.

        Called from the 'Fetch Overdue Invoices' button in the form JS.
        """
        if not self.customer:
            frappe.throw("Please select a Customer first.")
        if not self.company:
            frappe.throw("Please select a Company first.")

        rows = fetch_invoices_for_notice(
            self.customer,
            self.company,
            flt(self.interest_rate or 18),
            frappe.db.get_single_value(
                "Demand Notice Settings", "interest_start_after_days"
            ) or 60,
        )

        if not rows:
            frappe.msgprint(
                f"No outstanding invoices found for {self.customer_name or self.customer}.",
                indicator="orange",
                title="No Invoices Found",
            )

        return rows
