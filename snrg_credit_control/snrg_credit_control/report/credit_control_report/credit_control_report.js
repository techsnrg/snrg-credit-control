// Credit Control Report — filters + formatting

frappe.query_reports["Credit Control Report"] = {
  filters: [
    {
      fieldname: "company",
      label: __("Company"),
      fieldtype: "Link",
      options: "Company",
      default: frappe.defaults.get_user_default("Company"),
      reqd: 1,
    },
    {
      fieldname: "status",
      label: __("Status"),
      fieldtype: "Select",
      options: [
        "All",
        "Credit Hold",
        "Pending Approval",
        "Approved",
        "Expired",
      ].join("\n"),
      default: "All",
    },
    {
      fieldname: "customer",
      label: __("Customer"),
      fieldtype: "Link",
      options: "Customer",
      get_query: () => ({ filters: { disabled: 0 } }),
    },
    {
      fieldname: "from_date",
      label: __("SO Date From"),
      fieldtype: "Date",
      default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
    },
    {
      fieldname: "to_date",
      label: __("SO Date To"),
      fieldtype: "Date",
      default: frappe.datetime.get_today(),
    },
  ],

  onload(report) {
    // Wire Select filters to auto-refresh
    setTimeout(() => {
      const f = report.get_filter("status");
      if (f && f.$input) {
        f.$input.off("change.ccr").on("change.ccr", () => report.refresh());
      }
    }, 400);
  },

  formatter(value, row, column, data, default_formatter) {
    value = default_formatter(value, row, column, data);

    if (column.fieldname === "custom_snrg_credit_check_status" && data) {
      const s = (data.custom_snrg_credit_check_status || "").toLowerCase();
      if (s === "credit hold") {
        value = `<span style="color:#c0392b;font-weight:600;">🔴 ${data.custom_snrg_credit_check_status}</span>`;
      } else if (s === "pending approval") {
        value = `<span style="color:#e67e22;font-weight:600;">🟠 ${data.custom_snrg_credit_check_status}</span>`;
      } else if (s === "approved") {
        value = `<span style="color:#27ae60;font-weight:600;">🟢 ${data.custom_snrg_credit_check_status}</span>`;
      } else if (s === "expired") {
        value = `<span style="color:#f39c12;font-weight:600;">🟡 ${data.custom_snrg_credit_check_status}</span>`;
      } else if (s === "credit ok") {
        value = `<span style="color:#27ae60;">✅ ${data.custom_snrg_credit_check_status}</span>`;
      }
    }

    // Highlight overdue amounts in red
    if (column.fieldname === "custom_snrg_overdue_amount_terms" && data) {
      if ((data.custom_snrg_overdue_amount_terms || 0) > 0) {
        value = `<span style="color:#c0392b;font-weight:600;">${value}</span>`;
      }
    }

    // Highlight expired valid-till
    if (column.fieldname === "custom_snrg_override_valid_till" && data) {
      const vt = data.custom_snrg_override_valid_till;
      if (vt && frappe.datetime.get_diff(vt, frappe.datetime.get_today()) < 0) {
        value = `<span style="color:#e74c3c;text-decoration:line-through;">${value}</span>`;
      }
    }

    // Bold PTP commitment date if it has passed and status is still Pending
    if (column.fieldname === "ptp_commitment_date" && data) {
      const cd = data.ptp_commitment_date;
      if (cd && frappe.datetime.get_diff(cd, frappe.datetime.get_today()) < 0) {
        value = `<span style="color:#e74c3c;font-weight:600;" title="PTP date has passed">${value} ⚠️</span>`;
      }
    }

    return value;
  },
};
