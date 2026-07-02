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
    {
      fieldname: "basic_report",
      label: __("Basic Report"),
      fieldtype: "Check",
      default: 0,
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
        (print_settings) => {
          print_settings.columns = [];
          print_settings.include_filters = 0;
          report.pdf_report(print_settings);
        },
        report.report_doc && report.report_doc.letter_head,
        report.get_visible_columns ? report.get_visible_columns() : [],
        true
      );

      if (report.add_portrait_warning) {
        report.add_portrait_warning(dialog);
      }
    });
  },

  get_pdf_format(report) {
    const context = getSalaryReportPdfContext(report);

    return `
      <style>
        .salary-certified-report {
          color: #111827;
          font-family: Arial, sans-serif;
          font-size: 10.5px;
          line-height: 1.35;
        }
        .salary-certified-report .report-topline {
          border: 1px solid #111827;
          padding: 6px 10px;
          text-align: center;
          font-size: 10px;
          font-weight: 700;
          letter-spacing: .4px;
          text-transform: uppercase;
        }
        .salary-certified-report .company-block {
          border: 1px solid #111827;
          border-top: 0;
          padding: 14px 18px 12px;
          text-align: center;
        }
        .salary-certified-report .company-name {
          margin: 0 0 5px;
          font-size: 18px;
          font-weight: 700;
          text-transform: uppercase;
        }
        .salary-certified-report .company-address {
          color: #374151;
          font-size: 10.5px;
          white-space: pre-line;
        }
        .salary-certified-report .report-title {
          margin: 14px 0 0;
          font-size: 15px;
          font-weight: 700;
          text-transform: uppercase;
        }
        .salary-certified-report .meta-table,
        .salary-certified-report .salary-table {
          width: 100%;
          border-collapse: collapse;
        }
        .salary-certified-report .meta-table {
          margin: 12px 0 14px;
          border: 1px solid #111827;
        }
        .salary-certified-report .meta-table td {
          border: 1px solid #111827;
          padding: 6px 8px;
          vertical-align: top;
          width: 25%;
        }
        .salary-certified-report .meta-label {
          color: #4b5563;
          display: block;
          font-size: 9px;
          font-weight: 700;
          margin-bottom: 2px;
          text-transform: uppercase;
        }
        .salary-certified-report .meta-value {
          font-size: 11px;
          font-weight: 700;
        }
        .salary-certified-report .salary-table {
          border: 1px solid #111827;
          margin-top: 8px;
        }
        .salary-certified-report .salary-table th,
        .salary-certified-report .salary-table td {
          border: 1px solid #111827;
          padding: 6px 7px;
          vertical-align: top;
        }
        .salary-certified-report .salary-table th {
          background: #f3f4f6;
          color: #111827;
          font-weight: 700;
          text-align: left;
        }
        .salary-certified-report .salary-table .sr-col {
          text-align: center;
          width: 42px;
        }
        .salary-certified-report .salary-table .number-cell {
          text-align: right;
          white-space: nowrap;
        }
        .salary-certified-report .salary-table tfoot td {
          background: #f9fafb;
          font-weight: 700;
        }
        .salary-certified-report .certification {
          border: 1px solid #111827;
          margin-top: 16px;
          padding: 10px 12px;
        }
        .salary-certified-report .certification-title {
          font-weight: 700;
          margin-bottom: 4px;
          text-transform: uppercase;
        }
        .salary-certified-report .signature-row {
          margin-top: 32px;
          width: 100%;
        }
        .salary-certified-report .signature-cell {
          display: inline-block;
          width: 49%;
          vertical-align: bottom;
        }
        .salary-certified-report .signature-line {
          border-top: 1px solid #111827;
          display: inline-block;
          min-width: 190px;
          padding-top: 5px;
        }
      </style>

      <div class="salary-certified-report">
        <div class="report-topline">Certified Salary Statement</div>
        <div class="company-block">
          <h1 class="company-name">${context.company_name}</h1>
          <div class="company-address">${context.company_address}</div>
          <div class="report-title">Employee Salary Management Report</div>
        </div>

        <table class="meta-table">
          <tr>
            <td>
              <span class="meta-label">Salary Month</span>
              <span class="meta-value">${context.month_label}</span>
            </td>
            <td>
              <span class="meta-label">Period</span>
              <span class="meta-value">${context.period_label}</span>
            </td>
            <td>
              <span class="meta-label">Report Type</span>
              <span class="meta-value">${context.report_type}</span>
            </td>
            <td>
              <span class="meta-label">Generated On</span>
              <span class="meta-value">${context.generated_on}</span>
            </td>
          </tr>
        </table>

        <table class="salary-table">
          <thead>
            <tr>
              <th class="sr-col">S. No.</th>
              {% for (let column of columns) { %}
                <th class="{%= column.fieldtype === "Currency" ? "number-cell" : "" %}">
                  {%= frappe.utils.escape_html(__(column.label || "")) %}
                </th>
              {% } %}
            </tr>
          </thead>
          <tbody>
            {% for (let i = 0; i < data.length; i++) { %}
              {% let row = data[i]; %}
              <tr>
                <td class="sr-col">{%= i + 1 %}</td>
                {% for (let column of columns) { %}
                  {% let value = frappe.format(row[column.fieldname], column, { inline: true }, row); %}
                  <td class="{%= column.fieldtype === "Currency" ? "number-cell" : "" %}">
                    {%= value || "" %}
                  </td>
                {% } %}
              </tr>
            {% } %}
          </tbody>
          <tfoot>
            <tr>
              <td colspan="{%= Math.max(columns.length, 1) %}">Total Salary Amount</td>
              <td class="number-cell">{%= format_currency(data.reduce((total, row) => total + flt(row.salary_amount), 0), data[0] && data[0].currency ? data[0].currency : "INR") %}</td>
            </tr>
          </tfoot>
        </table>

        <div class="certification">
          <div class="certification-title">Certification</div>
          <div>
            Certified that the salary details stated above are generated from the company's posted accounting records for the selected salary month.
          </div>
          <div class="signature-row">
            <div class="signature-cell">
              <span class="signature-line">Prepared By</span>
            </div>
            <div class="signature-cell" style="text-align:right;">
              <span class="signature-line">Authorised Signatory</span>
            </div>
          </div>
        </div>
      </div>
    `;
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

function getSalaryReportPdfContext(report) {
  const filterValues = report.get_filter_values ? report.get_filter_values() : {};
  const monthDate = filterValues.month || (report.get_filter_value && report.get_filter_value("month"));
  const monthRange = getSalaryReportMonthRange(monthDate);
  const header = report.$status && report.$status.find(".salary-report-print-header");
  const companyName = header && header.find("h2").text()
    ? header.find("h2").text()
    : filterValues.company || (report.get_filter_value && report.get_filter_value("company")) || "";
  const companyAddress = header && header.find(".company-address").text()
    ? header.find(".company-address").text()
    : "";
  const generatedOn = frappe.datetime && frappe.datetime.now_datetime
    ? frappe.datetime.str_to_user(frappe.datetime.now_datetime())
    : new Date().toLocaleString();

  return {
    company_name: escapeSalaryReportHtml(companyName),
    company_address: escapeSalaryReportHtml(companyAddress),
    month_label: escapeSalaryReportHtml(getSalaryReportMonthLabel(monthDate)),
    period_label: escapeSalaryReportHtml(
      monthRange.from_date && monthRange.to_date
        ? `${frappe.datetime.str_to_user(monthRange.from_date)} to ${frappe.datetime.str_to_user(monthRange.to_date)}`
        : ""
    ),
    report_type: filterValues.basic_report ? "Basic Report" : "Detailed Report",
    generated_on: escapeSalaryReportHtml(generatedOn),
  };
}

function getSalaryReportMonthRange(monthDate) {
  if (!monthDate) {
    return { from_date: "", to_date: "" };
  }

  const parts = monthDate.split("-");
  if (parts.length < 2) {
    return { from_date: monthDate, to_date: monthDate };
  }

  const year = Number(parts[0]);
  const month = Number(parts[1]);
  const lastDay = new Date(year, month, 0).getDate();
  const paddedMonth = String(month).padStart(2, "0");

  return {
    from_date: `${year}-${paddedMonth}-01`,
    to_date: `${year}-${paddedMonth}-${String(lastDay).padStart(2, "0")}`,
  };
}

function getSalaryReportMonthLabel(monthDate) {
  if (!monthDate) {
    return "";
  }

  const parts = monthDate.split("-");
  if (parts.length < 2) {
    return monthDate;
  }

  const date = new Date(Number(parts[0]), Number(parts[1]) - 1, 1);
  return date.toLocaleString(undefined, { month: "long", year: "numeric" });
}

function escapeSalaryReportHtml(value) {
  return frappe.utils.escape_html(String(value || ""));
}
