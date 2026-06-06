import math

import frappe
from frappe import _
from frappe.utils import flt, getdate


@frappe.whitelist()
def evaluate_sales_invoice_schemes(doc):
    invoice = _parse_doc(doc)
    return get_best_sales_invoice_scheme_suggestion(invoice)


def get_best_sales_invoice_scheme_suggestion(invoice):
    posting_date = _get_invoice_date(invoice)
    schemes = _get_active_schemes(invoice, posting_date)
    if not schemes:
        return None

    item_codes = [
        row.get("item_code")
        for row in invoice.get("items", [])
        if row.get("item_code")
    ]
    item_map = _get_item_map(item_codes)
    group_bounds = _get_item_group_bounds(schemes, item_map)
    evaluations = [
        evaluate_single_invoice_amount_scheme(scheme, invoice, item_map, group_bounds, posting_date)
        for scheme in schemes
    ]
    evaluations = [evaluation for evaluation in evaluations if flt(evaluation.get("eligible_amount")) > 0]
    if not evaluations:
        return None

    evaluations.sort(
        key=lambda row: (
            len(row.get("achieved_slabs") or []),
            flt(row.get("eligible_amount")),
            -flt(row.get("shortfall_amount")),
        ),
        reverse=True,
    )
    return evaluations[0]


def evaluate_single_invoice_amount_scheme(scheme, invoice, item_map, group_bounds, posting_date):
    eligible_rows = []
    eligible_amount = 0

    for row in invoice.get("items", []):
        item = item_map.get(row.get("item_code")) or {}
        if not _is_eligible_scheme_row(row, item, scheme, group_bounds):
            continue

        amount = _get_pre_gst_amount(row)
        eligible_amount += amount
        eligible_rows.append(
            {
                "idx": row.get("idx"),
                "item_code": row.get("item_code"),
                "item_name": row.get("item_name") or item.get("item_name"),
                "qty": flt(row.get("qty")),
                "rate": _get_pre_gst_rate(row),
                "amount": amount,
            }
        )

    achieved_slabs = [
        slab
        for slab in scheme.slabs
        if eligible_amount >= flt(slab["amount"])
    ]
    next_slab = next(
        (slab for slab in scheme.slabs if eligible_amount < flt(slab["amount"])),
        None,
    )

    return {
        "scheme_code": scheme.name,
        "scheme_name": scheme.scheme_name,
        "valid_from": str(scheme.valid_from),
        "valid_upto": str(scheme.valid_upto),
        "basis": scheme.calculation_basis,
        "is_in_period": True,
        "posting_date": str(posting_date),
        "eligible_amount": eligible_amount,
        "eligible_rows": eligible_rows,
        "achieved_slabs": achieved_slabs,
        "next_slab": next_slab,
        "shortfall_amount": flt(next_slab["amount"]) - eligible_amount if next_slab else 0,
        "suggestions": _build_quantity_suggestions(eligible_rows, next_slab, eligible_amount),
        "payment_timeline": _get_payment_timeline(),
        "notes": _get_scheme_notes(scheme),
    }


def _parse_doc(doc):
    if isinstance(doc, str):
        doc = frappe.parse_json(doc)
    if not isinstance(doc, dict):
        frappe.throw(_("Invalid Sales Invoice payload."))
    return frappe._dict(doc)


def _get_invoice_date(invoice):
    return getdate(invoice.get("posting_date") or invoice.get("transaction_date") or getdate())


def _get_active_schemes(invoice, posting_date):
    if not frappe.db.exists("DocType", "SNRG Scheme"):
        return []

    rows = frappe.get_all(
        "SNRG Scheme",
        filters={"disabled": 0, "scheme_type": "Single Invoice Amount Slab"},
        fields=["name", "company", "valid_from", "valid_upto", "modified"],
        order_by="modified desc",
    )
    company = invoice.get("company")
    active_scheme_names = []

    for row in rows:
        if row.company and company and row.company != company:
            continue
        if row.valid_from and getdate(row.valid_from) > posting_date:
            continue
        if row.valid_upto and getdate(row.valid_upto) < posting_date:
            continue
        active_scheme_names.append(row.name)

    return [_get_scheme_config(name) for name in active_scheme_names]


def _get_scheme_config(name):
    doc = frappe.get_doc("SNRG Scheme", name)
    slabs = [
        {"amount": flt(row.slab_amount), "reward": row.reward}
        for row in doc.slabs
        if flt(row.slab_amount) > 0 and row.reward
    ]
    slabs.sort(key=lambda row: row["amount"])

    return frappe._dict(
        name=doc.name,
        scheme_name=doc.scheme_name,
        valid_from=doc.valid_from,
        valid_upto=doc.valid_upto,
        calculation_basis=doc.calculation_basis,
        notes=doc.notes,
        eligible_items=[
            frappe._dict(item_code=row.item_code, uom=row.uom)
            for row in doc.eligible_items
            if row.item_code
        ],
        eligible_item_groups=[
            frappe._dict(item_group=row.item_group, uom=row.uom)
            for row in doc.eligible_item_groups
            if row.item_group
        ],
        excluded_items={row.item_code for row in doc.excluded_items if row.item_code},
        slabs=slabs,
    )


