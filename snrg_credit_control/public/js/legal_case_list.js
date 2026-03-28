function snrgLegalCaseStatusBadge(value) {
  const config = {
    "Marked to Legal": ["#dc2626", "rgba(220, 38, 38, 0.12)", "rgba(220, 38, 38, 0.22)"],
    "Documents Pending": ["#b54708", "rgba(245, 158, 11, 0.14)", "rgba(245, 158, 11, 0.22)"],
    "Under Review": ["#7c3aed", "rgba(124, 58, 237, 0.12)", "rgba(124, 58, 237, 0.22)"],
    "Notice Preparation": ["#c2410c", "rgba(234, 88, 12, 0.14)", "rgba(234, 88, 12, 0.22)"],
    "Notice Sent": ["#155eef", "rgba(21, 94, 239, 0.12)", "rgba(21, 94, 239, 0.22)"],
    "Follow-up in Progress": ["#0369a1", "rgba(2, 132, 199, 0.12)", "rgba(2, 132, 199, 0.22)"],
    "Settlement Discussion": ["#9f1239", "rgba(190, 24, 93, 0.12)", "rgba(190, 24, 93, 0.22)"],
    "Partially Recovered": ["#027a48", "rgba(34, 197, 94, 0.12)", "rgba(34, 197, 94, 0.22)"],
    "Fully Recovered": ["#15803d", "rgba(22, 163, 74, 0.12)", "rgba(22, 163, 74, 0.22)"],
    "Complaint / Case Filing": ["#831843", "rgba(190, 24, 93, 0.12)", "rgba(190, 24, 93, 0.22)"],
    "In Proceedings": ["#4338ca", "rgba(67, 56, 202, 0.12)", "rgba(67, 56, 202, 0.22)"],
    "Closed": ["#475467", "rgba(71, 84, 103, 0.12)", "rgba(71, 84, 103, 0.22)"],
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

frappe.listview_settings["Legal Case"] = {
  add_fields: ["status"],
  formatters: {
    status(value) {
      return snrgLegalCaseStatusBadge(value);
    },
  },
};
