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
    const availableCredit = creditLimit ? (creditLimit - exposure) : 0;
    const projectedAvailable = creditLimit ? (creditLimit - exposure - quotationValue) : 0;
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
        subtitle: reason === "Over-Limit" && stage !== "preview"
          ? "Current exposure plus this quotation crosses the customer's credit limit."
          : reason === "Over-Limit"
          ? "Current exposure is already beyond the customer's credit limit."
          : "Customer has overdue invoices beyond the configured threshold.",
      },
    };

    const theme = themes[status];
    if (!theme) return;

    const pill = `<span style="display:inline-flex;align-items:center;background:rgba(${theme.rgb},.12);border:1px solid rgba(${theme.rgb},.24);color:rgba(${theme.rgb},1);font-size:11px;font-weight:700;padding:4px 10px;border-radius:999px;white-space:nowrap;">${frappe.utils.escape_html(theme.badge)}</span>`;
    const step = (label, value, sign = "", valueStyle = "", accent = "") =>
      `<div style="display:flex;align-items:center;gap:10px;min-width:220px;flex:1 1 220px;">
        <div style="min-width:0;">
          <div style="font-size:11px;font-weight:600;opacity:.62;margin-bottom:4px;">${label}</div>
          <div style="font-size:20px;font-weight:700;letter-spacing:-0.25px;${valueStyle}">${sign}${value}</div>
        </div>
        ${accent ? `<div style="font-size:18px;font-weight:700;opacity:.4;padding-top:16px;">${accent}</div>` : ""}
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
          <div style="display:flex;align-items:flex-start;gap:18px 16px;flex-wrap:wrap;">
            ${step("Credit Limit", fmt(creditLimit), "", "", "−")}
            ${step("Current Exposure", fmt(exposure), "", "", "=")}
            ${step("Available Credit", fmtSigned(availableCredit), "", availabilityTone)}
          </div>
        `
      : `
          <div style="display:flex;align-items:flex-start;gap:18px 16px;flex-wrap:wrap;">
            ${step("Credit Limit", fmt(creditLimit), "", "", "−")}
            ${step("Current Exposure", fmt(exposure), "", "", "=")}
            ${step("Available Credit", fmtSigned(availableCredit), "", availabilityTone, "−")}
            ${step("Quotation Value", fmt(quotationValue), "", "", "=")}
            ${step("Projected Balance", fmtSigned(projectedAvailable), "", projectedTone)}
          </div>
        `;

    frm.dashboard.set_headline(`
      <div style="${basePanel}border-radius:10px;padding:16px 18px;line-height:1.45;color:var(--text-color, #36414c);box-shadow:none;">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px;flex-wrap:wrap;">
          <div>
            <div style="font-size:18px;font-weight:700;margin-bottom:2px;">${theme.title}</div>
            <div style="font-size:12px;opacity:.72;">${theme.subtitle}</div>
          </div>
          ${pill}
        </div>
        <div style="margin-top:14px;border:1px solid rgba(140,140,140,.12);border-radius:8px;background:rgba(255,255,255,.35);padding:14px 14px 10px;">
          <div style="font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;opacity:.55;margin-bottom:10px;">Credit Calculation</div>
          ${calculationRow}
        </div>
        <div style="border-top:1px solid rgba(140,140,140,.14);margin-top:12px;padding-top:12px;font-size:12px;opacity:.8;">
          <span style="margin-right:18px;"><strong>Overdue Invoices:</strong> ${overdueCount}</span>
          <span style="margin-right:18px;"><strong>Overdue Amount:</strong> ${fmt(overdueAmount)}</span>
          <span><strong>Status:</strong> ${frappe.utils.escape_html(reason || "Within policy")}</span>
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
    fetch_quotation_credit_preview(frm);
  },
  company(frm) {
    fetch_quotation_credit_preview(frm);
  },
  quotation_to(frm) {
    fetch_quotation_credit_preview(frm);
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

async function fetch_quotation_credit_preview(frm) {
  frm._snrg_credit_preview = null;

  if (!frm.doc.party_name || !frm.doc.company || frm.doc.quotation_to !== "Customer") {
    render_quotation_credit_chip(frm);
    render_quotation_header_status(frm);
    return;
  }

  try {
    const { message } = await frappe.call({
      method: "snrg_credit_control.overrides.quotation.get_credit_preview",
      args: {
        customer: frm.doc.party_name,
        company: frm.doc.company,
        currency: frm.doc.currency,
      },
    });

    frm._snrg_credit_preview = message || null;
    render_quotation_credit_chip(frm);
    render_quotation_header_status(frm);
  } catch (e) {
    console.warn("[SNRG Quotation Credit Preview] fetch error:", e);
  }
}

function add_quotation_credit_button(frm) {
  if (!frm.doc.party_name || !frm.doc.company || frm.doc.quotation_to !== "Customer") {
    return;
  }

  frm.add_custom_button("Credit Details", () => open_quotation_credit_details(frm));
  frm.add_custom_button("Refresh Credit Status", () => refresh_quotation_credit_status(frm));
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
      freeze: true,
      freeze_message: __("Refreshing credit status..."),
    });

    const snapshot = message || {};
    frm._snrg_credit_preview = null;

    frm.doc.custom_snrg_credit_check_status = snapshot.status || "Not Run";
    frm.doc.custom_snrg_credit_check_reason_code = snapshot.reason_code || "";
    frm.doc.custom_snrg_overdue_count_terms = snapshot.overdue_count || 0;
    frm.doc.custom_snrg_overdue_amount_terms = snapshot.total_overdue || 0;
    frm.doc.custom_snrg_exposure_at_check = snapshot.effective_ar || 0;
    frm.doc.custom_snrg_credit_limit_at_check = snapshot.credit_limit || 0;

    [
      "custom_snrg_credit_check_status",
      "custom_snrg_credit_check_reason_code",
      "custom_snrg_overdue_count_terms",
      "custom_snrg_overdue_amount_terms",
      "custom_snrg_exposure_at_check",
      "custom_snrg_credit_limit_at_check",
    ].forEach(fieldname => frm.refresh_field(fieldname));

    render_quotation_credit_chip(frm);
    render_quotation_header_status(frm);

    frappe.show_alert({
      message: __("Credit status refreshed"),
      indicator: "green",
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
