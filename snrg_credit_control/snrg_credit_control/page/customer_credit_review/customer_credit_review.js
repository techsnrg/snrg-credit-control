frappe.pages["customer-credit-review"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Customer Credit Review",
        single_column: true,
    });

    wrapper.customer_credit_review = new SnrgCustomerCreditReview(page, wrapper);
};

class SnrgCustomerCreditReview {
    constructor(page, wrapper) {
        this.page = page;
        this.wrapper = $(wrapper);
        this.data = { columns: [], rows: [], summary: [] };
        this.controls = {};
        this.visibleColumns = new Set();
        this.searchText = "";
        this.storageKey = "snrg-customer-credit-review-columns";

        this.setup();
    }

    setup() {
        this.page.set_primary_action("Refresh", () => this.refresh(), "refresh");
        this.page.set_secondary_action("Sync Recommended Limits", () => this.syncRecommendedLimits(), "refresh");
        this.render_shell();
        this.make_filters();
        this.bind_events();
    }

    render_shell() {
        this.wrapper.find(".layout-main-section").html(`
            <style>
                .snrg-ccr-page {
                    display: flex;
                    flex-direction: column;
                    gap: 18px;
                    color: #10253f;
                }
                .snrg-ccr-hero {
                    position: relative;
                    overflow: hidden;
                    border-radius: 28px;
                    padding: 24px;
                    background:
                        radial-gradient(circle at top right, rgba(255,255,255,0.18), transparent 28%),
                        linear-gradient(135deg, #1f3c88 0%, #2a5298 48%, #f59e0b 100%);
                    color: #fff;
                    box-shadow: 0 20px 40px rgba(15, 23, 42, 0.10);
                }
                .snrg-ccr-kicker {
                    font-size: 11px;
                    text-transform: uppercase;
                    letter-spacing: .18em;
                    font-weight: 700;
                    opacity: 0.82;
                }
                .snrg-ccr-hero h2 {
                    margin: 8px 0 10px;
                    font-size: 30px;
                    line-height: 1.08;
                    font-weight: 800;
                    color: #fff;
                }
                .snrg-ccr-hero p {
                    margin: 0;
                    max-width: 760px;
                    font-size: 14px;
                    line-height: 1.6;
                    color: rgba(255,255,255,0.88);
                }
                .snrg-ccr-meta {
                    display: flex;
                    gap: 10px;
                    flex-wrap: wrap;
                    margin-top: 18px;
                }
                .snrg-ccr-chip {
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    padding: 7px 11px;
                    border-radius: 999px;
                    background: rgba(255,255,255,0.12);
                    border: 1px solid rgba(255,255,255,0.18);
                    font-size: 12px;
                }
                .snrg-ccr-filter-row {
                    display: grid;
                    grid-template-columns: minmax(220px, 280px) minmax(220px, 320px) auto;
                    gap: 12px;
                    align-items: end;
                }
                .snrg-ccr-summary {
                    display: grid;
                    grid-template-columns: repeat(6, minmax(0, 1fr));
                    gap: 12px;
                }
                .snrg-ccr-card {
                    border-radius: 20px;
                    padding: 16px;
                    border: 1px solid #e2e8f0;
                    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
                    box-shadow: 0 12px 24px rgba(15, 23, 42, 0.04);
                    min-height: 118px;
                }
                .snrg-ccr-card[data-tone="red"] { background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%); }
                .snrg-ccr-card[data-tone="amber"] { background: linear-gradient(180deg, #fffbeb 0%, #ffffff 100%); }
                .snrg-ccr-card[data-tone="blue"] { background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%); }
                .snrg-ccr-card[data-tone="teal"] { background: linear-gradient(180deg, #ecfeff 0%, #ffffff 100%); }
                .snrg-ccr-card[data-tone="purple"] { background: linear-gradient(180deg, #f5f3ff 0%, #ffffff 100%); }
                .snrg-ccr-card-label {
                    font-size: 11px;
                    color: #5b7088;
                    text-transform: uppercase;
                    letter-spacing: .08em;
                    font-weight: 700;
                }
                .snrg-ccr-card-value {
                    margin-top: 10px;
                    font-size: 26px;
                    line-height: 1.1;
                    font-weight: 800;
                    color: #0f172a;
                }
                .snrg-ccr-layout {
                    display: grid;
                    grid-template-columns: 320px minmax(0, 1fr);
                    gap: 14px;
                    align-items: start;
                }
                .snrg-ccr-panel {
                    border-radius: 24px;
                    border: 1px solid #e2e8f0;
                    background: #fff;
                    box-shadow: 0 12px 24px rgba(15, 23, 42, 0.04);
                }
                .snrg-ccr-panel-body {
                    padding: 18px;
                }
                .snrg-ccr-panel-title {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    gap: 10px;
                    margin-bottom: 14px;
                }
                .snrg-ccr-panel-title h3 {
                    margin: 0;
                    font-size: 18px;
                    font-weight: 800;
                    color: #0f172a;
                }
                .snrg-ccr-panel-title span {
                    font-size: 12px;
                    color: #64748b;
                }
                .snrg-ccr-column-actions {
                    display: flex;
                    gap: 8px;
                    margin-bottom: 12px;
                }
                .snrg-ccr-column-btn {
                    border: 1px solid #dbe3ef;
                    border-radius: 999px;
                    padding: 8px 12px;
                    background: #f8fafc;
                    color: #334155;
                    font-size: 12px;
                    font-weight: 700;
                    cursor: pointer;
                }
                .snrg-ccr-columns {
                    display: grid;
                    gap: 10px;
                    max-height: 680px;
                    overflow: auto;
                    padding-right: 4px;
                }
                .snrg-ccr-checkbox {
                    display: flex;
                    gap: 10px;
                    align-items: flex-start;
                    padding: 10px 12px;
                    border-radius: 16px;
                    border: 1px solid #e2e8f0;
                    background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
                }
                .snrg-ccr-checkbox label {
                    margin: 0;
                    font-size: 13px;
                    line-height: 1.45;
                    color: #334155;
                    font-weight: 700;
                    cursor: pointer;
                }
                .snrg-ccr-checkbox small {
                    display: block;
                    margin-top: 3px;
                    color: #64748b;
                    font-weight: 500;
                }
                .snrg-ccr-table-shell {
                    overflow: auto;
                    border-radius: 20px;
                    border: 1px solid #e2e8f0;
                }
                .snrg-ccr-table {
                    width: 100%;
                    min-width: 1180px;
                    border-collapse: separate;
                    border-spacing: 0;
                    background: #fff;
                }
                .snrg-ccr-table thead th {
                    position: sticky;
                    top: 0;
                    z-index: 2;
                    padding: 12px 12px;
                    background: #f8fafc;
                    border-bottom: 1px solid #dbe3ef;
                    font-size: 12px;
                    text-transform: uppercase;
                    letter-spacing: .06em;
                    color: #526277;
                    white-space: nowrap;
                }
                .snrg-ccr-table tbody td {
                    padding: 12px 12px;
                    border-bottom: 1px solid #edf2f7;
                    vertical-align: top;
                    font-size: 13px;
                    color: #1e293b;
                    white-space: nowrap;
                }
                .snrg-ccr-table tbody tr:hover {
                    background: #f8fbff;
                }
                .snrg-ccr-name {
                    font-weight: 800;
                    color: #0f172a;
                }
                .snrg-ccr-tag {
                    display: inline-flex;
                    align-items: center;
                    padding: 5px 9px;
                    border-radius: 999px;
                    font-size: 12px;
                    font-weight: 700;
                    border: 1px solid #dbe3ef;
                }
                .snrg-ccr-tag.yes {
                    background: #ecfdf5;
                    border-color: #bbf7d0;
                    color: #047857;
                }
                .snrg-ccr-tag.no {
                    background: #fef2f2;
                    border-color: #fecaca;
                    color: #b91c1c;
                }
                .snrg-ccr-actions {
                    display: flex;
                    gap: 8px;
                }
                .snrg-ccr-action {
                    border: 1px solid #dbe3ef;
                    border-radius: 999px;
                    padding: 6px 10px;
                    background: #fff;
                    color: #1d4ed8;
                    font-size: 12px;
                    font-weight: 700;
                    cursor: pointer;
                }
                .snrg-ccr-empty {
                    padding: 28px 16px;
                    text-align: center;
                    color: #64748b;
                    font-size: 13px;
                    border: 1px dashed #cbd5e1;
                    border-radius: 18px;
                    background: #f8fafc;
                }
                .snrg-ccr-skeleton {
                    height: 118px;
                    border-radius: 20px;
                    background: linear-gradient(90deg, #e2e8f0 25%, #f8fafc 50%, #e2e8f0 75%);
                    background-size: 220% 100%;
                    animation: snrg-ccr-shimmer 1.4s infinite;
                }
                @keyframes snrg-ccr-shimmer {
                    0% { background-position: 200% 0; }
                    100% { background-position: -200% 0; }
                }
                @media (max-width: 1280px) {
                    .snrg-ccr-summary { grid-template-columns: repeat(3, minmax(0, 1fr)); }
                    .snrg-ccr-layout { grid-template-columns: 1fr; }
                }
                @media (max-width: 768px) {
                    .snrg-ccr-hero { padding: 20px 18px; border-radius: 24px; }
                    .snrg-ccr-hero h2 { font-size: 24px; }
                    .snrg-ccr-filter-row { grid-template-columns: 1fr; }
                    .snrg-ccr-summary { grid-template-columns: 1fr; }
                }
            </style>
            <div class="snrg-ccr-page">
                <section class="snrg-ccr-hero">
                    <div class="snrg-ccr-kicker">Credit Review Console</div>
                    <h2>Customer Credit Review</h2>
                    <p>Review payment-driven credit capacity, outstanding exposure, and current limit position customer by customer with a focused company-level lens.</p>
                    <div class="snrg-ccr-meta"></div>
                </section>
                <section class="snrg-ccr-filter-row">
                    <div class="snrg-ccr-company-filter"></div>
                    <div class="snrg-ccr-search-filter"></div>
                    <div></div>
                </section>
                <section class="snrg-ccr-summary"></section>
                <section class="snrg-ccr-layout">
                    <div class="snrg-ccr-panel">
                        <div class="snrg-ccr-panel-body">
                            <div class="snrg-ccr-panel-title">
                                <h3>Visible Columns</h3>
                                <span>Use checkmarks to shape the view</span>
                            </div>
                            <div class="snrg-ccr-column-actions">
                                <button class="snrg-ccr-column-btn" data-column-action="select-all">Select All</button>
                                <button class="snrg-ccr-column-btn" data-column-action="clear-all">Clear All</button>
                            </div>
                            <div class="snrg-ccr-columns"></div>
                        </div>
                    </div>
                    <div class="snrg-ccr-panel">
                        <div class="snrg-ccr-panel-body">
                            <div class="snrg-ccr-panel-title">
                                <h3>Customer Table</h3>
                                <span class="snrg-ccr-table-meta">Waiting for company selection</span>
                            </div>
                            <div class="snrg-ccr-table-region"></div>
                        </div>
                    </div>
                </section>
            </div>
        `);
    }

