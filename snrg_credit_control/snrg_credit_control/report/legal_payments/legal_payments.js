frappe.query_reports["Legal Payments"] = {
  filters: [
    {
      fieldname: "company",
      label: __("Company"),
      fieldtype: "Link",
      options: "Company",
    },
    {
      fieldname: "customer",
      label: __("Customer"),
      fieldtype: "Link",
      options: "Customer",
    },
    {
      fieldname: "from_date",
      label: __("From Date"),
      fieldtype: "Date",
    },
    {
      fieldname: "to_date",
      label: __("To Date"),
      fieldtype: "Date",
    },
    {
      fieldname: "assigned_counsel",
      label: __("Assigned Counsel"),
      fieldtype: "Link",
      options: "User",
    },
  ],
};
