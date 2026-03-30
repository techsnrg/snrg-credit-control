"""
snrg_credit_control — Sales Order overrides.

Replaces all 4 DB-stored server scripts:
  - validate()      : approver guard + credit field computation + notification flags
  - before_submit() : credit gate (throws if hold and not approved)
  - after_save()    : sends email notifications
"""

from urllib.parse import quote

import frappe
from frappe.utils import getdate, today, add_days, fmt_money, formatdate
from snrg_credit_control.credit_status import (
    build_credit_snapshot,
    escape_html,
    get_advance_balance,
    render_credit_details_html,
    stamp_credit_fields,
    zero,
)
from snrg_credit_control.ptp import (
    build_ptp_reference_label,
    get_active_credit_ptp,
    get_ptp_references_for_sales_order,
    get_sales_order_ptp_docs,
)


# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

def _is_approver(user=None):
    """Return True if the user holds the Credit Approver role."""
    user = user or frappe.session.user
    return frappe.db.exists("Has Role", {"parent": user, "role": "Credit Approver"}) or \
           frappe.db.exists("Has Role", {"parent": user, "role": "System Manager"})


def _is_selected_approver(doc, user=None):
    user = user or frappe.session.user
    target = _get_employee_notification_target(doc.custom_snrg_requested_to_employee)
    return bool(user and target.get("user_id") == user)


def _can_approve_request(doc, user=None):
    return _is_approver(user) or _is_selected_approver(doc, user)


def _val(x):
    return zero(x)


def _esc(val):
    return escape_html(val)


# ---------------------------------------------------------------------------
# validate — runs on every Save (draft or submitted)
# ---------------------------------------------------------------------------

def validate(doc, method=None):
    if not (doc.get("customer") and doc.get("company")):
        return

    # 1. Approver guard — only Credit Approvers may change override fields
    _check_approver_guard(doc)

    # 1a. Ensure the selected approver can actually receive the request
    _validate_request_target(doc)

    # 2. Compute credit fields
    _compute_credit_fields(doc)

    # 3. Detect changes that need notifications (compare against saved values)
    _detect_notification_flags(doc)


def _check_approver_guard(doc):
    """Block non-approvers from editing override cap / valid-till."""
    if doc.is_new():
        return

    # Allow normal business users to submit an already-approved document
    # without re-triggering the override editor guard on the submit save cycle.
    if getattr(doc.flags, "in_submit", False):
        return

    prev = frappe.db.get_value(
        "Sales Order",
        doc.name,
        ["custom_snrg_override_cap_amount", "custom_snrg_override_valid_till"],
        as_dict=True,
    ) or {}

    changed_cap = _val(doc.custom_snrg_override_cap_amount) != _val(prev.get("custom_snrg_override_cap_amount"))

    current_till = getdate(doc.custom_snrg_override_valid_till) if doc.custom_snrg_override_valid_till else None
    previous_till = getdate(prev.get("custom_snrg_override_valid_till")) if prev.get("custom_snrg_override_valid_till") else None
    changed_till = current_till != previous_till

    if (changed_cap or changed_till) and not _can_approve_request(doc):
        frappe.throw("Only Credit Approvers can set the Override Cap / Valid Till.")


def _validate_request_target(doc):
    if not doc.custom_snrg_request_time:
        return

    if not doc.custom_snrg_requested_to_employee:
        frappe.throw("Select the employee who should receive this credit approval request.")

    target = _get_employee_notification_target(doc.custom_snrg_requested_to_employee)
    if target.get("user_id") and target.get("email"):
        return

    frappe.throw(
        "The selected employee must have a linked ERPNext user and an email address "
        "so the approval request can be sent through both internal notification and email."
    )


def _get_ptp_reference_label(row):
    return build_ptp_reference_label(row)


def _compute_credit_fields(doc):
    """Recompute all credit check fields. Non-blocking on save."""
    snapshot = build_credit_snapshot(
        customer=doc.customer,
        company=doc.company,
        amount=doc.grand_total or doc.rounded_total,
        currency=doc.currency,
        more_prefix="…",
    )
    stamp_credit_fields(doc, snapshot)

    # Non-blocking heads-up on save (not on submit — submit throws instead)
    action = (frappe.form_dict.get("action") or "").lower()
    if action != "submit" and snapshot["needs_review"]:
        frappe.msgprint(
            "Heads-up: credit risk detected for this customer. "
            "Submitting this order will be blocked until credit is approved.",
            indicator="orange",
            alert=True,
        )


