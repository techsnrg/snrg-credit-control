frappe.pages["ptp-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "PTP Dashboard",
        single_column: true,
    });

    wrapper.ptp_dashboard = new SnrgPTPDashboard(page, wrapper);
};

class SnrgPTPDashboard {
    constructor(page, wrapper) {
        this.page = page;
        this.wrapper = $(wrapper);
        this.view = "overview";
        this.calendarMonth = this.monthStart(new Date());
        this.upcomingSort = "date";
        this.data = null;
        this.controls = {};
        this.statusOptions = ["Pending", "Partially Cleared", "Cleared", "Broken", "Superseded"];
        this.bucketOptions = ["Due Today", "Overdue", "Upcoming This Week", "Partially Cleared", "Upcoming Later", "No Date"];

        this.setup();
    }

    setup() {
        this.page.set_primary_action("Refresh", () => this.refresh(), "refresh");
        this.render_shell();
        this.make_filters();
        this.bind_static_controls();
        this.refresh();
    }

    render_shell() {
        this.wrapper.find(".layout-main-section").html(`
            <style>
                .snrg-ptp-page {
                    display: flex;
                    flex-direction: column;
                    gap: 18px;
                }
                .snrg-ptp-topbar {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 16px;
                    flex-wrap: wrap;
                    margin-bottom: 14px;
                }
                .snrg-ptp-topbar-copy {
                    min-width: 0;
                }
                .snrg-ptp-kicker {
                    font-size: 11px;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: .08em;
                    font-weight: 700;
                }
                .snrg-ptp-panel {
                    border: 1px solid #e5e7eb;
                    border-radius: 18px;
                    background: linear-gradient(180deg, #ffffff 0%, #fbfcff 100%);
                    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                }
                .snrg-ptp-panel-body {
                    padding: 18px 20px;
                }
                .snrg-ptp-subtitle {
                    margin-top: 6px;
                    font-size: 14px;
                    color: #64748b;
                }
                .snrg-ptp-view-switch {
                    display: inline-flex;
                    gap: 8px;
                    background: #f8fafc;
                    padding: 6px;
                    border-radius: 999px;
                    border: 1px solid #e2e8f0;
                }
                .snrg-ptp-view-btn {
                    border: 0;
                    background: transparent;
                    color: #475569;
                    font-size: 13px;
                    font-weight: 700;
                    padding: 8px 14px;
                    border-radius: 999px;
                }
                .snrg-ptp-view-btn.active {
                    background: #0f172a;
                    color: #fff;
                }
                .snrg-ptp-filters {
                    display: grid;
                    grid-template-columns: repeat(7, minmax(0, 1fr));
                    gap: 12px;
                }
                .snrg-ptp-filter label {
                    font-size: 11px;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: .08em;
                    font-weight: 700;
                    margin-bottom: 6px;
                }
                .snrg-ptp-summary {
                    display: grid;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    gap: 12px;
                }
                .snrg-ptp-card {
                    border: 1px solid #e5e7eb;
                    border-radius: 16px;
                    background: #fff;
                    padding: 12px 13px;
                    min-height: 88px;
                }
                .snrg-ptp-card-label {
                    font-size: 10px;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: .08em;
                    font-weight: 700;
                }
                .snrg-ptp-card-value {
                    margin-top: 6px;
                    font-size: 18px;
                    line-height: 1.15;
                    font-weight: 800;
                    color: #0f172a;
                }
                .snrg-ptp-card-helper {
                    margin-top: 4px;
                    font-size: 11px;
                    color: #64748b;
                }
                .snrg-ptp-section-grid {
                    display: grid;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                    gap: 12px;
                }
                .snrg-ptp-section-title {
                    font-size: 18px;
                    font-weight: 800;
                    color: #0f172a;
                    margin-bottom: 12px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 12px;
                }
                .snrg-ptp-section-subtext {
                    margin-top: -6px;
                    margin-bottom: 12px;
                    font-size: 13px;
                    color: #64748b;
                }
                .snrg-ptp-list {
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                }
                .snrg-ptp-list-item {
                    border: 1px solid #e5e7eb;
                    border-radius: 14px;
                    background: #fff;
                    padding: 14px 16px;
                }
                .snrg-ptp-list-top {
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    gap: 12px;
                }
                .snrg-ptp-list-title {
                    font-size: 16px;
                    line-height: 1.25;
                    font-weight: 800;
                    color: #0f172a;
                }
                .snrg-ptp-list-meta {
                    margin-top: 6px;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                    font-size: 13px;
                    color: #475569;
                }
                .snrg-ptp-pill-row {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                    margin-top: 10px;
                }
                .snrg-ptp-pill {
                    display: inline-flex;
                    align-items: center;
                    padding: 6px 10px;
                    border-radius: 999px;
                    font-size: 12px;
                    line-height: 1;
                    font-weight: 700;
                    border: 1px solid #e2e8f0;
                    background: #f8fafc;
                    color: #475569;
                }
                .snrg-ptp-pill.status-pending { background: #fff7ed; color: #c2410c; border-color: #fed7aa; }
                .snrg-ptp-pill.status-partially-cleared { background: #ecfeff; color: #0f766e; border-color: #a5f3fc; }
                .snrg-ptp-pill.status-broken { background: #fef2f2; color: #b91c1c; border-color: #fecaca; }
                .snrg-ptp-pill.status-cleared { background: #ecfdf5; color: #047857; border-color: #bbf7d0; }
                .snrg-ptp-pill.status-superseded { background: #f8fafc; color: #64748b; border-color: #e2e8f0; }
                .snrg-ptp-action-row {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                    margin-top: 12px;
                }
                .snrg-ptp-link-btn {
                    border: 1px solid #dbe3ef;
                    border-radius: 999px;
                    background: #fff;
                    color: #1e293b;
                    padding: 7px 12px;
                    font-size: 12px;
                    font-weight: 700;
                    line-height: 1;
                }
                .snrg-ptp-link-btn:hover {
                    border-color: #94a3b8;
                    background: #f8fafc;
                }
                .snrg-ptp-table-wrap {
                    overflow-x: auto;
                }
                .snrg-ptp-table {
                    width: 100%;
                    border-collapse: separate;
                    border-spacing: 0;
                    min-width: 1040px;
                }
                .snrg-ptp-table th,
                .snrg-ptp-table td {
                    padding: 12px 14px;
                    border-bottom: 1px solid #edf2f7;
                    vertical-align: top;
                    text-align: left;
                    font-size: 13px;
                }
                .snrg-ptp-table th {
                    font-size: 11px;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: .08em;
                    font-weight: 800;
                    background: #f8fafc;
                    position: sticky;
                    top: 0;
                }
                .snrg-ptp-table strong {
                    color: #0f172a;
                }
                .snrg-ptp-calendar-toolbar {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 16px;
                    margin-bottom: 16px;
                }
                .snrg-ptp-calendar-nav {
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                }
                .snrg-ptp-calendar-title {
                    font-size: 24px;
                    font-weight: 800;
                    color: #0f172a;
                }
                .snrg-ptp-calendar-grid {
                    display: grid;
                    grid-template-columns: repeat(7, minmax(0, 1fr));
                    gap: 10px;
                }
                .snrg-ptp-calendar-grid.compact {
                    gap: 8px;
                }
                .snrg-ptp-calendar-day-name {
                    font-size: 11px;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: .08em;
                    font-weight: 800;
                    padding: 0 2px 4px;
                }
                .snrg-ptp-calendar-cell {
                    min-height: 132px;
                    border: 1px solid #e5e7eb;
                    border-radius: 16px;
                    background: #fff;
                    padding: 12px;
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }
                .snrg-ptp-calendar-cell.muted {
                    background: #f8fafc;
                    color: #94a3b8;
                }
                .snrg-ptp-calendar-date {
                    font-size: 14px;
                    font-weight: 800;
                    color: #0f172a;
                }
                .snrg-ptp-calendar-cell.muted .snrg-ptp-calendar-date {
                    color: #94a3b8;
                }
                .snrg-ptp-calendar-entry {
                    border-radius: 12px;
                    padding: 8px 10px;
                    font-size: 12px;
                    line-height: 1.35;
                    cursor: pointer;
                }
                .snrg-ptp-calendar-entry.status-pending { background: #eff6ff; color: #1d4ed8; }
                .snrg-ptp-calendar-entry.status-partially-cleared { background: #ecfeff; color: #0f766e; }
                .snrg-ptp-calendar-entry.status-broken { background: #fef2f2; color: #b91c1c; }
                .snrg-ptp-calendar-entry.status-cleared { background: #ecfdf5; color: #047857; }
                .snrg-ptp-calendar-entry.status-superseded { background: #f8fafc; color: #64748b; }
                .snrg-ptp-calendar-grid.compact .snrg-ptp-calendar-cell {
                    min-height: 96px;
                    padding: 10px;
                }
                .snrg-ptp-calendar-grid.compact .snrg-ptp-calendar-entry {
                    padding: 6px 8px;
                    font-size: 11px;
                }
                .snrg-ptp-calendar-grid.compact .snrg-ptp-calendar-day-name {
                    padding-bottom: 2px;
                }
                .snrg-ptp-muted {
                    color: #64748b;
                    font-size: 13px;
                }
                .snrg-ptp-total-row td {
                    background: #f8fafc;
                    font-weight: 700;
                    border-bottom: 0;
                }
                .snrg-ptp-mini-table-wrap {
                    max-height: 360px;
                    overflow: auto;
                    border: 1px solid #e5e7eb;
                    border-radius: 14px;
                    background: #fff;
                }
                .snrg-ptp-mini-table {
                    width: 100%;
                    border-collapse: separate;
                    border-spacing: 0;
                    min-width: 720px;
                }
                .snrg-ptp-mini-table th,
                .snrg-ptp-mini-table td {
                    padding: 10px 12px;
                    border-bottom: 1px solid #edf2f7;
                    font-size: 13px;
                    vertical-align: top;
                    text-align: left;
                }
                .snrg-ptp-mini-table th {
                    position: sticky;
                    top: 0;
                    background: #f8fafc;
                    z-index: 1;
                    font-size: 11px;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: .08em;
                    font-weight: 800;
                }
                .snrg-ptp-toolbar-inline {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 12px;
                    flex-wrap: wrap;
                    margin-bottom: 12px;
                }
                .hidden {
                    display: none !important;
                }
                @media (max-width: 1400px) {
                    .snrg-ptp-filters {
                        grid-template-columns: repeat(4, minmax(0, 1fr));
                    }
                    .snrg-ptp-summary {
                        grid-template-columns: repeat(2, minmax(0, 1fr));
                    }
                }
                @media (max-width: 900px) {
                    .snrg-ptp-section-grid,
                    .snrg-ptp-summary,
                    .snrg-ptp-filters,
                    .snrg-ptp-calendar-grid {
                        grid-template-columns: 1fr;
                    }
                    .snrg-ptp-topbar,
                    .snrg-ptp-calendar-toolbar,
                    .snrg-ptp-list-top {
                        flex-direction: column;
                        align-items: flex-start;
                    }
                }
            </style>
            <div class="snrg-ptp-page">
                <div class="snrg-ptp-panel">
                    <div class="snrg-ptp-panel-body">
                        <div class="snrg-ptp-topbar">
                            <div class="snrg-ptp-topbar-copy">
                                <div class="snrg-ptp-kicker">Credit Control</div>
                                <div class="snrg-ptp-subtitle">Track commitments, follow up faster, and keep the daily collection queue visible.</div>
                            </div>
                            <div class="snrg-ptp-view-switch">
                                <button class="snrg-ptp-view-btn active" data-view="overview" type="button">Overview</button>
                                <button class="snrg-ptp-view-btn" data-view="calendar" type="button">Calendar</button>
                            </div>
                        </div>
                        <div class="snrg-ptp-filters"></div>
                    </div>
                </div>
                <div class="snrg-ptp-overview-view"></div>
                <div class="snrg-ptp-calendar-view hidden"></div>
            </div>
        `);
    }

