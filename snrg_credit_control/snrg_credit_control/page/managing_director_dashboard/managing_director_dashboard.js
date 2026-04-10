frappe.pages["managing-director-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Managing Director Dashboard",
        single_column: true,
    });

    wrapper.md_dashboard = new SnrgManagingDirectorDashboard(page, wrapper);
};

class SnrgManagingDirectorDashboard {
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
                .snrg-md-page {
                    display: flex;
                    flex-direction: column;
                    gap: 18px;
                    color: #10253f;
                }
                .snrg-md-hero {
                    position: relative;
                    overflow: hidden;
                    border-radius: 28px;
                    padding: 24px 24px 22px;
                    background:
                        radial-gradient(circle at top right, rgba(255,255,255,0.24), transparent 28%),
                        linear-gradient(135deg, #0f3d3e 0%, #155e75 52%, #d97706 100%);
                    color: #fff;
                    box-shadow: 0 20px 40px rgba(15, 23, 42, 0.12);
                }
                .snrg-md-hero::after {
                    content: "";
                    position: absolute;
                    inset: auto -120px -120px auto;
                    width: 300px;
                    height: 300px;
                    border-radius: 50%;
                    background: rgba(255, 255, 255, 0.08);
                }
                .snrg-md-kicker {
                    font-size: 11px;
                    text-transform: uppercase;
                    letter-spacing: .18em;
                    font-weight: 700;
                    opacity: 0.8;
                }
                .snrg-md-hero h2 {
                    margin: 8px 0 10px;
                    font-size: 30px;
                    line-height: 1.1;
                    font-weight: 800;
                    color: #fff;
                }
                .snrg-md-hero p {
                    margin: 0;
                    max-width: 780px;
                    font-size: 14px;
                    line-height: 1.6;
                    color: rgba(255,255,255,0.88);
                }
                .snrg-md-toolbar {
                    display: flex;
                    align-items: flex-end;
                    justify-content: space-between;
                    gap: 16px;
                    flex-wrap: wrap;
                    margin-top: 18px;
                }
                .snrg-md-toolbar-meta {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                    font-size: 12px;
                    color: rgba(255,255,255,0.88);
                }
                .snrg-md-chip {
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    padding: 7px 11px;
                    border-radius: 999px;
                    background: rgba(255,255,255,0.12);
                    border: 1px solid rgba(255,255,255,0.18);
                }
                .snrg-md-actions {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                }
                .snrg-md-action {
                    border: 0;
                    border-radius: 999px;
                    padding: 10px 14px;
                    background: rgba(255,255,255,0.14);
                    color: #fff;
                    font-size: 13px;
                    font-weight: 700;
                }
                .snrg-md-filter-row {
                    display: grid;
                    grid-template-columns: minmax(220px, 320px) auto;
                    gap: 14px;
                    align-items: end;
                }
                .snrg-md-card-grid {
                    display: grid;
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                    gap: 12px;
                }
                .snrg-md-card {
                    border-radius: 20px;
                    padding: 16px;
                    border: 1px solid #e2e8f0;
                    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
                    box-shadow: 0 12px 24px rgba(15, 23, 42, 0.04);
                    min-height: 122px;
                }
                .snrg-md-card[data-tone="red"] { background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%); }
                .snrg-md-card[data-tone="rose"] { background: linear-gradient(180deg, #fff7ed 0%, #ffffff 100%); }
                .snrg-md-card[data-tone="amber"] { background: linear-gradient(180deg, #fffbeb 0%, #ffffff 100%); }
                .snrg-md-card[data-tone="blue"] { background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%); }
                .snrg-md-card[data-tone="teal"] { background: linear-gradient(180deg, #ecfeff 0%, #ffffff 100%); }
                .snrg-md-card[data-tone="slate"] { background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%); }
                .snrg-md-card[data-tone="purple"] { background: linear-gradient(180deg, #f5f3ff 0%, #ffffff 100%); }
                .snrg-md-card-label {
                    font-size: 11px;
                    color: #5b7088;
                    text-transform: uppercase;
                    letter-spacing: .08em;
                    font-weight: 700;
                }
                .snrg-md-card-value {
                    margin-top: 10px;
                    font-size: 26px;
                    line-height: 1.1;
                    font-weight: 800;
                    color: #0f172a;
                }
                .snrg-md-card-helper {
                    margin-top: 8px;
                    font-size: 12px;
                    line-height: 1.5;
                    color: #526277;
                }
                .snrg-md-grid {
                    display: grid;
                    grid-template-columns: 1.1fr .9fr;
                    gap: 12px;
                }
                .snrg-md-panel {
                    border-radius: 24px;
                    border: 1px solid #e2e8f0;
                    background: #fff;
                    box-shadow: 0 12px 24px rgba(15, 23, 42, 0.04);
                }
                .snrg-md-panel-body {
                    padding: 18px 18px 16px;
                }
                .snrg-md-panel-title {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 10px;
                    margin-bottom: 14px;
                }
                .snrg-md-panel-title h3 {
                    margin: 0;
                    font-size: 18px;
                    font-weight: 800;
                    color: #0f172a;
                }
                .snrg-md-panel-title span {
                    font-size: 12px;
                    color: #64748b;
                }
                .snrg-md-bars {
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                }
                .snrg-md-bar-label {
                    display: flex;
                    justify-content: space-between;
                    gap: 12px;
                    font-size: 13px;
                    font-weight: 700;
                    color: #334155;
                    margin-bottom: 6px;
                }
                .snrg-md-bar-track {
                    height: 10px;
                    border-radius: 999px;
                    background: #e2e8f0;
                    overflow: hidden;
                }
                .snrg-md-bar-fill {
                    height: 100%;
                    border-radius: 999px;
                    background: linear-gradient(90deg, #0f766e 0%, #f59e0b 100%);
                }
                .snrg-md-list {
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                }
                .snrg-md-item {
                    border: 1px solid #e2e8f0;
                    border-radius: 18px;
                    padding: 14px 15px;
                    background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
                }
                .snrg-md-item-top {
                    display: flex;
                    align-items: flex-start;
                    justify-content: space-between;
                    gap: 10px;
                }
                .snrg-md-item-title {
                    margin: 0;
                    font-size: 15px;
                    line-height: 1.35;
                    font-weight: 800;
                    color: #0f172a;
                }
                .snrg-md-item-sub {
                    margin-top: 5px;
                    font-size: 12px;
                    color: #64748b;
                }
                .snrg-md-item-meta {
                    margin-top: 9px;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                }
                .snrg-md-pill {
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    padding: 6px 10px;
                    border-radius: 999px;
                    border: 1px solid #dbe3ef;
                    background: #f8fafc;
                    color: #334155;
                    font-size: 12px;
                    font-weight: 700;
                }
                .snrg-md-pill.status-pending { background: #fff7ed; border-color: #fed7aa; color: #c2410c; }
                .snrg-md-pill.status-approved,
                .snrg-md-pill.status-cleared,
                .snrg-md-pill.status-credit-ok,
                .snrg-md-pill.status-issued { background: #ecfdf5; border-color: #bbf7d0; color: #047857; }
                .snrg-md-pill.status-broken,
                .snrg-md-pill.status-credit-hold,
                .snrg-md-pill.status-cancelled { background: #fef2f2; border-color: #fecaca; color: #b91c1c; }
                .snrg-md-pill.status-partially-cleared,
                .snrg-md-pill.status-draft { background: #eff6ff; border-color: #bfdbfe; color: #1d4ed8; }
                .snrg-md-empty {
                    padding: 24px 16px;
                    text-align: center;
                    color: #64748b;
                    font-size: 13px;
                    border: 1px dashed #cbd5e1;
                    border-radius: 18px;
                    background: #f8fafc;
                }
                .snrg-md-skeleton {
                    height: 132px;
                    border-radius: 20px;
                    background: linear-gradient(90deg, #e2e8f0 25%, #f8fafc 50%, #e2e8f0 75%);
                    background-size: 220% 100%;
                    animation: snrg-md-shimmer 1.4s infinite;
                }
                @keyframes snrg-md-shimmer {
                    0% { background-position: 200% 0; }
                    100% { background-position: -200% 0; }
                }
                @media (max-width: 1200px) {
                    .snrg-md-card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                    .snrg-md-grid { grid-template-columns: 1fr; }
                }
                @media (max-width: 768px) {
                    .snrg-md-hero { padding: 20px 18px; border-radius: 24px; }
                    .snrg-md-hero h2 { font-size: 24px; }
                    .snrg-md-filter-row { grid-template-columns: 1fr; }
                    .snrg-md-card-grid { grid-template-columns: 1fr; }
                }
            </style>
            <div class="snrg-md-page">
                <section class="snrg-md-hero">
                    <div class="snrg-md-kicker">Executive Control Room</div>
                    <h2>Managing Director Dashboard</h2>
                    <p>Track revenue risk, delayed approvals, receivable pressure, customer promises, and legal follow-up from one command view built for fast decision-making.</p>
                    <div class="snrg-md-toolbar">
                        <div class="snrg-md-toolbar-meta"></div>
                        <div class="snrg-md-actions">
                            <button class="snrg-md-action" data-route-type="Report" data-route-name="Credit Control Report">Open Credit Report</button>
                            <button class="snrg-md-action" data-route-type="List" data-route-name="Credit PTP">Open PTPs</button>
                            <button class="snrg-md-action" data-route-type="List" data-route-name="Demand Notice">Open Notices</button>
                        </div>
                    </div>
                </section>
                <section class="snrg-md-filter-row">
                    <div class="snrg-md-company-filter"></div>
                    <div></div>
                </section>
                <section class="snrg-md-card-grid snrg-md-summary"></section>
                <section class="snrg-md-grid">
                    <div class="snrg-md-panel">
                        <div class="snrg-md-panel-body">
                            <div class="snrg-md-panel-title">
                                <h3>Approval Pressure</h3>
                                <span>How draft orders are moving through approval</span>
                            </div>
                            <div class="snrg-md-bars snrg-md-approval-mix"></div>
                        </div>
                    </div>
                    <div class="snrg-md-panel">
                        <div class="snrg-md-panel-body">
                            <div class="snrg-md-panel-title">
                                <h3>Credit Check Mix</h3>
                                <span>Draft order value by risk state</span>
                            </div>
                            <div class="snrg-md-bars snrg-md-risk-mix"></div>
                        </div>
                    </div>
                </section>
                <section class="snrg-md-grid">
                    <div class="snrg-md-panel">
                        <div class="snrg-md-panel-body">
                            <div class="snrg-md-panel-title">
                                <h3>Approval Queue</h3>
                                <span>Orders waiting for executive attention</span>
                            </div>
                            <div class="snrg-md-list snrg-md-approval-queue"></div>
                        </div>
                    </div>
                    <div class="snrg-md-panel">
                        <div class="snrg-md-panel-body">
                            <div class="snrg-md-panel-title">
                                <h3>Blocked Orders</h3>
                                <span>Highest-value credit holds right now</span>
                            </div>
                            <div class="snrg-md-list snrg-md-blocked-orders"></div>
                        </div>
                    </div>
                </section>
                <section class="snrg-md-grid">
                    <div class="snrg-md-panel">
                        <div class="snrg-md-panel-body">
                            <div class="snrg-md-panel-title">
                                <h3>Overdue Customers</h3>
                                <span>Customers with invoices aging past control threshold</span>
                            </div>
                            <div class="snrg-md-list snrg-md-overdue-customers"></div>
                        </div>
                    </div>
                    <div class="snrg-md-panel">
                        <div class="snrg-md-panel-body">
                            <div class="snrg-md-panel-title">
                                <h3>PTP Watchlist</h3>
                                <span>Promises that need follow-up or recovery action</span>
                            </div>
                            <div class="snrg-md-list snrg-md-ptp-watchlist"></div>
                        </div>
                    </div>
                </section>
                <section class="snrg-md-panel">
                    <div class="snrg-md-panel-body">
                        <div class="snrg-md-panel-title">
                            <h3>Demand Notice Tracker</h3>
                            <span>Latest legal follow-up and deadline posture</span>
                        </div>
                        <div class="snrg-md-list snrg-md-demand-notices"></div>
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
            change: () => this.refresh(),
        });
        $(this.controls.company.wrapper).appendTo(this.wrapper.find(".snrg-md-company-filter"));
    }

    bind_events() {
        this.wrapper.on("click", ".snrg-md-action", (event) => {
            const button = $(event.currentTarget);
            frappe.set_route(button.data("route-type"), button.data("route-name"));
        });
    }

    async refresh() {
        this.render_loading();
        const response = await frappe.call({
            method: "snrg_credit_control.snrg_credit_control.page.managing_director_dashboard.managing_director_dashboard.get_dashboard_data",
            args: {
                company: this.controls.company.get_value() || "",
            },
        });
        this.data = response.message || {};
        this.render();
    }

    render_loading() {
        const skeletons = Array.from({ length: 8 }, () => `<div class="snrg-md-skeleton"></div>`).join("");
        this.wrapper.find(".snrg-md-summary").html(skeletons);
        this.wrapper.find(".snrg-md-approval-mix, .snrg-md-risk-mix, .snrg-md-approval-queue, .snrg-md-blocked-orders, .snrg-md-overdue-customers, .snrg-md-ptp-watchlist, .snrg-md-demand-notices")
            .html(`<div class="snrg-md-empty">Loading dashboard data…</div>`);
    }

    render() {
        this.render_meta();
        this.render_summary();
        this.render_mix(".snrg-md-approval-mix", this.data.approval_mix || [], "amount");
        this.render_mix(".snrg-md-risk-mix", this.data.risk_mix || [], "amount");
        this.render_order_list(".snrg-md-approval-queue", this.data.approval_queue || [], {
            statusField: "approval_status",
            primaryMetric: (row) => this.metricPill("Order", this.money(row.grand_total)),
            secondaryMetric: (row) => row.overdue_amount ? this.metricPill("Overdue", this.money(row.overdue_amount)) : "",
            extra: (row) => [
                row.requested_on ? this.metricPill("Requested", row.requested_on) : "",
                row.requested_to_employee ? this.metricPill("To", row.requested_to_employee) : "",
            ].join(""),
        });
        this.render_order_list(".snrg-md-blocked-orders", this.data.blocked_orders || [], {
            statusField: "approval_status",
            defaultStatus: "Credit Hold",
            primaryMetric: (row) => this.metricPill("Order", this.money(row.grand_total)),
            secondaryMetric: (row) => row.overdue_amount ? this.metricPill("Overdue", this.money(row.overdue_amount)) : "",
            extra: (row) => [
                row.reason_code ? this.metricPill("Reason", row.reason_code) : "",
                row.overdue_count ? this.metricPill("Invoices", `${row.overdue_count}`) : "",
            ].join(""),
        });
        this.render_customer_list(".snrg-md-overdue-customers", this.data.overdue_customers || []);
        this.render_ptp_list(".snrg-md-ptp-watchlist", this.data.ptp_watchlist || []);
        this.render_notice_list(".snrg-md-demand-notices", this.data.demand_notices || []);
    }

    render_meta() {
        const generated = this.data.generated_on
            ? frappe.datetime.str_to_user(this.data.generated_on)
            : frappe.datetime.now_datetime();
        this.wrapper.find(".snrg-md-toolbar-meta").html(`
            <span class="snrg-md-chip">Scope: ${frappe.utils.escape_html(this.data.company || "All Companies")}</span>
            <span class="snrg-md-chip">Updated: ${frappe.utils.escape_html(generated)}</span>
        `);
    }

    render_summary() {
        const cards = (this.data.summary || []).map((card) => `
            <div class="snrg-md-card" data-tone="${card.tone || "slate"}">
                <div class="snrg-md-card-label">${frappe.utils.escape_html(card.label || "")}</div>
                <div class="snrg-md-card-value">${card.datatype === "Currency" ? this.money(card.value) : frappe.format(card.value || 0, { fieldtype: "Int" })}</div>
                <div class="snrg-md-card-helper">${frappe.utils.escape_html(card.helper || "")}</div>
            </div>
        `).join("");
        this.wrapper.find(".snrg-md-summary").html(cards || `<div class="snrg-md-empty">No summary data available.</div>`);
    }

    render_mix(selector, rows, metricKey) {
        const total = rows.reduce((sum, row) => sum + Number(row[metricKey] || 0), 0) || 1;
        const html = rows.length ? rows.map((row) => {
            const share = Math.max(8, Math.round((Number(row[metricKey] || 0) / total) * 100));
            return `
                <div>
                    <div class="snrg-md-bar-label">
                        <span>${frappe.utils.escape_html(row.label || "Unknown")} (${frappe.format(row.count || 0, { fieldtype: "Int" })})</span>
                        <span>${this.money(row.amount || 0)}</span>
                    </div>
                    <div class="snrg-md-bar-track">
                        <div class="snrg-md-bar-fill" style="width:${share}%"></div>
                    </div>
                </div>
            `;
        }).join("") : `<div class="snrg-md-empty">No data in this view yet.</div>`;
        this.wrapper.find(selector).html(html);
    }

    render_order_list(selector, rows, options) {
        const html = rows.length ? rows.map((row) => `
            <div class="snrg-md-item">
                <div class="snrg-md-item-top">
                    <div>
                        <p class="snrg-md-item-title">
                            <a href="/app/sales-order/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(row.name)}</a>
                            · ${frappe.utils.escape_html(row.customer_name || row.customer || "")}
                        </p>
                        <div class="snrg-md-item-sub">${frappe.utils.escape_html(row.company || "")}${row.transaction_date ? ` · ${frappe.datetime.str_to_user(row.transaction_date)}` : ""}</div>
                    </div>
                    ${this.statusPill(row[options.statusField] || options.defaultStatus || "")}
                </div>
                <div class="snrg-md-item-meta">
                    ${options.primaryMetric ? options.primaryMetric(row) : ""}
                    ${options.secondaryMetric ? options.secondaryMetric(row) : ""}
                    ${options.extra ? options.extra(row) : ""}
                </div>
            </div>
        `).join("") : `<div class="snrg-md-empty">Nothing needs attention here right now.</div>`;
        this.wrapper.find(selector).html(html);
    }

    render_customer_list(selector, rows) {
        const html = rows.length ? rows.map((row) => `
            <div class="snrg-md-item">
                <div class="snrg-md-item-top">
                    <div>
                        <p class="snrg-md-item-title">
                            <a href="/app/customer/${encodeURIComponent(row.customer)}">${frappe.utils.escape_html(row.customer_name)}</a>
                        </p>
                        <div class="snrg-md-item-sub">${row.oldest_invoice_date ? `Oldest invoice: ${frappe.datetime.str_to_user(row.oldest_invoice_date)}` : "Oldest invoice date unavailable"}</div>
                    </div>
                    ${this.statusPill("Credit Hold")}
                </div>
                <div class="snrg-md-item-meta">
                    ${this.metricPill("Overdue", this.money(row.overdue_amount))}
                    ${this.metricPill("Invoices", `${row.invoice_count}`)}
                    ${row.oldest_age_days != null ? this.metricPill("Age", `${row.oldest_age_days} days`) : ""}
                </div>
            </div>
        `).join("") : `<div class="snrg-md-empty">No aged overdue customers for the selected scope.</div>`;
        this.wrapper.find(selector).html(html);
    }

    render_ptp_list(selector, rows) {
        const html = rows.length ? rows.map((row) => `
            <div class="snrg-md-item">
                <div class="snrg-md-item-top">
                    <div>
                        <p class="snrg-md-item-title">
                            <a href="/app/credit-ptp/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(row.name)}</a>
                            · ${frappe.utils.escape_html(row.customer_name || row.customer || "")}
                        </p>
                        <div class="snrg-md-item-sub">${frappe.utils.escape_html(row.company || "")}${row.commitment_date ? ` · Due ${frappe.datetime.str_to_user(row.commitment_date)}` : ""}</div>
                    </div>
                    ${this.statusPill(row.status)}
                </div>
                <div class="snrg-md-item-meta">
                    ${this.metricPill("Gap", this.money(row.difference_amount))}
                    ${this.metricPill("Committed", this.money(row.committed_amount))}
                    ${row.days_to_due != null ? this.metricPill(row.days_to_due < 0 ? "Late By" : "Due In", `${Math.abs(row.days_to_due)} days`) : ""}
                    ${row.ptp_by_name ? this.metricPill("By", row.ptp_by_name) : ""}
                </div>
            </div>
        `).join("") : `<div class="snrg-md-empty">No open PTP follow-up items for this scope.</div>`;
        this.wrapper.find(selector).html(html);
    }

    render_notice_list(selector, rows) {
        const html = rows.length ? rows.map((row) => `
            <div class="snrg-md-item">
                <div class="snrg-md-item-top">
                    <div>
                        <p class="snrg-md-item-title">
                            <a href="/app/demand-notice/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(row.name)}</a>
                            · ${frappe.utils.escape_html(row.customer_name || row.customer || "")}
                        </p>
                        <div class="snrg-md-item-sub">${frappe.utils.escape_html(row.company || "")}${row.payment_deadline ? ` · Deadline ${frappe.datetime.str_to_user(row.payment_deadline)}` : ""}</div>
                    </div>
                    ${this.statusPill(row.status)}
                </div>
                <div class="snrg-md-item-meta">
                    ${this.metricPill("Due", this.money(row.grand_total_due))}
                    ${this.metricPill("Outstanding", this.money(row.total_outstanding))}
                    ${row.total_interest ? this.metricPill("Interest", this.money(row.total_interest)) : ""}
                    ${row.notice_date ? this.metricPill("Notice Date", frappe.datetime.str_to_user(row.notice_date)) : ""}
                </div>
            </div>
        `).join("") : `<div class="snrg-md-empty">No demand notices found for the selected scope.</div>`;
        this.wrapper.find(selector).html(html);
    }

    metricPill(label, value) {
        return `<span class="snrg-md-pill">${frappe.utils.escape_html(label)}: ${frappe.utils.escape_html(value || "")}</span>`;
    }

    statusPill(value) {
        const label = value || "Unknown";
        return `<span class="snrg-md-pill status-${frappe.scrub(label)}">${frappe.utils.escape_html(label)}</span>`;
    }

    money(value) {
        return format_currency(value || 0, this.data.currency || "INR");
    }
}
