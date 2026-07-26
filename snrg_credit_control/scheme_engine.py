import math

import frappe
from frappe import _
from frappe.utils import flt, getdate


INVOICE_AMOUNT_SLAB = "Invoice Amount Slab"
PERIOD_CUMULATIVE_AMOUNT_SLAB = "Period Cumulative Amount Slab"
CATEGORY_TARGET_SLAB = "Period Cumulative Category Target Slab"
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
        scheme_types=(PERIOD_CUMULATIVE_AMOUNT_SLAB, CATEGORY_TARGET_SLAB),
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
def get_scheme_customer_progress(
    company=None,
    scheme=None,
    as_on_date=None,
    include_draft_quotations=0,
    include_submitted_quotations=0,
):
    as_on_date = getdate(as_on_date or getdate())
    quotation_docstatuses = _get_selected_quotation_docstatuses(
        include_draft_quotations,
        include_submitted_quotations,
    )
    schemes = _get_active_schemes(
        {"company": company},
        as_on_date,
        scheme_name=scheme,
        scheme_types=(PERIOD_CUMULATIVE_AMOUNT_SLAB, CATEGORY_TARGET_SLAB),
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
        quotation_rows = _get_scheme_quotation_item_rows(
            company=company or scheme_config.company,
            from_date=period_from,
            upto_date=period_upto,
            docstatuses=quotation_docstatuses,
        )
        quotation_rows = _exclude_invoiced_quotation_rows(quotation_rows)
        item_map = _get_item_map(
            [row.item_code for row in rows if row.item_code]
            + [row.item_code for row in quotation_rows if row.item_code]
        )
        group_bounds = _get_item_group_bounds([scheme_config], item_map)
        if scheme_config.scheme_type == CATEGORY_TARGET_SLAB:
            customer_rows = _evaluate_category_scheme_customers(
                scheme_config,
                rows,
                quotation_rows,
                item_map,
                group_bounds,
                as_on_date,
                period_from,
                period_upto,
            )
        else:
            customer_rows = _evaluate_scheme_customers(
                scheme_config,
                rows,
                quotation_rows,
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
                "scheme_type": scheme_config.scheme_type,
                "valid_from": str(scheme_config.valid_from),
                "valid_upto": str(scheme_config.valid_upto),
                "period_from": str(period_from),
                "period_upto": str(period_upto),
                "customer_count": len(customer_rows),
                "eligible_amount": sum(flt(row.get("eligible_amount")) for row in customer_rows),
                "quotation_amount": sum(flt(row.get("quotation_amount")) for row in customer_rows),
                "projected_amount": sum(flt(row.get("projected_amount")) for row in customer_rows),
                "categories": scheme_config.categories,
                "customers": customer_rows,
            }
        )

    return {
        "company": company,
        "scheme": scheme,
        "as_on_date": str(as_on_date),
        "quotation_docstatuses": quotation_docstatuses,
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
    quotation_rows=None,
):
    eligible_rows = []
    quotation_eligible_rows = []
    eligible_amount = 0
    quotation_amount = 0
    invoice_names = set()
    quotation_names = set()

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

    for row in quotation_rows or []:
        item = item_map.get(row.get("item_code")) or {}
        if not _is_eligible_scheme_row(row, item, scheme, group_bounds):
            continue

        amount = _get_scheme_amount(row, scheme.gst_treatment)
        quotation_amount += amount
        quotation_names.add(row.get("quotation"))
        quotation_eligible_rows.append(
            {
                "quotation": row.get("quotation"),
                "transaction_date": str(row.get("transaction_date") or ""),
                "quotation_status": _get_quotation_status(row.get("quotation_docstatus")),
                "customer": row.get("customer"),
                "customer_name": row.get("customer_name"),
                "item_code": row.get("item_code"),
                "item_name": row.get("item_name") or item.get("item_name"),
                "uom": row.get("uom"),
                "qty": flt(row.get("qty")),
                "rate": _get_pre_gst_rate(row),
                "amount": amount,
            }
        )

    projected_amount = eligible_amount + quotation_amount
    achieved_slabs, achieved_slab, next_slab = _get_slab_progress(scheme.slabs, eligible_amount)
    projected_slabs, projected_slab, projected_next_slab = _get_slab_progress(scheme.slabs, projected_amount)

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
        "invoice_amount": eligible_amount,
        "quotation_amount": quotation_amount,
        "projected_amount": projected_amount,
        "eligible_invoice_count": len(invoice_names),
        "eligible_quotation_count": len(quotation_names),
        "eligible_rows": eligible_rows,
        "quotation_rows": quotation_eligible_rows,
        "top_items": _summarize_eligible_items(eligible_rows),
        "projected_top_items": _summarize_eligible_items(eligible_rows + quotation_eligible_rows),
        "invoice_details": _summarize_eligible_invoices(eligible_rows),
        "quotation_details": _summarize_eligible_quotations(quotation_eligible_rows),
        "payment_summary": _summarize_scheme_payments(eligible_rows),
        "achieved_slabs": achieved_slabs,
        "achieved_slab": achieved_slab,
        "next_slab": next_slab,
        "shortfall_amount": flt(next_slab["amount"]) - eligible_amount if next_slab else 0,
        "projected_slabs": projected_slabs,
        "projected_slab": projected_slab,
        "projected_next_slab": projected_next_slab,
        "projected_shortfall_amount": flt(projected_next_slab["amount"]) - projected_amount if projected_next_slab else 0,
        "suggestions": _build_customer_quantity_suggestions(eligible_rows, next_slab, eligible_amount),
        "notes": _get_scheme_notes(scheme),
    }


