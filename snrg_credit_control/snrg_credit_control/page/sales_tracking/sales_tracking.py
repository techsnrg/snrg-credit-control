from __future__ import annotations

from collections import defaultdict
import json
from urllib.parse import quote

import frappe
from frappe.utils import cint, date_diff, flt, get_datetime, getdate, now_datetime, nowdate
from snrg_credit_control.snrg_credit_control.pending_invoice_planning import (
    get_pending_invoice_planning_rows,
    get_sales_order_item_quotation_link_config as get_pending_planning_so_link_config,
)


def get_context(context):
    context.no_cache = 1
    return context


@frappe.whitelist()
def get_tracker_data(
    company=None,
    from_date=None,
    to_date=None,
    order_month=None,
    territory=None,
    customer=None,
    search=None,
    credit_status=None,
    delivery_status=None,
    limit=250,
):
    sla_settings = _get_sla_settings()
    filters = {
        "company": company,
        "from_date": from_date,
        "to_date": to_date,
        "order_month": order_month,
        "territory": territory,
        "customer": customer,
        "search": search,
    }
    quotations = _get_quotations(filters, limit=limit)
    if not quotations:
        return {
            "generated_on": str(now_datetime()),
            "filters": filters,
            "sla_settings": sla_settings,
            "summary": _build_summary([]),
            "rows": [],
        }

    quotation_names = [row.name for row in quotations]
    salespeople_by_quote = _get_salespeople(quotation_names)
    sales_orders_by_quote = _get_sales_orders(quotation_names)
    invoices_by_quote = _get_invoices(sales_orders_by_quote)

    rows = []
    for quotation in quotations:
        salespeople = salespeople_by_quote.get(quotation.name, [])
        sales_orders = sales_orders_by_quote.get(quotation.name, [])
        invoices = invoices_by_quote.get(quotation.name, [])
        row = _build_tracker_row(quotation, salespeople, sales_orders, invoices, sla_settings)
        if credit_status and row["credit_status"] != credit_status:
            continue
        if delivery_status and row["delivery_status_overall"] != delivery_status:
            continue
        rows.append(row)

    return {
        "generated_on": str(now_datetime()),
        "filters": filters,
        "sla_settings": sla_settings,
        "summary": _build_summary(rows),
        "rows": rows,
    }


@frappe.whitelist()
def get_saved_views():
    if not frappe.db.exists("DocType", "Sales Tracking Saved View"):
        return []

    views = frappe.get_all(
        "Sales Tracking Saved View",
        filters={"page_name": "sales-tracking", "is_shared": 1},
        fields=["name", "view_name", "view_state_json", "modified", "modified_by"],
        order_by="view_name asc",
    )
    return [
        {
            "name": row.name,
            "view_name": row.view_name,
            "modified": str(row.modified) if row.modified else "",
            "modified_by": row.modified_by,
            "state": _safe_json_loads(row.view_state_json),
        }
        for row in views
    ]


@frappe.whitelist()
def save_saved_view(view_name, state_json, docname=None):
    if not frappe.db.exists("DocType", "Sales Tracking Saved View"):
        frappe.throw("Sales Tracking Saved View DocType is not available yet. Please run migrate.")

    view_name = (view_name or "").strip()
    if not view_name:
        frappe.throw("View name is required.")

    state = _safe_json_loads(state_json)
    if not isinstance(state, dict):
        frappe.throw("Saved view state must be valid JSON.")

    existing_name = docname or frappe.db.exists("Sales Tracking Saved View", view_name)
    if existing_name:
        doc = frappe.get_doc("Sales Tracking Saved View", existing_name)
        doc.view_name = view_name
        doc.page_name = "sales-tracking"
        doc.is_shared = 1
        doc.view_state_json = json.dumps(state, separators=(",", ":"))
        doc.save()
        if doc.name != view_name:
            new_name = frappe.rename_doc("Sales Tracking Saved View", doc.name, view_name, force=True)
            doc = frappe.get_doc("Sales Tracking Saved View", new_name)
    else:
        doc = frappe.get_doc(
            {
                "doctype": "Sales Tracking Saved View",
                "view_name": view_name,
                "page_name": "sales-tracking",
                "is_shared": 1,
                "view_state_json": json.dumps(state, separators=(",", ":")),
            }
        ).insert()

    return {
        "name": doc.name,
        "view_name": doc.view_name,
        "state": state,
    }


