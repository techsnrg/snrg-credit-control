import frappe
from frappe import _
from frappe.model.document import Document

from snrg_credit_control import payables


class APPaymentBatch(Document):
    def validate(self):
        payables.validate_payment_batch(self)

    @frappe.whitelist()
    def generate_export(self):
        if not self.has_permission("write"):
            frappe.throw(_("Not permitted."), frappe.PermissionError)

        file_doc = payables.generate_batch_export_file(self)
        self.generated_export_file = file_doc.file_url
        self.status = "Exported"
        self.save(ignore_permissions=True)
        return {"file_url": file_doc.file_url, "file_name": file_doc.file_name}

    @frappe.whitelist()
    def create_draft_payment_entries(self):
        if not self.has_permission("write"):
            frappe.throw(_("Not permitted."), frappe.PermissionError)

        created, skipped = payables.create_payment_entries_for_batch(self)
        return {
            "created": created,
            "skipped_rows": skipped,
            "message": _("Created {0} draft Payment Entry records.").format(len(created)),
        }

    @frappe.whitelist()
    def send_export_by_email(self):
        if not self.has_permission("write"):
            frappe.throw(_("Not permitted."), frappe.PermissionError)

        payables.send_export_email(self)
        self.status = "Emailed"
        self.save(ignore_permissions=True)
        return {"message": _("Export email sent successfully.")}
