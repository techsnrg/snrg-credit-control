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
    limit_breach  = bool(credit_limit and (effective_ar + order_amount) > credit_limit)

    # ── shared styles ────────────────────────────────────────────────────────
    S = {
        "card":   "border-radius:8px;padding:10px 14px;margin-bottom:10px;",
        "label":  "font-size:11px;text-transform:uppercase;letter-spacing:0.5px;opacity:0.55;margin-bottom:3px;",
        "value":  "font-weight:600;font-size:14px;",
        "th":     "padding:8px 10px;font-weight:600;opacity:0.65;font-size:12px;text-transform:uppercase;letter-spacing:0.4px;background:transparent;",
        "td":     "padding:9px 10px;background:transparent;vertical-align:middle;",
        "divider":"border:none;border-top:1px solid rgba(128,128,128,0.15);margin:12px 0;",
        "next":   "margin-top:14px;padding:10px 14px;border-left:3px solid #3b82f6;"
                  "border-radius:0 6px 6px 0;background:rgba(59,130,246,0.08);font-size:13px;",
    }

    def summary_card(bg_css, label, value, value_css=""):
        return (
            f'<div style="{S["card"]}{bg_css}">'
            f'  <div style="{S["label"]}">{label}</div>'
            f'  <div style="{S["value"]}{value_css}">{value}</div>'
            f'</div>'
        )

    if count > 0:
        # ── OVERDUE INVOICES layout ──────────────────────────────────────────
        rows_html = ""
        for i, r in enumerate(rows[:15]):
            age  = (today_date - getdate(r.posting_date)).days
            bg   = "background:rgba(128,128,128,0.04);" if i % 2 == 0 else "background:transparent;"
            age_color = "color:#ef4444;font-weight:700;" if age > 90 else "color:#f97316;font-weight:600;"
            rows_html += (
                f'<tr>'
                f'<td style="{S["td"]}{bg}">'
                f'  <a href="#Form/Sales%20Invoice/{r.name}" target="_blank"'
                f'     style="color:#3b82f6;text-decoration:none;font-weight:600;">'
                f'    {_esc(r.name)}</a>'
                f'</td>'
                f'<td style="{S["td"]}{bg}text-align:center;{age_color}">{age}d</td>'
                f'<td style="{S["td"]}{bg}text-align:right;font-weight:600;">'
                f'  {fmt_money(r.outstanding_amount, currency=cur)}'
                f'</td>'
                f'</tr>'
            )
        if count > 15:
            rows_html += (
                f'<tr><td colspan="3" style="{S["td"]}text-align:center;opacity:0.5;">'
                f'… and {count - 15} more invoice(s)</td></tr>'
            )

        html = f"""
<div style="font-size:13px;line-height:1.5;">
  <!-- Summary cards -->
  <div style="display:flex;gap:10px;margin-bottom:4px;">
    {summary_card("background:rgba(128,128,128,0.07);", "Customer",
                  f'{_esc(doc.customer_name)}<br><span style="font-size:12px;opacity:0.6;">'
                  f'{_esc(doc.customer)}</span>')}
    {summary_card("background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);",
                  "Overdue Invoices",
                  f'{count} invoice{"s" if count != 1 else ""} &nbsp;·&nbsp; '
                  f'{fmt_money(total_overdue, currency=cur)}',
                  "color:#ef4444;")}
  </div>

  <!-- Threshold note -->
  <div style="font-size:12px;opacity:0.5;margin-bottom:8px;">
    Threshold: {threshold} days &nbsp;·&nbsp; Cutoff date: {formatdate(cutoff)}
  </div>

  <!-- Invoice table -->
  <table style="width:100%;border-collapse:collapse;border-radius:6px;overflow:hidden;">
    <thead>
      <tr style="border-bottom:2px solid rgba(128,128,128,0.2);">
        <th style="{S["th"]}text-align:left;">Invoice</th>
        <th style="{S["th"]}text-align:center;">Age</th>
        <th style="{S["th"]}text-align:right;">Outstanding</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
    <tfoot>
      <tr style="border-top:2px solid rgba(128,128,128,0.2);">
        <td style="{S["td"]}font-weight:700;">Total</td>
        <td></td>
        <td style="{S["td"]}text-align:right;font-weight:700;color:#ef4444;">
          {fmt_money(total_overdue, currency=cur)}
        </td>
      </tr>
    </tfoot>
  </table>

  <!-- Next step -->
  <div style="{S["next"]}">
    <b>Next step:</b> Use <b>Credit Control → Request Approval</b> on this Sales Order
    to notify the Credit Approver team. The order can be submitted once approved.
  </div>
</div>"""

    else:
        # ── CREDIT LIMIT BREACH layout ───────────────────────────────────────
        breach = (effective_ar + order_amount) - credit_limit
        html = f"""
<div style="font-size:13px;line-height:1.5;">
  <!-- Summary cards -->
  <div style="display:flex;gap:10px;margin-bottom:4px;">
    {summary_card("background:rgba(128,128,128,0.07);", "Customer",
                  f'{_esc(doc.customer_name)}<br><span style="font-size:12px;opacity:0.6;">'
                  f'{_esc(doc.customer)}</span>')}
    {summary_card("background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);",
                  "Breach Amount", fmt_money(breach, currency=cur), "color:#ef4444;")}
  </div>

  <!-- Breakdown table -->
  <table style="width:100%;border-collapse:collapse;margin-top:4px;">
    <tbody>
      <tr style="border-bottom:1px solid rgba(128,128,128,0.12);">
        <td style="{S["td"]}opacity:0.65;">Credit Limit</td>
        <td style="{S["td"]}text-align:right;font-weight:600;">{fmt_money(credit_limit, currency=cur)}</td>
      </tr>
      <tr style="border-bottom:1px solid rgba(128,128,128,0.12);">
        <td style="{S["td"]}opacity:0.65;">Current AR (net of advances)</td>
        <td style="{S["td"]}text-align:right;font-weight:600;">{fmt_money(effective_ar, currency=cur)}</td>
      </tr>
      <tr style="border-bottom:1px solid rgba(128,128,128,0.12);">
        <td style="{S["td"]}opacity:0.65;">Advance Balance</td>
        <td style="{S["td"]}text-align:right;font-weight:600;">{fmt_money(advances, currency=cur)}</td>
      </tr>
      <tr style="border-bottom:2px solid rgba(128,128,128,0.2);">
        <td style="{S["td"]}opacity:0.65;">This Order</td>
        <td style="{S["td"]}text-align:right;font-weight:600;">{fmt_money(order_amount, currency=cur)}</td>
      </tr>
      <tr>
        <td style="{S["td"]}font-weight:700;">Total Exposure</td>
        <td style="{S["td"]}text-align:right;font-weight:700;color:#ef4444;">
          {fmt_money(effective_ar + order_amount, currency=cur)}
          &nbsp;<span style="font-size:11px;opacity:0.7;">(limit: {fmt_money(credit_limit, currency=cur)})</span>
        </td>
      </tr>
    </tbody>
  </table>

  <!-- Next step -->
  <div style="{S["next"]}">
    <b>Next step:</b> Use <b>Credit Control → Request Approval</b> on this Sales Order
    to notify the Credit Approver team. The order can be submitted once approved.
  </div>
</div>"""

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
