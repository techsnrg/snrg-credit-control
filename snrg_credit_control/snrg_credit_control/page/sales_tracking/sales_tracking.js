frappe.pages["sales-tracking"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Sales Tracking",
        single_column: true,
    });

    wrapper.sales_tracking = new SnrgSalesTrackingPage(page, wrapper);
};

class SnrgSalesTrackingPage {
    constructor(page, wrapper) {
        this.page = page;
        this.wrapper = $(wrapper);
        this.data = null;
        this.controls = {};
        this.sortState = { key: null, direction: null };
        this.columnFilters = {};
        this.columns = [];

        this.setup();
    }

    setup() {
        this.page.set_primary_action("Refresh", () => this.refresh(), "refresh");
        this.render_shell();
        this.make_filters();
        this.bind_events();
        this.refresh();
    }

    render_shell() {
        this.wrapper.find(".layout-main-section").html(`
            <style>
                .snrg-st-page { display:flex; flex-direction:column; gap:18px; color:#10253f; }
                .snrg-st-filter-panel {
                    border-radius:22px; border:1px solid #dbe3ef; background:#fff;
                    box-shadow:0 10px 22px rgba(15,23,42,.04); padding:20px 20px 18px;
                }
                .snrg-st-filter-header {
                    display:flex; justify-content:space-between; gap:16px; align-items:flex-start; flex-wrap:wrap; margin-bottom:16px;
                }
                .snrg-st-filter-title h2 {
                    margin:0; font-size:24px; line-height:1.1; font-weight:800; color:#0f172a;
                }
                .snrg-st-filter-title p {
                    margin:6px 0 0; font-size:13px; line-height:1.55; color:#64748b; max-width:760px;
                }
                .snrg-st-meta { display:flex; gap:10px; flex-wrap:wrap; }
                .snrg-st-chip {
                    display:inline-flex; align-items:center; gap:6px; padding:7px 11px; border-radius:999px;
                    background:#f8fafc; border:1px solid #dbe3ef; font-size:12px; color:#334155; font-weight:600;
                }
                .snrg-st-filter-row { display:grid; grid-template-columns:repeat(6, minmax(180px, 1fr)); gap:12px; align-items:start; }
                .snrg-st-filter-slot {
                    width: 100%;
                }
                .snrg-st-filter-row .frappe-control {
                    margin-bottom: 0;
                    padding: 10px 12px 10px;
                    border: 1px solid #dbe3ef;
                    border-radius: 16px;
                    background: #fbfdff;
                    box-shadow: none;
                    min-height: 78px;
                }
                .snrg-st-filter-row .frappe-control .control-label {
                    font-size: 11px;
                    font-weight: 700;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: .08em;
                    margin-bottom: 8px;
                }
                .snrg-st-filter-row .frappe-control input,
                .snrg-st-filter-row .frappe-control .input-with-feedback,
                .snrg-st-filter-row .frappe-control .link-field,
                .snrg-st-filter-row .frappe-control select {
                    min-height: 40px;
                    border-radius: 12px;
                    border: 1px solid #dbe3ef;
                    background: #fff;
                }
                .snrg-st-summary { display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:12px; }
                .snrg-st-card {
                    border-radius:18px; padding:16px; border:1px solid #e2e8f0;
                    background:#fff; box-shadow:0 8px 18px rgba(15,23,42,.03);
                }
                .snrg-st-card.interactive {
                    cursor: pointer;
                    transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease;
                }
                .snrg-st-card.interactive:hover {
                    border-color: #94a3b8;
                    box-shadow: 0 12px 24px rgba(15,23,42,.06);
                    transform: translateY(-1px);
                }
                .snrg-st-card-label { font-size:11px; color:#5b7088; text-transform:uppercase; letter-spacing:.08em; font-weight:700; }
                .snrg-st-card-value { margin-top:10px; font-size:24px; line-height:1.1; font-weight:800; color:#0f172a; }
                .snrg-st-table-shell {
                    border-radius:24px; border:1px solid #e2e8f0; background:#fff;
                    box-shadow:0 12px 24px rgba(15,23,42,.04); overflow:hidden;
                }
                .snrg-st-table-toolbar {
                    display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap; padding:16px 18px;
                    border-bottom:1px solid #e2e8f0; background:#f8fafc;
                }
                .snrg-st-table-wrap {
                    overflow: auto;
                    max-height: calc(100vh - 260px);
                }
                .snrg-st-table { width:100%; min-width:1900px; border-collapse:separate; border-spacing:0; }
                .snrg-st-table th {
                    position:sticky; top:0; z-index:3; background:#f8fafc; border-bottom:1px solid #e2e8f0;
                    font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:#64748b; text-align:left;
                    padding:12px 14px; white-space:nowrap;
                    box-shadow: inset 0 -1px 0 #e2e8f0;
                }
                .snrg-st-th-content {
                    display:flex; align-items:center; justify-content:space-between; gap:8px;
                }
                .snrg-st-th-main {
                    display:inline-flex; align-items:center; gap:6px; min-width:0;
                }
                .snrg-st-th-label {
                    cursor:pointer; user-select:none;
                }
                .snrg-st-th-sort {
                    font-size:10px; color:#94a3b8;
                }
                .snrg-st-th-actions {
                    display:inline-flex; align-items:center; gap:4px;
                }
                .snrg-st-th-btn {
                    display:inline-flex; align-items:center; justify-content:center;
                    width:22px; height:22px; border-radius:999px; border:1px solid transparent;
                    background:transparent; color:#64748b; cursor:pointer;
                }
                .snrg-st-th-btn:hover {
                    border-color:#cbd5e1; background:#fff;
                }
                .snrg-st-th-btn.active {
                    border-color:#94a3b8; background:#fff; color:#0f172a;
                }
                .snrg-st-table td {
                    padding:12px 14px; border-bottom:1px solid #edf2f7; font-size:13px; line-height:1.45; vertical-align:top;
                    color:#1e293b;
                }
                .snrg-st-table tfoot td {
                    position: sticky;
                    bottom: 0;
                    z-index: 2;
                    background: #f8fafc;
                    border-top: 2px solid #cbd5e1;
                    font-size: 12px;
                    font-weight: 800;
                    color: #0f172a;
                    box-shadow: inset 0 1px 0 #e2e8f0;
                }
                .snrg-st-table tr:hover td { background:#fcfdff; }
                .snrg-st-link { color:#0f766e; font-weight:700; text-decoration:none; cursor:pointer; }
                .snrg-st-link:hover { text-decoration:underline; }
                .snrg-st-muted { color:#64748b; }
                .snrg-st-pill {
                    display:inline-flex; align-items:center; padding:5px 10px; border-radius:999px;
                    font-size:11px; font-weight:700; border:1px solid #dbe3ef; background:#f8fafc; color:#334155;
                }
                .snrg-st-pill.red { background:#fef2f2; border-color:#fecaca; color:#b91c1c; }
                .snrg-st-pill.green { background:#ecfdf5; border-color:#bbf7d0; color:#047857; }
                .snrg-st-pill.amber { background:#fffbeb; border-color:#fcd34d; color:#b45309; }
                .snrg-st-pill.blue { background:#eff6ff; border-color:#bfdbfe; color:#1d4ed8; }
                .snrg-st-pill.slate { background:#f8fafc; border-color:#cbd5e1; color:#475569; }
                .snrg-st-empty {
                    padding:28px 16px; text-align:center; color:#64748b; font-size:13px; border:1px dashed #cbd5e1;
                    border-radius:18px; background:#f8fafc; margin:16px;
                }
                .snrg-st-cell-lines { display:flex; flex-direction:column; gap:3px; min-width:0; }
                .snrg-st-cell-lines .secondary { color:#64748b; font-size:12px; }
                .snrg-st-remarks {
                    max-width:260px; white-space:normal; word-break:break-word; display:-webkit-box;
                    -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
                }
                .snrg-st-skeleton {
                    height:280px; margin:16px; border-radius:18px;
                    background:linear-gradient(90deg, #e2e8f0 25%, #f8fafc 50%, #e2e8f0 75%);
                    background-size:220% 100%; animation:snrg-st-shimmer 1.4s infinite;
                }
                @keyframes snrg-st-shimmer { 0% { background-position:200% 0; } 100% { background-position:-200% 0; } }
                @media (max-width: 1280px) { .snrg-st-filter-row, .snrg-st-summary { grid-template-columns:repeat(2, minmax(0, 1fr)); } .snrg-st-table-wrap { max-height: calc(100vh - 220px); } }
                @media (max-width: 768px) { .snrg-st-filter-row, .snrg-st-summary { grid-template-columns:1fr; } .snrg-st-filter-title h2 { font-size:24px; } }
            </style>
            <div class="snrg-st-page">
                <section class="snrg-st-filter-panel">
                    <div class="snrg-st-filter-header">
                        <div class="snrg-st-filter-title">
                            <h2>Sales Tracking</h2>
                            <p>Track customer quotations through credit, billing, dispatch, delivery, and POD completion from one operational view.</p>
                        </div>
                        <div class="snrg-st-meta"></div>
                    </div>
                    <div class="snrg-st-filter-row">
                        <div class="snrg-st-filter-slot snrg-st-company-filter"></div>
                        <div class="snrg-st-filter-slot snrg-st-month-filter"></div>
                        <div class="snrg-st-filter-slot snrg-st-date-range-filter"></div>
                        <div class="snrg-st-filter-slot snrg-st-territory-filter"></div>
                        <div class="snrg-st-filter-slot snrg-st-credit-filter"></div>
                        <div class="snrg-st-filter-slot snrg-st-search-filter"></div>
                    </div>
                </section>
                <section class="snrg-st-summary"></section>
                <section class="snrg-st-table-shell">
                    <div class="snrg-st-table-toolbar">
                        <div class="snrg-st-toolbar-title">
                            <strong>Live Tracker</strong>
                            <span class="snrg-st-muted">Click invoice, salesperson, SO delivery, or remarks cells for detail.</span>
                        </div>
                        <div class="snrg-st-row-count snrg-st-muted"></div>
                    </div>
                    <div class="snrg-st-table-wrap">
                        <div class="snrg-st-table-container"></div>
                    </div>
                </section>
            </div>
        `);
    }