def _evaluate_scheme_customers(
    scheme,
    rows,
    quotation_rows,
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

    for row in quotation_rows:
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
                "quotation_rows": [],
            },
        )
        customer_rows[customer]["customer_name"] = customer_rows[customer].get("customer_name") or row.get("customer_name")
        customer_rows[customer].setdefault("quotation_rows", []).append(row)

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
            quotation_rows=data.get("quotation_rows") or [],
        )
        if flt(result.get("projected_amount")) <= 0:
            continue

        result["customer"] = customer
        result["customer_name"] = data.get("customer_name")
        results.append(result)

    results.sort(key=lambda row: flt(row.get("projected_amount")), reverse=True)
    return results


def _evaluate_category_scheme_customers(
    scheme,
    rows,
    quotation_rows,
    item_map,
    group_bounds,
    as_on_date,
    period_from,
    period_upto,
):
    customer_rows = {}

    for row in rows:
        item = item_map.get(row.get("item_code")) or {}
        category = _get_scheme_row_category(row, item, scheme, group_bounds)
        if not category:
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
                "quotation_rows": [],
            },
        )["rows"].append((row, category))

    for row in quotation_rows:
        item = item_map.get(row.get("item_code")) or {}
        category = _get_scheme_row_category(row, item, scheme, group_bounds)
        if not category:
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
                "quotation_rows": [],
            },
        )
        customer_rows[customer]["customer_name"] = customer_rows[customer].get("customer_name") or row.get("customer_name")
        customer_rows[customer]["quotation_rows"].append((row, category))

    results = []
    for customer, data in customer_rows.items():
        result = evaluate_customer_category_scheme(
            scheme,
            data["rows"],
            data["quotation_rows"],
            item_map,
            as_on_date,
            period_from,
            period_upto,
        )
        if flt(result.get("projected_amount")) <= 0:
            continue

        result["customer"] = customer
        result["customer_name"] = data.get("customer_name")
        results.append(result)

    results.sort(key=lambda row: flt(row.get("projected_amount")), reverse=True)
    return results


