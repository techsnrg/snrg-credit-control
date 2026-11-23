"""Associate the existing Rohit moulding guide with its customer master."""
import frappe


def execute():
    guide = "abgkke5n5v"
    title = frappe.db.get_value("Teamspace Guide", guide, "title")
    if (
        title == "KB-00001 Rohit Industries Moulding Production and Invoicing"
        and not frappe.db.get_value("Teamspace Guide", guide, "customer")
        and frappe.db.exists("Customer", "CUST-10180")
    ):
        frappe.db.set_value("Teamspace Guide", guide, "customer", "CUST-10180")
