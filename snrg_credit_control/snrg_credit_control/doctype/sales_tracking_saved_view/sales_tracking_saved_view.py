import frappe
from frappe.model.document import Document


class SalesTrackingSavedView(Document):
    def validate(self):
        self.page_name = self.page_name or "sales-tracking"
        self.is_shared = 1
        self.view_name = (self.view_name or "").strip()
        if not self.view_name:
            frappe.throw("View Name is required.")

