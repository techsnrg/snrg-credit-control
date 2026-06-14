frappe.pages["customer-credit-profile"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Customer Credit Profile",
        single_column: true,
    });

    wrapper.customer_credit_profile = new SnrgCustomerCreditProfile(page, wrapper);
};

class SnrgCustomerCreditProfile {
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
        this.apply_route_options();
    }

    render_shell() {
        this.wrapper.find(".layout-main-section").html(`
            <style>
                .snrg-ccp-page { display:flex; flex-direction:column; gap:18px; color:#10253f; }
                .snrg-ccp-hero {
                    position:relative; overflow:hidden; border-radius:28px; padding:24px;
                    background:
                        radial-gradient(circle at top right, rgba(255,255,255,0.18), transparent 28%),
                        linear-gradient(135deg, #0f3d3e 0%, #155e75 48%, #d97706 100%);
                    color:#fff; box-shadow:0 20px 40px rgba(15,23,42,.10);
                }
                .snrg-ccp-kicker { font-size:11px; text-transform:uppercase; letter-spacing:.18em; font-weight:700; opacity:.82; }
                .snrg-ccp-hero h2 { margin:8px 0 10px; font-size:30px; line-height:1.08; font-weight:800; color:#fff; }
                .snrg-ccp-hero p { margin:0; max-width:760px; font-size:14px; line-height:1.6; color:rgba(255,255,255,.88); }
                .snrg-ccp-meta { display:flex; gap:10px; flex-wrap:wrap; margin-top:18px; }
                .snrg-ccp-chip {
                    display:inline-flex; align-items:center; gap:6px; padding:7px 11px; border-radius:999px;
                    background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.18); font-size:12px;
                }
                .snrg-ccp-filter-row { display:grid; grid-template-columns:minmax(220px,280px) minmax(240px,360px) auto; gap:12px; align-items:end; }
                .snrg-ccp-card-grid { display:grid; grid-template-columns:repeat(6, minmax(0, 1fr)); gap:12px; }
                .snrg-ccp-card {
                    border-radius:20px; padding:16px; border:1px solid #e2e8f0;
                    background:linear-gradient(180deg, #ffffff 0%, #f8fafc 100%); box-shadow:0 12px 24px rgba(15,23,42,.04);
                    min-height:118px;
                }
                .snrg-ccp-card[data-tone="blue"] { background:linear-gradient(180deg, #eff6ff 0%, #ffffff 100%); }
                .snrg-ccp-card[data-tone="amber"] { background:linear-gradient(180deg, #fffbeb 0%, #ffffff 100%); }
                .snrg-ccp-card[data-tone="teal"] { background:linear-gradient(180deg, #ecfeff 0%, #ffffff 100%); }
                .snrg-ccp-card[data-tone="purple"] { background:linear-gradient(180deg, #f5f3ff 0%, #ffffff 100%); }
                .snrg-ccp-card[data-tone="red"] { background:linear-gradient(180deg, #fff1f2 0%, #ffffff 100%); }
                .snrg-ccp-card-label { font-size:11px; color:#5b7088; text-transform:uppercase; letter-spacing:.08em; font-weight:700; }
                .snrg-ccp-card-value { margin-top:10px; font-size:26px; line-height:1.1; font-weight:800; color:#0f172a; }
                .snrg-ccp-layout { display:grid; grid-template-columns:1.05fr .95fr; gap:14px; }
                .snrg-ccp-panel {
                    border-radius:24px; border:1px solid #e2e8f0; background:#fff; box-shadow:0 12px 24px rgba(15,23,42,.04);
                }
                .snrg-ccp-panel-body { padding:18px; }
                .snrg-ccp-panel-title { display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:14px; }
                .snrg-ccp-panel-title h3 { margin:0; font-size:18px; font-weight:800; color:#0f172a; }
                .snrg-ccp-panel-title span { font-size:12px; color:#64748b; }
                .snrg-ccp-metrics { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:12px; }
                .snrg-ccp-metric {
                    border:1px solid #e2e8f0; border-radius:18px; padding:14px; background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
                }
                .snrg-ccp-metric-label { font-size:12px; color:#64748b; font-weight:700; }
                .snrg-ccp-metric-value { margin-top:6px; font-size:20px; font-weight:800; color:#0f172a; }
                .snrg-ccp-list { display:flex; flex-direction:column; gap:10px; }
                .snrg-ccp-item {
                    border:1px solid #e2e8f0; border-radius:18px; padding:14px 15px; background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
                }
                .snrg-ccp-item-top { display:flex; align-items:flex-start; justify-content:space-between; gap:10px; }
                .snrg-ccp-item-title { margin:0; font-size:15px; line-height:1.35; font-weight:800; color:#0f172a; }
                .snrg-ccp-item-sub { margin-top:5px; font-size:12px; color:#64748b; }
                .snrg-ccp-item-meta { margin-top:9px; display:flex; flex-wrap:wrap; gap:8px; }
                .snrg-ccp-pill {
                    display:inline-flex; align-items:center; gap:6px; padding:6px 10px; border-radius:999px;
                    border:1px solid #dbe3ef; background:#f8fafc; color:#334155; font-size:12px; font-weight:700;
                }
                .snrg-ccp-tag { display:inline-flex; align-items:center; padding:6px 10px; border-radius:999px; font-size:12px; font-weight:700; border:1px solid #dbe3ef; }
                .snrg-ccp-tag.yes { background:#ecfdf5; border-color:#bbf7d0; color:#047857; }
                .snrg-ccp-tag.no { background:#fef2f2; border-color:#fecaca; color:#b91c1c; }
                .snrg-ccp-actions { display:flex; gap:8px; flex-wrap:wrap; }
                .snrg-ccp-action {
                    border:1px solid #dbe3ef; border-radius:999px; padding:8px 12px; background:#fff; color:#1d4ed8; font-size:12px; font-weight:700; cursor:pointer;
                }
                .snrg-ccp-empty {
                    padding:28px 16px; text-align:center; color:#64748b; font-size:13px; border:1px dashed #cbd5e1; border-radius:18px; background:#f8fafc;
                }
                .snrg-ccp-skeleton {
                    height:118px; border-radius:20px; background:linear-gradient(90deg, #e2e8f0 25%, #f8fafc 50%, #e2e8f0 75%);
                    background-size:220% 100%; animation:snrg-ccp-shimmer 1.4s infinite;
                }
                @keyframes snrg-ccp-shimmer { 0% { background-position:200% 0; } 100% { background-position:-200% 0; } }
                @media (max-width: 1280px) { .snrg-ccp-card-grid { grid-template-columns:repeat(3, minmax(0, 1fr)); } .snrg-ccp-layout { grid-template-columns:1fr; } }
                @media (max-width: 768px) { .snrg-ccp-filter-row, .snrg-ccp-card-grid, .snrg-ccp-metrics { grid-template-columns:1fr; } .snrg-ccp-hero { padding:20px 18px; border-radius:24px; } .snrg-ccp-hero h2 { font-size:24px; } }
            </style>
            <div class="snrg-ccp-page">
                <section class="snrg-ccp-hero">
                    <div class="snrg-ccp-kicker">Customer Deep Dive</div>
                    <h2>Customer Credit Profile</h2>
                    <p>Select one customer and review payment behaviour, receivable exposure, credit headroom, and recent transactions in one clear view.</p>
                    <div class="snrg-ccp-meta"></div>
                </section>
                <section class="snrg-ccp-filter-row">
                    <div class="snrg-ccp-company-filter"></div>
                    <div class="snrg-ccp-customer-filter"></div>
                    <div class="snrg-ccp-actions">
                        <button class="snrg-ccp-action" data-action="customer">Open Customer</button>
                        <button class="snrg-ccp-action" data-action="quotations">Open Quotations</button>
                        <button class="snrg-ccp-action" data-action="orders">Open Orders</button>
                    </div>
                </section>
                <section class="snrg-ccp-card-grid"></section>
                <section class="snrg-ccp-layout">
                    <div class="snrg-ccp-panel">
                        <div class="snrg-ccp-panel-body">
                            <div class="snrg-ccp-panel-title">
                                <h3>Exposure & Activity</h3>
                                <span>Core credit signals for the selected customer</span>
                            </div>
                            <div class="snrg-ccp-metrics snrg-ccp-main-metrics"></div>
                        </div>
                    </div>
                    <div class="snrg-ccp-panel">
                        <div class="snrg-ccp-panel-body">
                            <div class="snrg-ccp-panel-title">
                                <h3>Timeline & Status</h3>
                                <span>Recency and control checks</span>
                            </div>
                            <div class="snrg-ccp-metrics snrg-ccp-secondary-metrics"></div>
                        </div>
                    </div>
                </section>
                <section class="snrg-ccp-layout">
                    <div class="snrg-ccp-panel">
                        <div class="snrg-ccp-panel-body">
                            <div class="snrg-ccp-panel-title">
                                <h3>Recent Invoices</h3>
                                <span>Latest submitted invoices in this company</span>
                            </div>
                            <div class="snrg-ccp-list snrg-ccp-invoices"></div>
                        </div>
                    </div>
                    <div class="snrg-ccp-panel">
                        <div class="snrg-ccp-panel-body">
                            <div class="snrg-ccp-panel-title">
                                <h3>Recent Payments</h3>
                                <span>Latest submitted payment entries</span>
                            </div>
                            <div class="snrg-ccp-list snrg-ccp-payments"></div>
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
            change: () => {
                this.controls.customer.set_value("");
                this.data = null;
                this.render_empty("Select a customer to load the profile.");
            },
        });
        $(this.controls.company.wrapper).appendTo(this.wrapper.find(".snrg-ccp-company-filter"));

        this.controls.customer = this.page.add_field({
            label: "Customer Code",
            fieldname: "customer",
            fieldtype: "Link",
            options: "Customer",
            reqd: 1,
            get_query: () => ({ filters: { disabled: 0 } }),
            change: () => this.refresh(),
        });
        $(this.controls.customer.wrapper).appendTo(this.wrapper.find(".snrg-ccp-customer-filter"));

        this.render_empty("Select a customer to load the profile.");
    }

    bind_events() {
        this.wrapper.on("click", ".snrg-ccp-action", (event) => {
            const action = $(event.currentTarget).data("action");
            const customer = this.controls.customer.get_value();
            if (!customer) {
                frappe.show_alert({ message: __("Select a customer first."), indicator: "orange" });
                return;
            }

            if (action === "customer") {
                frappe.set_route("Form", "Customer", customer);
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

    apply_route_options() {
        const routeOptions = frappe.route_options || {};
        if (routeOptions.company) {
            this.controls.company.set_value(routeOptions.company);
        }
        if (routeOptions.customer) {
            this.controls.customer.set_value(routeOptions.customer);
        }
        frappe.route_options = null;
        if (this.controls.company.get_value() && this.controls.customer.get_value()) {
            this.refresh();
        }
    }

    async refresh() {
        const company = this.controls.company.get_value();
        const customer = this.controls.customer.get_value();
        if (!company || !customer) {
            this.render_empty("Select both company and customer to load the profile.");
            return;
        }

        this.render_loading();
        const response = await frappe.call({
            method: "snrg_credit_control.customer_credit_review.get_customer_detail",
            args: { company, customer },
        });
        this.data = response.message || null;
        this.render();
    }

    render_loading() {
        const skeletons = Array.from({ length: 6 }, () => `<div class="snrg-ccp-skeleton"></div>`).join("");
        this.wrapper.find(".snrg-ccp-card-grid").html(skeletons);
        this.wrapper.find(".snrg-ccp-main-metrics, .snrg-ccp-secondary-metrics, .snrg-ccp-invoices, .snrg-ccp-payments").html(`<div class="snrg-ccp-empty">Loading customer profile…</div>`);
    }

    render_empty(message) {
        this.wrapper.find(".snrg-ccp-meta").html("");
        this.wrapper.find(".snrg-ccp-card-grid").html(`<div class="snrg-ccp-empty">${frappe.utils.escape_html(message)}</div>`);
        this.wrapper.find(".snrg-ccp-main-metrics, .snrg-ccp-secondary-metrics, .snrg-ccp-invoices, .snrg-ccp-payments").html(`<div class="snrg-ccp-empty">${frappe.utils.escape_html(message)}</div>`);
    }

    render() {
        if (!this.data) {
            this.render_empty("No customer data found.");
            return;
        }
        this.render_meta();
        this.render_cards();
        this.render_metrics();
        this.render_invoices();
        this.render_payments();
    }

    render_meta() {
        const generated = this.data.generated_on ? frappe.datetime.str_to_user(this.data.generated_on) : frappe.datetime.now_datetime();
        this.wrapper.find(".snrg-ccp-meta").html(`
            <span class="snrg-ccp-chip">Customer: ${frappe.utils.escape_html(this.data.customer_code || "")}</span>
            <span class="snrg-ccp-chip">Group: ${frappe.utils.escape_html(this.data.customer_group || "-")}</span>
            <span class="snrg-ccp-chip">Scope: ${frappe.utils.escape_html(this.data.company || "")}</span>
            <span class="snrg-ccp-chip">Updated: ${frappe.utils.escape_html(generated)}</span>
        `);
    }

    render_cards() {
        const cards = [
            { label: "Current Outstanding", value: this.data.current_outstanding, datatype: "Currency", tone: "blue" },
            { label: "Credit Limit", value: this.data.current_credit_limit, datatype: "Currency", tone: "teal" },
            { label: "Remaining Limit", value: this.data.remaining_limit, datatype: "Currency", tone: "purple" },
            { label: "Recommended Limit", value: this.data.recommended_credit_limit, datatype: "Currency", tone: "amber" },
            { label: "Over Limit Amount", value: this.data.over_limit_amount, datatype: "Currency", tone: "red" },
            { label: "Collection Ratio", value: this.data.collection_ratio, datatype: "Percent", tone: "blue" },
        ];
        this.wrapper.find(".snrg-ccp-card-grid").html(cards.map((card) => `
            <div class="snrg-ccp-card" data-tone="${card.tone}">
                <div class="snrg-ccp-card-label">${frappe.utils.escape_html(card.label)}</div>
                <div class="snrg-ccp-card-value">${this.formatValue(card.value, card.datatype)}</div>
            </div>
        `).join(""));
    }

    render_metrics() {
        const primary = [
            ["Customer Name", this.data.customer_name, "Data"],
            ["Security Cheque", this.securityTag(this.data.security_cheque_available), "HTML"],
            ["Sales (Last 6M)", this.data.sales_last_6m, "Currency"],
            ["Payments (Last 6M)", this.data.payment_last_6m, "Currency"],
            ["Avg Monthly Payment", this.data.avg_monthly_payment, "Currency"],
            ["Credit Utilization", this.data.credit_utilization, "Percent"],
            ["Overdue Outstanding", this.data.overdue_outstanding, "Currency"],
            ["Not Yet Due", this.data.not_yet_due_outstanding, "Currency"],
            ["Open Invoices", this.data.open_invoice_count, "Int"],
            ["Gap vs Recommended", this.data.gap_vs_recommended, "Currency"],
        ];
        const secondary = [
            ["Months Used", this.data.months_used, "Float"],
            ["Days Since Cutoff", this.data.days_since_cutoff, "Int"],
            ["Max Days of AR", this.data.max_days_of_ar, "Int"],
            ["Last Sales Date", this.data.last_sales_date, "Date"],
            ["Days Since Last Invoice", this.data.days_since_last_invoice, "Int"],
            ["Last Payment Date", this.data.last_payment_date, "Date"],
            ["Days Since Last Payment", this.data.days_since_last_payment, "Int"],
        ];

        this.wrapper.find(".snrg-ccp-main-metrics").html(primary.map(([label, value, datatype]) => this.metricCard(label, value, datatype)).join(""));
        this.wrapper.find(".snrg-ccp-secondary-metrics").html(secondary.map(([label, value, datatype]) => this.metricCard(label, value, datatype)).join(""));
    }

    render_invoices() {
        const rows = this.data.recent_invoices || [];
        const html = rows.length ? rows.map((row) => `
            <div class="snrg-ccp-item">
                <div class="snrg-ccp-item-top">
                    <div>
                        <p class="snrg-ccp-item-title"><a href="/app/sales-invoice/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(row.name)}</a></p>
                        <div class="snrg-ccp-item-sub">${row.posting_date ? `Posted ${frappe.datetime.str_to_user(row.posting_date)}` : ""}${row.due_date ? ` · Due ${frappe.datetime.str_to_user(row.due_date)}` : ""}</div>
                    </div>
                    ${this.metricPill("Outstanding", this.formatValue(row.outstanding_amount, "Currency"))}
                </div>
                <div class="snrg-ccp-item-meta">
                    ${this.metricPill("Invoice", this.formatValue(row.invoice_amount, "Currency"))}
                    ${row.age_days != null ? this.metricPill("Age", `${row.age_days} days`) : ""}
                </div>
            </div>
        `).join("") : `<div class="snrg-ccp-empty">No invoices found for this customer in the selected company.</div>`;
        this.wrapper.find(".snrg-ccp-invoices").html(html);
    }

    render_payments() {
        const rows = this.data.recent_payments || [];
        const html = rows.length ? rows.map((row) => `
            <div class="snrg-ccp-item">
                <div class="snrg-ccp-item-top">
                    <div>
                        <p class="snrg-ccp-item-title"><a href="/app/payment-entry/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(row.name)}</a></p>
                        <div class="snrg-ccp-item-sub">${row.posting_date ? `Posted ${frappe.datetime.str_to_user(row.posting_date)}` : ""}${row.mode_of_payment ? ` · ${frappe.utils.escape_html(row.mode_of_payment)}` : ""}</div>
                    </div>
                    ${this.metricPill("Amount", this.formatValue(row.paid_amount, "Currency"))}
                </div>
                <div class="snrg-ccp-item-meta">
                    ${row.reference_no ? this.metricPill("Ref", frappe.utils.escape_html(row.reference_no)) : ""}
                </div>
            </div>
        `).join("") : `<div class="snrg-ccp-empty">No payment entries found for this customer in the selected company.</div>`;
        this.wrapper.find(".snrg-ccp-payments").html(html);
    }

    metricCard(label, value, datatype) {
        const rendered = datatype === "HTML" ? value : this.formatValue(value, datatype);
        return `
            <div class="snrg-ccp-metric">
                <div class="snrg-ccp-metric-label">${frappe.utils.escape_html(label)}</div>
                <div class="snrg-ccp-metric-value">${rendered}</div>
            </div>
        `;
    }

    metricPill(label, value) {
        return `<span class="snrg-ccp-pill">${frappe.utils.escape_html(label)}: ${value}</span>`;
    }

    securityTag(value) {
        const statusClass = value === "Yes" ? "yes" : "no";
        return `<span class="snrg-ccp-tag ${statusClass}">${frappe.utils.escape_html(value || "No")}</span>`;
    }

    formatValue(value, fieldtype) {
        if (value === null || value === undefined || value === "") {
            return `<span style="color:#94a3b8;">-</span>`;
        }
        if (fieldtype === "Currency") {
            return format_currency(value || 0, this.data?.currency || "INR");
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