def _get_item_map(item_codes):
    item_codes = sorted(set(item_codes))
    if not item_codes:
        return {}

    rows = frappe.get_all(
        "Item",
        filters={"name": ["in", item_codes]},
        fields=["name", "item_name", "item_group", "description"],
    )
    return {row.name: row for row in rows}


def _get_item_group_bounds(schemes, item_map):
    group_names = {
        row.item_group
        for scheme in schemes
        for row in scheme.eligible_item_groups
        if row.item_group
    }
    group_names.update(
        item.get("item_group")
        for item in item_map.values()
        if item.get("item_group")
    )
    group_names = sorted(group_name for group_name in group_names if group_name)
    if not group_names:
        return {}

    rows = frappe.get_all(
        "Item Group",
        filters={"name": ["in", group_names]},
        fields=["name", "lft", "rgt"],
    )
    return {row.name: row for row in rows}


def _is_eligible_scheme_row(row, item, scheme, group_bounds):
    item_code = row.get("item_code")
    if not item_code:
        return False

    if item_code in scheme.excluded_items:
        return False

    row_uom = row.get("uom")
    if any(_matches_item_rule(rule, item_code, row_uom) for rule in scheme.eligible_items):
        return True

    item_group = item.get("item_group")
    if item_group and any(
        _matches_item_group_rule(rule, item_group, row_uom, group_bounds)
        for rule in scheme.eligible_item_groups
    ):
        return True

    return False


def _matches_item_rule(rule, item_code, row_uom):
    if rule.item_code != item_code:
        return False
    return not rule.uom or not row_uom or rule.uom == row_uom


def _matches_item_group_rule(rule, item_group, row_uom, group_bounds):
    if rule.uom and row_uom and rule.uom != row_uom:
        return False
    if rule.item_group == item_group:
        return True

    parent = group_bounds.get(rule.item_group)
    child = group_bounds.get(item_group)
    if not parent or not child:
        return False

    return flt(parent.lft) <= flt(child.lft) and flt(parent.rgt) >= flt(child.rgt)


def _get_pre_gst_amount(row):
    for fieldname in ("base_net_amount", "net_amount", "base_amount", "amount"):
        if row.get(fieldname) is not None:
            return flt(row.get(fieldname))
    return flt(row.get("qty")) * _get_pre_gst_rate(row)


def _get_pre_gst_rate(row):
    for fieldname in ("base_net_rate", "net_rate", "base_rate", "rate"):
        if row.get(fieldname) is not None:
            return flt(row.get(fieldname))
    return 0


def _build_quantity_suggestions(eligible_rows, next_slab, eligible_amount):
    if not next_slab:
        return []

    shortfall = flt(next_slab["amount"]) - eligible_amount
    if shortfall <= 0:
        return []

    suggestions = []
    for row in eligible_rows:
        rate = flt(row.get("rate"))
        if rate <= 0:
            continue

        extra_qty = int(math.ceil(shortfall / rate))
        if extra_qty <= 0:
            continue

        suggestions.append(
            {
                "item_code": row.get("item_code"),
                "item_name": row.get("item_name"),
                "current_qty": flt(row.get("qty")),
                "rate": rate,
                "extra_qty": extra_qty,
                "new_qty": flt(row.get("qty")) + extra_qty,
                "extra_amount": extra_qty * rate,
                "target_amount": flt(next_slab.get("amount")),
                "reward": next_slab.get("reward"),
            }
        )

    suggestions.sort(key=lambda row: (flt(row.get("extra_amount")), flt(row.get("extra_qty"))))
    return suggestions[:5]


def _get_scheme_notes(scheme):
    notes = [
        _("Eligibility is controlled by this SNRG Scheme master: included item codes, included item groups, and excluded item codes."),
        _("All scheme values are calculated before GST."),
    ]
    if scheme.notes:
        notes.append(frappe.utils.strip_html(scheme.notes))
    return notes


def _get_payment_timeline():
    return [
        {
            "payment_window": _("Advance or clear payment before 20 June 2026"),
            "reward_timeline": _("1st week of July"),
        },
        {
            "payment_window": _("Payment between 20 June 2026 and 20 July 2026"),
            "reward_timeline": _("1st week of August"),
        },
        {
            "payment_window": _("Payment between 21 July 2026 and 20 August 2026"),
            "reward_timeline": _("1st week of September"),
        },
        {
            "payment_window": _("Payment between 21 August 2026 and 31 August 2026"),
            "reward_timeline": _("3rd week of September"),
        },
        {
            "payment_window": _("Payment after 1 September 2026"),
            "reward_timeline": _("No scheme achieved"),
        },
    ]
