"""Additional native launcher tiles for pages shipped by this app."""
import frappe


def boot_session(bootinfo):
    # Frappe's app hook consumes only the first entry. Add this second page
    # through the public boot hook, without changing the framework launcher.
    if frappe.session.user == "Guest" or not frappe.db.exists("Page", "sales-tracking"):
        return
    if not frappe.get_doc("Page", "sales-tracking").is_permitted():
        return
    apps = bootinfo.setdefault("app_data", [])
    if any(app.get("app_name") == "snrg_sales_tracking" for app in apps):
        return
    apps.append({
        "app_name": "snrg_sales_tracking",
        "app_title": "Sales Tracking",
        "app_route": "/desk/sales-tracking",
        "app_logo_url": "/assets/snrg_credit_control/images/sales-tracking.svg",
        "on_apps_screen": True,
        "sequence_id": 7,
        "desk_route": "",
        "dock": [],
    })
