from __future__ import annotations

import json
from collections import defaultdict

import frappe
from frappe.utils import cint, flt, getdate

QTY_EPSILON = 0.0001
VALUE_EPSILON = 0.01


@frappe.whitelist()
def create_production_requests_from_pending_rows(rows):
    from snrg_credit_control.snrg_credit_control.doctype.production_request.production_request import (
        create_from_pending_rows,
    )

    return create_from_pending_rows(rows)


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

    invoice_items = _get_invoice_items(
        sales_order_names=sorted(invoice_candidate_maps["submitted_sales_orders"]),
        quotation_names=quotation_names,
    )
    if invoice_items:
        _apply_invoice_items(
            grouped_rows,
            quotation_lookups,
            sales_order_item_to_group,
            invoice_candidate_maps,
            invoice_items,
        )

    rows = _finalize_group_rows(grouped_rows)
    _attach_production_request_state(rows)

    production_statuses = set(_normalize_multiselect(filters.get("production_status")))
    if production_statuses:
        rows = [row for row in rows if (row.get("production_request_status") or "Not Requested") in production_statuses]

    required_by_from, required_by_to = _extract_date_bounds(
        frappe._dict(
            {
                "from_date": filters.get("required_by_from_date"),
                "to_date": filters.get("required_by_to_date"),
                "date_range": filters.get("required_by_date_range"),
            }
        )
    )
    if required_by_from or required_by_to:
        rows = [
            row for row in rows
            if _matches_required_by_date_range(row.get("production_required_by_date"), required_by_from, required_by_to)
        ]

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


def _attach_production_request_state(rows):
    if not rows:
        return

    source_keys = {
        _build_pending_invoice_source_key(row.get("quotation"), row.get("item_code"))
        for row in rows
        if row.get("quotation") and row.get("item_code")
    }
    source_keys.discard("")

    if not source_keys:
        return

    request_rows = _get_production_requests_for_source_keys(sorted(source_keys))
    requests_by_source_key = defaultdict(list)
    user_ids = set()

    for request in request_rows:
        source_key = (request.get("source_key") or "").strip().lower()
        if not source_key:
            continue

        requests_by_source_key[source_key].append(request)
        if request.get("assigned_to"):
            user_ids.add(request.get("assigned_to"))

    user_name_map = _get_pending_invoice_user_name_map(user_ids)

    for row in rows:
        source_key = _build_pending_invoice_source_key(row.get("quotation"), row.get("item_code"))
        request_list = requests_by_source_key.get(source_key, [])
        display_request = _get_pending_invoice_display_request(request_list)
        production_status = _get_pending_invoice_production_status(request_list)
        requested_qty = sum(
            flt(request.get("requested_qty"))
            for request in request_list
            if request.get("status") in ("Open", "In Progress", "Completed")
        )
        active_requested_qty = sum(
            flt(request.get("requested_qty"))
            for request in request_list
            if request.get("status") in ("Open", "In Progress")
        )
        remaining_requestable_qty = max(flt(row.get("total_uninvoiced_qty")) - requested_qty, 0)

        row["has_active_production_request"] = active_requested_qty > QTY_EPSILON
        row["production_request_name"] = display_request.get("name") if display_request else ""
        row["production_request_status"] = production_status
        row["production_required_by_date"] = (
            str(display_request.get("required_by_date") or "") if display_request else ""
        )
        row["production_requested_qty"] = requested_qty
        row["production_active_requested_qty"] = active_requested_qty
        row["remaining_requestable_qty"] = remaining_requestable_qty
        row["production_assigned_to"] = display_request.get("assigned_to") if display_request else ""
        row["production_assigned_to_name"] = (
            user_name_map.get(display_request.get("assigned_to")) or display_request.get("assigned_to") or ""
        ) if display_request else ""