    make_filters() {
        const filterDefs = [
            { fieldname: "company", label: "Company", fieldtype: "Link", options: "Company" },
            { fieldname: "status", label: "Status", fieldtype: "Select", options: ["", ...this.statusOptions] },
            { fieldname: "bucket", label: "Bucket", fieldtype: "Select", options: ["", ...this.bucketOptions] },
            { fieldname: "ptp_by", label: "Committed By", fieldtype: "Link", options: "Employee" },
            { fieldname: "requested_to_employee", label: "Requested To", fieldtype: "Link", options: "Employee" },
            { fieldname: "date_range", label: "Date", fieldtype: "DateRange" },
            { fieldname: "show_superseded", label: "Show Superseded", fieldtype: "Check" },
        ];

        const target = this.wrapper.find(".snrg-ptp-filters");
        filterDefs.forEach((df) => {
            const fieldWrap = $(`<div class="snrg-ptp-filter"></div>`).appendTo(target);
            const control = frappe.ui.form.make_control({
                parent: fieldWrap,
                df: {
                    fieldname: df.fieldname,
                    label: df.label,
                    fieldtype: df.fieldtype,
                    options: Array.isArray(df.options) ? df.options.join("\n") : df.options,
                    default: df.fieldtype === "Check" ? 0 : undefined,
                    change: () => this.refresh(),
                },
                render_input: true,
            });
            control.refresh();
            this.controls[df.fieldname] = control;
        });
    }

