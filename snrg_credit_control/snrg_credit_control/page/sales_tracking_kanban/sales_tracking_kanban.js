frappe.pages["sales-tracking-kanban"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Sales Tracking Kanban",
        single_column: true,
    });

    wrapper.sales_tracking_kanban = new SnrgSalesTrackingKanbanPage(page, wrapper);
};

class SnrgSalesTrackingKanbanPage {
    constructor(page, wrapper) {
        this.page = page;
        this.wrapper = $(wrapper);
        this.data = null;
        this.controls = {};
        this.suppressRefresh = false;
        this.refreshSequence = 0;
        this.isRefreshing = false;
        this.laneOrder = [
            "Draft Quotation",
            "Submitted Awaiting SO",
            "SO Created",
            "Partially Invoiced",
            "Fully Invoiced",
            "Dispatched",
            "Delivered",
            "POD Pending",
            "Closed",
            "Cancelled",
        ];

        this.setup();
    }

    setup() {
        this.page.set_primary_action("Refresh", () => this.refresh(), "refresh");
        this.page.set_secondary_action("Table View", () => frappe.set_route("sales-tracking"));
        this.renderShell();
        this.makeFilters();
        this.bindEvents();
        this.refresh();
    }

    renderShell() {
        this.wrapper.find(".layout-main-section").html(`
            <style>
                .snrg-stk-page {
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                    color: #10253f;
                }
                .snrg-stk-page-header-meta {
                    display: inline-flex;
                    align-items: center;
                    margin-left: 10px;
                    vertical-align: middle;
                }
                .snrg-stk-chip {
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    padding: 5px 9px;
                    border-radius: 999px;
                    background: #f8fafc;
                    border: 1px solid #dbe3ef;
                    font-size: 11px;
                    color: #334155;
                    font-weight: 600;
                }
                .snrg-stk-panel {
                    border: 1px solid #dde5f0;
                    border-radius: 12px;
                    background: #fff;
                    padding: 10px;
                }
                .snrg-stk-control-strip {
                    display: grid;
                    grid-template-columns: repeat(5, minmax(150px, 1fr));
                    gap: 8px;
                    align-items: end;
                }
                .snrg-stk-control-strip .frappe-control {
                    margin-bottom: 0;
                    padding: 4px 6px;
                    border: 1px solid #dde5f0;
                    border-radius: 8px;
                    background: #fff;
                    min-height: 50px;
                }
                .snrg-stk-control-strip .control-label {
                    font-size: 10px;
                    font-weight: 700;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: .08em;
                    margin-bottom: 2px;
                }
                .snrg-stk-control-strip input,
                .snrg-stk-control-strip select,
                .snrg-stk-control-strip .input-with-feedback {
                    min-height: 28px;
                    border-radius: 6px;
                    border: 1px solid #dbe3ef;
                    background: #fff;
                    font-size: 11px;
                }
                .snrg-stk-board-head {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 12px;
                    flex-wrap: wrap;
                    margin-bottom: 8px;
                }
                .snrg-stk-board-title {
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                }
                .snrg-stk-board-title strong {
                    font-size: 16px;
                    color: #0f172a;
                }
                .snrg-stk-board-subtitle {
                    font-size: 12px;
                    color: #64748b;
                }
                .snrg-stk-lanes {
                    display: grid;
                    grid-auto-flow: column;
                    grid-auto-columns: minmax(280px, 320px);
                    gap: 10px;
                    overflow-x: auto;
                    padding-bottom: 6px;
                }
                .snrg-stk-lane {
                    display: flex;
                    flex-direction: column;
                    border: 1px solid #dde5f0;
                    border-radius: 12px;
                    background: #f8fafc;
                    min-height: calc(100vh - 250px);
                    max-height: calc(100vh - 250px);
                }
                .snrg-stk-lane-header {
                    position: sticky;
                    top: 0;
                    z-index: 2;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 8px;
                    padding: 10px 12px;
                    border-bottom: 1px solid #dbe3ef;
                    background: #f8fafc;
                    border-top-left-radius: 12px;
                    border-top-right-radius: 12px;
                }
                .snrg-stk-lane-title {
                    font-size: 11px;
                    font-weight: 800;
                    letter-spacing: .08em;
                    text-transform: uppercase;
                    color: #475569;
                }
                .snrg-stk-lane-count {
                    min-width: 28px;
                    height: 28px;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 999px;
                    border: 1px solid #cbd5e1;
                    background: #fff;
                    font-size: 12px;
                    font-weight: 800;
                    color: #0f172a;
                }
                .snrg-stk-lane-body {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                    padding: 10px;
                    overflow-y: auto;
                }
                .snrg-stk-card {
                    border: 1px solid #dbe3ef;
                    border-radius: 10px;
                    background: #fff;
                    padding: 10px;
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
                }
                .snrg-stk-card-head {
                    display: flex;
                    align-items: flex-start;
                    justify-content: space-between;
                    gap: 8px;
                }
                .snrg-stk-quotation-link {
                    color: #0f766e;
                    font-weight: 800;
                    font-size: 15px;
                    line-height: 1.2;
                    text-decoration: none;
                    cursor: pointer;
                }
                .snrg-stk-quotation-link:hover { text-decoration: underline; }
                .snrg-stk-card-grid {
                    display: grid;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                    gap: 8px 10px;
                }
                .snrg-stk-metric {
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                    min-width: 0;
                }
                .snrg-stk-label {
                    font-size: 10px;
                    font-weight: 700;
                    letter-spacing: .06em;
                    text-transform: uppercase;
                    color: #64748b;
                }
                .snrg-stk-value {
                    font-size: 12px;
                    color: #0f172a;
                    font-weight: 600;
                    line-height: 1.35;
                    word-break: break-word;
                }
                .snrg-stk-value.secondary {
                    font-size: 11px;
                    color: #64748b;
                    font-weight: 500;
                }
                .snrg-stk-stack {
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                }
                .snrg-stk-pill {
                    display: inline-flex;
                    align-items: center;
                    padding: 3px 8px;
                    border-radius: 999px;
                    font-size: 10px;
                    font-weight: 700;
                    border: 1px solid #dbe3ef;
                    background: #f8fafc;
                    color: #334155;
                    white-space: nowrap;
                }
                .snrg-stk-pill.red { background: #fef2f2; border-color: #fecaca; color: #b91c1c; }
                .snrg-stk-pill.green { background: #ecfdf5; border-color: #bbf7d0; color: #047857; }
                .snrg-stk-pill.amber { background: #fffbeb; border-color: #fcd34d; color: #b45309; }
                .snrg-stk-pill.blue { background: #eff6ff; border-color: #bfdbfe; color: #1d4ed8; }
                .snrg-stk-pill.slate { background: #f8fafc; border-color: #cbd5e1; color: #475569; }
                .snrg-stk-remark {
                    font-size: 11px;
                    color: #475569;
                    line-height: 1.45;
                    background: #fafcff;
                    border: 1px dashed #dbe3ef;
                    border-radius: 8px;
                    padding: 8px;
                }
                .snrg-stk-card-actions {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 8px;
                    padding-top: 2px;
                }
                .snrg-stk-action {
                    color: #0f766e;
                    font-size: 11px;
                    font-weight: 700;
                    cursor: pointer;
                    text-decoration: none;
                }
                .snrg-stk-action:hover { text-decoration: underline; }
                .snrg-stk-empty,
                .snrg-stk-empty-lane {
                    border: 1px dashed #cbd5e1;
                    border-radius: 10px;
                    background: #fff;
                    color: #64748b;
                    text-align: center;
                }
                .snrg-stk-empty {
                    padding: 28px 16px;
                    font-size: 13px;
                }
                .snrg-stk-empty-lane {
                    padding: 22px 12px;
                    font-size: 12px;
                }
                .snrg-stk-skeleton {
                    height: 320px;
                    border-radius: 14px;
                    background: linear-gradient(90deg, #e2e8f0 25%, #f8fafc 50%, #e2e8f0 75%);
                    background-size: 220% 100%;
                    animation: snrg-stk-shimmer 1.4s infinite;
                }
                @keyframes snrg-stk-shimmer {
                    0% { background-position: 200% 0; }
                    100% { background-position: -200% 0; }
                }
                @media (max-width: 1400px) {
                    .snrg-stk-control-strip { grid-template-columns: repeat(3, minmax(160px, 1fr)); }
                }
                @media (max-width: 980px) {
                    .snrg-stk-control-strip { grid-template-columns: repeat(2, minmax(160px, 1fr)); }
                }
                @media (max-width: 720px) {
                    .snrg-stk-control-strip { grid-template-columns: 1fr; }
                    .snrg-stk-lanes { grid-auto-columns: minmax(260px, 85vw); }
                }
            </style>
            <div class="snrg-stk-page">
                <section class="snrg-stk-panel">
                    <div class="snrg-stk-control-strip">
                        <div class="snrg-stk-company-filter"></div>
                        <div class="snrg-stk-month-filter"></div>
                        <div class="snrg-stk-date-range-filter"></div>
                        <div class="snrg-stk-territory-filter"></div>
                        <div class="snrg-stk-search-filter"></div>
                    </div>
                </section>
                <section class="snrg-stk-panel">
                    <div class="snrg-stk-board-head">
                        <div class="snrg-stk-board-title">
                            <strong>Kanban Board</strong>
                            <span class="snrg-stk-board-subtitle">Quotation-led operational flow from draft to closed.</span>
                        </div>
                        <div class="snrg-stk-board-meta"></div>
                    </div>
                    <div class="snrg-stk-board"></div>
                </section>
            </div>
        `);
    }