def _detect_notification_flags(doc):
    """Set doc.flags for after_save to pick up and send emails."""
    if doc.is_new():
        return
    prev = frappe.db.get_value(
        "Sales Order",
        doc.name,
        ["custom_snrg_request_time", "custom_credit_approval_status"],
        as_dict=True,
    ) or {}

    # New approval request
    new_req_time  = doc.custom_snrg_request_time or ""
    prev_req_time = prev.get("custom_snrg_request_time") or ""
    if new_req_time and new_req_time != str(prev_req_time):
        doc.flags.notify_approvers = True

    # Status flipped to Approved
    new_status  = (doc.custom_credit_approval_status or "").lower()
    prev_status = (prev.get("custom_credit_approval_status") or "").lower()
    if new_status == "approved" and prev_status != "approved":
        doc.flags.notify_requester = True


# ---------------------------------------------------------------------------
# before_submit — credit gate
# ---------------------------------------------------------------------------

def before_submit(doc, method=None):
    if not (doc.get("customer") and doc.get("company")):
        return

    # Re-query live data — never trust stamped fields alone at submit time
    snapshot = build_credit_snapshot(
        customer=doc.customer,
        company=doc.company,
        amount=doc.grand_total or doc.rounded_total,
        currency=doc.currency,
        more_prefix="…",
    )

    if not snapshot["needs_review"]:
        return

    # Check valid approval
    today_date    = getdate(today())
    cap           = _val(doc.custom_snrg_override_cap_amount)
    vt            = doc.custom_snrg_override_valid_till
    order_amount  = _val(doc.grand_total or doc.rounded_total)
    approval_status = (doc.custom_credit_approval_status or "").lower()

    valid_till_ok = bool(vt and getdate(vt) >= today_date)
    approved_ok   = valid_till_ok and (order_amount <= cap) and (approval_status == "approved")

    if approved_ok:
        return  # all good — allow submit

    # Build a rich HTML error
    _throw_credit_error(doc, snapshot)


@frappe.whitelist()
def get_credit_status(customer, company, currency=None, amount=0):
    if not customer or not company:
        return {}

    snapshot = build_credit_snapshot(
        customer=customer,
        company=company,
        amount=amount,
        currency=currency,
        more_prefix="…",
    )

    return {
        "status": snapshot["status"],
        "reason_code": snapshot["reason_code"],
        "overdue_count": snapshot["overdue_count"],
        "total_overdue": snapshot["total_overdue"],
        "effective_ar": snapshot["effective_ar"],
        "credit_limit": snapshot["credit_limit"],
        "details": snapshot["details"],
        "currency": snapshot["currency"],
    }


@frappe.whitelist()
def get_ptp_references(sales_order):
    if not sales_order:
        return []

    doc = frappe.get_doc("Sales Order", sales_order)
    if not doc.has_permission("read"):
        frappe.throw("Not permitted.", frappe.PermissionError)

    return get_ptp_references_for_sales_order(sales_order, actionable_only=True)


@frappe.whitelist()
def request_credit_approval(
    sales_order,
    approver_employee,
    ptp_by,
    ptp_date,
    commitment_date,
    committed_amount,
    payment_mode,
    cheque_number=None,
    remarks=None,
):
    if not sales_order:
        frappe.throw("Sales Order is required.")

    doc = frappe.get_doc("Sales Order", sales_order)
    if not doc.has_permission("write"):
        frappe.throw("Not permitted.", frappe.PermissionError)

    amount = _val(doc.grand_total or doc.rounded_total)
    now = frappe.utils.now_datetime()

    frappe.db.set_value(
        "Sales Order",
        doc.name,
        {
            "custom_snrg_request_time": now,
            "custom_snrg_request_amount": amount,
            "custom_snrg_requested_to_employee": approver_employee,
            "custom_credit_approval_status": "Pending",
        },
        update_modified=True,
    )

    ptp = frappe.get_doc(
        {
            "doctype": "Credit PTP",
            "sales_order": doc.name,
            "customer": doc.customer,
            "customer_name": doc.customer_name,
            "company": doc.company,
            "currency": doc.currency,
            "requested_to_employee": approver_employee,
            "requested_by": frappe.session.user,
            "ptp_by": ptp_by,
            "ptp_date": ptp_date,
            "commitment_date": commitment_date,
            "committed_amount": _val(committed_amount),
            "payment_mode": payment_mode,
            "cheque_number": cheque_number or "",
            "remarks": remarks or "",
        }
    ).insert(ignore_permissions=True)

    refreshed_doc = frappe.get_doc("Sales Order", doc.name)
    _notify_approvers(refreshed_doc, ptp_docs=[frappe._dict(ptp.as_dict())])
    return {"message": "Approval request sent successfully.", "ptp": ptp.name}


