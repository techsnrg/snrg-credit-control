frappe.pages["legal-desk"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Customer Desk",
    single_column: true,
  });

  const desk = new LegalDesk(page, wrapper);
  wrapper.legal_desk = desk;
};

class LegalDesk {
  constructor(page, wrapper) {
    this.page = page;
    this.wrapper = $(wrapper);
    this.currentCase = null;
    this.currentCustomer = null;
    this.currentContext = null;
    this.timelineRows = [];
    this.syncingCustomerFilter = false;
    this.activeSourceFilter = "All";
    this.manualActions = ["Call", "Visit", "Email", "WhatsApp", "Notice"];
    this.sourceFilters = [
      "All",
      "Communication",
      "Quotation",
      "Sales Invoice",
      "Payment",
      "Legal Workflow",
    ];

    this.setup();
  }

  setup() {
    this.page.set_primary_action("Refresh", () => this.refresh(), "refresh");
    this.render_shell();
    this.make_filters();
    this.read_route();
  }

  render_shell() {
    this.wrapper.find(".layout-main-section").html(`
      <style>
        .snrg-desk-page {
          display: flex;
          flex-direction: column;
          gap: 18px;
        }
        .snrg-desk-panel {
          border: 1px solid #e5e7eb;
          border-radius: 18px;
          background: linear-gradient(180deg, #ffffff 0%, #fbfcff 100%);
          box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        .snrg-desk-panel-body {
          padding: 18px 20px;
        }
        .snrg-desk-search-label {
          font-size: 12px;
          color: #64748b;
          text-transform: uppercase;
          letter-spacing: .08em;
          margin-bottom: 8px;
          font-weight: 700;
        }
        .snrg-desk-summary {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 12px;
        }
        .snrg-summary-card {
          border: 1px solid #e6ebf2;
          border-radius: 16px;
          background: #fff;
          padding: 16px;
          min-height: 96px;
        }
        .snrg-summary-label {
          font-size: 11px;
          color: #64748b;
          text-transform: uppercase;
          letter-spacing: .08em;
          font-weight: 700;
        }
        .snrg-summary-value {
          margin-top: 8px;
          font-size: 19px;
          line-height: 1.25;
          font-weight: 800;
          color: #0f172a;
        }
        .snrg-summary-helper {
          margin-top: 6px;
          font-size: 12px;
          color: #64748b;
        }
        .snrg-feed-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 18px;
          padding-bottom: 16px;
          border-bottom: 1px solid #edf1f7;
        }
        .snrg-feed-eyebrow {
          font-size: 12px;
          color: #64748b;
          text-transform: uppercase;
          letter-spacing: .08em;
          font-weight: 700;
        }
        .snrg-feed-title {
          margin-top: 6px;
          font-size: 28px;
          line-height: 1.15;
          font-weight: 800;
          color: #0f172a;
        }
        .snrg-feed-subtitle {
          margin-top: 8px;
          font-size: 14px;
          color: #64748b;
        }
        .snrg-feed-subtitle a {
          color: #2563eb;
          text-decoration: none;
          font-weight: 600;
        }
        .snrg-feed-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          justify-content: flex-end;
        }
        .snrg-pill {
          display: inline-flex;
          align-items: center;
          padding: 6px 10px;
          border-radius: 999px;
          font-size: 12px;
          line-height: 1;
          font-weight: 700;
          white-space: nowrap;
        }
        .snrg-pill-legal {
          background: #fff1f2;
          color: #be123c;
          border: 1px solid #fecdd3;
        }
        .snrg-pill-neutral {
          background: #f8fafc;
          color: #475569;
          border: 1px solid #e2e8f0;
        }
        .snrg-feed-toolbar {
          display: flex;
          flex-direction: column;
          gap: 12px;
          margin: 16px 0 18px;
        }
        .snrg-quick-actions,
        .snrg-source-filters {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
        .snrg-action-btn,
        .snrg-filter-chip {
          border-radius: 999px;
          border: 1px solid #dbe3ef;
          background: #fff;
          color: #1e293b;
          padding: 7px 14px;
          font-size: 13px;
          font-weight: 700;
          line-height: 1;
          transition: all .15s ease;
        }
        .snrg-action-btn:hover,
        .snrg-filter-chip:hover {
          border-color: #94a3b8;
          background: #f8fafc;
        }
        .snrg-filter-chip.active {
          background: #0f172a;
          color: #fff;
          border-color: #0f172a;
        }
        .snrg-timeline-rail {
          position: relative;
          margin-top: 4px;
          padding-left: 26px;
        }
        .snrg-timeline-rail::before {
          content: "";
          position: absolute;
          top: 8px;
          bottom: 8px;
          left: 8px;
          width: 2px;
          background: linear-gradient(180deg, #d7e3f7 0%, #e2e8f0 100%);
        }
        .snrg-timeline-item {
          position: relative;
          margin-bottom: 14px;
          border: 1px solid #e5e7eb;
          border-radius: 18px;
          background: #fff;
          padding: 16px 18px 16px 20px;
          box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
        }
        .snrg-timeline-dot {
          position: absolute;
          left: -25px;
          top: 22px;
          width: 12px;
          height: 12px;
          border-radius: 999px;
          border: 3px solid #fff;
          box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.2);
        }
        .snrg-timeline-topline {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 12px;
        }
        .snrg-timeline-title {
          font-size: 17px;
          font-weight: 800;
          line-height: 1.25;
          color: #0f172a;
        }
        .snrg-source-badge {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          padding: 5px 10px;
          font-size: 11px;
          line-height: 1;
          font-weight: 800;
          white-space: nowrap;
        }
        .snrg-source-communication {
          background: #ecfeff;
          color: #155e75;
        }
        .snrg-source-quotation {
          background: #eff6ff;
          color: #1d4ed8;
        }
        .snrg-source-invoice {
          background: #eef2ff;
          color: #4338ca;
        }
        .snrg-source-payment {
          background: #ecfdf5;
          color: #047857;
        }
        .snrg-source-legal {
          background: #fdf2f8;
          color: #be185d;
        }
        .snrg-timeline-meta {
          margin-top: 6px;
          font-size: 13px;
          color: #64748b;
        }
        .snrg-timeline-details {
          display: flex;
          flex-wrap: wrap;
          gap: 12px;
          margin-top: 10px;
          font-size: 14px;
        }
        .snrg-timeline-detail {
          color: #0f172a;
          font-weight: 600;
        }
        .snrg-timeline-remarks {
          margin-top: 10px;
          color: #475569;
          white-space: pre-wrap;
          line-height: 1.55;
        }
        .snrg-timeline-reference {
          margin-top: 12px;
        }
        .snrg-timeline-reference a {
          color: #2563eb;
          text-decoration: none;
          font-weight: 700;
        }
        @media (max-width: 1200px) {
          .snrg-desk-summary {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }
        @media (max-width: 768px) {
          .snrg-desk-summary {
            grid-template-columns: 1fr;
          }
          .snrg-feed-header {
            flex-direction: column;
          }
          .snrg-feed-meta {
            justify-content: flex-start;
          }
          .snrg-timeline-topline {
            flex-direction: column;
          }
        }
      </style>
      <div class="snrg-desk-page">
        <div class="snrg-desk-panel">
          <div class="snrg-desk-panel-body">
            <div class="snrg-desk-search-label">Open Customer Thread</div>
            <div class="legal-desk-filter"></div>
          </div>
        </div>
        <div class="legal-desk-summary snrg-desk-summary"></div>
        <div class="legal-desk-timeline-panel"></div>
      </div>
    `);
  }