    make_filters() {
        this.controls.company = this.page.add_field({
            label: "Company",
            fieldname: "company",
            fieldtype: "Link",
            options: "Company",
            reqd: 1,
            default: frappe.defaults.get_user_default("Company"),
            change: () => this.refresh(),
        });
        $(this.controls.company.wrapper).appendTo(this.wrapper.find(".snrg-ccr-company-filter"));

        this.controls.search = this.page.add_field({
            label: "Search",
            fieldname: "search_text",
            fieldtype: "Data",
            placeholder: "Customer code, name, or group",
            change: () => {
                this.searchText = (this.controls.search.get_value() || "").trim().toLowerCase();
                this.render_table();
            },
        });
        $(this.controls.search.wrapper).appendTo(this.wrapper.find(".snrg-ccr-search-filter"));

        if (this.controls.company.get_value()) {
            this.refresh();
        }
    }

    bind_events() {
        this.wrapper.on("change", ".snrg-ccr-column-toggle", (event) => {
            const fieldname = $(event.currentTarget).data("fieldname");
            if (event.currentTarget.checked) {
                this.visibleColumns.add(fieldname);
            } else {
                this.visibleColumns.delete(fieldname);
            }
            this.persistVisibleColumns();
            this.render_table();
        });

        this.wrapper.on("click", "[data-column-action]", (event) => {
            const action = $(event.currentTarget).data("column-action");
            if (action === "select-all") {
                this.visibleColumns = new Set(this.data.columns.map((column) => column.fieldname));
            } else {
                this.visibleColumns = new Set();
            }
            this.persistVisibleColumns();
            this.render_column_picker();
            this.render_table();
        });

        this.wrapper.on("click", ".snrg-ccr-action", (event) => {
            const button = $(event.currentTarget);
            const action = button.data("action");
            const customer = button.data("customer");
            const company = this.controls.company.get_value();

            if (action === "profile") {
                frappe.set_route("customer-credit-profile", { company, customer });
                return;
            }

            if (action === "quotations") {
                frappe.route_options = { party_name: customer };
                frappe.set_route("List", "Quotation");
                return;
            }

            if (action === "orders") {
                frappe.route_options = { customer };
                frappe.set_route("List", "Sales Order");
            }
        });
    }