def evaluate_customer_category_scheme(
    scheme,
    rows_with_category,
    quotation_rows_with_category,
    item_map,
    as_on_date,
    period_from,
    period_upto,
):
    eligible_rows = []
    quotation_eligible_rows = []
    category_amounts = {category: 0 for category in scheme.categories}
    quotation_category_amounts = {category: 0 for category in scheme.categories}
    invoice_names = set()
    quotation_names = set()

    for row, category in rows_with_category:
        item = item_map.get(row.get("item_code")) or {}
        amount = _get_scheme_amount(row, scheme.gst_treatment)
        category_amounts[category] = flt(category_amounts.get(category)) + amount
        invoice_names.add(row.get("sales_invoice"))
        eligible_rows.append(_build_scheme_detail_row(row, item, amount, category=category))

    for row, category in quotation_rows_with_category:
        item = item_map.get(row.get("item_code")) or {}
        amount = _get_scheme_amount(row, scheme.gst_treatment)
        quotation_category_amounts[category] = flt(quotation_category_amounts.get(category)) + amount
        quotation_names.add(row.get("quotation"))
        quotation_eligible_rows.append(_build_scheme_detail_row(row, item, amount, category=category, is_quotation=True))

    projected_category_amounts = {
        category: flt(category_amounts.get(category)) + flt(quotation_category_amounts.get(category))
        for category in scheme.categories
    }
    eligible_amount = sum(flt(value) for value in category_amounts.values())
    quotation_amount = sum(flt(value) for value in quotation_category_amounts.values())
    projected_amount = eligible_amount + quotation_amount
    achieved_slabs, next_slab = _get_category_slab_progress(scheme.category_slabs, category_amounts, eligible_amount)
    projected_slabs, projected_next_slab = _get_category_slab_progress(
        scheme.category_slabs,
        projected_category_amounts,
        projected_amount,
    )

    achieved_rewards = [slab["reward"] for slab in achieved_slabs]
    projected_rewards = [slab["reward"] for slab in projected_slabs]

    return {
        "scheme_code": scheme.name,
        "scheme_name": scheme.scheme_name,
        "scheme_type": scheme.scheme_type,
        "valid_from": str(scheme.valid_from),
        "valid_upto": str(scheme.valid_upto),
        "period_from": str(period_from),
        "period_upto": str(period_upto),
        "gst_treatment": scheme.gst_treatment,
        "posting_date": str(as_on_date),
        "eligible_amount": eligible_amount,
        "invoice_amount": eligible_amount,
        "quotation_amount": quotation_amount,
        "projected_amount": projected_amount,
        "category_amounts": category_amounts,
        "quotation_category_amounts": quotation_category_amounts,
        "projected_category_amounts": projected_category_amounts,
        "category_count": _count_categories_for_slab(category_amounts, achieved_slabs[-1] if achieved_slabs else None),
        "projected_category_count": _count_categories_for_slab(projected_category_amounts, projected_slabs[-1] if projected_slabs else None),
        "eligible_invoice_count": len(invoice_names),
        "eligible_quotation_count": len(quotation_names),
        "eligible_rows": eligible_rows,
        "quotation_rows": quotation_eligible_rows,
        "top_items": _summarize_eligible_items(eligible_rows),
        "projected_top_items": _summarize_eligible_items(eligible_rows + quotation_eligible_rows),
        "invoice_details": _summarize_eligible_invoices(eligible_rows),
        "quotation_details": _summarize_eligible_quotations(quotation_eligible_rows),
        "payment_summary": _summarize_scheme_payments(eligible_rows),
        "achieved_slabs": achieved_slabs,
        "achieved_slab": achieved_slabs[-1] if achieved_slabs else None,
        "achieved_rewards": achieved_rewards,
        "next_slab": next_slab,
        "shortfall_amount": _get_category_total_shortfall(next_slab, eligible_amount),
        "category_shortfalls": _get_category_shortfalls(next_slab, category_amounts),
        "projected_slabs": projected_slabs,
        "projected_slab": projected_slabs[-1] if projected_slabs else None,
        "projected_rewards": projected_rewards,
        "projected_next_slab": projected_next_slab,
        "projected_shortfall_amount": _get_category_total_shortfall(projected_next_slab, projected_amount),
        "projected_category_shortfalls": _get_category_shortfalls(projected_next_slab, projected_category_amounts),
        "notes": _get_scheme_notes(scheme),
    }


