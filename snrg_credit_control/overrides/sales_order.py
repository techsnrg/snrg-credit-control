"""
snrg_credit_control — Sales Order overrides.

Replaces all 4 DB-stored server scripts:
  - validate()      : approver guard + credit field computation + notification flags
  - before_submit() : credit gate (throws if hold and not approved)
  - after_save()    : sends email notifications
"""

import frappe
from frappe.utils import getdate, today, add_days, fmt_money, formatdate


# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLD_DAYS = 75


def _get_threshold(customer):
    """Return credit lock days for this customer, falling back to default."""
    days = frappe.db.get_value("Customer", customer, "custom_credit_lock_days")
    try:
        return int(days) if days else DEFAULT_THRESHOLD_DAYS
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLD_DAYS


def _is_approver(user=None):
    """Return True if the user holds the Credit Approver role."""
    user = user or frappe.session.user
    return frappe.db.exists("Has Role", {"parent": user, "role": "Credit Approver"}) or \
           frappe.db.exists("Has Role", {"parent": user, "role": "System Manager"})


def _val(x):
    return x or 0


def _esc(val):
    try:
        return frappe.utils.escape_html(val or "")
    except Exception:
        s = str(val or "")
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _get_overdue_invoices(customer, company, cutoff):
    return frappe.get_all(
        "Sales Invoice",
        filters={
            "docstatus": 1,
            "is_return": 0,
            "customer": customer,
            "company": company,
            "outstanding_amount": (">", 0),
            "posting_date": ("<=", cutoff),
        },
        fields=["name", "posting_date", "outstanding_amount"],
        order_by="posting_date asc",
    )


def _get_credit_limit(customer, company):
    return frappe.db.get_value(
        "Customer Credit Limit",
        {"parent": customer, "company": company},
        "credit_limit",
    ) or 0


def _get_total_outstanding(customer, company):
    val = frappe.db.sql(
        """
        SELECT COALESCE(SUM(outstanding_amount), 0)
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND is_return  = 0
          AND customer   = %s
          AND company    = %s
        """,
        (customer, company),
    )[0][0]
    return val or 0


def _get_advance_balance(customer, company):
    val = frappe.db.sql(
        """
        SELECT ABS(COALESCE(SUM(outstanding_amount), 0))
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND is_return  = 0
          AND customer   = %s
          AND company    = %s
          AND outstanding_amount < 0
        """,
        (customer, company),
    )[0][0]
    return val or 0


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
    today_date = getdate(today())
    threshold  = _get_threshold(doc.customer)
    cutoff     = add_days(today_date, -threshold)
    cur        = doc.currency or frappe.db.get_value("Company", doc.company, "default_currency") or "INR"

    rows            = _get_overdue_invoices(doc.customer, doc.company, cutoff)
    count           = len(rows)
    total_overdue   = sum(r.outstanding_amount for r in rows) if rows else 0
    credit_limit    = _get_credit_limit(doc.customer, doc.company)
    total_outstanding = _get_total_outstanding(doc.customer, doc.company)
    effective_ar    = max(total_outstanding, 0)   # treat credit balance as zero
    order_amount    = _val(doc.grand_total or doc.rounded_total)
    limit_breach    = bool(credit_limit and (effective_ar + order_amount) > credit_limit)
    advances        = _get_advance_balance(doc.customer, doc.company)

    # Detail string (top 15 overdue invoices)
    detail_lines = []
    for r in rows[:15]:
        age = (today_date - getdate(r.posting_date)).days
        detail_lines.append(
            f"{r.name} ({fmt_money(r.outstanding_amount, currency=cur)}, {age}d)"
        )
    if count > 15:
        detail_lines.append(f"… +{count - 15} more")

    # Stamp fields
    doc.custom_snrg_overdue_count_terms    = count
    doc.custom_snrg_overdue_amount_terms   = total_overdue
    doc.custom_snrg_exposure_at_check      = effective_ar
    doc.custom_snrg_credit_limit_at_check  = credit_limit
    doc.custom_snrg_credit_check_details   = "; ".join(detail_lines)

    if count > 0:
        doc.custom_snrg_credit_check_status      = "Credit Hold"
        doc.custom_snrg_credit_check_reason_code = "Overdue>Terms"
    elif limit_breach:
        doc.custom_snrg_credit_check_status      = "Credit Hold"
        doc.custom_snrg_credit_check_reason_code = "Over-Limit"
    else:
        doc.custom_snrg_credit_check_status      = "Credit OK"
        doc.custom_snrg_credit_check_reason_code = ""

    # Non-blocking heads-up on save (not on submit — submit throws instead)
    action = (frappe.form_dict.get("action") or "").lower()
    if action != "submit" and (count > 0 or limit_breach):
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
    today_date   = getdate(today())
    threshold    = _get_threshold(doc.customer)
    cutoff       = add_days(today_date, -threshold)
    rows         = _get_overdue_invoices(doc.customer, doc.company, cutoff)
    overdue_count = len(rows)

    credit_limit  = _get_credit_limit(doc.customer, doc.company)
    total_ar      = _get_total_outstanding(doc.customer, doc.company)
    effective_ar  = max(total_ar, 0)
    order_amount  = _val(doc.grand_total or doc.rounded_total)
    limit_breach  = bool(credit_limit and (effective_ar + order_amount) > credit_limit)

    needs_approval = (overdue_count > 0) or limit_breach
    if not needs_approval:
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
    cur = doc.currency or frappe.db.get_value("Company", doc.company, "default_currency") or "INR"
    _throw_credit_error(doc, cur, today_date)