@frappe.whitelist()
def delete_saved_view(docname):
    if not docname:
        frappe.throw("Saved view name is required.")
    frappe.delete_doc("Sales Tracking Saved View", docname)
    return {"ok": True}


@frappe.whitelist()
def get_shortage_details(quotation_id):
    quotation_id = (quotation_id or "").strip()
    if not quotation_id:
        frappe.throw("Quotation ID is required.")

    quotation = frappe.db.get_value(
        "Quotation",
        quotation_id,
        ["name", "currency", "customer_name", "party_name"],
        as_dict=True,
    )
    if not quotation:
        frappe.throw("Quotation not found.")

    rows = _get_shortage_rows_for_quotation(quotation_id)
    return {
        "quotation_id": quotation_id,
        "currency": quotation.get("currency") or "INR",
        "channel_partner_name": quotation.get("customer_name") or quotation.get("party_name") or "",
        "rows": rows,
        "totals": {
            "quotation_qty": sum(flt(row["quotation_qty"]) for row in rows),
            "invoiced_qty": sum(flt(row["invoiced_qty"]) for row in rows),
            "pending_qty": sum(flt(row["pending_qty"]) for row in rows),
            "quotation_value": sum(flt(row["quotation_value"]) for row in rows),
            "invoiced_value": sum(flt(row["invoiced_value"]) for row in rows),
            "pending_value": sum(flt(row["pending_value"]) for row in rows),
        },
    }


def _get_quotations(filters, limit=250):
    conditions = ["q.quotation_to = 'Customer'"]
    values = {}

    if filters.get("company"):
        conditions.append("q.company = %(company)s")
        values["company"] = filters["company"]
    if filters.get("from_date"):
        conditions.append("q.transaction_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        conditions.append("q.transaction_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]
    if filters.get("order_month"):
        order_month = (filters.get("order_month") or "").strip()
        if len(order_month) == 7 and order_month[4] == "-":
            conditions.append("DATE_FORMAT(q.transaction_date, '%%Y-%%m') = %(order_month)s")
            values["order_month"] = order_month
        else:
            conditions.append("DATE_FORMAT(q.transaction_date, '%%b %%Y') = %(order_month_label)s")
            values["order_month_label"] = order_month
    if filters.get("territory"):
        conditions.append("q.territory = %(territory)s")
        values["territory"] = filters["territory"]
    if filters.get("customer"):
        conditions.append("q.party_name = %(customer)s")
        values["customer"] = filters["customer"]
    if filters.get("search"):
        values["search"] = f"%{filters['search'].strip()}%"
        conditions.append(
            "(q.name LIKE %(search)s OR q.party_name LIKE %(search)s OR IFNULL(q.customer_name, '') LIKE %(search)s)"
        )

    values["limit"] = cint(limit) or 250
    where_clause = " AND ".join(conditions)

    return frappe.db.sql(
        f"""
        SELECT
            q.name,
            q.company,
            q.transaction_date,
            q.party_name AS customer,
            q.customer_name,
            q.territory,
            q.grand_total,
            q.net_total,
            q.currency,
            q.owner,
            q.custom_delay_reason,
            q.custom_expected_dispatch_date,
            q.custom_latest_ho_remark,
            q.customer_confirmation_status,
            q.custom_snrg_credit_check_status,
            q.custom_snrg_credit_checked_on,
            q.custom_credit_clearance_date,
            q.docstatus,
            c.custom_city,
            c.custom_state
        FROM `tabQuotation` q
        LEFT JOIN `tabCustomer` c ON c.name = q.party_name
        WHERE {where_clause}
        ORDER BY q.transaction_date DESC, q.modified DESC
        LIMIT %(limit)s
        """,
        values,
        as_dict=True,
    )


