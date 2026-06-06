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
    _ensure_so_fields()
    _ensure_quotation_fields()
    _ensure_sales_invoice_fields()
    _ensure_report()
    _ensure_employee_signatory_fields()
    _ensure_demand_notice_settings()
    _ensure_sales_tracking_sla_settings()
    _ensure_summer_bonanza_scheme()
    _ensure_credit_control_workspace()
    _ensure_scheme_management_workspace()
    _ensure_demand_notice_default_print_format()
    frappe.db.commit()


def after_migrate():
    _ensure_module()
    _ensure_role()
    _ensure_customer_fields()
    _ensure_so_fields()
    _ensure_quotation_fields()
    _ensure_sales_invoice_fields()
    _ensure_report()
    _ensure_employee_signatory_fields()
    _ensure_demand_notice_settings()
    _ensure_sales_tracking_sla_settings()
    _ensure_summer_bonanza_scheme()
    _ensure_credit_control_workspace()
    _ensure_scheme_management_workspace()
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
    for role_name in ("Credit Approver", "Legal", "Fulfillment User", "Price Request User", "Pricing Approver"):
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
        "fieldname": "custom_snrg_credit_checked_on",
        "fieldtype": "Datetime",
        "label": "Credit Checked On",
        "read_only": 1,
        "hidden": 1,
        "insert_after": "custom_snrg_credit_check_reason_code",
    },
    {
        "fieldname": "custom_snrg_col_break_1",
        "fieldtype": "Column Break",
        "insert_after": "custom_snrg_credit_checked_on",
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
    {
        "fieldname": "custom_credit_clearance_date",
        "fieldtype": "Date",
        "label": "Credit Clearance Date",
        "read_only": 1,
        "insert_after": "custom_credit_approval_status",
    },
]


def _ensure_so_fields():
    for fdef in _SO_FIELDS:
        _ensure_custom_field("Sales Order", fdef)