def _get_production_requests_for_source_keys(source_keys):
    if not source_keys:
        return []

    placeholders = ", ".join(["%s"] * len(source_keys))
    return frappe.db.sql(
        f"""
        SELECT
            name,
            source_key,
            status,
            requested_qty,
            required_by_date,
            assigned_to,
            modified,
            creation
        FROM `tabProduction Request`
        WHERE source_key IN ({placeholders})
        ORDER BY modified DESC, creation DESC, name DESC
        """,
        tuple(source_keys),
        as_dict=True,
    )


def _get_pending_invoice_user_name_map(user_ids):
    user_ids = [user_id for user_id in user_ids if user_id]
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


def _get_pending_invoice_display_request(request_list):
    if not request_list:
        return None

    active_requests = [request for request in request_list if request.get("status") in ("Open", "In Progress")]
    if active_requests:
        return sorted(
            active_requests,
            key=lambda request: (
                1 if not request.get("required_by_date") else 0,
                str(request.get("required_by_date") or ""),
                str(request.get("modified") or ""),
                str(request.get("name") or ""),
            ),
        )[0]

    non_cancelled_requests = [request for request in request_list if request.get("status") != "Cancelled"]
    if non_cancelled_requests:
        return non_cancelled_requests[0]

    return request_list[0]


def _get_pending_invoice_production_status(request_list):
    statuses = {request.get("status") for request in request_list if request.get("status")}
    if "In Progress" in statuses:
        return "In Progress"
    if "Open" in statuses:
        return "Open"
    if "Completed" in statuses:
        return "Completed"
    if "Cancelled" in statuses:
        return "Cancelled"
    return "Not Requested"


def get_pending_invoice_planning_item_summary_rows(filters=None):
    detail_rows = get_pending_invoice_planning_rows(filters=filters, pending_only=True)
    grouped = {}

    for row in detail_rows:
        key = (row.get("item_code") or "", row.get("item_name") or "", row.get("currency") or "")
        if key not in grouped:
            grouped[key] = {
                "item_code": row.get("item_code") or "",
                "item_name": row.get("item_name") or "",
                "currency": row.get("currency") or "INR",
                "quotation_count": 0,
                "customer_count": 0,
                "sales_order_count": 0,
                "latest_quotation_date": "",
                "latest_sales_order": "",
                "latest_sales_order_date": "",
                "latest_invoice_date": "",
                "quotation_qty": 0,
                "quotation_value": 0,
                "quotation_open_qty": 0,
                "quotation_open_value": 0,
                "draft_so_qty": 0,
                "draft_so_value": 0,
                "submitted_so_uninvoiced_qty": 0,
                "submitted_so_uninvoiced_value": 0,
                "invoiced_qty": 0,
                "invoiced_value": 0,
                "total_uninvoiced_qty": 0,
                "total_uninvoiced_value": 0,
                "_quotation_names": set(),
                "_customer_names": set(),
                "_sales_order_names": set(),
            }

        group = grouped[key]
        _sum_planning_fields(group, row)
        group["_quotation_names"].add(row.get("quotation") or "")
        group["_customer_names"].add(row.get("customer") or "")
        group["_sales_order_names"].update(row.get("sales_order_names") or [])
        _capture_latest_reference(group, "latest_sales_order", "latest_sales_order_date", row.get("latest_sales_order"), row.get("latest_sales_order_date"))
        _capture_latest_reference(group, None, "latest_quotation_date", row.get("quotation"), row.get("quotation_date"))
        _capture_latest_reference(group, None, "latest_invoice_date", None, row.get("latest_invoice_date"))

    rows = []
    for group in grouped.values():
        group["quotation_count"] = len([value for value in group.pop("_quotation_names") if value])
        group["customer_count"] = len([value for value in group.pop("_customer_names") if value])
        group["sales_order_count"] = len([value for value in group.pop("_sales_order_names") if value])
        group.pop("latest_sales_order_date", None)
        rows.append(group)

    rows.sort(
        key=lambda row: (
            -flt(row.get("total_uninvoiced_value")),
            row.get("item_code", ""),
            row.get("item_name", ""),
        )
    )
    return rows


