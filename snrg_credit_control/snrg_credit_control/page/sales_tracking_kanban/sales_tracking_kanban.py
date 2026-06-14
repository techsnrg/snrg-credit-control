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
    allowed_args = {
        "company",
        "from_date",
        "to_date",
        "order_month",
        "territory",
        "customer",
        "search",
        "credit_status",
        "delivery_status",
        "limit",
    }
    return get_tracker_data(**{key: value for key, value in kwargs.items() if key in allowed_args})
