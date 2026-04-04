function get_quotation_credit_view_model(frm) {
  const preview = frm._snrg_credit_preview;

  if (preview && (frm.is_new() || frm.is_dirty())) {
    return {
      stage: "preview",
      status: preview.status,
      reason: preview.reason_code || "",
      overdueCount: Number(preview.overdue_count || 0),
      overdueAmount: Number(preview.total_overdue || 0),
      exposure: Number(preview.effective_ar || 0),
      creditLimit: Number(preview.credit_limit || 0),
      quotationValue: 0,
      currency: preview.currency || frm.doc.currency || "INR",
    };
  }

  const status = frm.doc.custom_snrg_credit_check_status;
  if (!status || status === "Not Run") {
    return null;
  }

  return {
    stage: "saved",
    status,
    reason: frm.doc.custom_snrg_credit_check_reason_code || "",
    overdueCount: Number(frm.doc.custom_snrg_overdue_count_terms || 0),
    overdueAmount: Number(frm.doc.custom_snrg_overdue_amount_terms || 0),
    exposure: Number(frm.doc.custom_snrg_exposure_at_check || 0),
    creditLimit: Number(frm.doc.custom_snrg_credit_limit_at_check || 0),
    quotationValue: Number(frm.doc.grand_total || frm.doc.rounded_total || 0),
    currency: frm.doc.currency || "INR",
  };
}

