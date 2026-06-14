from __future__ import annotations

import frappe
from frappe.utils import cint, flt, now_datetime

from snrg_credit_control.snrg_credit_control.doctype.production_request.production_request import (
    get_board_data,
    require_request_role,
)
from snrg_credit_control.snrg_credit_control.pending_invoice_planning import (
    get_pending_invoice_planning_rows,
)


def get_context(context):
    context.no_cache = 1
    return context


@frappe.whitelist()
def get_console_data(company=None, search=None, show_completed=1):
    require_request_role()

    company = (company or frappe.defaults.get_user_default("Company") or "").strip()
    search_term = (search or "").strip().lower()

    pending_filters = frappe._dict()
    if company:
        pending_filters.company = company

    pending_rows = get_pending_invoice_planning_rows(filters=pending_filters, pending_only=True)
    if search_term:
        pending_rows = [row for row in pending_rows if _matches_pending_search(row, search_term)]

    board_data = get_board_data(company=company, search=search, show_completed=show_completed)
    grouped_requests = board_data.get("groups") or {}
    all_request_rows = [
        row
        for status in ("Open", "In Progress", "Completed")
        for row in (grouped_requests.get(status) or [])
    ]

    return {
        "generated_on": str(now_datetime()),
        "filters": {
            "company": company,
            "search": search or "",
            "show_completed": cint(show_completed),
        },
        "meta": {
            "companies": _get_company_options(),
            "assignable_users": _get_assignable_user_options(),
        },
        "summary": {
            "pending_line_count": len(pending_rows),
            "pending_qty": sum(flt(row.get("total_uninvoiced_qty")) for row in pending_rows),
            "pending_value": sum(flt(row.get("total_uninvoiced_value")) for row in pending_rows),
            "requested_open_qty": sum(flt(row.get("requested_qty")) for row in grouped_requests.get("Open", [])),
            "requested_in_progress_qty": sum(
                flt(row.get("requested_qty")) for row in grouped_requests.get("In Progress", [])
            ),
            "open_request_count": len(grouped_requests.get("Open", [])),
            "in_progress_request_count": len(grouped_requests.get("In Progress", [])),
            "completed_request_count": len(grouped_requests.get("Completed", [])),
            "urgent_request_count": sum(1 for row in all_request_rows if _is_request_urgent(row)),
        },
        "pending_rows": pending_rows,
        "groups": {
            "Open": grouped_requests.get("Open", []),
            "In Progress": grouped_requests.get("In Progress", []),
            "Completed": grouped_requests.get("Completed", []),
        },
    }


def _matches_pending_search(row, search_term):
    haystack = " ".join(
        [
            str(row.get("quotation") or "").lower(),
            str(row.get("customer") or "").lower(),
            str(row.get("customer_name") or "").lower(),
            str(row.get("item_code") or "").lower(),
            str(row.get("item_name") or "").lower(),
            str(row.get("status_summary") or "").lower(),
            str(row.get("planning_stage_summary") or "").lower(),
            str(row.get("production_request_name") or "").lower(),
            str(row.get("production_request_status") or "").lower(),
            str(row.get("production_assigned_to") or "").lower(),
            str(row.get("production_assigned_to_name") or "").lower(),
            str(row.get("production_required_by_date") or "").lower(),
        ]
    )
    return search_term in haystack


def _get_company_options():
    return [row.name for row in frappe.get_all("Company", fields=["name"], order_by="name asc", limit_page_length=500)]


def _get_assignable_user_options():
    rows = frappe.get_all(
        "User",
        filters={"enabled": 1, "user_type": "System User"},
        fields=["name", "full_name"],
        order_by="full_name asc, name asc",
        limit_page_length=500,
    )
    return [
        {
            "value": row.name,
            "label": row.full_name or row.name,
        }
        for row in rows
        if row.name not in {"Guest"}
    ]


def _is_request_urgent(row):
    required_by_date = row.get("required_by_date")
    if not required_by_date:
        return False

    try:
        due_date = frappe.utils.getdate(required_by_date)
        today = frappe.utils.getdate(now_datetime())
    except Exception:
        return False

    return (due_date - today).days <= 2

