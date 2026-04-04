import frappe
from frappe.utils import add_days, flt, fmt_money, formatdate, getdate, now_datetime, today


DEFAULT_THRESHOLD_DAYS = 75


def zero(value):
    return flt(value)


def escape_html(value):
    try:
        return frappe.utils.escape_html(value or "")
    except Exception:
        string_value = str(value or "")
        return string_value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def get_threshold(customer):
    days = frappe.db.get_value("Customer", customer, "custom_credit_lock_days")
    try:
        return int(days) if days else DEFAULT_THRESHOLD_DAYS
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLD_DAYS


def get_overdue_invoices(customer, company, cutoff):
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


def get_credit_limit(customer, company):
    return frappe.db.get_value(
        "Customer Credit Limit",
        {"parent": customer, "company": company},
        "credit_limit",
    ) or 0


def get_total_outstanding(customer, company):
    value = frappe.db.sql(
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
    return value or 0


def get_advance_balance(customer, company):
    value = frappe.db.sql(
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
    return value or 0


def build_credit_snapshot(customer, company, amount=0, currency=None, detail_limit=15, more_prefix="..."):
    today_date = getdate(today())
    threshold = get_threshold(customer)
    cutoff = add_days(today_date, -threshold)
    resolved_currency = (
        currency
        or frappe.db.get_value("Company", company, "default_currency")
        or "INR"
    )

    rows = get_overdue_invoices(customer, company, cutoff)
    overdue_count = len(rows)
    total_overdue = sum(row.outstanding_amount for row in rows) if rows else 0
    credit_limit = get_credit_limit(customer, company)
    total_outstanding = get_total_outstanding(customer, company)
    # Preserve signed exposure so customer advances / net credit balances
    # reduce the projected exposure instead of being discarded as zero.
    effective_ar = total_outstanding
    current_amount = zero(amount)
    limit_breach = bool(credit_limit and (effective_ar + current_amount) > credit_limit)
    advances = get_advance_balance(customer, company)

    detail_lines = []
    for row in rows[:detail_limit]:
        age = (today_date - getdate(row.posting_date)).days
        detail_lines.append(
            f"{row.name} ({fmt_money(row.outstanding_amount, currency=resolved_currency)}, {age}d)"
        )
    if overdue_count > detail_limit:
        detail_lines.append(f"{more_prefix} +{overdue_count - detail_limit} more")

    reasons = []
    if overdue_count > 0:
        reasons.append("Overdue>Terms")
    if limit_breach:
        reasons.append("Over-Limit")

    if reasons:
        status = "Credit Hold"
        reason_code = " + ".join(reasons)
    else:
        status = "Credit OK"
        reason_code = ""

    return {
        "today_date": today_date,
        "checked_on": now_datetime(),
        "threshold": threshold,
        "cutoff": cutoff,
        "currency": resolved_currency,
        "rows": rows,
        "overdue_count": overdue_count,
        "total_overdue": total_overdue,
        "credit_limit": credit_limit,
        "total_outstanding": total_outstanding,
        "effective_ar": effective_ar,
        "amount": current_amount,
        "limit_breach": limit_breach,
        "needs_review": overdue_count > 0 or limit_breach,
        "advances": advances,
        "detail_lines": detail_lines,
        "details": "; ".join(detail_lines),
        "status": status,
        "reason_code": reason_code,
    }


def stamp_credit_fields(doc, snapshot):
    doc.custom_snrg_overdue_count_terms = snapshot["overdue_count"]
    doc.custom_snrg_overdue_amount_terms = snapshot["total_overdue"]
    doc.custom_snrg_exposure_at_check = snapshot["effective_ar"]
    doc.custom_snrg_credit_limit_at_check = snapshot["credit_limit"]
    doc.custom_snrg_credit_check_details = snapshot["details"]
    doc.custom_snrg_credit_checked_on = snapshot.get("checked_on")
    doc.custom_snrg_credit_check_status = snapshot["status"]
    doc.custom_snrg_credit_check_reason_code = snapshot["reason_code"]


def reset_credit_fields(doc):
    doc.custom_snrg_credit_check_status = "Not Run"
    doc.custom_snrg_credit_check_reason_code = ""
    doc.custom_snrg_overdue_count_terms = 0
    doc.custom_snrg_overdue_amount_terms = 0
    doc.custom_snrg_exposure_at_check = 0
    doc.custom_snrg_credit_limit_at_check = 0
    doc.custom_snrg_credit_check_details = ""
    doc.custom_snrg_credit_checked_on = None


def render_credit_details_html(snapshot, customer, customer_name, next_step_html=None):
    cur = snapshot["currency"]
    today_date = snapshot["today_date"]
    threshold = snapshot["threshold"]
    cutoff = snapshot["cutoff"]
    amount = snapshot["amount"]
    rows = snapshot["rows"]
    count = snapshot["overdue_count"]
    total_overdue = snapshot["total_overdue"]
    credit_limit = snapshot["credit_limit"]
    effective_ar = snapshot["effective_ar"]
    advances = snapshot["advances"]
    limit_breach = snapshot["limit_breach"]

    padding = "padding:8px 6px;"
    border_bottom = "border-bottom:1px solid #e0e0e0;"
    th_style = f"{padding}font-size:11px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.6px;{border_bottom}"
    hr = "<hr style='border:none;border-top:1px solid #e0e0e0;margin:14px 0;'>"

    next_step = next_step_html or ""

    breach = (effective_ar + amount) - credit_limit
    available_balance = (credit_limit - (effective_ar + amount)) if credit_limit else 0

    def breakdown_row(label, value, val_color=None, bold_val=False):
        value_color = f"color:{val_color};" if val_color else ""
        value_weight = "font-weight:800;font-size:15px;" if bold_val else "font-weight:600;"
        return (
            f"<tr>"
            f"<td style='{padding}{border_bottom}color:#666;'>{label}</td>"
            f"<td style='{padding}{border_bottom}text-align:right;{value_weight}{value_color}'>{value}</td>"
            f"</tr>"
        )

    invoice_rows = ""
    if count > 0:
        for row in rows[:15]:
            age = (today_date - getdate(row.posting_date)).days
            age_color = "#c0392b" if age > 90 else ("#e67e22" if age > 75 else "#555")
            invoice_rows += (
                f"<tr>"
                f"<td style='{padding}{border_bottom}'>"
                f"<a href='#Form/Sales%20Invoice/{row.name}' style='color:#2980b9;font-weight:600;text-decoration:none;'>"
                f"{escape_html(row.name)}</a></td>"
                f"<td style='{padding}{border_bottom}text-align:center;font-weight:700;color:{age_color};'>{age}d</td>"
                f"<td style='{padding}{border_bottom}text-align:right;font-weight:600;'>{fmt_money(row.outstanding_amount, currency=cur)}</td>"
                f"</tr>"
            )
        if count > 15:
            invoice_rows += (
                f"<tr><td colspan='3' style='{padding}text-align:center;color:#aaa;font-size:12px;'>"
                f"&#8230; and {count - 15} more invoice(s)</td></tr>"
            )

    overdue_summary = ""
    if count > 0:
        overdue_summary = (
            f"<div style='margin-bottom:{'10px' if limit_breach else '0'};'>"
            f"<p style='margin:0 0 2px;font-size:11px;color:#c0392b;font-weight:700;letter-spacing:.6px;text-transform:uppercase;'>&#9888;&#65039; Total Overdue</p>"
            f"<p style='margin:0 0 2px;font-size:22px;font-weight:800;color:#c0392b;'>{fmt_money(total_overdue, currency=cur)}</p>"
            f"<p style='margin:0;font-size:12px;color:#e67e22;'>{count} invoice{'s' if count != 1 else ''} &nbsp;&#183;&nbsp; older than {threshold} days</p>"
            f"</div>"
        )

    breach_summary = ""
    if limit_breach:
        breach_summary = (
            f"<div>"
            f"<p style='margin:0 0 2px;font-size:11px;color:#c0392b;font-weight:700;letter-spacing:.6px;text-transform:uppercase;'>&#128683; Breach Amount</p>"
            f"<p style='margin:0 0 2px;font-size:22px;font-weight:800;color:#c0392b;'>{fmt_money(breach, currency=cur)}</p>"
            f"<p style='margin:0;font-size:12px;color:#e67e22;'>Exceeds assigned credit limit</p>"
            f"</div>"
        )
    elif count == 0:
        breach_summary = (
            f"<div>"
            f"<p style='margin:0 0 2px;font-size:11px;color:#16a34a;font-weight:700;letter-spacing:.6px;text-transform:uppercase;'>&#9989; Available Balance</p>"
            f"<p style='margin:0 0 2px;font-size:22px;font-weight:800;color:#16a34a;'>{fmt_money(available_balance, currency=cur)}</p>"
            f"<p style='margin:0;font-size:12px;color:#16a34a;'>Within assigned credit limit</p>"
            f"</div>"
        )

    overdue_section = ""
    if count > 0:
        overdue_section = (
            f"{hr}"
            f"<p style='margin:0 0 8px;font-size:12px;color:#888;'>&#128203; <strong>Overdue Invoices</strong>"
            f"&nbsp;&nbsp;&#183;&nbsp;&nbsp;Cutoff date: <strong>{formatdate(cutoff)}</strong>"
            f"&nbsp;&nbsp;&#183;&nbsp;&nbsp;Threshold: <strong>{threshold} days</strong></p>"
            f"<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse;'>"
            f"<thead><tr>"
            f"<th style='{th_style}text-align:left;'>Invoice</th>"
            f"<th style='{th_style}text-align:center;'>Age</th>"
            f"<th style='{th_style}text-align:right;'>Outstanding</th>"
            f"</tr></thead>"
            f"<tbody>{invoice_rows}</tbody>"
            f"<tfoot><tr>"
            f"<td colspan='2' style='{padding}font-weight:700;font-size:13px;border-top:2px solid #ccc;'>&#128197; Total Overdue</td>"
            f"<td style='{padding}text-align:right;font-weight:800;font-size:16px;color:#c0392b;border-top:2px solid #ccc;'>{fmt_money(total_overdue, currency=cur)}</td>"
            f"</tr></tfoot>"
            f"</table>"
        )

    breach_section = ""
    if limit_breach or count == 0:
        total_exposure_color = "#c0392b" if limit_breach else "#16a34a"
        total_exposure_note = (
            f"vs limit {fmt_money(credit_limit, currency=cur)}"
            if limit_breach
            else f"available {fmt_money(available_balance, currency=cur)}"
        )
        breach_section = (
            f"{hr}"
            f"<p style='margin:0 0 8px;font-size:12px;color:#888;'>&#128200; <strong>Credit Limit Breakdown</strong></p>"
            f"<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse;'><tbody>"
            f"{breakdown_row('&#127974; Credit Limit', fmt_money(credit_limit, currency=cur))}"
            f"{breakdown_row('&#128196; Current AR Outstanding', fmt_money(effective_ar, currency=cur))}"
            f"{breakdown_row('&#128179; Advance Balance (credit)', fmt_money(advances, currency=cur))}"
            f"{breakdown_row('&#128666; This Document', fmt_money(amount, currency=cur))}"
            f"<tr>"
            f"<td style='{padding}font-weight:700;font-size:13px;border-top:2px solid #ccc;'>&#9889; Total Exposure</td>"
            f"<td style='{padding}text-align:right;font-weight:800;font-size:15px;color:{total_exposure_color};border-top:2px solid #ccc;'>"
            f"{fmt_money(effective_ar + amount, currency=cur)}"
            f"<br><span style='font-size:11px;color:#888;font-weight:400;'>{total_exposure_note}</span>"
            f"</td>"
            f"</tr>"
            f"</tbody></table>"
        )

    return (
        f"<table width='100%' cellpadding='0' cellspacing='0'>"
        f"<tr>"
        f"<td width='48%' style='padding:4px 12px 4px 0;vertical-align:top;'>"
        f"<p style='margin:0 0 2px;font-size:11px;color:#888;font-weight:700;letter-spacing:.6px;text-transform:uppercase;'>&#128100; Customer</p>"
        f"<p style='margin:0 0 2px;font-size:15px;font-weight:700;'>{escape_html(customer_name)}</p>"
        f"<p style='margin:0;font-size:12px;color:#999;'>{escape_html(customer)}</p>"
        f"</td>"
        f"<td width='4%'></td>"
        f"<td width='48%' style='padding:4px 0;vertical-align:top;'>"
        f"{overdue_summary}"
        f"{breach_summary}"
        f"</td>"
        f"</tr>"
        f"</table>"
        f"{overdue_section}"
        f"{breach_section}"
        f"{hr if next_step else ''}"
        f"{next_step}"
    )
