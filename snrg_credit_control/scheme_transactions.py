"""Sales line eligibility and posted scheme contributions."""
from html import escape
import re

import frappe
from frappe import _
from frappe.utils import flt, fmt_money, formatdate, getdate

from snrg_credit_control import scheme_engine as engine, scheme_approvals, scheme_corrections


SALES_DOCTYPES = ("Quotation", "Sales Order", "Sales Invoice")
SCHEME_TYPES = (
    engine.INVOICE_AMOUNT_SLAB,
    engine.PERIOD_CUMULATIVE_AMOUNT_SLAB,
    engine.CATEGORY_TARGET_SLAB,
)
STATE_FIELD = "custom_scheme_state"
SOURCE_FIELD = "custom_scheme_quotation_item"
CONTRIBUTIONS = "custom_scheme_contributions"
SUMMARY = "custom_scheme_summary"


def _state(row):
    value = row.get(STATE_FIELD)
    if not value:
        return {}
    state = frappe.parse_json(value)
    if not isinstance(state, dict):
        frappe.throw(_("Invalid scheme line state."))
    return state


def _signature(row):
    return [row.get("item_code"), row.get("uom")]


def _source(doc, row):
    order_item = row.get("so_detail") if doc.doctype == "Sales Invoice" else None
    if order_item:
        source = frappe.db.get_value("Sales Order Item", order_item,
                                     ["parent", STATE_FIELD, SOURCE_FIELD, "quotation_item"], as_dict=True)
        if not source or source.parent != row.get("sales_order"):
            frappe.throw(_("Row {0}: invalid Sales Order item reference.").format(row.idx))
        return _state(source), source.get("quotation_item") or source.get(SOURCE_FIELD)
    quotation_item = row.get("quotation_item") or row.get(SOURCE_FIELD)
    if doc.doctype == "Quotation" or not quotation_item:
        return {}, None
    source = frappe.db.get_value("Quotation Item", quotation_item, ["parent", STATE_FIELD], as_dict=True)
    if not source or source.parent != row.get("prevdoc_docname"):
        frappe.throw(_("Row {0}: invalid Quotation item reference.").format(row.idx))
    return _state(source), quotation_item


def _rules(local, carried, row):
    rules = {}
    for rule in [*carried.get("exclusions", []), *local.get("own_exclusions", [])]:
        if not isinstance(rule, dict):
            frappe.throw(_("Row {0}: invalid scheme exclusion.").format(row.idx))
        scope, target = rule.get("scope"), rule.get("target") or ""
        reason = str(rule.get("reason") or "").strip()
        if scope not in ("scheme", "series", "all") or (scope != "all" and not target) or not reason:
            frappe.throw(_("Row {0}: an exclusion requires a scope and reason.").format(row.idx))
        rules[scope, target] = dict(scope=scope, target=target, reason=reason)
    return list(rules.values())


def _excluded(scheme, rules):
    return any(rule["scope"] == "all"
               or (rule["scope"] == "scheme" and rule["target"] == scheme.name)
               or (rule["scope"] == "series" and rule["target"] == scheme.scheme_series)
               for rule in rules)


def _category(row, item, scheme, bounds):
    if scheme.scheme_type == engine.CATEGORY_TARGET_SLAB:
        return engine._get_scheme_row_category(row, item, scheme, bounds)
    if engine._is_eligible_scheme_row(row, item, scheme, bounds):
        return ""


def _manager():
    return "Scheme Manager" in frappe.get_roles()


