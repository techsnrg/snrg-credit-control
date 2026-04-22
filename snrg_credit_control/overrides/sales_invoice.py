import json

import frappe
from frappe import _
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice

FULFILLMENT_ROLE = "Fulfillment User"
FULFILLMENT_FIELDS = (
    "custom_shipping_date",
    "custom_awb_number",
    "custom_no_of_cartons",
    "custom_delivery_status",
    "custom_delivery_date",
    "custom_pod_attachment",
    "custom_dispatch_delivery_remarks",
)


class CustomSalesInvoice(SalesInvoice):
    def check_credit_limit(self):
        if self._is_backed_by_approved_sales_orders():
            return
        return super().check_credit_limit()

    def _is_backed_by_approved_sales_orders(self):
        sales_orders = {
            row.sales_order
            for row in (self.items or [])
            if getattr(row, "sales_order", None)
        }

        if not sales_orders:
            return False

        rows = frappe.get_all(
            "Sales Order",
            filters={"name": ["in", list(sales_orders)]},
            fields=["name", "docstatus", "custom_credit_approval_status"],
        )

        if len(rows) != len(sales_orders):
            return False

        for row in rows:
            if row.docstatus != 1:
                return False
            if (row.custom_credit_approval_status or "").strip().lower() != "approved":
                return False

        return True


@frappe.whitelist()
def update_fulfillment_details(name, values=None):
    if not name:
        frappe.throw(_("Sales Invoice is required."))

    doc = frappe.get_doc("Sales Invoice", name)
    _ensure_can_update_fulfillment(doc)

    if doc.docstatus != 1:
        frappe.throw(_("Fulfillment details can only be updated after the Sales Invoice is submitted."))

    parsed_values = _parse_fulfillment_values(values)
    updates = {fieldname: parsed_values[fieldname] for fieldname in FULFILLMENT_FIELDS if fieldname in parsed_values}

    if not updates:
        frappe.throw(_("No fulfillment details were provided."))

    for fieldname, value in updates.items():
        doc.set(fieldname, value)

    doc.save(ignore_permissions=True)

    return {
        "name": doc.name,
        "message": _("Fulfillment details updated successfully."),
        "values": {fieldname: doc.get(fieldname) for fieldname in FULFILLMENT_FIELDS},
    }


def _ensure_can_update_fulfillment(doc):
    if not doc.has_permission("read"):
        frappe.throw(_("Not permitted."), frappe.PermissionError)

    user_roles = set(frappe.get_roles(frappe.session.user))
    if FULFILLMENT_ROLE in user_roles or "System Manager" in user_roles:
        return

    frappe.throw(
        _("Only users with the {0} role can update fulfillment details on submitted Sales Invoices.").format(
            frappe.bold(FULFILLMENT_ROLE)
        ),
        frappe.PermissionError,
    )


def _parse_fulfillment_values(values):
    if values is None:
        return {}

    if isinstance(values, str):
        values = values.strip()
        if not values:
            return {}
        try:
            values = json.loads(values)
        except json.JSONDecodeError:
            frappe.throw(_("Invalid fulfillment update payload."), frappe.ValidationError)

    if not isinstance(values, dict):
        frappe.throw(_("Fulfillment update payload must be a JSON object."))

    parsed = {}
    meta = frappe.get_meta("Sales Invoice")

    for fieldname in FULFILLMENT_FIELDS:
        if fieldname not in values:
            continue

        value = values.get(fieldname)
        df = meta.get_field(fieldname)

        if df and df.fieldtype in {"Date", "Datetime"}:
            parsed[fieldname] = value or None
        elif df and df.fieldtype == "Int":
            parsed[fieldname] = cint_or_none(value)
        else:
            parsed[fieldname] = (value or "").strip() if isinstance(value, str) else value

    _validate_delivery_status(parsed, meta)
    return parsed


def _validate_delivery_status(values, meta):
    if "custom_delivery_status" not in values:
        return

    status = values.get("custom_delivery_status") or ""
    df = meta.get_field("custom_delivery_status")
    allowed = {
        option.strip()
        for option in (df.options or "").splitlines()
        if option.strip()
    }

    if status and status not in allowed:
        frappe.throw(_("Invalid Delivery Status: {0}").format(frappe.bold(status)))


def cint_or_none(value):
    if value in (None, ""):
        return None
    return frappe.utils.cint(value)
