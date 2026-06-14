frappe.query_reports["Pending Invoice Planning Item Summary"] = {
  disable_prepared_report: true,

  filters: [
    {
      fieldname: "company",
      label: __("Company"),
      fieldtype: "Link",
      options: "Company",
      default: frappe.defaults.get_user_default("Company"),
      reqd: 1,
      on_change: refresh_pending_invoice_planning_item_summary,
    },
    {
      fieldname: "default_warehouse",
      label: __("Default Warehouse"),
      fieldtype: "Link",
      options: "Warehouse",
      reqd: 1,
      get_query() {
        const company = frappe.query_report.get_filter_value("company");
        return company ? { filters: { company } } : {};
      },
      on_change: refresh_pending_invoice_planning_item_summary,
    },
    {
      fieldname: "date_range",
      label: __("Date Range"),
      fieldtype: "DateRange",
      on_change: refresh_pending_invoice_planning_item_summary,
    },
    {
      fieldname: "customer",
      label: __("Customer"),
      fieldtype: "Link",
      options: "Customer",
      on_change: refresh_pending_invoice_planning_item_summary,
    },
    {
      fieldname: "territory",
      label: __("Territory"),
      fieldtype: "Link",
      options: "Territory",
      on_change: refresh_pending_invoice_planning_item_summary,
    },
    {
      fieldname: "quotation",
      label: __("Quotation"),
      fieldtype: "Link",
      options: "Quotation",
      on_change: refresh_pending_invoice_planning_item_summary,
    },
    {
      fieldname: "item_code",
      label: __("Item Code"),
      fieldtype: "Link",
      options: "Item",
      on_change: refresh_pending_invoice_planning_item_summary,
    },
    {
      fieldname: "quotation_status",
      label: __("Quotation Status"),
      fieldtype: "MultiSelectList",
      on_change: refresh_pending_invoice_planning_item_summary,
      get_data(txt) {
        return ["Draft", "Submitted"]
          .filter((option) => !txt || option.toLowerCase().includes(txt.toLowerCase()))
          .map((value) => ({ value, description: value }));
      },
    },
    {
      fieldname: "sales_order_status",
      label: __("Sales Order Status"),
      fieldtype: "MultiSelectList",
      on_change: refresh_pending_invoice_planning_item_summary,
      get_data(txt) {
        return ["No SO", "Draft SO", "Submitted SO", "Mixed SO"]
          .filter((option) => !txt || option.toLowerCase().includes(txt.toLowerCase()))
          .map((value) => ({ value, description: value }));
      },
    },
    {
      fieldname: "production_status",
      label: __("Production Status"),
      fieldtype: "MultiSelectList",
      on_change: refresh_pending_invoice_planning_item_summary,
      get_data(txt) {
        return ["Not Requested", "Open", "In Progress", "Completed", "Cancelled"]
          .filter((option) => !txt || option.toLowerCase().includes(txt.toLowerCase()))
          .map((value) => ({ value, description: value }));
      },
    },
    {
      fieldname: "show_values",
      label: __("Show Values"),
      fieldtype: "Check",
      default: 0,
      on_change: refresh_pending_invoice_planning_item_summary,
    },
  ],

  onload(report) {
    set_pending_invoice_planning_item_summary_stock_breadcrumb();
    set_default_pending_invoice_planning_item_summary_warehouse(report);
  },

  after_datatable_render() {
    set_pending_invoice_planning_item_summary_stock_breadcrumb();
  },

  formatter(value, row, column, data, default_formatter) {
    const formatted = default_formatter(value, row, column, data);
    if (!data) {
      return formatted;
    }

    if (column.fieldname === "item_code") {
      return `<a href="/app/item/${encodeURIComponent(data.item_code || "")}" style="font-weight:700;color:#344054;">${frappe.utils.escape_html(data.item_code || "")}</a>`;
    }

    if (["shortage_qty", "remaining_to_request_qty"].includes(column.fieldname)) {
      const qty = Number(data[column.fieldname] || 0);
      if (qty > 0) {
        return `<span style="color:#b42318;font-weight:700;">${formatted}</span>`;
      }
    }

    if (column.fieldname === "stock_after_pending_qty") {
      const qty = Number(data.stock_after_pending_qty || 0);
      if (qty < 0) {
        return `<span style="color:#b42318;font-weight:700;">${formatted}</span>`;
      }
      return `<span style="color:#027a48;font-weight:700;">${formatted}</span>`;
    }

    if (column.fieldname === "production_status_summary") {
      const text = String(data.production_status_summary || "");
      if (text.includes("In Progress")) {
        return `<span style="color:#b45309;font-weight:700;">${formatted}</span>`;
      }
      if (text.includes("Open")) {
        return `<span style="color:#2563eb;font-weight:700;">${formatted}</span>`;
      }
      if (text === "Not Requested") {
        return `<span style="color:#667085;font-weight:700;">${formatted}</span>`;
      }
    }

    return formatted;
  },
};

function refresh_pending_invoice_planning_item_summary(report) {
  if (!report) {
    return;
  }
  clearTimeout(report.snrgPendingInvoicePlanningItemSummaryRefreshTimer);
  report.snrgPendingInvoicePlanningItemSummaryRefreshTimer = setTimeout(() => {
    report.refresh();
  }, 200);
}

function set_default_pending_invoice_planning_item_summary_warehouse(report) {
  const warehouse = frappe.defaults.get_user_default("Warehouse");
  if (!warehouse || report.get_filter_value("default_warehouse")) {
    return;
  }
  report.set_filter_value("default_warehouse", warehouse);
}

function set_pending_invoice_planning_item_summary_stock_breadcrumb() {
  if (frappe.breadcrumbs) {
    try {
      frappe.breadcrumbs.clear?.();
      frappe.breadcrumbs.add("Stock");
    } catch (error) {
      // Breadcrumb behavior differs slightly across Frappe versions.
    }
  }

  const updateLabel = () => {
    $(".breadcrumb-container a, .breadcrumbs a, .page-head a").each((_, element) => {
      const link = $(element);
      const text = link.text().trim();
      if (text === "Selling" || text === "Credit Control") {
        link.text("Stock");
        link.attr("href", "/app/stock");
      }
    });
  };

  setTimeout(updateLabel, 50);
  setTimeout(updateLabel, 250);
}
