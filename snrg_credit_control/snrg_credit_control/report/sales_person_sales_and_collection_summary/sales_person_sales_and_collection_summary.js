frappe.query_reports["Sales Person Sales and Collection Summary"] = {
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
      default: getDefaultDateRange(),
      reqd: 1,
    },
    {
      fieldname: "employee",
      label: __("Employee"),
      fieldtype: "Link",
      options: "Employee",
    },
  ],

  onload(report) {
    report.page.add_action_item(__("Copy All Messages"), () => {
      const messages = (report.data || [])
        .map((row) => row.whatsapp_message)
        .filter(Boolean);
      copyReportText(messages.join("\n\n"));
    });

    report.page.add_action_item(__("Copy All Detailed Messages"), () => {
      const messages = (report.data || [])
        .map((row) => row.detailed_whatsapp_message)
        .filter(Boolean);
      copyReportText(messages.join("\n\n"));
    });
  },

  formatter(value, row, column, data, default_formatter) {
    if (column.fieldname === "copy_message" && data && data.whatsapp_message) {
      const encoded = encodeURIComponent(data.whatsapp_message).replace(/'/g, "%27");
      return `<button class="btn btn-xs btn-default" onclick="window.copySalesCollectionMessage('${encoded}')">${__(
        "Copy Message"
      )}</button>`;
    }
    if (column.fieldname === "copy_detailed_message" && data && data.detailed_whatsapp_message) {
      const encoded = encodeURIComponent(data.detailed_whatsapp_message).replace(/'/g, "%27");
      return `<button class="btn btn-xs btn-default" onclick="window.copySalesCollectionMessage('${encoded}')">${__(
        "Copy Detailed"
      )}</button>`;
    }
    return default_formatter(value, row, column, data);
  },
};

window.copySalesCollectionMessage = function copySalesCollectionMessage(encodedMessage) {
  copyReportText(decodeURIComponent(encodedMessage));
};

function copyReportText(text) {
  if (!text) {
    frappe.show_alert({ message: __("No messages to copy."), indicator: "orange" });
    return;
  }

  frappe.utils.copy_to_clipboard(text);
  frappe.show_alert({ message: __("WhatsApp message copied."), indicator: "green" });
}

function getDefaultDateRange() {
  const today = frappe.datetime.get_today();
  const day = new Date(`${today}T00:00:00`).getDay();

  if (day === 1) {
    return [frappe.datetime.add_days(today, -7), frappe.datetime.add_days(today, -1)];
  }
  if (day === 4) {
    return [frappe.datetime.add_days(today, -3), frappe.datetime.add_days(today, -1)];
  }

  const daysSinceMonday = (day + 6) % 7;
  return [frappe.datetime.add_days(today, -daysSinceMonday), today];
}