  make_filters() {
    const target = this.wrapper.find(".legal-desk-filter");
    this.customerFilter = frappe.ui.form.make_control({
      parent: target,
      df: {
        label: "Customer",
        fieldname: "customer",
        fieldtype: "Link",
        options: "Customer",
        placeholder: "Select a Customer",
        change: () => {
          if (this.syncingCustomerFilter) {
            return;
          }
          this.currentCustomer = this.customerFilter.get_value();
          this.currentCase = null;
          this.currentContext = null;
          this.activeSourceFilter = "All";
          this.refresh();
        },
      },
      render_input: true,
    });
    this.customerFilter.refresh();
  }

  read_route() {
    const route = frappe.get_route();
    const routeOptions = frappe.route_options || {};

    if (routeOptions.customer) {
      this.currentCustomer = routeOptions.customer;
      frappe.route_options = null;
      this.refresh();
      return;
    }

    if (routeOptions.legal_case) {
      this.currentCase = routeOptions.legal_case;
      this.loadCustomerFromCase(routeOptions.legal_case, () => this.refresh());
      frappe.route_options = null;
      return;
    }

    if (route.length > 1 && route[1]) {
      if ((route[1] || "").startsWith("LC-")) {
        this.currentCase = route[1];
        this.loadCustomerFromCase(route[1], () => this.refresh());
      } else {
        this.currentCustomer = route[1];
        this.refresh();
      }
      return;
    }

    this.render_empty_state();
  }