def get_pending_invoice_planning_customer_summary_rows(filters=None):
    detail_rows = get_pending_invoice_planning_rows(filters=filters, pending_only=True)
    grouped = {}

    for row in detail_rows:
        key = (row.get("customer") or "", row.get("customer_name") or "", row.get("currency") or "")
        if key not in grouped:
            grouped[key] = {
                "customer": row.get("customer") or "",
                "customer_name": row.get("customer_name") or "",
                "company": row.get("company") or "",
                "currency": row.get("currency") or "INR",
                "quotation_count": 0,
                "item_count": 0,
                "sales_order_count": 0,
                "latest_quotation_date": "",
                "latest_sales_order": "",
                "latest_sales_order_date": "",
                "latest_invoice_date": "",
                "quotation_value": 0,
                "quotation_open_value": 0,
                "draft_so_value": 0,
                "submitted_so_uninvoiced_value": 0,
                "invoiced_value": 0,
                "total_uninvoiced_value": 0,
                "planning_stage_summary": "",
                "_quotation_names": set(),
                "_item_keys": set(),
                "_sales_order_names": set(),
            }

        group = grouped[key]
        group["quotation_value"] += flt(row.get("quotation_value"))
        group["quotation_open_value"] += flt(row.get("quotation_open_value"))
        group["draft_so_value"] += flt(row.get("draft_so_value"))
        group["submitted_so_uninvoiced_value"] += flt(row.get("submitted_so_uninvoiced_value"))
        group["invoiced_value"] += flt(row.get("invoiced_value"))
        group["total_uninvoiced_value"] += flt(row.get("total_uninvoiced_value"))
        group["_quotation_names"].add(row.get("quotation") or "")
        group["_item_keys"].add((row.get("item_code") or "", row.get("item_name") or ""))
        group["_sales_order_names"].update(row.get("sales_order_names") or [])
        _capture_latest_reference(group, "latest_sales_order", "latest_sales_order_date", row.get("latest_sales_order"), row.get("latest_sales_order_date"))
        _capture_latest_reference(group, None, "latest_quotation_date", row.get("quotation"), row.get("quotation_date"))
        _capture_latest_reference(group, None, "latest_invoice_date", None, row.get("latest_invoice_date"))

    rows = []
    for group in grouped.values():
        group["quotation_count"] = len([value for value in group.pop("_quotation_names") if value])
        group["item_count"] = len([value for value in group.pop("_item_keys") if any(value)])
        group["sales_order_count"] = len([value for value in group.pop("_sales_order_names") if value])
        group["planning_stage_summary"] = _build_value_stage_summary(
            quotation_open_value=flt(group.get("quotation_open_value")),
            draft_so_value=flt(group.get("draft_so_value")),
            submitted_so_uninvoiced_value=flt(group.get("submitted_so_uninvoiced_value")),
            invoiced_value=flt(group.get("invoiced_value")),
        )
        group.pop("latest_sales_order_date", None)
        rows.append(group)

    rows.sort(
        key=lambda row: (
            -flt(row.get("total_uninvoiced_value")),
            row.get("customer_name", ""),
            row.get("customer", ""),
        )
    )
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
    return {
        "sales_order_fieldname": "sales_order" if meta.has_field("sales_order") else None,
        "sales_order_item_fieldname": next(
            (candidate for candidate in ("so_detail", "sales_order_item") if meta.has_field(candidate)),
            None,
        ),
        "quotation_fieldname": "quotation" if meta.has_field("quotation") else None,
        "quotation_item_fieldname": "quotation_item" if meta.has_field("quotation_item") else None,
        "prevdoc_fieldname": "prevdoc_docname" if meta.has_field("prevdoc_docname") else None,
        "prevdoc_detail_fieldname": "prevdoc_detail_docname" if meta.has_field("prevdoc_detail_docname") else None,
        "has_prevdoc_doctype": meta.has_field("prevdoc_doctype"),
    }


