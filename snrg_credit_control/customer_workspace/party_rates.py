"""Rates recorded in Teamspace and rates on submitted ERPNext quotations."""
from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint
from pypika import Order

from snrg_credit_control.customer_workspace.api import INTERACTION, guard, party_values
from snrg_credit_control.customer_workspace.settings import allowed

RATE = "custom_teamspace_rate_amount"
CURRENCY = "custom_teamspace_rate_currency"
ITEM = "custom_teamspace_rate_item"
UNIT = "custom_teamspace_rate_unit"
RATE_TABLE = "custom_teamspace_rates"
RATE_ROW = "Customer Interaction Rate"
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
        dict(fieldname=RATE_TABLE, label="Rates", fieldtype="Table", options=RATE_ROW, insert_after=RATE, read_only=1),
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
    unit = str(rate.get("unit", "Nos") or "").strip()
    currency = str(rate.get("currency") or "").strip().upper()
    if not item or not unit or len(item) > 140 or len(unit) > 140:
        frappe.throw(_("Enter an item or description and a unit, each up to 140 characters."))
    if len(currency) != 3 or not frappe.db.exists("Currency", currency):
        frappe.throw(_("Enter a valid three-letter currency code."))
    return {ITEM: item, UNIT: unit, CURRENCY: currency, RATE: amount}


def interaction_rows(rows, legacy_rate=None):
    if rows is None:
        rows = [legacy_rate] if legacy_rate else []
    if not isinstance(rows, list) or len(rows) > 100:
        frappe.throw(_("Enter up to 100 rate rows per interaction."))
    result = []
    for row in rows:
        values = interaction_values(row)
        if not values:
            frappe.throw(_("Complete each rate row or remove it."))
        result.append({
            "item": values[ITEM], "uom": values[UNIT],
            "currency": values[CURRENCY], "rate": values[RATE],
        })
    return result


def _logged_rates(kind, name, start):
    parent = frappe.qb.DocType(INTERACTION)
    child = frappe.qb.DocType(RATE_ROW)
    linked = frappe.qb.from_(child).select(child.parent).where(
        (child.parenttype == INTERACTION) & (child.parentfield == RATE_TABLE)
    )
    parents = (
        frappe.qb.from_(parent)
        .select(parent.name, parent.channel, parent.interaction_on.as_("date"), parent.spoken_by,
                parent[ITEM].as_("item"), parent[UNIT].as_("unit"), parent[CURRENCY].as_("currency"), parent[RATE].as_("rate"))
        .where((parent[kind.lower()] == name) & ((parent[CURRENCY] != "") | parent.name.isin(linked)))
        .orderby(parent.interaction_on, parent.name, order=Order.desc).offset(start).limit(26)
        .run(as_dict=True)
    )
    if not parents:
        return [], False
    rate_rows = frappe.get_all(RATE_ROW, filters={
        "parent": ["in", [row.name for row in parents[:25]]],
        "parenttype": INTERACTION, "parentfield": RATE_TABLE,
    }, fields=["parent", "name", "item", "uom as unit", "currency", "rate"],
        order_by="idx asc", limit_page_length=0)
    by_parent = {}
    for row in rate_rows:
        by_parent.setdefault(row.parent, []).append(row)
    rows = []
    for parent_row in parents[:25]:
        if parent_row.currency:
            rows.append(parent_row)
        rows.extend({**parent_row, **line} for line in by_parent.get(parent_row.name, []))
    return rows, len(parents) > 25


@frappe.whitelist(methods=["GET"])
def list_rates(customer=None, supplier=None, source="interaction", start=0):
    guard()
    party_values(customer, supplier)
    kind, name = ("Supplier", supplier) if supplier else ("Customer", customer)
    doctype, party_field = QUOTATIONS[kind]
    can_quote = bool(allowed("Transactions") and frappe.has_permission(doctype, "read"))
    start = max(0, cint(start))
    if source == "interaction":
        rows, has_more = _logged_rates(kind, name, start)
        return {"rows": rows, "has_more": has_more, "can_quote": can_quote}
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
