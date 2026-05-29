import frappe
from frappe import _
from frappe.utils import flt, getdate

from snrg_credit_control.pricing_guard import MINIMUM_SELLING_PRICE_LIST


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)
    rows = get_invoice_item_rows(filters)
    data = build_report_rows(rows, filters)
    return get_columns(), data


def validate_filters(filters):
    if not filters.get("company"):
        frappe.throw(_("Please select a Company."))
    if not filters.get("date_range") or len(filters.get("date_range")) != 2:
        frappe.throw(_("Please select a Posting Date Range."))


def get_invoice_item_rows(filters):
    date_range = filters.get("date_range")
    conditions = [
        "si.docstatus = 1",
        "si.company = %(company)s",
        "si.posting_date BETWEEN %(from_date)s AND %(to_date)s",
    ]
    values = {
        "company": filters.company,
        "from_date": date_range[0],
        "to_date": date_range[1],
    }

    if filters.get("customer"):
        conditions.append("si.customer = %(customer)s")
        values["customer"] = filters.customer
    if filters.get("customer_group"):
        conditions.append("customer.customer_group = %(customer_group)s")
        values["customer_group"] = filters.customer_group
    if filters.get("item_code"):
        conditions.append("sii.item_code = %(item_code)s")
        values["item_code"] = filters.item_code
    if filters.get("item_group"):
        conditions.append("item.item_group = %(item_group)s")
        values["item_group"] = filters.item_group

    return frappe.db.sql(
        """
        SELECT
            si.name AS sales_invoice,
            si.posting_date,
            si.customer,
            si.customer_name,
            customer.customer_group,
            si.company,
            si.currency,
            sii.idx,
            sii.item_code,
            sii.item_name,
            sii.qty,
            sii.uom,
            sii.conversion_factor,
            sii.rate,
            sii.amount,
            item.item_group,
            item.is_stock_item,
            item.stock_uom
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        LEFT JOIN `tabCustomer` customer ON customer.name = si.customer
        LEFT JOIN `tabItem` item ON item.name = sii.item_code
        WHERE {conditions}
        ORDER BY si.posting_date DESC, si.name DESC, sii.idx ASC
        """.format(conditions=" AND ".join(conditions)),
        values,
        as_dict=True,
    )


def build_report_rows(invoice_rows, filters):
    if not invoice_rows:
        return []

    item_codes = sorted({row.item_code for row in invoice_rows if row.item_code})
    currencies = sorted({row.currency for row in invoice_rows if row.currency})
    price_rows = get_minimum_price_rows(item_codes, currencies)
    only_issues = flt(filters.get("only_issues", 1))
    data = []

    for row in invoice_rows:
        status, minimum_rate, minimum_source = get_row_status(row, price_rows)
        variance = flt(row.rate) - flt(minimum_rate) if minimum_rate is not None else None

        if only_issues and status == "OK":
            continue

        data.append(
            {
                "status": status,
                "sales_invoice": row.sales_invoice,
                "posting_date": row.posting_date,
                "customer": row.customer,
                "customer_name": row.customer_name,
                "customer_group": row.customer_group,
                "item_code": row.item_code,
                "item_name": row.item_name,
                "item_group": row.item_group,
                "qty": row.qty,
                "uom": row.uom,
                "rate": row.rate,
                "minimum_rate": minimum_rate,
                "variance": variance,
                "amount": row.amount,
                "currency": row.currency,
                "minimum_source": minimum_source,
                "sales_invoice_row": row.idx,
            }
        )

    return data


def get_minimum_price_rows(item_codes, currencies):
    if not item_codes:
        return []

    filters = {
        "price_list": MINIMUM_SELLING_PRICE_LIST,
        "item_code": ["in", item_codes],
    }
    if currencies:
        filters["currency"] = ["in", currencies]

    return frappe.get_all(
        "Item Price",
        filters=filters,
        fields=[
            "name",
            "item_code",
            "uom",
            "currency",
            "price_list_rate",
            "valid_from",
            "valid_upto",
        ],
    )


def get_row_status(row, price_rows):
    rate = flt(row.rate)
    if rate < 0:
        return "Negative Rate", None, ""

    if not flt(row.is_stock_item):
        return "OK", None, ""

    minimum_price = find_minimum_price(row, price_rows)
    if not minimum_price:
        return "Missing Minimum", None, ""

    if flt(minimum_price["rate"]) <= 0:
        return "Invalid Minimum", None, minimum_price["source"]

    minimum_rate = flt(minimum_price["rate"])
    if rate < minimum_rate:
        return "Below Minimum", minimum_rate, minimum_price["source"]

    return "OK", minimum_rate, minimum_price["source"]


def find_minimum_price(row, price_rows):
    exact = find_active_price(row, price_rows, row.uom)
    if exact:
        return exact

    stock_uom = row.stock_uom or ""
    stock_price = find_active_price(row, price_rows, stock_uom) or find_active_price(row, price_rows, "")
    if not stock_price:
        return None

    conversion_factor = flt(row.conversion_factor) or 1
    return {
        "rate": flt(stock_price["rate"]) * conversion_factor,
        "source": _("{0} converted from {1}").format(stock_price["source"], stock_uom or _("blank UOM")),
    }


def find_active_price(row, price_rows, uom):
    posting_date = getdate(row.posting_date)
    candidates = []

    for price in price_rows:
        if price.item_code != row.item_code:
            continue
        if price.currency and row.currency and price.currency != row.currency:
            continue
        if (price.uom or "") != (uom or ""):
            continue
        if price.valid_from and getdate(price.valid_from) > posting_date:
            continue
        if price.valid_upto and getdate(price.valid_upto) < posting_date:
            continue

        candidates.append(
            {
                "rate": flt(price.price_list_rate),
                "source": price.name,
            }
        )

    if not candidates:
        return None

    return max(candidates, key=lambda candidate: candidate["rate"])


def get_columns():
    return [
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 130},
        {
            "label": "Sales Invoice",
            "fieldname": "sales_invoice",
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 160,
        },
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
        {
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 150,
        },
        {"label": "Customer Name", "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
        {
            "label": "Customer Group",
            "fieldname": "customer_group",
            "fieldtype": "Link",
            "options": "Customer Group",
            "width": 140,
        },
        {
            "label": "Item Code",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 130,
        },
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {
            "label": "Item Group",
            "fieldname": "item_group",
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 130,
        },
        {"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 90},
        {"label": "UOM", "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 90},
        {
            "label": "Invoice Rate",
            "fieldname": "rate",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": "Minimum Rate",
            "fieldname": "minimum_rate",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": "Variance",
            "fieldname": "variance",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": "Amount",
            "fieldname": "amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {"label": "Minimum Source", "fieldname": "minimum_source", "fieldtype": "Data", "width": 180},
        {"label": "Invoice Row", "fieldname": "sales_invoice_row", "fieldtype": "Int", "width": 90},
        {"label": "Currency", "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 90},
    ]
