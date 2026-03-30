import frappe
from frappe.model.document import Document

from snrg_credit_control.legal_case import get_active_legal_case, get_default_company


ALLOWED_COMMUNICATION_TYPES = {"Call", "Visit", "Email", "WhatsApp", "Notice"}


class CustomerCommunication(Document):
    def validate(self):
        if not self.performed_by:
            self.performed_by = frappe.session.user

        if self.communication_type and self.communication_type not in ALLOWED_COMMUNICATION_TYPES:
            frappe.throw("Unsupported communication type.")

        if self.customer and not self.company:
            self.company = get_default_company()

        if self.customer and not self.legal_case:
            self.legal_case = get_active_legal_case(self.customer, self.company or None) or ""