  refresh() {
    if (!this.currentCustomer && !this.currentCase) {
      this.render_empty_state();
      return;
    }

    this.set_loading_state();

    frappe.call({
      method: "snrg_credit_control.customer_communication.get_customer_desk_context",
      args: { customer: this.currentCustomer },
      callback: (r) => {
        const context = r.message;
        if (!context) {
          this.render_empty_state("Unable to load this customer's communication feed.");
          return;
        }

        this.currentContext = context;
        this.currentCase = context.legal_case ? context.legal_case.name : null;
        this.currentCustomer = context.customer.name;

        if (this.customerFilter && this.customerFilter.get_value() !== context.customer.name) {
          this.syncingCustomerFilter = true;
          this.customerFilter.set_value(context.customer.name);
          this.syncingCustomerFilter = false;
        }

        this.render_summary(context.customer, context.legal_case);
        this.render_timeline(context.timeline || []);
      },
      error: () => {
        this.render_empty_state("Unable to load Customer Desk right now.");
      },
    });
  }

  set_loading_state() {
    this.wrapper.find(".legal-desk-summary").html(this.render_loading_cards());
    this.wrapper
      .find(".legal-desk-timeline-panel")
      .html(this.panel("Communication Feed", `<div class="text-muted">Loading activity feed...</div>`));
  }

  render_empty_state(message) {
    this.currentContext = null;
    this.timelineRows = [];
    const text = message || "Select a Customer to open the communication desk view.";
    this.wrapper.find(".legal-desk-summary").html("");
    this.wrapper
      .find(".legal-desk-timeline-panel")
      .html(this.panel("Communication Feed", `<div class="text-muted">${text}</div>`));
  }

  render_summary(customer, legalCase) {
    const cards = [
      {
        label: "Current Outstanding",
        value: format_currency(customer.current_outstanding_balance || 0),
      },
      {
        label: "Legal Status",
        value: legalCase ? legalCase.status || "Under Legal" : "Not in Legal",
      },
      {
        label: "Assigned Counsel",
        value: legalCase ? legalCase.assigned_counsel || "-" : "-",
      },
      {
        label: "Last Communication",
        value: customer.last_communication_at
          ? frappe.datetime.str_to_user(customer.last_communication_at)
          : "-",
      },
      {
        label: "Last Payment",
        value: customer.last_payment_date
          ? frappe.datetime.str_to_user(customer.last_payment_date)
          : "-",
      },
      {
        label: "Action Due By",
        value: legalCase
          ? this.formatDateWithReason(
              legalCase.next_action_due_by,
              legalCase.next_action_due_by_reason
            )
          : "-",
      },
      {
        label: "Action On Or After",
        value: legalCase
          ? this.formatDateWithReason(
              legalCase.next_action_on_or_after,
              legalCase.next_action_on_or_after_reason
            )
          : "-",
      },
      {
        label: "Original Legal Amount",
        value: legalCase
          ? format_currency(legalCase.original_legal_amount || 0)
          : "-",
      },
    ];

    this.wrapper.find(".legal-desk-summary").html(
      cards
        .map(
          (card) => `
            <div class="snrg-summary-card">
              <div class="snrg-summary-label">${frappe.utils.escape_html(card.label)}</div>
              <div class="snrg-summary-value">${card.value}</div>
            </div>
          `
        )
        .join("")
    );
  }

  render_timeline(rows) {
    this.timelineRows = rows || [];
    const filteredRows = this.get_filtered_rows();
    const body = filteredRows.length
      ? `<div class="snrg-timeline-rail">
           ${filteredRows.map((row) => this.timeline_item(row)).join("")}
         </div>`
      : `<div class="text-muted">No activity matches this feed filter yet.</div>`;

    this.wrapper.find(".legal-desk-timeline-panel").html(
      this.panel(
        "Communication Feed",
        `
          ${this.render_feed_header()}
          ${this.render_feed_controls()}
          ${body}
        `
      )
    );

    this.bind_controls();
  }