    make_filters() {
        this.controls.company = this.makeFilterControl(".snrg-st-company-filter", {
            label: "Company",
            fieldname: "company",
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company"),
            change: () => this.refresh(),
        });

        this.controls.order_month = this.makeFilterControl(".snrg-st-month-filter", {
            label: "Order Month",
            fieldname: "order_month",
            fieldtype: "Select",
            options: "\n",
            change: () => this.refresh(),
        });

        this.controls.date_range = this.makeFilterControl(".snrg-st-date-range-filter", {
            label: "Date Range",
            fieldname: "date_range",
            fieldtype: "DateRange",
            change: () => this.refresh(),
        });

        this.controls.territory = this.makeFilterControl(".snrg-st-territory-filter", {
            label: "Zone",
            fieldname: "territory",
            fieldtype: "Select",
            options: "\n",
            change: () => this.refresh(),
        });

        this.controls.credit_status = this.makeFilterControl(".snrg-st-credit-filter", {
            label: "Credit Status",
            fieldname: "credit_status",
            fieldtype: "Select",
            options: "\nCredit OK\nCredit Hold\nMixed\nNot Run",
            change: () => this.refresh(),
        });

        this.controls.search = this.makeFilterControl(".snrg-st-search-filter", {
            label: "Search",
            fieldname: "search",
            fieldtype: "Data",
            placeholder: "Quotation / customer",
            change: frappe.utils.debounce(() => this.refresh(), 350),
        });

        this.render_loading();
    }

