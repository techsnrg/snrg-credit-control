import json
import frappe


def setup():
    if not frappe.db.exists("Role", "Customer Workspace Manager"):
        frappe.get_doc({"doctype": "Role", "role_name": "Customer Workspace Manager", "desk_access": 1}).insert(ignore_permissions=True)
    if not frappe.db.exists("Workspace", "Customer Relationships"):
        frappe.get_doc({"doctype": "Workspace", "name": "Customer Relationships", "label": "Customer Relationships", "title": "Customer Relationships", "module": "Snrg Credit Control", "public": 1, "type": "Workspace", "icon": "users", "roles": [{"role": r} for r in ("Employee", "Customer Workspace Manager", "System Manager")], "content": json.dumps([{"id": "cw-header", "type": "header", "data": {"text": "Customer Workspace", "col": 12}}, {"id": "cw-shortcut", "type": "shortcut", "data": {"shortcut_name": "My Day & Customer Activity", "col": 4}}]), "shortcuts": [{"label": "My Day & Customer Activity", "type": "Page", "link_to": "customer-workspace"}]}).insert(ignore_permissions=True)
