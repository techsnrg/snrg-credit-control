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
      } else if (s === "superseded") {
        value = `<span style="color:#7f8c8d;font-weight:600;">${value}</span>`;
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
  const d = new frappe.ui.Dialog({
    title: __("Update PTP"),
    fields: [
      {
        fieldtype: "Link",
        fieldname: "sales_order",
        label: __("Sales Order"),
        options: "Sales Order",
        reqd: 1,
        default: row && row.name ? row.name : "",
        onchange() {
          load_ptp_references_for_sales_order(d, report, d.get_value("sales_order"));
        },
        get_query: () => ({
          filters: {
            docstatus: 0,
            company: report.get_filter_value("company") || undefined,
          },
        }),
      },
      {
        fieldtype: "HTML",
        fieldname: "sales_order_context",
      },
      {
        fieldtype: "Select",
        fieldname: "ptp_reference",
        label: __("PTP Reference"),
        reqd: 1,
        options: "",
      },
      {
        fieldtype: "Link",
        fieldname: "payment_entry",
        label: __("Payment Entry"),
        options: "Payment Entry",
        reqd: 1,
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
      const ref = d._ptp_ref_map && d._ptp_ref_map[values.ptp_reference];
      if (!values.sales_order) {
        frappe.msgprint({
          title: __("Missing Sales Order"),
          message: __("Select a Sales Order."),
          indicator: "red",
        });
        return;
      }
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
          sales_order: values.sales_order,
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
    const ref = d._ptp_ref_map && d._ptp_ref_map[d.get_value("ptp_reference")];
    if (!ref) return;
    d.set_value("allocated_amount", Math.max(0, Number(ref.difference_amount || 0)));
  });

  if (d.get_value("sales_order")) {
    load_ptp_references_for_sales_order(d, report, d.get_value("sales_order"));
  }
}

function load_ptp_references_for_sales_order(d, report, salesOrder) {
  if (!salesOrder) {
    d.set_df_property("ptp_reference", "options", "");
    d.set_value("ptp_reference", "");
    d.get_field("sales_order_context").$wrapper.html("");
    d._ptp_ref_map = {};
    return;
  }

  frappe.call({
    method: "snrg_credit_control.overrides.sales_order.get_ptp_references",
    args: { sales_order: salesOrder },
    callback: ({ message }) => {
      const refs = message || [];
      if (!refs.length) {
        d.set_df_property("ptp_reference", "options", "");
        d.set_value("ptp_reference", "");
        d.get_field("sales_order_context").$wrapper.html(
          `<div style="color:var(--text-muted);padding:4px 0;">${__("This Sales Order does not have any PTP entries.")}</div>`
        );
        d._ptp_ref_map = {};
        return;
      }

      const refMap = {};
      const refOptions = refs.map(ref => {
        const label = `${ref.label} | Remaining ${frappe.format(ref.difference_amount || 0, { fieldtype: "Currency", options: report.get_filter_value("currency") || "INR" })} | ${ref.status}`;
        refMap[label] = ref;
        return label;
      });
      d._ptp_ref_map = refMap;
      d.set_df_property("ptp_reference", "options", ["", ...refOptions].join("\n"));
      d.set_value("ptp_reference", "");
      d.set_value("allocated_amount", "");
      d.get_field("payment_entry").get_query = () => ({
        filters: {
          docstatus: 1,
          party_type: "Customer",
          party: infer_customer_from_report(report, salesOrder),
        },
      });
      d.get_field("sales_order_context").$wrapper.html(
        `<div style="background:var(--control-bg);border:1px solid var(--border-color);border-radius:8px;padding:10px 12px;margin-bottom:8px;">
          <div><strong>${__("Sales Order")}:</strong> ${frappe.utils.escape_html(salesOrder)}</div>
        </div>`
      );
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

function infer_customer_from_report(report, salesOrder) {
  const row = (report.data || []).find(entry => entry.name === salesOrder);
  return row && row.customer ? row.customer : undefined;
}