    async refresh() {
        const company = this.controls.company.get_value();
        if (!company) {
            this.wrapper.find(".snrg-ccr-table-region").html(`<div class="snrg-ccr-empty">Select a company to load the review page.</div>`);
            return;
        }

        this.render_loading();
        const response = await frappe.call({
            method: "snrg_credit_control.snrg_credit_control.page.customer_credit_review.customer_credit_review.get_page_data",
            args: { company },
        });
        this.data = response.message || { columns: [], rows: [], summary: [] };
        this.initializeVisibleColumns();
        this.render();
    }

    syncRecommendedLimits() {
        const company = this.controls.company.get_value();
        if (!company) {
            frappe.show_alert({ message: __("Select a company first."), indicator: "orange" });
            return;
        }

        frappe.confirm(
            __(`This will update the read-only recommended credit limit snapshot for all active customers in ${company}. Continue?`),
            async () => {
                const response = await frappe.call({
                    method: "snrg_credit_control.snrg_credit_control.page.customer_credit_review.customer_credit_review.sync_recommended_limits",
                    args: { company },
                    freeze: true,
                    freeze_message: __("Syncing recommended credit limits..."),
                });

                const result = response.message || {};
                frappe.show_alert({
                    message: __(
                        "{0} customers processed. Updated: {1}, Created: {2}.",
                        [result.processed || 0, result.updated || 0, result.created || 0]
                    ),
                    indicator: "green",
                });
                this.refresh();
            }
        );
    }

