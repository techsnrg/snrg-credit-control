from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, now_datetime


REQUEST_ROLES = {"System Manager", "Sales Manager", "Sales User", "Fulfillment User"}
VALID_STATUSES = ("Open", "In Progress", "Completed", "Cancelled")
QTY_EPSILON = 0.0001


class ProductionRequest(Document):
    def validate(self):
        self._set_defaults()
        self._set_source_key()
        self._validate_requested_qty()
        self._validate_status()
        self._sync_completion_fields()

    def _set_defaults(self):
        if not self.status:
            self.status = "Open"
        if not self.requested_by:
            self.requested_by = frappe.session.user
        if not self.requested_on:
            self.requested_on = now_datetime()

    def _set_source_key(self):
        self.source_key = build_source_key(self.quotation, self.item_code)

    def _validate_requested_qty(self):
        if flt(self.requested_qty) <= 0:
            frappe.throw(_("Requested Qty must be greater than zero."))

    def _validate_status(self):
        if self.status not in VALID_STATUSES:
            frappe.throw(_("Invalid Production Request status: {0}").format(frappe.bold(self.status or "")))

    def _sync_completion_fields(self):
        if self.status == "Completed":
            if not self.completed_by:
                self.completed_by = frappe.session.user
            if not self.completed_on:
                self.completed_on = now_datetime()
            return

        self.completed_by = None
        self.completed_on = None


@frappe.whitelist()
def create_from_pending_rows(rows):
    require_request_role()
    rows = normalize_rows(rows)
    if not rows:
        frappe.throw(_("Select at least one pending row to create a production request."))

    created = []
    skipped = []
    pending_qty_by_source_key = {}
    requested_qty_by_source_key = {}

    for row in rows:
        normalized = normalize_pending_row(row)
        if flt(normalized["requested_qty"]) <= 0:
            skipped.append(
                {
                    "quotation": normalized["quotation"],
                    "item_code": normalized["item_code"],
                    "reason": "No pending quantity remaining.",
                }
            )
            continue

        source_key = build_source_key(normalized["quotation"], normalized["item_code"])
        if source_key not in pending_qty_by_source_key:
            pending_qty_by_source_key[source_key] = get_current_pending_qty_for_source_key(normalized)
        if source_key not in requested_qty_by_source_key:
            requested_qty_by_source_key[source_key] = get_existing_requested_qty_for_source_key(source_key)

        remaining_qty = max(
            flt(pending_qty_by_source_key[source_key]) - flt(requested_qty_by_source_key[source_key]),
            0,
        )
        if remaining_qty <= QTY_EPSILON:
            skipped.append(
                {
                    "quotation": normalized["quotation"],
                    "item_code": normalized["item_code"],
                    "reason": _("Pending quantity is already fully requested."),
                }
            )
            continue

        if flt(normalized["requested_qty"]) - remaining_qty > QTY_EPSILON:
            skipped.append(
                {
                    "quotation": normalized["quotation"],
                    "item_code": normalized["item_code"],
                    "reason": _("Only {0} qty is still available to request.").format(
                        frappe.format_value(remaining_qty, {"fieldtype": "Float", "precision": 2})
                    ),
                }
            )
            continue

        doc = frappe.get_doc(
            {
                "doctype": "Production Request",
                **normalized,
                "status": "Open",
                "requested_by": frappe.session.user,
                "requested_on": now_datetime(),
            }
        )
        doc.insert(ignore_permissions=True)
        created.append(doc.name)
        requested_qty_by_source_key[source_key] = flt(requested_qty_by_source_key[source_key]) + flt(
            normalized["requested_qty"]
        )

    message_parts = []
    if created:
        if len(created) == 1:
            message_parts.append(_("Request created"))
        else:
            message_parts.append(_("{0} requests created").format(len(created)))
    if skipped:
        if len(skipped) == 1:
            message_parts.append(_("1 skipped"))
        else:
            message_parts.append(_("{0} skipped").format(len(skipped)))

    return {
        "created": created,
        "updated": [],
        "skipped": skipped,
        "created_count": len(created),
        "updated_count": 0,
        "skipped_count": len(skipped),
        "message": ", ".join(message_parts) if message_parts else _("No requests were created."),
    }