def _get_quotations(filters, quotation_id=None, include_cancelled=False):
    quotation_statuses = set(_normalize_multiselect(filters.get("quotation_status")))
    docstatus_map = {"Draft": 0, "Submitted": 1, "Cancelled": 2}
    from_date, to_date = _extract_date_bounds(filters)

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

    if from_date and to_date:
        report_filters["transaction_date"] = ["between", [from_date, to_date]]
    elif from_date:
        report_filters["transaction_date"] = [">=", from_date]
    elif to_date:
        report_filters["transaction_date"] = ["<=", to_date]

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
                "submitted_so_invoiced_qty": 0,
                "submitted_so_invoiced_value": 0,
                "direct_quote_invoiced_qty": 0,
                "direct_quote_invoiced_value": 0,
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


def _get_invoice_items(sales_order_names=None, quotation_names=None):
    sales_order_names = sales_order_names or []
    quotation_names = quotation_names or []
    if not sales_order_names and not quotation_names:
        return []

    link_config = _get_sales_invoice_item_link_config()
    source_conditions = []
    values = []

    sales_order_condition, sales_order_values = _build_invoice_source_condition(
        values=sales_order_names,
        direct_fieldname=link_config["sales_order_fieldname"],
        prevdoc_fieldname=link_config["prevdoc_fieldname"],
        has_prevdoc_doctype=link_config["has_prevdoc_doctype"],
        target_doctype="Sales Order",
    )
    if sales_order_condition:
        source_conditions.append(sales_order_condition)
        values.extend(sales_order_values)

    quotation_condition, quotation_values = _build_invoice_source_condition(
        values=quotation_names,
        direct_fieldname=link_config["quotation_fieldname"],
        prevdoc_fieldname=link_config["prevdoc_fieldname"],
        has_prevdoc_doctype=link_config["has_prevdoc_doctype"],
        target_doctype="Quotation",
    )
    if quotation_condition:
        source_conditions.append(quotation_condition)
        values.extend(quotation_values)

    if not source_conditions:
        return []

    sales_order_select = _build_invoice_source_select(
        direct_fieldname=link_config["sales_order_fieldname"],
        prevdoc_fieldname=link_config["prevdoc_fieldname"],
        has_prevdoc_doctype=link_config["has_prevdoc_doctype"],
        target_doctype="Sales Order",
        alias="sales_order",
    )
    sales_order_item_select = _build_invoice_source_select(
        direct_fieldname=link_config["sales_order_item_fieldname"],
        prevdoc_fieldname=link_config["prevdoc_detail_fieldname"],
        has_prevdoc_doctype=link_config["has_prevdoc_doctype"],
        target_doctype="Sales Order",
        alias="sales_order_item_ref",
    )
    quotation_select = _build_invoice_source_select(
        direct_fieldname=link_config["quotation_fieldname"],
        prevdoc_fieldname=link_config["prevdoc_fieldname"],
        has_prevdoc_doctype=link_config["has_prevdoc_doctype"],
        target_doctype="Quotation",
        alias="quotation",
    )
    quotation_item_select = _build_invoice_source_select(
        direct_fieldname=link_config["quotation_item_fieldname"],
        prevdoc_fieldname=link_config["prevdoc_detail_fieldname"],
        has_prevdoc_doctype=link_config["has_prevdoc_doctype"],
        target_doctype="Quotation",
        alias="quotation_item_ref",
    )

    return frappe.db.sql(
        f"""
        SELECT
            sii.parent AS invoice_name,
            {sales_order_select},
            {quotation_select},
            sii.item_code,
            sii.item_name,
            sii.qty,
            sii.amount,
            si.posting_date
            , {sales_order_item_select}
            , {quotation_item_select}
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE ({' OR '.join(f'({condition})' for condition in source_conditions)})
          AND si.docstatus = 1
          AND COALESCE(si.is_return, 0) = 0
        ORDER BY si.posting_date DESC, si.name DESC, sii.idx ASC
        """,
        tuple(values),
        as_dict=True,
    )