function render_quotation_credit_chip(frm) {
  try {
    if (!frm || !frm.dashboard || !frm.dashboard.set_headline) return;
    if (frm.dashboard.clear_headline) frm.dashboard.clear_headline();

    const model = get_quotation_credit_view_model(frm);
    if (!model) return;

    const { stage, status, reason, overdueCount, overdueAmount, exposure, creditLimit, quotationValue, currency } = model;
    const hasOverdueTerms = reason.includes("Overdue>Terms");
    const hasOverLimit = reason.includes("Over-Limit");
    const availableCredit = creditLimit ? (creditLimit - exposure) : 0;
    const projectedAvailable = creditLimit ? (creditLimit - exposure - quotationValue) : 0;
    const fmt = value => frappe.format(value, { fieldtype: "Currency", options: currency });
    const fmtSigned = value => {
      const formatted = fmt(Math.abs(value)).replace(/^-+/, "");
      return value < 0 ? `-\u00a0${formatted}` : formatted;
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
        subtitle: hasOverdueTerms && hasOverLimit
          ? "Customer has overdue invoices beyond the configured threshold and the current exposure plus this quotation crosses the assigned credit limit."
          : hasOverLimit && stage !== "preview"
          ? "Current exposure plus this quotation crosses the customer's credit limit."
          : hasOverLimit
          ? "Current exposure is already beyond the customer's credit limit."
          : "Customer has overdue invoices beyond the configured threshold.",
      },
    };

    const theme = themes[status];
    if (!theme) return;

    const pill = `<span style="display:inline-flex;align-items:center;background:rgba(${theme.rgb},.10);border:1px solid rgba(${theme.rgb},.22);color:rgba(${theme.rgb},1);font-size:10px;font-weight:700;padding:3px 9px;border-radius:999px;white-space:nowrap;">${frappe.utils.escape_html(theme.badge)}</span>`;
    const metric = (label, value, sign = "", valueStyle = "", accent = "") =>
      `<div style="position:relative;min-width:0;padding-right:${accent ? "14px" : "0"};">
        <div style="font-size:10px;font-weight:700;opacity:.52;margin-bottom:3px;letter-spacing:.03em;text-transform:uppercase;">${label}</div>
        <div style="font-size:16px;font-weight:700;letter-spacing:-0.2px;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;${valueStyle}">${sign}${value}</div>
        ${accent ? `<div style="position:absolute;right:0;top:18px;font-size:13px;font-weight:800;opacity:.26;">${accent}</div>` : ""}
      </div>`;
    const availabilityTone = projectedAvailable < 0
      ? "color:#fca5a5;"
      : (availableCredit <= 0 ? "color:#fdba74;" : `color:rgba(${theme.rgb},1);`);
    const projectedTone = projectedAvailable < 0
      ? "color:#f87171;text-shadow:0 0 0 rgba(0,0,0,0.01);"
      : (status === "Credit OK" ? "color:#22c55e;font-weight:800;text-shadow:0 0 0 rgba(0,0,0,0.01);" : "color:#f8fafc;font-weight:800;");
    const basePanel = "background:var(--control-bg, #f8f9fa);border:1px solid var(--border-color, #d1d8dd);";
    const calculationRow = stage === "preview"
      ? `
          <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));gap:10px 14px;align-items:flex-start;">
            ${metric("Credit Limit", fmt(creditLimit), "", "", "−")}
            ${metric("Current Exposure", fmt(exposure), "", "", "=")}
            ${metric("Available Credit", fmtSigned(availableCredit), "", availabilityTone)}
          </div>
        `
      : `
          <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));gap:10px 14px;align-items:flex-start;">
            ${metric("Credit Limit", fmt(creditLimit), "", "", "−")}
            ${metric("Current Exposure", fmt(exposure), "", "", "=")}
            ${metric("Available Credit", fmtSigned(availableCredit), "", availabilityTone, "−")}
            ${metric("Quotation Value", fmt(quotationValue), "", "", "=")}
            ${metric("Projected Balance", fmtSigned(projectedAvailable), "", projectedTone)}
          </div>
        `;

    frm.dashboard.set_headline(`
      <div style="${basePanel}border-radius:10px;padding:12px 14px;line-height:1.35;color:var(--text-color, #36414c);box-shadow:none;">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;flex-wrap:wrap;">
          <div style="min-width:0;">
            <div style="font-size:16px;font-weight:700;margin-bottom:1px;">${theme.title}</div>
            <div style="font-size:11px;opacity:.7;max-width:780px;">${theme.subtitle}</div>
          </div>
          ${pill}
        </div>
        <div style="margin-top:10px;padding:10px 12px;border-radius:8px;background:rgba(255,255,255,.55);border:1px solid rgba(140,140,140,.10);">
          ${calculationRow}
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:10px;font-size:11px;opacity:.85;">
          <span style="display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:rgba(15,23,42,.05);"><strong>Overdue:</strong>&nbsp;${overdueCount}</span>
          <span style="display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:rgba(15,23,42,.05);"><strong>Amount:</strong>&nbsp;${fmt(overdueAmount)}</span>
          <span style="display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:rgba(15,23,42,.05);"><strong>Status:</strong>&nbsp;${frappe.utils.escape_html(reason || "Within policy")}</span>
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

    const model = get_quotation_credit_view_model(frm);
    frm.page.wrapper.find(".snrg-credit-header-pill").remove();

    if (!model || !model.status || model.status === "Not Run") return;

    const status = model.status;
    const reason = model.reason || "";
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
  setup(frm) {
    frm._snrg_credit_preview = null;
  },
  refresh(frm) {
    render_quotation_credit_chip(frm);
    render_quotation_header_status(frm);
    add_quotation_credit_button(frm);
  },
  party_name(frm) {
    clear_quotation_credit_preview(frm);
  },
  company(frm) {
    clear_quotation_credit_preview(frm);
  },
  quotation_to(frm) {
    clear_quotation_credit_preview(frm);
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
  before_save(frm) {
    frm._snrg_credit_preview = null;
  },
});

function clear_quotation_credit_preview(frm) {
  frm._snrg_credit_preview = null;
  render_quotation_credit_chip(frm);
  render_quotation_header_status(frm);
}

function add_quotation_credit_button(frm) {
  if (!frm.doc.party_name || !frm.doc.company || frm.doc.quotation_to !== "Customer") {
    return;
  }

  frm.add_custom_button("Refresh Credit Status", () => refresh_quotation_credit_status(frm), "Credit Control");
  frm.add_custom_button("Current Credit Details", () => open_quotation_credit_details(frm), "Credit Control");
}

async function open_quotation_credit_details(frm) {
  if (!frm.doc.party_name || !frm.doc.company) {
    frappe.msgprint({
      title: "Missing Customer",
      message: "Select a customer and company first to view credit details.",
      indicator: "orange",
    });
    return;
  }

  try {
    const { message } = await frappe.call({
      method: "snrg_credit_control.overrides.quotation.get_credit_details",
      args: {
        customer: frm.doc.party_name,
        customer_name: frm.doc.customer_name || frm.doc.party_name,
        company: frm.doc.company,
        currency: frm.doc.currency,
        amount: frm.doc.grand_total || frm.doc.rounded_total || 0,
      },
    });

    if (!message || !message.html) {
      return;
    }

    frappe.msgprint({
      title: message.title || "Customer Credit Details",
      message: message.html,
      wide: true,
    });
  } catch (e) {
    console.warn("[SNRG Quotation Credit Details] dialog error:", e);
    frappe.msgprint({
      title: "Unable to load credit details",
      message: (e && e.message) || String(e),
      indicator: "red",
    });
  }
}

async function refresh_quotation_credit_status(frm) {
  if (!frm.doc.party_name || !frm.doc.company) {
    frappe.msgprint({
      title: "Missing Customer",
      message: "Select a customer and company first to refresh credit status.",
      indicator: "orange",
    });
    return;
  }

  try {
    const { message } = await frappe.call({
      method: "snrg_credit_control.overrides.quotation.refresh_credit_status",
      args: {
        customer: frm.doc.party_name,
        company: frm.doc.company,
        currency: frm.doc.currency,
        amount: frm.doc.grand_total || frm.doc.rounded_total || 0,
      },
    });

    if (!message) return;

    frm._snrg_credit_preview = null;
    frm.doc.custom_snrg_credit_check_status = message.status || "Not Run";
    frm.doc.custom_snrg_credit_check_reason_code = message.reason_code || "";
    frm.doc.custom_snrg_overdue_count_terms = message.overdue_count || 0;
    frm.doc.custom_snrg_overdue_amount_terms = message.total_overdue || 0;
    frm.doc.custom_snrg_exposure_at_check = message.effective_ar || 0;
    frm.doc.custom_snrg_credit_limit_at_check = message.credit_limit || 0;

    render_quotation_credit_chip(frm);
    render_quotation_header_status(frm);

    frappe.show_alert({
      message: "Credit status refreshed",
      indicator: message.status === "Credit Hold" ? "orange" : "green",
    });
  } catch (e) {
    console.warn("[SNRG Quotation Credit Refresh] error:", e);
    frappe.msgprint({
      title: "Unable to refresh credit status",
      message: (e && e.message) || String(e),
      indicator: "red",
    });
  }
}