def _build_scheme_detail_row(row, item, amount, category=None, is_quotation=False):
    detail = {
        "item_code": row.get("item_code"),
        "item_name": row.get("item_name") or item.get("item_name"),
        "uom": row.get("uom"),
        "qty": flt(row.get("qty")),
        "rate": _get_pre_gst_rate(row),
        "amount": amount,
        "category": category,
    }
    if is_quotation:
        detail.update(
            {
                "quotation": row.get("quotation"),
                "transaction_date": str(row.get("transaction_date") or ""),
                "quotation_status": _get_quotation_status(row.get("quotation_docstatus")),
                "customer": row.get("customer"),
                "customer_name": row.get("customer_name"),
            }
        )
    else:
        detail.update(
            {
                "sales_invoice": row.get("sales_invoice"),
                "posting_date": str(row.get("posting_date") or ""),
                "invoice_grand_total": flt(row.get("invoice_grand_total")),
                "invoice_outstanding_amount": flt(row.get("invoice_outstanding_amount")),
            }
        )
    return detail


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
    categories = []

    def add_category(category):
        category = (category or "").strip()
        if category and category not in categories:
            categories.append(category)
        return category

    for row in doc.get("category_rules", []):
        add_category(row.category)

    category_slab_groups = {}
    for row in doc.get("category_slabs", []):
        category = add_category(row.category)
        if not category or not row.slab_id or flt(row.total_target) <= 0 or not row.reward:
            continue

        slab = category_slab_groups.setdefault(
            row.slab_id,
            {
                "amount": flt(row.total_target),
                "total_target": flt(row.total_target),
                "targets": {},
                "minimum_categories_required": int(flt(row.minimum_categories_required) or 2),
                "reward": row.reward,
            },
        )
        slab["targets"][category] = flt(row.category_target)

    category_slabs = sorted(category_slab_groups.values(), key=lambda row: row["total_target"])

    return frappe._dict(
        name=doc.name,
        company=doc.company,
        scheme_name=doc.scheme_name,
        scheme_type=doc.scheme_type,
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
        categories=categories,
        category_rules=[
            frappe._dict(
                category=(row.category or "").strip(),
                apply_on=row.apply_on,
                item_code=row.item_code,
                item_group=row.item_group,
                uom=row.uom,
                exclude=frappe.utils.cint(row.exclude),
            )
            for row in doc.get("category_rules", [])
            if row.category
        ],
        category_slabs=category_slabs,
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
        "coalesce(si.is_return, 0) = 0",
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
            gross_amount_fields=_get_optional_item_gross_amount_fields("Sales Invoice Item", "sii"),
        ),
        values,
        as_dict=True,
    )


def _get_scheme_invoice_item_rows(company, from_date, upto_date):
    conditions = [
        "si.docstatus = 1",
        "coalesce(si.is_return, 0) = 0",
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
            gross_amount_fields=_get_optional_item_gross_amount_fields("Sales Invoice Item", "sii"),
        ),
        values,
        as_dict=True,
    )


def _get_scheme_quotation_item_rows(company, from_date, upto_date, docstatuses):
    if not docstatuses:
        return []

    conditions = [
        "q.quotation_to = 'Customer'",
        "q.docstatus in %(docstatuses)s",
        "q.transaction_date between %(from_date)s and %(upto_date)s",
    ]
    values = {
        "company": company,
        "from_date": from_date,
        "upto_date": upto_date,
        "docstatuses": tuple(docstatuses),
    }

    if company:
        conditions.append("q.company = %(company)s")

    return frappe.db.sql(
        """
        select
            qi.name as quotation_item,
            qi.parent as quotation,
            q.transaction_date,
            q.docstatus as quotation_docstatus,
            q.party_name as customer,
            q.customer_name,
            qi.idx,
            qi.item_code,
            qi.item_name,
            qi.description,
            qi.uom,
            qi.qty,
            qi.base_net_rate,
            qi.net_rate,
            qi.base_rate,
            qi.rate,
            {gross_amount_fields}
            qi.base_net_amount,
            qi.net_amount,
            qi.base_amount,
            qi.amount
        from `tabQuotation Item` qi
        inner join `tabQuotation` q on q.name = qi.parent
        where {conditions}
        order by q.customer_name asc, q.transaction_date desc, qi.idx asc
        """.format(
            conditions=" and ".join(conditions),
            gross_amount_fields=_get_optional_item_gross_amount_fields("Quotation Item", "qi"),
        ),
        values,
        as_dict=True,
    )


