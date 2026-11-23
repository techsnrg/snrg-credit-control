"""Review legacy scheme calculations without editing issued documents."""

import hashlib
import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate, now_datetime, today

from snrg_credit_control import scheme_engine as engine

DOCTYPE = "SNRG Historical Scheme Review"


def access():
    settings = frappe.conf.get("historical_scheme_review") or {}
    if not settings or frappe.session.user != settings.get("reviewer"):
        return None
    if "Scheme Manager" not in frappe.get_roles():
        return None
    until = settings.get("until")
    return {"until": until, "writable": not until or now_datetime() < get_datetime(until)}


def _scheme(name, write=False):
    permission = access()
    if not permission or (write and not permission["writable"]):
        frappe.throw(_("Historical Review is unavailable for this account or the review window has ended."), frappe.PermissionError)
    doc = frappe.get_doc("SNRG Scheme", name)
    doc.check_permission("read")
    if doc.disabled or doc.track_invoice_items or getdate(doc.valid_upto) >= getdate(today()) or not doc.company:
        frappe.throw(_("Select a closed historical scheme with a company."))
    return doc


def _reviews(scheme, customer=None):
    filters = {"scheme": scheme}
    if customer:
        filters["customer"] = customer
    records = frappe.get_all(DOCTYPE, filters=filters, fields=["invoice", "eligibility", "reason", "approved_by", "creation"])
    return {row.invoice: row for row in records}


def _documents(scheme, customer=None):
    filters = {"docstatus": 1, "company": scheme.company, "posting_date": ["between", [scheme.valid_from, scheme.valid_upto]]}
    if customer:
        filters["customer"] = customer
    fields = ["name", "customer", "customer_name", "posting_date", "is_return", "return_against", "modified"]
    documents = frappe.get_list("Sales Invoice", filters=filters, fields=fields, limit_page_length=0)
    invoices = [row.name for row in documents if not row.is_return]
    if invoices:
        filters.pop("posting_date")
        filters.update({"is_return": 1, "return_against": ["in", invoices]})
        linked = frappe.get_list("Sales Invoice", filters=filters, fields=fields, limit_page_length=0)
        documents = list({row.name: row for row in documents + linked}.values())
    return sorted(documents, key=lambda row: (row.is_return, row.posting_date, row.name))


def _legacy(scheme, customer):
    rows = engine._get_customer_invoice_item_rows(customer, scheme.company, scheme.valid_from, scheme.valid_upto)
    config = engine._get_scheme_config(scheme.name)
    items = engine._get_item_map([row.item_code for row in rows if row.item_code])
    bounds = engine._get_item_group_bounds([config], items)
    eligible = {}
    for row in rows:
        item = items.get(row.item_code) or {}
        category = None
        if config.scheme_type == engine.CATEGORY_TARGET_SLAB:
            category = engine._get_scheme_row_category(row, item, config, bounds)
            if not category:
                continue
        elif not engine._is_eligible_scheme_row(row, item, config, bounds):
            continue
        eligible[row.sales_invoice_item] = {
            "category": category, "amount": engine._get_scheme_amount(row, config.gst_treatment),
        }
    return eligible


def _invoice(name, scheme, customer):
    doc = frappe.get_doc("Sales Invoice", name)
    doc.check_permission("read")
    if doc.docstatus != 1 or doc.company != scheme.company or doc.customer != customer:
        frappe.throw(_("The document must be submitted for this company and customer."))
    return doc


