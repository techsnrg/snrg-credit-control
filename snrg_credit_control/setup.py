"""
snrg_credit_control — install / migrate helpers.

Runs after `bench install-app` and after every `bench migrate`.
Idempotent: safe to run multiple times.
"""

import json

import frappe


# ---------------------------------------------------------------------------
# Public entry-points (referenced in hooks.py)
# ---------------------------------------------------------------------------

def after_install():
    _ensure_module()
    _ensure_role()
    _ensure_customer_fields()
    _ensure_journal_entry_fields()
    _ensure_so_fields()
    _ensure_quotation_fields()
    _ensure_report()
    _ensure_employee_signatory_fields()
    _ensure_demand_notice_settings()
    _ensure_credit_control_workspace()
    _ensure_demand_notice_default_print_format()
    frappe.db.commit()


def after_migrate():
    _ensure_module()
    _ensure_role()
    _ensure_customer_fields()
    _ensure_journal_entry_fields()
    _ensure_so_fields()
    _ensure_quotation_fields()
    _ensure_report()
    _ensure_employee_signatory_fields()
    _ensure_demand_notice_settings()
    _ensure_credit_control_workspace()
    _ensure_demand_notice_default_print_format()
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
    for role_name in ("Credit Approver", "Legal"):
        if frappe.db.exists("Role", role_name):
            continue
        frappe.get_doc(
            {
                "doctype": "Role",
                "role_name": role_name,
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
# Custom Fields — Journal Entry
# ---------------------------------------------------------------------------

_JOURNAL_ENTRY_FIELDS = [
    {
        "fieldname": "custom_cheque_bounce_section",
        "fieldtype": "Section Break",
        "label": "Cheque Bounce Tracking",
        "insert_after": "user_remark",
        "collapsible": 1,
        "allow_on_submit": 1,
    },
    {
        "fieldname": "custom_is_cheque_bounce",
        "fieldtype": "Check",
        "label": "Is Cheque Bounce",
        "insert_after": "custom_cheque_bounce_section",
        "allow_on_submit": 1,
    },
    {
        "fieldname": "custom_cheque_bounce_case",
        "fieldtype": "Link",
        "label": "Cheque Bounce Case",
        "options": "Cheque Bounce Case",
        "insert_after": "custom_is_cheque_bounce",
        "read_only": 1,
        "allow_on_submit": 1,
    },
    {
        "fieldname": "custom_cheque_bounce_status",
        "fieldtype": "Data",
        "label": "Cheque Bounce Status",
        "insert_after": "custom_cheque_bounce_case",
        "read_only": 1,
        "allow_on_submit": 1,
    },
]


def _ensure_journal_entry_fields():
    for fdef in _JOURNAL_ENTRY_FIELDS:
        _ensure_custom_field("Journal Entry", fdef)


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
    # ── Section: Credit Override ─────────────────────────────────────────────
    {
        "fieldname": "custom_snrg_override_section",
        "fieldtype": "Section Break",
        "label": "Credit Override",
        "insert_after": "custom_snrg_requested_to_employee",
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


# ---------------------------------------------------------------------------
# Employee — Bar Council Number custom field
# ---------------------------------------------------------------------------

def _ensure_employee_signatory_fields():
    _ensure_custom_field("Employee", {
        "fieldname": "custom_bar_council_number",
        "fieldtype": "Data",
        "label": "Bar Council Number",
        "insert_after": "designation",
    })
    _ensure_custom_field("Employee", {
        "fieldname": "custom_signature_image",
        "fieldtype": "Attach Image",
        "label": "Signature Image",
        "insert_after": "custom_bar_council_number",
    })


# ---------------------------------------------------------------------------
# Demand Notice Settings — default singleton record
# ---------------------------------------------------------------------------

_DEFAULT_LEGAL_TEXT = (
    "TAKE NOTICE that the sum stated above is due and payable forthwith. "
    "Should the outstanding amount not be received in full by the payment deadline "
    "stated herein, we reserve the right to:\n\n"
    "1. Initiate legal proceedings for recovery of the outstanding amount together "
    "with interest, costs and legal fees without further notice.\n"
    "2. Report the default to relevant credit bureaus and regulatory authorities.\n"
    "3. Suspend all credit facilities and withhold further supply of goods or services.\n\n"
    "This notice is issued without prejudice to any other rights and remedies "
    "available to us under law."
)


def _ensure_demand_notice_settings():
    if frappe.db.exists("Demand Notice Settings", "Demand Notice Settings"):
        if not frappe.db.get_single_value("Demand Notice Settings", "interest_start_after_days"):
            frappe.db.set_single_value(
                "Demand Notice Settings", "interest_start_after_days", 60
            )
        frappe.db.set_single_value("Demand Notice Settings", "payment_deadline_days", 7)
        return
    frappe.get_doc({
        "doctype": "Demand Notice Settings",
        "default_interest_rate": 18,
        "interest_start_after_days": 60,
        "payment_deadline_days": 7,
        "default_legal_text": _DEFAULT_LEGAL_TEXT,
    }).insert(ignore_permissions=True)


def _ensure_demand_notice_default_print_format():
    if not frappe.db.exists("DocType", "Demand Notice"):
        return

    if not frappe.db.exists("Print Format", "Demand Notice"):
        return

    doctype_meta = frappe.get_meta("DocType")
    if doctype_meta.has_field("default_print_format"):
        frappe.db.set_value(
            "DocType",
            "Demand Notice",
            "default_print_format",
            "Demand Notice",
            update_modified=False,
        )

    print_format_meta = frappe.get_meta("Print Format")
    if print_format_meta.has_field("default"):
        frappe.db.set_value(
            "Print Format",
            "Demand Notice",
            "default",
            1,
            update_modified=False,
        )


# ---------------------------------------------------------------------------
# Credit Control Workspace
# ---------------------------------------------------------------------------

def _ensure_credit_control_workspace():
    has_demand_notice = frappe.db.exists("DocType", "Demand Notice")
    has_demand_notice_settings = frappe.db.exists("DocType", "Demand Notice Settings")
    has_cheque_bounce_case = frappe.db.exists("DocType", "Cheque Bounce Case")

    content_blocks = [
        {
            "id": "credit_control_header",
            "type": "header",
            "data": {"text": "Credit Management", "col": 12},
        },
        {
            "id": "credit_ptp_shortcut",
            "type": "shortcut",
            "data": {"shortcut_name": "Credit PTP", "col": 3},
        },
        {
            "id": "credit_report_shortcut",
            "type": "shortcut",
            "data": {"shortcut_name": "Credit Control Report", "col": 3},
        },
    ]

    links = [
        {
            "label": "Credit Management",
            "type": "Card Break",
            "hidden": 0,
            "is_query_report": 0,
            "link_count": 0,
            "onboard": 0,
            "dependencies": "",
        },
        {
            "label": "Credit PTP",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "Credit PTP",
            "hidden": 0,
            "is_query_report": 0,
            "link_count": 0,
            "onboard": 1,
            "dependencies": "",
        },
        {
            "label": "Credit Control Report",
            "type": "Link",
            "link_type": "Report",
            "link_to": "Credit Control Report",
            "hidden": 0,
            "is_query_report": 0,
            "link_count": 0,
            "onboard": 1,
            "dependencies": "",
        },
    ]

    shortcuts = [
        {
            "type": "DocType",
            "label": "Credit PTP",
            "link_to": "Credit PTP",
            "icon": "shield",
            "color": "Blue",
        },
        {
            "type": "Report",
            "label": "Credit Control Report",
            "link_to": "Credit Control Report",
            "icon": "list",
            "doc_view": "",
            "color": "Green",
        },
    ]

    if has_demand_notice or has_demand_notice_settings:
        content_blocks.append(
            {
                "id": "demand_notice_header",
                "type": "header",
                "data": {"text": "Demand Notices", "col": 12},
            }
        )

    if has_demand_notice:
        content_blocks.append(
            {
                "id": "demand_notice_shortcut",
                "type": "shortcut",
                "data": {"shortcut_name": "Demand Notice", "col": 3},
            }
        )
        links.extend(
            [
                {
                    "label": "Demand Notices",
                    "type": "Card Break",
                    "hidden": 0,
                    "is_query_report": 0,
                    "link_count": 0,
                    "onboard": 0,
                    "dependencies": "",
                },
                {
                    "label": "Demand Notice",
                    "type": "Link",
                    "link_type": "DocType",
                    "link_to": "Demand Notice",
                    "hidden": 0,
                    "is_query_report": 0,
                    "link_count": 0,
                    "onboard": 1,
                    "dependencies": "",
                },
            ]
        )
        shortcuts.append(
            {
                "type": "DocType",
                "label": "Demand Notice",
                "link_to": "Demand Notice",
                "icon": "file-text",
                "color": "Orange",
            }
        )

    if has_demand_notice_settings:
        content_blocks.append(
            {
                "id": "demand_notice_settings_shortcut",
                "type": "shortcut",
                "data": {"shortcut_name": "Demand Notice Settings", "col": 3},
            }
        )
        if not has_demand_notice:
            links.append(
                {
                    "label": "Demand Notices",
                    "type": "Card Break",
                    "hidden": 0,
                    "is_query_report": 0,
                    "link_count": 0,
                    "onboard": 0,
                    "dependencies": "",
                }
            )
        links.append(
            {
                "label": "Demand Notice Settings",
                "type": "Link",
                "link_type": "DocType",
                "link_to": "Demand Notice Settings",
                "hidden": 0,
                "is_query_report": 0,
                "link_count": 0,
                "onboard": 0,
                "dependencies": "",
            }
        )
        shortcuts.append(
            {
                "type": "DocType",
                "label": "Demand Notice Settings",
                "link_to": "Demand Notice Settings",
                "icon": "settings",
                "color": "Grey",
            }
        )

    if has_cheque_bounce_case:
        content_blocks.extend(
            [
                {
                    "id": "cheque_bounce_header",
                    "type": "header",
                    "data": {"text": "Cheque Bounce", "col": 12},
                },
                {
                    "id": "cheque_bounce_case_shortcut",
                    "type": "shortcut",
                    "data": {"shortcut_name": "Cheque Bounce Case", "col": 3},
                },
            ]
        )
        links.extend(
            [
                {
                    "label": "Cheque Bounce",
                    "type": "Card Break",
                    "hidden": 0,
                    "is_query_report": 0,
                    "link_count": 0,
                    "onboard": 0,
                    "dependencies": "",
                },
                {
                    "label": "Cheque Bounce Case",
                    "type": "Link",
                    "link_type": "DocType",
                    "link_to": "Cheque Bounce Case",
                    "hidden": 0,
                    "is_query_report": 0,
                    "link_count": 0,
                    "onboard": 1,
                    "dependencies": "",
                },
            ]
        )
        shortcuts.append(
            {
                "type": "DocType",
                "label": "Cheque Bounce Case",
                "link_to": "Cheque Bounce Case",
                "icon": "warning",
                "color": "Red",
            }
        )

    workspace_values = {
        "doctype": "Workspace",
        "name": "Credit Control",
        "title": "Credit Control",
        "label": "Credit Control",
        "module": "Snrg Credit Control",
        "category": "Modules",
        "public": 1,
        "icon": "credit-card",
        "developer_mode_only": 0,
        "disable_user_customization": 0,
        "hide_custom": 0,
        "is_default": 0,
        "is_hidden": 0,
        "extends": "",
        "extends_another_page": 0,
        "parent_page": "",
        "for_user": "",
        "restrict_to_domain": "",
        "content": json.dumps(content_blocks, separators=(",", ":")),
        "links": links,
        "roles": [],
        "shortcuts": shortcuts,
    }

    if frappe.db.exists("Workspace", "Credit Control"):
        workspace = frappe.get_doc("Workspace", "Credit Control")
        workspace.update(workspace_values)
        workspace.save(ignore_permissions=True)
        return

    frappe.get_doc(workspace_values).insert(ignore_permissions=True)
