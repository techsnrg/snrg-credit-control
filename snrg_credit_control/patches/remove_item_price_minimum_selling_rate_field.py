import frappe


def execute():
    custom_field = "Item Price-minimum_selling_rate"
    if not frappe.db.exists("Custom Field", custom_field):
        return

    frappe.delete_doc("Custom Field", custom_field, ignore_permissions=True, force=True)
    frappe.clear_cache(doctype="Item Price")
