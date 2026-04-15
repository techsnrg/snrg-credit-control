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
                .snrg-st-hero {
                    position:relative; overflow:hidden; border-radius:28px; padding:24px;
                    background:
                        radial-gradient(circle at top right, rgba(255,255,255,.16), transparent 28%),
                        linear-gradient(130deg, #123b44 0%, #0f766e 45%, #d97706 100%);
                    color:#fff; box-shadow:0 20px 40px rgba(15,23,42,.10);
                }
                .snrg-st-hero::after {
                    content:""; position:absolute; right:-110px; bottom:-120px; width:280px; height:280px;
                    border-radius:50%; background:rgba(255,255,255,.08);
                }
                .snrg-st-kicker { font-size:11px; text-transform:uppercase; letter-spacing:.18em; font-weight:700; opacity:.84; }
                .snrg-st-hero h2 { margin:8px 0 10px; font-size:30px; line-height:1.08; font-weight:800; color:#fff; }
                .snrg-st-hero p { margin:0; max-width:900px; font-size:14px; line-height:1.6; color:rgba(255,255,255,.88); }
                .snrg-st-meta { display:flex; gap:10px; flex-wrap:wrap; margin-top:18px; }
                .snrg-st-chip {
                    display:inline-flex; align-items:center; gap:6px; padding:7px 11px; border-radius:999px;
                    background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.18); font-size:12px;
                }
                .snrg-st-filter-row { display:grid; grid-template-columns:repeat(6, minmax(180px, 1fr)); gap:12px; align-items:start; }
                .snrg-st-filter-row .form-group,
                .snrg-st-filter-row .frappe-control,
                .snrg-st-filter-row .control-input-wrapper,
                .snrg-st-filter-row .control-value {
                    width: 100%;
                }
                .snrg-st-filter-row .frappe-control {
                    margin-bottom: 0;
                    padding: 12px 14px 10px;
                    border: 1px solid #dbe3ef;
                    border-radius: 18px;
                    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
                    box-shadow: 0 10px 24px rgba(15,23,42,.04);
                    min-height: 84px;
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
                    border-radius:20px; padding:16px; border:1px solid #e2e8f0;
                    background:linear-gradient(180deg, #ffffff 0%, #f8fafc 100%); box-shadow:0 12px 24px rgba(15,23,42,.04);
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
                .snrg-st-table td {
                    padding:12px 14px; border-bottom:1px solid #edf2f7; font-size:13px; line-height:1.45; vertical-align:top;
                    color:#1e293b;
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
                @media (max-width: 768px) { .snrg-st-filter-row, .snrg-st-summary { grid-template-columns:1fr; } .snrg-st-hero h2 { font-size:24px; } }
            </style>
            <div class="snrg-st-page">
                <section class="snrg-st-hero">
                    <div class="snrg-st-kicker">Quotation-Led Operations</div>
                    <h2>Sales Tracking</h2>
                    <p>Track customer quotations through credit, billing, dispatch, delivery, and POD completion from one operational view, while keeping drill-down access to the linked sales orders and invoices.</p>
                    <div class="snrg-st-meta"></div>
                </section>
                <section class="snrg-st-filter-row">
                    <div class="snrg-st-company-filter"></div>
                    <div class="snrg-st-from-filter"></div>
                    <div class="snrg-st-to-filter"></div>
                    <div class="snrg-st-territory-filter"></div>
                    <div class="snrg-st-credit-filter"></div>
                    <div class="snrg-st-search-filter"></div>
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
        this.controls.company = this.page.add_field({
            label: "Company",
            fieldname: "company",
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company"),
            change: () => this.refresh(),
        });
        $(this.controls.company.wrapper).appendTo(this.wrapper.find(".snrg-st-company-filter"));

        this.controls.from_date = this.page.add_field({
            label: "From Date",
            fieldname: "from_date",
            fieldtype: "Date",
            change: () => this.refresh(),
        });
        $(this.controls.from_date.wrapper).appendTo(this.wrapper.find(".snrg-st-from-filter"));

        this.controls.to_date = this.page.add_field({
            label: "To Date",
            fieldname: "to_date",
            fieldtype: "Date",
            change: () => this.refresh(),
        });
        $(this.controls.to_date.wrapper).appendTo(this.wrapper.find(".snrg-st-to-filter"));

        this.controls.territory = this.page.add_field({
            label: "Zone",
            fieldname: "territory",
            fieldtype: "Link",
            options: "Territory",
            change: () => this.refresh(),
        });
        $(this.controls.territory.wrapper).appendTo(this.wrapper.find(".snrg-st-territory-filter"));

        this.controls.credit_status = this.page.add_field({
            label: "Credit Status",
            fieldname: "credit_status",
            fieldtype: "Select",
            options: "\nCredit OK\nCredit Hold\nMixed\nNot Run",
            change: () => this.refresh(),
        });
        $(this.controls.credit_status.wrapper).appendTo(this.wrapper.find(".snrg-st-credit-filter"));

        this.controls.search = this.page.add_field({
            label: "Search",
            fieldname: "search",
            fieldtype: "Data",
            placeholder: "Quotation / customer",
            change: frappe.utils.debounce(() => this.refresh(), 350),
        });
        $(this.controls.search.wrapper).appendTo(this.wrapper.find(".snrg-st-search-filter"));

        this.render_loading();
    }

    bind_events() {
        this.wrapper.on("click", ".snrg-st-open-quotation", (event) => {
            const index = Number($(event.currentTarget).closest("[data-row-index]").data("rowIndex"));
            const row = this.data?.rows?.[index];
            if (row) {
                frappe.set_route("Form", "Quotation", row.quotation_id);
            }
        });

        this.wrapper.on("click", ".snrg-st-open-comments", (event) => {
            event.preventDefault();
            const index = Number($(event.currentTarget).closest("[data-row-index]").data("rowIndex"));
            const row = this.data?.rows?.[index];
            if (row?.quotation_comments_url) {
                window.location.href = row.quotation_comments_url;
            }
        });

        this.wrapper.on("click", ".snrg-st-open-salespeople", (event) => {
            const index = Number($(event.currentTarget).closest("[data-row-index]").data("rowIndex"));
            const row = this.data?.rows?.[index];
            if (row) {
                this.showSalespeopleDialog(row);
            }
        });

        this.wrapper.on("click", ".snrg-st-open-invoices", (event) => {
            const index = Number($(event.currentTarget).closest("[data-row-index]").data("rowIndex"));
            const row = this.data?.rows?.[index];
            if (row) {
                this.showInvoicesDialog(row);
            }
        });

        this.wrapper.on("click", ".snrg-st-open-sales-orders", (event) => {
            const index = Number($(event.currentTarget).closest("[data-row-index]").data("rowIndex"));
            const row = this.data?.rows?.[index];
            if (row) {
                this.showSalesOrdersDialog(row);
            }
        });
    }

    async refresh() {
        this.render_loading();
        const response = await frappe.call({
            method: "snrg_credit_control.snrg_credit_control.page.sales_tracking.sales_tracking.get_tracker_data",
            args: {
                company: this.controls.company.get_value(),
                from_date: this.controls.from_date.get_value(),
                to_date: this.controls.to_date.get_value(),
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
        this.renderMeta();
        this.renderSummary();
        this.renderTable();
    }

    renderMeta() {
        const generated = this.data?.generated_on ? frappe.datetime.str_to_user(this.data.generated_on) : frappe.datetime.now_datetime();
        this.wrapper.find(".snrg-st-meta").html(`
            <span class="snrg-st-chip">Updated: ${frappe.utils.escape_html(generated)}</span>
            <span class="snrg-st-chip">Company: ${frappe.utils.escape_html(this.controls.company.get_value() || "All Companies")}</span>
            <span class="snrg-st-chip">Rows: ${frappe.utils.escape_html(String(this.data?.summary?.row_count || 0))}</span>
        `);
    }

    renderSummary() {
        const summary = this.data?.summary || {};
        const cards = [
            { label: "Rows", value: frappe.format(summary.row_count || 0, { fieldtype: "Int" }) },
            { label: "Order Value", value: format_currency(summary.order_value || 0, "INR") },
            { label: "Invoiced", value: format_currency(summary.invoice_amount || 0, "INR") },
            { label: "Credit Hold", value: frappe.format(summary.credit_hold_count || 0, { fieldtype: "Int" }) },
            { label: "POD Complete", value: frappe.format(summary.pod_complete_count || 0, { fieldtype: "Int" }) },
        ];

        this.wrapper.find(".snrg-st-summary").html(cards.map((card) => `
            <div class="snrg-st-card">
                <div class="snrg-st-card-label">${frappe.utils.escape_html(card.label)}</div>
                <div class="snrg-st-card-value">${card.value}</div>
            </div>
        `).join(""));
    }

    renderTable() {
        const rows = this.data?.rows || [];
        this.wrapper.find(".snrg-st-row-count").text(`${rows.length} row${rows.length === 1 ? "" : "s"}`);

        if (!rows.length) {
            this.wrapper.find(".snrg-st-table-container").html(`<div class="snrg-st-empty">No quotations matched the current filters.</div>`);
            return;
        }

        const columns = [
            ["Quotation ID", (row) => `<a class="snrg-st-link snrg-st-open-quotation">${frappe.utils.escape_html(row.quotation_id)}</a>`],
            ["Order Month", (row) => this.escapeCell(row.order_month)],
            ["Order Date", (row) => this.formatDate(row.order_date)],
            ["Channel Partner Name", (row) => this.escapeCell(row.channel_partner_name)],
            ["Zone", (row) => this.escapeCell(row.zone)],
            ["City", (row) => this.escapeCell(row.city)],
            ["State", (row) => this.escapeCell(row.state)],
            ["Salesperson", (row) => row.salespeople?.length ? `<a class="snrg-st-link snrg-st-open-salespeople">${frappe.utils.escape_html(row.salesperson_summary || "")}</a>` : this.emptyCell()],
            ["Order Value", (row) => this.money(row.order_value, row.currency)],
            ["Basic Value", (row) => this.money(row.basic_value, row.currency)],
            ["Credit Status", (row) => this.statusPill(row.credit_status)],
            ["Credit Clearance Date", (row) => this.formatDate(row.credit_clearance_date)],
            ["Delay Reason", (row) => this.escapeCell(row.delay_reason)],
            ["Original ESD", (row) => this.formatDate(row.original_esd)],
            ["SO Delivery Date", (row) => row.sales_orders?.length ? `<a class="snrg-st-link snrg-st-open-sales-orders">${this.formatDate(row.sales_order_delivery_date)}</a>` : this.emptyCell()],
            ["Latest HO Remark", (row) => row.latest_ho_remark ? `<a href="#" class="snrg-st-link snrg-st-open-comments"><span class="snrg-st-remarks">${frappe.utils.escape_html(row.latest_ho_remark)}</span></a>` : this.emptyCell()],
            ["Invoice No", (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${frappe.utils.escape_html(row.invoice_summary || "")}</a>` : this.emptyCell()],
            ["Invoice Amount", (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${this.money(row.invoice_amount, row.currency)}</a>` : this.emptyCell()],
            ["Invoice Date", (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${this.formatDate(row.invoice_date)}</a>` : this.emptyCell()],
            ["Shortage Details", (row) => this.money(row.shortage_amount, row.currency)],
            ["Dispatch Date", (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${this.formatDate(row.dispatch_date)}</a>` : this.emptyCell()],
            ["No. of Cartons", (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${frappe.format(row.no_of_cartons || 0, { fieldtype: "Int" })}</a>` : this.emptyCell()],
            ["Transport Name", (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${frappe.utils.escape_html(row.transport_name || "-")}</a>` : this.emptyCell()],
            ["Tracking Details", (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${frappe.utils.escape_html(row.tracking_details || "-")}</a>` : this.emptyCell()],
            ["Delivery Status", (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${this.statusPill(row.delivery_status_overall)}</a>` : this.statusPill("Pending")],
            ["Delivery Date", (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${this.formatDate(row.delivery_date)}</a>` : this.emptyCell()],
            ["POD Received", (row) => row.invoice_details?.length ? `<a class="snrg-st-link snrg-st-open-invoices">${this.statusPill(row.pod_status)}</a>` : this.statusPill("Pending")],
            ["Remarks", (row) => row.remarks ? `<a class="snrg-st-link snrg-st-open-invoices"><span class="snrg-st-remarks">${frappe.utils.escape_html(row.remarks)}</span></a>` : this.emptyCell()],
        ];

        const headerHtml = columns.map(([label]) => `<th>${frappe.utils.escape_html(label)}</th>`).join("");
        const bodyHtml = rows.map((row, index) => `
            <tr data-row-index="${index}">
                ${columns.map(([, renderer]) => `<td>${renderer(row)}</td>`).join("")}
            </tr>
        `).join("");

        this.wrapper.find(".snrg-st-table-container").html(`
            <table class="snrg-st-table">
                <thead><tr>${headerHtml}</tr></thead>
                <tbody>${bodyHtml}</tbody>
            </table>
        `);
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
