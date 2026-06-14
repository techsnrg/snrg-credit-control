from __future__ import annotations

import frappe

from snrg_credit_control.snrg_credit_control.page.sales_tracking.sales_tracking import (
    get_tracker_data,
)


def get_context(context):
    context.no_cache = 1
    return context


@frappe.whitelist()
def get_kanban_data(**kwargs):
    return get_tracker_data(**kwargs)
