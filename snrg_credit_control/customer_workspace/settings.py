"""Optional team member allowlists, additional to native ERPNext permissions."""
import frappe
from frappe import _
from frappe.utils import cint
from snrg_credit_control.customer_workspace.api import guard, manager, internal

FEATURES = {"AR": "restrict_ar", "AP": "restrict_ap", "Transactions": "restrict_transactions"}


def allowed(feature, user=None):
    if feature not in FEATURES:
        return False
    if not frappe.db.exists("DocType", "Teamspace Settings"):
        return True
    settings = frappe.get_cached_doc("Teamspace Settings")
    return not settings.get(FEATURES[feature]) or any(row.feature == feature and row.user == (user or frappe.session.user) for row in settings.access)


@frappe.whitelist()
def visibility_settings():
    guard()
    if not manager():
        frappe.throw(_("Manager access required."), frappe.PermissionError)
    settings = frappe.get_single("Teamspace Settings")
    return {**{field: cint(settings.get(field)) for field in FEATURES.values()}, "access": [{"feature": row.feature, "user": row.user} for row in settings.access]}


@frappe.whitelist(methods=["POST"])
def save_visibility_settings(payload):
    guard()
    if not manager():
        frappe.throw(_("Manager access required."), frappe.PermissionError)
    data = frappe.parse_json(payload)
    settings = frappe.get_single("Teamspace Settings")
    for field in FEATURES.values():
        settings.set(field, cint(data.get(field)))
    access = []
    seen = set()
    for row in data.get("access") or []:
        key = (row.get("feature"), row.get("user"))
        if key in seen:
            continue
        if key[0] not in FEATURES or not internal(key[1]):
            frappe.throw(_("Choose an active internal team member and a valid feature."))
        seen.add(key)
        access.append({"feature": key[0], "user": key[1]})
    settings.set("access", access)
    settings.save(ignore_permissions=True)  # manager guard above; controller validates Desk writes too
    frappe.clear_document_cache("Teamspace Settings", "Teamspace Settings")
    return visibility_settings()
