import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, fmt_money, get_url, get_url_to_form, getdate, now_datetime, today


PRICE_REQUEST_USER_ROLE = "Price Request User"
PRICING_APPROVER_ROLE = "Pricing Approver"


class ItemPriceRequest(Document):
    def validate(self):
        self._set_defaults()
        self._validate_status_change()
        self._validate_locked_status()
        self._validate_price_list()
        self._validate_rate()
        self._validate_duplicate_item_price()

    def after_insert(self):
        _notify_pricing_approvers(self)

    def _set_defaults(self):
        if not self.status:
            self.status = "Pending"
        if not self.requested_by:
            self.requested_by = frappe.session.user
        if not self.valid_from:
            self.valid_from = today()

    def _validate_locked_status(self):
        if self.is_new() or getattr(self.flags, "ignore_price_request_lock", False):
            return

        previous_status = frappe.db.get_value(self.doctype, self.name, "status")
        if previous_status in ("Approved", "Rejected"):
            frappe.throw(
                _("Approved or rejected price requests cannot be edited."),
                title=_("Price Request Locked"),
            )

    def _validate_status_change(self):
        if getattr(self.flags, "ignore_price_request_lock", False):
            return

        if self.is_new():
            if self.status != "Pending":
                frappe.throw(_("New price requests must start as Pending."))
            return

        previous = frappe.db.get_value(
            self.doctype,
            self.name,
            ["status", "approved_by", "approval_time", "created_item_price"],
            as_dict=True,
        ) or {}
        if self.status != previous.get("status"):
            frappe.throw(_("Use the Approve or Reject action to change request status."))
        if self.approved_by != previous.get("approved_by"):
            frappe.throw(_("Approved By cannot be changed manually."))
        if str(self.approval_time or "") != str(previous.get("approval_time") or ""):
            frappe.throw(_("Approval Time cannot be changed manually."))
        if self.created_item_price != previous.get("created_item_price"):
            frappe.throw(_("Created Item Price cannot be changed manually."))

    def _validate_price_list(self):
        if not self.price_list:
            return

        price_list = frappe.db.get_value(
            "Price List",
            self.price_list,
            ["enabled", "selling"],
            as_dict=True,
        )
        if not price_list:
            frappe.throw(_("Price List {0} does not exist.").format(frappe.bold(self.price_list)))
        if not price_list.enabled or not price_list.selling:
            frappe.throw(_("Select an enabled selling Price List."))

    def _validate_rate(self):
        if flt(self.requested_rate) <= 0:
            frappe.throw(_("Requested Rate must be greater than zero."))
        if self.valid_upto and self.valid_from and getdate(self.valid_upto) < getdate(self.valid_from):
            frappe.throw(_("Valid Upto cannot be before Valid From."))

    def _validate_duplicate_item_price(self):
        if self.status != "Pending":
            return
        duplicate = find_matching_item_price(
            item_code=self.item_code,
            price_list=self.price_list,
            uom=self.uom,
            currency=self.currency,
            valid_from=self.valid_from,
            valid_upto=self.valid_upto,
        )
        if duplicate:
            frappe.throw(
                _("A matching Item Price already exists: {0}").format(
                    frappe.bold(duplicate)
                ),
                title=_("Duplicate Item Price"),
            )


