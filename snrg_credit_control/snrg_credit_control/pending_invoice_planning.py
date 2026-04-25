from __future__ import annotations

import json
from collections import defaultdict

import frappe
from frappe.utils import cint, flt, getdate

QTY_EPSILON = 0.0001
VALUE_EPSILON = 0.01


def get_pending_invoice_planning_rows(filters=None, quotation_id=None, include_cancelled=False, pending_only=True):
    filters = frappe._dict(filters or {})
    quotations = _get_quotations(filters, quotation_id=quotation_id, include_cancelled=include_cancelled)
    if not quotations:
        return []

    quotation_names = [row.name for row in quotations]
    quotation_items = _get_quotation_items(quotation_names, item_code=filters.get("item_code"))
    if not quotation_items:
        return []

    grouped_rows, quotation_lookups = _build_group_rows(quotations, quotation_items)
    sales_order_items = _get_sales_order_items(quotation_names)
    sales_order_item_to_group, invoice_candidate_maps = _apply_sales_order_items(
        grouped_rows,
        quotation_lookups,
        sales_order_items,
    )

    submitted_sales_orders = sorted(invoice_candidate_maps["submitted_sales_orders"])
    if submitted_sales_orders:
        invoice_items = _get_invoice_items(submitted_sales_orders)
        _apply_invoice_items(
            grouped_rows,
            sales_order_item_to_group,
            invoice_candidate_maps,
            invoice_items,
        )

    rows = _finalize_group_rows(grouped_rows)

    sales_order_statuses = set(_normalize_multiselect(filters.get("sales_order_status")))
    if sales_order_statuses:
        rows = [row for row in rows if row["sales_order_status"] in sales_order_statuses]

    if pending_only:
        rows = [row for row in rows if _is_pending_row(row)]

    rows.sort(
        key=lambda row: (
            -_sortable_date(row.get("quotation_date")).toordinal(),
            row.get("quotation", ""),
            cint(row.get("_sort_index")),
            row.get("item_code", ""),
            row.get("item_name", ""),
        )
    )

    for row in rows:
        row.pop("_sort_index", None)

    return rows


def get_sales_order_item_quotation_link_config():
    meta = frappe.get_meta("Sales Order Item")
    quotation_fieldname = None
    for candidate in ("prevdoc_docname", "quotation"):
        if meta.has_field(candidate):
            quotation_fieldname = candidate
            break

    if not quotation_fieldname:
        return None, None, False

    detail_fieldname = None
    for candidate in ("prevdoc_detail_docname", "quotation_item"):
        if meta.has_field(candidate):
            detail_fieldname = candidate
            break

    return quotation_fieldname, detail_fieldname, meta.has_field("prevdoc_doctype")


def _get_sales_invoice_item_link_config():
    meta = frappe.get_meta("Sales Invoice Item")
    for candidate in ("so_detail", "sales_order_item"):
        if meta.has_field(candidate):
            return candidate
    return None


