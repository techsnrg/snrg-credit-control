import frappe

from snrg_credit_control.bank_account import (
    APPROVAL_STATUS_FIELD,
    APPROVED_BY_FIELD,
    APPROVED_ON_FIELD,
    REJECTION_REASON_FIELD,
    REQUESTED_BY_FIELD,
    REQUESTED_ON_FIELD,
)


def ensure_ap_setup():
    _ensure_bank_account_fields()
    _ensure_ap_payment_settings()
    _ensure_ap_bank_export_template()


def _ensure_bank_account_fields():
    fields = [
        {
            "fieldname": "custom_snrg_ap_approval_section",
            "fieldtype": "Section Break",
            "label": "AP Approval",
            "insert_after": "party",
            "collapsible": 1,
        },
        {
            "fieldname": APPROVAL_STATUS_FIELD,
            "fieldtype": "Select",
            "label": "Approval Status",
            "options": "\nPending Approval\nApproved\nRejected",
            "read_only": 1,
            "in_list_view": 1,
            "insert_after": "custom_snrg_ap_approval_section",
        },
        {
            "fieldname": REQUESTED_BY_FIELD,
            "fieldtype": "Link",
            "label": "Requested By",
            "options": "User",
            "read_only": 1,
            "insert_after": APPROVAL_STATUS_FIELD,
        },
        {
            "fieldname": REQUESTED_ON_FIELD,
            "fieldtype": "Datetime",
            "label": "Requested On",
            "read_only": 1,
            "insert_after": REQUESTED_BY_FIELD,
        },
        {
            "fieldname": "custom_snrg_ap_approval_col_break",
            "fieldtype": "Column Break",
            "insert_after": REQUESTED_ON_FIELD,
        },
        {
            "fieldname": APPROVED_BY_FIELD,
            "fieldtype": "Link",
            "label": "Approved By",
            "options": "User",
            "read_only": 1,
            "insert_after": "custom_snrg_ap_approval_col_break",
        },
        {
            "fieldname": APPROVED_ON_FIELD,
            "fieldtype": "Datetime",
            "label": "Approved On",
            "read_only": 1,
            "insert_after": APPROVED_BY_FIELD,
        },
        {
            "fieldname": REJECTION_REASON_FIELD,
            "fieldtype": "Small Text",
            "label": "Rejection Reason",
            "read_only": 1,
            "insert_after": APPROVED_ON_FIELD,
        },
    ]

    for field in fields:
        _ensure_custom_field("Bank Account", field)


def _ensure_ap_payment_settings():
    if not frappe.db.exists("DocType", "AP Payment Settings"):
        return

    if frappe.db.exists("AP Payment Settings", "AP Payment Settings"):
        if not frappe.db.get_single_value("AP Payment Settings", "debit_narration_prefix"):
            frappe.db.set_single_value("AP Payment Settings", "debit_narration_prefix", "BULK")
        return

    frappe.get_doc(
        {
            "doctype": "AP Payment Settings",
            "debit_narration_prefix": "BULK",
        }
    ).insert(ignore_permissions=True)


def _ensure_ap_bank_export_template():
    if not frappe.db.exists("DocType", "AP Bank Export Template"):
        return

    if frappe.db.exists("AP Bank Export Template", "ICICI NPAB"):
        return

    bank_name = frappe.db.get_value("Bank", {"bank_name": ["like", "%ICICI%"]}, "name")
    if not bank_name:
        bank_name = frappe.db.get_value("Bank", {"name": ["like", "%ICICI%"]}, "name")

    doc = frappe.get_doc(
        {
            "doctype": "AP Bank Export Template",
            "template_name": "ICICI NPAB",
            "bank": bank_name,
            "exporter_key": "ICICI_NPAB",
            "output_format": "XLS",
            "is_active": 1,
            "description": "Seeded ICICI bulk-payment export template.",
        }
    )
    doc.insert(ignore_permissions=True)


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