    makeFilterControl(selector, df) {
        const parent = this.wrapper.find(selector).get(0);
        const control = frappe.ui.form.make_control({
            parent,
            df,
            render_input: true,
        });
        control.refresh();
        return control;
    }

    bind_events() {
        this.wrapper.on("click", ".snrg-st-sort-toggle", (event) => {
            const key = $(event.currentTarget).data("columnKey");
            if (!key) return;
            this.toggleSort(key);
        });

        this.wrapper.on("click", ".snrg-st-filter-toggle", (event) => {
            const key = $(event.currentTarget).data("columnKey");
            if (!key) return;
            this.openColumnFilter(key);
        });

        this.wrapper.on("click", ".snrg-st-open-quotation", (event) => {
            const index = Number($(event.currentTarget).closest("[data-row-index]").data("rowIndex"));
            const row = this.getVisibleRows()[index];
            if (row) {
                frappe.set_route("Form", "Quotation", row.quotation_id);
            }
        });

        this.wrapper.on("click", ".snrg-st-open-comments", (event) => {
            event.preventDefault();
            const index = Number($(event.currentTarget).closest("[data-row-index]").data("rowIndex"));
            const row = this.getVisibleRows()[index];
            if (row?.quotation_comments_url) {
                window.location.href = row.quotation_comments_url;
            }
        });

        this.wrapper.on("click", ".snrg-st-open-salespeople", (event) => {
            const index = Number($(event.currentTarget).closest("[data-row-index]").data("rowIndex"));
            const row = this.getVisibleRows()[index];
            if (row) {
                this.showSalespeopleDialog(row);
            }
        });

        this.wrapper.on("click", ".snrg-st-open-invoices", (event) => {
            const index = Number($(event.currentTarget).closest("[data-row-index]").data("rowIndex"));
            const row = this.getVisibleRows()[index];
            if (row) {
                this.showInvoicesDialog(row);
            }
        });

        this.wrapper.on("click", ".snrg-st-open-sales-orders", (event) => {
            const index = Number($(event.currentTarget).closest("[data-row-index]").data("rowIndex"));
            const row = this.getVisibleRows()[index];
            if (row) {
                this.showSalesOrdersDialog(row);
            }
        });

        this.wrapper.on("click", ".snrg-st-summary-card[data-summary-action]", (event) => {
            const action = $(event.currentTarget).data("summaryAction");
            if (action === "credit-hold") {
                this.controls.credit_status.set_value("Credit Hold");
                this.refresh();
            }
            if (action === "clear-credit-hold") {
                this.controls.credit_status.set_value("");
                this.refresh();
            }
        });
    }

