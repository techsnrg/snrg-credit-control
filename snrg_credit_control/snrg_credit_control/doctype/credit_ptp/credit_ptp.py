import frappe
from frappe.model.document import Document

from snrg_credit_control.ptp import build_ptp_reference_label, supersede_previous_ptps, sync_credit_ptp


class CreditPTP(Document):
    def validate(self):
        if self.ptp_by and not self.ptp_by_name:
            self.ptp_by_name = frappe.db.get_value("Employee", self.ptp_by, "employee_name")
        if self.sales_order and not self.customer:
            so = frappe.db.get_value(
                "Sales Order",
                self.sales_order,
                ["customer", "customer_name", "company", "currency"],
                as_dict=True,
            ) or {}
            self.customer = self.customer or so.get("customer")
            self.customer_name = self.customer_name or so.get("customer_name")
            self.company = self.company or so.get("company")
            self.currency = self.currency or so.get("currency")

        sync_credit_ptp(self)
        self.reference_label = build_ptp_reference_label(self)

    def after_insert(self):
        supersede_previous_ptps(self)

    def on_update(self):
        supersede_previous_ptps(self)

