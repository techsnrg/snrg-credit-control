function snrgLegalActivityBadge(value) {
  const config = {
    "Marked to Legal": ["#dc2626", "rgba(220, 38, 38, 0.12)", "rgba(220, 38, 38, 0.22)"],
    "Cheque Bounce Intake": ["#b54708", "rgba(245, 158, 11, 0.14)", "rgba(245, 158, 11, 0.22)"],
    "Demand Notice Created": ["#155eef", "rgba(21, 94, 239, 0.12)", "rgba(21, 94, 239, 0.22)"],
    "Demand Notice Submitted": ["#1d4ed8", "rgba(29, 78, 216, 0.12)", "rgba(29, 78, 216, 0.22)"],
    "Demand Notice Cancelled": ["#9f1239", "rgba(190, 24, 93, 0.12)", "rgba(190, 24, 93, 0.22)"],
    "Recovery Updated": ["#15803d", "rgba(22, 163, 74, 0.12)", "rgba(22, 163, 74, 0.22)"],
    "Status Updated": ["#7c3aed", "rgba(124, 58, 237, 0.12)", "rgba(124, 58, 237, 0.22)"],
    "Case Closed": ["#475467", "rgba(71, 84, 103, 0.12)", "rgba(71, 84, 103, 0.22)"],
  }[value];

  if (!config) {
    return frappe.utils.escape_html(value || "");
  }

  const [color, bg, border] = config;
  return `
    <span style="display:inline-flex;align-items:center;padding:2px 8px;border-radius:999px;border:1px solid ${border};background:${bg};color:${color};font-size:11px;font-weight:700;white-space:nowrap;">
      ${frappe.utils.escape_html(value)}
    </span>
  `;
}

frappe.listview_settings["Legal Case Activity"] = {
  add_fields: ["activity_type"],
  formatters: {
    activity_type(value) {
      return snrgLegalActivityBadge(value);
    },
  },
};
