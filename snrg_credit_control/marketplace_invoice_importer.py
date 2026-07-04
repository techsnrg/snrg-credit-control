from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import frappe
from frappe import _


B2B_CUSTOMER = "Moglix B2B"
B2C_CUSTOMER = "Moglix B2C"
SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}
SUPPORTED_MARKETPLACES = {"Auto Detect", "Moglix", "Amazon", "Flipkart"}
MISSING_INVOICE_LABEL = "Missing Invoice Number"


@frappe.whitelist()
def preview_file(file_url: str, marketplace: str = "Auto Detect"):
    """Parse an uploaded marketplace statement and return invoice/RTV preview rows."""
    if not file_url:
        frappe.throw(_("Please upload a CSV or XLSX file first."))

    selected_marketplace = _clean_marketplace(marketplace)
    path = _get_file_path(file_url)
    extension = Path(path).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        frappe.throw(_("Only CSV and XLSX marketplace files are supported right now."))

    rows = _read_rows(path, extension)
    if not rows:
        frappe.throw(_("The uploaded file does not contain any rows."))

    detected_marketplace = _detect_marketplace(rows[0])
    if selected_marketplace == "Auto Detect":
        marketplace = detected_marketplace
    else:
        marketplace = selected_marketplace

    if marketplace != detected_marketplace:
        frappe.throw(
            _(
                "The uploaded file looks like {0}, but {1} was selected."
            ).format(detected_marketplace, marketplace)
        )
    if marketplace in {"Amazon", "Flipkart"}:
        frappe.throw(_("{0} parser is not available yet. Please upload a Moglix file for now.").format(marketplace))
    if marketplace != "Moglix":
        frappe.throw(_("Could not detect a supported marketplace format from this file."))

    parsed_rows = [_normalise_moglix_row(row, index + 2) for index, row in enumerate(rows)]
    return _build_preview(file_url, marketplace, parsed_rows)


def _clean_marketplace(marketplace: str | None) -> str:
    marketplace = _clean_text(marketplace) or "Auto Detect"
    if marketplace not in SUPPORTED_MARKETPLACES:
        frappe.throw(_("Unsupported marketplace selection: {0}").format(marketplace))
    return marketplace


def _get_file_path(file_url: str) -> str:
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    return file_doc.get_full_path()


def _read_rows(path: str, extension: str) -> list[dict[str, str]]:
    if extension == ".csv":
        with open(path, "rb") as handle:
            raw = handle.read()
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        return [_clean_row(row) for row in reader]

    return _read_xlsx_rows(path)


def _read_xlsx_rows(path: str) -> list[dict[str, str]]:
    try:
        from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file
    except ImportError:
        frappe.throw(_("XLSX support is not available on this ERPNext site. Please upload CSV."))

    data = read_xlsx_file_from_attached_file(filepath=path)
    if not data:
        return []

    headers = [str(value or "").strip() for value in data[0]]
    rows = []
    for values in data[1:]:
        row = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            row[header] = "" if index >= len(values) or values[index] is None else str(values[index]).strip()
        if any(value for value in row.values()):
            rows.append(_clean_row(row))
    return rows


def _clean_row(row: dict) -> dict[str, str]:
    return {
        str(key or "").strip(): "" if value is None else str(value).strip()
        for key, value in row.items()
        if str(key or "").strip()
    }


def _detect_marketplace(sample_row: dict[str, str]) -> str:
    headers = {header.strip() for header in sample_row}
    moglix_markers = {
        "orderNumber",
        "suborderNumber",
        "productMsn",
        "netPayoutFromMoglix",
        "taxInvoice",
    }
    if moglix_markers.issubset(headers):
        return "Moglix"
    return "Unknown"


