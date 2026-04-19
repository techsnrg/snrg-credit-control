import frappe
from frappe import _
from frappe.utils import now_datetime


APPROVAL_STATUS_FIELD = "custom_snrg_ap_approval_status"
REQUESTED_BY_FIELD = "custom_snrg_ap_requested_by"
REQUESTED_ON_FIELD = "custom_snrg_ap_requested_on"
APPROVED_BY_FIELD = "custom_snrg_ap_approved_by"
APPROVED_ON_FIELD = "custom_snrg_ap_approved_on"
REJECTION_REASON_FIELD = "custom_snrg_ap_rejection_reason"

APPROVAL_CRITICAL_FIELDS = (
    "account_name",
    "account",
    "bank",
    "account_type",
    "account_subtype",
    "is_default",
    "is_company_account",
    "company",
    "party_type",
    "party",
    "iban",
    "branch_code",
    "bank_account_no",
    "disabled",
)


def get_approver_user():
    if not frappe.db.exists("DocType", "AP Payment Settings"):
        return None
    return frappe.db.get_single_value("AP Payment Settings", "approver_user")


def current_user_can_approve(user=None):
    user = user or frappe.session.user
    approver_user = get_approver_user()
    if not approver_user or user != approver_user:
        return False
    return "Managing Director" in frappe.get_roles(user)


def is_approved_bank_account(bank_account):
    if not bank_account:
        return False
    return (
        frappe.db.get_value("Bank Account", bank_account, APPROVAL_STATUS_FIELD) == "Approved"
    )


def validate(doc, method=None):
    if getattr(doc.flags, "snrg_skip_ap_approval_reset", False):
        return

    previous = None
    if not doc.is_new():
        fields = list(APPROVAL_CRITICAL_FIELDS) + [
            APPROVAL_STATUS_FIELD,
            REQUESTED_BY_FIELD,
            REQUESTED_ON_FIELD,
            APPROVED_BY_FIELD,
            APPROVED_ON_FIELD,
            REJECTION_REASON_FIELD,
        ]
        previous = frappe.db.get_value("Bank Account", doc.name, fields, as_dict=True)

    if doc.is_new():
        _mark_pending(doc)
        return

    if previous and _critical_fields_changed(doc, previous):
        _mark_pending(doc)
        return

    if not doc.get(APPROVAL_STATUS_FIELD):
        doc.set(APPROVAL_STATUS_FIELD, previous.get(APPROVAL_STATUS_FIELD) or "Pending Approval")


def _critical_fields_changed(doc, previous):
    for fieldname in APPROVAL_CRITICAL_FIELDS:
        if _normalize_field(doc.get(fieldname)) != _normalize_field(previous.get(fieldname)):
            return True
    return False


def _normalize_field(value):
    if value in (None, "", 0):
        return ""
    if isinstance(value, bool):
        return int(value)
    return str(value).strip()


def _mark_pending(doc):
    doc.set(APPROVAL_STATUS_FIELD, "Pending Approval")
    doc.set(REQUESTED_BY_FIELD, frappe.session.user or doc.owner or "Administrator")
    doc.set(REQUESTED_ON_FIELD, now_datetime())
    doc.set(APPROVED_BY_FIELD, None)
    doc.set(APPROVED_ON_FIELD, None)
    doc.set(REJECTION_REASON_FIELD, "")


@frappe.whitelist()
def get_bank_account_approval_context(bank_account=None):
    approver_user = get_approver_user()
    status = None
    if bank_account:
        status = frappe.db.get_value("Bank Account", bank_account, APPROVAL_STATUS_FIELD)
    return {
        "approver_user": approver_user,
        "can_approve": current_user_can_approve(),
        "status": status,
    }


@frappe.whitelist()
def approve_bank_account(name):
    _ensure_can_approve()
    if not name:
        frappe.throw(_("Bank Account is required."))

    frappe.db.set_value(
        "Bank Account",
        name,
        {
            APPROVAL_STATUS_FIELD: "Approved",
            APPROVED_BY_FIELD: frappe.session.user,
            APPROVED_ON_FIELD: now_datetime(),
            REJECTION_REASON_FIELD: "",
        },
        update_modified=True,
    )
    return {"message": _("Bank Account approved.")}


@frappe.whitelist()
def reject_bank_account(name, reason=None):
    _ensure_can_approve()
    if not name:
        frappe.throw(_("Bank Account is required."))

    frappe.db.set_value(
        "Bank Account",
        name,
        {
            APPROVAL_STATUS_FIELD: "Rejected",
            APPROVED_BY_FIELD: None,
            APPROVED_ON_FIELD: None,
            REJECTION_REASON_FIELD: (reason or "").strip(),
        },
        update_modified=True,
    )
    return {"message": _("Bank Account rejected.")}


def _ensure_can_approve():
    if not current_user_can_approve():
        frappe.throw(_("Only the configured Managing Director approver can do this action."), frappe.PermissionError)