def _proposal(doc, scheme, reviews, legacy, original_name=None, sources=None):
    original = None
    approved = {}
    used = defaultdict(float)
    sources = sources or {}
    if doc.is_return and (doc.return_against or original_name):
        original = _invoice(doc.return_against or original_name, scheme, doc.customer)
        if original.is_return or not getdate(scheme.valid_from) <= getdate(original.posting_date) <= getdate(scheme.valid_upto):
            frappe.throw(_("Select an original invoice within the scheme period."))
        if original.name not in reviews:
            frappe.throw(_("Review the original invoice before reviewing this credit note."))
        approved = {row["item"]: row for row in json.loads(reviews[original.name].eligibility) if row["included"]}
        for sibling, review in reviews.items():
            if sibling == doc.name:
                continue
            for item in json.loads(review.eligibility):
                if item["included"] and item.get("source") in approved:
                    used[item["source"]] += item["stock_qty"]

    result = []
    for row in doc.items:
        quantity = abs(flt(row.stock_qty))
        if not doc.is_return:
            match = legacy.get(row.name)
            result.append(dict(item=row.name, code=row.item_code, line=row.idx, category=(match or {}).get("category"),
                               amount=(match or {}).get("amount", 0), stock_qty=quantity,
                               included=bool(match), selectable=bool(match)))
            continue
        candidates = [item for item in (original.items if original else [])
                      if item.item_code == row.item_code]
        reference = sources.get(row.name) or row.get("sales_invoice_item")
        if not reference and len(candidates) == 1:
            reference = candidates[0].name
        source = approved.get(reference) if any(item.name == reference for item in candidates) else None
        available = source and source["stock_qty"] - used[reference]
        included = bool(source and quantity > 0 and quantity <= available + 0.000001)
        amount = 0
        if included:
            previous = used[reference]
            used[reference] += quantity
            precision = frappe.get_doc({"doctype": "SNRG Scheme Contribution"}).precision("eligible_amount")
            ratio = source["amount"] / source["stock_qty"]
            amount = flt(previous * ratio, precision) - flt(used[reference] * ratio, precision)
        result.append(dict(item=row.name, code=row.item_code, line=row.idx, category=(source or {}).get("category"),
                           amount=amount, stock_qty=quantity, source=reference, included=included,
                           original=original.name if original else None,
                           source_options=[{"value": item.name, "label": _("Item {0} · {1}").format(item.idx, item.item_code)}
                                           for item in candidates],
                           selectable=included, unresolved=bool((not reference and (not original or candidates)) or
                                                                (reference and not any(item.name == reference for item in candidates)) or
                                                                (source and not included))))
    return result


def _token(value):
    return hashlib.sha256(frappe.as_json(value).encode()).hexdigest()


def _store(scheme, doc, rows, reason=None):
    frappe.get_doc(dict(doctype=DOCTYPE, scheme=scheme.name, invoice=doc.name, customer=doc.customer,
                        approved_by=frappe.session.user, eligibility=json.dumps(rows), reason=reason)).insert(ignore_permissions=True)


def _lock(customer):
    frappe.get_doc("Customer", customer).check_permission("read")
    frappe.db.get_value("Customer", customer, "name", for_update=True)


@frappe.whitelist(methods=["GET"])
def customers(scheme):
    doc = _scheme(scheme)
    reviews = _reviews(doc.name)
    grouped = {}
    for row in _documents(doc):
        entry = grouped.setdefault(row.customer, dict(customer=row.customer, label=row.customer_name, invoices=0,
                                                     reviewed=0, credits=0, credits_pending=0, approved_amount=0))
        entry["invoices"] += int(not row.is_return)
        entry["reviewed"] += int(not row.is_return and row.name in reviews)
        entry["credits"] += int(bool(row.is_return))
        entry["credits_pending"] += int(row.is_return and row.name not in reviews)
        if row.name in reviews:
            entry["approved_amount"] += sum(item["amount"] for item in json.loads(reviews[row.name].eligibility) if item["included"])
    return sorted(grouped.values(), key=lambda row: (row["label"] or row["customer"]).casefold())


@frappe.whitelist(methods=["GET"])
def documents(scheme, customer):
    sd = _scheme(scheme)
    frappe.get_doc("Customer", customer).check_permission("read")
    reviews = _reviews(scheme, customer)
    rows = _documents(sd, customer)
    for row in rows:
        row.reviewed = row.name in reviews
    return rows


@frappe.whitelist(methods=["GET"])
def invoice_context(invoice):
    permission = access()
    if not permission:
        return None
    doc = frappe.get_doc("Sales Invoice", invoice)
    doc.check_permission("read")
    if doc.docstatus != 1 or doc.is_return:
        return None
    schemes = frappe.get_list("SNRG Scheme", filters=[
        ["company", "=", doc.company], ["disabled", "=", 0], ["track_invoice_items", "=", 0],
        ["valid_from", "<=", doc.posting_date], ["valid_upto", ">=", doc.posting_date],
        ["valid_upto", "<", today()],
    ], pluck="name", order_by="name asc", limit_page_length=0)
    if not schemes:
        return None
    approved = frappe.get_all(DOCTYPE, filters={"invoice": invoice, "scheme": ["in", schemes]}, pluck="scheme")
    return dict(writable=permission["writable"], schemes=schemes, reviewed=approved)