@frappe.whitelist()
def create_from_quotation(
    quotation,
    quotation_item_row,
    price_list,
    requested_rate,
    uom=None,
    currency=None,
    valid_from=None,
    valid_upto=None,
    reason=None,
    rate_communication_attachment=None,
):
    _require_requester()
    if not quotation:
        frappe.throw(_("Quotation is required."))

    quotation_doc = frappe.get_doc("Quotation", quotation)
    if not quotation_doc.has_permission("read"):
        frappe.throw(_("Not permitted."), frappe.PermissionError)

    item_row = _get_quotation_item(quotation_doc, quotation_item_row)
    doc = frappe.get_doc(
        {
            "doctype": "Item Price Request",
            "quotation": quotation_doc.name,
            "quotation_item_row": item_row.idx,
            "customer": quotation_doc.party_name if quotation_doc.quotation_to == "Customer" else None,
            "company": quotation_doc.company,
            "item_code": item_row.item_code,
            "item_name": item_row.item_name,
            "price_list": price_list,
            "uom": uom or item_row.uom,
            "currency": currency or quotation_doc.currency,
            "requested_rate": requested_rate,
            "valid_from": valid_from or today(),
            "valid_upto": valid_upto,
            "rate_communication_attachment": rate_communication_attachment,
            "reason": reason,
            "requested_by": frappe.session.user,
            "status": "Pending",
        }
    )
    doc.insert()
    return {
        "name": doc.name,
        "message": _("Item Price Request {0} created.").format(doc.name),
    }


@frappe.whitelist()
def approve_request(name):
    _require_approver()
    doc = _get_request(name)
    if doc.status != "Pending":
        frappe.throw(_("Only pending price requests can be approved."))

    duplicate = find_matching_item_price(
        item_code=doc.item_code,
        price_list=doc.price_list,
        uom=doc.uom,
        currency=doc.currency,
        valid_from=doc.valid_from,
        valid_upto=doc.valid_upto,
    )
    if duplicate:
        frappe.throw(
            _("A matching Item Price already exists: {0}").format(frappe.bold(duplicate)),
            title=_("Duplicate Item Price"),
        )

    item_price = frappe.get_doc(
        {
            "doctype": "Item Price",
            "item_code": doc.item_code,
            "price_list": doc.price_list,
            "uom": doc.uom,
            "currency": doc.currency,
            "price_list_rate": doc.requested_rate,
            "valid_from": doc.valid_from,
            "valid_upto": doc.valid_upto,
        }
    ).insert(ignore_permissions=True)

    doc.flags.ignore_price_request_lock = True
    doc.status = "Approved"
    doc.approved_by = frappe.session.user
    doc.approval_time = now_datetime()
    doc.created_item_price = item_price.name
    doc.save(ignore_permissions=True)

    _notify_requester(doc, approved=True)
    return {
        "item_price": item_price.name,
        "message": _("Item Price {0} created.").format(item_price.name),
    }


@frappe.whitelist()
def reject_request(name, rejection_reason=None):
    _require_approver()
    doc = _get_request(name)
    if doc.status != "Pending":
        frappe.throw(_("Only pending price requests can be rejected."))

    doc.flags.ignore_price_request_lock = True
    doc.status = "Rejected"
    doc.approved_by = frappe.session.user
    doc.approval_time = now_datetime()
    doc.rejection_reason = rejection_reason or ""
    doc.save(ignore_permissions=True)

    _notify_requester(doc, approved=False)
    return {"message": _("Item Price Request {0} rejected.").format(doc.name)}


def find_matching_item_price(item_code, price_list, uom, currency, valid_from=None, valid_upto=None):
    if not (item_code and price_list and uom and currency):
        return None

    rows = frappe.get_all(
        "Item Price",
        filters={
            "item_code": item_code,
            "price_list": price_list,
            "uom": uom,
            "currency": currency,
        },
        fields=["name", "valid_from", "valid_upto"],
        order_by="modified desc",
    )
    valid_from = str(valid_from or "")
    valid_upto = str(valid_upto or "")
    for row in rows:
        if str(row.get("valid_from") or "") == valid_from and str(row.get("valid_upto") or "") == valid_upto:
            return row.name
    return None


def _get_request(name):
    if not name:
        frappe.throw(_("Item Price Request is required."))
    doc = frappe.get_doc("Item Price Request", name)
    if not doc.has_permission("read"):
        frappe.throw(_("Not permitted."), frappe.PermissionError)
    return doc


def _get_quotation_item(quotation_doc, quotation_item_row):
    row_idx = int(quotation_item_row or 0)
    for row in quotation_doc.get("items") or []:
        if row.idx == row_idx:
            if not row.item_code:
                frappe.throw(_("Selected quotation row does not have an item."))
            return row
    frappe.throw(_("Selected quotation item row was not found."))