def _get_salespeople(quotation_names):
    if not quotation_names:
        return {}

    salesperson_fieldname = _get_salesperson_fieldname()
    rows = frappe.get_all(
        "Sales Team",
        filters={"parenttype": "Quotation", "parent": ["in", quotation_names]},
        fields=["parent", salesperson_fieldname, "allocated_percentage", "idx"],
        order_by="parent asc, idx asc",
    )

    grouped = defaultdict(list)
    for row in rows:
        grouped[row.parent].append(
            {
                "salesperson": row.get(salesperson_fieldname) or "",
                "allocated_percentage": flt(row.allocated_percentage),
                "idx": cint(row.idx),
            }
        )

    for quotation_name, details in grouped.items():
        details.sort(key=lambda entry: (-flt(entry["allocated_percentage"]), cint(entry["idx"])))

    return grouped


def _get_sales_orders(quotation_names):
    grouped = defaultdict(list)
    if not quotation_names:
        return grouped

    quotation_link_fieldname, has_prevdoc_doctype = _get_sales_order_item_quotation_link_config()
    if not quotation_link_fieldname:
        return grouped

    placeholders = ", ".join(["%s"] * len(quotation_names))
    extra_condition = "AND soi.prevdoc_doctype = 'Quotation'" if has_prevdoc_doctype else ""
    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT
            soi.{quotation_link_fieldname} AS quotation,
            so.name,
            so.transaction_date,
            so.delivery_date,
            so.grand_total,
            so.status,
            so.docstatus,
            so.custom_snrg_credit_check_status,
            so.custom_snrg_credit_checked_on,
            so.custom_credit_clearance_date
        FROM `tabSales Order Item` soi
        INNER JOIN `tabSales Order` so ON so.name = soi.parent
        WHERE soi.{quotation_link_fieldname} IN ({placeholders})
          {extra_condition}
          AND so.docstatus < 2
        ORDER BY so.transaction_date DESC, so.modified DESC
        """,
        tuple(quotation_names),
        as_dict=True,
    )

    seen = set()
    for row in rows:
        key = (row.quotation, row.name)
        if key in seen:
            continue
        seen.add(key)
        grouped[row.quotation].append(
            {
                "name": row.name,
                "transaction_date": _serialize_date(row.transaction_date),
                "delivery_date": _serialize_date(row.delivery_date),
                "grand_total": flt(row.grand_total),
                "status": row.status,
                "docstatus": cint(row.docstatus),
                "credit_status": row.custom_snrg_credit_check_status or "",
                "credit_checked_on": _serialize_date(row.custom_snrg_credit_checked_on),
                "credit_clearance_date": _serialize_date(row.custom_credit_clearance_date),
            }
        )

    return grouped


def _get_invoices(sales_orders_by_quote):
    grouped = defaultdict(list)
    sales_order_to_quote = {}
    for quotation_name, sales_orders in sales_orders_by_quote.items():
        for sales_order in sales_orders:
            sales_order_to_quote[sales_order["name"]] = quotation_name

    sales_order_names = list(sales_order_to_quote)
    if not sales_order_names:
        return grouped

    placeholders = ", ".join(["%s"] * len(sales_order_names))
    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT
            sii.parent AS invoice_name,
            sii.sales_order
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE sii.sales_order IN ({placeholders})
          AND si.docstatus = 1
          AND COALESCE(si.is_return, 0) = 0
        """,
        tuple(sales_order_names),
        as_dict=True,
    )

    invoice_to_quotes = defaultdict(set)
    invoice_names = []
    for row in rows:
        quotation_name = sales_order_to_quote.get(row.sales_order)
        if not quotation_name:
            continue
        invoice_to_quotes[row.invoice_name].add(quotation_name)
        invoice_names.append(row.invoice_name)

    if not invoice_names:
        return grouped

    unique_invoice_names = list(set(invoice_names))

    invoice_docs = frappe.get_all(
        "Sales Invoice",
        filters={"name": ["in", unique_invoice_names]},
        fields=[
            "name",
            "posting_date",
            "grand_total",
            "currency",
            "transporter",
            "custom_shipping_date",
            "custom_awb_number",
            "custom_no_of_cartons",
            "custom_dispatch_delivery_remarks",
            "custom_delivery_status",
            "custom_delivery_date",
            "custom_pod_attachment",
        ],
        order_by="posting_date desc, modified desc",
    )
    pod_date_map = _get_pod_received_dates(invoice_docs)

    invoice_map = {
        doc.name: {
            "name": doc.name,
            "posting_date": _serialize_date(doc.posting_date),
            "grand_total": flt(doc.grand_total),
            "currency": doc.currency,
            "transporter": doc.transporter or "",
            "shipping_date": _serialize_date(doc.custom_shipping_date),
            "awb_number": doc.custom_awb_number or "",
            "no_of_cartons": cint(doc.custom_no_of_cartons),
            "dispatch_delivery_remarks": doc.custom_dispatch_delivery_remarks or "",
            "delivery_status": doc.custom_delivery_status or "",
            "delivery_date": _serialize_date(doc.custom_delivery_date),
            "pod_attachment": doc.custom_pod_attachment or "",
            "pod_received": bool(doc.custom_pod_attachment),
            "pod_received_date": _serialize_date(pod_date_map.get(doc.name)),
        }
        for doc in invoice_docs
    }

    for invoice_name, quotation_names in invoice_to_quotes.items():
        invoice_detail = invoice_map.get(invoice_name)
        if not invoice_detail:
            continue
        for quotation_name in quotation_names:
            grouped[quotation_name].append(invoice_detail.copy())

    for quotation_name, details in grouped.items():
        details.sort(
            key=lambda row: (
                getdate(row["posting_date"]) if row.get("posting_date") else getdate("1900-01-01"),
                row["name"],
            ),
            reverse=True,
        )

    return grouped


