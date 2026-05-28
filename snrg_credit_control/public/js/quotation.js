function snrg_show_minimum_rate_check() {
  if (!frappe.dom || !frappe.dom.freeze) return;
  frappe.dom.freeze("Checking minimum selling rates...");
  clearTimeout(window.snrg_minimum_rate_check_timeout);
  window.snrg_minimum_rate_check_timeout = setTimeout(snrg_hide_minimum_rate_check, 15000);
}

function snrg_hide_minimum_rate_check() {
  clearTimeout(window.snrg_minimum_rate_check_timeout);
  if (frappe.dom && frappe.dom.unfreeze) {
    frappe.dom.unfreeze();
  }
}

function get_quotation_credit_view_model(frm) {
  const status = frm.doc.custom_snrg_credit_check_status;
  return {
    status: status || "Not Run",
    reason: frm.doc.custom_snrg_credit_check_reason_code || "",
    overdueCount: Number(frm.doc.custom_snrg_overdue_count_terms || 0),
    overdueAmount: Number(frm.doc.custom_snrg_overdue_amount_terms || 0),
    exposure: Number(frm.doc.custom_snrg_exposure_at_check || 0),
    creditLimit: Number(frm.doc.custom_snrg_credit_limit_at_check || 0),
    quotationValue: Number(frm.doc.grand_total || frm.doc.rounded_total || 0),
    currency: frm.doc.currency || "INR",
    checkedOn: frm.doc.custom_snrg_credit_checked_on || "",
    details: frm.doc.custom_snrg_credit_check_details || "",
  };
}

function parse_credit_detail_preview(details) {
  if (!details) return [];
  return String(details)
    .split(";")
    .map(part => part.trim())
    .filter(Boolean)
    .slice(0, 2);
}

function get_quotation_credit_reason_ui(reason, overdueCount) {
  const hasOverdue = (reason || "").includes("Overdue>Terms");
  const hasLimit = (reason || "").includes("Over-Limit");

  if (hasOverdue && hasLimit) {
    return {
      badge: "Overdue + Over Limit",
      summary: "Multiple credit issues",
      detail: "Customer has overdue invoices beyond the allowed payment terms, and this quotation also exceeds the available credit limit.",
    };
  }

  if (hasOverdue) {
    const detail = overdueCount
      ? `${overdueCount} invoice${overdueCount === 1 ? " is" : "s are"} overdue beyond the allowed payment terms.`
      : "Customer has overdue invoices beyond the allowed payment terms.";
    return {
      badge: "Overdue Invoice",
      summary: "Overdue invoices beyond allowed terms",
      detail,
    };
  }

  if (hasLimit) {
    return {
      badge: "Over Credit Limit",
      summary: "Quotation exceeds available credit limit",
      detail: "Current exposure plus this quotation exceeds the customer's available credit limit.",
    };
  }

  return {
    badge: "",
    summary: "Within policy",
    detail: "Customer is within the configured credit policy.",
  };
}