def _require_requester():
    if _has_any_role((PRICE_REQUEST_USER_ROLE, PRICING_APPROVER_ROLE, "System Manager")):
        return
    frappe.throw(_("You are not allowed to request item prices."), frappe.PermissionError)


def _require_approver():
    if _has_any_role((PRICING_APPROVER_ROLE, "System Manager")):
        return
    frappe.throw(_("You are not allowed to approve item price requests."), frappe.PermissionError)


def _has_any_role(roles):
    user_roles = set(frappe.get_roles(frappe.session.user))
    return any(role in user_roles for role in roles)


def _get_pricing_approver_users():
    rows = frappe.get_all(
        "Has Role",
        filters={"role": PRICING_APPROVER_ROLE, "parenttype": "User"},
        fields=["parent"],
    )
    enabled = []
    for row in rows:
        user = row.get("parent")
        if frappe.db.get_value("User", user, "enabled"):
            enabled.append(user)
    return sorted(set(enabled))


def _create_internal_notification(for_user, subject, html, document_name, from_user=None):
    if not for_user:
        return
    frappe.get_doc(
        {
            "doctype": "Notification Log",
            "for_user": for_user,
            "type": "Alert",
            "document_type": "Item Price Request",
            "document_name": document_name,
            "subject": subject,
            "email_content": html,
            "from_user": from_user or frappe.session.user,
        }
    ).insert(ignore_permissions=True)


def _notify_pricing_approvers(doc):
    approvers = _get_pricing_approver_users()
    if not approvers:
        return

    subject = f"[SNRG] Item Price Approval Requested - {doc.item_code}"
    message = _build_request_email(doc, heading="Item Price Approval Requested")
    for user in approvers:
        _create_internal_notification(user, subject, message, doc.name, from_user=doc.requested_by)

    recipients = [user for user in approvers if "@" in user]
    if recipients:
        frappe.sendmail(recipients=recipients, subject=subject, message=message, now=True)


def _notify_requester(doc, approved):
    if not doc.requested_by:
        return

    status_label = "Approved" if approved else "Rejected"
    subject = f"[SNRG] Item Price Request {status_label} - {doc.item_code}"
    message = _build_request_email(doc, heading=f"Item Price Request {status_label}")
    _create_internal_notification(
        doc.requested_by,
        subject,
        message,
        doc.name,
        from_user=doc.approved_by or frappe.session.user,
    )
    if "@" in doc.requested_by:
        frappe.sendmail(recipients=[doc.requested_by], subject=subject, message=message, now=True)


