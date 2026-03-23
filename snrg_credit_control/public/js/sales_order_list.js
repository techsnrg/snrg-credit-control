function snrgSalesOrderCreditBadge(value) {
  if (!value || value === "Not Run") {
    return value || "";
  }

  const config = {
    "Credit OK": {
      color: "#1f7a3d",
      bg: "rgba(34, 197, 94, 0.12)",
      border: "rgba(34, 197, 94, 0.22)",
    },
    "Credit Hold": {
      color: "#b42318",
      bg: "rgba(239, 68, 68, 0.12)",
      border: "rgba(239, 68, 68, 0.22)",
    },
  }[value];

  if (!config) {
    return frappe.utils.escape_html(value);
  }

  return `
    <span style="display:inline-flex;align-items:center;padding:2px 8px;border-radius:999px;border:1px solid ${config.border};background:${config.bg};color:${config.color};font-size:11px;font-weight:700;white-space:nowrap;">
      ${frappe.utils.escape_html(value)}
    </span>
  `;
}

frappe.listview_settings["Sales Order"] = {
  add_fields: ["custom_snrg_credit_check_status", "custom_snrg_credit_check_reason_code"],
  formatters: {
    custom_snrg_credit_check_status(value) {
      return snrgSalesOrderCreditBadge(value);
    },
  },
};
