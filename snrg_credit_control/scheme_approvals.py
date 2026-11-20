"""Request and resolve a closed-scheme exception against saved invoice terms."""

from hashlib import sha256
from html import escape

import frappe
from frappe import _
from frappe.utils import flt

DOCTYPE = "SNRG Scheme Approval"
ROLE = "Scheme Manager"


def terms(invoice, row, scheme):
    values = [
        invoice.name, invoice.customer, invoice.company, str(invoice.posting_date), invoice.currency,
        row.name, row.item_code, row.uom, flt(row.qty), flt(row.rate), flt(row.base_net_amount),
        row.get("so_detail"), row.get("custom_scheme_quotation_item"), scheme,
    ]
    return sha256(frappe.as_json(values).encode()).hexdigest()


def current_requests(invoice):
    if not invoice.name or invoice.is_new() or not frappe.db.exists("DocType", DOCTYPE):
        return {}
    entries = frappe.get_all(DOCTYPE, filters={"invoice": invoice.name}, fields=[
        "name", "invoice_item", "scheme", "terms", "status", "assignee", "reason", "decision_reason", "decided_by",
    ], order_by="creation desc, name desc")
    indexed = {}
    for entry in entries:
        indexed.setdefault((entry.invoice_item, entry.scheme, entry.terms), entry)
    return indexed


def _invoice(name, permission):
    doc = frappe.get_doc("Sales Invoice", name)
    doc.check_permission(permission)
    frappe.db.get_value("Sales Invoice", name, "name", for_update=True)
    doc.reload()
    if doc.docstatus != 0 or doc.is_return:
        frappe.throw(_("Approval is available on draft sales invoices."))
    return doc


def _row(invoice, row_id):
    row = next((row for row in invoice.items if row.name == row_id), None)
    if not row:
        frappe.throw(_("This invoice item is no longer present."))
    return row


def _managers():
    users = frappe.get_all("Has Role", filters={
        "role": ROLE, "parenttype": "User", "parentfield": "roles",
    }, pluck="parent")
    if not users:
        return []
    return frappe.get_all("User", filters={"name": ["in", users], "enabled": 1, "user_type": "System User"},
                          fields=["name", "full_name"], order_by="full_name")


def _notify(invoice, user, subject):
    frappe.get_doc(dict(
        doctype="Notification Log", subject=escape(subject), for_user=user,
        from_user=frappe.session.user, type="Alert", document_type="Sales Invoice", document_name=invoice,
    )).insert(ignore_permissions=True)


@frappe.whitelist()
def managers(invoice):
    frappe.get_doc("Sales Invoice", invoice).check_permission("write")
    return _managers()


@frappe.whitelist(methods=["POST"])
def request(invoice, invoice_item, scheme, assignee, reason):
    from snrg_credit_control import scheme_transactions as txn

    doc = _invoice(invoice, "write")
    if assignee not in {user.name for user in _managers()}:
        frappe.throw(_("Select an enabled Scheme Manager."))
    reason = (reason or "").strip()
    if not reason:
        frappe.throw(_("A request reason is required."))
    row = _row(doc, invoice_item)
    txn._evaluate(doc)
    if scheme not in txn._state(row).get("closed", {}):
        frappe.throw(_("This scheme is not eligible for a late exception on this invoice item."))
    fingerprint = terms(doc, row, scheme)
    existing = current_requests(doc).get((invoice_item, scheme, fingerprint))
    if existing and existing.status in ("Pending", "Approved"):
        return existing.name
    for stale in current_requests(doc).values():
        if stale.invoice_item == invoice_item and stale.scheme == scheme and stale.status == "Pending":
            assignment = frappe.db.get_value(DOCTYPE, stale.name, "assignment")
            _close(stale.name, assignment)
    approval = frappe.get_doc(dict(
        doctype=DOCTYPE, invoice=invoice, invoice_item=invoice_item, scheme=scheme, terms=fingerprint,
        assignee=assignee, requested_by=frappe.session.user, reason=reason, status="Pending",
    )).insert(ignore_permissions=True)
    if not frappe.has_permission("Sales Invoice", "read", doc=doc, user=assignee):
        frappe.share.add_docshare("Sales Invoice", invoice, assignee, read=1, notify=0,
                         flags={"ignore_share_permission": True})
    title = _("Scheme approval requested for {0}, item {1}").format(invoice, row.item_code)
    todo = frappe.get_doc(dict(
        doctype="ToDo", allocated_to=assignee, assigned_by=frappe.session.user,
        reference_type="Sales Invoice", reference_name=invoice, description=escape(title), status="Open",
    )).insert(ignore_permissions=True)
    approval.db_set("assignment", todo.name)
    _notify(invoice, assignee, title)
    return approval.name


@frappe.whitelist(methods=["POST"])
def decide(name, decision, note=None):
    from snrg_credit_control import scheme_transactions as txn

    approval = frappe.get_doc(DOCTYPE, name)
    if approval.assignee != frappe.session.user or ROLE not in frappe.get_roles():
        frappe.throw(_("Only the assigned Scheme Manager can decide this request."), frappe.PermissionError)
    invoice = _invoice(approval.invoice, "read")
    approval.reload()
    note = (note or "").strip()
    if approval.status != "Pending" or decision not in ("Approved", "Declined"):
        frappe.throw(_("This request can no longer be decided."))
    if decision == "Declined" and not note:
        frappe.throw(_("Enter a reason for declining."))
    row = _row(invoice, approval.invoice_item)
    txn._evaluate(invoice)
    if approval.terms != terms(invoice, row, approval.scheme) or approval.scheme not in txn._state(row).get("closed", {}):
        frappe.throw(_("The invoice item or scheme changed. Ask sales to submit a new request."))
    approval.db_set({"status": decision, "decided_by": frappe.session.user, "decision_reason": note})
    if approval.assignment:
        _finish_assignment(approval.assignment, "Closed")
    _notify(invoice.name, approval.requested_by, _("Scheme approval {0} for {1}").format(_(decision.lower()), invoice.name))


@frappe.whitelist()
def review(invoice):
    from snrg_credit_control import scheme_transactions as txn

    doc = frappe.get_doc("Sales Invoice", invoice)
    doc.check_permission("read")
    if doc.docstatus != 0 or doc.is_return:
        return {}
    txn._evaluate(doc)
    return {row.name: txn._state(row) for row in doc.items}


def _finish_assignment(name, status):
    todo = frappe.get_doc("ToDo", name)
    todo.db_set("status", status)
    todo.update_in_reference()


def _close(name, assignment):
    frappe.db.set_value(DOCTYPE, name, "status", "Cancelled")
    if assignment:
        _finish_assignment(assignment, "Cancelled")


def close_pending(doc, method=None):
    if not frappe.db.exists("DocType", DOCTYPE):
        return
    for approval in frappe.get_all(DOCTYPE, filters={"invoice": doc.name, "status": "Pending"},
                                   fields=["name", "assignment"]):
        _close(approval.name, approval.assignment)