def _build_tracker_row(quotation, salespeople, sales_orders, invoices, sla_settings):
    salespeople = salespeople or []
    if not salespeople and quotation.owner:
        salespeople = [
            {
                "salesperson": quotation.owner,
                "allocated_percentage": 0,
                "idx": 9999,
                "fallback_owner": True,
            }
        ]

    primary_salesperson = _get_primary_salesperson(salespeople)
    latest_invoice = _get_latest_by(invoices, "posting_date")
    latest_dispatch = _get_latest_by(invoices, "shipping_date")
    latest_delivery = _get_latest_by(invoices, "delivery_date")
    latest_sales_order = _get_latest_by(sales_orders, "delivery_date")
    latest_remark_invoice = _get_latest_non_empty(invoices, "dispatch_delivery_remarks", "shipping_date", fallback_key="posting_date")
    earliest_invoice = _get_earliest_by(invoices, "posting_date")
    latest_pod = _get_latest_by(invoices, "pod_received_date")

    invoice_total = sum(flt(invoice.get("grand_total")) for invoice in invoices)
    cartons_total = sum(cint(invoice.get("no_of_cartons")) for invoice in invoices)
    latest_invoice_no = latest_invoice["name"] if latest_invoice else ""
    latest_invoice_count = max(len(invoices) - 1, 0)

    credit_status = _derive_credit_status(quotation, sales_orders)
    credit_clearance_date = _derive_credit_clearance_date(quotation, sales_orders)
    overall_delivery_status = _derive_delivery_status(invoices)
    pod_status = _derive_pod_status(invoices)
    credit_hold_since = _derive_credit_hold_since(quotation, sales_orders, credit_status)
    shortage_amount = flt(quotation.grand_total) - invoice_total
    current_stage = _derive_current_stage(
        quotation=quotation,
        sales_orders=sales_orders,
        invoices=invoices,
        invoice_total=invoice_total,
        shortage_amount=shortage_amount,
        delivery_status=overall_delivery_status,
        pod_status=pod_status,
    )

    quotation_to_credit_clearance_sla = _build_sla_metric(
        quotation.transaction_date,
        credit_clearance_date,
        sla_settings.get("quotation_to_credit_clearance_days"),
    )
    quotation_to_delivery_sla = _build_sla_metric(
        quotation.transaction_date,
        latest_delivery.get("delivery_date") if latest_delivery else "",
        sla_settings.get("quotation_to_delivery_days"),
    )
    invoice_to_delivery_sla = _build_sla_metric(
        earliest_invoice.get("posting_date") if earliest_invoice else "",
        latest_delivery.get("delivery_date") if latest_delivery else "",
        sla_settings.get("invoice_to_delivery_days"),
    )
    delivery_to_pod_sla = _build_sla_metric(
        latest_delivery.get("delivery_date") if latest_delivery else "",
        latest_pod.get("pod_received_date") if latest_pod else "",
        sla_settings.get("delivery_to_pod_days"),
    )
    credit_hold_age_sla = _build_sla_metric(
        credit_hold_since,
        "",
        sla_settings.get("credit_hold_age_days"),
        active=credit_status == "Credit Hold",
    )
    esd_delay_sla = _build_esd_delay_metric(
        quotation.custom_expected_dispatch_date,
        latest_delivery.get("delivery_date") if latest_delivery else "",
        sla_settings.get("esd_delay_days"),
        active=current_stage not in {"Closed", "Cancelled"},
    )
    no_invoice_after_so_sla = _build_sla_metric(
        latest_sales_order.get("transaction_date") if latest_sales_order else "",
        earliest_invoice.get("posting_date") if earliest_invoice else "",
        sla_settings.get("no_invoice_after_so_days"),
        active=bool(sales_orders),
    )

    exceptions = {
        "overdue_esd": bool(esd_delay_sla["days"] and esd_delay_sla["status"] == "Breached"),
        "invoice_pending_dispatch": any(not invoice.get("shipping_date") for invoice in invoices),
        "delivered_pending_pod": overall_delivery_status == "Delivered" and pod_status != "Complete",
        "credit_hold_breached": credit_status == "Credit Hold" and credit_hold_age_sla["status"] == "Breached",
        "no_invoice_after_so": bool(sales_orders) and not invoices and no_invoice_after_so_sla["status"] == "Breached",
    }

    return {
        "quotation_id": quotation.name,
        "quotation_url": f"/app/quotation/{quote(quotation.name)}",
        "quotation_comments_url": f"/app/quotation/{quote(quotation.name)}#comments",
        "quotation_status": _get_quotation_status_label(quotation.docstatus),
        "current_stage": current_stage,
        "order_month": getdate(quotation.transaction_date).strftime("%b %Y") if quotation.transaction_date else "",
        "order_month_value": getdate(quotation.transaction_date).strftime("%Y-%m") if quotation.transaction_date else "",
        "order_date": _serialize_date(quotation.transaction_date),
        "customer": quotation.customer or "",
        "channel_partner_name": quotation.customer_name or quotation.customer,
        "zone": quotation.territory or "",
        "city": quotation.custom_city or "",
        "state": quotation.custom_state or "",
        "salesperson_summary": _get_salesperson_summary(primary_salesperson, salespeople),
        "salespeople": salespeople,
        "order_value": flt(quotation.grand_total),
        "basic_value": flt(quotation.net_total),
        "customer_confirmation_status": quotation.customer_confirmation_status or "",
        "delay_reason": quotation.custom_delay_reason or "",
        "original_esd": _serialize_date(quotation.custom_expected_dispatch_date),
        "sales_order_delivery_date": latest_sales_order.get("delivery_date") if latest_sales_order else "",
        "sales_orders": sales_orders,
        "latest_ho_remark": quotation.custom_latest_ho_remark or "",
        "credit_status": credit_status,
        "credit_clearance_date": credit_clearance_date,
        "credit_hold_since": _serialize_date(credit_hold_since),
        "invoice_summary": _get_invoice_summary(latest_invoice_no, latest_invoice_count),
        "invoice_details": invoices,
        "invoice_amount": invoice_total,
        "invoice_date": latest_invoice.get("posting_date") if latest_invoice else "",
        "shortage_amount": shortage_amount,
        "dispatch_date": latest_dispatch.get("shipping_date") if latest_dispatch else "",
        "transport_name": latest_dispatch.get("transporter") if latest_dispatch else "",
        "tracking_details": latest_dispatch.get("awb_number") if latest_dispatch else "",
        "delivery_status_overall": overall_delivery_status,
        "delivery_date": latest_delivery.get("delivery_date") if latest_delivery else "",
        "pod_status": pod_status,
        "pod_received_date": latest_pod.get("pod_received_date") if latest_pod else "",
        "remarks": latest_remark_invoice.get("dispatch_delivery_remarks") if latest_remark_invoice else "",
        "no_of_cartons": cartons_total,
        "quotation_to_credit_clearance_days": quotation_to_credit_clearance_sla["days"],
        "quotation_to_credit_clearance_sla": quotation_to_credit_clearance_sla["status"],
        "quotation_to_delivery_days": quotation_to_delivery_sla["days"],
        "quotation_to_delivery_sla": quotation_to_delivery_sla["status"],
        "invoice_to_delivery_days": invoice_to_delivery_sla["days"],
        "invoice_to_delivery_sla": invoice_to_delivery_sla["status"],
        "delivery_to_pod_days": delivery_to_pod_sla["days"],
        "delivery_to_pod_sla": delivery_to_pod_sla["status"],
        "credit_hold_age_days": credit_hold_age_sla["days"],
        "credit_hold_age_sla": credit_hold_age_sla["status"],
        "esd_delay_days": esd_delay_sla["days"],
        "esd_delay_sla": esd_delay_sla["status"],
        "no_invoice_after_so_days": no_invoice_after_so_sla["days"],
        "no_invoice_after_so_sla": no_invoice_after_so_sla["status"],
        "exception_overdue_esd": exceptions["overdue_esd"],
        "exception_invoice_pending_dispatch": exceptions["invoice_pending_dispatch"],
        "exception_delivered_pending_pod": exceptions["delivered_pending_pod"],
        "exception_credit_hold_breached": exceptions["credit_hold_breached"],
        "exception_no_invoice_after_so": exceptions["no_invoice_after_so"],
        "currency": quotation.currency or "INR",
    }


