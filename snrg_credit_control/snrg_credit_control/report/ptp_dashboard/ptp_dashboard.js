frappe.query_reports["PTP Dashboard"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
        },
        {
            fieldname: "status",
            label: __("Status"),
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                const options = [
                    "Pending",
                    "Partially Cleared",
                    "Cleared",
                    "Broken",
                    "Superseded",
                ];
                return options
                    .filter(option => !txt || option.toLowerCase().includes(txt.toLowerCase()))
                    .map(value => ({ value, description: value }));
            },
        },
        {
            fieldname: "bucket",
            label: __("Bucket"),
            fieldtype: "Select",
            options: "\nDue Today\nOverdue\nUpcoming This Week\nPartially Cleared\nUpcoming Later\nNo Date",
        },
        {
            fieldname: "ptp_by",
            label: __("Committed By"),
            fieldtype: "Link",
            options: "Employee",
        },
    ],

    formatter(value, row, column, data, default_formatter) {
        const formatted = default_formatter(value, row, column, data);

        if (!data) {
            return formatted;
        }

        if (column.fieldname === "status") {
            const colors = {
                "Pending": "orange",
                "Partially Cleared": "blue",
                "Cleared": "green",
                "Broken": "red",
                "Superseded": "gray",
            };
            const color = colors[data.status] || "gray";
            return `<span style="color:${color};font-weight:600;">${formatted}</span>`;
        }

        if (column.fieldname === "bucket") {
            const colors = {
                "Due Today": "#d97706",
                "Overdue": "#dc2626",
                "Upcoming This Week": "#2563eb",
                "Partially Cleared": "#0891b2",
                "Upcoming Later": "#6b7280",
                "No Date": "#6b7280",
            };
            const color = colors[data.bucket] || "#6b7280";
            return `<span style="color:${color};font-weight:600;">${formatted}</span>`;
        }

        if (column.fieldname === "difference_amount") {
            const amount = flt(data.difference_amount || 0);
            const color = amount > 0 ? "#dc2626" : "#16a34a";
            return `<span style="color:${color};font-weight:600;">${formatted}</span>`;
        }

        return formatted;
    },
};