    async refresh() {
        this.render_loading();
        const dateRange = this.controls.date_range.get_value() || [];
        const [fromDate, toDate] = Array.isArray(dateRange) ? dateRange : [null, null];
        const response = await frappe.call({
            method: "snrg_credit_control.snrg_credit_control.page.sales_tracking.sales_tracking.get_tracker_data",
            args: {
                company: this.controls.company.get_value(),
                order_month: this.controls.order_month.get_value(),
                from_date: fromDate,
                to_date: toDate,
                territory: this.controls.territory.get_value(),
                credit_status: this.controls.credit_status.get_value(),
                search: this.controls.search.get_value(),
            },
        });
        this.data = response.message || { rows: [], summary: {} };
        this.updateOrderMonthOptions();
        this.updateTerritoryOptions();
        this.render();
    }

    render_loading() {
        this.wrapper.find(".snrg-st-summary").html(Array.from({ length: 5 }, () => `
            <div class="snrg-st-card"><div class="snrg-st-card-label">Loading</div><div class="snrg-st-card-value">…</div></div>
        `).join(""));
        this.wrapper.find(".snrg-st-table-container").html(`<div class="snrg-st-skeleton"></div>`);
        this.wrapper.find(".snrg-st-row-count").text("Loading…");
    }

    render() {
        this.updateOrderMonthOptions();
        this.updateTerritoryOptions();
        this.renderMeta();
        this.renderSummary();
        this.renderTable();
    }

    updateOrderMonthOptions() {
        if (!this.controls.order_month) return;

        const currentValue = this.controls.order_month.get_value();
        const monthMap = new Map();

        (this.data?.rows || []).forEach((row) => {
            if (row.order_month_value && row.order_month) {
                monthMap.set(row.order_month_value, row.order_month);
            }
        });

        const optionLines = [""];
        [...monthMap.entries()]
            .sort((left, right) => right[0].localeCompare(left[0]))
            .forEach(([, label]) => {
                optionLines.push(label);
            });

        this.controls.order_month.df.options = optionLines.join("\n");
        this.controls.order_month.refresh();
        if (currentValue && optionLines.includes(currentValue)) {
            this.controls.order_month.set_value(currentValue);
        }
    }

    updateTerritoryOptions() {
        if (!this.controls.territory) return;

        const currentValue = this.controls.territory.get_value();
        const values = new Set();
        (this.data?.rows || []).forEach((row) => {
            if (row.zone) {
                values.add(String(row.zone));
            }
        });

        const optionLines = [""];
        [...values]
            .sort((left, right) => left.localeCompare(right, undefined, { sensitivity: "base" }))
            .forEach((value) => optionLines.push(value));

        this.controls.territory.df.options = optionLines.join("\n");
        this.controls.territory.refresh();
        if (currentValue && optionLines.includes(currentValue)) {
            this.controls.territory.set_value(currentValue);
        }
    }

    renderMeta() {
        const generated = this.data?.generated_on ? frappe.datetime.str_to_user(this.data.generated_on) : frappe.datetime.now_datetime();
        this.wrapper.find(".snrg-st-meta").html(`
            <span class="snrg-st-chip">Updated: ${frappe.utils.escape_html(generated)}</span>
            <span class="snrg-st-chip">Company: ${frappe.utils.escape_html(this.controls.company.get_value() || "All Companies")}</span>
        `);
    }

    renderSummary() {
        const summary = this.data?.summary || {};
        const creditHoldActive = this.controls.credit_status.get_value() === "Credit Hold";
        const cards = [
            {
                label: "Credit Hold",
                value: frappe.format(summary.credit_hold_count || 0, { fieldtype: "Int" }),
                interactive: true,
                action: creditHoldActive ? "clear-credit-hold" : "credit-hold",
                helper: creditHoldActive ? "Click to clear filter" : "Click to filter table",
            },
            {
                label: "Delivered",
                value: frappe.format(summary.delivery_complete_count || 0, { fieldtype: "Int" }),
                helper: "Rows with overall delivered status",
            },
            {
                label: "POD Complete",
                value: frappe.format(summary.pod_complete_count || 0, { fieldtype: "Int" }),
                helper: "Rows where POD is complete",
            },
        ];

        this.wrapper.find(".snrg-st-summary").html(cards.map((card) => `
            <div class="snrg-st-card snrg-st-summary-card ${card.interactive ? "interactive" : ""}" ${card.action ? `data-summary-action="${card.action}"` : ""}>
                <div class="snrg-st-card-label">${frappe.utils.escape_html(card.label)}</div>
                <div class="snrg-st-card-value">${card.value}</div>
                ${card.helper ? `<div class="snrg-st-muted" style="margin-top:8px;font-size:12px;">${frappe.utils.escape_html(card.helper)}</div>` : ""}
            </div>
        `).join(""));
    }

