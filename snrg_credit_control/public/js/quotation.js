function render_quotation_credit_chip(frm) {
  try {
    if (!frm || !frm.dashboard || !frm.dashboard.set_headline) return;
    if (frm.is_new() || !frm.doc.name) return;
    if (frm.dashboard.clear_headline) frm.dashboard.clear_headline();

    const status = frm.doc.custom_snrg_credit_check_status;
    if (!status || status === "Not Run") return;

    const reason = frm.doc.custom_snrg_credit_check_reason_code || "";
    const overdueCount = Number(frm.doc.custom_snrg_overdue_count_terms || 0);
    const overdueAmount = Number(frm.doc.custom_snrg_overdue_amount_terms || 0);
    const exposure = Number(frm.doc.custom_snrg_exposure_at_check || 0);
    const creditLimit = Number(frm.doc.custom_snrg_credit_limit_at_check || 0);
    const quotationValue = Number(frm.doc.grand_total || frm.doc.rounded_total || 0);
    const availableCredit = creditLimit ? (creditLimit - exposure) : 0;
    const projectedAvailable = creditLimit ? (creditLimit - exposure - quotationValue) : 0;
    const currency = frm.doc.currency || "INR";
    const fmt = value => frappe.format(value, { fieldtype: "Currency", options: currency });
    const fmtSigned = value => {
      const formatted = fmt(Math.abs(value));
      return value < 0 ? `-${formatted}` : formatted;
    };

    const themes = {
      "Credit OK": {
        rgb: "34,197,94",
        bg: "rgba(34,197,94,.08)",
        border: "rgba(34,197,94,.18)",
        title: "Credit OK",
        badge: "Healthy",
        subtitle: "Customer is currently within the configured credit policy.",
      },
      "Credit Hold": {
        rgb: "239,68,68",
        bg: "rgba(239,68,68,.08)",
        border: "rgba(239,68,68,.18)",
        title: "Credit Hold",
        badge: reason || "Review",
        subtitle: reason === "Over-Limit"
          ? "Current exposure plus this quotation crosses the customer's credit limit."
          : "Customer has overdue invoices beyond the configured threshold.",
      },
    };

    const theme = themes[status];
    if (!theme) return;

    const pill = `<span style="display:inline-flex;align-items:center;background:rgba(${theme.rgb},.12);border:1px solid rgba(${theme.rgb},.24);color:rgba(${theme.rgb},1);font-size:11px;font-weight:700;padding:4px 10px;border-radius:999px;white-space:nowrap;">${frappe.utils.escape_html(theme.badge)}</span>`;
    const stat = (label, value, width, valueStyle = "") =>
      `<div style="display:inline-block;vertical-align:top;width:${width};min-width:160px;padding-right:18px;padding-bottom:12px;box-sizing:border-box;">
        <div style="font-size:11px;font-weight:600;opacity:.65;margin-bottom:4px;">${label}</div>
        <div style="font-size:19px;font-weight:700;letter-spacing:-0.2px;${valueStyle}">${value}</div>
      </div>`;
    const availabilityTone = projectedAvailable < 0
      ? "color:#fca5a5;"
      : (availableCredit <= 0 ? "color:#fdba74;" : `color:rgba(${theme.rgb},1);`);

    frm.dashboard.set_headline(`
      <div style="border:1px solid ${theme.border};border-radius:10px;padding:14px 16px;background:${theme.bg};line-height:1.45;">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px;flex-wrap:wrap;">
          <div>
            <div style="font-size:18px;font-weight:700;margin-bottom:2px;">${theme.title}</div>
            <div style="font-size:12px;opacity:.72;">${theme.subtitle}</div>
          </div>
          ${pill}
        </div>
        <div style="margin-top:12px;">
          ${stat("Available Credit", fmtSigned(availableCredit), "24%", availabilityTone)}
          ${stat("Current Exposure", fmt(exposure), "19%")}
          ${stat("Credit Limit", fmt(creditLimit), "19%")}
          ${stat("Quotation Value", fmt(quotationValue), "19%")}
          ${stat("Projected Balance", fmtSigned(projectedAvailable), "19%", projectedAvailable < 0 ? "color:#fca5a5;" : "")}
        </div>
        <div style="border-top:1px solid rgba(140,140,140,.14);margin-top:4px;padding-top:12px;font-size:12px;opacity:.8;">
          <span style="margin-right:18px;"><strong>Overdue Invoices:</strong> ${overdueCount}</span>
          <span style="margin-right:18px;"><strong>Overdue Amount:</strong> ${fmt(overdueAmount)}</span>
          <span><strong>Reason:</strong> ${frappe.utils.escape_html(reason || "Within policy")}</span>
        </div>
      </div>
    `);

    const box = frm.dashboard.wrapper.find(".dashboard-headline");
    box.css({ background: "transparent", padding: "0", "box-shadow": "none", border: "none" });
  } catch (e) {
    console.warn("[SNRG Quotation Credit Chip] render error:", e);
  }
}

function render_quotation_header_status(frm) {
  try {
    if (!frm || !frm.page || !frm.page.wrapper) return;

    const status = frm.doc.custom_snrg_credit_check_status;
    frm.page.wrapper.find(".snrg-credit-header-pill").remove();

    if (!status || status === "Not Run" || frm.is_new()) return;

    const reason = frm.doc.custom_snrg_credit_check_reason_code || "";
    const config = {
      "Credit OK": {
        bg: "rgba(34,197,94,.14)",
        border: "rgba(34,197,94,.28)",
        color: "#22c55e",
        label: "Credit OK",
      },
      "Credit Hold": {
        bg: "rgba(239,68,68,.14)",
        border: "rgba(239,68,68,.28)",
        color: "#f87171",
        label: reason ? `Credit Hold · ${reason}` : "Credit Hold",
      },
    }[status];

    if (!config) return;

    const pill = $(`
      <span class="snrg-credit-header-pill" style="display:inline-flex;align-items:center;margin-left:8px;padding:4px 12px;border-radius:999px;border:1px solid ${config.border};background:${config.bg};color:${config.color};font-size:12px;font-weight:700;line-height:1.2;white-space:nowrap;">
        ${frappe.utils.escape_html(config.label)}
      </span>
    `);

    const primaryIndicator = frm.page.wrapper.find(".page-head .indicator-pill, .layout-main .indicator-pill").first();
    if (primaryIndicator.length) {
      pill.insertAfter(primaryIndicator);
      return;
    }

    const titleArea = frm.page.wrapper.find(".page-title, .title-area, .page-form-header").first();
    if (titleArea.length) {
      titleArea.append(pill);
    }
  } catch (e) {
    console.warn("[SNRG Quotation Header Status] render error:", e);
  }
}

frappe.ui.form.on("Quotation", {
  refresh(frm) {
    render_quotation_credit_chip(frm);
    render_quotation_header_status(frm);
  },
  custom_snrg_credit_check_status(frm) {
    render_quotation_credit_chip(frm);
    render_quotation_header_status(frm);
  },
  custom_snrg_credit_check_reason_code(frm) {
    render_quotation_credit_chip(frm);
    render_quotation_header_status(frm);
  },
  custom_snrg_overdue_count_terms(frm) {
    render_quotation_credit_chip(frm);
  },
  custom_snrg_overdue_amount_terms(frm) {
    render_quotation_credit_chip(frm);
  },
  custom_snrg_exposure_at_check(frm) {
    render_quotation_credit_chip(frm);
  },
  custom_snrg_credit_limit_at_check(frm) {
    render_quotation_credit_chip(frm);
  },
});
