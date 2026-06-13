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
    {
      fieldname: "show_values",
      label: __("Show Values"),
      fieldtype: "Check",
      default: 0,
      on_change: refresh_pending_invoice_planning_report,
    },
  ],

  onload(report) {
    setTimeout(() => force_live_pending_invoice_planning_refresh(report), 300);
    setTimeout(() => setup_pending_invoice_planning_actions(report), 400);
  },

  formatter(value, row, column, data, default_formatter) {
    if (column.fieldname === "production_request_action" && data) {
      const pendingQty = Number(data.total_uninvoiced_qty || 0);
      if (pendingQty <= 0) {
        return "";
      }

      return `
        <button
          type="button"
          class="btn btn-xs btn-default snrg-pip-request-production"
          data-quotation="${encodeURIComponent(data.quotation || "")}"
          data-quotation-date="${encodeURIComponent(data.quotation_date || "")}"
          data-customer="${encodeURIComponent(data.customer || "")}"
          data-customer-name="${encodeURIComponent(data.customer_name || "")}"
          data-company="${encodeURIComponent(data.company || "")}"
          data-item-code="${encodeURIComponent(data.item_code || "")}"
          data-item-name="${encodeURIComponent(data.item_name || "")}"
          data-requested-qty="${encodeURIComponent(String(data.total_uninvoiced_qty || 0))}"
        >
          ${__("Request")}
        </button>
      `;
    }

    if (column.fieldname === "quotation" && data) {
      return render_pending_invoice_planning_stacked_link({
        route: `/app/quotation/${encodeURIComponent(data.quotation || "")}`,
        primary: data.quotation || "",
        secondary: formatPendingInvoicePlanningDate(data.quotation_date),
      });
    }

    if (column.fieldname === "customer" && data) {
      return render_pending_invoice_planning_stacked_link({
        route: `/app/customer/${encodeURIComponent(data.customer || "")}`,
        primary: data.customer || "",
        secondary: data.customer_name || "",
      });
    }

    if (column.fieldname === "item_code" && data) {
      return render_pending_invoice_planning_link({
        route: `/app/item/${encodeURIComponent(data.item_code || "")}`,
        label: data.item_code || "",
      });
    }

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
  report.page.add_action_item(__("Open Production Planning"), () => {
    frappe.route_options = {
      company: report.get_filter_value("company") || "",
    };
    frappe.set_route("production-planning");
  });

  const wrapper = report.page && report.page.wrapper ? report.page.wrapper : $(document.body);
  wrapper.off("click.snrg_pip_request_production");
  wrapper.on("click.snrg_pip_request_production", ".snrg-pip-request-production", (event) => {
    event.preventDefault();
    const button = $(event.currentTarget);
    create_production_request_from_button(report, button);
  });
}

function create_production_request_from_button(report, button) {
  if (!button || !button.length) {
    return;
  }

  const payload = [{
    quotation: decodeURIComponent(button.attr("data-quotation") || ""),
    quotation_date: decodeURIComponent(button.attr("data-quotation-date") || ""),
    customer: decodeURIComponent(button.attr("data-customer") || ""),
    customer_name: decodeURIComponent(button.attr("data-customer-name") || ""),
    company: decodeURIComponent(button.attr("data-company") || ""),
    item_code: decodeURIComponent(button.attr("data-item-code") || ""),
    item_name: decodeURIComponent(button.attr("data-item-name") || ""),
    requested_qty: Number(decodeURIComponent(button.attr("data-requested-qty") || "0")) || 0,
  }];

  button.prop("disabled", true).text(__("Creating..."));

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
      button
        .removeClass("btn-default")
        .addClass("btn-secondary")
        .prop("disabled", true)
        .text(result.updated_count ? __("Updated") : __("Requested"));
    },
    error: () => {
      button.prop("disabled", false).text(__("Request"));
    },
  });
}

function render_pending_invoice_planning_stacked_link({ route, primary, secondary }) {
  return `
    <div style="display:grid;gap:2px;line-height:1.25;">
      <a href="${route}" style="font-weight:700;color:#0f766e;">${frappe.utils.escape_html(primary || "")}</a>
      <div style="color:#667085;font-size:12px;">${frappe.utils.escape_html(secondary || "")}</div>
    </div>
  `;
}

function render_pending_invoice_planning_link({ route, label }) {
  return `<a href="${route}" style="font-weight:600;color:#344054;">${frappe.utils.escape_html(label || "")}</a>`;
}

function formatPendingInvoicePlanningDate(value) {
  if (!value) {
    return "";
  }
  return frappe.datetime.str_to_user ? frappe.datetime.str_to_user(value) : value;
}
