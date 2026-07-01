frappe.query_reports["Employee Salary Management Report"] = {
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
      fieldname: "month",
      label: __("Month"),
      fieldtype: "Date",
      default: `${frappe.datetime.get_today().slice(0, 7)}-01`,
      reqd: 1,
    },
    {
      fieldname: "employee",
      label: __("Employee"),
      fieldtype: "Link",
      options: "Employee",
    },
    {
      fieldname: "salary_account",
      label: __("Salary Account"),
      fieldtype: "Link",
      options: "Account",
      get_query() {
        return {
          filters: {
            company: frappe.query_report.get_filter_value("company"),
            is_group: 0,
          },
        };
      },
    },
  ],

  onload(report) {
    report.page.add_action_item(__("Export Ready PDF"), () => {
      if (typeof report.pdf_report !== "function" || !frappe.ui.get_print_settings) {
        frappe.msgprint({
          title: __("PDF Export Unavailable"),
          message: __("Please use Menu > PDF for this report."),
          indicator: "orange",
        });
        return;
      }

      const dialog = frappe.ui.get_print_settings(
        false,
        (print_settings) => report.pdf_report(print_settings),
        report.report_doc && report.report_doc.letter_head,
        report.get_visible_columns ? report.get_visible_columns() : [],
        true
      );

      if (report.add_portrait_warning) {
        report.add_portrait_warning(dialog);
      }
    });
  },

  formatter(value, row, column, data, default_formatter) {
    value = default_formatter(value, row, column, data);

    if (column.fieldname === "salary_amount" && data && Number(data.salary_amount || 0) > 0) {
      return `<span style="font-weight:600;">${value}</span>`;
    }

    if (column.fieldname === "voucher_no" && data && data.voucher_no) {
      return `<a href="/app/journal-entry/${encodeURIComponent(data.voucher_no)}">${value}</a>`;
    }

    return value;
  },
};