    initializeVisibleColumns() {
        const stored = this.getStoredVisibleColumns();
        if (stored.length) {
            const valid = stored.filter((fieldname) => this.data.columns.some((column) => column.fieldname === fieldname));
            this.visibleColumns = new Set(valid);
        }

        if (!this.visibleColumns.size) {
            this.visibleColumns = new Set(this.data.columns.map((column) => column.fieldname));
        }
    }

    getStoredVisibleColumns() {
        try {
            return JSON.parse(localStorage.getItem(this.storageKey) || "[]");
        } catch (error) {
            return [];
        }
    }

    persistVisibleColumns() {
        localStorage.setItem(this.storageKey, JSON.stringify(Array.from(this.visibleColumns)));
    }

    render_loading() {
        const skeletons = Array.from({ length: 6 }, () => `<div class="snrg-ccr-skeleton"></div>`).join("");
        this.wrapper.find(".snrg-ccr-summary").html(skeletons);
        this.wrapper.find(".snrg-ccr-columns").html(`<div class="snrg-ccr-empty">Loading columns…</div>`);
        this.wrapper.find(".snrg-ccr-table-region").html(`<div class="snrg-ccr-empty">Loading customer data…</div>`);
    }

    render() {
        this.render_meta();
        this.render_summary();
        this.render_column_picker();
        this.render_table();
    }

    render_meta() {
        const generated = this.data.generated_on
            ? frappe.datetime.str_to_user(this.data.generated_on)
            : frappe.datetime.now_datetime();
        this.wrapper.find(".snrg-ccr-meta").html(`
            <span class="snrg-ccr-chip">Scope: ${frappe.utils.escape_html(this.data.company || "")}</span>
            <span class="snrg-ccr-chip">Updated: ${frappe.utils.escape_html(generated)}</span>
            <span class="snrg-ccr-chip">Rows: ${frappe.format((this.data.rows || []).length, { fieldtype: "Int" })}</span>
        `);
    }

    render_summary() {
        const cards = (this.data.summary || []).map((card) => `
            <div class="snrg-ccr-card" data-tone="${card.tone || "slate"}">
                <div class="snrg-ccr-card-label">${frappe.utils.escape_html(card.label || "")}</div>
                <div class="snrg-ccr-card-value">${this.formatValue(card.value, card.datatype)}</div>
            </div>
        `).join("");
        this.wrapper.find(".snrg-ccr-summary").html(cards || `<div class="snrg-ccr-empty">No summary data available.</div>`);
    }

