frappe.query_reports["Customer Credit Review"] = {
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
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "Link",
            options: "Customer",
            get_query: () => ({ filters: { disabled: 0 } }),
        },
        {
            fieldname: "search",
            label: __("Search"),
            fieldtype: "Data",
            placeholder: __("Code, name, group, or cheque status"),
        },
    ],

    formatter(value, row, column, data, default_formatter) {
        const formatted = default_formatter(value, row, column, data);
        if (!data) {
            return formatted;
        }

        if (column.fieldname === "security_cheque_available") {
            const color = data.security_cheque_available === "Yes" ? "#16a34a" : "#dc2626";
            return `<span style="color:${color};font-weight:600;">${formatted}</span>`;
        }

        if (["over_limit_amount", "overdue_outstanding"].includes(column.fieldname)) {
            return flt(data[column.fieldname] || 0) > 0
                ? `<span style="color:#dc2626;font-weight:600;">${formatted}</span>`
                : formatted;
        }

        if (column.fieldname === "remaining_limit") {
            const color = flt(data.remaining_limit || 0) < 0 ? "#dc2626" : "#16a34a";
            return `<span style="color:${color};font-weight:600;">${formatted}</span>`;
        }

        if (column.fieldname === "gap_vs_recommended") {
            const color = flt(data.gap_vs_recommended || 0) >= 0 ? "#2563eb" : "#dc2626";
            return `<span style="color:${color};font-weight:600;">${formatted}</span>`;
        }

        return formatted;
    },
};