def _build_summary(rows):
    return {
        "row_count": len(rows),
        "order_value": sum(flt(row["order_value"]) for row in rows),
        "invoice_amount": sum(flt(row["invoice_amount"]) for row in rows),
        "credit_hold_count": sum(1 for row in rows if row["credit_status"] == "Credit Hold"),
        "delivery_complete_count": sum(1 for row in rows if row["delivery_status_overall"] == "Delivered"),
        "pod_complete_count": sum(1 for row in rows if row["pod_status"] == "Complete"),
    }


def _get_sla_settings():
    defaults = {
        "quotation_to_credit_clearance_days": 3,
        "quotation_to_delivery_days": 10,
        "invoice_to_delivery_days": 4,
        "delivery_to_pod_days": 2,
        "credit_hold_age_days": 2,
        "esd_delay_days": 1,
        "no_invoice_after_so_days": 3,
    }
    if not frappe.db.exists("DocType", "Sales Tracking SLA Settings"):
        return defaults

    settings = {}
    for fieldname, fallback in defaults.items():
        settings[fieldname] = cint(
            frappe.db.get_single_value("Sales Tracking SLA Settings", fieldname) or fallback
        )
    return settings


def _get_primary_salesperson(salespeople):
    return salespeople[0] if salespeople else None


def _get_salesperson_summary(primary_salesperson, salespeople):
    if not primary_salesperson:
        return ""
    extra_count = max(len(salespeople) - 1, 0)
    if not extra_count:
        return primary_salesperson["salesperson"]
    return f"{primary_salesperson['salesperson']} (+{extra_count} more)"


