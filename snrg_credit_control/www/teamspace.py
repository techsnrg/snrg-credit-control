"""Authenticated short entry point using Frappe's own Desk boot context."""
from urllib.parse import urlencode

import frappe
from frappe.www.desk import get_context as desk_context

no_cache = 1


def get_context(context):
    task = frappe.request.args.get("task")
    if frappe.session.user == "Guest" and task:
        # Desk's default sign-in redirect keeps the path but drops the query.
        target = "/teamspace?" + urlencode({"task": task})
        frappe.redirect("/login?" + urlencode({"redirect-to": target}))
    return desk_context(context)
