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
        surface: "rgba(16, 185, 129, 0.10)",
        border: "rgba(52, 211, 153, 0.22)",
        title: "Credit OK",
        badge: "Healthy",
        subtitle: "Customer is within overdue and credit-limit thresholds after the latest save.",
      },
      "Credit Hold": {
        rgb: "239,68,68",
        surface: "rgba(239, 68, 68, 0.10)",
        border: "rgba(248, 113, 113, 0.24)",
        title: "Credit Hold",
        badge: reason || "Review",
        subtitle: reason === "Over-Limit"
          ? "Live exposure plus this quotation is above the customer's credit limit."
          : "Customer has overdue invoices beyond the configured threshold.",
      },
    };

    const theme = themes[status];
    if (!theme) return;

    const pill = `<span style="display:inline-flex;align-items:center;gap:6px;background:rgba(${theme.rgb},.14);border:1px solid rgba(${theme.rgb},.32);color:rgba(${theme.rgb},1);font-size:10px;font-weight:800;letter-spacing:1.1px;text-transform:uppercase;padding:5px 12px;border-radius:999px;white-space:nowrap;">${frappe.utils.escape_html(theme.badge)}</span>`;
    const stat = (label, value, width, valueStyle = "") =>
      `<div style="display:inline-block;vertical-align:top;width:${width};padding-right:16px;padding-bottom:14px;box-sizing:border-box;min-width:180px;">
        <div style="font-size:10px;font-weight:700;letter-spacing:1.1px;text-transform:uppercase;opacity:.48;margin-bottom:6px;">${label}</div>
        <div style="font-size:18px;font-weight:800;letter-spacing:-0.2px;${valueStyle}">${value}</div>
      </div>`;
    const progressPct = creditLimit > 0
      ? Math.max(0, Math.min(100, Math.round((exposure / creditLimit) * 100)))
      : 0;
    const availabilityTone = projectedAvailable < 0
      ? "color:#fca5a5;"
      : (availableCredit <= 0 ? "color:#fdba74;" : `color:rgba(${theme.rgb},1);`);
    const summaryLabel = creditLimit > 0 ? `${progressPct}% of credit limit currently utilized` : "No credit limit configured";

    frm.dashboard.set_headline(`
      <div style="border:1px solid ${theme.border};border-left:5px solid rgba(${theme.rgb},1);border-radius:12px;padding:18px 22px;background:linear-gradient(135deg, ${theme.surface} 0%, rgba(15, 23, 42, 0.04) 100%);box-shadow:0 12px 24px rgba(15,23,42,.08);line-height:1.4;overflow:hidden;">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px;flex-wrap:wrap;">
          <div>
            <div style="font-size:20px;font-weight:800;letter-spacing:-0.3px;margin-bottom:3px;">${theme.title}</div>
            <div style="font-size:12px;opacity:.74;max-width:780px;">${theme.subtitle}</div>
          </div>
          ${pill}
        </div>
        <div style="height:8px;border-radius:999px;background:rgba(148,163,184,.16);overflow:hidden;margin-bottom:8px;">
          <div style="width:${progressPct}%;height:100%;background:linear-gradient(90deg, rgba(${theme.rgb},.78) 0%, rgba(${theme.rgb},1) 100%);border-radius:999px;"></div>
        </div>
        <div style="font-size:11px;font-weight:600;letter-spacing:.2px;opacity:.58;margin-bottom:16px;">${summaryLabel}</div>
        <div style="margin-bottom:2px;">
          ${stat("Available Credit", fmtSigned(availableCredit), "28%", availabilityTone)}
          ${stat("Projected After Quote", fmtSigned(projectedAvailable), "28%", projectedAvailable < 0 ? "color:#fca5a5;" : "")}
          ${stat("Current Exposure", fmt(exposure), "22%")}
          ${stat("Credit Limit", fmt(creditLimit), "22%")}
        </div>
        <div style="border-top:1px solid rgba(148,163,184,.18);padding-top:14px;">
          ${stat("Overdue Invoices", overdueCount, "22%", overdueCount ? "color:#f59e0b;" : "")}
          ${stat("Overdue Amount", fmt(overdueAmount), "26%", overdueAmount ? "color:#f59e0b;" : "")}
          ${stat("Quotation Value", fmt(quotationValue), "26%")}
          ${stat("Reason", reason || "Within policy", "26%", reason ? "color:#fca5a5;font-size:15px;" : "font-size:15px;")}
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