def _get_invoice_summary(latest_invoice_no, extra_count):
    if not latest_invoice_no:
        return ""
    if not extra_count:
        return latest_invoice_no
    return f"{latest_invoice_no} (+{extra_count} more)"


def _derive_credit_status(quotation, sales_orders):
    statuses = [row.get("credit_status") for row in sales_orders if row.get("credit_status")]
    if not statuses:
        return quotation.custom_snrg_credit_check_status or ""
    unique_statuses = list(dict.fromkeys(statuses))
    if len(unique_statuses) == 1:
        return unique_statuses[0]
    return "Mixed"


def _derive_credit_clearance_date(quotation, sales_orders):
    dated_rows = [row.get("credit_clearance_date") for row in sales_orders if row.get("credit_clearance_date")]
    if dated_rows:
        return max(dated_rows)
    return _serialize_date(quotation.custom_credit_clearance_date)


def _derive_credit_hold_since(quotation, sales_orders, credit_status):
    if credit_status != "Credit Hold":
        return ""

    dated_rows = [
        row.get("credit_checked_on")
        for row in sales_orders
        if row.get("credit_status") == "Credit Hold" and row.get("credit_checked_on")
    ]
    if dated_rows:
        return max(dated_rows)
    return _serialize_date(quotation.custom_snrg_credit_checked_on)