def _evaluate(doc, submit=False):
    date = getdate(doc.get("posting_date") or doc.get("transaction_date"))
    active = [scheme for scheme in engine._get_active_schemes(doc, date, scheme_types=SCHEME_TYPES)
              if scheme.track_invoice_items]
    configs = {scheme.name: scheme for scheme in active}
    source_cache = []
    for row in doc.items:
        carried, quotation_item = _source(doc, row)
        if doc.doctype == "Quotation":
            quotation_item = row.name
        row.set(SOURCE_FIELD, quotation_item)
        if carried.get("signature") != _signature(row):
            carried = {}
        source_cache.append(carried)
        if doc.doctype == "Sales Invoice":
            for name in carried.get("applicable", []):
                if name not in configs and frappe.db.exists("SNRG Scheme", name):
                    configs[name] = engine._get_scheme_config(name)

    items = engine._get_item_map([row.item_code for row in doc.items if row.item_code])
    bounds = engine._get_item_group_bounds(configs.values(), items)
    contributions = []
    requests = scheme_approvals.current_requests(doc) if doc.doctype == "Sales Invoice" else {}
    for row, carried in zip(doc.items, source_cache):
        local = _state(row)
        if local.get("signature") != _signature(row):
            local = {}
        rules = _rules(local, carried, row)
        item = items.get(row.item_code) or {}
        candidates = {}
        applicable = {}
        for scheme in active:
            category = _category(row, item, scheme, bounds)
            if category is not None:
                match = dict(category=category, series=scheme.scheme_series)
                candidates[scheme.name] = match
                if not _excluded(scheme, rules):
                    applicable[scheme.name] = match

        eligible_not_applied = {}
        approvals = {}
        closed = {}
        decisions = {}
        pending = {}
        if doc.doctype == "Sales Invoice":
            if row.get(SOURCE_FIELD):
                quoted = carried.get("applicable", {})
                eligible_not_applied = {name: match for name, match in applicable.items() if name not in quoted}
                applicable = {name: match for name, match in applicable.items() if name in quoted}
            for name, original in carried.get("applicable", {}).items():
                scheme = configs.get(name)
                if not scheme or not scheme.track_invoice_items or _excluded(scheme, rules):
                    continue
                if date <= getdate(scheme.valid_upto):
                    continue
                closed[name] = scheme.valid_upto
                decision = local.get("decisions", {}).get(name, {})
                approval = requests.get((row.name, name, scheme_approvals.terms(doc, row, name)))
                if approval:
                    approvals[name] = approval
                approved = approval and approval.status == "Approved" and decision.get("choice") != "skip"
                choice = "honour" if approved else decision.get("choice")
                reason = approval.reason if approved else str(decision.get("reason") or "").strip()
                if choice not in ("skip", "honour") or (choice == "honour" and not reason):
                    pending[name] = scheme.valid_upto
                    continue
                decisions[name] = dict(choice=choice, reason=reason)
                if choice == "skip":
                    continue
                if submit and not approved and not _manager():
                    frappe.throw(_("A Scheme Manager must submit an invoice that honours a closed scheme."))
                if scheme.company and scheme.company != doc.company:
                    frappe.throw(_("The closed scheme belongs to another company."))
                if scheme.scheme_series:
                    applicable = {key: value for key, value in applicable.items()
                                  if configs[key].scheme_series != scheme.scheme_series}
                applicable[name] = dict(category=original["category"], series=scheme.scheme_series, reason=reason,
                                        approved_by=approval.decided_by if approved else frappe.session.user if submit else None)
            if pending and submit:
                frappe.throw(_("Row {0}: closed schemes require a decision before submission ({1}).")
                             .format(row.idx, ", ".join(pending)))

        if doc.doctype == "Sales Order":
            # Preserve quotation terms even when the order is created after the scheme closes.
            if row.get(SOURCE_FIELD):
                candidates = carried.get("candidates", carried.get("applicable", {}))
                applicable = {name: match for name, match in carried.get("applicable", {}).items()
                              if not any(rule["scope"] == "all"
                                         or (rule["scope"] == "scheme" and rule["target"] == name)
                                         or (rule["scope"] == "series" and rule["target"] == match.get("series"))
                                         for rule in rules)}
        state = dict(signature=_signature(row), applicable=applicable, candidates=candidates, exclusions=rules,
                     inherited_exclusions=carried.get("exclusions", []),
                     own_exclusions=local.get("own_exclusions", []), decisions=decisions,
                     closed=closed, pending=pending, eligible_not_applied=eligible_not_applied, approvals=approvals,
                     quotation=carried.get("quotation") or (doc.name if doc.doctype == "Quotation" else None))
        if submit and doc.doctype == "Sales Invoice":
            state["candidate_amounts"] = {name: _invoice_amount(doc, row, configs[name])
                                          for name in candidates if name in configs}
        row.set(STATE_FIELD, frappe.as_json(state))
        if submit and doc.doctype == "Sales Invoice":
            for name, match in applicable.items():
                amount = _invoice_amount(doc, row, configs[name])
                if amount > 0 and flt(row.stock_qty) > 0:
                    contributions.append(dict(scheme=name, invoice_item=row.name, item_code=row.item_code,
                                              category=match["category"], eligible_amount=amount,
                                              stock_qty=abs(flt(row.stock_qty)), quotation=state["quotation"],
                                              exception_reason=match.get("reason"), exception_by=match.get("approved_by")))
    return contributions