@frappe.whitelist()
def get_board_data(company=None, search=None, show_completed=1):
    require_request_role()

    filters = {}
    if company:
        filters["company"] = company
    if not cint(show_completed):
        filters["status"] = ["!=", "Completed"]

    rows = frappe.get_all(
        "Production Request",
        filters=filters,
        fields=[
            "name",
            "quotation",
            "quotation_date",
            "customer",
            "customer_name",
            "company",
            "item_code",
            "item_name",
            "requested_qty",
            "required_by_date",
            "status",
            "remarks",
            "assigned_to",
            "requested_by",
            "requested_on",
            "completed_by",
            "completed_on",
            "modified",
        ],
        order_by="modified desc, creation desc",
        limit_page_length=500,
    )

    user_ids = sorted(
        {
            user_id
            for row in rows
            for user_id in (row.get("requested_by"), row.get("assigned_to"))
            if user_id
        }
    )
    user_name_map = get_user_name_map(user_ids)

    search_term = (search or "").strip().lower()
    normalized_rows = [serialize_request_row(row, user_name_map) for row in rows]
    if search_term:
        normalized_rows = [
            row
            for row in normalized_rows
            if search_term in " ".join(
                [
                    str(row.get("name") or "").lower(),
                    str(row.get("quotation") or "").lower(),
                    str(row.get("customer") or "").lower(),
                    str(row.get("customer_name") or "").lower(),
                    str(row.get("item_code") or "").lower(),
                    str(row.get("item_name") or "").lower(),
                    str(row.get("required_by_date") or "").lower(),
                    str(row.get("requested_by_name") or "").lower(),
                    str(row.get("assigned_to") or "").lower(),
                    str(row.get("assigned_to_name") or "").lower(),
                ]
            )
        ]

    grouped = {status: [] for status in VALID_STATUSES}
    for row in normalized_rows:
        grouped.setdefault(row["status"], []).append(row)

    return {
        "generated_on": str(now_datetime()),
        "filters": {
            "company": company or "",
            "search": search or "",
            "show_completed": cint(show_completed),
        },
        "summary": {
            "open_count": len(grouped.get("Open", [])),
            "in_progress_count": len(grouped.get("In Progress", [])),
            "completed_count": len(grouped.get("Completed", [])),
            "open_qty": sum(flt(row.get("requested_qty")) for row in grouped.get("Open", [])),
            "in_progress_qty": sum(flt(row.get("requested_qty")) for row in grouped.get("In Progress", [])),
            "completed_qty": sum(flt(row.get("requested_qty")) for row in grouped.get("Completed", [])),
        },
        "groups": grouped,
    }


@frappe.whitelist()
def set_request_status(name, status):
    require_request_role()

    if not name:
        frappe.throw(_("Production Request name is required."))
    if status not in VALID_STATUSES:
        frappe.throw(_("Invalid status: {0}").format(frappe.bold(status or "")))

    doc = frappe.get_doc("Production Request", name)
    doc.status = status
    doc.save(ignore_permissions=True)

    return {
        "name": doc.name,
        "status": doc.status,
        "message": _("Production Request {0} moved to {1}.").format(
            frappe.bold(doc.name),
            frappe.bold(doc.status),
        ),
    }


@frappe.whitelist()
def set_request_assignee(name, assigned_to=None):
    require_request_role()

    if not name:
        frappe.throw(_("Production Request name is required."))

    doc = frappe.get_doc("Production Request", name)
    doc.assigned_to = (assigned_to or "").strip() or None
    doc.save(ignore_permissions=True)

    user_name_map = get_user_name_map([doc.assigned_to] if doc.assigned_to else [])
    assigned_to_name = user_name_map.get(doc.assigned_to) or doc.assigned_to or ""
    return {
        "name": doc.name,
        "assigned_to": doc.assigned_to or "",
        "assigned_to_name": assigned_to_name,
        "message": _("Production Request {0} assignee updated.").format(frappe.bold(doc.name)),
    }


def require_request_role():
    if any(role in REQUEST_ROLES for role in frappe.get_roles()):
        return
    frappe.throw(_("Not permitted."), frappe.PermissionError)