def _apply_invoice_items(grouped_rows, quotation_lookups, sales_order_item_to_group, invoice_candidate_maps, invoice_items):
    for row in invoice_items:
        allocation = _resolve_invoice_allocations(
            row,
            grouped_rows,
            quotation_lookups,
            sales_order_item_to_group,
            invoice_candidate_maps,
        )
        if not allocation:
            continue

        allocations = allocation["group_keys"]
        source = allocation["source"]
        qty = flt(row.qty)
        amount = flt(row.amount)

        if source == "submitted_so":
            qty_weights = _get_allocation_weights(
                grouped_rows,
                allocations,
                "submitted_so_qty",
                "submitted_so_invoiced_qty",
            )
            value_weights = _get_allocation_weights(
                grouped_rows,
                allocations,
                "submitted_so_value",
                "submitted_so_invoiced_value",
            )
        else:
            qty_weights = _get_quote_open_allocation_weights(
                grouped_rows,
                allocations,
                "quotation_qty",
                "draft_so_qty",
                "submitted_so_qty",
                "direct_quote_invoiced_qty",
            )
            value_weights = _get_quote_open_allocation_weights(
                grouped_rows,
                allocations,
                "quotation_value",
                "draft_so_value",
                "submitted_so_value",
                "direct_quote_invoiced_value",
            )

        qty_shares = _allocate_by_weights(qty, qty_weights)
        value_shares = _allocate_by_weights(amount, value_weights)

        for index, group_key in enumerate(allocations):
            group = grouped_rows[group_key]
            if source == "submitted_so":
                group["submitted_so_invoiced_qty"] += qty_shares[index]
                group["submitted_so_invoiced_value"] += value_shares[index]
            else:
                group["direct_quote_invoiced_qty"] += qty_shares[index]
                group["direct_quote_invoiced_value"] += value_shares[index]
            _capture_latest_reference(group, None, "latest_invoice_date", row.invoice_name, row.posting_date)


def _resolve_invoice_allocations(row, grouped_rows, quotation_lookups, sales_order_item_to_group, invoice_candidate_maps):
    sales_order_item_ref = row.get("sales_order_item_ref")
    if sales_order_item_ref and sales_order_item_ref in sales_order_item_to_group:
        return {
            "source": "submitted_so",
            "group_keys": [sales_order_item_to_group[sales_order_item_ref]],
        }

    quotation_item_ref = row.get("quotation_item_ref")
    if quotation_item_ref and quotation_item_ref in quotation_lookups["by_quote_item"]:
        return {
            "source": "direct_quote",
            "group_keys": [quotation_lookups["by_quote_item"][quotation_item_ref]],
        }

    sales_order = row.get("sales_order") or ""
    item_code = row.get("item_code") or ""
    item_name = row.get("item_name") or ""

    if item_code:
        candidates = invoice_candidate_maps["by_code"].get((sales_order, item_code), set())
        if candidates:
            return {
                "source": "submitted_so",
                "group_keys": sorted(key for key in candidates if key in grouped_rows),
            }

    if item_name:
        candidates = invoice_candidate_maps["by_name"].get((sales_order, item_name), set())
        if candidates:
            return {
                "source": "submitted_so",
                "group_keys": sorted(key for key in candidates if key in grouped_rows),
            }

    quotation = row.get("quotation") or ""
    if item_code:
        candidates = quotation_lookups["by_code"].get((quotation, item_code), set())
        if candidates:
            return {
                "source": "direct_quote",
                "group_keys": sorted(key for key in candidates if key in grouped_rows),
            }

    if item_name:
        candidates = quotation_lookups["by_name"].get((quotation, item_name), set())
        if candidates:
            return {
                "source": "direct_quote",
                "group_keys": sorted(key for key in candidates if key in grouped_rows),
            }

    return None


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


