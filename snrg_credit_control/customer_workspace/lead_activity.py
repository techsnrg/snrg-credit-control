"""Structured rates and private attachments for Teamspace lead comments."""
from decimal import Decimal, InvalidOperation
from html import escape
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import cint
from pypika import Order
from werkzeug.wrappers import Response

RATE = "custom_teamspace_rate_amount"
CURRENCY = "custom_teamspace_rate_currency"
BASIS = "custom_teamspace_rate_basis"
RATE_FIELDS = [RATE, CURRENCY, BASIS]
MAX_ATTACHMENTS = 5


def install_fields(create_custom_fields):
    create_custom_fields({"Comment": [
        dict(fieldname=CURRENCY, label="Teamspace rate currency", fieldtype="Link", options="Currency", insert_after="content", hidden=1),
        dict(fieldname=RATE, label="Teamspace rate amount", fieldtype="Currency", options=CURRENCY, insert_after=CURRENCY, hidden=1),
        dict(fieldname=BASIS, label="Teamspace rate for", fieldtype="Data", insert_after=RATE, hidden=1),
    ]})


def activity_extras(rate, currency, rate_basis):
    from snrg_credit_control.customer_workspace.leads import _text

    values = {}
    if rate not in (None, ""):
        try:
            amount = Decimal(_text(rate, 32))
        except InvalidOperation:
            frappe.throw(_("Enter a valid rate."))
        if not amount.is_finite() or not 0 <= amount < 10**12 or amount.as_tuple().exponent < -6:
            frappe.throw(_("Enter a non-negative rate with up to six decimal places."))
        currency = _text(currency or "INR", 3).upper()
        if not frappe.db.exists("Currency", currency):
            frappe.throw(_("Enter a valid currency code."))
        basis = _text(rate_basis, 140)
        if not basis:
            frappe.throw(_("Enter the product or basis for the rate."))
        values = {RATE: amount, CURRENCY: currency, BASIS: basis}
    files = frappe.request.files.getlist("attachments") if frappe.request else []
    if len(files) > MAX_ATTACHMENTS:
        frappe.throw(_("Attach up to {0} files per activity.").format(MAX_ATTACHMENTS))
    return values, files


def add_activity(lead, text, rate_values, files):
    from snrg_credit_control.customer_workspace.leads import NOTE_PREFIX

    comment = lead.add_comment("Comment", NOTE_PREFIX + escape(text))
    if rate_values:
        frappe.db.set_value("Comment", comment.name, rate_values, update_modified=False)
    for upload in files:
        frappe.get_doc({
            "doctype": "File", "file_name": upload.filename, "content": upload.read(),
            "is_private": 1, "attached_to_doctype": "Comment", "attached_to_name": comment.name,
        }).insert(ignore_permissions=True)


def rate_fields(row):
    return {"rate": row.get(RATE) if row.get(CURRENCY) else None,
            "currency": row.get(CURRENCY), "rate_basis": row.get(BASIS)}


def attachments_for(comments):
    if not comments:
        return {}
    files = frappe.get_all("File", filters={
        "attached_to_doctype": "Comment", "attached_to_name": ["in", comments], "is_private": 1,
    }, fields=["name", "file_name", "attached_to_name"], order_by="creation asc, name asc")
    result = {}
    for file in files:
        result.setdefault(file.attached_to_name, []).append({"name": file.name, "file_name": file.file_name})
    return result


@frappe.whitelist(methods=["GET"])
def rates(start=0, division=None):
    from snrg_credit_control.customer_workspace.leads import (
        DIVISION, DIVISIONS, DOCTYPE, NOTE_PREFIX, SHARED, _guard,
    )

    _guard()
    lead = frappe.qb.DocType(DOCTYPE)
    comment = frappe.qb.DocType("Comment")
    query = (
        frappe.qb.from_(comment).join(lead).on(comment.reference_name == lead.name)
        .select(comment.name, comment.creation, comment.owner, comment[RATE], comment[CURRENCY], comment[BASIS],
                lead.name.as_("lead_id"), lead.organization, lead.lead_name, lead[DIVISION].as_("division"))
        .where((lead[SHARED] == 1) & (comment.reference_doctype == DOCTYPE)
               & (comment.comment_type == "Comment") & comment.content.like(NOTE_PREFIX + "%")
               & comment[CURRENCY].isnotnull() & (comment[CURRENCY] != ""))
    )
    if division:
        if division not in DIVISIONS:
            frappe.throw(_("Choose a valid division."))
        query = query.where(lead[DIVISION] == division)
    rows = query.orderby(comment.creation, comment.name, order=Order.desc).offset(max(0, cint(start))).limit(51).run(as_dict=True)
    return {"rows": [{**row, **rate_fields(row)} for row in rows[:50]], "has_more": len(rows) > 50, "divisions": DIVISIONS}


def preview_type(content):
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


@frappe.whitelist(methods=["GET"])
def attachment(name, download=0):
    from snrg_credit_control.customer_workspace.leads import DOCTYPE, NOTE_PREFIX, _guard, _lead

    _guard()
    file = frappe.get_doc("File", name)
    if not file.is_private or file.attached_to_doctype != "Comment":
        frappe.throw(_("This attachment is unavailable."), frappe.PermissionError)
    comment = frappe.get_doc("Comment", file.attached_to_name)
    if comment.reference_doctype != DOCTYPE or comment.comment_type != "Comment" or not comment.content.startswith(NOTE_PREFIX):
        frappe.throw(_("This attachment is unavailable."), frappe.PermissionError)
    _lead(comment.reference_name)
    content = file.get_content()
    if isinstance(content, str):
        content = content.encode()
    mime = preview_type(content)
    if mime == "application/pdf" and not file.file_name.lower().endswith(".pdf"):
        mime = "application/octet-stream"
    response = Response(content, mimetype=mime)
    disposition = "attachment" if cint(download) or mime == "application/octet-stream" else "inline"
    response.headers.set("Content-Disposition", disposition, filename="attachment")
    response.headers["Content-Disposition"] += "; filename*=UTF-8''" + quote(file.file_name, safe="")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response