    bind_static_controls() {
        this.wrapper.find(".snrg-ptp-view-btn").on("click", (e) => {
            const view = $(e.currentTarget).attr("data-view");
            if (!view || view === this.view) {
                return;
            }
            this.view = view;
            this.sync_view_state();
        });

        this.wrapper.on("change", "[data-upcoming-sort]", (e) => {
            const value = $(e.currentTarget).val();
            this.upcomingSort = value || "date";
            this.render_overview();
            this.bind_dynamic_controls();
        });
    }

    refresh() {
        frappe.call({
            method: "snrg_credit_control.ptp.get_ptp_dashboard_data",
            args: {
                filters: this.get_filters(),
                calendar_month: this.calendarMonth,
            },
            freeze: true,
            freeze_message: "Refreshing PTP dashboard...",
            callback: (r) => {
                this.data = r.message || null;
                this.render();
            },
        });
    }

    get_filters() {
        const filters = {};
        Object.keys(this.controls).forEach((fieldname) => {
            const value = this.controls[fieldname].get_value();
            if (!value) {
                return;
            }

            if (fieldname === "date_range") {
                const range = this.extractDateRange(value);
                if (range.from_date) {
                    filters.from_date = range.from_date;
                }
                if (range.to_date) {
                    filters.to_date = range.to_date;
                }
                if (range.from_date || range.to_date) {
                    filters.date_range = [range.from_date || "", range.to_date || ""];
                }
                return;
            }

            filters[fieldname] = value;
        });
        return filters;
    }

