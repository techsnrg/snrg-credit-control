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
    const currency = frm.doc.currency || "INR";
    const fmt = value => frappe.format(value, { fieldtype: "Currency", options: currency });

    const themes = {
      "Credit OK": {
        rgb: "34,197,94",
        title: "Credit OK",
        badge: "Healthy",
        subtitle: "Customer is within overdue and credit-limit thresholds.",
      },
      "Credit Hold": {
        rgb: "239,68,68",
        title: "Credit Hold",
        badge: reason || "Review",
        subtitle: reason === "Over-Limit"
          ? "Exposure plus this quotation is above the credit limit."
          : "Customer has overdue invoices beyond the configured threshold.",
      },
    };

    const theme = themes[status];
    if (!theme) return;

    const pill = `<span style="background:rgba(${theme.rgb},.16);border:1px solid rgba(${theme.rgb},.38);color:rgba(${theme.rgb},1);font-size:10px;font-weight:800;letter-spacing:1px;text-transform:uppercase;padding:3px 10px;border-radius:999px;white-space:nowrap;">${frappe.utils.escape_html(theme.badge)}</span>`;
    const stat = (label, value, width) =>
      `<div style="display:inline-block;vertical-align:top;width:${width};padding-right:12px;box-sizing:border-box;">
        <div style="font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;opacity:.45;margin-bottom:4px;">${label}</div>
        <div style="font-size:15px;font-weight:700;">${value}</div>
      </div>`;

    frm.dashboard.set_headline(`
      <div style="border:1px solid rgba(${theme.rgb},.22);border-left:4px solid rgba(${theme.rgb},1);border-radius:0 8px 8px 0;padding:16px 20px;background:rgba(${theme.rgb},.06);box-shadow:0 2px 12px rgba(0,0,0,.08);line-height:1.4;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
          <span style="font-size:13px;font-weight:700;">${theme.title}</span>
          ${pill}
        </div>
        <div style="font-size:12px;opacity:.72;margin-bottom:12px;">${theme.subtitle}</div>
        <div>
          ${stat("Overdue Invoices", overdueCount, "25%")}
          ${stat("Overdue Amount", fmt(overdueAmount), "25%")}
          ${stat("Exposure", fmt(exposure), "25%")}
          ${stat("Credit Limit", fmt(creditLimit), "25%")}
        </div>
      </div>
    `);

    const box = frm.dashboard.wrapper.find(".dashboard-headline");
    box.css({ background: "transparent", padding: "0", "box-shadow": "none", border: "none" });
  } catch (e) {
    console.warn("[SNRG Quotation Credit Chip] render error:", e);
  }
}

frappe.ui.form.on("Quotation", {
  refresh(frm) {
    render_quotation_credit_chip(frm);
  },
  custom_snrg_credit_check_status(frm) {
    render_quotation_credit_chip(frm);
  },
  custom_snrg_credit_check_reason_code(frm) {
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
});