def _build_request_email(doc, heading):
    request_link = get_url_to_form("Item Price Request", doc.name)
    quotation_link = get_url_to_form("Quotation", doc.quotation) if doc.quotation else ""
    item_price_link = get_url_to_form("Item Price", doc.created_item_price) if doc.created_item_price else ""
    attachment_html = _build_attachment_html(doc.rate_communication_attachment)
    rate = fmt_money(flt(doc.requested_rate), currency=doc.currency)
    requester = frappe.db.get_value("User", doc.requested_by, "full_name") or doc.requested_by

    item_price_row = ""
    if item_price_link:
        item_price_row = (
            "<tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Created Item Price</td>"
            f"<td style='padding:6px 8px;'><a href='{item_price_link}'>{frappe.utils.escape_html(doc.created_item_price)}</a></td></tr>"
        )

    rejection_row = ""
    if doc.rejection_reason:
        rejection_row = (
            "<tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Rejection Reason</td>"
            f"<td style='padding:6px 8px;'>{frappe.utils.escape_html(doc.rejection_reason)}</td></tr>"
        )

    return f"""
<p>Hello,</p>
<p><strong>{frappe.utils.escape_html(requester or '')}</strong> has an item price request for review.</p>
<h3 style="margin:16px 0 8px;">{frappe.utils.escape_html(heading)}</h3>
<table border="1" cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:100%;margin-bottom:16px;">
  <tbody>
    <tr><td style="padding:6px 8px;font-weight:600;background:#f5f5f5;">Request</td>
        <td style="padding:6px 8px;"><a href="{request_link}">{frappe.utils.escape_html(doc.name)}</a></td></tr>
    <tr><td style="padding:6px 8px;font-weight:600;background:#f5f5f5;">Quotation</td>
        <td style="padding:6px 8px;"><a href="{quotation_link}">{frappe.utils.escape_html(doc.quotation or '')}</a> / Row {frappe.utils.escape_html(str(doc.quotation_item_row or ''))}</td></tr>
    <tr><td style="padding:6px 8px;font-weight:600;background:#f5f5f5;">Customer</td>
        <td style="padding:6px 8px;">{frappe.utils.escape_html(doc.customer or '-')}</td></tr>
    <tr><td style="padding:6px 8px;font-weight:600;background:#f5f5f5;">Item</td>
        <td style="padding:6px 8px;">{frappe.utils.escape_html(doc.item_code or '')} - {frappe.utils.escape_html(doc.item_name or '')}</td></tr>
    <tr><td style="padding:6px 8px;font-weight:600;background:#f5f5f5;">Price List</td>
        <td style="padding:6px 8px;">{frappe.utils.escape_html(doc.price_list or '')}</td></tr>
    <tr><td style="padding:6px 8px;font-weight:600;background:#f5f5f5;">UOM / Currency</td>
        <td style="padding:6px 8px;">{frappe.utils.escape_html(doc.uom or '')} / {frappe.utils.escape_html(doc.currency or '')}</td></tr>
    <tr><td style="padding:6px 8px;font-weight:600;background:#f5f5f5;">Requested Rate</td>
        <td style="padding:6px 8px;font-weight:700;">{rate}</td></tr>
    <tr><td style="padding:6px 8px;font-weight:600;background:#f5f5f5;">Valid From / Upto</td>
        <td style="padding:6px 8px;">{frappe.utils.escape_html(str(doc.valid_from or '-'))} / {frappe.utils.escape_html(str(doc.valid_upto or '-'))}</td></tr>
    <tr><td style="padding:6px 8px;font-weight:600;background:#f5f5f5;">Status</td>
        <td style="padding:6px 8px;">{frappe.utils.escape_html(doc.status or '')}</td></tr>
    <tr><td style="padding:6px 8px;font-weight:600;background:#f5f5f5;">Reason / Notes</td>
        <td style="padding:6px 8px;">{frappe.utils.escape_html(doc.reason or '-')}</td></tr>
    {item_price_row}
    {rejection_row}
  </tbody>
</table>
{attachment_html}
<p style="margin-top:16px;">
  <a href="{request_link}" style="display:inline-block;background:#0d6efd;color:#fff;padding:8px 16px;border-radius:4px;text-decoration:none;font-weight:600;">Open Item Price Request</a>
</p>
<p style="color:#888;font-size:12px;margin-top:16px;">This is an automated notification from SNRG ERPNext.</p>
"""


def _build_attachment_html(file_url):
    if not file_url:
        return "<p><strong>Rate Communication Attachment:</strong> Not attached.</p>"

    absolute_url = file_url if file_url.startswith("http") else get_url(file_url)
    escaped_url = frappe.utils.escape_html(absolute_url)
    label = frappe.utils.escape_html(file_url.split("/")[-1] or "Attachment")
    image_exts = (".png", ".jpg", ".jpeg", ".gif", ".webp")
    preview = ""
    if file_url.lower().split("?")[0].endswith(image_exts):
        preview = (
            f'<div style="margin-top:8px;"><img src="{escaped_url}" '
            'style="max-width:680px;width:100%;height:auto;border:1px solid #ddd;border-radius:4px;" /></div>'
        )

    return (
        "<div style='margin:16px 0;'>"
        "<p style='margin:0 0 8px;'><strong>Rate Communication Attachment:</strong> "
        f"<a href='{escaped_url}'>{label}</a></p>{preview}</div>"
    )
