frappe.query_reports["Monthly Sales Plan Achievement"] = {
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
      fieldname: "plan_month",
      label: __("Plan Month"),
      fieldtype: "Date",
      default: frappe.datetime.month_start(frappe.datetime.get_today()),
      reqd: 1,
    },
    {
      fieldname: "sales_person",
      label: __("Sales Person"),
      fieldtype: "Link",
      options: "Sales Person",
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
      fieldname: "territory",
      label: __("Territory"),
      fieldtype: "Link",
      options: "Territory",
    },
    {
      fieldname: "include_superseded",
      label: __("Include Superseded"),
      fieldtype: "Check",
      default: 0,
    },
    {
      fieldname: "status",
      label: __("Plan Status"),
      fieldtype: "Select",
      options: "\nFrozen\nSuperseded",
      depends_on: "eval:doc.include_superseded",
    },
  ],

  formatter(value, row, column, data, default_formatter) {
    const formatted = default_formatter(value, row, column, data);
    if (!data) return formatted;

    if (column.fieldname === "revision_status" && data.revision_status === __("Revised")) {
      return `<span class="indicator-pill orange">${formatted}</span>`;
    }

    if (column.fieldname === "plan_status" && data.plan_status === "Superseded") {
      return `<span class="indicator-pill gray">${formatted}</span>`;
    }

    return formatted;
  },
};