def _derive_delivery_status(invoices):
    if not invoices:
        return "Pending"

    normalized = [(_normalize_delivery_status(row.get("delivery_status")) or "Pending") for row in invoices]
    delivered_count = sum(1 for status in normalized if status == "Delivered")
    if delivered_count == len(normalized):
        return "Delivered"
    if delivered_count > 0:
        return "Partially Delivered"

    unique_statuses = list(dict.fromkeys(normalized))
    if len(unique_statuses) == 1:
        return unique_statuses[0]
    return "Partially Delivered"


def _derive_pod_status(invoices):
    if not invoices:
        return "Pending"

    received_count = sum(1 for row in invoices if row.get("pod_received"))
    if received_count == 0:
        return "Pending"
    if received_count == len(invoices):
        return "Complete"
    return "Partial"


def _derive_current_stage(quotation, sales_orders, invoices, invoice_total, shortage_amount, delivery_status, pod_status):
    if cint(quotation.docstatus) == 2:
        return "Cancelled"
    if pod_status == "Complete":
        return "Closed"
    if delivery_status == "Delivered":
        return "POD Pending"
    if any(invoice.get("shipping_date") for invoice in invoices):
        return "Dispatched"
    if invoices:
        if flt(shortage_amount) > 0.01:
            return "Partially Invoiced"
        return "Fully Invoiced"
    if sales_orders:
        return "SO Created"
    if cint(quotation.docstatus) == 1:
        return "Submitted Awaiting SO"
    return "Draft Quotation"


def _build_sla_metric(start_date, end_date, threshold_days, active=True):
    if not active or not start_date or not threshold_days:
        return {"days": 0, "status": "Pending"}

    start = getdate(start_date)
    end = getdate(end_date) if end_date else getdate(nowdate())
    days = max(date_diff(end, start), 0)
    return {
        "days": days,
        "status": "Breached" if days > cint(threshold_days) else "On Track",
    }


def _build_esd_delay_metric(esd_date, delivery_date, threshold_days, active=True):
    if not active or not esd_date:
        return {"days": 0, "status": "Pending"}

    end_date = getdate(delivery_date) if delivery_date else getdate(nowdate())
    delay_days = max(date_diff(end_date, getdate(esd_date)), 0)
    return {
        "days": delay_days,
        "status": "Breached" if delay_days > cint(threshold_days) else "On Track",
    }


