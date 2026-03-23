"""
snrg_credit_control — install / migrate helpers.

Runs after `bench install-app` and after every `bench migrate`.
Idempotent: safe to run multiple times.
"""

import frappe


# ---------------------------------------------------------------------------
# Public entry-points (referenced in hooks.py)
# ---------------------------------------------------------------------------

def after_install():
    _ensure_module()
    _ensure_role()
    _ensure_customer_fields()
    _ensure_so_fields()
    _ensure_quotation_fields()
    _ensure_report()
    frappe.db.commit()


def after_migrate():
    _ensure_module()
    _ensure_role()
    _ensure_customer_fields()
    _ensure_so_fields()
    _ensure_quotation_fields()
    _ensure_report()
    frappe.db.commit()


# ---------------------------------------------------------------------------
# Module Def
# ---------------------------------------------------------------------------

def _ensure_module():
    if frappe.db.exists("Module Def", "Snrg Credit Control"):
        return
    frappe.get_doc(
        {
            "doctype": "Module Def",
            "module_name": "Snrg Credit Control",
            "app_name": "snrg_credit_control",
        }
    ).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Role
# ---------------------------------------------------------------------------

def _ensure_role():
    if frappe.db.exists("Role", "Credit Approver"):
        return
    frappe.get_doc(
        {
            "doctype": "Role",
            "role_name": "Credit Approver",
            "desk_access": 1,
        }
    ).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Custom Fields — Customer master
# ---------------------------------------------------------------------------

_CUSTOMER_FIELDS = [
    {
        "fieldname": "custom_credit_lock_days",
        "fieldtype": "Int",
        "label": "Credit Lock Days",
        "description": "Invoices older than this many days with outstanding balance trigger a Credit Hold. Leave blank to use the system default (75 days).",
        "default": "75",
        "insert_after": "credit_limits",  # placed after the credit limits table
    },
]


def _ensure_customer_fields():
    for fdef in _CUSTOMER_FIELDS:
        _ensure_custom_field("Customer", fdef)


# ---------------------------------------------------------------------------
# Custom Fields — Sales Order
# ---------------------------------------------------------------------------

_SO_FIELDS = [
    # ── Section: Credit Check ───────────────────────────────────────────────
    {
        "fieldname": "custom_snrg_credit_section",
        "fieldtype": "Section Break",
        "label": "Credit Check",
        "insert_after": "rounded_total",
        "collapsible": 1,
    },
    {
        "fieldname": "custom_snrg_credit_check_status",
        "fieldtype": "Select",
        "label": "Credit Check Status",
        "options": "\nNot Run\nCredit OK\nCredit Hold",
        "default": "Not Run",
        "read_only": 1,
        "in_list_view": 1,
        "in_standard_filter": 1,
        "insert_after": "custom_snrg_credit_section",
    },
    {
        "fieldname": "custom_snrg_credit_check_reason_code",
        "fieldtype": "Data",
        "label": "Reason Code",
        "read_only": 1,
        "in_standard_filter": 1,
        "insert_after": "custom_snrg_credit_check_status",
    },
    {
        "fieldname": "custom_snrg_col_break_1",
        "fieldtype": "Column Break",
        "insert_after": "custom_snrg_credit_check_reason_code",
    },
    {
        "fieldname": "custom_snrg_overdue_count_terms",
        "fieldtype": "Int",
        "label": "Overdue Invoice Count",
        "read_only": 1,
        "insert_after": "custom_snrg_col_break_1",
    },
    {
        "fieldname": "custom_snrg_overdue_amount_terms",
        "fieldtype": "Currency",
        "label": "Overdue Amount",
        "read_only": 1,
        "insert_after": "custom_snrg_overdue_count_terms",
    },
    {
        "fieldname": "custom_snrg_exposure_at_check",
        "fieldtype": "Currency",
        "label": "Total AR Exposure",
        "read_only": 1,
        "insert_after": "custom_snrg_overdue_amount_terms",
    },
    {
        "fieldname": "custom_snrg_credit_limit_at_check",
        "fieldtype": "Currency",
        "label": "Credit Limit Snapshot",
        "read_only": 1,
        "insert_after": "custom_snrg_exposure_at_check",
    },
    {
        "fieldname": "custom_snrg_credit_check_details",
        "fieldtype": "Text",
        "label": "Overdue Invoice Details",
        "read_only": 1,
        "insert_after": "custom_snrg_credit_limit_at_check",
    },

    # ── Section: Credit Approval Request ────────────────────────────────────
    {
        "fieldname": "custom_snrg_request_section",
        "fieldtype": "Section Break",
        "label": "Credit Approval Request",
        "insert_after": "custom_snrg_credit_check_details",
        "collapsible": 1,
    },
    {
        "fieldname": "custom_snrg_request_time",
        "fieldtype": "Datetime",
        "label": "Request Time",
        "read_only": 1,
        "insert_after": "custom_snrg_request_section",
    },
    {
        "fieldname": "custom_snrg_request_amount",
        "fieldtype": "Currency",
        "label": "Requested Amount",
        "read_only": 1,
        "insert_after": "custom_snrg_request_time",
    },
    {
        "fieldname": "custom_snrg_requested_to_employee",
        "fieldtype": "Link",
        "label": "Requested To",
        "options": "Employee",
        "read_only": 1,
        "insert_after": "custom_snrg_request_amount",
    },
    {
        "fieldname": "custom_snrg_ptp_entries",
        "fieldtype": "Table",
        "label": "PTP Entries",
        "options": "Credit PTP Entry",
        "insert_after": "custom_snrg_requested_to_employee",
    },
    {
        "fieldname": "custom_snrg_ptp_payment_links",
        "fieldtype": "Table",
        "label": "PTP Payment Links",
        "options": "Credit PTP Payment Link",
        "insert_after": "custom_snrg_ptp_entries",
    },

    # ── Section: Credit Override ─────────────────────────────────────────────
    {
        "fieldname": "custom_snrg_override_section",
        "fieldtype": "Section Break",
        "label": "Credit Override",
        "insert_after": "custom_snrg_ptp_payment_links",
        "collapsible": 1,
    },
    {
        "fieldname": "custom_snrg_override_cap_amount",
        "fieldtype": "Currency",
        "label": "Approved Cap Amount",
        "insert_after": "custom_snrg_override_section",
    },
    {
        "fieldname": "custom_snrg_override_valid_till",
        "fieldtype": "Date",
        "label": "Approval Valid Till",
        "insert_after": "custom_snrg_override_cap_amount",
    },
    {
        "fieldname": "custom_snrg_col_break_2",
        "fieldtype": "Column Break",
        "insert_after": "custom_snrg_override_valid_till",
    },
    {
        "fieldname": "custom_snrg_approver",
        "fieldtype": "Link",
        "label": "Approved By",
        "options": "User",
        "read_only": 1,
        "insert_after": "custom_snrg_col_break_2",
    },
    {
        "fieldname": "custom_snrg_approval_time",
        "fieldtype": "Datetime",
        "label": "Approval Time",
        "read_only": 1,
        "insert_after": "custom_snrg_approver",
    },
    {
        "fieldname": "custom_credit_approval_status",
        "fieldtype": "Select",
        "label": "Approval Status",
        "options": "\nPending\nApproved\nRejected",
        "insert_after": "custom_snrg_approval_time",
    },
]


