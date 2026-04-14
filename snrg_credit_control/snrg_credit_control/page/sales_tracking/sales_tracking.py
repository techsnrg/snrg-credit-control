from __future__ import annotations

from collections import defaultdict
from urllib.parse import quote

import frappe
from frappe.utils import cint, flt, getdate, now_datetime


def get_context(context):
    context.no_cache = 1
    return context


@frappe.whitelist()
def get_tracker_data(
    company=None,
    from_date=None,
    to_date=None,
    territory=None,
    customer=None,
    search=None,
    credit_status=None,
    delivery_status=None,
    limit=250,
):
    filters = {
        "company": company,
        "from_date": from_date,
        "to_date": to_date,
        "territory": territory,
        "customer": customer,
        "search": search,
    }
    quotations = _get_quotations(filters, limit=limit)
    if not quotations:
        return {
            "generated_on": str(now_datetime()),
            "filters": filters,
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
        row = _build_tracker_row(quotation, salespeople, sales_orders, invoices)
        if credit_status and row["credit_status"] != credit_status:
            continue
        if delivery_status and row["delivery_status_overall"] != delivery_status:
            continue
        rows.append(row)

    return {
        "generated_on": str(now_datetime()),
        "filters": filters,
        "summary": _build_summary(rows),
        "rows": rows,
    }


def _get_quotations(filters, limit=250):
    conditions = ["q.quotation_to = 'Customer'", "q.docstatus < 2"]
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
            q.custom_snrg_credit_check_status,
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

    placeholders = ", ".join(["%s"] * len(quotation_names))
    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT
            soi.prevdoc_docname AS quotation,
            so.name,
            so.transaction_date,
            so.delivery_date,
            so.grand_total,
            so.status,
            so.docstatus,
            so.custom_snrg_credit_check_status,
            so.custom_credit_clearance_date
        FROM `tabSales Order Item` soi
        INNER JOIN `tabSales Order` so ON so.name = soi.parent
        WHERE soi.prevdoc_doctype = 'Quotation'
          AND soi.prevdoc_docname IN ({placeholders})
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

    invoice_docs = frappe.get_all(
        "Sales Invoice",
        filters={"name": ["in", list(set(invoice_names))]},
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


def _build_tracker_row(quotation, salespeople, sales_orders, invoices):
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

    invoice_total = sum(flt(invoice.get("grand_total")) for invoice in invoices)
    cartons_total = sum(cint(invoice.get("no_of_cartons")) for invoice in invoices)
    latest_invoice_no = latest_invoice["name"] if latest_invoice else ""
    latest_invoice_count = max(len(invoices) - 1, 0)

    credit_status = _derive_credit_status(quotation, sales_orders)
    credit_clearance_date = _derive_credit_clearance_date(quotation, sales_orders)
    overall_delivery_status = _derive_delivery_status(invoices)
    pod_status = _derive_pod_status(invoices)

    return {
        "quotation_id": quotation.name,
        "quotation_url": f"/app/quotation/{quote(quotation.name)}",
        "quotation_comments_url": f"/app/quotation/{quote(quotation.name)}#comments",
        "order_month": getdate(quotation.transaction_date).strftime("%b %Y") if quotation.transaction_date else "",
        "order_date": _serialize_date(quotation.transaction_date),
        "channel_partner_name": quotation.customer_name or quotation.customer,
        "zone": quotation.territory or "",
        "city": quotation.custom_city or "",
        "state": quotation.custom_state or "",
        "salesperson_summary": _get_salesperson_summary(primary_salesperson, salespeople),
        "salespeople": salespeople,
        "order_value": flt(quotation.grand_total),
        "basic_value": flt(quotation.net_total),
        "delay_reason": quotation.custom_delay_reason or "",
        "original_esd": _serialize_date(quotation.custom_expected_dispatch_date),
        "sales_order_delivery_date": latest_sales_order.get("delivery_date") if latest_sales_order else "",
        "sales_orders": sales_orders,
        "latest_ho_remark": quotation.custom_latest_ho_remark or "",
        "credit_status": credit_status,
        "credit_clearance_date": credit_clearance_date,
        "invoice_summary": _get_invoice_summary(latest_invoice_no, latest_invoice_count),
        "invoice_details": invoices,
        "invoice_amount": invoice_total,
        "invoice_date": latest_invoice.get("posting_date") if latest_invoice else "",
        "shortage_amount": flt(quotation.grand_total) - invoice_total,
        "dispatch_date": latest_dispatch.get("shipping_date") if latest_dispatch else "",
        "transport_name": latest_dispatch.get("transporter") if latest_dispatch else "",
        "tracking_details": latest_dispatch.get("awb_number") if latest_dispatch else "",
        "delivery_status_overall": overall_delivery_status,
        "delivery_date": latest_delivery.get("delivery_date") if latest_delivery else "",
        "pod_status": pod_status,
        "remarks": latest_remark_invoice.get("dispatch_delivery_remarks") if latest_remark_invoice else "",
        "no_of_cartons": cartons_total,
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


def _get_salesperson_fieldname():
    meta = frappe.get_meta("Sales Team")
    for candidate in ("sales_person", "salesperson"):
        if meta.has_field(candidate):
            return candidate
    return "sales_person"