def _invoice_amount(doc, item, scheme):
    amount = engine._get_pre_gst_amount(item)
    if scheme.gst_treatment != engine.GST_INCLUDED:
        return amount
    # ERPNext 16 provides allocated base-currency taxes per actual child row.
    details = doc.get("_item_wise_tax_details") or []
    if details:
        gst = sum(flt(detail.amount) for detail in details
                  if detail.item.name == item.name
                  and re.search(r"(?i)\b(?:IGST|CGST|SGST|UTGST|GST CESS)\b", detail.tax.account_head or ""))
        return flt(amount + gst, item.precision("base_net_amount"))
    gst_fields = ("igst_amount", "cgst_amount", "sgst_amount", "utgst_amount", "cess_amount", "cess_non_advol_amount")
    if any(item.meta.has_field(field) for field in gst_fields):
        gst = sum(flt(item.get(field)) for field in gst_fields)
        return flt(amount + gst * flt(doc.conversion_rate or 1), item.precision("base_net_amount"))
    return engine._get_scheme_amount(item, scheme.gst_treatment)


def validate_transaction(doc, method=None):
    if not frappe.get_meta(doc.doctype + " Item").has_field(STATE_FIELD):
        return
    if doc.doctype == "Sales Invoice":
        doc.set(CONTRIBUTIONS, [])
        doc.set(SUMMARY, None)
        if doc.is_return:
            return
    _evaluate(doc)


def prepare_submission(doc, method=None):
    if not frappe.get_meta(doc.doctype + " Item").has_field(STATE_FIELD):
        return
    if doc.doctype != "Sales Invoice":
        _evaluate(doc)
        return

    frappe.db.get_value("Customer", doc.customer, "name", for_update=True)
    contributions = _return_contributions(doc) if doc.is_return else _evaluate(doc, submit=True)
    doc.set(CONTRIBUTIONS, contributions)
    doc.set(SUMMARY, _summary(doc, contributions) if contributions else None)


def posted_contributions(company, as_on_date, customer=None, scheme=None, lock=False, invoice_name=None):
    return frappe.db.sql(
        f"""
        select contribution.*, invoice.posting_date
        from ({scheme_corrections.effective_contributions_sql()}) contribution
        inner join `tabSales Invoice` invoice on invoice.name = contribution.parent
        where invoice.docstatus = 1 and invoice.posting_date <= %(date)s
          and (%(company)s is null or invoice.company = %(company)s)
          and (%(customer)s is null or invoice.customer = %(customer)s)
          and (%(scheme)s is null or contribution.scheme = %(scheme)s)
          and (%(invoice)s is null or invoice.name = %(invoice)s)
        """ + (" for update" if lock else ""),
        dict(company=company, date=as_on_date, customer=customer, scheme=scheme, invoice=invoice_name),
        as_dict=True,
    )


def _return_contributions(doc):
    if not doc.return_against:
        return []
    original = frappe.get_doc("Sales Invoice", doc.return_against)
    if original.docstatus != 1 or original.customer != doc.customer or original.company != doc.company:
        frappe.throw(_("The return must reference a submitted invoice for the same customer and company."))
    original_rows = posted_contributions(doc.company, original.posting_date, doc.customer, invoice_name=original.name, lock=True)
    if not original_rows:
        return []
    reversals = frappe.db.sql(
        """
        select contribution.original_invoice_item, contribution.scheme, contribution.stock_qty
        from `tabSNRG Scheme Contribution` contribution
        inner join `tabSales Invoice` invoice on invoice.name = contribution.parent
        where contribution.original_invoice = %s and invoice.docstatus = 1
        for update
        """, original.name, as_dict=True,
    )
    used = {}
    for reversal in reversals:
        key = (reversal.original_invoice_item, reversal.scheme)
        used[key] = used.get(key, 0) + abs(reversal.stock_qty)
    results = []
    for row in doc.items:
        reference = row.get("sales_invoice_item")
        if not reference and any(entry.item_code == row.item_code for entry in original_rows):
            frappe.throw(_("Row {0}: select the original invoice line to reverse its scheme contribution.")
                         .format(row.idx))
        original_item = next((item for item in original.items if item.name == reference), None)
        if reference and (not original_item or original_item.item_code != row.item_code):
            frappe.throw(_("Row {0}: invalid original invoice line.").format(row.idx))
        for entry in original_rows:
            if entry.invoice_item != reference:
                continue
            key = (reference, entry.scheme)
            returned = used.get(key, 0)
            quantity = abs(flt(row.stock_qty))
            if returned + quantity > entry.stock_qty + 0.000001:
                frappe.throw(_("Row {0}: returned quantity exceeds the original scheme contribution.")
                             .format(row.idx))
            used[key] = returned + quantity
            # Use cumulative rounding so several partial credits reverse exactly the original amount.
            precision = frappe.get_doc({"doctype": "SNRG Scheme Contribution"}).precision("eligible_amount")
            before = flt(entry.eligible_amount * returned / entry.stock_qty, precision)
            after = flt(entry.eligible_amount * used[key] / entry.stock_qty, precision)
            results.append(dict(scheme=entry.scheme, invoice_item=row.name, item_code=row.item_code,
                                category=entry.category, eligible_amount=before - after, stock_qty=-quantity,
                                original_invoice=original.name, original_invoice_item=reference,
                                quotation=entry.quotation))
    return results