def _throw_credit_error(doc, cur, today_date):
    """Throw a styled HTML credit-hold error dialog."""
    threshold     = _get_threshold(doc.customer)
    cutoff        = add_days(today_date, -threshold)
    order_amount  = _val(doc.grand_total or doc.rounded_total)
    rows          = _get_overdue_invoices(doc.customer, doc.company, cutoff)
    count         = len(rows)
    total_overdue = sum(r.outstanding_amount for r in rows) if rows else 0
    credit_limit  = _get_credit_limit(doc.customer, doc.company)
    total_ar      = _get_total_outstanding(doc.customer, doc.company)
    effective_ar  = max(total_ar, 0)
    advances      = _get_advance_balance(doc.customer, doc.company)

    # ── Shared style tokens ──────────────────────────────────────────────────
    LBL  = "font-size:10px;font-weight:700;letter-spacing:1.1px;text-transform:uppercase;opacity:0.45;margin-bottom:5px;"
    TD   = "padding:9px 12px;vertical-align:middle;border-bottom:1px solid rgba(128,128,128,0.12);"
    TH   = "padding:8px 12px;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;opacity:0.4;"
    NEXT = ("background:rgba(59,130,246,0.09);border:1px solid rgba(59,130,246,0.22);"
            "border-radius:8px;padding:12px 14px;margin-top:14px;font-size:13px;")

    # ── Two-column summary (TABLE-based — works in all Frappe dialog contexts) ─
    def summary_row(left_html, right_html):
        return (
            f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-bottom:14px;">'
            f'<tr>'
            f'<td width="49%" style="background:rgba(255,255,255,0.05);'
            f'border:1px solid rgba(255,255,255,0.1);border-radius:8px;'
            f'padding:12px 14px;vertical-align:top;">{left_html}</td>'
            f'<td width="2%"></td>'
            f'<td width="49%" style="background:rgba(239,68,68,0.1);'
            f'border:1px solid rgba(239,68,68,0.28);border-radius:8px;'
            f'padding:12px 14px;vertical-align:top;">{right_html}</td>'
            f'</tr></table>'
        )

    # ── Next-step panel ──────────────────────────────────────────────────────
    next_step = (
        f'<div style="{NEXT}">'
        f'<div style="font-size:10px;font-weight:700;letter-spacing:.9px;text-transform:uppercase;'
        f'color:#60a5fa;margin-bottom:4px;">Next Step</div>'
        f'Use <b>Credit Control &#8594; Request Approval</b> to notify the Credit Approver team. '
        f'The order can be submitted once approved.</div>'
    )

    if count > 0:
        # ── OVERDUE INVOICES ─────────────────────────────────────────────────
        left = (
            f'<div style="{LBL}">Customer</div>'
            f'<div style="font-size:14px;font-weight:700;margin-bottom:2px;">{_esc(doc.customer_name)}</div>'
            f'<div style="font-size:11px;opacity:0.4;">{_esc(doc.customer)}</div>'
        )
        right = (
            f'<div style="{LBL}color:#f87171;">Overdue</div>'
            f'<div style="font-size:22px;font-weight:800;color:#ef4444;letter-spacing:-.5px;">'
            f'{fmt_money(total_overdue, currency=cur)}</div>'
            f'<div style="font-size:11px;color:#f87171;margin-top:3px;">'
            f'{count} invoice{"s" if count != 1 else ""} past {threshold} days</div>'
        )

        # Invoice rows
        inv_rows = ""
        for i, r in enumerate(rows[:15]):
            age     = (today_date - getdate(r.posting_date)).days
            age_clr = "#ef4444" if age > 90 else ("#f97316" if age > 75 else "inherit")
            row_bg  = "rgba(255,255,255,0.025)" if i % 2 == 0 else "transparent"
            inv_rows += (
                f'<tr style="background:{row_bg};">'
                f'<td style="{TD}">'
                f'<a href="#Form/Sales%20Invoice/{r.name}" '
                f'style="color:#60a5fa;text-decoration:none;font-weight:600;">'
                f'{_esc(r.name)}</a></td>'
                f'<td style="{TD}text-align:center;font-weight:700;color:{age_clr};">{age}d</td>'
                f'<td style="{TD}text-align:right;font-weight:600;">'
                f'{fmt_money(r.outstanding_amount, currency=cur)}</td>'
                f'</tr>'
            )
        if count > 15:
            inv_rows += (
                f'<tr><td colspan="3" style="padding:8px 12px;text-align:center;'
                f'opacity:0.35;font-size:12px;">… and {count - 15} more</td></tr>'
            )

        inv_table = (
            f'<div style="font-size:10px;opacity:0.35;letter-spacing:.5px;'
            f'text-transform:uppercase;margin-bottom:8px;">'
            f'Cutoff date: {formatdate(cutoff)}</div>'
            f'<table width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;border:1px solid rgba(128,128,128,0.15);border-radius:8px;">'
            f'<thead><tr style="background:rgba(255,255,255,0.04);">'
            f'<th style="{TH}text-align:left;">Invoice</th>'
            f'<th style="{TH}text-align:center;">Age</th>'
            f'<th style="{TH}text-align:right;">Outstanding</th>'
            f'</tr></thead>'
            f'<tbody>{inv_rows}</tbody>'
            f'<tfoot><tr style="background:rgba(239,68,68,0.07);'
            f'border-top:2px solid rgba(239,68,68,0.2);">'
            f'<td colspan="2" style="padding:10px 12px;font-weight:700;font-size:13px;">Total Overdue</td>'
            f'<td style="padding:10px 12px;text-align:right;font-weight:800;font-size:15px;color:#ef4444;">'
            f'{fmt_money(total_overdue, currency=cur)}</td>'
            f'</tr></tfoot></table>'
        )

        html = (
            f'<div style="font-size:13px;line-height:1.5;">'
            f'{summary_row(left, right)}'
            f'{inv_table}'
            f'{next_step}'
            f'</div>'
        )

    else:
        # ── CREDIT LIMIT BREACH ──────────────────────────────────────────────
        breach = (effective_ar + order_amount) - credit_limit

        left = (
            f'<div style="{LBL}">Customer</div>'
            f'<div style="font-size:14px;font-weight:700;margin-bottom:2px;">{_esc(doc.customer_name)}</div>'
            f'<div style="font-size:11px;opacity:0.4;">{_esc(doc.customer)}</div>'
        )
        right = (
            f'<div style="{LBL}color:#f87171;">Breach Amount</div>'
            f'<div style="font-size:22px;font-weight:800;color:#ef4444;letter-spacing:-.5px;">'
            f'{fmt_money(breach, currency=cur)}</div>'
            f'<div style="font-size:11px;color:#f87171;margin-top:3px;">Exceeds credit limit</div>'
        )

        def brow(label, value, bold=False, red=False):
            val_style = "text-align:right;font-weight:" + ("800;font-size:15px;color:#ef4444;" if red else ("700;" if bold else "600;"))
            return (
                f'<tr><td style="{TD}opacity:0.6;">{label}</td>'
                f'<td style="{TD}{val_style}">{value}</td></tr>'
            )

        breakdown = (
            f'<table width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;border:1px solid rgba(128,128,128,0.15);border-radius:8px;margin-bottom:0;">'
            f'<tbody>'
            f'{brow("Credit Limit", fmt_money(credit_limit, currency=cur))}'
            f'{brow("Current AR (net)", fmt_money(effective_ar, currency=cur))}'
            f'{brow("Advance Balance", fmt_money(advances, currency=cur))}'
            f'{brow("This Order", fmt_money(order_amount, currency=cur))}'
            f'<tr style="background:rgba(239,68,68,0.07);border-top:2px solid rgba(239,68,68,0.2);">'
            f'<td style="padding:10px 12px;font-weight:700;">Total Exposure</td>'
            f'<td style="padding:10px 12px;text-align:right;font-weight:800;font-size:15px;color:#ef4444;">'
            f'{fmt_money(effective_ar + order_amount, currency=cur)}'
            f'<span style="font-size:11px;opacity:0.45;font-weight:400;"> / limit {fmt_money(credit_limit, currency=cur)}</span>'
            f'</td></tr>'
            f'</tbody></table>'
        )

        html = (
            f'<div style="font-size:13px;line-height:1.5;">'
            f'{summary_row(left, right)}'
            f'{breakdown}'
            f'{next_step}'
            f'</div>'
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
