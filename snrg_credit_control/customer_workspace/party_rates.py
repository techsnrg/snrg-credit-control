"""Rates recorded in Teamspace and rates on submitted ERPNext quotations."""
from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint

from snrg_credit_control.customer_workspace.api import INTERACTION, guard, party_values
from snrg_credit_control.customer_workspace.settings import allowed

RATE = "custom_teamspace_rate_amount"
CURRENCY = "custom_teamspace_rate_currency"
ITEM = "custom_teamspace_rate_item"
UNIT = "custom_teamspace_rate_unit"
QUOTATIONS = {
    "Customer": ("Quotation", "party_name"),
    "Supplier": ("Supplier Quotation", "supplier"),
}


def install_fields():
    create_custom_fields({INTERACTION: [
        dict(fieldname=ITEM, label="Rate for", fieldtype="Data", insert_after="summary", read_only=1),
        dict(fieldname=UNIT, label="Rate unit", fieldtype="Data", insert_after=ITEM, read_only=1),
        dict(fieldname=CURRENCY, label="Rate currency", fieldtype="Link", options="Currency", insert_after=UNIT, read_only=1),
        dict(fieldname=RATE, label="Rate amount", fieldtype="Currency", options=CURRENCY, insert_after=CURRENCY, read_only=1),
    ]})


def interaction_values(rate):
    if rate in (None, ""):
        return {}
    if not isinstance(rate, dict):
        frappe.throw(_("Enter valid rate details."))
    try:
        amount = Decimal(str(rate.get("amount", "")))
    except (InvalidOperation, ValueError):
        frappe.throw(_("Enter a valid rate amount."))
    if not amount.is_finite() or not 0 <= amount < 10**12 or amount.as_tuple().exponent < -6:
        frappe.throw(_("Enter a non-negative rate with up to six decimal places."))
    item = str(rate.get("item") or "").strip()
    unit = str(rate.get("unit") or "").strip()
    currency = str(rate.get("currency") or "").strip().upper()
    if not item or not unit or len(item) > 140 or len(unit) > 140:
        frappe.throw(_("Enter an item or description and a unit, each up to 140 characters."))
    if len(currency) != 3 or not frappe.db.exists("Currency", currency):
        frappe.throw(_("Enter a valid three-letter currency code."))
    return {ITEM: item, UNIT: unit, CURRENCY: currency, RATE: amount}


@frappe.whitelist(methods=["GET"])
def list_rates(customer=None, supplier=None, source="interaction", start=0):
    guard()
    party_values(customer, supplier)
    kind, name = ("Supplier", supplier) if supplier else ("Customer", customer)
    doctype, party_field = QUOTATIONS[kind]
    can_quote = bool(allowed("Transactions") and frappe.has_permission(doctype, "read"))
    start = max(0, cint(start))
    if source == "interaction":
        rows = frappe.get_all(
            INTERACTION, filters={kind.lower(): name, CURRENCY: ["!=", ""]},
            fields=["name", "channel", "interaction_on as date", "spoken_by",
                    f"{ITEM} as item", f"{UNIT} as unit", f"{CURRENCY} as currency", f"{RATE} as rate"],
            order_by="interaction_on desc, name desc", start=start, limit_page_length=26,
        )
        return {"rows": rows[:25], "has_more": len(rows) > 25, "can_quote": can_quote}
    if source != "quotation":
        frappe.throw(_("Choose a valid rate source."))
    if not can_quote:
        frappe.throw(_("You do not have access to these quotations."), frappe.PermissionError)

    filters = {party_field: name, "docstatus": 1}
    if kind == "Customer":
        filters["quotation_to"] = "Customer"
    parents = frappe.get_list(
        doctype, filters=filters, fields=["name"], order_by="transaction_date desc, name desc",
        start=start, limit_page_length=11,
    )
    rows = []
    for parent in parents[:10]:
        doc = frappe.get_doc(doctype, parent.name)
        if not doc.has_permission("read"):
            continue
        doc.apply_fieldlevel_read_permissions()
        for item in doc.get("items") or []:
            if item.rate is None:
                continue
            rows.append({
                "name": item.name, "quotation": doc.name, "date": doc.transaction_date,
                "item_code": item.item_code, "item": item.item_name, "unit": item.uom,
                "qty": item.qty, "currency": doc.currency, "rate": item.rate,
            })
    return {"rows": rows, "has_more": len(parents) > 10, "can_quote": can_quote}