def _normalise_moglix_row(row: dict[str, str], source_row: int) -> dict:
    tax_invoice = _clean_text(row.get("taxInvoice")).upper()
    current_status = _clean_text(row.get("currentStatus"))
    transition_status = _clean_text(row.get("transitionStatus"))
    transaction_type = _clean_text(row.get("transactionType"))
    invoice_value = _to_decimal(row.get("invoiceValue"))
    gst_value = _to_decimal(row.get("gstValue"))
    igst_amount = _to_decimal(row.get("igstAmount"))
    cgst_amount = _to_decimal(row.get("cgstAmount"))
    sgst_amount = _to_decimal(row.get("sgstAmount"))
    net_payout = _to_decimal(row.get("netPayoutFromMoglix"))

    return {
        "source_row": source_row,
        "marketplace": "Moglix",
        "customer_type": "B2B" if tax_invoice == "YES" else "B2C",
        "customer": B2B_CUSTOMER if tax_invoice == "YES" else B2C_CUSTOMER,
        "order_number": _clean_text(row.get("orderNumber")),
        "suborder_number": _clean_text(row.get("suborderNumber")),
        "invoice_number": _clean_text(row.get("invoiceNumber")) or MISSING_INVOICE_LABEL,
        "invoice_date": _parse_date(row.get("invoiceDate")),
        "product_name": _clean_text(row.get("productName")),
        "marketplace_sku": _clean_text(row.get("productMsn")),
        "hsn_code": _clean_text(row.get("hsnCode")),
        "quantity": _to_decimal(row.get("quantity")),
        "current_status": current_status,
        "transition_status": transition_status,
        "transaction_type": transaction_type,
        "tax_invoice": tax_invoice,
        "supplier_invoice": _clean_text(row.get("supplierInvoice")),
        "invoice_value": invoice_value,
        "gst_percentage": _to_decimal(row.get("gstPercentage")),
        "gst_value": gst_value,
        "taxable_value": invoice_value - gst_value,
        "igst_amount": igst_amount,
        "cgst_amount": cgst_amount,
        "sgst_amount": sgst_amount,
        "net_payout": net_payout,
        "commission": _to_decimal(row.get("moglixCommission")),
        "service_tax": _to_decimal(row.get("serviceTax")),
        "tcs_amount": _to_decimal(row.get("tcsAmount")),
        "tds_amount": _to_decimal(row.get("tdsAmount")),
        "utr_number": _clean_text(row.get("utrNumber")),
        "customer_name": _clean_text(row.get("customerName")),
        "customer_pincode": _clean_text(row.get("customerPincode")),
        "customer_city": _clean_text(row.get("customerCity")),
        "customer_state": _clean_text(row.get("customerState")),
        "rtv_done_date": _parse_date(row.get("rtvDoneDate")),
        "payment_status": _clean_text(row.get("paymentStatus")),
        "payment_reference_id": _clean_text(row.get("paymentReferenceId")),
    }


def _build_preview(file_url: str, marketplace: str, rows: list[dict]) -> dict:
    invoiceable = []
    cancelled = []
    rtv = []
    adjustments = []
    missing_invoice = []

    for row in rows:
        category = _classify_row(row)
        if category == "cancelled":
            cancelled.append(row)
        elif category == "rtv":
            rtv.append(row)
        elif category == "adjustment":
            adjustments.append(row)
        else:
            invoiceable.append(row)
            if row["invoice_number"] == MISSING_INVOICE_LABEL:
                missing_invoice.append(row)

    invoice_groups = _group_invoice_rows(invoiceable)
    return {
        "file_url": file_url,
        "marketplace": marketplace,
        "summary": {
            "total_rows": len(rows),
            "invoiceable_rows": len(invoiceable),
            "invoice_groups": len(invoice_groups),
            "b2b_invoices": sum(1 for group in invoice_groups if group["customer_type"] == "B2B"),
            "b2c_invoices": sum(1 for group in invoice_groups if group["customer_type"] == "B2C"),
            "rtv_rows": len(rtv),
            "cancelled_rows": len(cancelled),
            "adjustment_rows": len(adjustments),
            "missing_invoice_rows": len(missing_invoice),
            "gross_invoice_value": _money(sum((row["invoice_value"] for row in invoiceable), Decimal("0"))),
            "gst_value": _money(sum((row["gst_value"] for row in invoiceable), Decimal("0"))),
            "taxable_value": _money(sum((row["taxable_value"] for row in invoiceable), Decimal("0"))),
            "net_payout": _money(sum((row["net_payout"] for row in invoiceable), Decimal("0"))),
        },
        "invoice_groups": invoice_groups,
        "rtv_rows": [_serialise_row(row) for row in rtv],
        "cancelled_rows": [_serialise_row(row) for row in cancelled],
        "adjustment_rows": [_serialise_row(row) for row in adjustments],
        "warnings": _build_warnings(invoice_groups, rtv, cancelled, adjustments, missing_invoice),
    }