def _normalize_delivery_status(value):
    value = (value or "").strip()
    if not value:
        return ""
    lower_value = value.lower()
    if lower_value in {"delivered", "complete", "completed"}:
        return "Delivered"
    if lower_value in {"partial", "partially delivered"}:
        return "Partially Delivered"
    if lower_value in {"in transit", "shipped"}:
        return "In Transit"
    if lower_value in {"hold", "on hold"}:
        return "Hold"
    if lower_value in {"returned"}:
        return "Returned"
    return value


def _get_latest_by(rows, date_key):
    dated_rows = [row for row in rows if row.get(date_key)]
    if dated_rows:
        return max(dated_rows, key=lambda row: (getdate(row[date_key]), row.get("name", "")))
    return rows[0] if rows else None


def _get_earliest_by(rows, date_key):
    dated_rows = [row for row in rows if row.get(date_key)]
    if dated_rows:
        return min(dated_rows, key=lambda row: (getdate(row[date_key]), row.get("name", "")))
    return rows[0] if rows else None


def _get_latest_non_empty(rows, value_key, primary_date_key, fallback_key=None):
    candidates = [row for row in rows if row.get(value_key)]
    if not candidates:
        return None

    def sort_key(row):
        date_value = row.get(primary_date_key) or row.get(fallback_key or primary_date_key) or "1900-01-01"
        return getdate(date_value), row.get("name", "")

    return max(candidates, key=sort_key)


def _serialize_date(value):
    if not value:
        return ""
    return str(value)


def _safe_json_loads(value):
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def _get_pod_received_dates(invoice_docs):
    file_urls = [doc.custom_pod_attachment for doc in invoice_docs if doc.custom_pod_attachment]
    if not file_urls:
        return {}

    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Sales Invoice",
            "file_url": ["in", list(set(file_urls))],
        },
        fields=["attached_to_name", "creation", "file_url"],
        order_by="creation desc",
    )
    pod_date_map = {}
    for file_doc in files:
        if not file_doc.attached_to_name or file_doc.attached_to_name in pod_date_map:
            continue
        pod_date_map[file_doc.attached_to_name] = get_datetime(file_doc.creation).date()
    return pod_date_map


def _get_shortage_rows_for_quotation(quotation_id):
    planning_rows = get_pending_invoice_planning_rows(
        quotation_id=quotation_id,
        include_cancelled=True,
        pending_only=True,
    )
    return [
        {
            "item_code": row.get("item_code") or "",
            "item_name": row.get("item_name") or "",
            "quotation_qty": flt(row.get("quotation_qty")),
            "invoiced_qty": flt(row.get("invoiced_qty")),
            "pending_qty": flt(row.get("total_uninvoiced_qty")),
            "quotation_value": flt(row.get("quotation_value")),
            "invoiced_value": flt(row.get("invoiced_value")),
            "pending_value": flt(row.get("total_uninvoiced_value")),
            "quotation_open_qty": flt(row.get("quotation_open_qty")),
            "draft_so_qty": flt(row.get("draft_so_qty")),
            "submitted_so_uninvoiced_qty": flt(row.get("submitted_so_uninvoiced_qty")),
            "planning_stage_summary": row.get("planning_stage_summary") or "",
        }
        for row in planning_rows
    ]


def _get_quotation_status_label(docstatus):
    if cint(docstatus) == 0:
        return "Draft"
    if cint(docstatus) == 1:
        return "Submitted"
    if cint(docstatus) == 2:
        return "Cancelled"
    return ""


def _get_salesperson_fieldname():
    meta = frappe.get_meta("Sales Team")
    for candidate in ("sales_person", "salesperson"):
        if meta.has_field(candidate):
            return candidate
    return "sales_person"


def _get_sales_order_item_quotation_link_config():
    quotation_fieldname, _, has_prevdoc_doctype = get_pending_planning_so_link_config()
    return quotation_fieldname, has_prevdoc_doctype
