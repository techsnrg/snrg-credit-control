frappe.query_reports["Legal Tracker"] = {
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
      fieldname: "status",
      label: __("Status"),
      fieldtype: "Select",
      options: "\nMarked to Legal\nDocuments Pending\nUnder Review\nNotice Preparation\nNotice Sent\nFollow-up in Progress\nSettlement Discussion\nPartially Recovered\nFully Recovered\nComplaint / Case Filing\nIn Proceedings\nClosed",
    },
    {
      fieldname: "assigned_counsel",
      label: __("Assigned Counsel"),
      fieldtype: "Link",
      options: "User",
    },
    {
      fieldname: "show_closed",
      label: __("Show Closed"),
      fieldtype: "Check",
      default: 0,
    },
  ],
};
