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
        this.kpiFilters = {};
        this.columns = [];
        this.suppressFilterRefresh = false;
        this.savedViews = [];
        this.activeSavedView = "";

        this.setup();
    }

    setup() {
        this.page.set_primary_action("Refresh", () => this.refresh(), "refresh");
        this.page.set_secondary_action("Export", () => this.exportTrackerView(), "download");
        this.render_shell();
        this.make_filters();
        this.bind_events();
        this.loadSavedViews();
        this.refresh();
    }

    render_shell() {
        this.wrapper.find(".layout-main-section").html(`
            <style>
                .snrg-st-page { display:flex; flex-direction:column; gap:10px; color:#10253f; }
                .snrg-st-page-header-meta {
                    display:inline-flex; align-items:center; margin-left:10px; vertical-align:middle;
                }
                .snrg-st-filter-panel {
                    border-radius:12px; border:1px solid #dde5f0; background:#fff;
                    box-shadow:none; padding:8px 10px 10px;
                }
                .snrg-st-chip {
                    display:inline-flex; align-items:center; gap:6px; padding:5px 9px; border-radius:999px;
                    background:#f8fafc; border:1px solid #dbe3ef; font-size:11px; color:#334155; font-weight:600;
                }
                .snrg-st-control-strip {
                    display:grid;
                    grid-template-columns:minmax(96px,.85fr) minmax(104px,.85fr) minmax(118px,.9fr) minmax(104px,.85fr) minmax(104px,.85fr) minmax(128px,1fr) minmax(128px,1fr) auto;
                    gap:5px;
                    align-items:end;
                }
                .snrg-st-filter-slot {
                    width: 100%;
                }
                .snrg-st-saved-view-filter { min-width: 0; }
                .snrg-st-view-actions {
                    display:flex; gap:4px; flex-wrap:nowrap; align-items:flex-end; justify-content:flex-end;
                    min-width:0;
                }
                .snrg-st-btn {
                    display:inline-flex; align-items:center; justify-content:center; gap:6px;
                    padding:5px 7px; border-radius:6px; border:1px solid #cbd5e1;
                    background:#fff; color:#0f172a; font-size:10px; font-weight:700; cursor:pointer;
                    min-height:28px; white-space:nowrap;
                }
                .snrg-st-btn:hover { background:#f8fafc; border-color:#94a3b8; }
                .snrg-st-control-strip .frappe-control {
                    margin-bottom: 0;
                    padding: 3px 5px 4px;
                    border: 1px solid #dde5f0;
                    border-radius: 6px;
                    background: #fff;
                    box-shadow: none;
                    min-height: 48px;
                }
                .snrg-st-control-strip .frappe-control .control-label {
                    font-size: 10px;
                    font-weight: 700;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: .08em;
                    margin-bottom: 2px;
                }
                .snrg-st-control-strip .frappe-control input,
                .snrg-st-control-strip .frappe-control .input-with-feedback,
                .snrg-st-control-strip .frappe-control .link-field,
                .snrg-st-control-strip .frappe-control select {
                    min-height: 26px;
                    border-radius: 5px;
                    border: 1px solid #dbe3ef;
                    background: #fff;
                    font-size: 10px;
                }
                .snrg-st-summary {
                    display:grid;
                    grid-template-columns:repeat(5, minmax(0, 1fr));
                    gap:6px;
                    align-items:start;
                }
                .snrg-st-card {
                    border-radius:8px; padding:7px 8px; border:1px solid #dde5f0;
                    background:#fff; box-shadow:none; min-height:100%;
                }
                .snrg-st-card-label { font-size:9px; color:#5b7088; text-transform:uppercase; letter-spacing:.08em; font-weight:700; }
                .snrg-st-card-grid {
                    margin-top: 5px;
                    display: grid;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    gap: 4px;
                }
                .snrg-st-mini-stat {
                    border: 1px solid #e3eaf3;
                    border-radius: 6px;
                    padding: 4px 6px;
                    background: #fafcff;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 5px;
                    min-height: 32px;
                }
                .snrg-st-mini-stat.interactive { cursor:pointer; }
                .snrg-st-mini-stat.active {
                    border-color:#0f766e;
                    background:#eefbf9;
                    box-shadow:none;
                }
                .snrg-st-mini-stat-label {
                    font-size: 9px;
                    color: #64748b;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: .04em;
                }
                .snrg-st-mini-stat-value {
                    font-size: 12px;
                    font-weight: 800;
                    color: #0f172a;
                }
                .snrg-st-table-shell {
                    border-radius:10px; border:1px solid #dde5f0; background:#fff;
                    box-shadow:none; overflow:hidden;
                }
                .snrg-st-table-toolbar {
                    display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap; padding:8px 10px;
                    border-bottom:1px solid #e2e8f0; background:#fbfcfe;
                }
                .snrg-st-toolbar-actions { display:flex; gap:8px; flex-wrap:wrap; }
                .snrg-st-table-wrap {
                    overflow: auto;
                    max-height: calc(100vh - 190px);
                }
                .snrg-st-table { width:100%; min-width:1900px; border-collapse:separate; border-spacing:0; }
                .snrg-st-table th {
                    position:sticky; top:0; z-index:3; background:#f8fafc; border-bottom:1px solid #e2e8f0;
                    font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:#64748b; text-align:left;
                    padding:8px 10px; white-space:nowrap;
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
                    padding:7px 10px; border-bottom:1px solid #edf2f7; font-size:12px; line-height:1.3; vertical-align:top;
                    color:#1e293b;
                }
                .snrg-st-table tfoot td {
                    position: sticky;
                    bottom: 0;
                    z-index: 2;
                    background: #f8fafc;
                    border-top: 2px solid #cbd5e1;
                    font-size: 10px;
                    font-weight: 800;
                    color: #0f172a;
                    box-shadow: inset 0 1px 0 #e2e8f0;
                }
                .snrg-st-table tr:hover td { background:#fcfdff; }
                .snrg-st-link { color:#0f766e; font-weight:700; text-decoration:none; cursor:pointer; }
                .snrg-st-link:hover { text-decoration:underline; }
                .snrg-st-muted { color:#64748b; }
                .snrg-st-pill {
                    display:inline-flex; align-items:center; padding:3px 8px; border-radius:999px;
                    font-size:10px; font-weight:700; border:1px solid #dbe3ef; background:#f8fafc; color:#334155;
                }
                .snrg-st-pill.red { background:#fef2f2; border-color:#fecaca; color:#b91c1c; }
                .snrg-st-pill.green { background:#ecfdf5; border-color:#bbf7d0; color:#047857; }
                .snrg-st-pill.amber { background:#fffbeb; border-color:#fcd34d; color:#b45309; }
                .snrg-st-pill.blue { background:#eff6ff; border-color:#bfdbfe; color:#1d4ed8; }
                .snrg-st-pill.slate { background:#f8fafc; border-color:#cbd5e1; color:#475569; }
                .snrg-st-pill.interactive { cursor:pointer; }
                .snrg-st-empty {
                    padding:28px 16px; text-align:center; color:#64748b; font-size:13px; border:1px dashed #cbd5e1;
                    border-radius:18px; background:#f8fafc; margin:16px;
                }
                .snrg-st-cell-lines { display:flex; flex-direction:column; gap:2px; min-width:0; }
                .snrg-st-cell-lines .secondary { color:#64748b; font-size:10px; }
                .snrg-st-sla-cell {
                    display:flex; align-items:center; gap:6px; flex-wrap:wrap; min-width:0;
                }
                .snrg-st-sla-days {
                    font-weight:600; color:#334155; white-space:nowrap; line-height:1;
                }
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
                @media (max-width: 1500px) {
                    .snrg-st-control-strip { grid-template-columns:repeat(4, minmax(0, 1fr)); }
                    .snrg-st-view-actions { justify-content:flex-start; flex-wrap:wrap; }
                    .snrg-st-summary { grid-template-columns:repeat(3, minmax(0, 1fr)); }
                }
                @media (max-width: 1180px) {
                    .snrg-st-control-strip, .snrg-st-summary { grid-template-columns:repeat(2, minmax(0, 1fr)); }
                    .snrg-st-table-wrap { max-height: calc(100vh - 190px); }
                }
                @media (max-width: 768px) {
                    .snrg-st-control-strip, .snrg-st-summary, .snrg-st-card-grid { grid-template-columns:1fr; }
                    .snrg-st-filter-title h2 { font-size:18px; }
                    .snrg-st-view-actions { justify-content:flex-start; flex-wrap:wrap; }
                }
            </style>
            <div class="snrg-st-page">
                <section class="snrg-st-filter-panel">
                    <div class="snrg-st-control-strip">
                        <div class="snrg-st-filter-slot snrg-st-company-filter"></div>
                        <div class="snrg-st-filter-slot snrg-st-month-filter"></div>
                        <div class="snrg-st-filter-slot snrg-st-date-range-filter"></div>
                        <div class="snrg-st-filter-slot snrg-st-territory-filter"></div>
                        <div class="snrg-st-filter-slot snrg-st-credit-filter"></div>
                        <div class="snrg-st-filter-slot snrg-st-search-filter"></div>
                        <div class="snrg-st-saved-view-filter"></div>
                        <div class="snrg-st-view-actions">
                            <button class="snrg-st-btn snrg-st-save-view" type="button">Save View</button>
                            <button class="snrg-st-btn snrg-st-save-as-view" type="button">Save As</button>
                            <button class="snrg-st-btn snrg-st-delete-view" type="button">Delete View</button>
                            <button class="snrg-st-btn snrg-st-reset-filters" type="button">Reset</button>
                            <button class="snrg-st-btn snrg-st-export-table" type="button">Export</button>
                        </div>
                    </div>
                </section>
                <section class="snrg-st-summary"></section>
                <section class="snrg-st-table-shell">
                    <div class="snrg-st-table-toolbar">
                        <div class="snrg-st-toolbar-title">
                            <strong>Live Tracker</strong>
                            <span class="snrg-st-muted">Click invoice, shortage, salesperson, SO delivery, or remarks cells for detail.</span>
                        </div>
                        <div class="snrg-st-toolbar-actions">
                            <div class="snrg-st-row-count snrg-st-muted"></div>
                        </div>
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
            change: () => this.handleFilterChange(),
        });

        this.controls.order_month = this.makeFilterControl(".snrg-st-month-filter", {
            label: "Order Month",
            fieldname: "order_month",
            fieldtype: "Select",
            options: "\n",
            change: () => this.handleFilterChange(),
        });

        this.controls.date_range = this.makeFilterControl(".snrg-st-date-range-filter", {
            label: "Date Range",
            fieldname: "date_range",
            fieldtype: "DateRange",
            change: () => this.handleFilterChange(),
        });

        this.controls.territory = this.makeFilterControl(".snrg-st-territory-filter", {
            label: "Zone",
            fieldname: "territory",
            fieldtype: "Select",
            options: "\n",
            change: () => this.handleFilterChange(),
        });

        this.controls.credit_status = this.makeFilterControl(".snrg-st-credit-filter", {
            label: "Credit Status",
            fieldname: "credit_status",
            fieldtype: "Select",
            options: "\nCredit OK\nCredit Hold\nMixed\nNot Run",
            change: () => this.handleFilterChange(),
        });

        this.controls.search = this.makeFilterControl(".snrg-st-search-filter", {
            label: "Search",
            fieldname: "search",
            fieldtype: "Data",
            placeholder: "Quotation / customer",
            change: frappe.utils.debounce(() => this.handleFilterChange(), 350),
        });

        this.controls.saved_view = this.makeFilterControl(".snrg-st-saved-view-filter", {
            label: "Saved View",
            fieldname: "saved_view",
            fieldtype: "Select",
            options: "\n",
            change: () => this.handleSavedViewChange(),
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

    handleFilterChange() {
        if (this.suppressFilterRefresh) return;
        this.refresh();
    }

    handleSavedViewChange() {
        if (this.suppressFilterRefresh) return;
        const docname = this.controls.saved_view.get_value();
        this.activeSavedView = docname || "";
        if (!docname) {
            return;
        }
        const view = this.savedViews.find((entry) => entry.name === docname);
        if (!view?.state) {
            return;
        }
        this.applyViewState(view.state);
    }

    async loadSavedViews() {
        const response = await frappe.call({
            method: "snrg_credit_control.snrg_credit_control.page.sales_tracking.sales_tracking.get_saved_views",
        });
        this.savedViews = response.message || [];
        this.updateSavedViewOptions();
    }

    updateSavedViewOptions() {
        if (!this.controls.saved_view) return;
        const optionLines = [""];
        this.savedViews.forEach((view) => optionLines.push(view.name));
        this.setSelectOptions(this.controls.saved_view, optionLines);
        if (this.activeSavedView && optionLines.includes(this.activeSavedView)) {
            this.suppressFilterRefresh = true;
            try {
                this.controls.saved_view.set_value(this.activeSavedView);
            } finally {
                this.suppressFilterRefresh = false;
            }
        }
    }

    captureViewState() {
        const dateRange = this.controls.date_range.get_value() || [];
        const [from_date, to_date] = Array.isArray(dateRange) ? dateRange : [null, null];
        return {
            topFilters: {
                company: this.controls.company.get_value() || "",
                order_month: this.controls.order_month.get_value() || "",
                from_date: from_date || "",
                to_date: to_date || "",
                territory: this.controls.territory.get_value() || "",
                credit_status: this.controls.credit_status.get_value() || "",
                search: this.controls.search.get_value() || "",
            },
            kpiFilters: { ...this.kpiFilters },
            columnFilters: { ...this.columnFilters },
            sortState: { ...this.sortState },
        };
    }

    async applyViewState(state) {
        if (!state || typeof state !== "object") return;
        const topFilters = state.topFilters || {};

        this.suppressFilterRefresh = true;
        try {
            this.controls.company.set_value(topFilters.company || "");
            this.controls.order_month.set_value(topFilters.order_month || "");
            this.controls.date_range.set_value([
                topFilters.from_date || "",
                topFilters.to_date || "",
            ]);
            this.controls.territory.set_value(topFilters.territory || "");
            this.controls.credit_status.set_value(topFilters.credit_status || "");
            this.controls.search.set_value(topFilters.search || "");
            this.columnFilters = { ...(state.columnFilters || {}) };
            this.sortState = { key: null, direction: null, ...(state.sortState || {}) };
            this.kpiFilters = { ...(state.kpiFilters || {}) };
        } finally {
            this.suppressFilterRefresh = false;
        }

        await this.refresh();
    }

    resetAllFilters() {
        this.suppressFilterRefresh = true;
        try {
            this.controls.company.set_value(frappe.defaults.get_user_default("Company") || "");
            this.controls.order_month.set_value("");
            this.controls.date_range.set_value(["", ""]);
            this.controls.territory.set_value("");
            this.controls.credit_status.set_value("");
            this.controls.search.set_value("");
            this.controls.saved_view.set_value("");
            this.columnFilters = {};
            this.kpiFilters = {};
            this.sortState = { key: null, direction: null };
            this.activeSavedView = "";
        } finally {
            this.suppressFilterRefresh = false;
        }
        this.refresh();
    }

    async saveCurrentView(forceNew) {
        const existing = this.savedViews.find((entry) => entry.name === this.activeSavedView);
        let defaultName = existing?.view_name || "";
        if (forceNew) {
            defaultName = "";
        }

        frappe.prompt(
            [
                {
                    fieldname: "view_name",
                    fieldtype: "Data",
                    label: "View Name",
                    reqd: 1,
                    default: defaultName,
                },
            ],
            async (values) => {
                const response = await frappe.call({
                    method: "snrg_credit_control.snrg_credit_control.page.sales_tracking.sales_tracking.save_saved_view",
                    args: {
                        view_name: values.view_name,
                        state_json: JSON.stringify(this.captureViewState()),
                        docname: forceNew ? "" : (existing?.name || ""),
                    },
                });
                const saved = response.message || {};
                this.activeSavedView = saved.name || values.view_name;
                await this.loadSavedViews();
                frappe.show_alert({ message: "Saved view updated", indicator: "green" });
            },
            forceNew ? "Save View As" : "Save View",
            "Save"
        );
    }

    async deleteCurrentView() {
        const existing = this.savedViews.find((entry) => entry.name === this.activeSavedView);
        if (!existing) {
            frappe.show_alert({ message: "Select a saved view first", indicator: "orange" });
            return;
        }

        frappe.confirm(`Delete saved view ${frappe.utils.escape_html(existing.view_name)}?`, async () => {
            await frappe.call({
                method: "snrg_credit_control.snrg_credit_control.page.sales_tracking.sales_tracking.delete_saved_view",
                args: { docname: existing.name },
            });
            this.activeSavedView = "";
            await this.loadSavedViews();
            this.controls.saved_view.set_value("");
            frappe.show_alert({ message: "Saved view deleted", indicator: "green" });
        });
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

        this.wrapper.on("click", ".snrg-st-open-journey", (event) => {
            event.preventDefault();
            const index = Number($(event.currentTarget).closest("[data-row-index]").data("rowIndex"));
            const row = this.getVisibleRows()[index];
            if (row) {
                this.showJourneyDialog(row);
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

        this.wrapper.on("click", ".snrg-st-open-shortage", (event) => {
            event.preventDefault();
            const index = Number($(event.currentTarget).closest("[data-row-index]").data("rowIndex"));
            const row = this.getVisibleRows()[index];
            if (row) {
                this.showShortageDialog(row);
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
            }
            if (action === "clear-credit-hold") {
                this.controls.credit_status.set_value("");
            }
        });

        this.wrapper.on("click", ".snrg-st-mini-stat[data-kpi-group]", (event) => {
            const target = $(event.currentTarget);
            this.toggleKpiFilter(target.data("kpiGroup"), target.data("kpiValue"));
        });

        this.wrapper.on("click", ".snrg-st-save-view", () => this.saveCurrentView(false));
        this.wrapper.on("click", ".snrg-st-save-as-view", () => this.saveCurrentView(true));
        this.wrapper.on("click", ".snrg-st-delete-view", () => this.deleteCurrentView());
        this.wrapper.on("click", ".snrg-st-reset-filters", () => this.resetAllFilters());
        this.wrapper.on("click", ".snrg-st-export-table", () => this.exportTrackerView());
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

        this.setSelectOptions(this.controls.order_month, optionLines);
    }

    updateTerritoryOptions() {
        if (!this.controls.territory) return;
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

        this.setSelectOptions(this.controls.territory, optionLines);
    }

    setSelectOptions(control, optionLines) {
        if (!control) return;

        const currentValue = control.get_value();
        const nextOptions = optionLines.join("\n");
        const currentOptions = control.df.options || "";
        const hasCurrentValue = currentValue && optionLines.includes(currentValue);

        if (currentOptions === nextOptions && (!currentValue || hasCurrentValue)) {
            return;
        }

        this.suppressFilterRefresh = true;
        try {
            control.df.options = nextOptions;
            control.refresh();

            if (currentValue && hasCurrentValue && control.get_value() !== currentValue) {
                control.set_value(currentValue);
            }
        } finally {
            this.suppressFilterRefresh = false;
        }
    }

    renderMeta() {
        const generated = this.data?.generated_on ? frappe.datetime.str_to_user(this.data.generated_on) : frappe.datetime.now_datetime();
        const chipHtml = `<span class="snrg-st-chip">Updated: ${frappe.utils.escape_html(generated)}</span>`;
        const $pageHeaderMeta = this.page.wrapper.find(".snrg-st-page-header-meta");

        if ($pageHeaderMeta.length) {
            $pageHeaderMeta.html(chipHtml);
            return;
        }

        const $titleText = this.page.wrapper.find(".page-head .title-text, .page-title .title-text").first();
        if ($titleText.length) {
            $titleText.after(`<span class="snrg-st-page-header-meta">${chipHtml}</span>`);
        }
    }

    renderSummary() {
        const rows = this.getVisibleRows();
        const counts = this.getStatusCounts(rows);
        const cards = [
            {
                label: "Quotation Status",
                stats: [
                    { label: "Draft", value: counts.quotationStatus.Draft || 0, group: "quotation_status", key: "Draft" },
                    { label: "Submitted", value: counts.quotationStatus.Submitted || 0, group: "quotation_status", key: "Submitted" },
                    { label: "Cancelled", value: counts.quotationStatus.Cancelled || 0, group: "quotation_status", key: "Cancelled" },
                ],
            },
            {
                label: "Credit Status",
                stats: [
                    { label: "Credit Hold", value: counts.creditStatus["Credit Hold"] || 0, group: "credit_status", key: "Credit Hold" },
                    { label: "Credit OK", value: counts.creditStatus["Credit OK"] || 0, group: "credit_status", key: "Credit OK" },
                    { label: "Mixed", value: counts.creditStatus.Mixed || 0, group: "credit_status", key: "Mixed" },
                ],
            },
            {
                label: "Delivery Status",
                stats: [
                    { label: "Delivered", value: counts.deliveryStatus.Delivered || 0, group: "delivery_status_overall", key: "Delivered" },
                    { label: "Partial", value: counts.deliveryStatus["Partially Delivered"] || 0, group: "delivery_status_overall", key: "Partially Delivered" },
                    { label: "Pending", value: counts.deliveryStatus.Pending || 0, group: "delivery_status_overall", key: "Pending" },
                ],
            },
            {
                label: "POD Status",
                stats: [
                    { label: "Complete", value: counts.podStatus.Complete || 0, group: "pod_status", key: "Complete" },
                    { label: "Partial", value: counts.podStatus.Partial || 0, group: "pod_status", key: "Partial" },
                    { label: "Pending", value: counts.podStatus.Pending || 0, group: "pod_status", key: "Pending" },
                ],
            },
            {
                label: "Breaches",
                stats: [
                    { label: "Overdue ESD", value: counts.exceptions.overdue_esd || 0, group: "exception", key: "overdue_esd" },
                    { label: "Pending Dispatch", value: counts.exceptions.invoice_pending_dispatch || 0, group: "exception", key: "invoice_pending_dispatch" },
                    { label: "Pending POD", value: counts.exceptions.delivered_pending_pod || 0, group: "exception", key: "delivered_pending_pod" },
                    { label: "Hold Breached", value: counts.exceptions.credit_hold_breached || 0, group: "exception", key: "credit_hold_breached" },
                    { label: "No Invoice After SO", value: counts.exceptions.no_invoice_after_so || 0, group: "exception", key: "no_invoice_after_so" },
                ],
            },
        ];

        this.wrapper.find(".snrg-st-summary").html(cards.map((card) => `
            <div class="snrg-st-card snrg-st-summary-card">
                <div class="snrg-st-card-label">${frappe.utils.escape_html(card.label)}</div>
                <div class="snrg-st-card-grid">
                    ${(card.stats || []).map((stat) => `
                        <div
                            class="snrg-st-mini-stat interactive ${this.isKpiFilterActive(stat.group, stat.key) ? "active" : ""}"
                            data-kpi-group="${frappe.utils.escape_html(stat.group || "")}"
                            data-kpi-value="${frappe.utils.escape_html(stat.key || "")}"
                        >
                            <span class="snrg-st-mini-stat-label">${frappe.utils.escape_html(stat.label)}</span>
                            <span class="snrg-st-mini-stat-value">${frappe.format(stat.value || 0, { fieldtype: "Int" })}</span>
                        </div>
                    `).join("")}
                </div>
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
            {
                key: "quotation_id",
                label: "Quotation ID",
                type: "text",
                render: (row) => `
                    <div class="snrg-st-cell-lines">
                        <a class="snrg-st-link snrg-st-open-quotation">${frappe.utils.escape_html(row.quotation_id)}</a>
                        <a href="#" class="snrg-st-link snrg-st-open-journey secondary">View Journey</a>
                    </div>
                `,
            },
            { key: "quotation_status", label: "Quotation Status", type: "select", render: (row) => this.statusPill(row.quotation_status) },
            { key: "current_stage", label: "Current Stage", type: "select", render: (row) => this.statusPill(row.current_stage) },
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
            { key: "quotation_to_credit_clearance_days", label: "Qtn to Credit SLA", type: "number", render: (row) => this.slaCell(row.quotation_to_credit_clearance_days, row.quotation_to_credit_clearance_sla) },
            { key: "quotation_to_delivery_days", label: "Qtn to Delivery SLA", type: "number", render: (row) => this.slaCell(row.quotation_to_delivery_days, row.quotation_to_delivery_sla) },
            { key: "invoice_to_delivery_days", label: "Inv to Delivery SLA", type: "number", render: (row) => this.slaCell(row.invoice_to_delivery_days, row.invoice_to_delivery_sla) },
            { key: "delivery_to_pod_days", label: "Delivery to POD SLA", type: "number", render: (row) => this.slaCell(row.delivery_to_pod_days, row.delivery_to_pod_sla) },
            { key: "credit_hold_age_days", label: "Credit Hold Age", type: "number", render: (row) => this.slaCell(row.credit_hold_age_days, row.credit_hold_age_sla) },
            { key: "esd_delay_days", label: "ESD Delay", type: "number", render: (row) => this.slaCell(row.esd_delay_days, row.esd_delay_sla) },
            { key: "delay_reason", label: "Delay Reason", type: "text", render: (row) => this.escapeCell(row.delay_reason) },
            { key: "original_esd", label: "Original ESD", type: "date", render: (row) => this.formatDate(row.original_esd) },
            { key: "sales_order_delivery_date", label: "SO Delivery Date", type: "date", render: (row) => row.sales_orders?.length ? `<a class="snrg-st-link snrg-st-open-sales-orders">${this.formatDate(row.sales_order_delivery_date)}</a>` : this.emptyCell() },
            { key: "latest_ho_remark", label: "Latest HO Remark", type: "text", render: (row) => row.latest_ho_remark ? `<a href="#" class="snrg-st-link snrg-st-open-comments"><span class="snrg-st-remarks">${frappe.utils.escape_html(row.latest_ho_remark)}</span></a>` : this.emptyCell() },
            { key: "invoice_summary", label: "Invoice No", type: "text", render: (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${frappe.utils.escape_html(row.invoice_summary || "")}</a>` : this.emptyCell() },
            { key: "invoice_amount", label: "Invoice Amount", type: "number", render: (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${this.money(row.invoice_amount, row.currency)}</a>` : this.emptyCell() },
            { key: "invoice_date", label: "Invoice Date", type: "date", render: (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${this.formatDate(row.invoice_date)}</a>` : this.emptyCell() },
            { key: "shortage_amount", label: "Shortage Details", type: "number", render: (row) => Math.abs(Number(row.shortage_amount || 0)) > 0.009 ? `<a href="#" class="snrg-st-link snrg-st-open-shortage">${this.money(row.shortage_amount, row.currency)}</a>` : this.money(row.shortage_amount, row.currency) },
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

    getStatusCounts(rows) {
        const counts = {
            quotationStatus: {},
            creditStatus: {},
            deliveryStatus: {},
            podStatus: {},
            exceptions: {
                overdue_esd: 0,
                invoice_pending_dispatch: 0,
                delivered_pending_pod: 0,
                credit_hold_breached: 0,
                no_invoice_after_so: 0,
            },
        };

        rows.forEach((row) => {
            counts.quotationStatus[row.quotation_status || "Unknown"] = (counts.quotationStatus[row.quotation_status || "Unknown"] || 0) + 1;
            counts.creditStatus[row.credit_status || "Unknown"] = (counts.creditStatus[row.credit_status || "Unknown"] || 0) + 1;
            counts.deliveryStatus[row.delivery_status_overall || "Unknown"] = (counts.deliveryStatus[row.delivery_status_overall || "Unknown"] || 0) + 1;
            counts.podStatus[row.pod_status || "Unknown"] = (counts.podStatus[row.pod_status || "Unknown"] || 0) + 1;
            if (row.exception_overdue_esd) counts.exceptions.overdue_esd += 1;
            if (row.exception_invoice_pending_dispatch) counts.exceptions.invoice_pending_dispatch += 1;
            if (row.exception_delivered_pending_pod) counts.exceptions.delivered_pending_pod += 1;
            if (row.exception_credit_hold_breached) counts.exceptions.credit_hold_breached += 1;
            if (row.exception_no_invoice_after_so) counts.exceptions.no_invoice_after_so += 1;
        });

        return counts;
    }

    rowMatchesFilters(row) {
        return this.rowMatchesKpiFilters(row) && Object.entries(this.columnFilters).every(([key, value]) => {
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

    rowMatchesKpiFilters(row) {
        return Object.entries(this.kpiFilters).every(([group, value]) => {
            if (!value) return true;
            if (group === "exception") {
                return Boolean(row[`exception_${value}`]);
            }
            return String(row[group] || "") === String(value);
        });
    }

    isKpiFilterActive(group, value) {
        return this.kpiFilters[group] === value;
    }

    toggleKpiFilter(group, value) {
        if (!group || !value) return;
        if (this.kpiFilters[group] === value) {
            delete this.kpiFilters[group];
        } else {
            this.kpiFilters[group] = value;
        }
        this.renderSummary();
        this.renderTable();
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

    exportTrackerView() {
        const rows = this.getVisibleRows();
        const columns = this.buildColumns().map((column) => ({
            label: column.label,
            value: (row) => this.getExportValue(column.key, row),
        }));
        this.downloadCsv("sales_tracking_export.csv", columns, rows);
    }

    getExportValue(key, row) {
        const mapping = {
            quotation_id: row.quotation_id,
            quotation_status: row.quotation_status,
            current_stage: row.current_stage,
            order_month: row.order_month,
            order_date: row.order_date,
            channel_partner_name: row.channel_partner_name,
            zone: row.zone,
            city: row.city,
            state: row.state,
            salesperson_summary: row.salesperson_summary,
            order_value: row.order_value,
            basic_value: row.basic_value,
            credit_status: row.credit_status,
            credit_clearance_date: row.credit_clearance_date,
            quotation_to_credit_clearance_days: this.slaExport(row.quotation_to_credit_clearance_days, row.quotation_to_credit_clearance_sla),
            quotation_to_delivery_days: this.slaExport(row.quotation_to_delivery_days, row.quotation_to_delivery_sla),
            invoice_to_delivery_days: this.slaExport(row.invoice_to_delivery_days, row.invoice_to_delivery_sla),
            delivery_to_pod_days: this.slaExport(row.delivery_to_pod_days, row.delivery_to_pod_sla),
            credit_hold_age_days: this.slaExport(row.credit_hold_age_days, row.credit_hold_age_sla),
            esd_delay_days: this.slaExport(row.esd_delay_days, row.esd_delay_sla),
            delay_reason: row.delay_reason,
            original_esd: row.original_esd,
            sales_order_delivery_date: row.sales_order_delivery_date,
            latest_ho_remark: row.latest_ho_remark,
            invoice_summary: row.invoice_summary,
            invoice_amount: row.invoice_amount,
            invoice_date: row.invoice_date,
            shortage_amount: row.shortage_amount,
            dispatch_date: row.dispatch_date,
            no_of_cartons: row.no_of_cartons,
            transport_name: row.transport_name,
            tracking_details: row.tracking_details,
            delivery_status_overall: row.delivery_status_overall,
            delivery_date: row.delivery_date,
            pod_status: row.pod_status,
            remarks: row.remarks,
        };
        return mapping[key] ?? row[key] ?? "";
    }

    slaExport(days, status) {
        if (!days && status === "Pending") {
            return "";
        }
        return `${days || 0}d ${status || ""}`.trim();
    }

    downloadCsv(filename, columns, rows) {
        const escape = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
        const lines = [
            columns.map((column) => escape(column.label)).join(","),
            ...rows.map((row) => columns.map((column) => escape(column.value(row))).join(",")),
        ];
        const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = filename;
        anchor.click();
        URL.revokeObjectURL(url);
    }

    showJourneyDialog(row) {
        const dialog = new frappe.ui.Dialog({
            title: `Journey · ${row.quotation_id}`,
            size: "extra-large",
            fields: [{ fieldtype: "HTML", fieldname: "content" }],
        });

        const html = `
            <div style="display:flex;flex-direction:column;gap:16px;">
                <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;">
                    ${this.renderJourneyStat("Stage", row.current_stage)}
                    ${this.renderJourneyStat("Credit Status", row.credit_status)}
                    ${this.renderJourneyStat("Delivery Status", row.delivery_status_overall)}
                    ${this.renderJourneyStat("POD Status", row.pod_status)}
                    ${this.renderJourneyStat("Quotation to Credit", this.slaExport(row.quotation_to_credit_clearance_days, row.quotation_to_credit_clearance_sla))}
                    ${this.renderJourneyStat("Quotation to Delivery", this.slaExport(row.quotation_to_delivery_days, row.quotation_to_delivery_sla))}
                    ${this.renderJourneyStat("Invoice to Delivery", this.slaExport(row.invoice_to_delivery_days, row.invoice_to_delivery_sla))}
                    ${this.renderJourneyStat("Delivery to POD", this.slaExport(row.delivery_to_pod_days, row.delivery_to_pod_sla))}
                </div>
                <div>
                    <h5 style="margin:0 0 8px;">Quotation Summary</h5>
                    <table class="table table-bordered" style="margin:0;">
                        <tbody>
                            <tr><th>Customer</th><td>${this.escapeText(row.channel_partner_name)}</td><th>Order Value</th><td>${this.money(row.order_value, row.currency)}</td></tr>
                            <tr><th>Original ESD</th><td>${this.textOrDash(row.original_esd)}</td><th>Credit Clearance Date</th><td>${this.textOrDash(row.credit_clearance_date)}</td></tr>
                            <tr><th>Latest HO Remark</th><td colspan="3">${this.escapeText(row.latest_ho_remark || "-")}</td></tr>
                        </tbody>
                    </table>
                </div>
                <div>
                    <h5 style="margin:0 0 8px;">Sales Orders</h5>
                    ${this.renderSalesOrdersTable(row)}
                </div>
                <div>
                    <h5 style="margin:0 0 8px;">Invoices</h5>
                    ${this.renderInvoicesTable(row)}
                </div>
            </div>
        `;

        dialog.fields_dict.content.$wrapper.html(html);
        dialog.show();
    }

    renderJourneyStat(label, value) {
        return `
            <div style="border:1px solid #e2e8f0;border-radius:12px;padding:10px 12px;background:#f8fafc;">
                <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.08em;">${frappe.utils.escape_html(label)}</div>
                <div style="margin-top:6px;font-size:14px;font-weight:800;color:#0f172a;">${frappe.utils.escape_html(String(value || "-"))}</div>
            </div>
        `;
    }

    renderInvoicesTable(row) {
        const invoices = row.invoice_details || [];
        if (!invoices.length) {
            return `<div class="snrg-st-empty" style="margin:0;">No invoices linked yet.</div>`;
        }
        return `
            <div style="overflow:auto;">
                <table class="table table-bordered" style="margin:0;">
                    <thead>
                        <tr>
                            <th>Invoice</th>
                            <th>Date</th>
                            <th>Amount</th>
                            <th>Dispatch</th>
                            <th>Delivery</th>
                            <th>POD</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${invoices.map((invoice) => `
                            <tr>
                                <td><a href="/app/sales-invoice/${encodeURIComponent(invoice.name)}">${frappe.utils.escape_html(invoice.name)}</a></td>
                                <td>${this.textOrDash(invoice.posting_date)}</td>
                                <td>${this.money(invoice.grand_total, invoice.currency || row.currency)}</td>
                                <td>${this.textOrDash(invoice.shipping_date)}</td>
                                <td>${this.textOrDash(invoice.delivery_date)}</td>
                                <td>${invoice.pod_received ? this.textOrDash(invoice.pod_received_date || "Yes") : "Pending"}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        `;
    }

    renderSalesOrdersTable(row) {
        const salesOrders = row.sales_orders || [];
        if (!salesOrders.length) {
            return `<div class="snrg-st-empty" style="margin:0;">No sales orders linked yet.</div>`;
        }
        return `
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
                        </tr>
                    </thead>
                    <tbody>
                        ${salesOrders.map((salesOrder) => `
                            <tr>
                                <td><a href="/app/sales-order/${encodeURIComponent(salesOrder.name)}">${frappe.utils.escape_html(salesOrder.name)}</a></td>
                                <td>${this.textOrDash(salesOrder.transaction_date)}</td>
                                <td>${this.textOrDash(salesOrder.delivery_date)}</td>
                                <td>${this.money(salesOrder.grand_total, row.currency)}</td>
                                <td>${this.escapeText(salesOrder.status)}</td>
                                <td>${this.escapeText(salesOrder.credit_status || "-")}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        `;
    }

    async showShortageDialog(row) {
        const response = await frappe.call({
            method: "snrg_credit_control.snrg_credit_control.page.sales_tracking.sales_tracking.get_shortage_details",
            args: { quotation_id: row.quotation_id },
        });
        const payload = response.message || {};
        const shortageRows = payload.rows || [];
        const currency = payload.currency || row.currency || "INR";
        const dialog = new frappe.ui.Dialog({
            title: `Pending Items · ${row.quotation_id}`,
            size: "extra-large",
            fields: [{ fieldtype: "HTML", fieldname: "content" }],
            primary_action_label: "Export CSV",
            primary_action: () => {
                this.downloadCsv(
                    `${row.quotation_id}_pending_items.csv`,
                    [
                        { label: "Item Code", value: (entry) => entry.item_code || "" },
                        { label: "Item Name", value: (entry) => entry.item_name || "" },
                        { label: "Quotation Qty", value: (entry) => entry.quotation_qty || 0 },
                        { label: "Invoiced Qty", value: (entry) => entry.invoiced_qty || 0 },
                        { label: "Pending Qty", value: (entry) => entry.pending_qty || 0 },
                        { label: "Quotation Value", value: (entry) => entry.quotation_value || 0 },
                        { label: "Invoiced Value", value: (entry) => entry.invoiced_value || 0 },
                        { label: "Pending Value", value: (entry) => entry.pending_value || 0 },
                    ],
                    shortageRows
                );
            },
        });

        const html = shortageRows.length ? `
            <div style="overflow:auto;">
                <table class="table table-bordered" style="margin:0;">
                    <thead>
                        <tr>
                            <th>Item Code</th>
                            <th>Item Name</th>
                            <th>Quotation Qty</th>
                            <th>Invoiced Qty</th>
                            <th>Pending Qty</th>
                            <th>Pending Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${shortageRows.map((entry) => `
                            <tr>
                                <td>${this.escapeText(entry.item_code || "-")}</td>
                                <td>${this.escapeText(entry.item_name || "-")}</td>
                                <td>${frappe.format(entry.quotation_qty || 0, { fieldtype: "Float", precision: 2 })}</td>
                                <td>${frappe.format(entry.invoiced_qty || 0, { fieldtype: "Float", precision: 2 })}</td>
                                <td>${frappe.format(entry.pending_qty || 0, { fieldtype: "Float", precision: 2 })}</td>
                                <td>${this.money(entry.pending_value || 0, currency)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        ` : `<div class="snrg-st-empty" style="margin:0;">No pending items remaining for this quotation.</div>`;

        dialog.fields_dict.content.$wrapper.html(html);
        dialog.show();
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
                            <th>POD Date</th>
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
                                <td>${this.formatDate(invoice.pod_received_date)}</td>
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

    textOrDash(value) {
        return value ? frappe.utils.escape_html(String(value)) : "-";
    }

    escapeText(value) {
        return frappe.utils.escape_html(String(value || ""));
    }

    slaCell(days, status) {
        if ((!days && !status) || status === "Pending") {
            return this.emptyCell();
        }
        return `
            <div class="snrg-st-sla-cell">
                <span class="snrg-st-sla-days">${frappe.format(days || 0, { fieldtype: "Int" })}d</span>
                <span>${this.statusPill(status)}</span>
            </div>
        `;
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
            "On Track": "green",
            "Breached": "red",
            "Draft Quotation": "amber",
            "Submitted Awaiting SO": "blue",
            "SO Created": "blue",
            "Partially Invoiced": "amber",
            "Fully Invoiced": "blue",
            "Dispatched": "blue",
            "POD Pending": "amber",
            "Closed": "green",
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
