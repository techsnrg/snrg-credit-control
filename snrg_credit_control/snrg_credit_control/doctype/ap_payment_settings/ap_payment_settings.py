import frappe
from frappe import _
from frappe.model.document import Document


class APPaymentSettings(Document):
    def validate(self):
        if self.approver_user and "Managing Director" not in frappe.get_roles(self.approver_user):
            frappe.throw(_("Approver User must have the Managing Director role."))
        if not self.debit_narration_prefix:
            self.debit_narration_prefix = "BULK"
