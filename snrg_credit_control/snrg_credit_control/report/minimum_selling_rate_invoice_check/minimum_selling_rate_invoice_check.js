frappe.query_reports["Minimum Selling Rate Invoice Check"] = {
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
      label: __("Posting Date Range"),
      fieldtype: "DateRange",
      reqd: 1,
    },
    {
      fieldname: "customer",
      label: __("Customer"),
      fieldtype: "Link",
      options: "Customer",
    },
    {
      fieldname: "customer_group",
      label: __("Customer Group"),
      fieldtype: "Link",
      options: "Customer Group",
    },
    {
      fieldname: "item_code",
      label: __("Item Code"),
      fieldtype: "Link",
      options: "Item",
    },
    {
      fieldname: "item_group",
      label: __("Item Group"),
      fieldtype: "Link",
      options: "Item Group",
    },
    {
      fieldname: "only_issues",
      label: __("Only Issues"),
      fieldtype: "Check",
      default: 1,
    },
  ],

  formatter(value, row, column, data, default_formatter) {
    const formatted = default_formatter(value, row, column, data);
    if (!data) return formatted;

    if (column.fieldname === "status") {
      const status = String(data.status || "");
      if (status === "OK") {
        return `<span style="color:#16a34a;font-weight:600;">${formatted}</span>`;
      }
      if (status === "Below Minimum") {
        return `<span style="color:#dc2626;font-weight:700;">${formatted}</span>`;
      }
      return `<span style="color:#b45309;font-weight:700;">${formatted}</span>`;
    }

    if (column.fieldname === "variance" && Number(data.variance || 0) < 0) {
      return `<span style="color:#dc2626;font-weight:700;">${formatted}</span>`;
    }

    return formatted;
  },
};
