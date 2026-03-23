"""
snrg_credit_control — Sales Order overrides.

Replaces all 4 DB-stored server scripts:
  - validate()      : approver guard + credit field computation + notification flags
  - before_submit() : credit gate (throws if hold and not approved)
  - after_save()    : sends email notifications
"""

import frappe
from frappe.utils import getdate, today, add_days, fmt_money, formatdate
from snrg_credit_control.credit_status import (
    build_credit_snapshot,
    get_advance_balance,
    stamp_credit_fields,
    zero,
)


# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

def _is_approver(user=None):
    """Return True if the user holds the Credit Approver role."""
    user = user or frappe.session.user
    return frappe.db.exists("Has Role", {"parent": user, "role": "Credit Approver"}) or \
           frappe.db.exists("Has Role", {"parent": user, "role": "System Manager"})


def _val(x):
    return zero(x)


def _esc(val):
    try:
        return frappe.utils.escape_html(val or "")
    except Exception:
        s = str(val or "")
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# validate — runs on every Save (draft or submitted)
# ---------------------------------------------------------------------------

def validate(doc, method=None):
    if not (doc.get("customer") and doc.get("company")):
        return

    # 1. Approver guard — only Credit Approvers may change override fields
    _check_approver_guard(doc)

    # 2. Compute credit fields
    _compute_credit_fields(doc)

    # 3. Detect changes that need notifications (compare against saved values)
    _detect_notification_flags(doc)


def _check_approver_guard(doc):
    """Block non-approvers from editing override cap / valid-till."""
    if doc.is_new():
        return
    prev = frappe.db.get_value(
        "Sales Order",
        doc.name,
        ["custom_snrg_override_cap_amount", "custom_snrg_override_valid_till"],
        as_dict=True,
    ) or {}
    changed_cap  = _val(doc.custom_snrg_override_cap_amount) != _val(prev.get("custom_snrg_override_cap_amount"))
    changed_till = (doc.custom_snrg_override_valid_till or "") != (prev.get("custom_snrg_override_valid_till") or "")
    if (changed_cap or changed_till) and not _is_approver():
        frappe.throw("Only Credit Approvers can set the Override Cap / Valid Till.")


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


