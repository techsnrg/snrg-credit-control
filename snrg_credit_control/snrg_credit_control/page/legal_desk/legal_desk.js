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
    this.syncingCustomerFilter = false;
    this.manualActions = [
      "Call",
      "Visit",
      "Email",
      "WhatsApp",
      "Notice",
    ];

    this.setup();
  }

  setup() {
    this.page.set_primary_action("Refresh", () => this.refresh(), "refresh");
    this.render_shell();
    this.make_filters();
    this.read_route();
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
        this.refresh();
      },
      },
      render_input: true,
    });
    this.customerFilter.refresh();
  }

  render_shell() {
    this.wrapper.find(".layout-main-section").html(`
      <div class="legal-desk-page">
        <div style="border:1px solid #e5e7eb; border-radius:14px; background:#fff; padding:16px 18px; margin-bottom:16px;">
          <div style="font-size:12px; color:#6b7280; text-transform:uppercase; letter-spacing:.04em; margin-bottom:8px;">Open Customer Thread</div>
          <div class="legal-desk-filter"></div>
        </div>
        <div class="legal-desk-summary" style="display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 20px;"></div>
        <div class="legal-desk-timeline-panel"></div>
      </div>
    `);
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
      args: {
        customer: this.currentCustomer,
      },
      callback: (r) => {
        const context = r.message;
        if (!context) {
          this.render_empty_state("Unable to load this customer's communication feed.");
          return;
        }

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
    this.wrapper.find(".legal-desk-timeline-panel").html(this.panel("Communication Feed", `<div class="text-muted">Loading activity feed...</div>`));
  }

  render_empty_state(message) {
    const text = message || "Select a Customer to open the communication desk view.";
    this.wrapper.find(".legal-desk-summary").html("");
    this.wrapper.find(".legal-desk-timeline-panel").html(this.panel("Communication Feed", `<div class="text-muted">${text}</div>`));
  }

  render_summary(customer, legalCase) {
    const cards = [
      ["Current Outstanding", format_currency(customer.current_outstanding_balance || 0)],
      ["Legal Status", legalCase ? legalCase.status || "Under Legal" : "Not in Legal"],
      ["Assigned Counsel", legalCase ? legalCase.assigned_counsel || "-" : "-"],
      ["Last Communication", customer.last_communication_at ? frappe.datetime.str_to_user(customer.last_communication_at) : "-"],
      ["Last Payment", customer.last_payment_date ? frappe.datetime.str_to_user(customer.last_payment_date) : "-"],
      ["Action Due By", legalCase ? this.formatDateWithReason(legalCase.next_action_due_by, legalCase.next_action_due_by_reason) : "-"],
      ["Action On Or After", legalCase ? this.formatDateWithReason(legalCase.next_action_on_or_after, legalCase.next_action_on_or_after_reason) : "-"],
      ["Original Legal Amount", legalCase ? format_currency(legalCase.original_legal_amount || 0) : "-"],
    ];

    this.wrapper.find(".legal-desk-summary").html(
      cards
        .map(
          ([label, value]) => `
            <div style="border:1px solid #e5e7eb; border-radius:12px; padding:14px 16px; background:#fff;">
              <div style="font-size:12px; color:#6b7280; text-transform:uppercase; letter-spacing:.04em;">${frappe.utils.escape_html(label)}</div>
              <div style="margin-top:6px; font-size:16px; font-weight:700; color:#111827;">${value}</div>
            </div>
          `
        )
        .join("")
    );
  }

  render_timeline(rows) {
    const actionStrip = this.render_action_strip();
    const body = rows.length
      ? `<div style="position: relative; margin: 8px 0 4px 0; padding-left: 14px;">
           <div style="position: absolute; left: 4px; top: 8px; bottom: 8px; width: 2px; background: #dbe3f0;"></div>
           ${rows.map((row) => this.timeline_item(row)).join("")}
         </div>`
      : `<div class="text-muted">No communication has been logged for this customer yet.</div>`;

    this.wrapper.find(".legal-desk-timeline-panel").html(
      this.panel(
        "Communication Feed",
        `${this.render_feed_header()}${actionStrip}${body}`
      )
    );
    this.bind_action_strip();
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

  timeline_item(row) {
    const amount = row.amount
      ? `<div style="margin-top: 6px; font-weight: 600; color: #1f2937;">Amount: ${format_currency(row.amount)}</div>`
      : "";
    const source = row.source_label
      ? `<span style="display:inline-flex; align-items:center; margin-top:6px; padding:3px 8px; border-radius:999px; background:#eef2ff; color:#4338ca; font-size:11px; font-weight:700;">${frappe.utils.escape_html(row.source_label)}</span>`
      : "";
    const remarks = row.remarks
      ? `<div style="margin-top: 6px; color: #4b5563; white-space: pre-wrap;">${frappe.utils.escape_html(row.remarks)}</div>`
      : "";
    const reference = row.reference_route
      ? `<div style="margin-top: 6px;"><a href="${row.reference_route}" style="color: #2563eb; text-decoration: none;">${frappe.utils.escape_html(row.reference_doctype)}: ${frappe.utils.escape_html(row.reference_name)}</a></div>`
      : "";
    const meta = [
      row.performed_by ? `By ${frappe.utils.escape_html(row.performed_by)}` : "",
      row.activity_date || row.display_timestamp ? this.formatDate(row.activity_date || row.display_timestamp) : "",
      row.display_timestamp ? this.formatTime(row.display_timestamp) : "",
    ]
      .filter(Boolean)
      .join(" | ");

    return `
      <div style="position: relative; margin: 0 0 14px 18px; padding: 12px 14px; border: 1px solid #e5e7eb; border-radius: 10px; background: #fff;">
        <div style="position: absolute; left: -23px; top: 16px; width: 10px; height: 10px; border-radius: 999px; background: #2563eb;"></div>
        <div style="font-weight: 700; color: #111827;">${frappe.utils.escape_html(row.activity_type || "Activity")}</div>
        <div style="margin-top: 2px; font-size: 12px; color: #6b7280;">${meta}</div>
        ${source}
        ${amount}
        ${remarks}
        ${reference}
      </div>
    `;
  }

  panel(title, body) {
    return `
      <div style="border:1px solid #e5e7eb; border-radius:14px; background:#fff; padding:16px 18px; height:100%;">
        <div style="font-size:16px; font-weight:700; color:#111827; margin-bottom:12px;">${frappe.utils.escape_html(title)}</div>
        ${body}
      </div>
    `;
  }

  render_loading_cards() {
    return Array.from({ length: 4 })
      .map(
        () => `
          <div style="border:1px solid #e5e7eb; border-radius:12px; padding:14px 16px; background:#fff;">
            <div class="text-muted">Loading...</div>
          </div>
        `
      )
      .join("");
  }

  formatDateWithReason(date, reason) {
    if (!date) {
      return "-";
    }
    const dateLabel = frappe.datetime.str_to_user(date);
    const safeReason = reason ? `<div style="margin-top:4px; font-size:12px; color:#6b7280; font-weight:400;">${frappe.utils.escape_html(reason)}</div>` : "";
    return `<div>${dateLabel}</div>${safeReason}`;
  }

  render_action_strip() {
    const disabled = !this.currentCustomer;
    return `
      <div style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px;">
        ${this.manualActions
          .map((label) => {
            const safeLabel = frappe.utils.escape_html(label);
            return `
              <button
                class="btn btn-default btn-sm legal-desk-action"
                type="button"
                data-activity-type="${safeLabel}"
                ${disabled ? "disabled" : ""}
                style="border-radius:999px; padding:6px 12px;"
              >
                ${safeLabel}
              </button>
            `;
          })
          .join("")}
      </div>
    `;
  }

  bind_action_strip() {
    this.wrapper.find(".legal-desk-action").off("click").on("click", (e) => {
      const activityType = $(e.currentTarget).attr("data-activity-type");
      if (!activityType) {
        return;
      }
      this.open_action_dialog(activityType);
    });
  }

  render_feed_header() {
    if (!this.currentCustomer) {
      return "";
    }

    const caseName = frappe.utils.escape_html(this.currentCase || "");
    const customer = frappe.utils.escape_html(this.currentCustomer || "-");

    return `
      <div style="display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:space-between; margin-bottom:14px; padding-bottom:12px; border-bottom:1px solid #eef2f7;">
        <div>
          <div style="font-size:12px; color:#6b7280; text-transform:uppercase; letter-spacing:.04em;">Active Thread</div>
          <div style="margin-top:4px; font-size:15px; font-weight:700; color:#111827;">${customer}</div>
          <div style="margin-top:2px; font-size:13px; color:#6b7280;">
            ${this.currentCase ? `Legal Case: <a href="/app/legal-case/${caseName}" style="color:#2563eb; text-decoration:none;">${caseName}</a>` : "Customer communication feed"}
          </div>
        </div>
      </div>
    `;
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