_QUOTATION_FIELDS = [
    {
        "fieldname": "custom_snrg_tracking_section",
        "fieldtype": "Section Break",
        "label": "Sales Tracking",
        "insert_after": "valid_till",
        "collapsible": 1,
    },
    {
        "fieldname": "custom_expected_dispatch_date",
        "fieldtype": "Date",
        "label": "Expected Dispatch Date",
        "insert_after": "custom_snrg_tracking_section",
    },
    {
        "fieldname": "custom_latest_ho_remark",
        "fieldtype": "Small Text",
        "label": "Latest HO Remark",
        "insert_after": "custom_expected_dispatch_date",
    },
    {
        "fieldname": "custom_credit_clearance_date",
        "fieldtype": "Date",
        "label": "Credit Clearance Date",
        "read_only": 1,
        "insert_after": "custom_latest_ho_remark",
    },
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
        "fieldname": "custom_snrg_credit_checked_on",
        "fieldtype": "Datetime",
        "label": "Credit Checked On",
        "read_only": 1,
        "hidden": 1,
        "insert_after": "custom_snrg_credit_check_reason_code",
    },
    {
        "fieldname": "custom_snrg_overdue_count_terms",
        "fieldtype": "Int",
        "label": "Overdue Invoice Count",
        "read_only": 1,
        "hidden": 1,
        "insert_after": "custom_snrg_credit_checked_on",
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


_SALES_INVOICE_FIELDS = [
    {
        "fieldname": "custom_snrg_dispatch_section",
        "fieldtype": "Section Break",
        "label": "Dispatch & Delivery Tracking",
        "insert_after": "transporter",
        "collapsible": 1,
    },
    {
        "fieldname": "custom_shipping_date",
        "fieldtype": "Date",
        "label": "Shipping Date",
        "insert_after": "custom_snrg_dispatch_section",
        "allow_on_submit": 0,
    },
    {
        "fieldname": "custom_awb_number",
        "fieldtype": "Data",
        "label": "AWB Number",
        "insert_after": "custom_shipping_date",
        "allow_on_submit": 0,
    },
    {
        "fieldname": "custom_no_of_cartons",
        "fieldtype": "Int",
        "label": "No. of Cartons",
        "insert_after": "custom_awb_number",
        "allow_on_submit": 0,
    },
    {
        "fieldname": "custom_snrg_dispatch_col_break",
        "fieldtype": "Column Break",
        "insert_after": "custom_no_of_cartons",
    },
    {
        "fieldname": "custom_delivery_status",
        "fieldtype": "Select",
        "label": "Delivery Status",
        "options": "\nPending\nIn Transit\nDelivered\nPartially Delivered\nReturned\nHold",
        "insert_after": "custom_snrg_dispatch_col_break",
        "allow_on_submit": 0,
    },
    {
        "fieldname": "custom_delivery_date",
        "fieldtype": "Date",
        "label": "Delivery Date",
        "insert_after": "custom_delivery_status",
        "allow_on_submit": 0,
    },
    {
        "fieldname": "custom_pod_attachment",
        "fieldtype": "Attach",
        "label": "POD Attachment",
        "insert_after": "custom_delivery_date",
        "allow_on_submit": 0,
    },
    {
        "fieldname": "custom_dispatch_delivery_remarks",
        "fieldtype": "Small Text",
        "label": "Dispatch / Delivery Remarks",
        "insert_after": "custom_pod_attachment",
        "allow_on_submit": 0,
    },
]


def _ensure_sales_invoice_fields():
    meta = frappe.get_meta("Sales Invoice")
    dispatch_anchor = _pick_last_existing_field(
        meta,
        (
            "gst_vehicle_type",
            "distance",
            "lr_date",
            "transport_receipt_date",
            "transporter_name",
            "mode_of_transport",
            "gst_transporter_id",
            "transporter",
        ),
    ) or "transporter"

    for fdef in _SALES_INVOICE_FIELDS:
        resolved = dict(fdef)
        if resolved["fieldname"] == "custom_snrg_dispatch_section":
            resolved["insert_after"] = dispatch_anchor
        _ensure_custom_field("Sales Invoice", resolved)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _ensure_report():
    report_defs = [
        {
            "report_name": "Credit Control Report",
            "ref_doctype": "Sales Order",
        },
        {
            "report_name": "PTP Dashboard",
            "ref_doctype": "Credit PTP",
        },
        {
            "report_name": "Minimum Selling Rate Invoice Check",
            "ref_doctype": "Sales Invoice",
        },
        {
            "report_name": "Sales Person Sales and Collection Summary",
            "ref_doctype": "Sales Invoice",
        },
    ]

    for report_def in report_defs:
        name = report_def["report_name"]
        if frappe.db.exists("Report", name):
            frappe.db.set_value("Report", name, "module", "Snrg Credit Control")
            frappe.db.set_value("Report", name, "disabled", 0)
            continue

        frappe.get_doc(
            {
                "doctype": "Report",
                "report_name": name,
                "report_type": "Script Report",
                "ref_doctype": report_def["ref_doctype"],
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
# SNRG Scheme — starter records
# ---------------------------------------------------------------------------

def _ensure_summer_bonanza_scheme():
    if not frappe.db.exists("DocType", "SNRG Scheme"):
        return

    scheme_name = "Summer Bonanza Plates Scheme"
    if frappe.db.exists("SNRG Scheme", scheme_name):
        frappe.db.set_value(
            "SNRG Scheme",
            scheme_name,
            {
                "scheme_type": "Period Cumulative Amount Slab",
                "calculation_basis": "Excluded",
            },
            update_modified=False,
        )
        return

    frappe.get_doc(
        {
            "doctype": "SNRG Scheme",
            "scheme_name": scheme_name,
            "scheme_type": "Period Cumulative Amount Slab",
            "calculation_basis": "Excluded",
            "valid_from": "2026-05-28",
            "valid_upto": "2026-06-30",
            "slabs": [
                {"slab_amount": 50000, "reward": "1 Cooler (95 Ltrs.)"},
                {"slab_amount": 100000, "reward": "1.5 Ton AC"},
                {"slab_amount": 200000, "reward": "iPhone 16e"},
            ],
            "notes": (
                "Configure eligible plate item codes or item groups in this scheme. "
                "Use Excluded Item Codes for SKUs that should not qualify even if their item group qualifies."
            ),
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


def _pick_last_existing_field(meta, fieldnames):
    field_order = {
        df.fieldname: idx
        for idx, df in enumerate(meta.fields or [])
        if getattr(df, "fieldname", None)
    }
    matches = [fieldname for fieldname in fieldnames if fieldname in field_order]
    if not matches:
        return None
    return max(matches, key=lambda fieldname: field_order[fieldname])


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
# Sales Tracking SLA Settings — default singleton record
# ---------------------------------------------------------------------------

_DEFAULT_SALES_TRACKING_SLA_SETTINGS = {
    "quotation_to_credit_clearance_days": 3,
    "quotation_to_delivery_days": 10,
    "invoice_to_delivery_days": 4,
    "delivery_to_pod_days": 2,
    "credit_hold_age_days": 2,
    "esd_delay_days": 1,
    "no_invoice_after_so_days": 3,
}


def _ensure_sales_tracking_sla_settings():
    doctype_name = "Sales Tracking SLA Settings"
    if not frappe.db.exists("DocType", doctype_name):
        return

    if frappe.db.exists(doctype_name, doctype_name):
        for fieldname, value in _DEFAULT_SALES_TRACKING_SLA_SETTINGS.items():
            if frappe.db.get_single_value(doctype_name, fieldname) in (None, ""):
                frappe.db.set_single_value(doctype_name, fieldname, value)
        return

    frappe.get_doc(
        {
            "doctype": doctype_name,
            **_DEFAULT_SALES_TRACKING_SLA_SETTINGS,
        }
    ).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Credit Control Workspace
# ---------------------------------------------------------------------------

def _ensure_credit_control_workspace():
    has_demand_notice = frappe.db.exists("DocType", "Demand Notice")
    has_demand_notice_settings = frappe.db.exists("DocType", "Demand Notice Settings")
    has_ptp_dashboard_page = frappe.db.exists("Page", "ptp-dashboard")
    has_md_dashboard_page = frappe.db.exists("Page", "managing-director-dashboard")
    has_sales_tracking_page = frappe.db.exists("Page", "sales-tracking")
    has_sales_tracking_sla_settings = frappe.db.exists("DocType", "Sales Tracking SLA Settings")

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
        {
            "id": "sales_person_sales_collection_summary_shortcut",
            "type": "shortcut",
            "data": {"shortcut_name": "Sales Person Sales and Collection Summary", "col": 3},
        },
    ]

    if has_ptp_dashboard_page:
        content_blocks.append(
            {
                "id": "ptp_dashboard_page_shortcut",
                "type": "shortcut",
                "data": {"shortcut_name": "PTP Dashboard", "col": 3},
            }
        )

    if has_md_dashboard_page:
        content_blocks.append(
            {
                "id": "md_dashboard_page_shortcut",
                "type": "shortcut",
                "data": {"shortcut_name": "Managing Director Dashboard", "col": 3},
            }
        )

    if has_sales_tracking_page:
        content_blocks.append(
            {
                "id": "sales_tracking_page_shortcut",
                "type": "shortcut",
                "data": {"shortcut_name": "Sales Tracking", "col": 3},
            }
        )

    if has_sales_tracking_sla_settings:
        content_blocks.append(
            {
                "id": "sales_tracking_sla_settings_shortcut",
                "type": "shortcut",
                "data": {"shortcut_name": "Sales Tracking SLA Settings", "col": 3},
            }
        )
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
        {
            "label": "Sales Person Sales and Collection Summary",
            "type": "Link",
            "link_type": "Report",
            "link_to": "Sales Person Sales and Collection Summary",
            "hidden": 0,
            "is_query_report": 0,
            "link_count": 0,
            "onboard": 1,
            "dependencies": "",
        },
        {
            "label": "PTP Dashboard",
            "type": "Link",
            "link_type": "Page" if has_ptp_dashboard_page else "Report",
            "link_to": "ptp-dashboard" if has_ptp_dashboard_page else "PTP Dashboard",
            "hidden": 0,
            "is_query_report": 0,
            "link_count": 0,
            "onboard": 1,
            "dependencies": "",
        },
        {
            "label": "Managing Director Dashboard",
            "type": "Link",
            "link_type": "Page",
            "link_to": "managing-director-dashboard",
            "hidden": 0,
            "is_query_report": 0,
            "link_count": 0,
            "onboard": 1,
            "dependencies": "",
        },
        {
            "label": "Sales Tracking",
            "type": "Link",
            "link_type": "Page",
            "link_to": "sales-tracking",
            "hidden": 0,
            "is_query_report": 0,
            "link_count": 0,
            "onboard": 1,
            "dependencies": "",
        },
        {
            "label": "Sales Tracking SLA Settings",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "Sales Tracking SLA Settings",
            "hidden": 0,
            "is_query_report": 0,
            "link_count": 0,
            "onboard": 0,
            "dependencies": "",
        },
        {
            "label": "PTP Dashboard Report",
            "type": "Link",
            "link_type": "Report",
            "link_to": "PTP Dashboard",
            "hidden": 0,
            "is_query_report": 0,
            "link_count": 0,
            "onboard": 0,
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
        {
            "type": "Report",
            "label": "Sales Person Sales and Collection Summary",
            "link_to": "Sales Person Sales and Collection Summary",
            "icon": "chart",
            "doc_view": "",
            "color": "Blue",
        },
    ]

    if has_ptp_dashboard_page:
        shortcuts.append(
            {
                "type": "Page",
                "label": "PTP Dashboard",
                "link_to": "ptp-dashboard",
                "icon": "dashboard",
                "color": "Orange",
            }
        )

    if has_md_dashboard_page:
        shortcuts.append(
            {
                "type": "Page",
                "label": "Managing Director Dashboard",
                "link_to": "managing-director-dashboard",
                "icon": "dashboard",
                "color": "Dark Grey",
            }
        )

    if has_sales_tracking_page:
        shortcuts.append(
            {
                "type": "Page",
                "label": "Sales Tracking",
                "link_to": "sales-tracking",
                "icon": "table",
                "color": "Blue",
            }
        )

    if has_sales_tracking_sla_settings:
        shortcuts.append(
            {
                "type": "DocType",
                "label": "Sales Tracking SLA Settings",
                "link_to": "Sales Tracking SLA Settings",
                "icon": "settings",
                "color": "Grey",
            }
        )

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


# ---------------------------------------------------------------------------
# Scheme Management Workspace
# ---------------------------------------------------------------------------

def _ensure_scheme_management_workspace():
    has_snrg_scheme = frappe.db.exists("DocType", "SNRG Scheme")
    has_scheme_planning_page = frappe.db.exists("Page", "scheme-planning")

    if not has_snrg_scheme and not has_scheme_planning_page:
        return

    content_blocks = [
        {
            "id": "scheme_management_header",
            "type": "header",
            "data": {"text": "Scheme Management", "col": 12},
        },
    ]

    links = [
        {
            "label": "Scheme Management",
            "type": "Card Break",
            "hidden": 0,
            "is_query_report": 0,
            "link_count": 0,
            "onboard": 0,
            "dependencies": "",
        }
    ]

    shortcuts = []

    if has_scheme_planning_page:
        content_blocks.append(
            {
                "id": "scheme_planning_shortcut",
                "type": "shortcut",
                "data": {"shortcut_name": "Scheme Planning", "col": 3},
            }
        )
        links.append(
            {
                "label": "Scheme Planning",
                "type": "Link",
                "link_type": "Page",
                "link_to": "scheme-planning",
                "hidden": 0,
                "is_query_report": 0,
                "link_count": 0,
                "onboard": 1,
                "dependencies": "",
            }
        )
        shortcuts.append(
            {
                "type": "Page",
                "label": "Scheme Planning",
                "link_to": "scheme-planning",
                "icon": "search",
                "color": "Blue",
            }
        )

    if has_snrg_scheme:
        content_blocks.append(
            {
                "id": "snrg_scheme_shortcut",
                "type": "shortcut",
                "data": {"shortcut_name": "SNRG Scheme", "col": 3},
            }
        )
        links.append(
            {
                "label": "SNRG Scheme",
                "type": "Link",
                "link_type": "DocType",
                "link_to": "SNRG Scheme",
                "hidden": 0,
                "is_query_report": 0,
                "link_count": 0,
                "onboard": 1,
                "dependencies": "",
            }
        )
        shortcuts.append(
            {
                "type": "DocType",
                "label": "SNRG Scheme",
                "link_to": "SNRG Scheme",
                "icon": "gift",
                "color": "Purple",
            }
        )

    workspace_values = {
        "doctype": "Workspace",
        "name": "Scheme Management",
        "title": "Scheme Management",
        "label": "Scheme Management",
        "module": "Snrg Credit Control",
        "category": "Modules",
        "public": 1,
        "icon": "gift",
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

    if frappe.db.exists("Workspace", "Scheme Management"):
        workspace = frappe.get_doc("Workspace", "Scheme Management")
        workspace.update(workspace_values)
        workspace.save(ignore_permissions=True)
        return

    frappe.get_doc(workspace_values).insert(ignore_permissions=True)