def _throw_credit_error(doc, snapshot):
    """Throw a styled HTML credit-hold error dialog."""
    cur = snapshot["currency"]
    today_date = snapshot["today_date"]
    threshold = snapshot["threshold"]
    cutoff = snapshot["cutoff"]
    order_amount = snapshot["amount"]
    rows = snapshot["rows"]
    count = snapshot["overdue_count"]
    total_overdue = snapshot["total_overdue"]
    credit_limit = snapshot["credit_limit"]
    effective_ar = snapshot["effective_ar"]
    advances = snapshot["advances"]

    # ── Styles confirmed to survive Frappe dialog sanitizer ─────────────────
    # Only color, font-size, font-weight, padding, text-align, border-bottom
    # on <th>/<td>, and <hr> work reliably. background/border on <td> is stripped.

    P  = "padding:8px 6px;"                               # cell padding
    BD = "border-bottom:1px solid #e0e0e0;"                # row separator
    TH = f"{P}font-size:11px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.6px;{BD}"

    hr = "<hr style='border:none;border-top:1px solid #e0e0e0;margin:14px 0;'>"

    if count > 0:
        # ── Build invoice rows ───────────────────────────────────────────────
        inv_rows = ""
        for r in rows[:15]:
            age     = (today_date - getdate(r.posting_date)).days
            age_clr = "#c0392b" if age > 90 else ("#e67e22" if age > 75 else "#555"
            )
            inv_rows += (
                f'<tr>'
                f'<td style="{P}{BD}">'
                f'<a href="#Form/Sales%20Invoice/{r.name}" '
                f'style="color:#2980b9;font-weight:600;text-decoration:none;">'
                f'{_esc(r.name)}</a></td>'
                f'<td style="{P}{BD}text-align:center;font-weight:700;color:{age_clr};">{age}d</td>'
                f'<td style="{P}{BD}text-align:right;font-weight:600;">'
                f'{fmt_money(r.outstanding_amount, currency=cur)}</td>'
                f'</tr>'
            )
        if count > 15:
            inv_rows += (
                f'<tr><td colspan="3" style="{P}text-align:center;color:#aaa;font-size:12px;">'
                f'&#8230; and {count - 15} more invoice(s)</td></tr>'
            )

        html = (
            # ── Customer + Overdue summary ───────────────────────────────────
            f'<table width="100%" cellpadding="0" cellspacing="0">'
            f'<tr>'
            f'<td width="48%" style="padding:4px 12px 4px 0;vertical-align:top;">'
            f'<p style="margin:0 0 2px;font-size:11px;color:#888;font-weight:700;'
            f'letter-spacing:.6px;text-transform:uppercase;">&#128100; Customer</p>'
            f'<p style="margin:0 0 2px;font-size:15px;font-weight:700;">{_esc(doc.customer_name)}</p>'
            f'<p style="margin:0;font-size:12px;color:#999;">{_esc(doc.customer)}</p>'
            f'</td>'
            f'<td width="4%"></td>'
            f'<td width="48%" style="padding:4px 0 4px 0;vertical-align:top;">'
            f'<p style="margin:0 0 2px;font-size:11px;color:#c0392b;font-weight:700;'
            f'letter-spacing:.6px;text-transform:uppercase;">&#9888;&#65039; Total Overdue</p>'
            f'<p style="margin:0 0 2px;font-size:22px;font-weight:800;color:#c0392b;">'
            f'{fmt_money(total_overdue, currency=cur)}</p>'
            f'<p style="margin:0;font-size:12px;color:#e67e22;">'
            f'{count} invoice{"s" if count != 1 else ""} &nbsp;&#183;&nbsp; older than {threshold} days</p>'
            f'</td>'
            f'</tr>'
            f'</table>'

            f'{hr}'

            # ── Invoice table ─────────────────────────────────────────────────
            f'<p style="margin:0 0 8px;font-size:12px;color:#888;">'
            f'&#128203; <strong>Overdue Invoices</strong>'
            f'&nbsp;&nbsp;&#183;&nbsp;&nbsp;'
            f'Cutoff date: <strong>{formatdate(cutoff)}</strong>'
            f'&nbsp;&nbsp;&#183;&nbsp;&nbsp;'
            f'Threshold: <strong>{threshold} days</strong></p>'

            f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
            f'<thead>'
            f'<tr>'
            f'<th style="{TH}text-align:left;">Invoice</th>'
            f'<th style="{TH}text-align:center;">Age</th>'
            f'<th style="{TH}text-align:right;">Outstanding</th>'
            f'</tr>'
            f'</thead>'
            f'<tbody>{inv_rows}</tbody>'
            f'<tfoot>'
            f'<tr>'
            f'<td colspan="2" style="{P}font-weight:700;font-size:13px;'
            f'border-top:2px solid #ccc;">&#128197; Total Overdue</td>'
            f'<td style="{P}text-align:right;font-weight:800;font-size:16px;color:#c0392b;'
            f'border-top:2px solid #ccc;">{fmt_money(total_overdue, currency=cur)}</td>'
            f'</tr>'
            f'</tfoot>'
            f'</table>'

            f'{hr}'

            # ── Next step ─────────────────────────────────────────────────────
            f'<p style="margin:0;">'
            f'<strong>&#128161; Next Step</strong><br>'
            f'Use <strong>Credit Control &#8594; Request Approval</strong> '
            f'to notify the Credit Approver team.<br>'
            f'The order can be submitted once the approval is granted.'
            f'</p>'
        )

    else:
        # ── CREDIT LIMIT BREACH ──────────────────────────────────────────────
        breach = (effective_ar + order_amount) - credit_limit

        def brow(label, value, val_color=None, bold_val=False, top_border=False):
            top = "border-top:2px solid #ccc;" if top_border else ""
            vc  = f"color:{val_color};" if val_color else ""
            vw  = "font-weight:800;font-size:15px;" if bold_val else "font-weight:600;"
            return (
                f'<tr>'
                f'<td style="{P}{BD}color:#666;">{label}</td>'
                f'<td style="{P}{BD}text-align:right;{vw}{vc}{top}">{value}</td>'
                f'</tr>'
            )

        html = (
            # ── Customer + Breach summary ────────────────────────────────────
            f'<table width="100%" cellpadding="0" cellspacing="0">'
            f'<tr>'
            f'<td width="48%" style="padding:4px 12px 4px 0;vertical-align:top;">'
            f'<p style="margin:0 0 2px;font-size:11px;color:#888;font-weight:700;'
            f'letter-spacing:.6px;text-transform:uppercase;">&#128100; Customer</p>'
            f'<p style="margin:0 0 2px;font-size:15px;font-weight:700;">{_esc(doc.customer_name)}</p>'
            f'<p style="margin:0;font-size:12px;color:#999;">{_esc(doc.customer)}</p>'
            f'</td>'
            f'<td width="4%"></td>'
            f'<td width="48%" style="padding:4px 0;vertical-align:top;">'
            f'<p style="margin:0 0 2px;font-size:11px;color:#c0392b;font-weight:700;'
            f'letter-spacing:.6px;text-transform:uppercase;">&#128683; Breach Amount</p>'
            f'<p style="margin:0 0 2px;font-size:22px;font-weight:800;color:#c0392b;">'
            f'{fmt_money(breach, currency=cur)}</p>'
            f'<p style="margin:0;font-size:12px;color:#e67e22;">Exceeds approved credit limit</p>'
            f'</td>'
            f'</tr>'
            f'</table>'

            f'{hr}'

            # ── Breakdown table ───────────────────────────────────────────────
            f'<p style="margin:0 0 8px;font-size:12px;color:#888;">'
            f'&#128200; <strong>Credit Limit Breakdown</strong></p>'

            f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
            f'<tbody>'
            f'{brow("&#127974; Credit Limit", fmt_money(credit_limit, currency=cur))}'
            f'{brow("&#128196; Current AR Outstanding", fmt_money(effective_ar, currency=cur))}'
            f'{brow("&#128179; Advance Balance (credit)", fmt_money(advances, currency=cur))}'
            f'{brow("&#128666; This Order", fmt_money(order_amount, currency=cur))}'
            f'<tr>'
            f'<td style="{P}font-weight:700;font-size:13px;border-top:2px solid #ccc;">'
            f'&#9889; Total Exposure</td>'
            f'<td style="{P}text-align:right;font-weight:800;font-size:15px;color:#c0392b;'
            f'border-top:2px solid #ccc;">'
            f'{fmt_money(effective_ar + order_amount, currency=cur)}'
            f'<br><span style="font-size:11px;color:#888;font-weight:400;">'
            f'vs limit {fmt_money(credit_limit, currency=cur)}</span>'
            f'</td>'
            f'</tr>'
            f'</tbody>'
            f'</table>'

            f'{hr}'

            # ── Next step ─────────────────────────────────────────────────────
            f'<p style="margin:0;">'
            f'<strong>&#128161; Next Step</strong><br>'
            f'Use <strong>Credit Control &#8594; Request Approval</strong> '
            f'to notify the Credit Approver team.<br>'
            f'The order can be submitted once the approval is granted.'
            f'</p>'
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


def _notify_approvers(doc):
    """Send email to all users with the Credit Approver role."""
    approver_users = frappe.get_all(
        "Has Role",
        filters={"role": "Credit Approver"},
        fields=["parent"],
    )
    recipients = [u.parent for u in approver_users if "@" in (u.parent or "")]
    if not recipients:
        return

    order_amount = _val(doc.grand_total or doc.rounded_total)
    cur          = doc.currency or "INR"
    so_link      = frappe.utils.get_url_to_form("Sales Order", doc.name)

    # Build PTP summary from child table
    ptp_rows = ""
    for entry in (doc.custom_snrg_ptp_entries or []):
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
  </tbody>
</table>
<p><strong>Promise to Pay Details:</strong></p>
{ptp_table}
<p style='margin-top:16px;'>
  <a href='{so_link}' style='background:#0d6efd;color:#fff;padding:8px 16px;border-radius:4px;text-decoration:none;'>
    Open Sales Order
  </a>
</p>
<p style='color:#888;font-size:12px;margin-top:16px;'>
  This is an automated notification from SNRG ERPNext.
</p>
"""
    frappe.sendmail(
        recipients=recipients,
        subject=subject,
        message=message,
        now=True,
    )


def _notify_requester(doc):
    """Send approval confirmation email to the SO owner."""
    if not doc.owner or "@" not in doc.owner:
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
    frappe.sendmail(
        recipients=[doc.owner],
        subject=subject,
        message=message,
        now=True,
    )
