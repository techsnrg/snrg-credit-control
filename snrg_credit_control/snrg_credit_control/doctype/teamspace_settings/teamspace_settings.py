import frappe
from frappe import _
from frappe.model.document import Document


class TeamspaceSettings(Document):
    def validate(self):
        from snrg_credit_control.customer_workspace.api import guard, manager, internal
        guard()
        if not manager():
            frappe.throw(_("Manager access required."), frappe.PermissionError)
        for row in self.access:
            if row.feature not in ("AR", "AP", "Transactions") or not internal(row.user):
                frappe.throw(_("Choose an active internal team member and a valid feature."))