    render_column_picker() {
        const html = (this.data.columns || []).map((column) => `
            <div class="snrg-ccr-checkbox">
                <input
                    class="snrg-ccr-column-toggle"
                    id="snrg-ccr-col-${frappe.scrub(column.fieldname)}"
                    type="checkbox"
                    data-fieldname="${frappe.utils.escape_html(column.fieldname)}"
                    ${this.visibleColumns.has(column.fieldname) ? "checked" : ""}
                >
                <label for="snrg-ccr-col-${frappe.scrub(column.fieldname)}">
                    ${frappe.utils.escape_html(column.label)}
                    <small>${frappe.utils.escape_html(column.fieldtype || "Data")}</small>
                </label>
            </div>
        `).join("");
        this.wrapper.find(".snrg-ccr-columns").html(html || `<div class="snrg-ccr-empty">No columns available.</div>`);
    }

    render_table() {
        const visibleColumns = (this.data.columns || []).filter((column) => this.visibleColumns.has(column.fieldname));
        const rows = this.getFilteredRows();

        this.wrapper.find(".snrg-ccr-table-meta").text(`${rows.length} customer${rows.length === 1 ? "" : "s"} shown`);

        if (!visibleColumns.length) {
            this.wrapper.find(".snrg-ccr-table-region").html(`<div class="snrg-ccr-empty">Select at least one column to render the table.</div>`);
            return;
        }

        if (!rows.length) {
            this.wrapper.find(".snrg-ccr-table-region").html(`<div class="snrg-ccr-empty">No customers match the current filters.</div>`);
            return;
        }

        const head = visibleColumns.map((column) => `<th style="min-width:${column.width || 120}px">${frappe.utils.escape_html(column.label)}</th>`).join("");
        const body = rows.map((row) => `
            <tr>
                ${visibleColumns.map((column) => `<td>${this.renderCell(row, column)}</td>`).join("")}
            </tr>
        `).join("");

        this.wrapper.find(".snrg-ccr-table-region").html(`
            <div class="snrg-ccr-table-shell">
                <table class="snrg-ccr-table">
                    <thead><tr>${head}</tr></thead>
                    <tbody>${body}</tbody>
                </table>
            </div>
        `);
    }

    getFilteredRows() {
        const rows = this.data.rows || [];
        if (!this.searchText) {
            return rows;
        }

        return rows.filter((row) => {
            const haystack = [
                row.customer_code,
                row.customer_name,
                row.customer_group,
            ].join(" ").toLowerCase();
            return haystack.includes(this.searchText);
        });
    }

    renderCell(row, column) {
        const value = row[column.fieldname];

        if (column.fieldname === "customer_code") {
            return `<a class="snrg-ccr-name" href="/app/customer/${encodeURIComponent(row.customer_code)}">${frappe.utils.escape_html(row.customer_code)}</a>`;
        }

        if (column.fieldname === "security_cheque_available") {
            const statusClass = value === "Yes" ? "yes" : "no";
            return `<span class="snrg-ccr-tag ${statusClass}">${frappe.utils.escape_html(value || "No")}</span>`;
        }

        if (column.fieldname === "actions") {
            return `
                <div class="snrg-ccr-actions">
                    <button class="snrg-ccr-action" data-action="profile" data-customer="${frappe.utils.escape_html(row.customer_code)}">Profile</button>
                    <button class="snrg-ccr-action" data-action="quotations" data-customer="${frappe.utils.escape_html(row.customer_code)}">Quotations</button>
                    <button class="snrg-ccr-action" data-action="orders" data-customer="${frappe.utils.escape_html(row.customer_code)}">Orders</button>
                </div>
            `;
        }

        return this.formatValue(value, column.fieldtype);
    }

    formatValue(value, fieldtype) {
        if (value === null || value === undefined || value === "") {
            return `<span style="color:#94a3b8;">-</span>`;
        }

        if (fieldtype === "Currency") {
            return format_currency(value || 0, this.data.currency || "INR");
        }

        if (fieldtype === "Percent") {
            return `${frappe.format(value || 0, { fieldtype: "Float", precision: 2 })}%`;
        }

        if (fieldtype === "Float") {
            return frappe.format(value || 0, { fieldtype: "Float", precision: 2 });
        }

        if (fieldtype === "Int") {
            return frappe.format(value || 0, { fieldtype: "Int" });
        }

        if (fieldtype === "Date") {
            return frappe.datetime.str_to_user(value);
        }

        return frappe.utils.escape_html(String(value));
    }
}
