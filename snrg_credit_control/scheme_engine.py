import math

import frappe
from frappe import _
from frappe.utils import flt, getdate


INVOICE_AMOUNT_SLAB = "Invoice Amount Slab"
PERIOD_CUMULATIVE_AMOUNT_SLAB = "Period Cumulative Amount Slab"
LEGACY_SINGLE_INVOICE_AMOUNT_SLAB = "Single Invoice Amount Slab"
GST_EXCLUDED = "Excluded"
GST_INCLUDED = "Included"
LEGACY_BEFORE_GST = "Eligible Item Value Before GST"


@frappe.whitelist()
def evaluate_sales_invoice_schemes(doc):
    invoice = _parse_doc(doc)
    return get_best_sales_invoice_scheme_suggestion(invoice)


@frappe.whitelist()
def get_customer_scheme_suggestions(customer, company=None, scheme=None, as_on_date=None):
    if not customer:
        frappe.throw(_("Customer is required."))

    as_on_date = getdate(as_on_date or getdate())
    schemes = _get_active_schemes(
        {"company": company},
        as_on_date,
        scheme_name=scheme,
        scheme_types=(PERIOD_CUMULATIVE_AMOUNT_SLAB,),
    )
    suggestions = []

    for scheme_config in schemes:
        period_from = getdate(scheme_config.valid_from)
        period_upto = min(getdate(scheme_config.valid_upto), as_on_date)
        rows = _get_customer_invoice_item_rows(
            customer=customer,
            company=company or scheme_config.company,
            from_date=period_from,
            upto_date=period_upto,
        )
        item_map = _get_item_map([row.item_code for row in rows if row.item_code])
        group_bounds = _get_item_group_bounds([scheme_config], item_map)
        suggestions.append(
            evaluate_customer_amount_scheme(
                scheme_config,
                rows,
                item_map,
                group_bounds,
                as_on_date,
                period_from,
                period_upto,
            )
        )

    suggestions.sort(
        key=lambda row: (
            flt((row.get("achieved_slab") or {}).get("amount")),
            flt(row.get("eligible_amount")),
            -flt(row.get("shortfall_amount")),
        ),
        reverse=True,
    )

    return {
        "customer": customer,
        "company": company,
        "as_on_date": str(as_on_date),
        "suggestions": suggestions,
    }


@frappe.whitelist()
def get_scheme_customer_progress(company=None, scheme=None, as_on_date=None):
    as_on_date = getdate(as_on_date or getdate())
    schemes = _get_active_schemes(
        {"company": company},
        as_on_date,
        scheme_name=scheme,
        scheme_types=(PERIOD_CUMULATIVE_AMOUNT_SLAB,),
    )
    scheme_results = []

    for scheme_config in schemes:
        period_from = getdate(scheme_config.valid_from)
        period_upto = min(getdate(scheme_config.valid_upto), as_on_date)
        rows = _get_scheme_invoice_item_rows(
            company=company or scheme_config.company,
            from_date=period_from,
            upto_date=period_upto,
        )
        item_map = _get_item_map([row.item_code for row in rows if row.item_code])
        group_bounds = _get_item_group_bounds([scheme_config], item_map)
        customer_rows = _evaluate_scheme_customers(
            scheme_config,
            rows,
            item_map,
            group_bounds,
            as_on_date,
            period_from,
            period_upto,
        )

        if not customer_rows:
            continue

        scheme_results.append(
            {
                "scheme_code": scheme_config.name,
                "scheme_name": scheme_config.scheme_name,
                "valid_from": str(scheme_config.valid_from),
                "valid_upto": str(scheme_config.valid_upto),
                "period_from": str(period_from),
                "period_upto": str(period_upto),
                "customer_count": len(customer_rows),
                "eligible_amount": sum(flt(row.get("eligible_amount")) for row in customer_rows),
                "customers": customer_rows,
            }
        )

    return {
        "company": company,
        "scheme": scheme,
        "as_on_date": str(as_on_date),
        "schemes": scheme_results,
    }


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
            flt((row.get("achieved_slab") or {}).get("amount")),
            flt(row.get("eligible_amount")),
            -flt(row.get("shortfall_amount")),
        ),
        reverse=True,
    )
    return evaluations[0]


