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

    report.page.add_action_item(__("Update PTP"), () => open_ptp_update_dialog(report));
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

    if (column.fieldname === "ptp_status" && data) {
      const s = (data.ptp_status || "").toLowerCase();
      if (s === "cleared") {
        value = `<span style="color:#27ae60;font-weight:600;">${value}</span>`;
      } else if (s === "partially cleared") {
        value = `<span style="color:#f39c12;font-weight:600;">${value}</span>`;
      } else if (s === "broken") {
        value = `<span style="color:#c0392b;font-weight:600;">${value}</span>`;
      } else if (s === "pending") {
        value = `<span style="color:#e67e22;font-weight:600;">${value}</span>`;
      }
    }

    // Highlight overdue amounts in red
    if (column.fieldname === "custom_snrg_overdue_amount_terms" && data) {
      if ((data.custom_snrg_overdue_amount_terms || 0) > 0) {
        value = `<span style="color:#c0392b;font-weight:600;">${value}</span>`;
      }
    }

    if (column.fieldname === "ptp_difference_amount" && data) {
      const difference = Number(data.ptp_difference_amount || 0);
      if (difference > 0) {
        value = `<span style="color:#c0392b;font-weight:600;">${value}</span>`;
      } else if (difference <= 0 && Number(data.ptp_received_amount || 0) > 0) {
        value = `<span style="color:#27ae60;font-weight:600;">${value}</span>`;
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

function open_ptp_update_dialog(report) {
  const row = get_selected_report_row(report);
  if (!row || !row.name) {
    frappe.msgprint({
      title: __("Select a Row"),
      message: __("Select a Sales Order row in the report first."),
      indicator: "orange",
    });
    return;
  }

  frappe.call({
    method: "snrg_credit_control.overrides.sales_order.get_ptp_references",
    args: { sales_order: row.name },
    callback: ({ message }) => {
      const refs = message || [];
      if (!refs.length) {
        frappe.msgprint({
          title: __("No PTP Found"),
          message: __("This Sales Order does not have any PTP entries."),
          indicator: "orange",
        });
        return;
      }

      const refMap = {};
      const refOptions = refs.map(ref => {
        const label = `${ref.label} | Remaining ${frappe.format(ref.difference_amount || 0, { fieldtype: "Currency", options: row.currency || "INR" })} | ${ref.status}`;
        refMap[label] = ref;
        return label;
      });

      const d = new frappe.ui.Dialog({
        title: __("Update PTP for {0}", [row.name]),
        fields: [
          {
            fieldtype: "HTML",
            options: `
              <div style="background:var(--control-bg);border:1px solid var(--border-color);border-radius:8px;padding:10px 12px;margin-bottom:8px;">
                <div><strong>Sales Order:</strong> ${frappe.utils.escape_html(row.name)}</div>
                <div><strong>Customer:</strong> ${frappe.utils.escape_html(row.customer_name || row.customer || "")}</div>
              </div>
            `,
          },
          {
            fieldtype: "Select",
            fieldname: "ptp_reference",
            label: __("PTP Reference"),
            reqd: 1,
            options: ["", ...refOptions].join("\n"),
          },
          {
            fieldtype: "Link",
            fieldname: "payment_entry",
            label: __("Payment Entry"),
            options: "Payment Entry",
            reqd: 1,
            get_query: () => ({
              filters: {
                docstatus: 1,
                party_type: "Customer",
                party: row.customer,
              },
            }),
          },
          {
            fieldtype: "Currency",
            fieldname: "allocated_amount",
            label: __("Allocated Amount"),
            reqd: 1,
          },
          {
            fieldtype: "Small Text",
            fieldname: "remarks",
            label: __("Remarks"),
          },
        ],
        primary_action_label: __("Save"),
        primary_action(values) {
          const ref = refMap[values.ptp_reference];
          if (!ref) {
            frappe.msgprint({
              title: __("Missing PTP"),
              message: __("Select a valid PTP reference."),
              indicator: "red",
            });
            return;
          }

          frappe.call({
            method: "snrg_credit_control.overrides.sales_order.link_payment_entry_from_report",
            args: {
              sales_order: row.name,
              ptp_entry_id: ref.ptp_entry_id,
              payment_entry: values.payment_entry,
              allocated_amount: values.allocated_amount,
              remarks: values.remarks,
            },
            freeze: true,
            freeze_message: __("Updating PTP..."),
            callback: () => {
              d.hide();
              frappe.show_alert({ message: __("PTP updated successfully."), indicator: "green" });
              report.refresh();
            },
            error: (err) => {
              frappe.msgprint({
                title: __("Failed to update PTP"),
                message: (err && err.message) || __("Unknown error"),
                indicator: "red",
              });
            },
          });
        },
      });

      d.show();
      d.get_field("ptp_reference").$input.on("change", () => {
        const ref = refMap[d.get_value("ptp_reference")];
        if (!ref) return;
        d.set_value("allocated_amount", Math.max(0, Number(ref.difference_amount || 0)));
      });
    },
  });
}

function get_selected_report_row(report) {
  const datatableRowmanager = report.datatable && report.datatable.rowmanager;
  if (!datatableRowmanager || !datatableRowmanager.getCheckedRows) {
    return null;
  }

  const checkedRows = datatableRowmanager.getCheckedRows() || [];
  if (!checkedRows.length) {
    return null;
  }

  const index = checkedRows[0];
  return (report.data || [])[index] || null;
}