def normalize_rows(rows):
    rows = frappe.parse_json(rows) if isinstance(rows, str) else rows
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def normalize_pending_row(row):
    quotation = (row.get("quotation") or "").strip()
    if not quotation:
        frappe.throw(_("Quotation is required to create a Production Request."))

    item_code = (row.get("item_code") or "").strip()
    if not item_code:
        frappe.throw(_("Item Code is required to create a Production Request."))

    required_by_date = row.get("required_by_date")
    if not required_by_date:
        frappe.throw(_("Required By date is required to create a Production Request."))

    return {
        "quotation": quotation,
        "quotation_date": row.get("quotation_date") or None,
        "customer": (row.get("customer") or "").strip(),
        "customer_name": (row.get("customer_name") or "").strip(),
        "company": (row.get("company") or "").strip(),
        "item_code": item_code,
        "item_name": (row.get("item_name") or "").strip(),
        "requested_qty": flt(
            row.get("requested_qty") or row.get("remaining_requestable_qty") or row.get("total_uninvoiced_qty")
        ),
        "required_by_date": str(getdate(required_by_date)),
        "remarks": (row.get("remarks") or "").strip(),
        "assigned_to": (row.get("assigned_to") or "").strip() or None,
    }


def apply_row_to_request(doc, row):
    doc.quotation = row["quotation"]
    doc.quotation_date = row.get("quotation_date") or None
    doc.customer = row.get("customer") or ""
    doc.customer_name = row.get("customer_name") or ""
    doc.company = row.get("company") or ""
    doc.item_code = row["item_code"]
    doc.item_name = row.get("item_name") or ""
    doc.requested_qty = flt(row.get("requested_qty"))
    doc.required_by_date = row.get("required_by_date") or None
    doc.assigned_to = row.get("assigned_to") or None
    if row.get("remarks"):
        doc.remarks = row["remarks"]
    return doc


def get_current_pending_qty_for_source_key(row):
    from snrg_credit_control.snrg_credit_control.pending_invoice_planning import get_pending_invoice_planning_rows

    filters = {
        "quotation": row.get("quotation"),
        "item_code": row.get("item_code"),
    }
    if row.get("company"):
        filters["company"] = row.get("company")

    rows = get_pending_invoice_planning_rows(
        filters=filters,
        quotation_id=row.get("quotation"),
        pending_only=False,
    )
    for detail_row in rows:
        if build_source_key(detail_row.get("quotation"), detail_row.get("item_code")) == build_source_key(
            row.get("quotation"),
            row.get("item_code"),
        ):
            return flt(detail_row.get("total_uninvoiced_qty"))
    return 0


def get_existing_requested_qty_for_source_key(source_key):
    return flt(
        frappe.db.sql(
            """
            SELECT COALESCE(SUM(requested_qty), 0)
            FROM `tabProduction Request`
            WHERE source_key = %s
              AND status != 'Cancelled'
            """,
            source_key,
        )[0][0]
        or 0
    )


def build_source_key(quotation, item_code):
    return f"{(quotation or '').strip().lower()}::{(item_code or '').strip().lower()}"


def get_user_name_map(user_ids):
    user_ids = [user_id for user_id in (user_ids or []) if user_id]
    if not user_ids:
        return {}

    return {
        user.name: (user.full_name or user.name)
        for user in frappe.get_all(
            "User",
            filters={"name": ["in", user_ids]},
            fields=["name", "full_name"],
            limit_page_length=len(user_ids),
        )
    }


def serialize_request_row(row, user_name_map=None):
    user_name_map = user_name_map or {}
    requested_on = row.get("requested_on")
    completed_on = row.get("completed_on")
    requested_by = row.get("requested_by") or ""
    assigned_to = row.get("assigned_to") or ""
    return {
        "name": row.get("name"),
        "quotation": row.get("quotation") or "",
        "quotation_date": str(row.get("quotation_date") or ""),
        "customer": row.get("customer") or "",
        "customer_name": row.get("customer_name") or "",
        "company": row.get("company") or "",
        "item_code": row.get("item_code") or "",
        "item_name": row.get("item_name") or "",
        "requested_qty": flt(row.get("requested_qty")),
        "required_by_date": str(row.get("required_by_date") or ""),
        "status": row.get("status") or "Open",
        "remarks": row.get("remarks") or "",
        "assigned_to": assigned_to,
        "assigned_to_name": user_name_map.get(assigned_to) or assigned_to,
        "requested_by": requested_by,
        "requested_by_name": user_name_map.get(requested_by) or requested_by,
        "requested_on": str(requested_on or ""),
        "completed_by": row.get("completed_by") or "",
        "completed_on": str(completed_on or ""),
        "modified": str(row.get("modified") or ""),
        "age_days": get_age_days(requested_on),
    }


def get_age_days(requested_on):
    if not requested_on:
        return 0
    return max((getdate(now_datetime()) - getdate(requested_on)).days, 0)