@frappe.whitelist()
def link_payment_entry_from_report(sales_order=None, ptp_entry_id=None, payment_entry=None, allocated_amount=0, remarks=None):
    if not ptp_entry_id or not payment_entry:
        frappe.throw("PTP reference and Payment Entry are required.")

    ptp = frappe.get_doc("Credit PTP", ptp_entry_id)
    if not ptp.has_permission("write"):
        frappe.throw("Not permitted.", frappe.PermissionError)

    ptp.append(
        "payment_links",
        {
            "payment_entry": payment_entry,
            "allocated_amount": _val(allocated_amount),
            "remarks": remarks or "",
        },
    )
    ptp.save(ignore_permissions=True)

    return {"message": "Payment Entry linked successfully."}


@frappe.whitelist()
def get_active_ptp_for_sales_order(sales_order):
    if not sales_order:
        return {}

    active = get_active_credit_ptp(sales_order)
    return active[0] if active else {}


@frappe.whitelist(allow_guest=True)
def approve_from_email(name):
    if not name:
        frappe.throw("Sales Order is required.")

    if frappe.session.user == "Guest":
        return _redirect_to_login(name)

    doc = frappe.get_doc("Sales Order", name)
    if not doc.custom_snrg_request_time:
        frappe.throw("This Sales Order does not have a pending credit approval request.")

    if not _can_approve_request(doc):
        frappe.throw("You are not allowed to approve this Sales Order.", frappe.PermissionError)

    if (doc.custom_credit_approval_status or "").lower() == "approved":
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = frappe.utils.get_url_to_form("Sales Order", doc.name)
        return

    order_amount = _val(doc.grand_total or doc.rounded_total)
    approved_cap = min(_val(doc.custom_snrg_request_amount or order_amount), order_amount)
    valid_till = add_days(today(), 7)

    doc.custom_snrg_override_cap_amount = approved_cap
    doc.custom_snrg_override_valid_till = valid_till
    doc.custom_snrg_approver = frappe.session.user
    doc.custom_snrg_approval_time = frappe.utils.now_datetime()
    doc.custom_credit_approval_status = "Approved"
    doc.save(ignore_permissions=True)

    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = frappe.utils.get_url_to_form("Sales Order", doc.name)


def _redirect_to_login(name):
    approve_url = frappe.utils.get_url(
        f"/api/method/snrg_credit_control.overrides.sales_order.approve_from_email?name={quote(name)}"
    )
    login_url = frappe.utils.get_url(f"/login?redirect-to={quote(approve_url, safe='')}")
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = login_url


def _get_approve_from_email_url(doc):
    return frappe.utils.get_url(
        f"/api/method/snrg_credit_control.overrides.sales_order.approve_from_email?name={quote(doc.name)}"
    )


def _throw_credit_error(doc, snapshot):
    """Throw a styled HTML credit-hold error dialog."""
    html = render_credit_details_html(
        snapshot=snapshot,
        customer=doc.customer,
        customer_name=doc.customer_name,
        next_step_html=(
            "<p style='margin:0;'>"
            "<strong>&#128161; Next Step</strong><br>"
            "Use <strong>Credit Control &#8594; Request Approval</strong> "
            "to notify the Credit Approver team.<br>"
            "The order can be submitted once the approval is granted."
            "</p>"
        ),
    )
    frappe.throw(html, title="🚫 Credit Hold — Submission Blocked")


# ---------------------------------------------------------------------------
# after_save — email notifications
# ---------------------------------------------------------------------------

