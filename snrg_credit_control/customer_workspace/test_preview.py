"""Idempotent, explicitly labelled preview fixtures. Never runs on a live site."""
import frappe
from frappe.utils import today, add_days
from snrg_credit_control.customer_workspace import api


def seed():
    if not ("staging" in frappe.local.site or "test" in frappe.local.site):
        raise RuntimeError("Preview fixtures are restricted to test/staging sites")
    frappe.set_user("Administrator")
    company = frappe.db.get_value("Company", {"name": ["like", "SNRG%"]}, "name")
    employees = []
    for person in ("Asha", "Rohan"):
        email = "teamspace." + person.lower() + "@example.invalid"
        if not frappe.db.exists("User", email):
            frappe.get_doc({"doctype": "User", "email": email, "first_name": person, "last_name": "(Preview)", "enabled": 1, "user_type": "System User", "send_welcome_email": 0, "roles": [{"role": "Employee"}]}).insert(ignore_permissions=True)
        employee = frappe.db.get_value("Employee", {"user_id": email}, "name")
        if not employee:
            doc = frappe.get_doc({"doctype": "Employee", "first_name": person, "last_name": "(Preview)", "status": "Active", "user_id": email, "company": company, "date_of_joining": today()})
            doc.flags.ignore_mandatory = True
            employee = doc.insert(ignore_permissions=True).name
        employees.append((email, employee))
    supplier = frappe.db.get_value("Supplier", {"supplier_name": "Teamspace Preview Supplies"}, "name")
    if not supplier:
        doc = frappe.get_doc({"doctype": "Supplier", "supplier_name": "Teamspace Preview Supplies", "supplier_type": "Company"})
        doc.flags.ignore_mandatory = True
        supplier = doc.insert(ignore_permissions=True).name
    if not frappe.db.exists(api.INTERACTION, {"supplier": supplier, "summary": "Preview: supplier confirmed dispatch. Please coordinate receipt."}):
        api.log_interaction({"supplier": supplier, "summary": "Preview: supplier confirmed dispatch. Please coordinate receipt.", "summary_html": "<p>Supplier confirmed <strong>dispatch for tomorrow</strong>.</p><ul><li>Confirm vehicle details</li><li>Coordinate receiving at the warehouse</li></ul>", "mentions": [employees[0][1]], "actions": [{"subject": "Preview: confirm supplier delivery", "assigned_to": employees[0][0], "due_date": add_days(today(), 2), "due_time": "11:30", "action_type": "Delivery"}]})
    customer = frappe.db.get_value("Customer", {"customer_name": ["like", "Returns QA%"]}, "name")
    if customer and not frappe.db.exists(api.INTERACTION, {"customer": customer, "summary": "Preview: discussed outstanding invoices; payment confirmation pending."}):
        api.log_interaction({"customer": customer, "summary": "Preview: discussed outstanding invoices; payment confirmation pending.", "summary_html": "<p>Discussed the <strong>outstanding invoices</strong>.</p><p>Customer will confirm the payment date. Awaiting their update.</p>", "actions": [{"subject": "Preview: confirm customer payment date", "assigned_to": "Administrator", "due_date": add_days(today(), 1), "due_time": "10:30", "action_type": "Collection"}]})
    frappe.db.commit()
    return {"preview_only": True, "supplier": frappe.get_doc("Supplier", supplier).name, "customer": frappe.get_doc("Customer", customer).name if customer else None, "employees": [frappe.get_doc("Employee", row[1]).name for row in employees]}
