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
      fieldtype: "Data",
      default: frappe.datetime.get_today().slice(0, 7),
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

  onload(report) {
    setTimeout(() => {
      const filter = report.get_filter("plan_month");
      if (!filter || !filter.$input) return;
      filter.$input.attr("type", "month");
      filter.$input.attr("placeholder", "YYYY-MM");
    }, 0);
  },

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