    render() {
        this.render_overview();
        this.render_calendar();
        this.sync_view_state();
        this.bind_dynamic_controls();
    }

    render_overview() {
        const target = this.wrapper.find(".snrg-ptp-overview-view");
        if (!this.data) {
            target.html(this.panel("Loading dashboard...", `<div class="snrg-ptp-muted">Fetching PTP data.</div>`));
            return;
        }

        const summary = this.data.summary || {};
        const sections = this.data.sections || {};
        const queue = this.data.queue || [];
        target.html(`
            ${this.panel("Snapshot", this.render_summary(summary))}
            ${this.panel("Action Boards", this.render_sections(sections))}
            ${this.panel("Full Queue", this.render_queue(queue))}
        `);
    }

    render_summary(summary) {
        const cards = [
            { label: "Due Today", value: summary.due_today || 0, helper: `Needs same-day follow-up (${format_currency(summary.due_today_amount || 0)})` },
            { label: "Due Tomorrow", value: summary.due_tomorrow || 0, helper: `Plan tomorrow's follow-up (${format_currency(summary.due_tomorrow_amount || 0)})` },
            { label: "Overdue", value: summary.overdue || 0, helper: `Past commitment date (${format_currency(summary.overdue_amount || 0)})` },
            { label: "Partially Cleared", value: summary.partially_cleared || 0, helper: "Received but still open" },
            { label: "Committed Amount", value: format_currency(summary.committed_amount || 0), helper: "Active committed total" },
            { label: "Received Amount", value: format_currency(summary.received_amount || 0), helper: "Recovered against active PTPs" },
            { label: "Gap Amount", value: format_currency(summary.difference_amount || 0), helper: "Still pending collection" },
        ];

        return `
            <div class="snrg-ptp-summary">
                ${cards.map((card) => `
                    <div class="snrg-ptp-card">
                        <div class="snrg-ptp-card-label">${this.esc(card.label)}</div>
                        <div class="snrg-ptp-card-value">${card.value}</div>
                        <div class="snrg-ptp-card-helper">${this.esc(card.helper)}</div>
                    </div>
                `).join("")}
            </div>
        `;
    }