  render_feed_controls() {
    return `
      <div class="snrg-feed-toolbar">
        <div class="snrg-quick-actions">
          ${this.manualActions
            .map((label) => {
              const safeLabel = frappe.utils.escape_html(label);
              return `
                <button
                  class="snrg-action-btn legal-desk-action"
                  type="button"
                  data-activity-type="${safeLabel}"
                  ${!this.currentCustomer ? "disabled" : ""}
                >
                  ${safeLabel}
                </button>
              `;
            })
            .join("")}
        </div>
        <div class="snrg-source-filters">
          ${this.sourceFilters
            .map((label) => {
              const safeLabel = frappe.utils.escape_html(label);
              const active = label === this.activeSourceFilter ? "active" : "";
              return `
                <button
                  class="snrg-filter-chip legal-desk-filter-chip ${active}"
                  type="button"
                  data-source-filter="${safeLabel}"
                >
                  ${safeLabel}
                </button>
              `;
            })
            .join("")}
        </div>
      </div>
    `;
  }

  bind_controls() {
    this.wrapper.find(".legal-desk-action").off("click").on("click", (e) => {
      const activityType = $(e.currentTarget).attr("data-activity-type");
      if (!activityType) {
        return;
      }
      this.open_action_dialog(activityType);
    });

    this.wrapper.find(".legal-desk-filter-chip").off("click").on("click", (e) => {
      const filter = $(e.currentTarget).attr("data-source-filter");
      if (!filter || filter === this.activeSourceFilter) {
        return;
      }
      this.activeSourceFilter = filter;
      this.render_timeline(this.timelineRows);
    });
  }

  open_action_dialog(activityType) {
    if (!this.currentCustomer) {
      frappe.msgprint("Select a customer first.");
      return;
    }

    const dialog = new frappe.ui.Dialog({
      title: `Log ${activityType}`,
      fields: [
        {
          fieldname: "communication_at",
          fieldtype: "Datetime",
          label: "Communication At",
          reqd: 1,
          default: frappe.datetime.now_datetime(),
        },
        {
          fieldname: "remarks",
          fieldtype: "Small Text",
          label: "Remarks",
          reqd: 1,
        },
      ],
      primary_action_label: "Log Action",
      primary_action: (values) => {
        frappe.call({
          method: "snrg_credit_control.customer_communication.log_customer_communication",
          args: {
            customer: this.currentCustomer,
            communication_type: activityType,
            communication_at: values.communication_at,
            remarks: values.remarks,
          },
          freeze: true,
          freeze_message: "Logging communication...",
          callback: () => {
            dialog.hide();
            this.refresh();
          },
        });
      },
    });

    dialog.show();
  }

  get_filtered_rows() {
    if (this.activeSourceFilter === "All") {
      return this.timelineRows;
    }
    return this.timelineRows.filter(
      (row) => (row.source_label || "") === this.activeSourceFilter
    );
  }

  timeline_item(row) {
    const theme = this.get_source_theme(row.source_label);
    const details = [];

    if (row.amount) {
      details.push(
        `<span class="snrg-timeline-detail">Amount: ${format_currency(row.amount)}</span>`
      );
    }

    if (row.reference_route && row.reference_doctype && row.reference_name) {
      details.push(
        `<span class="snrg-timeline-detail"><a href="${row.reference_route}" style="color:#2563eb; text-decoration:none;">${frappe.utils.escape_html(
          row.reference_doctype
        )}: ${frappe.utils.escape_html(row.reference_name)}</a></span>`
      );
    }

    const remarks = row.remarks
      ? `<div class="snrg-timeline-remarks">${frappe.utils.escape_html(row.remarks)}</div>`
      : "";

    const meta = [
      row.performed_by ? `By ${frappe.utils.escape_html(row.performed_by)}` : "",
      row.activity_date || row.display_timestamp
        ? this.formatDate(row.activity_date || row.display_timestamp)
        : "",
      row.display_timestamp ? this.formatTime(row.display_timestamp) : "",
    ]
      .filter(Boolean)
      .join(" | ");

    return `
      <div class="snrg-timeline-item">
        <div class="snrg-timeline-dot" style="background:${theme.dotColor};"></div>
        <div class="snrg-timeline-topline">
          <div class="snrg-timeline-title">${frappe.utils.escape_html(
            row.activity_type || "Activity"
          )}</div>
          <span class="snrg-source-badge ${theme.badgeClass}">${frappe.utils.escape_html(
            row.source_label || "Activity"
          )}</span>
        </div>
        <div class="snrg-timeline-meta">${meta}</div>
        ${details.length ? `<div class="snrg-timeline-details">${details.join("")}</div>` : ""}
        ${remarks}
      </div>
    `;
  }

