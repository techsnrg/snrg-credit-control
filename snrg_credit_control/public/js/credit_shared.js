(function () {
  if (window.snrgCreditUi) return;

  function formatCurrency(value, currency) {
    return frappe.format(value, { fieldtype: "Currency", options: currency || "INR" });
  }

  function formatSignedCurrency(value, currency) {
    const formatted = formatCurrency(Math.abs(value || 0), currency).replace(/^-+/, "");
    return value < 0 ? `-${formatted}` : formatted;
  }

  function formatCheckedOn(value) {
    if (!value) return "Not refreshed yet";
    return frappe.datetime.str_to_user(value);
  }

  function buildCreditCardHtml(model, options = {}) {
    const currency = model.currency || "INR";
    const title = options.title || "Credit Status";
    const reason = model.reason || "";
    const status = model.status || "Not Run";
    const hasOverdueTerms = reason.includes("Overdue>Terms");
    const hasOverLimit = reason.includes("Over-Limit");
    const creditLimit = Number(model.creditLimit || 0);
    const exposure = Number(model.exposure || 0);
    const documentValue = Number(model.documentValue || 0);
    const availableCredit = creditLimit ? (creditLimit - exposure) : 0;
    const projectedBalance = creditLimit ? (creditLimit - exposure - documentValue) : 0;
    const fmt = (value) => formatCurrency(value, currency);
    const fmtSigned = (value) => formatSignedCurrency(value, currency);

    if (status === "Not Run") {
      return `
        <div style="background:var(--control-bg, #f8f9fa);border:1px solid var(--border-color, #d1d8dd);border-radius:10px;padding:12px 14px;line-height:1.35;color:var(--text-color, #36414c);box-shadow:none;">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;flex-wrap:wrap;">
            <div style="min-width:0;">
              <div style="font-size:16px;font-weight:700;margin-bottom:1px;">${title}</div>
              <div style="font-size:11px;opacity:.7;max-width:780px;">Credit status has not been refreshed yet. Save the document or use Credit Control &gt; Refresh Credit Status.</div>
            </div>
            <span style="display:inline-flex;align-items:center;background:rgba(100,116,139,.10);border:1px solid rgba(100,116,139,.18);color:#475569;font-size:10px;font-weight:700;padding:3px 9px;border-radius:999px;white-space:nowrap;">Not Run</span>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:10px;font-size:11px;opacity:.85;">
            <span style="display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:rgba(15,23,42,.05);"><strong>Last Refresh:</strong>&nbsp;${formatCheckedOn(model.checkedOn)}</span>
          </div>
        </div>
      `;
    }

    const themes = {
      "Credit OK": {
        rgb: "34,197,94",
        title,
        badge: "Healthy",
        subtitle: "Customer is currently within the configured credit policy.",
      },
      "Credit Hold": {
        rgb: "239,68,68",
        title,
        badge: reason || "Review",
        subtitle: hasOverdueTerms && hasOverLimit
          ? `Customer has overdue invoices beyond the configured threshold and the current exposure plus this ${options.documentLabel || "document"} crosses the assigned credit limit.`
          : hasOverLimit
          ? `Current exposure plus this ${options.documentLabel || "document"} crosses the customer's credit limit.`
          : "Customer has overdue invoices beyond the configured threshold.",
      },
    };

    const theme = themes[status];
    if (!theme) return "";

    const pill = `<span style="display:inline-flex;align-items:center;background:rgba(${theme.rgb},.10);border:1px solid rgba(${theme.rgb},.22);color:rgba(${theme.rgb},1);font-size:10px;font-weight:700;padding:3px 9px;border-radius:999px;white-space:nowrap;">${frappe.utils.escape_html(theme.badge)}</span>`;
    const metricLabel = (label) =>
      `<div style="min-width:0;width:100%;font-size:10px;font-weight:700;opacity:.52;letter-spacing:.03em;text-transform:uppercase;text-align:left;justify-self:start;">${label}</div>`;
    const metricValue = (value, valueStyle = "") =>
      `<div style="min-width:0;width:100%;font-size:16px;font-weight:700;letter-spacing:-0.2px;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:left;justify-self:start;${valueStyle}">${value}</div>`;
    const separator = (symbol) =>
      `<div style="display:flex;align-items:center;justify-content:center;font-size:24px;line-height:1;font-weight:700;color:rgba(100,116,139,.42);grid-row:1 / span 2;align-self:center;">${symbol}</div>`;

    const availableTone = projectedBalance < 0
      ? "color:#fca5a5;"
      : (availableCredit <= 0 ? "color:#fdba74;" : `color:rgba(${theme.rgb},1);`);
    const projectedTone = projectedBalance < 0
      ? "color:#f87171;font-weight:800;"
      : (status === "Credit OK" ? "color:#22c55e;font-weight:800;" : "color:#f8fafc;font-weight:800;");

    const extraPills = [];
    extraPills.push(`<span style="display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:rgba(15,23,42,.05);"><strong>Overdue:</strong>&nbsp;${Number(model.overdueCount || 0)}</span>`);
    extraPills.push(`<span style="display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:rgba(15,23,42,.05);"><strong>Amount:</strong>&nbsp;${fmt(Number(model.overdueAmount || 0))}</span>`);
    extraPills.push(`<span style="display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:rgba(15,23,42,.05);"><strong>Status:</strong>&nbsp;${frappe.utils.escape_html(reason || "Within policy")}</span>`);
    extraPills.push(`<span style="display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:rgba(15,23,42,.05);"><strong>Last Refresh:</strong>&nbsp;${formatCheckedOn(model.checkedOn)}</span>`);

    if (Array.isArray(model.metaParts)) {
      model.metaParts.forEach((part) => {
        if (part) extraPills.push(`<span style="display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:rgba(15,23,42,.05);">${part}</span>`);
      });
    }

    return `
      <div style="background:var(--control-bg, #f8f9fa);border:1px solid var(--border-color, #d1d8dd);border-radius:10px;padding:12px 14px;line-height:1.35;color:var(--text-color, #36414c);box-shadow:none;">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;flex-wrap:wrap;">
          <div style="min-width:0;">
            <div style="font-size:16px;font-weight:700;margin-bottom:1px;">${theme.title}</div>
            <div style="font-size:11px;opacity:.7;max-width:780px;">${theme.subtitle}</div>
          </div>
          ${pill}
        </div>
        <div style="margin-top:10px;padding:10px 12px;border-radius:8px;background:rgba(255,255,255,.55);border:1px solid rgba(140,140,140,.10);">
          <div style="display:grid;grid-template-columns:minmax(140px, 1fr) 22px minmax(140px, 1fr) 22px minmax(140px, 1fr) 22px minmax(140px, 1fr) 22px minmax(140px, 1fr);grid-template-rows:auto auto;column-gap:12px;row-gap:8px;align-items:start;justify-items:start;">
            ${metricLabel("Credit Limit")}
            ${separator("−")}
            ${metricLabel("Current Exposure")}
            ${separator("=")}
            ${metricLabel("Available Credit")}
            ${separator("−")}
            ${metricLabel(options.documentValueLabel || "Document Value")}
            ${separator("=")}
            ${metricLabel("Projected Balance")}
            ${metricValue(fmt(creditLimit))}
            ${metricValue(fmt(exposure))}
            ${metricValue(fmtSigned(availableCredit), availableTone)}
            ${metricValue(fmt(documentValue))}
            ${metricValue(fmtSigned(projectedBalance), projectedTone)}
          </div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:10px;font-size:11px;opacity:.85;">
          ${extraPills.join("")}
        </div>
      </div>
    `;
  }

  function renderHeadline(frm, html) {
    if (!frm || !frm.dashboard || !frm.dashboard.set_headline) return;
    if (frm.dashboard.clear_headline) frm.dashboard.clear_headline();
    frm.dashboard.set_headline(html);
    const box = frm.dashboard.wrapper.find(".dashboard-headline");
    box.css({ background: "transparent", padding: "0", "box-shadow": "none", border: "none" });
  }

  function renderHeaderPill(frm, selectorClass, model) {
    try {
      if (!frm || !frm.page || !frm.page.wrapper) return;
      frm.page.wrapper.find(`.${selectorClass}`).remove();
      if (!model || !model.status || model.status === "Not Run") return;

      const config = {
        "Credit OK": { bg: "rgba(34,197,94,.14)", border: "rgba(34,197,94,.28)", color: "#22c55e", label: "Credit OK" },
        "Credit Hold": { bg: "rgba(239,68,68,.14)", border: "rgba(239,68,68,.28)", color: "#f87171", label: model.reason ? `Credit Hold · ${model.reason}` : "Credit Hold" },
      }[model.status];
      if (!config) return;

      const pill = $(`
        <span class="${selectorClass}" style="display:inline-flex;align-items:center;margin-left:8px;padding:4px 12px;border-radius:999px;border:1px solid ${config.border};background:${config.bg};color:${config.color};font-size:12px;font-weight:700;line-height:1.2;white-space:nowrap;">
          ${frappe.utils.escape_html(config.label)}
        </span>
      `);

      const primaryIndicator = frm.page.wrapper.find(".page-head .indicator-pill, .layout-main .indicator-pill").first();
      if (primaryIndicator.length) {
        pill.insertAfter(primaryIndicator);
        return;
      }

      const titleArea = frm.page.wrapper.find(".page-title, .title-area, .page-form-header").first();
      if (titleArea.length) titleArea.append(pill);
    } catch (e) {
      console.warn("[SNRG Credit Header Status] render error:", e);
    }
  }

  window.snrgCreditUi = {
    buildCreditCardHtml,
    renderHeadline,
    renderHeaderPill,
  };
})();