    render_sections(sections) {
        const upcomingRows = this.getSortedUpcomingRows();
        return `
            <div class="snrg-ptp-section-grid">
                ${this.render_section_panel("Due Today", "Commitments that need follow-up today.", sections.due_today || [])}
                ${this.render_section_panel("Overdue", "Old commitments that have crossed their payment date.", sections.overdue || [])}
                <div style="grid-column:1 / -1;">${this.render_upcoming_week_panel(upcomingRows)}</div>
            </div>
        `;
    }

    render_upcoming_week_panel(rows) {
        const sortOptions = `
            <select data-upcoming-sort style="min-width:160px;padding:8px 12px;border:1px solid #dbe3ef;border-radius:999px;background:#fff;font-size:12px;font-weight:700;color:#1e293b;">
                <option value="date" ${this.upcomingSort === "date" ? "selected" : ""}>Sort: Date</option>
                <option value="amount" ${this.upcomingSort === "amount" ? "selected" : ""}>Sort: Amount</option>
            </select>
        `;
        const body = rows.length
            ? `
                <div class="snrg-ptp-mini-table-wrap">
                    <table class="snrg-ptp-mini-table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Amount</th>
                                <th>Customer</th>
                                <th>PTP</th>
                                <th>Sales Order</th>
                                <th>Committed By</th>
                                <th>Event</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rows.map((row) => `
                                <tr>
                                    <td>${row.commitment_date ? frappe.datetime.str_to_user(row.commitment_date) : "—"}</td>
                                    <td><strong>${format_currency(row.committed_amount || 0)}</strong></td>
                                    <td>${this.esc(row.customer_name || row.customer || "—")}</td>
                                    <td><button class="snrg-ptp-link-btn" type="button" data-route-doctype="Credit PTP" data-route-name="${this.esc(row.name)}">${this.esc(row.name)}</button></td>
                                    <td>${row.sales_order ? `<button class="snrg-ptp-link-btn" type="button" data-route-doctype="Sales Order" data-route-name="${this.esc(row.sales_order)}">${this.esc(row.sales_order)}</button>` : "—"}</td>
                                    <td>${this.esc(row.ptp_by_name || row.ptp_by || "—")}</td>
                                    <td>${row.calendar_event ? `<button class="snrg-ptp-link-btn" type="button" data-route-doctype="Event" data-route-name="${this.esc(row.calendar_event)}">${this.esc(row.calendar_event)}</button>` : `<span class="snrg-ptp-muted">Missing</span>`}</td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            `
            : `<div class="snrg-ptp-muted">Nothing upcoming this week right now.</div>`;

        return `
            <div class="snrg-ptp-card">
                <div class="snrg-ptp-section-title">Upcoming This Week</div>
                <div class="snrg-ptp-toolbar-inline">
                    <div class="snrg-ptp-section-subtext" style="margin:0;">Soon-to-mature commitments sorted for quick planning.</div>
                    ${sortOptions}
                </div>
                ${body}
            </div>
        `;
    }

    render_section_panel(title, subtitle, rows) {
        const body = rows.length
            ? `<div class="snrg-ptp-list">${rows.map((row) => this.render_list_item(row)).join("")}</div>`
            : `<div class="snrg-ptp-muted">Nothing to action here right now.</div>`;

        return `
            <div class="snrg-ptp-card">
                <div class="snrg-ptp-section-title">${this.esc(title)}</div>
                <div class="snrg-ptp-section-subtext">${this.esc(subtitle)}</div>
                ${body}
            </div>
        `;
    }

    render_list_item(row) {
        const issuePills = (row.issue_flags || []).map((issue) => `<span class="snrg-ptp-pill">${this.esc(issue)}</span>`).join("");
        return `
            <div class="snrg-ptp-list-item">
                <div class="snrg-ptp-list-top">
                    <div>
                        <div class="snrg-ptp-list-title">${this.esc(row.customer_name || row.customer || row.name)}</div>
                        <div class="snrg-ptp-list-meta">
                            <span>${this.esc(row.name)}</span>
                            <span>${this.esc(row.sales_order || "No Sales Order")}</span>
                            <span>${row.commitment_date ? frappe.datetime.str_to_user(row.commitment_date) : "No Date"}</span>
                        </div>
                    </div>
                    <div class="snrg-ptp-list-title">${format_currency(row.committed_amount || 0)}</div>
                </div>
                <div class="snrg-ptp-pill-row">
                    <span class="snrg-ptp-pill status-${this.slug(row.status)}">${this.esc(row.status || "Pending")}</span>
                    <span class="snrg-ptp-pill">${this.esc(row.bucket || "No Bucket")}</span>
                    <span class="snrg-ptp-pill">By: ${this.esc(row.ptp_by_name || row.ptp_by || "—")}</span>
                    ${row.calendar_event ? `<span class="snrg-ptp-pill">Event: ${this.esc(row.calendar_event)}</span>` : ""}
                    ${issuePills}
                </div>
                <div class="snrg-ptp-action-row">
                    <button class="snrg-ptp-link-btn" type="button" data-route-doctype="Credit PTP" data-route-name="${this.esc(row.name)}">Open PTP</button>
                    ${row.sales_order ? `<button class="snrg-ptp-link-btn" type="button" data-route-doctype="Sales Order" data-route-name="${this.esc(row.sales_order)}">Open Sales Order</button>` : ""}
                    ${row.calendar_event ? `<button class="snrg-ptp-link-btn" type="button" data-route-doctype="Event" data-route-name="${this.esc(row.calendar_event)}">Open Event</button>` : ""}
                </div>
            </div>
        `;
    }

    render_queue(rows) {
        if (!rows.length) {
            return `<div class="snrg-ptp-muted">No PTP records match the current filters.</div>`;
        }

        const totals = rows.reduce((acc, row) => {
            acc.committed += Number(row.committed_amount || 0);
            acc.received += Number(row.received_amount || 0);
            acc.gap += Number(row.difference_amount || 0);
            return acc;
        }, { committed: 0, received: 0, gap: 0 });

        return `
            <div class="snrg-ptp-table-wrap">
                <table class="snrg-ptp-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>PTP</th>
                            <th>Customer</th>
                            <th>Sales Order</th>
                            <th>Committed By</th>
                            <th>Requested To</th>
                            <th>Commitment Date</th>
                            <th>Status</th>
                            <th>Committed</th>
                            <th>Received</th>
                            <th>Gap</th>
                            <th>Event</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows.map((row, index) => `
                            <tr>
                                <td>${index + 1}</td>
                                <td><button class="snrg-ptp-link-btn" type="button" data-route-doctype="Credit PTP" data-route-name="${this.esc(row.name)}">${this.esc(row.name)}</button></td>
                                <td><strong>${this.esc(row.customer_name || row.customer || "—")}</strong><br><span class="snrg-ptp-muted">${this.esc(row.company || "")}</span></td>
                                <td>${row.sales_order ? `<button class="snrg-ptp-link-btn" type="button" data-route-doctype="Sales Order" data-route-name="${this.esc(row.sales_order)}">${this.esc(row.sales_order)}</button>` : "—"}</td>
                                <td>${this.esc(row.ptp_by_name || row.ptp_by || "—")}</td>
                                <td>${this.esc(row.requested_to_employee_name || row.requested_to_employee || "—")}</td>
                                <td>${row.commitment_date ? frappe.datetime.str_to_user(row.commitment_date) : "—"}<br><span class="snrg-ptp-muted">${this.esc(row.bucket || "")}</span></td>
                                <td><span class="snrg-ptp-pill status-${this.slug(row.status)}">${this.esc(row.status || "Pending")}</span></td>
                                <td>${format_currency(row.committed_amount || 0)}</td>
                                <td>${format_currency(row.received_amount || 0)}</td>
                                <td>${format_currency(row.difference_amount || 0)}</td>
                                <td>${row.calendar_event ? `<button class="snrg-ptp-link-btn" type="button" data-route-doctype="Event" data-route-name="${this.esc(row.calendar_event)}">${this.esc(row.calendar_event)}</button>` : `<span class="snrg-ptp-muted">Missing</span>`}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                    <tfoot>
                        <tr class="snrg-ptp-total-row">
                            <td colspan="8">Total</td>
                            <td>${format_currency(totals.committed)}</td>
                            <td>${format_currency(totals.received)}</td>
                            <td>${format_currency(totals.gap)}</td>
                            <td></td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        `;
    }

    render_calendar() {
        const target = this.wrapper.find(".snrg-ptp-calendar-view");
        if (!this.data || !this.data.calendar) {
            target.html(this.panel("Calendar", `<div class="snrg-ptp-muted">Loading month view.</div>`));
            return;
        }

        const calendarData = this.data.calendar;
        const calendarGrid = this.render_calendar_grid(calendarData);

        target.html(this.panel("Calendar", `
            <div class="snrg-ptp-calendar-toolbar">
                <div>
                    <div class="snrg-ptp-calendar-title">${this.esc(calendarData.month_label)}</div>
                    <div class="snrg-ptp-muted">Active and filtered PTP commitments for the selected month.</div>
                </div>
                <div class="snrg-ptp-calendar-nav">
                    <button class="snrg-ptp-link-btn" type="button" data-calendar-nav="prev">Prev</button>
                    <button class="snrg-ptp-link-btn" type="button" data-calendar-nav="today">Today</button>
                    <button class="snrg-ptp-link-btn" type="button" data-calendar-nav="next">Next</button>
                </div>
            </div>
            ${calendarGrid}
        `));
    }

    render_calendar_grid(calendarData, compact = false) {
        const month = calendarData.month;
        const year = calendarData.year;
        const daysInMonth = new Date(year, month, 0).getDate();
        const firstDay = new Date(year, month - 1, 1);
        const leadingDays = firstDay.getDay();
        const prevMonthDays = new Date(year, month - 1, 0).getDate();
        const entriesByDate = {};

        (calendarData.entries || []).forEach((entry) => {
            entriesByDate[entry.date] = entriesByDate[entry.date] || [];
            entriesByDate[entry.date].push(entry);
        });

        const cells = [];
        for (let i = leadingDays; i > 0; i -= 1) {
            const date = new Date(year, month - 2, prevMonthDays - i + 1);
            cells.push(this.render_calendar_cell(date, entriesByDate, true));
        }
        for (let day = 1; day <= daysInMonth; day += 1) {
            const date = new Date(year, month - 1, day);
            cells.push(this.render_calendar_cell(date, entriesByDate, false));
        }
        while (cells.length % 7 !== 0) {
            const nextDay = cells.length - (leadingDays + daysInMonth) + 1;
            const date = new Date(year, month, nextDay);
            cells.push(this.render_calendar_cell(date, entriesByDate, true));
        }

        const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
        return `
            <div class="snrg-ptp-calendar-grid ${compact ? "compact" : ""}">
                ${dayNames.map((label) => `<div class="snrg-ptp-calendar-day-name">${label}</div>`).join("")}
                ${cells.join("")}
            </div>
        `;
    }

    render_calendar_cell(date, entriesByDate, muted) {
        const dateKey = frappe.datetime.obj_to_str(date).slice(0, 10);
        const entries = entriesByDate[dateKey] || [];
        const visibleEntries = entries.slice(0, 2);
        const hiddenCount = Math.max(0, entries.length - visibleEntries.length);
        return `
            <div class="snrg-ptp-calendar-cell ${muted ? "muted" : ""}">
                <div class="snrg-ptp-calendar-date">${date.getDate()}</div>
                ${visibleEntries.map((entry) => `
                    <div class="snrg-ptp-calendar-entry status-${this.slug(entry.status)}" data-route-doctype="Credit PTP" data-route-name="${this.esc(entry.ptp)}">
                        <div><strong>${this.esc(entry.customer_name || entry.ptp)}</strong></div>
                        <div>${format_currency(entry.committed_amount || 0)}</div>
                    </div>
                `).join("")}
                ${hiddenCount ? `<div class="snrg-ptp-muted">+${hiddenCount} more</div>` : ""}
            </div>
        `;
    }

    getSortedUpcomingRows() {
        const rows = (this.data?.queue || []).filter((row) => row.bucket === "Upcoming This Week");
        return rows.sort((a, b) => {
            const dateA = a.commitment_date || "";
            const dateB = b.commitment_date || "";
            const amountA = Number(a.committed_amount || 0);
            const amountB = Number(b.committed_amount || 0);

            if (this.upcomingSort === "amount") {
                if (amountB !== amountA) return amountB - amountA;
                if (dateA !== dateB) return dateA.localeCompare(dateB);
                return (a.name || "").localeCompare(b.name || "");
            }

            if (dateA !== dateB) return dateA.localeCompare(dateB);
            if (amountB !== amountA) return amountB - amountA;
            return (a.name || "").localeCompare(b.name || "");
        });
    }

    sync_view_state() {
        this.wrapper.find(".snrg-ptp-view-btn").removeClass("active");
        this.wrapper.find(`.snrg-ptp-view-btn[data-view="${this.view}"]`).addClass("active");
        this.wrapper.find(".snrg-ptp-overview-view").toggleClass("hidden", this.view !== "overview");
        this.wrapper.find(".snrg-ptp-calendar-view").toggleClass("hidden", this.view !== "calendar");
    }

    bind_dynamic_controls() {
        this.wrapper.find("[data-route-doctype]").off("click").on("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            const doctype = $(e.currentTarget).attr("data-route-doctype");
            const name = $(e.currentTarget).attr("data-route-name");
            if (doctype && name) {
                frappe.set_route("Form", doctype, name);
            }
        });

        this.wrapper.find("[data-calendar-nav]").off("click").on("click", (e) => {
            const direction = $(e.currentTarget).attr("data-calendar-nav");
            if (!direction) {
                return;
            }
            if (direction === "today") {
                this.calendarMonth = this.monthStart(new Date());
            } else {
                const offset = direction === "next" ? 1 : -1;
                const current = new Date(this.calendarMonth);
                current.setMonth(current.getMonth() + offset);
                this.calendarMonth = this.monthStart(current);
            }
            this.refresh();
        });
    }