    makeFilters() {
        this.controls.company = this.makeFilterControl(".snrg-stk-company-filter", {
            label: "Company",
            fieldname: "company",
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company"),
            change: () => this.handleFilterChange(),
        });

        this.controls.order_month = this.makeFilterControl(".snrg-stk-month-filter", {
            label: "Order Month",
            fieldname: "order_month",
            fieldtype: "Select",
            options: "\n",
            change: () => this.handleFilterChange(),
        });

        this.controls.date_range = this.makeFilterControl(".snrg-stk-date-range-filter", {
            label: "Date Range",
            fieldname: "date_range",
            fieldtype: "DateRange",
            change: () => this.handleFilterChange(),
        });

        this.controls.territory = this.makeFilterControl(".snrg-stk-territory-filter", {
            label: "Zone",
            fieldname: "territory",
            fieldtype: "Select",
            options: "\n",
            change: () => this.handleFilterChange(),
        });

        this.controls.search = this.makeFilterControl(".snrg-stk-search-filter", {
            label: "Search",
            fieldname: "search",
            fieldtype: "Data",
            placeholder: "Quotation / customer / salesperson",
            change: frappe.utils.debounce(() => this.renderBoard(), 250),
        });

        this.renderLoading();
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

    bindEvents() {
        this.wrapper.on("click", ".snrg-stk-open-quotation", (event) => {
            const index = Number($(event.currentTarget).closest("[data-row-index]").data("rowIndex"));
            const row = this.getVisibleRows()[index];
            if (row) {
                frappe.set_route("Form", "Quotation", row.quotation_id);
            }
        });

        this.wrapper.on("click", ".snrg-stk-open-tracker", (event) => {
            const index = Number($(event.currentTarget).closest("[data-row-index]").data("rowIndex"));
            const row = this.getVisibleRows()[index];
            if (row) {
                frappe.set_route("sales-tracking", { search: row.quotation_id });
            }
        });
    }

    handleFilterChange() {
        if (this.suppressRefresh) return;
        this.refresh();
    }

    setRefreshing(isRefreshing) {
        this.isRefreshing = isRefreshing;
        const $primary = this.page.btn_primary;
        if ($primary?.length) {
            $primary.prop("disabled", isRefreshing);
            $primary.toggleClass("disabled", isRefreshing);
            $primary.find(".alt-vertical-align").text(isRefreshing ? "Refreshing..." : "Refresh");
        }
    }

    async refresh() {
        const refreshId = ++this.refreshSequence;
        this.setRefreshing(true);
        this.renderLoading();

        const dateRange = this.controls.date_range.get_value() || [];
        const [fromDate, toDate] = Array.isArray(dateRange) ? dateRange : [null, null];

        try {
            const response = await frappe.call({
                method: "snrg_credit_control.snrg_credit_control.page.sales_tracking_kanban.sales_tracking_kanban.get_kanban_data",
                args: {
                    company: this.controls.company.get_value(),
                    order_month: this.controls.order_month.get_value(),
                    from_date: fromDate,
                    to_date: toDate,
                    territory: this.controls.territory.get_value(),
                    limit: 500,
                },
            });

            if (refreshId !== this.refreshSequence) {
                return;
            }

            this.data = response.message || { rows: [] };
            this.updateOrderMonthOptions();
            this.updateTerritoryOptions();
            this.renderMeta();
            this.renderBoard();
        } finally {
            if (refreshId === this.refreshSequence) {
                this.setRefreshing(false);
            }
        }
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
            .forEach(([, label]) => optionLines.push(label));

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

        this.suppressRefresh = true;
        try {
            control.df.options = nextOptions;
            control.refresh();

            if (currentValue && hasCurrentValue && control.get_value() !== currentValue) {
                control.set_value(currentValue);
            }
        } finally {
            this.suppressRefresh = false;
        }
    }

    renderMeta() {
        const generated = this.data?.generated_on
            ? frappe.datetime.str_to_user(this.data.generated_on)
            : frappe.datetime.now_datetime();
        const rowCount = this.getVisibleRows().length;
        const chipHtml = [
            `<span class="snrg-stk-chip">Updated: ${frappe.utils.escape_html(generated)}</span>`,
            `<span class="snrg-stk-chip">Cards: ${rowCount}</span>`,
        ].join("");

        const $pageHeaderMeta = this.page.wrapper.find(".snrg-stk-page-header-meta");
        if ($pageHeaderMeta.length) {
            $pageHeaderMeta.html(chipHtml);
        } else {
            const $titleText = this.page.wrapper.find(".page-head .title-text, .page-title .title-text").first();
            if ($titleText.length) {
                $titleText.after(`<span class="snrg-stk-page-header-meta">${chipHtml}</span>`);
            }
        }

        this.wrapper.find(".snrg-stk-board-meta").html(chipHtml);
    }

    renderLoading() {
        this.wrapper.find(".snrg-stk-board").html(`<div class="snrg-stk-skeleton"></div>`);
    }

    renderBoard() {
        const rows = this.getVisibleRows();
        const lanes = this.buildLanes(rows);
        this.visibleRowIndexMap = new Map(rows.map((row, index) => [row.quotation_id, index]));

        this.renderMeta();

        if (!rows.length) {
            this.wrapper.find(".snrg-stk-board").html(`
                <div class="snrg-stk-empty">No quotations matched the current filters.</div>
            `);
            return;
        }

        const html = `
            <div class="snrg-stk-lanes">
                ${lanes.map((lane) => `
                    <section class="snrg-stk-lane">
                        <header class="snrg-stk-lane-header">
                            <span class="snrg-stk-lane-title">${frappe.utils.escape_html(lane.label)}</span>
                            <span class="snrg-stk-lane-count">${lane.rows.length}</span>
                        </header>
                        <div class="snrg-stk-lane-body">
                            ${lane.rows.length
                                ? lane.rows.map((row) => this.renderCard(row)).join("")
                                : `<div class="snrg-stk-empty-lane">No quotations in this stage.</div>`}
                        </div>
                    </section>
                `).join("")}
            </div>
        `;

        this.wrapper.find(".snrg-stk-board").html(html);
    }

    buildLanes(rows) {
        const grouped = new Map(this.laneOrder.map((stage) => [stage, []]));
        const fallback = [];

        rows.forEach((row) => {
            const stage = row.current_stage || "Unclassified";
            if (!grouped.has(stage)) {
                fallback.push(row);
                return;
            }
            grouped.get(stage).push(row);
        });

        const lanes = this.laneOrder.map((stage) => ({
            key: stage,
            label: stage,
            rows: grouped.get(stage) || [],
        }));

        if (fallback.length) {
            lanes.push({ key: "Unclassified", label: "Unclassified", rows: fallback });
        }

        return lanes;
    }

    getVisibleRows() {
        let rows = [...(this.data?.rows || [])];
        const searchValue = (this.controls.search?.get_value() || "").trim().toLowerCase();

        if (searchValue) {
            rows = rows.filter((row) => {
                const haystack = [
                    row.quotation_id,
                    row.customer,
                    row.channel_partner_name,
                    row.salesperson_summary,
                    row.credit_status,
                    row.customer_confirmation_status,
                    row.current_stage,
                    row.latest_ho_remark,
                ]
                    .filter(Boolean)
                    .join(" ")
                    .toLowerCase();
                return haystack.includes(searchValue);
            });
        }

        return rows;
    }

    renderCard(row) {
        const rowIndex = this.visibleRowIndexMap?.get(row.quotation_id) ?? -1;
        const customerCode = row.customer ? frappe.utils.escape_html(row.customer) : "-";
        const customerName = row.channel_partner_name ? frappe.utils.escape_html(row.channel_partner_name) : "-";
        const remark = row.latest_ho_remark ? frappe.utils.escape_html(row.latest_ho_remark) : "No HO remark yet.";
        const valueHtml = `
            <div class="snrg-stk-stack">
                <span class="snrg-stk-value">GT - ${this.formatCurrency(row.order_value, row.currency)}</span>
                <span class="snrg-stk-value secondary">NT - ${this.formatCurrency(row.basic_value, row.currency)}</span>
            </div>
        `;

        return `
            <article class="snrg-stk-card" data-row-index="${rowIndex}">
                <div class="snrg-stk-card-head">
                    <div class="snrg-stk-stack">
                        <a class="snrg-stk-quotation-link snrg-stk-open-quotation">${frappe.utils.escape_html(row.quotation_id)}</a>
                        <span class="snrg-stk-value secondary">${this.formatDate(row.order_date)}</span>
                    </div>
                    ${this.renderPill(row.quotation_status, "status")}
                </div>

                <div class="snrg-stk-card-grid">
                    <div class="snrg-stk-metric">
                        <span class="snrg-stk-label">Customer</span>
                        <span class="snrg-stk-value">${customerCode}</span>
                        <span class="snrg-stk-value secondary">${customerName}</span>
                    </div>
                    <div class="snrg-stk-metric">
                        <span class="snrg-stk-label">Quotation Value</span>
                        ${valueHtml}
                    </div>
                    <div class="snrg-stk-metric">
                        <span class="snrg-stk-label">Salesperson</span>
                        <span class="snrg-stk-value">${frappe.utils.escape_html(row.salesperson_summary || "-")}</span>
                    </div>
                    <div class="snrg-stk-metric">
                        <span class="snrg-stk-label">Credit</span>
                        ${this.renderPill(row.credit_status, "credit")}
                    </div>
                    <div class="snrg-stk-metric">
                        <span class="snrg-stk-label">Customer Confirmation</span>
                        ${this.renderPill(row.customer_confirmation_status, "confirmation")}
                    </div>
                    <div class="snrg-stk-metric">
                        <span class="snrg-stk-label">ESD</span>
                        <span class="snrg-stk-value">${this.formatDate(row.original_esd)}</span>
                    </div>
                </div>

                <div class="snrg-stk-remark">${remark}</div>

                <div class="snrg-stk-card-actions">
                    <a class="snrg-stk-action snrg-stk-open-quotation">Open Quotation</a>
                    <a class="snrg-stk-action snrg-stk-open-tracker">Open In Tracker</a>
                </div>
            </article>
        `;
    }

    renderPill(value, type) {
        const text = frappe.utils.escape_html(value || "-");
        const color = this.getPillColor(value, type);
        return `<span class="snrg-stk-pill ${color}">${text}</span>`;
    }

    getPillColor(value, type) {
        const normalized = String(value || "").toLowerCase();

        if (type === "status") {
            if (normalized.includes("cancel")) return "red";
            if (normalized.includes("draft")) return "amber";
            if (normalized.includes("submit")) return "blue";
        }

        if (type === "credit") {
            if (normalized === "credit ok") return "green";
            if (normalized === "credit hold") return "red";
            if (normalized === "mixed") return "amber";
        }

        if (type === "confirmation") {
            if (normalized === "confirmed") return "green";
            if (normalized.includes("request")) return "red";
            if (normalized === "pending") return "amber";
        }

        return "slate";
    }

    formatCurrency(value, currency) {
        const amount = frappe.format(value || 0, {
            fieldtype: "Currency",
            options: currency || "INR",
        });
        return amount || "0.00";
    }

    formatDate(value) {
        if (!value) return "-";
        try {
            return frappe.datetime.str_to_user(String(value));
        } catch (error) {
            return String(value);
        }
    }
}
