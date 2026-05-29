import frappe
from frappe import _
from frappe.utils import flt, getdate


MINIMUM_SELLING_PRICE_LIST = "Minimum Selling Rate"
INVALID_MINIMUM_RATE = object()


def validate_minimum_selling_rates(doc):
    """Block negative rates and stock item rates below the controlled minimum price list."""
    items = [row for row in (doc.get("items") or []) if row.get("item_code")]
    if not items:
        return

    item_codes = sorted({row.item_code for row in items})
    item_map = _get_item_map(item_codes)
    stock_item_codes = sorted(
        item_code
        for item_code, item in item_map.items()
        if flt(item.get("is_stock_item"))
    )
    price_map, invalid_price_keys = _get_minimum_price_map(stock_item_codes, doc)
    violations = []

    for row in items:
        rate = flt(row.get("rate"))
        item = item_map.get(row.item_code) or {}
        is_stock_item = flt(item.get("is_stock_item"))

        if rate < 0:
            violations.append(
                _build_violation(
                    row=row,
                    entered_rate=rate,
                    minimum_rate=None,
                    issue=_("Negative rate is not allowed."),
                )
            )
            continue

        if not is_stock_item:
            continue

        minimum_rate = _get_minimum_rate_for_row(row, item, price_map, invalid_price_keys)
        if minimum_rate is INVALID_MINIMUM_RATE:
            violations.append(
                _build_violation(
                    row=row,
                    entered_rate=rate,
                    minimum_rate=None,
                    issue=_("Minimum selling rate is not configured properly."),
                )
            )
            continue

        if minimum_rate is None:
            violations.append(
                _build_violation(
                    row=row,
                    entered_rate=rate,
                    minimum_rate=None,
                    issue=_("Minimum selling rate is missing."),
                )
            )
            continue

        if rate < minimum_rate:
            violations.append(
                _build_violation(
                    row=row,
                    entered_rate=rate,
                    minimum_rate=minimum_rate,
                    issue=_("Rate is below minimum selling rate."),
                )
            )

    if violations:
        _throw_minimum_rate_error(doc, violations)


def _get_item_map(item_codes):
    if not item_codes:
        return {}

    rows = frappe.get_all(
        "Item",
        filters={"name": ["in", item_codes]},
        fields=["name", "is_stock_item", "stock_uom"],
    )
    return {row.name: row for row in rows}


def _get_minimum_price_map(item_codes, doc):
    if not item_codes:
        return {}, set()

    currency = doc.get("currency")
    filters = {
        "price_list": MINIMUM_SELLING_PRICE_LIST,
        "item_code": ["in", item_codes],
    }
    if currency:
        filters["currency"] = currency

    rows = frappe.get_all(
        "Item Price",
        filters=filters,
        fields=[
            "item_code",
            "uom",
            "price_list_rate",
            "valid_from",
            "valid_upto",
        ],
    )
    posting_date = _get_document_date(doc)
    price_map = {}
    invalid_price_keys = set()

    for row in rows:
        if not _is_price_active(row, posting_date):
            continue

        key = (row.item_code, row.uom or "")
        current_rate = price_map.get(key)
        row_rate = flt(row.price_list_rate)
        if row_rate <= 0:
            invalid_price_keys.add(key)
            continue
        if current_rate is None or row_rate > current_rate:
            price_map[key] = row_rate

    return price_map, invalid_price_keys


def _get_document_date(doc):
    for fieldname in ("transaction_date", "posting_date"):
        if doc.get(fieldname):
            return getdate(doc.get(fieldname))
    return getdate()


def _is_price_active(price_row, posting_date):
    valid_from = price_row.get("valid_from")
    valid_upto = price_row.get("valid_upto")

    if valid_from and getdate(valid_from) > posting_date:
        return False
    if valid_upto and getdate(valid_upto) < posting_date:
        return False
    return True


def _get_minimum_rate_for_row(row, item, price_map, invalid_price_keys):
    row_uom = row.get("uom") or item.get("stock_uom") or ""
    exact_key = (row.item_code, row_uom)
    if exact_key in invalid_price_keys:
        return INVALID_MINIMUM_RATE

    exact_rate = price_map.get((row.item_code, row_uom))
    if exact_rate is not None:
        return flt(exact_rate)

    stock_uom = item.get("stock_uom") or ""
    stock_uom_key = (row.item_code, stock_uom)
    blank_uom_key = (row.item_code, "")
    if stock_uom_key in invalid_price_keys or blank_uom_key in invalid_price_keys:
        return INVALID_MINIMUM_RATE

    stock_uom_rate = price_map.get(stock_uom_key)
    if stock_uom_rate is None:
        stock_uom_rate = price_map.get(blank_uom_key)
    if stock_uom_rate is None:
        return None

    conversion_factor = flt(row.get("conversion_factor")) or 1
    return flt(stock_uom_rate) * conversion_factor


def _build_violation(row, entered_rate, minimum_rate, issue):
    return {
        "idx": row.get("idx"),
        "item_code": row.get("item_code"),
        "uom": row.get("uom"),
        "entered_rate": entered_rate,
        "minimum_rate": minimum_rate,
        "issue": issue,
    }


def _throw_minimum_rate_error(doc, violations):
    currency = doc.get("currency")
    rows_html = "".join(_format_violation_row(row, currency) for row in violations)
    message = _(
        "Some item rates do not meet the controlled minimum selling rate from Price List {0}."
    ).format(frappe.bold(MINIMUM_SELLING_PRICE_LIST))

    frappe.throw(
        """
        <p>{message}</p>
        <table class="table table-bordered table-condensed">
            <thead>
                <tr>
                    <th>{row_label}</th>
                    <th>{item_label}</th>
                    <th>{uom_label}</th>
                    <th>{rate_label}</th>
                    <th>{minimum_label}</th>
                    <th>{issue_label}</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        """.format(
            message=message,
            row_label=_("Row"),
            item_label=_("Item"),
            uom_label=_("UOM"),
            rate_label=_("Entered Rate"),
            minimum_label=_("Minimum Rate"),
            issue_label=_("Issue"),
            rows=rows_html,
        ),
        title=_("Minimum Selling Rate Check Failed"),
    )


def _format_violation_row(row, currency):
    return """
        <tr>
            <td>{idx}</td>
            <td>{item_code}</td>
            <td>{uom}</td>
            <td class="text-right">{entered_rate}</td>
            <td class="text-right">{minimum_rate}</td>
            <td>{issue}</td>
        </tr>
    """.format(
        idx=frappe.utils.escape_html(row.get("idx") or ""),
        item_code=frappe.utils.escape_html(row.get("item_code") or ""),
        uom=frappe.utils.escape_html(row.get("uom") or ""),
        entered_rate=frappe.utils.fmt_money(row.get("entered_rate"), currency=currency),
        minimum_rate=(
            frappe.utils.fmt_money(row.get("minimum_rate"), currency=currency)
            if row.get("minimum_rate") is not None
            else "-"
        ),
        issue=frappe.utils.escape_html(row.get("issue") or ""),
    )
