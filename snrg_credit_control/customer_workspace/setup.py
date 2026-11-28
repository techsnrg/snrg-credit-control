import json
import frappe


def setup():
    from snrg_credit_control.customer_workspace.notifications import ensure_keys
    from snrg_credit_control.customer_workspace.leads import install_fields
    from snrg_credit_control.customer_workspace.party_rates import install_fields as install_rate_fields

    ensure_keys()
    install_fields()
    install_rate_fields()
    if not frappe.db.exists("Role", "Customer Workspace Manager"):
        frappe.get_doc({"doctype": "Role", "role_name": "Customer Workspace Manager", "desk_access": 1}).insert(ignore_permissions=True)
    if frappe.db.exists("Workspace", "Customer Relationships") and not frappe.db.exists("Workspace", "Teamspace"):
        frappe.rename_doc("Workspace", "Customer Relationships", "Teamspace", force=True)
    if not frappe.db.exists("Workspace", "Teamspace"):
        frappe.get_doc({"doctype": "Workspace", "name": "Teamspace", "label": "Teamspace", "title": "Teamspace", "module": "Snrg Credit Control", "public": 1, "type": "Workspace", "icon": "users", "roles": [{"role": r} for r in ("Employee", "Customer Workspace Manager", "System Manager")], "content": json.dumps([{"id": "cw-header", "type": "header", "data": {"text": "Teamspace", "col": 12}}, {"id": "cw-shortcut", "type": "shortcut", "data": {"shortcut_name": "Open Teamspace", "col": 4}}]), "shortcuts": [{"label": "Open Teamspace", "type": "Page", "link_to": "customer-workspace"}]}).insert(ignore_permissions=True)
    else:
        workspace = frappe.get_doc("Workspace", "Teamspace")
        workspace.label = workspace.title = "Teamspace"
        workspace.content = (workspace.content or "[]").replace("Customer Workspace", "Teamspace").replace("My Day & Customer Activity", "Open Teamspace")
        for shortcut in workspace.shortcuts:
            if shortcut.link_to == "customer-workspace":
                shortcut.label = "Open Teamspace"
        workspace.save(ignore_permissions=True)