def _exclude_invoiced_quotation_rows(rows):
    quotation_names = sorted({row.get("quotation") for row in rows if row.get("quotation")})
    if not quotation_names:
        return rows

    invoiced_links = _get_invoiced_quotation_links(quotation_names)
    if not invoiced_links["items"] and not invoiced_links["item_codes"]:
        return rows

    filtered_rows = []
    for row in rows:
        quotation = row.get("quotation")
        quotation_item = row.get("quotation_item")
        item_code = row.get("item_code")

        if quotation_item and (quotation, quotation_item) in invoiced_links["items"]:
            continue
        if (quotation, item_code) in invoiced_links["item_codes"]:
            continue

        filtered_rows.append(row)

    return filtered_rows


def _get_invoiced_quotation_links(quotation_names):
    quotation_fieldname, detail_fieldname, has_prevdoc_doctype = _get_sales_order_item_quotation_link_config()
    invoice_item_link_fieldname = _get_sales_invoice_item_link_config()
    if not quotation_fieldname or not quotation_names:
        return {"items": set(), "item_codes": set()}

    detail_select = f"soi.{detail_fieldname} as quotation_item" if detail_fieldname else "NULL as quotation_item"
    prevdoc_condition = "and soi.prevdoc_doctype = 'Quotation'" if has_prevdoc_doctype else ""
    invoice_join_condition = (
        f"sii.{invoice_item_link_fieldname} = soi.name"
        if invoice_item_link_fieldname
        else "sii.sales_order = soi.parent and sii.item_code = soi.item_code"
    )

    rows = frappe.db.sql(
        f"""
        select distinct
            soi.{quotation_fieldname} as quotation,
            soi.item_code,
            {detail_select}
        from `tabSales Order Item` soi
        inner join `tabSales Order` so on so.name = soi.parent
        inner join `tabSales Invoice Item` sii on {invoice_join_condition}
        inner join `tabSales Invoice` si on si.name = sii.parent
        where soi.{quotation_fieldname} in %(quotation_names)s
          {prevdoc_condition}
          and so.docstatus = 1
          and si.docstatus = 1
          and coalesce(si.is_return, 0) = 0
        """,
        {"quotation_names": tuple(quotation_names)},
        as_dict=True,
    )

    return {
        "items": {
            (row.get("quotation"), row.get("quotation_item"))
            for row in rows
            if row.get("quotation") and row.get("quotation_item")
        },
        "item_codes": {
            (row.get("quotation"), row.get("item_code"))
            for row in rows
            if row.get("quotation") and row.get("item_code")
        },
    }


def _get_sales_order_item_quotation_link_config():
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


def _get_item_group_bounds(schemes, item_map):
    group_names = {
        row.item_group
        for scheme in schemes
        for row in scheme.eligible_item_groups
        if row.item_group
    }
    group_names.update(
        row.item_group
        for scheme in schemes
        for row in getattr(scheme, "category_rules", [])
        if row.get("apply_on") == "Item Group" and row.get("item_group")
    )
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