  panel(title, body) {
    return `
      <div class="snrg-desk-panel">
        <div class="snrg-desk-panel-body">
          <div style="font-size:18px; font-weight:800; color:#0f172a; margin-bottom:14px;">${frappe.utils.escape_html(
            title
          )}</div>
          ${body}
        </div>
      </div>
    `;
  }

  render_loading_cards() {
    return Array.from({ length: 8 })
      .map(
        () => `
          <div class="snrg-summary-card">
            <div class="text-muted">Loading...</div>
          </div>
        `
      )
      .join("");
  }

  render_feed_header() {
    if (!this.currentContext || !this.currentCustomer) {
      return "";
    }

    const customer = frappe.utils.escape_html(
      this.currentContext.customer.display_name || this.currentCustomer || "-"
    );
    const company = frappe.utils.escape_html(this.currentContext.customer.company || "-");
    const caseName = frappe.utils.escape_html(this.currentCase || "");

    return `
      <div class="snrg-feed-header">
        <div>
          <div class="snrg-feed-eyebrow">Customer Thread</div>
          <div class="snrg-feed-title">${customer}</div>
          <div class="snrg-feed-subtitle">
            ${company}
            ${
              this.currentCase
                ? ` · Legal Case <a href="/app/legal-case/${caseName}">${caseName}</a>`
                : " · Customer communication feed"
            }
          </div>
        </div>
        <div class="snrg-feed-meta">
          <span class="snrg-pill ${this.currentCase ? "snrg-pill-legal" : "snrg-pill-neutral"}">
            ${this.currentCase ? "Under Legal" : "Regular Follow-up"}
          </span>
          ${
            this.currentContext.legal_case && this.currentContext.legal_case.assigned_counsel
              ? `<span class="snrg-pill snrg-pill-neutral">Counsel: ${frappe.utils.escape_html(
                  this.currentContext.legal_case.assigned_counsel
                )}</span>`
              : ""
          }
        </div>
      </div>
    `;
  }

  formatDateWithReason(date, reason) {
    if (!date) {
      return "-";
    }
    const dateLabel = frappe.datetime.str_to_user(date);
    const safeReason = reason
      ? `<div class="snrg-summary-helper">${frappe.utils.escape_html(reason)}</div>`
      : "";
    return `<div>${dateLabel}</div>${safeReason}`;
  }

  formatTime(datetimeValue) {
    if (!datetimeValue) {
      return "";
    }
    const userValue = frappe.datetime.str_to_user(datetimeValue);
    const parts = userValue.split(" ");
    return parts.length > 1 ? parts.slice(1).join(" ") : userValue;
  }

  formatDate(value) {
    if (!value) {
      return "";
    }
    const userValue = frappe.datetime.str_to_user(value);
    return userValue.split(" ")[0] || userValue;
  }

  get_source_theme(sourceLabel) {
    const source = sourceLabel || "";
    if (source === "Communication") {
      return { badgeClass: "snrg-source-communication", dotColor: "#0891b2" };
    }
    if (source === "Quotation") {
      return { badgeClass: "snrg-source-quotation", dotColor: "#2563eb" };
    }
    if (source === "Sales Invoice") {
      return { badgeClass: "snrg-source-invoice", dotColor: "#4f46e5" };
    }
    if (source === "Payment") {
      return { badgeClass: "snrg-source-payment", dotColor: "#059669" };
    }
    return { badgeClass: "snrg-source-legal", dotColor: "#db2777" };
  }

  loadCustomerFromCase(legalCase, callback) {
    frappe.db.get_value("Legal Case", legalCase, "customer").then((r) => {
      const customer = r.message && r.message.customer;
      if (!customer) {
        return;
      }
      this.currentCustomer = customer;
      if (this.customerFilter && this.customerFilter.get_value() !== customer) {
        this.syncingCustomerFilter = true;
        this.customerFilter.set_value(customer);
        this.syncingCustomerFilter = false;
      }
      if (callback) {
        callback();
      }
    });
  }
}