    renderTable() {
        const rows = this.getVisibleRows();
        const totalRows = this.data?.rows?.length || 0;
        this.wrapper.find(".snrg-st-row-count").text(
            totalRows === rows.length
                ? `${rows.length} row${rows.length === 1 ? "" : "s"}`
                : `${rows.length} of ${totalRows} rows`
        );

        if (!rows.length) {
            this.wrapper.find(".snrg-st-table-container").html(`<div class="snrg-st-empty">No quotations matched the current filters.</div>`);
            return;
        }

        this.columns = this.buildColumns();
        const headerHtml = this.columns.map((column) => `<th>${this.renderHeader(column)}</th>`).join("");
        const bodyHtml = rows.map((row, index) => `
            <tr data-row-index="${index}">
                ${this.columns.map((column) => `<td>${column.render(row)}</td>`).join("")}
            </tr>
        `).join("");
        const footerHtml = this.renderFooter(rows);

        this.wrapper.find(".snrg-st-table-container").html(`
            <table class="snrg-st-table">
                <thead><tr>${headerHtml}</tr></thead>
                <tbody>${bodyHtml}</tbody>
                <tfoot>${footerHtml}</tfoot>
            </table>
        `);
    }

    buildColumns() {
        return [
            { key: "quotation_id", label: "Quotation ID", type: "text", render: (row) => `<a class="snrg-st-link snrg-st-open-quotation">${frappe.utils.escape_html(row.quotation_id)}</a>` },
            { key: "quotation_status", label: "Quotation Status", type: "select", render: (row) => this.statusPill(row.quotation_status) },
            { key: "order_month", label: "Order Month", type: "text", render: (row) => this.escapeCell(row.order_month) },
            { key: "order_date", label: "Order Date", type: "date", render: (row) => this.formatDate(row.order_date) },
            { key: "channel_partner_name", label: "Channel Partner Name", type: "text", render: (row) => this.escapeCell(row.channel_partner_name) },
            { key: "zone", label: "Zone", type: "text", render: (row) => this.escapeCell(row.zone) },
            { key: "city", label: "City", type: "text", render: (row) => this.escapeCell(row.city) },
            { key: "state", label: "State", type: "text", render: (row) => this.escapeCell(row.state) },
            { key: "salesperson_summary", label: "Salesperson", type: "text", render: (row) => row.salespeople?.length ? `<a class="snrg-st-link snrg-st-open-salespeople">${frappe.utils.escape_html(row.salesperson_summary || "")}</a>` : this.emptyCell() },
            { key: "order_value", label: "Order Value", type: "number", render: (row) => this.money(row.order_value, row.currency) },
            { key: "basic_value", label: "Basic Value", type: "number", render: (row) => this.money(row.basic_value, row.currency) },
            { key: "credit_status", label: "Credit Status", type: "select", render: (row) => this.statusPill(row.credit_status) },
            { key: "credit_clearance_date", label: "Credit Clearance Date", type: "date", render: (row) => this.formatDate(row.credit_clearance_date) },
            { key: "delay_reason", label: "Delay Reason", type: "text", render: (row) => this.escapeCell(row.delay_reason) },
            { key: "original_esd", label: "Original ESD", type: "date", render: (row) => this.formatDate(row.original_esd) },
            { key: "sales_order_delivery_date", label: "SO Delivery Date", type: "date", render: (row) => row.sales_orders?.length ? `<a class="snrg-st-link snrg-st-open-sales-orders">${this.formatDate(row.sales_order_delivery_date)}</a>` : this.emptyCell() },
            { key: "latest_ho_remark", label: "Latest HO Remark", type: "text", render: (row) => row.latest_ho_remark ? `<a href="#" class="snrg-st-link snrg-st-open-comments"><span class="snrg-st-remarks">${frappe.utils.escape_html(row.latest_ho_remark)}</span></a>` : this.emptyCell() },
            { key: "invoice_summary", label: "Invoice No", type: "text", render: (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${frappe.utils.escape_html(row.invoice_summary || "")}</a>` : this.emptyCell() },
            { key: "invoice_amount", label: "Invoice Amount", type: "number", render: (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${this.money(row.invoice_amount, row.currency)}</a>` : this.emptyCell() },
            { key: "invoice_date", label: "Invoice Date", type: "date", render: (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${this.formatDate(row.invoice_date)}</a>` : this.emptyCell() },
            { key: "shortage_amount", label: "Shortage Details", type: "number", render: (row) => this.money(row.shortage_amount, row.currency) },
            { key: "dispatch_date", label: "Dispatch Date", type: "date", render: (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${this.formatDate(row.dispatch_date)}</a>` : this.emptyCell() },
            { key: "no_of_cartons", label: "No. of Cartons", type: "number", render: (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${frappe.format(row.no_of_cartons || 0, { fieldtype: "Int" })}</a>` : this.emptyCell() },
            { key: "transport_name", label: "Transport Name", type: "text", render: (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${frappe.utils.escape_html(row.transport_name || "-")}</a>` : this.emptyCell() },
            { key: "tracking_details", label: "Tracking Details", type: "text", render: (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${frappe.utils.escape_html(row.tracking_details || "-")}</a>` : this.emptyCell() },
            { key: "delivery_status_overall", label: "Delivery Status", type: "select", render: (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${this.statusPill(row.delivery_status_overall)}</a>` : this.statusPill("Pending") },
            { key: "delivery_date", label: "Delivery Date", type: "date", render: (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${this.formatDate(row.delivery_date)}</a>` : this.emptyCell() },
            { key: "pod_status", label: "POD Received", type: "select", render: (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${this.statusPill(row.pod_status)}</a>` : this.statusPill("Pending") },
            { key: "remarks", label: "Remarks", type: "text", render: (row) => row.remarks ? `<a class="snrg-st-link snrg-st-open-invoices"><span class="snrg-st-remarks">${frappe.utils.escape_html(row.remarks)}</span></a>` : this.emptyCell() },
        ];
    }

    renderHeader(column) {
        const isSorted = this.sortState.key === column.key;
        const sortIndicator = !isSorted
            ? "↕"
            : (this.sortState.direction === "asc" ? "↑" : "↓");
        const hasFilter = !!this.columnFilters[column.key];

        return `
            <div class="snrg-st-th-content">
                <div class="snrg-st-th-main">
                    <span class="snrg-st-th-label snrg-st-sort-toggle" data-column-key="${frappe.utils.escape_html(column.key)}">${frappe.utils.escape_html(column.label)}</span>
                    <span class="snrg-st-th-sort">${sortIndicator}</span>
                </div>
                <div class="snrg-st-th-actions">
                    <button class="snrg-st-th-btn snrg-st-filter-toggle ${hasFilter ? "active" : ""}" data-column-key="${frappe.utils.escape_html(column.key)}" title="Filter">⏷</button>
                </div>
            </div>
        `;
    }

    getVisibleRows() {
        const sourceRows = [...(this.data?.rows || [])];
        const filteredRows = sourceRows.filter((row) => this.rowMatchesFilters(row));
        return this.applySort(filteredRows);
    }

    renderFooter(rows) {
        const totals = this.getFooterTotals(rows);
        const footerCells = this.columns.map((column, index) => {
            if (index === 0) {
                return `<td>Total (${frappe.format(rows.length || 0, { fieldtype: "Int" })} rows)</td>`;
            }

            if (column.key === "order_value") {
                return `<td>${this.money(totals.order_value, totals.currency)}</td>`;
            }
            if (column.key === "basic_value") {
                return `<td>${this.money(totals.basic_value, totals.currency)}</td>`;
            }
            if (column.key === "invoice_amount") {
                return `<td>${this.money(totals.invoice_amount, totals.currency)}</td>`;
            }
            if (column.key === "shortage_amount") {
                return `<td>${this.money(totals.shortage_amount, totals.currency)}</td>`;
            }
            if (column.key === "no_of_cartons") {
                return `<td>${frappe.format(totals.no_of_cartons || 0, { fieldtype: "Int" })}</td>`;
            }
            if (column.key === "credit_status") {
                return `<td>${frappe.format(totals.credit_hold_count || 0, { fieldtype: "Int" })} hold</td>`;
            }
            if (column.key === "delivery_status_overall") {
                return `<td>${frappe.format(totals.delivery_complete_count || 0, { fieldtype: "Int" })} delivered</td>`;
            }
            if (column.key === "pod_status") {
                return `<td>${frappe.format(totals.pod_complete_count || 0, { fieldtype: "Int" })} complete</td>`;
            }
            return `<td></td>`;
        }).join("");

        return `<tr>${footerCells}</tr>`;
    }

    getFooterTotals(rows) {
        return rows.reduce((accumulator, row) => {
            accumulator.order_value += Number(row.order_value || 0);
            accumulator.basic_value += Number(row.basic_value || 0);
            accumulator.invoice_amount += Number(row.invoice_amount || 0);
            accumulator.shortage_amount += Number(row.shortage_amount || 0);
            accumulator.no_of_cartons += Number(row.no_of_cartons || 0);
            if (row.credit_status === "Credit Hold") {
                accumulator.credit_hold_count += 1;
            }
            if (row.delivery_status_overall === "Delivered") {
                accumulator.delivery_complete_count += 1;
            }
            if (row.pod_status === "Complete") {
                accumulator.pod_complete_count += 1;
            }
            if (!accumulator.currency && row.currency) {
                accumulator.currency = row.currency;
            }
            return accumulator;
        }, {
            order_value: 0,
            basic_value: 0,
            invoice_amount: 0,
            shortage_amount: 0,
            no_of_cartons: 0,
            credit_hold_count: 0,
            delivery_complete_count: 0,
            pod_complete_count: 0,
            currency: "INR",
        });
    }

    rowMatchesFilters(row) {
        return Object.entries(this.columnFilters).every(([key, value]) => {
            if (value === null || value === undefined || value === "") {
                return true;
            }

            const rawValue = row[key];
            if (Array.isArray(value)) {
                return value.includes(rawValue || "");
            }

            const normalizedNeedle = String(value).trim().toLowerCase();
            if (!normalizedNeedle) {
                return true;
            }

            return String(rawValue || "").toLowerCase().includes(normalizedNeedle);
        });
    }

    applySort(rows) {
        const { key, direction } = this.sortState;
        if (!key || !direction) {
            return rows;
        }

        const column = this.columns.find((entry) => entry.key === key) || this.buildColumns().find((entry) => entry.key === key);
        const multiplier = direction === "asc" ? 1 : -1;
        return [...rows].sort((left, right) => multiplier * this.compareValues(left[key], right[key], column?.type));
    }

    compareValues(left, right, type) {
        if (type === "number") {
            return (Number(left || 0) - Number(right || 0));
        }
        if (type === "date") {
            const leftDate = left ? new Date(left).getTime() : 0;
            const rightDate = right ? new Date(right).getTime() : 0;
            return leftDate - rightDate;
        }
        return String(left || "").localeCompare(String(right || ""), undefined, { sensitivity: "base" });
    }

    toggleSort(key) {
        if (this.sortState.key !== key) {
            this.sortState = { key, direction: "asc" };
        } else if (this.sortState.direction === "asc") {
            this.sortState = { key, direction: "desc" };
        } else if (this.sortState.direction === "desc") {
            this.sortState = { key: null, direction: null };
        } else {
            this.sortState = { key, direction: "asc" };
        }
        this.renderTable();
    }

    openColumnFilter(key) {
        const column = this.columns.find((entry) => entry.key === key) || this.buildColumns().find((entry) => entry.key === key);
        if (!column) return;

        const currentValue = this.columnFilters[key] || "";
        const fields = [];

        if (column.type === "select") {
            const options = this.getUniqueColumnValues(key).filter(Boolean);
            fields.push({
                fieldtype: "Select",
                fieldname: "filter_value",
                label: column.label,
                options: ["", ...options].join("\n"),
                default: currentValue,
            });
        } else {
            fields.push({
                fieldtype: "Data",
                fieldname: "filter_value",
                label: `${column.label} contains`,
                default: currentValue,
            });
        }

        const dialog = new frappe.ui.Dialog({
            title: `Filter · ${column.label}`,
            fields,
            primary_action_label: "Apply",
            primary_action: (values) => {
                const nextValue = values.filter_value || "";
                if (nextValue) {
                    this.columnFilters[key] = nextValue;
                } else {
                    delete this.columnFilters[key];
                }
                dialog.hide();
                this.renderTable();
            },
            secondary_action_label: "Clear",
            secondary_action: () => {
                delete this.columnFilters[key];
                dialog.hide();
                this.renderTable();
            },
        });

        dialog.show();
    }

    getUniqueColumnValues(key) {
        const values = new Set();
        (this.data?.rows || []).forEach((row) => {
            if (row[key]) {
                values.add(String(row[key]));
            }
        });
        return [...values].sort((left, right) => left.localeCompare(right, undefined, { sensitivity: "base" }));
    }

    showInvoicesDialog(row) {
        const invoices = row.invoice_details || [];
        const dialog = new frappe.ui.Dialog({
            title: `Invoices · ${row.quotation_id}`,
            size: "extra-large",
            fields: [{ fieldtype: "HTML", fieldname: "content" }],
        });

        const html = invoices.length ? `
            <div style="overflow:auto;">
                <table class="table table-bordered" style="margin:0;">
                    <thead>
                        <tr>
                            <th>Invoice</th>
                            <th>Date</th>
                            <th>Amount</th>
                            <th>Shipping Date</th>
                            <th>AWB</th>
                            <th>Cartons</th>
                            <th>Transporter</th>
                            <th>Delivery Status</th>
                            <th>Delivery Date</th>
                            <th>POD</th>
                            <th>Remarks</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${invoices.map((invoice) => `
                            <tr>
                                <td><a href="/app/sales-invoice/${encodeURIComponent(invoice.name)}">${frappe.utils.escape_html(invoice.name)}</a></td>
                                <td>${this.formatDate(invoice.posting_date)}</td>
                                <td>${this.money(invoice.grand_total, invoice.currency || row.currency)}</td>
                                <td>${this.formatDate(invoice.shipping_date)}</td>
                                <td>${this.escapeCell(invoice.awb_number)}</td>
                                <td>${frappe.format(invoice.no_of_cartons || 0, { fieldtype: "Int" })}</td>
                                <td>${this.escapeCell(invoice.transporter)}</td>
                                <td>${this.escapeCell(invoice.delivery_status || "Pending")}</td>
                                <td>${this.formatDate(invoice.delivery_date)}</td>
                                <td>${invoice.pod_received ? "Yes" : "No"}</td>
                                <td>${this.escapeCell(invoice.dispatch_delivery_remarks)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        ` : `<div class="snrg-st-empty" style="margin:0;">No invoices linked yet.</div>`;

        dialog.fields_dict.content.$wrapper.html(html);
        dialog.show();
    }

    showSalespeopleDialog(row) {
        const salespeople = row.salespeople || [];
        const dialog = new frappe.ui.Dialog({
            title: `Sales Team · ${row.quotation_id}`,
            fields: [{ fieldtype: "HTML", fieldname: "content" }],
        });

        const html = salespeople.length ? `
            <div style="overflow:auto;">
                <table class="table table-bordered" style="margin:0;">
                    <thead><tr><th>Salesperson</th><th>Allocation %</th></tr></thead>
                    <tbody>
                        ${salespeople.map((entry) => `
                            <tr>
                                <td>${this.escapeCell(entry.salesperson)}</td>
                                <td>${frappe.format(entry.allocated_percentage || 0, { fieldtype: "Percent", precision: 2 })}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        ` : `<div class="snrg-st-empty" style="margin:0;">No sales team rows found.</div>`;

        dialog.fields_dict.content.$wrapper.html(html);
        dialog.show();
    }

    showSalesOrdersDialog(row) {
        const salesOrders = row.sales_orders || [];
        const dialog = new frappe.ui.Dialog({
            title: `Sales Orders · ${row.quotation_id}`,
            size: "large",
            fields: [{ fieldtype: "HTML", fieldname: "content" }],
        });

        const html = salesOrders.length ? `
            <div style="overflow:auto;">
                <table class="table table-bordered" style="margin:0;">
                    <thead>
                        <tr>
                            <th>Sales Order</th>
                            <th>Date</th>
                            <th>Delivery Date</th>
                            <th>Amount</th>
                            <th>Status</th>
                            <th>Credit Status</th>
                            <th>Credit Clearance Date</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${salesOrders.map((salesOrder) => `
                            <tr>
                                <td><a href="/app/sales-order/${encodeURIComponent(salesOrder.name)}">${frappe.utils.escape_html(salesOrder.name)}</a></td>
                                <td>${this.formatDate(salesOrder.transaction_date)}</td>
                                <td>${this.formatDate(salesOrder.delivery_date)}</td>
                                <td>${this.money(salesOrder.grand_total, row.currency)}</td>
                                <td>${this.escapeCell(salesOrder.status)}</td>
                                <td>${this.escapeCell(salesOrder.credit_status || "-")}</td>
                                <td>${this.formatDate(salesOrder.credit_clearance_date)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        ` : `<div class="snrg-st-empty" style="margin:0;">No sales orders linked yet.</div>`;

        dialog.fields_dict.content.$wrapper.html(html);
        dialog.show();
    }

    money(value, currency) {
        return format_currency(value || 0, currency || "INR");
    }

    formatDate(value) {
        if (!value) {
            return this.emptyCell();
        }
        return frappe.datetime.str_to_user(value);
    }

    statusPill(value) {
        const label = value || "Pending";
        const tone = {
            "Credit Hold": "red",
            "Credit OK": "green",
            "Mixed": "amber",
            "Draft": "amber",
            "Submitted": "blue",
            "Cancelled": "red",
            "Pending": "amber",
            "Partially Delivered": "amber",
            "Partial": "amber",
            "Delivered": "green",
            "Complete": "green",
            "In Transit": "blue",
            "Hold": "red",
        }[label] || "slate";
        return `<span class="snrg-st-pill ${tone}">${frappe.utils.escape_html(label)}</span>`;
    }

    emptyCell() {
        return `<span class="snrg-st-muted">-</span>`;
    }

    escapeCell(value) {
        return value ? frappe.utils.escape_html(String(value)) : this.emptyCell();
    }
}
