from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, now_datetime


REQUEST_ROLES = {"System Manager", "Sales Manager", "Sales User", "Fulfillment User"}
ACTIVE_REQUEST_STATUSES = ("Open", "In Progress")
VALID_STATUSES = ("Open", "In Progress", "Completed", "Cancelled")


class ProductionRequest(Document):
    def validate(self):
        self._set_defaults()
        self._set_source_key()
        self._validate_requested_qty()
        self._validate_status()
        self._validate_active_duplicate()
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

    def _validate_active_duplicate(self):
        if self.status not in ACTIVE_REQUEST_STATUSES or not self.source_key:
            return

        filters = {
            "source_key": self.source_key,
            "status": ["in", list(ACTIVE_REQUEST_STATUSES)],
        }
        if not self.is_new():
            filters["name"] = ["!=", self.name]

        duplicate = frappe.db.get_value(self.doctype, filters, "name")
        if duplicate:
            frappe.throw(
                _("Active Production Request {0} already exists for this quotation item.").format(
                    frappe.bold(duplicate)
                ),
                title=_("Duplicate Production Request"),
            )

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
    updated = []
    skipped = []

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

        existing_name = frappe.db.get_value(
            "Production Request",
            {
                "source_key": build_source_key(normalized["quotation"], normalized["item_code"]),
                "status": ["in", list(ACTIVE_REQUEST_STATUSES)],
            },
            "name",
        )

        if existing_name:
            doc = frappe.get_doc("Production Request", existing_name)
            apply_row_to_request(doc, normalized)
            doc.save(ignore_permissions=True)
            updated.append(doc.name)
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

    message_parts = []
    if created:
        message_parts.append(_("{0} created").format(len(created)))
    if updated:
        message_parts.append(_("{0} refreshed").format(len(updated)))
    if skipped:
        message_parts.append(_("{0} skipped").format(len(skipped)))

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "created_count": len(created),
        "updated_count": len(updated),
        "skipped_count": len(skipped),
        "message": ", ".join(message_parts) if message_parts else _("No Production Requests were created."),
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
            "status",
            "remarks",
            "requested_by",
            "requested_on",
            "completed_by",
            "completed_on",
            "modified",
        ],
        order_by="modified desc, creation desc",
        limit_page_length=500,
    )

    requested_by_ids = sorted({row.get("requested_by") for row in rows if row.get("requested_by")})
    requested_by_name_map = {}
    if requested_by_ids:
        requested_by_name_map = {
            user.name: (user.full_name or user.name)
            for user in frappe.get_all(
                "User",
                filters={"name": ["in", requested_by_ids]},
                fields=["name", "full_name"],
                limit_page_length=len(requested_by_ids),
            )
        }

    search_term = (search or "").strip().lower()
    normalized_rows = [serialize_request_row(row, requested_by_name_map) for row in rows]
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
                    str(row.get("requested_by_name") or "").lower(),
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

    return {
        "quotation": quotation,
        "quotation_date": row.get("quotation_date") or None,
        "customer": (row.get("customer") or "").strip(),
        "customer_name": (row.get("customer_name") or "").strip(),
        "company": (row.get("company") or "").strip(),
        "item_code": item_code,
        "item_name": (row.get("item_name") or "").strip(),
        "requested_qty": flt(row.get("requested_qty") or row.get("total_uninvoiced_qty")),
        "remarks": (row.get("remarks") or "").strip(),
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
    if row.get("remarks"):
        doc.remarks = row["remarks"]
    return doc


def build_source_key(quotation, item_code):
    return f"{(quotation or '').strip().lower()}::{(item_code or '').strip().lower()}"


def serialize_request_row(row, requested_by_name_map=None):
    requested_by_name_map = requested_by_name_map or {}
    requested_on = row.get("requested_on")
    completed_on = row.get("completed_on")
    requested_by = row.get("requested_by") or ""
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
        "status": row.get("status") or "Open",
        "remarks": row.get("remarks") or "",
        "requested_by": requested_by,
        "requested_by_name": requested_by_name_map.get(requested_by) or requested_by,
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