def _ensure_so_fields():
    for fdef in _SO_FIELDS:
        _ensure_custom_field("Sales Order", fdef)


_QUOTATION_FIELDS = [
    {
        "fieldname": "custom_snrg_credit_check_status",
        "fieldtype": "Select",
        "label": "Credit Check Status",
        "options": "\nNot Run\nCredit OK\nCredit Hold",
        "default": "Not Run",
        "read_only": 1,
        "hidden": 0,
        "in_list_view": 1,
        "in_standard_filter": 1,
        "insert_after": "rounded_total",
    },
    {
        "fieldname": "custom_snrg_credit_check_reason_code",
        "fieldtype": "Data",
        "label": "Reason Code",
        "read_only": 1,
        "hidden": 0,
        "in_standard_filter": 1,
        "insert_after": "custom_snrg_credit_check_status",
    },
    {
        "fieldname": "custom_snrg_overdue_count_terms",
        "fieldtype": "Int",
        "label": "Overdue Invoice Count",
        "read_only": 1,
        "hidden": 1,
        "insert_after": "custom_snrg_credit_check_reason_code",
    },
    {
        "fieldname": "custom_snrg_overdue_amount_terms",
        "fieldtype": "Currency",
        "label": "Overdue Amount",
        "read_only": 1,
        "hidden": 1,
        "insert_after": "custom_snrg_overdue_count_terms",
    },
    {
        "fieldname": "custom_snrg_exposure_at_check",
        "fieldtype": "Currency",
        "label": "Total AR Exposure",
        "read_only": 1,
        "hidden": 1,
        "insert_after": "custom_snrg_overdue_amount_terms",
    },
    {
        "fieldname": "custom_snrg_credit_limit_at_check",
        "fieldtype": "Currency",
        "label": "Credit Limit Snapshot",
        "read_only": 1,
        "hidden": 1,
        "insert_after": "custom_snrg_exposure_at_check",
    },
    {
        "fieldname": "custom_snrg_credit_check_details",
        "fieldtype": "Small Text",
        "label": "Credit Check Details",
        "read_only": 1,
        "hidden": 1,
        "insert_after": "custom_snrg_credit_limit_at_check",
    },
]


def _ensure_quotation_fields():
    for fdef in _QUOTATION_FIELDS:
        _ensure_custom_field("Quotation", fdef)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _ensure_report():
    name = "Credit Control Report"
    if frappe.db.exists("Report", name):
        frappe.db.set_value("Report", name, "module", "Snrg Credit Control")
        frappe.db.set_value("Report", name, "disabled", 0)
        return

    frappe.get_doc(
        {
            "doctype": "Report",
            "report_name": name,
            "report_type": "Script Report",
            "ref_doctype": "Sales Order",
            "module": "Snrg Credit Control",
            "is_standard": "Yes",
            "disabled": 0,
            "roles": [
                {"role": "Credit Approver"},
                {"role": "Accounts Manager"},
                {"role": "System Manager"},
                {"role": "Sales Manager"},
            ],
        }
    ).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _ensure_custom_field(doctype, field_def):
    fieldname = field_def["fieldname"]
    custom_field_name = f"{doctype}-{fieldname}"
    if frappe.db.exists("Custom Field", custom_field_name):
        for key, value in field_def.items():
            frappe.db.set_value("Custom Field", custom_field_name, key, value, update_modified=False)
        return
    doc = {"doctype": "Custom Field", "dt": doctype}
    doc.update(field_def)
    frappe.get_doc(doc).insert(ignore_permissions=True)