def _get_quote_open_allocation_weights(grouped_rows, allocations, total_key, draft_key, submitted_key, used_key):
    weights = []
    for group_key in allocations:
        group = grouped_rows[group_key]
        remaining = max(
            flt(group.get(total_key))
            - flt(group.get(draft_key))
            - flt(group.get(submitted_key))
            - flt(group.get(used_key)),
            0,
        )
        weights.append(remaining)

    if any(weight > 0 for weight in weights):
        return weights

    fallback_weights = [
        max(
            flt(grouped_rows[group_key].get(total_key))
            - flt(grouped_rows[group_key].get(draft_key))
            - flt(grouped_rows[group_key].get(submitted_key)),
            0,
        )
        for group_key in allocations
    ]
    if any(weight > 0 for weight in fallback_weights):
        return fallback_weights

    absolute_weights = [flt(grouped_rows[group_key].get(total_key)) for group_key in allocations]
    if any(weight > 0 for weight in absolute_weights):
        return absolute_weights

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
        quotation_open_qty = max(
            flt(group["quotation_qty"])
            - flt(group["draft_so_qty"])
            - flt(group["submitted_so_qty"])
            - flt(group["direct_quote_invoiced_qty"]),
            0,
        )
        quotation_open_value = max(
            flt(group["quotation_value"])
            - flt(group["draft_so_value"])
            - flt(group["submitted_so_value"])
            - flt(group["direct_quote_invoiced_value"]),
            0,
        )
        order_qty = flt(group["draft_so_qty"]) + flt(group["submitted_so_qty"])
        order_value = flt(group["draft_so_value"]) + flt(group["submitted_so_value"])
        submitted_so_uninvoiced_qty = max(
            flt(group["submitted_so_qty"]) - flt(group["submitted_so_invoiced_qty"]),
            0,
        )
        submitted_so_uninvoiced_value = max(
            flt(group["submitted_so_value"]) - flt(group["submitted_so_invoiced_value"]),
            0,
        )
        invoiced_qty = flt(group["submitted_so_invoiced_qty"]) + flt(group["direct_quote_invoiced_qty"])
        invoiced_value = flt(group["submitted_so_invoiced_value"]) + flt(group["direct_quote_invoiced_value"])
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
            "order_qty": order_qty,
            "order_value": order_value,
            "quotation_open_qty": quotation_open_qty,
            "quotation_open_value": quotation_open_value,
            "draft_so_qty": flt(group["draft_so_qty"]),
            "draft_so_value": flt(group["draft_so_value"]),
            "submitted_so_qty": flt(group["submitted_so_qty"]),
            "submitted_so_value": flt(group["submitted_so_value"]),
            "submitted_so_uninvoiced_qty": submitted_so_uninvoiced_qty,
            "submitted_so_uninvoiced_value": submitted_so_uninvoiced_value,
            "invoiced_qty": invoiced_qty,
            "invoiced_value": invoiced_value,
            "total_uninvoiced_qty": total_uninvoiced_qty,
            "total_uninvoiced_value": total_uninvoiced_value,
            "sales_order_status": sales_order_status,
            "sales_order_count": len(group["sales_order_names"]),
            "sales_order_names": sorted(group["sales_order_names"]),
            "latest_sales_order": group["latest_sales_order"],
            "latest_sales_order_date": group["latest_sales_order_date"],
            "latest_invoice_date": group["latest_invoice_date"],
            "status_summary": _build_status_summary(
                quotation_status=group["quotation_status"],
                sales_order_status=sales_order_status,
            ),
            "planning_stage_summary": _build_planning_stage_summary(
                quotation_open_qty=quotation_open_qty,
                draft_so_qty=flt(group["draft_so_qty"]),
                submitted_so_uninvoiced_qty=submitted_so_uninvoiced_qty,
                invoiced_qty=invoiced_qty,
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


def _build_value_stage_summary(quotation_open_value, draft_so_value, submitted_so_uninvoiced_value, invoiced_value):
    stages = []
    if quotation_open_value > VALUE_EPSILON:
        stages.append("Quotation Open")
    if draft_so_value > VALUE_EPSILON:
        stages.append("Draft SO")
    if submitted_so_uninvoiced_value > VALUE_EPSILON:
        if invoiced_value > VALUE_EPSILON:
            stages.append("Partially Invoiced SO")
        else:
            stages.append("Submitted SO Awaiting Invoice")

    if stages:
        return " + ".join(stages)

    if invoiced_value > VALUE_EPSILON:
        return "Fully Invoiced"

    return "No Activity"


def _build_status_summary(quotation_status, sales_order_status):
    quote_label = quotation_status or "Unknown Quote"
    order_label = sales_order_status or "Unknown SO"
    return f"{quote_label} / {order_label}"


def _build_pending_invoice_source_key(quotation, item_code):
    return f"{(quotation or '').strip().lower()}::{(item_code or '').strip().lower()}"


def _sum_planning_fields(target, source):
    for fieldname in (
        "quotation_qty",
        "quotation_value",
        "quotation_open_qty",
        "quotation_open_value",
        "draft_so_qty",
        "draft_so_value",
        "submitted_so_uninvoiced_qty",
        "submitted_so_uninvoiced_value",
        "invoiced_qty",
        "invoiced_value",
        "total_uninvoiced_qty",
        "total_uninvoiced_value",
    ):
        target[fieldname] += flt(source.get(fieldname))


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


def _build_invoice_source_select(direct_fieldname, prevdoc_fieldname, has_prevdoc_doctype, target_doctype, alias):
    if direct_fieldname:
        return f"sii.{direct_fieldname} AS {alias}"
    if prevdoc_fieldname and has_prevdoc_doctype:
        return f"CASE WHEN sii.prevdoc_doctype = '{target_doctype}' THEN sii.{prevdoc_fieldname} ELSE NULL END AS {alias}"
    return f"NULL AS {alias}"


def _build_invoice_source_condition(values, direct_fieldname, prevdoc_fieldname, has_prevdoc_doctype, target_doctype):
    if not values:
        return None, []

    placeholders = ", ".join(["%s"] * len(values))
    if direct_fieldname:
        return f"sii.{direct_fieldname} IN ({placeholders})", list(values)
    if prevdoc_fieldname and has_prevdoc_doctype:
        return (
            f"(sii.{prevdoc_fieldname} IN ({placeholders}) AND sii.prevdoc_doctype = '{target_doctype}')",
            list(values),
        )
    return None, []


def _extract_date_bounds(filters):
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    date_range = filters.get("date_range")

    if date_range:
        parsed_range = _normalize_date_range(date_range)
        from_date = parsed_range.get("from_date") or from_date
        to_date = parsed_range.get("to_date") or to_date

    return from_date, to_date


def _matches_required_by_date_range(required_by_date, from_date, to_date):
    if not required_by_date:
        return False

    required_date = getdate(required_by_date)
    if from_date and required_date < getdate(from_date):
        return False
    if to_date and required_date > getdate(to_date):
        return False
    return True


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


def _normalize_date_range(value):
    if not value:
        return {"from_date": "", "to_date": ""}

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {"from_date": "", "to_date": ""}
        try:
            value = json.loads(raw)
        except Exception:
            parts = [entry.strip() for entry in raw.split(",")]
            value = parts if len(parts) >= 2 else [raw, ""]

    if isinstance(value, dict):
        return {
            "from_date": value.get("from_date") or value.get("start") or "",
            "to_date": value.get("to_date") or value.get("end") or "",
        }

    if isinstance(value, (list, tuple)):
        items = list(value) + ["", ""]
        return {
            "from_date": items[0] or "",
            "to_date": items[1] or "",
        }

    return {"from_date": "", "to_date": ""}


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