def after_save(doc, method=None):
    if getattr(doc.flags, "notify_approvers", False):
        _notify_approvers(doc)
    if getattr(doc.flags, "notify_requester", False):
        _notify_requester(doc)


def _get_employee_notification_target(employee):
    if not employee:
        return {}

    row = frappe.db.get_value(
        "Employee",
        employee,
        ["employee_name", "user_id", "company_email", "personal_email"],
        as_dict=True,
    ) or {}

    user_id = row.get("user_id")
    email = (user_id if user_id and "@" in user_id else None) or row.get("company_email") or row.get("personal_email")

    return {
        "employee": employee,
        "employee_name": row.get("employee_name") or employee,
        "user_id": user_id,
        "email": email,
    }


def _create_internal_notification(for_user, subject, html, document_type, document_name, from_user=None):
    if not for_user:
        return

    frappe.get_doc(
        {
            "doctype": "Notification Log",
            "for_user": for_user,
            "type": "Alert",
            "document_type": document_type,
            "document_name": document_name,
            "subject": subject,
            "email_content": html,
            "from_user": from_user or frappe.session.user,
        }
    ).insert(ignore_permissions=True)


def _notify_approvers(doc, ptp_docs=None):
    """Send notification to the selected employee approver."""
    target = _get_employee_notification_target(doc.custom_snrg_requested_to_employee)
    if not target:
        return

    order_amount = _val(doc.grand_total or doc.rounded_total)
    cur          = doc.currency or "INR"
    so_link      = frappe.utils.get_url_to_form("Sales Order", doc.name)
    approve_link = _get_approve_from_email_url(doc)
    ptp_docs = ptp_docs or get_sales_order_ptp_docs(doc.name)

    # Build PTP summary from child table
    ptp_rows = ""
    for entry in (ptp_docs or []):
        ptp_rows += (
            f"<tr>"
            f"<td style='padding:4px 8px;'>{_esc(entry.get('ptp_by_name') or entry.get('ptp_by') or '—')}</td>"
            f"<td style='padding:4px 8px;'>{_esc(str(entry.get('commitment_date') or '—'))}</td>"
            f"<td style='padding:4px 8px;'>{fmt_money(_val(entry.get('committed_amount')), currency=cur)}</td>"
            f"<td style='padding:4px 8px;'>{_esc(entry.get('payment_mode') or '—')}</td>"
            f"<td style='padding:4px 8px;'>{_esc(entry.get('remarks') or '—')}</td>"
            f"</tr>"
        )
    ptp_table = (
        f"<table border='1' cellpadding='0' cellspacing='0' style='border-collapse:collapse;width:100%;'>"
        f"<thead><tr style='background:#f5f5f5;'>"
        f"<th style='padding:6px 8px;text-align:left;'>Committed By</th>"
        f"<th style='padding:6px 8px;text-align:left;'>Payment By</th>"
        f"<th style='padding:6px 8px;text-align:left;'>Amount</th>"
        f"<th style='padding:6px 8px;text-align:left;'>Mode</th>"
        f"<th style='padding:6px 8px;text-align:left;'>Remarks</th>"
        f"</tr></thead><tbody>{ptp_rows}</tbody></table>"
    ) if ptp_rows else "<p><em>No PTP entries provided.</em></p>"

    requester_name = frappe.db.get_value("User", doc.owner, "full_name") or doc.owner

    subject = f"[SNRG] Credit Approval Requested — {doc.name} ({doc.customer_name})"
    message = f"""
<p>Hello,</p>
<p><strong>{requester_name}</strong> has requested credit approval for the following Sales Order:</p>
<table border='1' cellpadding='0' cellspacing='0' style='border-collapse:collapse;width:100%;margin-bottom:16px;'>
  <tbody>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Sales Order</td>
        <td style='padding:6px 8px;'><a href='{so_link}'>{_esc(doc.name)}</a></td></tr>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Customer</td>
        <td style='padding:6px 8px;'>{_esc(doc.customer_name)} ({_esc(doc.customer)})</td></tr>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Order Amount</td>
        <td style='padding:6px 8px;'>{fmt_money(order_amount, currency=cur)}</td></tr>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Credit Check Status</td>
        <td style='padding:6px 8px;'>{_esc(doc.custom_snrg_credit_check_status or 'Not Run')}</td></tr>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Overdue Invoices</td>
        <td style='padding:6px 8px;'>{doc.custom_snrg_overdue_count_terms or 0} invoice(s) —
        {fmt_money(_val(doc.custom_snrg_overdue_amount_terms), currency=cur)}</td></tr>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Requested To</td>
        <td style='padding:6px 8px;'>{_esc(target.get('employee_name') or doc.custom_snrg_requested_to_employee or '—')}</td></tr>
  </tbody>
</table>
<p><strong>Promise to Pay Details:</strong></p>
{ptp_table}
<p style='margin-top:16px;'>
  <a href='{approve_link}' style='display:inline-block;background:#16a34a;color:#fff;padding:8px 16px;border-radius:4px;text-decoration:none;font-weight:600;margin-right:8px;'>
    Approve Order
  </a>
  <a href='{so_link}' style='display:inline-block;background:#0d6efd;color:#fff;padding:8px 16px;border-radius:4px;text-decoration:none;'>
    Open Sales Order
  </a>
</p>
<p style='font-size:12px;color:#666;margin-top:10px;'>
  The approve button works for the logged-in selected approver and applies the standard quick-approval defaults.
</p>
<p style='color:#888;font-size:12px;margin-top:16px;'>
  This is an automated notification from SNRG ERPNext.
</p>
"""
    if target.get("user_id"):
        _create_internal_notification(
            for_user=target["user_id"],
            subject=subject,
            html=message,
            document_type="Sales Order",
            document_name=doc.name,
            from_user=doc.owner,
        )

    if target.get("email"):
        frappe.sendmail(
            recipients=[target["email"]],
            subject=subject,
            message=message,
            now=True,
        )