def evaluate_customer_amount_scheme(
    scheme,
    rows,
    item_map,
    group_bounds,
    as_on_date,
    period_from,
    period_upto,
):
    eligible_rows = []
    eligible_amount = 0
    invoice_names = set()

    for row in rows:
        item = item_map.get(row.get("item_code")) or {}
        if not _is_eligible_scheme_row(row, item, scheme, group_bounds):
            continue

        amount = _get_scheme_amount(row, scheme.gst_treatment)
        eligible_amount += amount
        invoice_names.add(row.get("sales_invoice"))
        eligible_rows.append(
            {
                "sales_invoice": row.get("sales_invoice"),
                "posting_date": str(row.get("posting_date") or ""),
                "invoice_grand_total": flt(row.get("invoice_grand_total")),
                "invoice_outstanding_amount": flt(row.get("invoice_outstanding_amount")),
                "item_code": row.get("item_code"),
                "item_name": row.get("item_name") or item.get("item_name"),
                "uom": row.get("uom"),
                "qty": flt(row.get("qty")),
                "rate": _get_pre_gst_rate(row),
                "amount": amount,
            }
        )

    achieved_slabs, achieved_slab, next_slab = _get_slab_progress(scheme.slabs, eligible_amount)

    return {
        "scheme_code": scheme.name,
        "scheme_name": scheme.scheme_name,
        "valid_from": str(scheme.valid_from),
        "valid_upto": str(scheme.valid_upto),
        "period_from": str(period_from),
        "period_upto": str(period_upto),
        "gst_treatment": scheme.gst_treatment,
        "posting_date": str(as_on_date),
        "eligible_amount": eligible_amount,
        "eligible_invoice_count": len(invoice_names),
        "eligible_rows": eligible_rows,
        "top_items": _summarize_eligible_items(eligible_rows),
        "invoice_details": _summarize_eligible_invoices(eligible_rows),
        "payment_summary": _summarize_scheme_payments(eligible_rows),
        "achieved_slabs": achieved_slabs,
        "achieved_slab": achieved_slab,
        "next_slab": next_slab,
        "shortfall_amount": flt(next_slab["amount"]) - eligible_amount if next_slab else 0,
        "suggestions": _build_customer_quantity_suggestions(eligible_rows, next_slab, eligible_amount),
        "notes": _get_scheme_notes(scheme),
    }


def _evaluate_scheme_customers(
    scheme,
    rows,
    item_map,
    group_bounds,
    as_on_date,
    period_from,
    period_upto,
):
    customer_rows = {}

    for row in rows:
        item = item_map.get(row.get("item_code")) or {}
        if not _is_eligible_scheme_row(row, item, scheme, group_bounds):
            continue

        customer = row.get("customer")
        if not customer:
            continue

        customer_rows.setdefault(
            customer,
            {
                "customer": customer,
                "customer_name": row.get("customer_name"),
                "rows": [],
            },
        )["rows"].append(row)

    results = []
    for customer, data in customer_rows.items():
        result = evaluate_customer_amount_scheme(
            scheme,
            data["rows"],
            item_map,
            group_bounds,
            as_on_date,
            period_from,
            period_upto,
        )
        if flt(result.get("eligible_amount")) <= 0:
            continue

        result["customer"] = customer
        result["customer_name"] = data.get("customer_name")
        results.append(result)

    results.sort(key=lambda row: flt(row.get("eligible_amount")), reverse=True)
    return results


