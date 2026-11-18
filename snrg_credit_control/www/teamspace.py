"""Authenticated short entry point using Frappe's own Desk boot context."""
from frappe.www.desk import get_context as desk_context

no_cache = 1


def get_context(context):
    return desk_context(context)