def _notify_requester(doc):
    """Send approval confirmation notification to the SO owner."""
    if not doc.owner:
        return

    cur        = doc.currency or "INR"
    cap        = _val(doc.custom_snrg_override_cap_amount)
    vt         = doc.custom_snrg_override_valid_till
    approver   = frappe.db.get_value("User", doc.custom_snrg_approver, "full_name") or doc.custom_snrg_approver or "—"
    so_link    = frappe.utils.get_url_to_form("Sales Order", doc.name)
    order_amount = _val(doc.grand_total or doc.rounded_total)

    subject = f"[SNRG] Credit Approved — {doc.name} ({doc.customer_name})"
    message = f"""
<p>Hello,</p>
<p>Your credit approval request for Sales Order <strong>{_esc(doc.name)}</strong> has been
<span style='color:green;font-weight:700;'>Approved</span>.</p>
<table border='1' cellpadding='0' cellspacing='0' style='border-collapse:collapse;width:100%;margin-bottom:16px;'>
  <tbody>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Sales Order</td>
        <td style='padding:6px 8px;'><a href='{so_link}'>{_esc(doc.name)}</a></td></tr>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Customer</td>
        <td style='padding:6px 8px;'>{_esc(doc.customer_name)} ({_esc(doc.customer)})</td></tr>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Order Amount</td>
        <td style='padding:6px 8px;'>{fmt_money(order_amount, currency=cur)}</td></tr>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Approved Cap</td>
        <td style='padding:6px 8px;color:green;font-weight:700;'>{fmt_money(cap, currency=cur)}</td></tr>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Valid Till</td>
        <td style='padding:6px 8px;'>{_esc(str(vt or '—'))}</td></tr>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Approved By</td>
        <td style='padding:6px 8px;'>{_esc(approver)}</td></tr>
  </tbody>
</table>
<p>You may now submit the Sales Order.</p>
<p style='margin-top:16px;'>
  <a href='{so_link}' style='background:#28a745;color:#fff;padding:8px 16px;border-radius:4px;text-decoration:none;'>
    Open Sales Order
  </a>
</p>
<p style='color:#888;font-size:12px;margin-top:16px;'>
  This is an automated notification from SNRG ERPNext.
</p>
"""
    _create_internal_notification(
        for_user=doc.owner,
        subject=subject,
        html=message,
        document_type="Sales Order",
        document_name=doc.name,
        from_user=doc.custom_snrg_approver or frappe.session.user,
    )

    if "@" in doc.owner:
        frappe.sendmail(
            recipients=[doc.owner],
            subject=subject,
            message=message,
            now=True,
        )
