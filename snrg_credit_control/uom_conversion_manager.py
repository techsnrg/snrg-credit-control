from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, flt


SORT_FIELDS = {
    "item_code": "i.name",
    "item_name": "i.item_name",
    "item_group": "i.item_group",
    "stock_uom": "i.stock_uom",
    "modified": "i.modified",
}


def _as_list(value):
    if not value:
        return []
    if isinstance(value, str):
        return json.loads(value)
    return value


def _require_item_read():
    if not frappe.has_permission("Item", "read"):
        frappe.throw(_("Not permitted to read Item records."), frappe.PermissionError)


def _require_item_write():
    if not frappe.has_permission("Item", "write"):
        frappe.throw(_("Not permitted to update Item UOM conversion factors."), frappe.PermissionError)


def _validate_item(item_code):
    if not item_code:
        frappe.throw(_("Item Code is required."))
    if not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item {0} does not exist.").format(frappe.bold(item_code)))


def _validate_uom(uom):
    if not uom:
        frappe.throw(_("UOM is required."))
    if not frappe.db.exists("UOM", uom):
        frappe.throw(_("UOM {0} does not exist.").format(frappe.bold(uom)))


def _validate_conversion_factor(conversion_factor):
    conversion_factor = flt(conversion_factor)
    if conversion_factor <= 0:
        frappe.throw(_("Conversion Factor must be greater than zero."))
    return conversion_factor


@frappe.whitelist()
def get_items(
    item_group=None,
    item_code=None,
    item_name=None,
    sort_by="item_code",
    sort_order="asc",
    limit_start=0,
    limit_page_length=50,
):
    _require_item_read()

    sort_column = SORT_FIELDS.get(sort_by) or SORT_FIELDS["item_code"]
    sort_direction = "DESC" if str(sort_order).lower() == "desc" else "ASC"
    conditions = []
    values = {
        "limit_start": cint(limit_start),
        "limit_page_length": min(cint(limit_page_length) or 50, 200),
    }

    if item_group:
        conditions.append("i.item_group = %(item_group)s")
        values["item_group"] = item_group
    if item_code:
        conditions.append("i.name = %(item_code)s")
        values["item_code"] = item_code
    if item_name:
        conditions.append("i.item_name LIKE %(item_name)s")
        values["item_name"] = f"%{item_name}%"

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    items = frappe.db.sql(
        """
        SELECT
            i.name AS item_code,
            i.item_name,
            i.item_group,
            i.stock_uom,
            i.disabled,
            i.modified
        FROM `tabItem` i
        {where_clause}
        ORDER BY {sort_column} {sort_direction}, i.name ASC
        LIMIT %(limit_start)s, %(limit_page_length)s
        """.format(
            where_clause=where_clause,
            sort_column=sort_column,
            sort_direction=sort_direction,
        ),
        values,
        as_dict=True,
    )

    total = frappe.db.sql(
        """
        SELECT COUNT(*)
        FROM `tabItem` i
        {where_clause}
        """.format(where_clause=where_clause),
        values,
    )[0][0]

    if not items:
        return {"rows": [], "total": total}

    item_codes = tuple(item.item_code for item in items)
    uom_rows = frappe.db.sql(
        """
        SELECT
            name,
            parent AS item_code,
            uom,
            conversion_factor,
            idx
        FROM `tabUOM Conversion Detail`
        WHERE parenttype = 'Item'
          AND parentfield = 'uoms'
          AND parent IN %(item_codes)s
        ORDER BY parent ASC, idx ASC
        """,
        {"item_codes": item_codes},
        as_dict=True,
    )

    by_item = {}
    for row in uom_rows:
        by_item.setdefault(row.item_code, []).append(row)

    for item in items:
        item["uoms"] = by_item.get(item.item_code, [])

    return {"rows": items, "total": total}


@frappe.whitelist()
def save_conversion_factors(changes):
    _require_item_write()
    changes = _as_list(changes)
    if not changes:
        frappe.throw(_("No conversion factor changes found."))

    grouped_changes = {}
    for change in changes:
        item_code = change.get("item_code")
        uom = change.get("uom")
        conversion_factor = _validate_conversion_factor(change.get("conversion_factor"))
        _validate_item(item_code)
        _validate_uom(uom)
        grouped_changes.setdefault(item_code, {})[uom] = conversion_factor

    updated = []
    failed = []

    for item_code, item_changes in grouped_changes.items():
        try:
            doc = frappe.get_doc("Item", item_code)
            existing_by_uom = {row.uom: row for row in doc.get("uoms", [])}

            for uom, conversion_factor in item_changes.items():
                if doc.stock_uom == uom and conversion_factor != 1:
                    frappe.throw(_("Stock UOM conversion factor must be 1 for item {0}.").format(frappe.bold(item_code)))

                if uom in existing_by_uom:
                    existing_by_uom[uom].conversion_factor = conversion_factor
                else:
                    doc.append("uoms", {"uom": uom, "conversion_factor": conversion_factor})

            doc.save()
            updated.append(item_code)
        except Exception as exc:
            failed.append({"item_code": item_code, "reason": str(exc)})

    if updated:
        frappe.db.commit()

    return {"updated": updated, "failed": failed}
