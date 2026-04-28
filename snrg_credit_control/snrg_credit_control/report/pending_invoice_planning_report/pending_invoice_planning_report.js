frappe.query_reports["Pending Invoice Planning Report"] = {
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
      fieldname: "date_range",
      label: __("Date Range"),
      fieldtype: "DateRange",
    },
    {
      fieldname: "customer",
      label: __("Customer"),
      fieldtype: "Link",
      options: "Customer",
    },
    {
      fieldname: "territory",
      label: __("Territory"),
      fieldtype: "Link",
      options: "Territory",
    },
    {
      fieldname: "quotation",
      label: __("Quotation"),
      fieldtype: "Link",
      options: "Quotation",
    },
    {
      fieldname: "item_code",
      label: __("Item Code"),
      fieldtype: "Link",
      options: "Item",
    },
    {
      fieldname: "quotation_status",
      label: __("Quotation Status"),
      fieldtype: "MultiSelectList",
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
      get_data(txt) {
        const options = ["No SO", "Draft SO", "Submitted SO", "Mixed SO"];
        return options
          .filter((option) => !txt || option.toLowerCase().includes(txt.toLowerCase()))
          .map((value) => ({ value, description: value }));
      },
    },
  ],

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
