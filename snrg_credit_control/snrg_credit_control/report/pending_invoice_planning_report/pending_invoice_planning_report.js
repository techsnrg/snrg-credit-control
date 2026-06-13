frappe.query_reports["Pending Invoice Planning Report"] = {
  disable_prepared_report: true,

  filters: [
    {
      fieldname: "company",
      label: __("Company"),
      fieldtype: "Link",
      options: "Company",
      default: frappe.defaults.get_user_default("Company"),
      reqd: 1,
      on_change: refresh_pending_invoice_planning_report,
    },
    {
      fieldname: "date_range",
      label: __("Date Range"),
      fieldtype: "DateRange",
      on_change: refresh_pending_invoice_planning_report,
    },
    {
      fieldname: "customer",
      label: __("Customer"),
      fieldtype: "Link",
      options: "Customer",
      on_change: refresh_pending_invoice_planning_report,
    },
    {
      fieldname: "territory",
      label: __("Territory"),
      fieldtype: "Link",
      options: "Territory",
      on_change: refresh_pending_invoice_planning_report,
    },
    {
      fieldname: "quotation",
      label: __("Quotation"),
      fieldtype: "Link",
      options: "Quotation",
      on_change: refresh_pending_invoice_planning_report,
    },
    {
      fieldname: "item_code",
      label: __("Item Code"),
      fieldtype: "Link",
      options: "Item",
      on_change: refresh_pending_invoice_planning_report,
    },
    {
      fieldname: "quotation_status",
      label: __("Quotation Status"),
      fieldtype: "MultiSelectList",
      on_change: refresh_pending_invoice_planning_report,
      get_data(txt) {
        const options = ["Draft", "Submitted"];
        return options
          .filter((option) => !txt || option.toLowerCase().includes(txt.toLowerCase()))
          .map((value) => ({ value, description: value }));
      },
    },
    {
      fieldname: "sales_order_status",
      label: __("Sales Order Status"),
      fieldtype: "MultiSelectList",
      on_change: refresh_pending_invoice_planning_report,
      get_data(txt) {
        const options = ["No SO", "Draft SO", "Submitted SO", "Mixed SO"];
        return options
          .filter((option) => !txt || option.toLowerCase().includes(txt.toLowerCase()))
          .map((value) => ({ value, description: value }));
      },
    },
  ],

  onload(report) {
    setTimeout(() => force_live_pending_invoice_planning_refresh(report), 300);
    setTimeout(() => setup_pending_invoice_planning_actions(report), 400);
  },

  formatter(value, row, column, data, default_formatter) {
    const formatted = default_formatter(value, row, column, data);
    if (!data) {
      return formatted;
    }

    if (column.fieldname === "status_summary") {
      const valueText = String(data.status_summary || "").toLowerCase();
      if (valueText.includes("draft") && valueText.includes("submitted")) {
        return `<span style="color:#7c3aed;font-weight:600;">${formatted}</span>`;
      }
      if (valueText.includes("draft")) {
        return `<span style="color:#b45309;font-weight:600;">${formatted}</span>`;
      }
      if (valueText.includes("submitted")) {
        return `<span style="color:#2563eb;font-weight:600;">${formatted}</span>`;
      }
    }

    if (column.fieldname === "total_uninvoiced_value") {
      const amount = Number(data.total_uninvoiced_value || 0);
      if (amount > 0) {
        return `<span style="color:#b91c1c;font-weight:700;">${formatted}</span>`;
      }
    }

    if (column.fieldname === "total_uninvoiced_qty") {
      const qty = Number(data.total_uninvoiced_qty || 0);
      if (qty > 0) {
        return `<span style="font-weight:700;">${formatted}</span>`;
      }
    }

    return formatted;
  },
};

function refresh_pending_invoice_planning_report(report) {
  if (!report) {
    return;
  }

  clearTimeout(report.snrgPendingInvoicePlanningRefreshTimer);
  report.snrgPendingInvoicePlanningRefreshTimer = setTimeout(() => {
    report.refresh();
  }, 200);
}

function force_live_pending_invoice_planning_refresh(report) {
  if (!report || report.__snrgPendingInvoicePlanningLiveRefreshDone) {
    return;
  }

  const wrapperText = report.page && report.page.wrapper ? report.page.wrapper.text() : "";
  if (wrapperText && wrapperText.includes("See all past reports")) {
    report.__snrgPendingInvoicePlanningLiveRefreshDone = true;
    report.refresh();
  }
}

function setup_pending_invoice_planning_actions(report) {
  if (!report || report.__snrgPendingInvoicePlanningActionsSetup) {
    return;
  }

  report.__snrgPendingInvoicePlanningActionsSetup = true;
  report.page.add_action_item(__("Request Production"), () => create_production_requests_from_report(report));
  report.page.add_action_item(__("Open Production Planning"), () => {
    frappe.route_options = {
      company: report.get_filter_value("company") || "",
    };
    frappe.set_route("production-planning");
  });
}

function create_production_requests_from_report(report) {
  const rows = get_selected_pending_invoice_planning_rows(report);
  if (!rows.length) {
    frappe.msgprint({
      title: __("Select Rows"),
      message: __("Select one or more rows from the report to create Production Requests."),
      indicator: "orange",
    });
    return;
  }

  const payload = rows.map((row) => ({
    quotation: row.quotation,
    quotation_date: row.quotation_date,
    customer: row.customer,
    customer_name: row.customer_name,
    company: row.company,
    item_code: row.item_code,
    item_name: row.item_name,
    requested_qty: row.total_uninvoiced_qty,
  }));

  frappe.call({
    method: "snrg_credit_control.snrg_credit_control.doctype.production_request.production_request.create_from_pending_rows",
    args: {
      rows: payload,
    },
    freeze: true,
    freeze_message: __("Creating Production Requests..."),
    callback: ({ message }) => {
      const result = message || {};
      frappe.show_alert({
        message: result.message || __("Production Requests created."),
        indicator: "green",
      });
      report.refresh();
      frappe.route_options = {
        company: report.get_filter_value("company") || "",
      };
      frappe.set_route("production-planning");
    },
  });
}

function get_selected_pending_invoice_planning_rows(report) {
  const datatableRowmanager = report.datatable && report.datatable.rowmanager;
  if (!datatableRowmanager || !datatableRowmanager.getCheckedRows) {
    return [];
  }

  const checkedRows = datatableRowmanager.getCheckedRows() || [];
  return checkedRows
    .map((index) => (report.data || [])[index] || null)
    .filter(Boolean);
}