def _classify_row(row: dict) -> str:
    statuses = " ".join(
        value
        for value in (row.get("current_status"), row.get("transition_status"))
        if value
    ).upper()
    transaction_type = (row.get("transaction_type") or "").upper()

    if "RTV" in statuses or row.get("rtv_done_date"):
        return "rtv"
    if "CANCEL" in statuses:
        return "cancelled"
    if transaction_type == "RECEIVABLE" or row.get("invoice_value", Decimal("0")) < 0:
        return "adjustment"
    return "invoiceable"


def _group_invoice_rows(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["customer"], row["invoice_number"])].append(row)

    groups = []
    for (customer, invoice_number), group_rows in sorted(grouped.items(), key=lambda item: item[0]):
        first = group_rows[0]
        groups.append(
            {
                "customer": customer,
                "customer_type": first["customer_type"],
                "invoice_number": invoice_number,
                "invoice_date": first["invoice_date"],
                "supplier_invoices": _unique_values(group_rows, "supplier_invoice"),
                "buyer_names": _unique_values(group_rows, "customer_name"),
                "buyer_pincodes": _unique_values(group_rows, "customer_pincode"),
                "buyer_cities": _unique_values(group_rows, "customer_city"),
                "buyer_states": _unique_values(group_rows, "customer_state"),
                "orders": sorted({row["order_number"] for row in group_rows if row["order_number"]}),
                "line_count": len(group_rows),
                "quantity": _number(sum((row["quantity"] for row in group_rows), Decimal("0"))),
                "gross_invoice_value": _money(sum((row["invoice_value"] for row in group_rows), Decimal("0"))),
                "taxable_value": _money(sum((row["taxable_value"] for row in group_rows), Decimal("0"))),
                "gst_value": _money(sum((row["gst_value"] for row in group_rows), Decimal("0"))),
                "igst_amount": _money(sum((row["igst_amount"] for row in group_rows), Decimal("0"))),
                "cgst_amount": _money(sum((row["cgst_amount"] for row in group_rows), Decimal("0"))),
                "sgst_amount": _money(sum((row["sgst_amount"] for row in group_rows), Decimal("0"))),
                "net_payout": _money(sum((row["net_payout"] for row in group_rows), Decimal("0"))),
                "rows": [_serialise_row(row) for row in group_rows],
            }
        )
    return groups


def _unique_values(rows: list[dict], key: str) -> list[str]:
    return sorted({row.get(key) for row in rows if row.get(key)})


def _build_warnings(invoice_groups, rtv_rows, cancelled_rows, adjustment_rows, missing_invoice_rows):
    warnings = []
    if missing_invoice_rows:
        warnings.append(
            f"{len(missing_invoice_rows)} invoiceable row(s) do not have an invoice number."
        )
    if rtv_rows:
        warnings.append(f"{len(rtv_rows)} RTV row(s) were kept out of invoice creation.")
    if cancelled_rows:
        warnings.append(f"{len(cancelled_rows)} cancelled row(s) were skipped.")
    if adjustment_rows:
        warnings.append(
            f"{len(adjustment_rows)} receivable/negative row(s) were kept as adjustments."
        )
    duplicate_candidates = _duplicate_invoice_numbers(invoice_groups)
    if duplicate_candidates:
        warnings.append(
            "These invoice numbers appear under multiple customer buckets: "
            + ", ".join(duplicate_candidates)
        )
    return warnings


def _duplicate_invoice_numbers(invoice_groups) -> list[str]:
    by_invoice = defaultdict(set)
    for group in invoice_groups:
        by_invoice[group["invoice_number"]].add(group["customer"])
    return sorted(invoice for invoice, customers in by_invoice.items() if len(customers) > 1)


def _serialise_row(row: dict) -> dict:
    return {
        key: _serialise_value(value)
        for key, value in row.items()
    }


def _serialise_value(value):
    if isinstance(value, Decimal):
        return _number(value)
    return value


def _parse_date(value) -> str:
    value = _clean_text(value)
    if not value or value.lower() in {"null", "none"}:
        return ""

    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


def _to_decimal(value) -> Decimal:
    value = _clean_text(value)
    if not value or value.lower() in {"null", "none"}:
        return Decimal("0")
    try:
        return Decimal(value.replace(",", ""))
    except (InvalidOperation, AttributeError):
        return Decimal("0")


def _clean_text(value) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