function render_quotation_credit_chip(frm) {
  try {
    if (!frm || !frm.dashboard || !frm.dashboard.set_headline) return;
    if (frm.dashboard.clear_headline) frm.dashboard.clear_headline();

    const model = get_quotation_credit_view_model(frm);
    const { status, reason, overdueCount, overdueAmount, exposure, creditLimit, quotationValue, currency, checkedOn, details } = model;
    const reasonUi = get_quotation_credit_reason_ui(reason, overdueCount);
    const fmt = value => frappe.format(value, { fieldtype: "Currency", options: currency });
    const fmtSigned = value => {
      const formatted = fmt(Math.abs(value)).replace(/^-+/, "");
      return value < 0 ? `-\u00a0${formatted}` : formatted;
    };
    const formatCheckedOn = value => value ? frappe.datetime.str_to_user(value) : "Not refreshed yet";
    const metricCard = (label, value, valueStyle = "") => `
      <div style="min-width:0;padding:12px 14px;border-radius:8px;background:rgba(255,255,255,.7);border:1px solid rgba(148,163,184,.14);">
        <div style="font-size:10px;font-weight:700;opacity:.52;letter-spacing:.04em;text-transform:uppercase;margin-bottom:6px;">${label}</div>
        <div style="font-size:16px;font-weight:700;line-height:1.2;word-break:break-word;${valueStyle}">${value}</div>
      </div>
    `;
    const metricOp = symbol => `
      <div style="display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;opacity:.42;min-width:22px;">${symbol}</div>
    `;
    const infoCard = (label, value) => `
      <div style="min-width:0;padding:10px 12px;border-radius:8px;background:rgba(15,23,42,.04);border:1px solid rgba(148,163,184,.12);">
        <div style="font-size:10px;font-weight:700;opacity:.52;letter-spacing:.04em;text-transform:uppercase;margin-bottom:5px;">${label}</div>
        <div style="font-size:14px;font-weight:600;line-height:1.2;word-break:break-word;">${value}</div>
      </div>
    `;
    const overduePreview = parse_credit_detail_preview(details);
    const overduePreviewHtml = overduePreview.length
      ? overduePreview.map(line => `<div style="font-size:13px;font-weight:600;line-height:1.35;">${frappe.utils.escape_html(line)}</div>`).join("")
      : `<div style="font-size:13px;opacity:.72;">No overdue invoice lines</div>`;
    const availableCredit = creditLimit ? (creditLimit - exposure) : 0;
    const projectedAvailable = creditLimit ? (creditLimit - exposure - quotationValue) : 0;
    const availableTone = availableCredit < 0
      ? "color:#ef4444;"
      : (availableCredit === 0 ? "color:#f59e0b;" : "color:#22c55e;");
    const projectedTone = projectedAvailable < 0 ? "color:#ef4444;" : "color:#22c55e;";

    const themes = {
      "Not Run": {
        rgb: "100,116,139",
        title: "Credit Status",
        badge: "Not Run",
      },
      "Credit OK": {
        rgb: "34,197,94",
        title: "Credit Status",
        badge: "Healthy",
      },
      "Credit Hold": {
        rgb: "239,68,68",
        title: "Credit Hold",
        badge: reasonUi.badge || "Needs Review",
      },
    };

    const theme = themes[status];
    if (!theme) return;

    const pill = `<span style="display:inline-flex;align-items:center;background:rgba(${theme.rgb},.10);border:1px solid rgba(${theme.rgb},.22);color:rgba(${theme.rgb},1);font-size:10px;font-weight:700;padding:4px 10px;border-radius:999px;white-space:nowrap;">${frappe.utils.escape_html(theme.badge)}</span>`;

    frm.dashboard.set_headline(`
      <div style="background:var(--control-bg, #f8f9fa);border:1px solid var(--border-color, #d1d8dd);border-radius:10px;padding:12px 14px;line-height:1.35;color:var(--text-color, #36414c);box-shadow:none;">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;flex-wrap:wrap;">
          <div style="min-width:0;">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
              <div style="font-size:16px;font-weight:700;">${theme.title}</div>
              <div style="font-size:11px;opacity:.68;">Last Refresh: ${formatCheckedOn(checkedOn)}</div>
            </div>
          </div>
          ${pill}
        </div>
        <div style="margin-top:10px;overflow-x:auto;">
          <div style="display:grid;grid-template-columns:minmax(150px,1fr) 26px minmax(150px,1fr) 26px minmax(150px,1fr) 26px minmax(150px,1fr) 26px minmax(150px,1fr);gap:10px;align-items:stretch;min-width:900px;">
          ${metricCard("Credit Limit", fmt(creditLimit))}
          ${metricOp("-")}
          ${metricCard("Current Exposure", fmtSigned(exposure))}
          ${metricOp("=")}
          ${metricCard("Available Credit", fmtSigned(availableCredit), availableTone)}
          ${metricOp("-")}
          ${metricCard("Quotation Value", fmt(quotationValue))}
          ${metricOp("=")}
          ${metricCard("Projected Balance", fmtSigned(projectedAvailable), projectedTone)}
          </div>
        </div>
        <div style="margin-top:10px;display:grid;grid-template-columns:minmax(120px,.75fr) minmax(150px,.9fr) minmax(260px,1.35fr) minmax(260px,1.4fr);gap:10px 12px;align-items:stretch;">
          ${infoCard("Overdue Invoices", String(overdueCount))}
          ${infoCard("Overdue Amount", fmt(overdueAmount))}
          ${infoCard("Top Overdue Invoices", overduePreviewHtml)}
          ${infoCard("Reason", frappe.utils.escape_html(reasonUi.detail))}
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
        label: `Credit Hold · ${get_quotation_credit_reason_ui(reason, model.overdueCount).badge || "Needs Review"}`,
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
  custom_snrg_credit_checked_on(frm) {
    render_quotation_credit_chip(frm);
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
    snrg_show_minimum_rate_check();
    frm._snrg_credit_preview = null;
  },
  after_save() {
    snrg_hide_minimum_rate_check();
  },
  before_submit() {
    snrg_show_minimum_rate_check();
  },
  on_submit() {
    snrg_hide_minimum_rate_check();
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
        quotation_name: frm.doc.name,
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
    frm.doc.custom_snrg_credit_check_details = message.details || "";
    frm.doc.custom_snrg_credit_checked_on = message.checked_on || "";
    frm.doc.custom_credit_clearance_date = message.credit_clearance_date || frm.doc.custom_credit_clearance_date || "";

    render_quotation_credit_chip(frm);
    render_quotation_header_status(frm);
    frm.refresh_fields([
      "custom_snrg_credit_check_status",
      "custom_snrg_credit_check_reason_code",
      "custom_snrg_overdue_count_terms",
      "custom_snrg_overdue_amount_terms",
      "custom_snrg_exposure_at_check",
      "custom_snrg_credit_limit_at_check",
      "custom_snrg_credit_check_details",
      "custom_snrg_credit_checked_on",
      "custom_credit_clearance_date",
    ]);

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