def _get_quotations(filters, quotation_id=None, include_cancelled=False):
    quotation_statuses = set(_normalize_multiselect(filters.get("quotation_status")))
    docstatus_map = {"Draft": 0, "Submitted": 1, "Cancelled": 2}

    report_filters = {"quotation_to": "Customer"}
    if filters.get("company"):
        report_filters["company"] = filters.get("company")
    if filters.get("customer"):
        report_filters["party_name"] = filters.get("customer")
    if filters.get("territory"):
        report_filters["territory"] = filters.get("territory")
    if quotation_id:
        report_filters["name"] = quotation_id
    elif filters.get("quotation"):
        report_filters["name"] = filters.get("quotation")

    docstatuses = []
    if quotation_statuses:
        docstatuses = sorted({docstatus_map[value] for value in quotation_statuses if value in docstatus_map})
        if not include_cancelled:
            docstatuses = [value for value in docstatuses if value < 2]
        if not docstatuses:
            return []
    elif not include_cancelled:
        docstatuses = [0, 1]

    if docstatuses:
        report_filters["docstatus"] = ["in", docstatuses]

    if filters.get("from_date") and filters.get("to_date"):
        report_filters["transaction_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
    elif filters.get("from_date"):
        report_filters["transaction_date"] = [">=", filters.get("from_date")]
    elif filters.get("to_date"):
        report_filters["transaction_date"] = ["<=", filters.get("to_date")]

    rows = frappe.get_all(
        "Quotation",
        filters=report_filters,
        fields=[
            "name",
            "company",
            "transaction_date",
            "party_name",
            "customer_name",
            "territory",
            "currency",
            "docstatus",
        ],
        order_by="transaction_date desc, modified desc",
    )

    for row in rows:
        row.customer = row.party_name

    return rows


def _get_quotation_items(quotation_names, item_code=None):
    if not quotation_names:
        return []

    filters = {"parent": ["in", quotation_names]}
    if item_code:
        filters["item_code"] = item_code

    return frappe.get_all(
        "Quotation Item",
        filters=filters,
        fields=["name", "parent", "idx", "item_code", "item_name", "qty", "amount"],
        order_by="parent asc, idx asc",
    )


def _build_group_rows(quotations, quotation_items):
    quotation_by_name = {row.name: row for row in quotations}
    grouped_rows = {}
    lookup_by_quote_item = {}
    lookup_by_code = defaultdict(set)
    lookup_by_name = defaultdict(set)

    for row in quotation_items:
        quotation = quotation_by_name.get(row.parent)
        if not quotation:
            continue

        group_key = (row.parent, row.item_code or "", row.item_name or "")
        if group_key not in grouped_rows:
            grouped_rows[group_key] = {
                "quotation": quotation.name,
                "quotation_date": _serialize_date(quotation.transaction_date),
                "customer": quotation.party_name or "",
                "customer_name": quotation.customer_name or quotation.party_name or "",
                "company": quotation.company or "",
                "territory": quotation.territory or "",
                "currency": quotation.currency or "INR",
                "quotation_status": _get_quotation_status_label(quotation.docstatus),
                "item_code": row.item_code or "",
                "item_name": row.item_name or "",
                "quotation_qty": 0,
                "quotation_value": 0,
                "quotation_open_qty": 0,
                "quotation_open_value": 0,
                "draft_so_qty": 0,
                "draft_so_value": 0,
                "submitted_so_qty": 0,
                "submitted_so_value": 0,
                "submitted_so_uninvoiced_qty": 0,
                "submitted_so_uninvoiced_value": 0,
                "invoiced_qty": 0,
                "invoiced_value": 0,
                "total_uninvoiced_qty": 0,
                "total_uninvoiced_value": 0,
                "sales_order_names": set(),
                "sales_order_docstatuses": set(),
                "latest_sales_order": "",
                "latest_sales_order_date": "",
                "latest_invoice_date": "",
                "sales_order_count": 0,
                "planning_stage_summary": "",
                "_sort_index": cint(row.idx),
            }

        group = grouped_rows[group_key]
        group["quotation_qty"] += flt(row.qty)
        group["quotation_value"] += flt(row.amount)

        lookup_by_quote_item[row.name] = group_key
        if row.item_code:
            lookup_by_code[(row.parent, row.item_code)].add(group_key)
        if row.item_name:
            lookup_by_name[(row.parent, row.item_name)].add(group_key)

    return grouped_rows, {
        "by_quote_item": lookup_by_quote_item,
        "by_code": lookup_by_code,
        "by_name": lookup_by_name,
    }


def _get_sales_order_items(quotation_names):
    quotation_fieldname, detail_fieldname, has_prevdoc_doctype = get_sales_order_item_quotation_link_config()
    if not quotation_fieldname or not quotation_names:
        return []

    placeholders = ", ".join(["%s"] * len(quotation_names))
    detail_select = f", soi.{detail_fieldname} AS quotation_item_ref" if detail_fieldname else ", NULL AS quotation_item_ref"
    extra_condition = "AND soi.prevdoc_doctype = 'Quotation'" if has_prevdoc_doctype else ""

    return frappe.db.sql(
        f"""
        SELECT
            soi.name AS sales_order_item,
            soi.parent AS sales_order,
            soi.{quotation_fieldname} AS quotation,
            soi.item_code,
            soi.item_name,
            soi.qty,
            soi.amount,
            so.docstatus,
            so.transaction_date
            {detail_select}
        FROM `tabSales Order Item` soi
        INNER JOIN `tabSales Order` so ON so.name = soi.parent
        WHERE soi.{quotation_fieldname} IN ({placeholders})
          {extra_condition}
          AND so.docstatus < 2
        ORDER BY so.transaction_date DESC, so.name DESC, soi.idx ASC
        """,
        tuple(quotation_names),
        as_dict=True,
    )


def _apply_sales_order_items(grouped_rows, quotation_lookups, sales_order_items):
    sales_order_item_to_group = {}
    invoice_candidate_maps = {
        "submitted_sales_orders": set(),
        "by_code": defaultdict(set),
        "by_name": defaultdict(set),
    }

    for row in sales_order_items:
        group_key = _resolve_sales_order_group_key(row, grouped_rows, quotation_lookups)
        if not group_key:
            continue

        group = grouped_rows[group_key]
        qty = flt(row.qty)
        amount = flt(row.amount)
        docstatus = cint(row.docstatus)

        group["sales_order_names"].add(row.sales_order)
        group["sales_order_docstatuses"].add(docstatus)
        _capture_latest_reference(group, "latest_sales_order", "latest_sales_order_date", row.sales_order, row.transaction_date)

        sales_order_item_to_group[row.sales_order_item] = group_key

        if docstatus == 0:
            group["draft_so_qty"] += qty
            group["draft_so_value"] += amount
            continue

        if docstatus != 1:
            continue

        group["submitted_so_qty"] += qty
        group["submitted_so_value"] += amount
        invoice_candidate_maps["submitted_sales_orders"].add(row.sales_order)
        if row.item_code:
            invoice_candidate_maps["by_code"][(row.sales_order, row.item_code)].add(group_key)
        if row.item_name:
            invoice_candidate_maps["by_name"][(row.sales_order, row.item_name)].add(group_key)

    return sales_order_item_to_group, invoice_candidate_maps


def _resolve_sales_order_group_key(row, grouped_rows, quotation_lookups):
    quotation = row.get("quotation") or ""
    quotation_item_ref = row.get("quotation_item_ref")
    if quotation_item_ref and quotation_item_ref in quotation_lookups["by_quote_item"]:
        return quotation_lookups["by_quote_item"][quotation_item_ref]

    item_code = row.get("item_code") or ""
    item_name = row.get("item_name") or ""

    if item_code:
        candidates = quotation_lookups["by_code"].get((quotation, item_code), set())
        if len(candidates) == 1:
            return next(iter(candidates))

    if item_name:
        candidates = quotation_lookups["by_name"].get((quotation, item_name), set())
        if len(candidates) == 1:
            return next(iter(candidates))

    direct_key = (quotation, item_code, item_name)
    if direct_key in grouped_rows:
        return direct_key

    return None


def _get_invoice_items(sales_order_names):
    if not sales_order_names:
        return []

    so_detail_fieldname = _get_sales_invoice_item_link_config()
    placeholders = ", ".join(["%s"] * len(sales_order_names))
    detail_select = f", sii.{so_detail_fieldname} AS sales_order_item_ref" if so_detail_fieldname else ", NULL AS sales_order_item_ref"

    return frappe.db.sql(
        f"""
        SELECT
            sii.parent AS invoice_name,
            sii.sales_order,
            sii.item_code,
            sii.item_name,
            sii.qty,
            sii.amount,
            si.posting_date
            {detail_select}
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE sii.sales_order IN ({placeholders})
          AND si.docstatus = 1
          AND COALESCE(si.is_return, 0) = 0
        ORDER BY si.posting_date DESC, si.name DESC, sii.idx ASC
        """,
        tuple(sales_order_names),
        as_dict=True,
    )


def _apply_invoice_items(grouped_rows, sales_order_item_to_group, invoice_candidate_maps, invoice_items):
    for row in invoice_items:
        allocations = _resolve_invoice_allocations(
            row,
            grouped_rows,
            sales_order_item_to_group,
            invoice_candidate_maps,
        )
        if not allocations:
            continue

        qty = flt(row.qty)
        amount = flt(row.amount)
        qty_weights = _get_allocation_weights(grouped_rows, allocations, "submitted_so_qty", "invoiced_qty")
        value_weights = _get_allocation_weights(grouped_rows, allocations, "submitted_so_value", "invoiced_value")
        qty_shares = _allocate_by_weights(qty, qty_weights)
        value_shares = _allocate_by_weights(amount, value_weights)

        for index, group_key in enumerate(allocations):
            group = grouped_rows[group_key]
            group["invoiced_qty"] += qty_shares[index]
            group["invoiced_value"] += value_shares[index]
            _capture_latest_reference(group, None, "latest_invoice_date", row.invoice_name, row.posting_date)


def _resolve_invoice_allocations(row, grouped_rows, sales_order_item_to_group, invoice_candidate_maps):
    sales_order_item_ref = row.get("sales_order_item_ref")
    if sales_order_item_ref and sales_order_item_ref in sales_order_item_to_group:
        return [sales_order_item_to_group[sales_order_item_ref]]

    sales_order = row.get("sales_order") or ""
    item_code = row.get("item_code") or ""
    item_name = row.get("item_name") or ""

    if item_code:
        candidates = invoice_candidate_maps["by_code"].get((sales_order, item_code), set())
        if candidates:
            return sorted(key for key in candidates if key in grouped_rows)

    if item_name:
        candidates = invoice_candidate_maps["by_name"].get((sales_order, item_name), set())
        if candidates:
            return sorted(key for key in candidates if key in grouped_rows)

    return []


def _get_allocation_weights(grouped_rows, allocations, total_key, used_key):
    weights = []
    for group_key in allocations:
        group = grouped_rows[group_key]
        remaining = max(flt(group.get(total_key)) - flt(group.get(used_key)), 0)
        weights.append(remaining)

    if any(weight > 0 for weight in weights):
        return weights

    fallback_weights = [flt(grouped_rows[group_key].get(total_key)) for group_key in allocations]
    if any(weight > 0 for weight in fallback_weights):
        return fallback_weights

    return [1] * len(allocations)


def _allocate_by_weights(total, weights):
    if not weights:
        return []

    total = flt(total)
    denominator = sum(flt(weight) for weight in weights)
    if denominator <= 0:
        equal_share = total / len(weights) if weights else 0
        return [equal_share] * len(weights)

    allocated = []
    remainder = total
    for index, weight in enumerate(weights):
        if index == len(weights) - 1:
            share = remainder
        else:
            share = total * flt(weight) / denominator
            remainder -= share
        allocated.append(share)

    return allocated


def _finalize_group_rows(grouped_rows):
    rows = []
    for group in grouped_rows.values():
        quotation_open_qty = max(flt(group["quotation_qty"]) - flt(group["draft_so_qty"]) - flt(group["submitted_so_qty"]), 0)
        quotation_open_value = max(
            flt(group["quotation_value"]) - flt(group["draft_so_value"]) - flt(group["submitted_so_value"]),
            0,
        )
        submitted_so_uninvoiced_qty = max(flt(group["submitted_so_qty"]) - flt(group["invoiced_qty"]), 0)
        submitted_so_uninvoiced_value = max(flt(group["submitted_so_value"]) - flt(group["invoiced_value"]), 0)
        total_uninvoiced_qty = quotation_open_qty + flt(group["draft_so_qty"]) + submitted_so_uninvoiced_qty
        total_uninvoiced_value = quotation_open_value + flt(group["draft_so_value"]) + submitted_so_uninvoiced_value

        sales_order_status = _derive_sales_order_status(group["sales_order_docstatuses"])
        row = {
            "quotation": group["quotation"],
            "quotation_date": group["quotation_date"],
            "customer": group["customer"],
            "customer_name": group["customer_name"],
            "company": group["company"],
            "territory": group["territory"],
            "currency": group["currency"],
            "quotation_status": group["quotation_status"],
            "item_code": group["item_code"],
            "item_name": group["item_name"],
            "quotation_qty": flt(group["quotation_qty"]),
            "quotation_value": flt(group["quotation_value"]),
            "quotation_open_qty": quotation_open_qty,
            "quotation_open_value": quotation_open_value,
            "draft_so_qty": flt(group["draft_so_qty"]),
            "draft_so_value": flt(group["draft_so_value"]),
            "submitted_so_qty": flt(group["submitted_so_qty"]),
            "submitted_so_value": flt(group["submitted_so_value"]),
            "submitted_so_uninvoiced_qty": submitted_so_uninvoiced_qty,
            "submitted_so_uninvoiced_value": submitted_so_uninvoiced_value,
            "invoiced_qty": flt(group["invoiced_qty"]),
            "invoiced_value": flt(group["invoiced_value"]),
            "total_uninvoiced_qty": total_uninvoiced_qty,
            "total_uninvoiced_value": total_uninvoiced_value,
            "sales_order_status": sales_order_status,
            "sales_order_count": len(group["sales_order_names"]),
            "latest_sales_order": group["latest_sales_order"],
            "latest_invoice_date": group["latest_invoice_date"],
            "planning_stage_summary": _build_planning_stage_summary(
                quotation_open_qty=quotation_open_qty,
                draft_so_qty=flt(group["draft_so_qty"]),
                submitted_so_uninvoiced_qty=submitted_so_uninvoiced_qty,
                invoiced_qty=flt(group["invoiced_qty"]),
            ),
            "_sort_index": group["_sort_index"],
        }
        rows.append(row)

    return rows


def _derive_sales_order_status(docstatuses):
    normalized = {cint(value) for value in docstatuses if value in (0, 1)}
    if not normalized:
        return "No SO"
    if normalized == {0}:
        return "Draft SO"
    if normalized == {1}:
        return "Submitted SO"
    return "Mixed SO"


def _build_planning_stage_summary(quotation_open_qty, draft_so_qty, submitted_so_uninvoiced_qty, invoiced_qty):
    stages = []
    if quotation_open_qty > QTY_EPSILON:
        stages.append("Quotation Open")
    if draft_so_qty > QTY_EPSILON:
        stages.append("Draft SO")
    if submitted_so_uninvoiced_qty > QTY_EPSILON:
        if invoiced_qty > QTY_EPSILON:
            stages.append("Partially Invoiced SO")
        else:
            stages.append("Submitted SO Awaiting Invoice")

    if stages:
        return " + ".join(stages)

    if invoiced_qty > QTY_EPSILON:
        return "Fully Invoiced"

    return "No Activity"


def _capture_latest_reference(group, name_field, date_field, docname, date_value):
    if not date_field or not date_value:
        return

    current_sort = _sortable_date(group.get(date_field))
    candidate_sort = _sortable_date(date_value)
    if candidate_sort < current_sort:
        return
    if candidate_sort == current_sort and name_field and docname and (group.get(name_field) or "") >= docname:
        return

    group[date_field] = _serialize_date(date_value)
    if name_field:
        group[name_field] = docname or ""


def _is_pending_row(row):
    return (
        abs(flt(row.get("total_uninvoiced_qty"))) > QTY_EPSILON
        or abs(flt(row.get("total_uninvoiced_value"))) > VALUE_EPSILON
    )


def _normalize_multiselect(value):
    if not value:
        return []
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except Exception:
            parsed = [entry.strip() for entry in value.split(",") if entry.strip()]
        else:
            value = parsed
    if isinstance(value, (list, tuple, set)):
        return [str(entry).strip() for entry in value if str(entry).strip()]
    return [str(value).strip()]


def _get_quotation_status_label(docstatus):
    if cint(docstatus) == 0:
        return "Draft"
    if cint(docstatus) == 1:
        return "Submitted"
    if cint(docstatus) == 2:
        return "Cancelled"
    return ""


def _serialize_date(value):
    if not value:
        return ""
    return str(value)


def _sortable_date(value):
    if not value:
        return getdate("1900-01-01")
    return getdate(value)