    panel(title, body) {
        return `
            <div class="snrg-ptp-panel">
                <div class="snrg-ptp-panel-body">
                    <div class="snrg-ptp-section-title">${this.esc(title)}</div>
                    ${body}
                </div>
            </div>
        `;
    }

    monthStart(date) {
        const value = new Date(date);
        value.setDate(1);
        value.setHours(0, 0, 0, 0);
        return frappe.datetime.obj_to_str(value).slice(0, 10);
    }

    extractDateRange(value) {
        if (!value) {
            return {};
        }

        if (Array.isArray(value) && value.length >= 2) {
            return {
                from_date: value[0] || "",
                to_date: value[1] || "",
            };
        }

        if (typeof value === "object") {
            return {
                from_date: value.from_date || value.from || value.start || "",
                to_date: value.to_date || value.to || value.end || "",
            };
        }

        if (typeof value === "string") {
            for (const separator of [",", " to ", " - ", "|"]) {
                if (value.includes(separator)) {
                    const parts = value.split(separator).map(part => part.trim()).filter(Boolean);
                    if (parts.length >= 2) {
                        return {
                            from_date: parts[0],
                            to_date: parts[1],
                        };
                    }
                }
            }
        }

        return {};
    }

    slug(value) {
        return String(value || "").trim().toLowerCase().replace(/\s+/g, "-");
    }

    esc(value) {
        return frappe.utils.escape_html(String(value == null ? "" : value));
    }
}