def evaluate_single_invoice_amount_scheme(scheme, invoice, item_map, group_bounds, posting_date):
    eligible_rows = []
    eligible_amount = 0

    for row in invoice.get("items", []):
        item = item_map.get(row.get("item_code")) or {}
        if not _is_eligible_scheme_row(row, item, scheme, group_bounds):
            continue

        amount = _get_scheme_amount(row, scheme.gst_treatment)
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

    achieved_slabs, achieved_slab, next_slab = _get_slab_progress(scheme.slabs, eligible_amount)

    return {
        "scheme_code": scheme.name,
        "scheme_name": scheme.scheme_name,
        "valid_from": str(scheme.valid_from),
        "valid_upto": str(scheme.valid_upto),
        "gst_treatment": scheme.gst_treatment,
        "is_in_period": True,
        "posting_date": str(posting_date),
        "eligible_amount": eligible_amount,
        "eligible_rows": eligible_rows,
        "achieved_slabs": achieved_slabs,
        "achieved_slab": achieved_slab,
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


def _get_active_schemes_for_context(invoice, posting_date, scheme_name=None, scheme_types=None):
    if not frappe.db.exists("DocType", "SNRG Scheme"):
        return []

    scheme_types = tuple(scheme_types or (INVOICE_AMOUNT_SLAB, LEGACY_SINGLE_INVOICE_AMOUNT_SLAB))
    filters = {"disabled": 0, "scheme_type": ["in", scheme_types]}
    if scheme_name:
        filters["name"] = scheme_name

    rows = frappe.get_all(
        "SNRG Scheme",
        filters=filters,
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


def _get_active_schemes(invoice, posting_date, scheme_name=None, scheme_types=None):
    return _get_active_schemes_for_context(
        invoice,
        posting_date,
        scheme_name=scheme_name,
        scheme_types=scheme_types,
    )


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
        company=doc.company,
        scheme_name=doc.scheme_name,
        valid_from=doc.valid_from,
        valid_upto=doc.valid_upto,
        gst_treatment=_normalize_gst_treatment(doc.calculation_basis),
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


def _get_slab_progress(slabs, eligible_amount):
    achieved_slabs = [
        slab
        for slab in slabs
        if eligible_amount >= flt(slab["amount"])
    ]
    achieved_slab = achieved_slabs[-1] if achieved_slabs else None
    next_slab = next(
        (slab for slab in slabs if eligible_amount < flt(slab["amount"])),
        None,
    )
    return achieved_slabs, achieved_slab, next_slab


def _get_customer_invoice_item_rows(customer, company, from_date, upto_date):
    conditions = [
        "si.docstatus = 1",
        "si.customer = %(customer)s",
        "si.posting_date between %(from_date)s and %(upto_date)s",
    ]
    values = {
        "customer": customer,
        "company": company,
        "from_date": from_date,
        "upto_date": upto_date,
    }

    if company:
        conditions.append("si.company = %(company)s")

    return frappe.db.sql(
        """
        select
            sii.parent as sales_invoice,
            si.posting_date,
            si.customer,
            si.customer_name,
            si.grand_total as invoice_grand_total,
            si.outstanding_amount as invoice_outstanding_amount,
            sii.idx,
            sii.item_code,
            sii.item_name,
            sii.description,
            sii.uom,
            sii.qty,
            sii.base_net_rate,
            sii.net_rate,
            sii.base_rate,
            sii.rate,
            {gross_amount_fields}
            sii.base_net_amount,
            sii.net_amount,
            sii.base_amount,
            sii.amount
        from `tabSales Invoice Item` sii
        inner join `tabSales Invoice` si on si.name = sii.parent
        where {conditions}
        order by si.posting_date desc, sii.idx asc
        """.format(
            conditions=" and ".join(conditions),
            gross_amount_fields=_get_optional_item_gross_amount_fields(),
        ),
        values,
        as_dict=True,
    )


def _get_scheme_invoice_item_rows(company, from_date, upto_date):
    conditions = [
        "si.docstatus = 1",
        "si.posting_date between %(from_date)s and %(upto_date)s",
    ]
    values = {
        "company": company,
        "from_date": from_date,
        "upto_date": upto_date,
    }

    if company:
        conditions.append("si.company = %(company)s")

    return frappe.db.sql(
        """
        select
            sii.parent as sales_invoice,
            si.posting_date,
            si.customer,
            si.customer_name,
            si.grand_total as invoice_grand_total,
            si.outstanding_amount as invoice_outstanding_amount,
            sii.idx,
            sii.item_code,
            sii.item_name,
            sii.description,
            sii.uom,
            sii.qty,
            sii.base_net_rate,
            sii.net_rate,
            sii.base_rate,
            sii.rate,
            {gross_amount_fields}
            sii.base_net_amount,
            sii.net_amount,
            sii.base_amount,
            sii.amount
        from `tabSales Invoice Item` sii
        inner join `tabSales Invoice` si on si.name = sii.parent
        where {conditions}
        order by si.customer_name asc, si.posting_date desc, sii.idx asc
        """.format(
            conditions=" and ".join(conditions),
            gross_amount_fields=_get_optional_item_gross_amount_fields(),
        ),
        values,
        as_dict=True,
    )


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


def _get_scheme_amount(row, gst_treatment):
    if gst_treatment == GST_INCLUDED:
        for fieldname in ("base_gross_amount", "gross_amount", "base_amount", "amount"):
            if row.get(fieldname) is not None:
                return flt(row.get(fieldname))

    return _get_pre_gst_amount(row)


def _get_optional_item_gross_amount_fields():
    fields = []
    if frappe.db.has_column("Sales Invoice Item", "base_gross_amount"):
        fields.append("sii.base_gross_amount")
    if frappe.db.has_column("Sales Invoice Item", "gross_amount"):
        fields.append("sii.gross_amount")
    if not fields:
        return ""
    return ",\n            ".join(fields) + ",\n            "


def _get_pre_gst_rate(row):
    for fieldname in ("base_net_rate", "net_rate", "base_rate", "rate"):
        if row.get(fieldname) is not None:
            return flt(row.get(fieldname))
    return 0


def _normalize_gst_treatment(value):
    if value == LEGACY_BEFORE_GST:
        return GST_EXCLUDED
    if value in (GST_EXCLUDED, GST_INCLUDED):
        return value
    return GST_EXCLUDED


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


def _build_customer_quantity_suggestions(eligible_rows, next_slab, eligible_amount):
    if not next_slab:
        return []

    item_summary = _summarize_eligible_items(eligible_rows)
    shortfall = flt(next_slab["amount"]) - eligible_amount
    if shortfall <= 0:
        return []

    suggestions = []
    for row in item_summary:
        rate = flt(row.get("average_rate"))
        if rate <= 0:
            continue

        extra_qty = int(math.ceil(shortfall / rate))
        suggestions.append(
            {
                "item_code": row.get("item_code"),
                "item_name": row.get("item_name"),
                "uom": row.get("uom"),
                "historical_qty": flt(row.get("qty")),
                "average_rate": rate,
                "extra_qty": extra_qty,
                "extra_amount": extra_qty * rate,
                "target_amount": flt(next_slab.get("amount")),
                "reward": next_slab.get("reward"),
            }
        )

    suggestions.sort(key=lambda row: (flt(row.get("extra_amount")), flt(row.get("extra_qty"))))
    return suggestions[:5]


def _summarize_eligible_items(eligible_rows):
    summary = {}

    for row in eligible_rows:
        key = (row.get("item_code"), row.get("uom"))
        if not key[0]:
            continue

        current = summary.setdefault(
            key,
            {
                "item_code": row.get("item_code"),
                "item_name": row.get("item_name"),
                "uom": row.get("uom"),
                "qty": 0,
                "amount": 0,
                "invoice_count": set(),
            },
        )
        current["qty"] += flt(row.get("qty"))
        current["amount"] += flt(row.get("amount"))
        if row.get("sales_invoice"):
            current["invoice_count"].add(row.get("sales_invoice"))

    rows = []
    for row in summary.values():
        qty = flt(row["qty"])
        amount = flt(row["amount"])
        rows.append(
            {
                "item_code": row["item_code"],
                "item_name": row["item_name"],
                "uom": row["uom"],
                "qty": qty,
                "amount": amount,
                "average_rate": amount / qty if qty else 0,
                "invoice_count": len(row["invoice_count"]),
            }
        )

    rows.sort(key=lambda row: flt(row.get("amount")), reverse=True)
    return rows[:10]


def _summarize_eligible_invoices(eligible_rows):
    summary = {}

    for row in eligible_rows:
        invoice = row.get("sales_invoice")
        if not invoice:
            continue

        current = summary.setdefault(
            invoice,
            {
                "sales_invoice": invoice,
                "posting_date": row.get("posting_date"),
                "qty": 0,
                "amount": 0,
                "invoice_grand_total": 0,
                "invoice_outstanding_amount": 0,
                "item_count": set(),
            },
        )
        current["qty"] += flt(row.get("qty"))
        current["amount"] += flt(row.get("amount"))
        current["invoice_grand_total"] = flt(row.get("invoice_grand_total"))
        current["invoice_outstanding_amount"] = flt(row.get("invoice_outstanding_amount"))
        if row.get("item_code"):
            current["item_count"].add(row.get("item_code"))

    rows = []
    for row in summary.values():
        payment = _get_invoice_payment_allocation(
            row["amount"],
            row["invoice_grand_total"],
            row["invoice_outstanding_amount"],
        )
        rows.append(
            {
                "sales_invoice": row["sales_invoice"],
                "posting_date": row["posting_date"],
                "qty": row["qty"],
                "amount": row["amount"],
                "paid_amount": payment["paid_amount"],
                "outstanding_amount": payment["outstanding_amount"],
                "payment_status": payment["payment_status"],
                "item_count": len(row["item_count"]),
            }
        )

    rows.sort(key=lambda row: (row.get("posting_date") or "", flt(row.get("amount"))), reverse=True)
    return rows


def _summarize_scheme_payments(eligible_rows):
    invoice_rows = _summarize_eligible_invoices(eligible_rows)
    paid_amount = sum(flt(row.get("paid_amount")) for row in invoice_rows)
    outstanding_amount = sum(flt(row.get("outstanding_amount")) for row in invoice_rows)
    eligible_amount = sum(flt(row.get("amount")) for row in invoice_rows)

    if not invoice_rows:
        payment_status = "No Invoices"
    elif outstanding_amount <= 0.01:
        payment_status = "Paid"
    elif paid_amount > 0:
        payment_status = "Partly Paid"
    else:
        payment_status = "Unpaid"

    return {
        "paid_amount": paid_amount,
        "outstanding_amount": outstanding_amount,
        "eligible_amount": eligible_amount,
        "payment_status": payment_status,
    }


def _get_invoice_payment_allocation(eligible_amount, invoice_grand_total, invoice_outstanding_amount):
    eligible_amount = flt(eligible_amount)
    invoice_grand_total = flt(invoice_grand_total)
    invoice_outstanding_amount = max(flt(invoice_outstanding_amount), 0)

    if invoice_grand_total <= 0:
        scheme_outstanding = min(invoice_outstanding_amount, eligible_amount)
    else:
        ratio = min(eligible_amount / invoice_grand_total, 1)
        scheme_outstanding = min(invoice_outstanding_amount * ratio, eligible_amount)

    paid_amount = max(eligible_amount - scheme_outstanding, 0)
    if scheme_outstanding <= 0.01:
        payment_status = "Paid"
    elif paid_amount > 0:
        payment_status = "Partly Paid"
    else:
        payment_status = "Unpaid"

    return {
        "paid_amount": paid_amount,
        "outstanding_amount": scheme_outstanding,
        "payment_status": payment_status,
    }


def _get_scheme_notes(scheme):
    notes = [
        _("Eligibility is controlled by this SNRG Scheme master: included item codes, included item groups, and excluded item codes."),
    ]
    if scheme.gst_treatment == GST_INCLUDED:
        notes.append(_("Scheme values include GST where item-level gross amounts are available."))
    else:
        notes.append(_("Scheme values are calculated with GST excluded."))
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