def _summary(doc, current, as_on_date=None):
    names = sorted({row["scheme"] for row in current})
    prior = posted_contributions(doc.company, as_on_date or doc.posting_date, doc.customer, lock=True)
    blocks = []
    for name in names:
        scheme = engine._get_scheme_config(name)
        amount = sum(row["eligible_amount"] for row in current if row["scheme"] == name)
        rows = [row for row in current if row["scheme"] == name]
        if scheme.scheme_type != engine.INVOICE_AMOUNT_SLAB:
            rows += [row for row in prior if row.scheme == name and row.parent != doc.name]
        total = sum(row["eligible_amount"] for row in rows)
        currency = frappe.get_cached_value("Company", doc.company, "default_currency")
        category_note = ""
        if scheme.scheme_type == engine.CATEGORY_TARGET_SLAB:
            category_amounts = {category: sum(row["eligible_amount"] for row in rows if row["category"] == category)
                                for category in scheme.categories}
            achieved, next_slab = engine._get_category_slab_progress(scheme.category_slabs, category_amounts, total)
            if next_slab:
                targets = next_slab["targets"]
                gaps = [f"{category}: {fmt_money(targets[category] - category_amounts.get(category, 0), currency=currency)}"
                        for category in targets if targets[category] > category_amounts.get(category, 0)]
                needed = next_slab["minimum_categories_required"] - next_slab["qualified_categories"]
                if needed > 0:
                    category_note = _("Additional category targets required: {0}. Gaps: {1}").format(
                        needed, ", ".join(gaps))
        else:
            achieved, _highest_slab, next_slab = engine._get_slab_progress(scheme.slabs, total)

        def money(value):
            return fmt_money(value, currency=currency)
        rewards = ", ".join(engine._get_scheme_rewards(achieved, scheme.reward_policy)) or _("None yet")
        remaining = (money(max(0, next_slab["amount"] - total)) if next_slab else _("All slabs cleared"))
        reward_label = _("Invoiced reward level: {0}") if scheme.payment_hard_deadline else _("Reward achieved: {0}")
        values = [
            _("This invoice: {0}").format(money(amount)),
            _("Eligible total: {0}").format(money(total)),
            reward_label.format(rewards),
            _("Claimable only after eligible invoices clear by {0}.").format(formatdate(scheme.payment_hard_deadline))
            if scheme.payment_hard_deadline else "",
            _("Amount remaining to next slab: {0}").format(remaining),
            category_note,
        ]
        blocks.append(f"<p><strong>{escape(name)}</strong><br>"
                      + "<br>".join(escape(value) for value in values if value) + "</p>")
    return "".join(blocks)


@frappe.whitelist()
def preview(document):
    payload = frappe.parse_json(document)
    doctype = payload.get("doctype")
    if doctype not in SALES_DOCTYPES:
        frappe.throw(_("Unsupported sales document."))
    doc = frappe.get_doc(payload)
    if not doc.name or not frappe.db.exists(doctype, doc.name):
        if not frappe.has_permission(doctype, "create"):
            frappe.throw(_("You cannot create this document."), frappe.PermissionError)
    else:
        frappe.get_doc(doctype, doc.name).check_permission("write")
    if doc.docstatus or doc.get("is_return"):
        return {}
    _evaluate(doc)
    return {row.name: {"state": _state(row), "source": row.get(SOURCE_FIELD)} for row in doc.items}