def _individual(scheme, customer, name, reviews, original=None, sources=None):
    if name not in {row.name for row in _documents(scheme, customer)}:
        frappe.throw(_("This document is outside the historical review queue."))
    doc = _invoice(name, scheme, customer)
    rows = _proposal(doc, scheme, reviews, _legacy(scheme, customer), original, sources)
    return doc, rows, _token([doc.modified, rows])


@frappe.whitelist(methods=["GET"])
def preview(scheme, customer, invoice, original=None, sources=None):
    sd = _scheme(scheme)
    frappe.get_doc("Customer", customer).check_permission("read")
    reviews = _reviews(scheme, customer)
    if invoice in reviews:
        row = reviews[invoice]
        _invoice(invoice, sd, customer)
        rows = json.loads(row.eligibility)
        return dict(rows=rows, original=next((item.get("original") for item in rows if item.get("original")), None),
                    reviewed=True, reason=row.reason,
                    approved_by=row.approved_by, approved_at=row.creation)
    doc, rows, token = _individual(sd, customer, invoice, reviews, original, frappe.parse_json(sources or "{}"))
    original_options = []
    if doc.is_return and not doc.return_against:
        original_options = [row.name for row in _documents(sd, customer) if not row.is_return and row.name in reviews]
    return dict(rows=rows, is_return=doc.is_return, original=doc.return_against or original,
                original_options=original_options, original_is_linked=bool(doc.return_against), token=token)


@frappe.whitelist(methods=["POST"])
def approve(scheme, customer, invoice, token, excluded=None, reason=None, original=None, sources=None, zero_unresolved=0):
    sd = _scheme(scheme, write=True)
    _lock(customer)
    reviews = _reviews(scheme, customer)
    if invoice in reviews:
        return
    doc, rows, revision = _individual(sd, customer, invoice, reviews, original, frappe.parse_json(sources or "{}"))
    if token != revision:
        frappe.throw(_("Eligibility changed. Refresh the preview and try again."))
    excluded = set(frappe.parse_json(excluded or "[]"))
    if excluded - {row["item"] for row in rows if row["selectable"]}:
        frappe.throw(_("Invalid item selection."))
    reason = (reason or "").strip()
    unresolved = any(row.get("unresolved") for row in rows)
    if unresolved and not cint(zero_unresolved):
        frappe.throw(_("Match the unresolved credit items or explicitly confirm a zero deduction for them."))
    if (excluded or unresolved) and not reason:
        frappe.throw(_("Enter a reason for each review with an exclusion or an unresolved credit item."))
    for row in rows:
        if row["item"] in excluded:
            row["included"] = False
    _store(sd, doc, rows, reason)


def apply_reviews(scheme, company, date, customer, rows):
    if not frappe.db.exists("DocType", DOCTYPE):
        return rows
    reviews = _reviews(scheme.name, customer)
    if not reviews:
        return rows
    effective = {item["item"]: (item, record) for record in reviews.values()
                 for item in json.loads(record.eligibility) if item["included"]}
    candidates = {row.sales_invoice_item: row for row in rows if row.sales_invoice in reviews}
    missing = set(effective) - candidates.keys()
    if missing:
        documents = [name for name, record in reviews.items()
                     if any(item["item"] in missing for item in json.loads(record.eligibility))]
        extra = engine._get_scheme_invoice_item_rows(company, scheme.valid_from, date, invoice_names=documents)
        candidates.update({row.sales_invoice_item: row for row in extra if row.sales_invoice_item in missing})
    result = [row for row in rows if row.sales_invoice not in reviews]
    for key, row in candidates.items():
        if key not in effective or getdate(row.posting_date) > getdate(date):
            continue
        item, record = effective[key]
        row.update(posted_scheme_amount=item["amount"], posted_scheme_category=item["category"],
                   exception_reason=record.reason, exception_by=record.approved_by)
        result.append(row)
    return sorted(result, key=lambda row: (getdate(row.posting_date), -row.idx), reverse=True)
