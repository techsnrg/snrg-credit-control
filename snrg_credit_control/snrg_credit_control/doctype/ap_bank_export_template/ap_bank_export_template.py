import frappe
from frappe import _
from frappe.model.document import Document


class APBankExportTemplate(Document):
    def validate(self):
        if self.exporter_key == "ICICI_NPAB" and self.output_format != "XLS":
            frappe.throw(_("ICICI NPAB templates must use XLS output format."))
