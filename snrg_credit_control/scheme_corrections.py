"""Append-only corrections to scheme eligibility on submitted invoice items."""

from html import escape

import frappe
from frappe import _
from frappe.utils import flt, fmt_money, formatdate, today

DOCTYPE = "SNRG Scheme Correction"
ROLE = "Scheme Manager"


def effective_contributions_sql():
    original = """
        select sc.parent, sc.invoice_item, sc.item_code, sc.scheme, sc.category,
               sc.eligible_amount, sc.stock_qty, sc.quotation, sc.exception_reason, sc.exception_by
        from `tabSNRG Scheme Contribution` sc
        where sc.parenttype = 'Sales Invoice'
    """
    if not frappe.get_meta("Sales Invoice").has_field("custom_scheme_contributions") or not frappe.db.exists("DocType", DOCTYPE):
        return original
    return original + """
        and not exists (
            select 1 from `tabSNRG Scheme Correction` correction
            where correction.invoice = sc.parent and correction.invoice_item = sc.invoice_item
              and correction.scheme = sc.scheme
        )
        union all
        select correction.invoice, correction.invoice_item, correction.item_code, correction.scheme,
               correction.category, correction.eligible_amount, correction.stock_qty, correction.quotation,
               correction.reason, correction.corrected_by
        from `tabSNRG Scheme Correction` correction
        where correction.action = 'Include' and not exists (
            select 1 from `tabSNRG Scheme Correction` newer
            where newer.invoice = correction.invoice and newer.invoice_item = correction.invoice_item
              and newer.scheme = correction.scheme
              and (newer.creation > correction.creation
                   or (newer.creation = correction.creation and newer.name > correction.name))
        )
    """


def latest(invoice_names, scheme):
    if not invoice_names or not frappe.db.exists("DocType", DOCTYPE):
        return {}
    rows = frappe.get_all(DOCTYPE, filters={"invoice": ["in", invoice_names], "scheme": scheme},
                          fields=["invoice", "invoice_item", "action", "reason"],
                          order_by="creation desc, name desc")
    latest_rows = {}
    for row in rows:
        latest_rows.setdefault((row.invoice, row.invoice_item), row)
    return latest_rows


def _manager():
    if ROLE not in frappe.get_roles():
        frappe.throw(_("Only Scheme Managers can correct scheme eligibility."), frappe.PermissionError)


def _submitted_invoice(name):
    invoice = frappe.get_doc("Sales Invoice", name)
    invoice.check_permission("read")
    if invoice.docstatus != 1 or invoice.is_return:
        frappe.throw(_("Select a submitted sales invoice."))
    return invoice


def _current(invoice):
    from snrg_credit_control import scheme_transactions as txn

    return txn.posted_contributions(invoice.company, invoice.posting_date, invoice.customer, invoice_name=invoice.name)


def _choices(invoice, current):
    from snrg_credit_control import scheme_transactions as txn
    from snrg_credit_control import scheme_engine as engine

    included = {(row.invoice_item, row.scheme): row for row in current}
    original = {(row.invoice_item, row.scheme): row for row in invoice.get(txn.CONTRIBUTIONS) or []}
    result = []
    for row in invoice.items:
        state = txn._state(row)
        carried, quotation_item = txn._source(invoice, row)
        quoted = carried.get("candidates", carried.get("applicable", {}))
        candidates = dict(state.get("candidates", {}))
        if quotation_item:
            candidates = {name: match for name, match in candidates.items() if name in quoted}
        candidates.update({
            name: {"category": entry.category} for (item, name), entry in original.items() if item == row.name
        })
        candidates.update({
            name: {"category": entry.category} for (item, name), entry in included.items() if item == row.name
        })
        for name, match in sorted(candidates.items()):
            has_contribution = (row.name, name) in included
            original_contribution = original.get((row.name, name))
            config = engine._get_scheme_config(name)
            if not has_contribution:
                if not config.track_invoice_items or name in state.get("eligible_not_applied", {}):
                    continue
                if name in state.get("closed", {}) and not original_contribution:
                    continue
                # A corrected row must keep the existing one-scheme-per-series rule.
                if config.scheme_series and any(
                    entry.invoice_item == row.name and engine._get_scheme_config(entry.scheme).scheme_series == config.scheme_series
                    for entry in current
                ):
                    continue
                if config.gst_treatment == engine.GST_INCLUDED and not original_contribution:
                    # Older submitted rows may lack the tax allocation needed to reconstruct their amount.
                    if name not in state.get("candidate_amounts", {}):
                        continue
                amount = flt(original_contribution.eligible_amount if original_contribution
                             else state.get("candidate_amounts", {}).get(name, engine._get_pre_gst_amount(row)))
                if amount <= 0 or flt(row.stock_qty) <= 0:
                    continue
            else:
                amount = 0
            result.append({
                "invoice_item": row.name, "line": row.idx, "item_code": row.item_code,
                "scheme": name, "action": "Exclude" if has_contribution else "Include",
                "category": match.get("category"), "eligible_amount": amount,
                "stock_qty": flt(row.stock_qty), "quotation": state.get("quotation"),
            })
    return result