def _get_scheme_row_category(row, item, scheme, group_bounds):
    item_code = row.get("item_code")
    if not item_code or item_code in scheme.excluded_items:
        return None

    row_uom = row.get("uom")
    item_group = item.get("item_group")

    has_scheme_item_filters = bool(scheme.eligible_items or scheme.eligible_item_groups)
    if has_scheme_item_filters and not _is_eligible_scheme_row(row, item, scheme, group_bounds):
        return None

    for rule in scheme.category_rules:
        if not rule.exclude:
            continue
        if _matches_category_rule(rule, item_code, item_group, row_uom, group_bounds):
            return None

    for rule in scheme.category_rules:
        if rule.exclude:
            continue
        if _matches_category_rule(rule, item_code, item_group, row_uom, group_bounds):
            return rule.category

    return None


def _matches_category_rule(rule, item_code, item_group, row_uom, group_bounds):
    if rule.uom and row_uom and rule.uom != row_uom:
        return False
    if rule.apply_on == "Item Code":
        return rule.item_code == item_code
    if rule.apply_on == "Item Group" and item_group:
        return _matches_item_group_rule(rule, item_group, row_uom, group_bounds)
    return False


def _get_category_slab_progress(slabs, category_amounts, total_amount):
    achieved = []
    next_slab = None

    for slab in slabs:
        qualified_categories = _count_categories_for_slab(category_amounts, slab)
        qualifies = (
            flt(total_amount) >= flt(slab["total_target"])
            and qualified_categories >= int(slab.get("minimum_categories_required") or 0)
        )
        enriched = dict(slab)
        enriched["qualified_categories"] = qualified_categories
        if qualifies:
            achieved.append(enriched)
        elif next_slab is None:
            next_slab = enriched

    return achieved, next_slab


def _count_categories_for_slab(category_amounts, slab):
    if not slab:
        return 0
    return sum(
        1
        for category, target in (slab.get("targets") or {}).items()
        if flt(target) > 0 and flt(category_amounts.get(category)) >= flt(target)
    )


def _get_category_total_shortfall(slab, total_amount):
    if not slab:
        return 0
    return max(flt(slab.get("total_target")) - flt(total_amount), 0)


def _get_category_shortfalls(slab, category_amounts):
    if not slab:
        return {}
    return {
        category: max(flt(target) - flt(category_amounts.get(category)), 0)
        for category, target in (slab.get("targets") or {}).items()
    }


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


def _get_optional_item_gross_amount_fields(doctype, alias):
    fields = []
    if frappe.db.has_column(doctype, "base_gross_amount"):
        fields.append(f"{alias}.base_gross_amount")
    if frappe.db.has_column(doctype, "gross_amount"):
        fields.append(f"{alias}.gross_amount")
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


def _get_selected_quotation_docstatuses(include_draft_quotations, include_submitted_quotations):
    docstatuses = []
    if frappe.utils.cint(include_draft_quotations):
        docstatuses.append(0)
    if frappe.utils.cint(include_submitted_quotations):
        docstatuses.append(1)
    return docstatuses


def _get_quotation_status(docstatus):
    docstatus = frappe.utils.cint(docstatus)
    if docstatus == 0:
        return "Draft"
    if docstatus == 1:
        return "Submitted"
    return "Unknown"


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


def _summarize_eligible_quotations(eligible_rows):
    summary = {}

    for row in eligible_rows:
        quotation = row.get("quotation")
        if not quotation:
            continue

        current = summary.setdefault(
            quotation,
            {
                "quotation": quotation,
                "transaction_date": row.get("transaction_date"),
                "quotation_status": row.get("quotation_status"),
                "qty": 0,
                "amount": 0,
                "item_count": set(),
            },
        )
        current["qty"] += flt(row.get("qty"))
        current["amount"] += flt(row.get("amount"))
        if row.get("item_code"):
            current["item_count"].add(row.get("item_code"))

    rows = []
    for row in summary.values():
        rows.append(
            {
                "quotation": row["quotation"],
                "transaction_date": row["transaction_date"],
                "quotation_status": row["quotation_status"],
                "qty": row["qty"],
                "amount": row["amount"],
                "item_count": len(row["item_count"]),
            }
        )

    rows.sort(key=lambda row: (row.get("transaction_date") or "", flt(row.get("amount"))), reverse=True)
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