@frappe.whitelist()
def options(invoice):
    doc = _submitted_invoice(invoice)
    history = frappe.get_all(DOCTYPE, filters={"invoice": doc.name},
                             fields=["name", "item_code", "scheme", "action", "reason", "creation"],
                             order_by="creation desc")
    if ROLE not in frappe.get_roles():
        return {"history": history, "choices": []}
    if _has_return(doc.name):
        return {"history": history, "choices": [], "blocked": _("A submitted credit note already references this invoice.")}
    return {"history": history, "choices": _choices(doc, _current(doc))}


def _has_return(invoice):
    return frappe.db.exists("Sales Invoice", {"return_against": invoice, "is_return": 1, "docstatus": 1})


@frappe.whitelist(methods=["POST"])
def correct(invoice, invoice_item, scheme, action, reason):
    from snrg_credit_control import scheme_transactions as txn

    _manager()
    doc = _submitted_invoice(invoice)
    reason = (reason or "").strip()
    if not reason:
        frappe.throw(_("Enter a reason for the correction."))
    frappe.db.get_value("Customer", doc.customer, "name", for_update=True)
    frappe.db.get_value("Sales Invoice", doc.name, "name", for_update=True)
    doc.reload()
    if doc.docstatus != 1 or _has_return(doc.name):
        frappe.throw(_("Corrections require a submitted invoice without a submitted credit note."))
    current = _current(doc)
    choice = next((row for row in _choices(doc, current) if
                   (row["invoice_item"], row["scheme"], row["action"]) == (invoice_item, scheme, action)), None)
    if not choice:
        frappe.throw(_("This correction is no longer available. Refresh the invoice and try again."))
    correction = frappe.get_doc(dict(
        doctype=DOCTYPE, invoice=invoice, corrected_by=frappe.session.user, reason=reason,
        **{key: value for key, value in choice.items() if key != "line"},
    )).insert(ignore_permissions=True)
    revised = [row for row in _current(doc) if row.scheme == scheme]
    if not revised:
        revised = [{"scheme": scheme, "category": choice["category"], "eligible_amount": 0}]
    progress = txn._summary(doc, revised, as_on_date=today())
    currency = frappe.get_cached_value("Company", doc.company, "default_currency")
    previous = sum(flt(row.eligible_amount) for row in current if row.scheme == scheme and row.invoice_item == invoice_item)
    headings = [
        (_("Invoice"), doc.name), (_("Customer"), doc.customer_name or doc.customer),
        (_("Correction"), correction.name), (_("Date"), formatdate(correction.creation)),
        (_("Item"), _("Item {0} · {1}").format(choice["line"], choice["item_code"])),
        (_("Scheme"), scheme), (_("Action"), _(action)), (_("Reason"), reason),
        (_("Corrected by"), frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user),
        (_("Previous eligible value for this item"), fmt_money(previous, currency=currency)),
        (_("Revised eligible value for this item"), fmt_money(choice["eligible_amount"], currency=currency)),
    ]
    table = "".join(f"<tr><th>{escape(label)}</th><td>{escape(str(value))}</td></tr>" for label, value in headings)
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
      body {{ font: 11pt 'DejaVu Sans', sans-serif; color: #17242a; }}
      h1 {{ font-size: 21pt; margin: 0 0 14pt; }} h2 {{ font-size: 13pt; margin-top: 18pt; }}
      table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
      th,td {{ border-bottom: 1px solid #d4dde0; padding: 6pt; text-align: left;
               vertical-align: top; overflow-wrap: break-word; }}
      th {{ width: 39%; }} tr {{ page-break-inside: avoid; }}
      </style></head><body><h1>{escape(_("Revised Scheme Statement"))}</h1><table>{table}</table>
      <h2>{escape(_("Updated scheme achievement"))}</h2>{progress}</body></html>"""
    correction.db_set("statement", html)
    return correction.name


@frappe.whitelist()
def download(name):
    from frappe.utils.pdf import get_pdf

    correction = frappe.get_doc(DOCTYPE, name)
    frappe.get_doc("Sales Invoice", correction.invoice).check_permission("read")
    frappe.response.update(filename=f"revised-scheme-statement-{correction.name}.pdf",
                           filecontent=get_pdf(correction.statement), type="download")


def preserve_history_on_cancel(invoice, method=None):
    invoice.ignore_linked_doctypes = (*tuple(invoice.get("ignore_linked_doctypes") or ()), DOCTYPE)
