frappe.pages["legal-desk"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Legal Desk",
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
    this.manualActions = [
      "Call Made",
      "Visit Done",
      "Email Sent",
      "WhatsApp Sent",
      "Meeting Held",
      "Settlement Discussed",
      "Counsel Note Added",
    ];

    this.setup();
  }

  setup() {
    this.page.set_primary_action("Refresh", () => this.refresh(), "refresh");
    this.make_actions_menu();
    this.render_shell();
    this.make_filters();
    this.read_route();
  }

  make_filters() {
    const target = this.wrapper.find(".legal-desk-filter");
    this.caseFilter = frappe.ui.form.make_control({
      parent: target,
      df: {
      label: "Legal Case",
      fieldname: "legal_case",
      fieldtype: "Link",
      options: "Legal Case",
      placeholder: "Select a Legal Case",
      change: () => {
        this.currentCase = this.caseFilter.get_value();
        this.refresh();
      },
      },
      render_input: true,
    });
    this.caseFilter.refresh();
  }

  make_actions_menu() {
    this.manualActions.forEach((label) => {
      this.page.add_menu_item(label, () => this.open_action_dialog(label));
    });
  }

  render_shell() {
    this.wrapper.find(".layout-main-section").html(`
      <div class="legal-desk-page">
        <div style="border:1px solid #e5e7eb; border-radius:14px; background:#fff; padding:16px 18px; margin-bottom:16px;">
          <div style="font-size:12px; color:#6b7280; text-transform:uppercase; letter-spacing:.04em; margin-bottom:8px;">Open Legal Case</div>
          <div class="legal-desk-filter"></div>
        </div>
        <div class="legal-desk-summary" style="display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 20px;"></div>
        <div style="display:grid; grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr); gap: 16px;">
          <div class="legal-desk-timeline-panel"></div>
          <div class="legal-desk-side-panel"></div>
        </div>
      </div>
    `);
  }

  read_route() {
    const route = frappe.get_route();
    const routeOptions = frappe.route_options || {};

    if (routeOptions.legal_case) {
      this.currentCase = routeOptions.legal_case;
      this.caseFilter.set_value(routeOptions.legal_case);
      frappe.route_options = null;
      this.refresh();
      return;
    }

    if (route.length > 1 && route[1]) {
      this.currentCase = route[1];
      this.caseFilter.set_value(route[1]);
      this.refresh();
      return;
    }

    this.render_empty_state();
  }

  refresh() {
    if (!this.currentCase) {
      this.render_empty_state();
      return;
    }

    this.set_loading_state();

    frappe.call({
      method: "snrg_credit_control.legal_case.get_legal_desk_context",
      args: {
        legal_case: this.currentCase,
      },
      callback: (r) => {
        const context = r.message;
        if (!context) {
          this.render_empty_state("Unable to load this legal case.");
          return;
        }

        this.render_summary(context.case);
        this.render_timeline(context.timeline || []);
        this.render_side_panel(context.case, context.notices || []);
      },
      error: () => {
        this.render_empty_state("Unable to load Legal Desk right now.");
      },
    });
  }

  set_loading_state() {
    this.wrapper.find(".legal-desk-summary").html(this.render_loading_cards());
    this.wrapper.find(".legal-desk-timeline-panel").html(this.panel("Timeline", `<div class="text-muted">Loading timeline...</div>`));
    this.wrapper.find(".legal-desk-side-panel").html(this.panel("Case Details", `<div class="text-muted">Loading case details...</div>`));
  }

  render_empty_state(message) {
    const text = message || "Select a Legal Case to open its desk view.";
    this.wrapper.find(".legal-desk-summary").html("");
    this.wrapper.find(".legal-desk-timeline-panel").html(this.panel("Timeline", `<div class="text-muted">${text}</div>`));
    this.wrapper.find(".legal-desk-side-panel").html(this.panel("Case Details", `<div class="text-muted">${text}</div>`));
  }

  render_summary(legalCase) {
    const cards = [
      ["Status", legalCase.status || "-"],
      ["Assigned Counsel", legalCase.assigned_counsel || "-"],
      ["Original Legal Amount", format_currency(legalCase.original_legal_amount || 0)],
      ["Current Outstanding", format_currency(legalCase.current_outstanding_balance || 0)],
      ["Recovered", format_currency(legalCase.amount_recovered || 0)],
      ["Action Due By", this.formatDateWithReason(legalCase.next_action_due_by, legalCase.next_action_due_by_reason)],
      ["Action On Or After", this.formatDateWithReason(legalCase.next_action_on_or_after, legalCase.next_action_on_or_after_reason)],
      ["Last Activity", legalCase.last_activity_date ? frappe.datetime.str_to_user(legalCase.last_activity_date) : "-"],
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
    const body = rows.length
      ? `<div style="position: relative; margin: 8px 0 4px 0; padding-left: 14px;">
           <div style="position: absolute; left: 4px; top: 8px; bottom: 8px; width: 2px; background: #dbe3f0;"></div>
           ${rows.map((row) => this.timeline_item(row)).join("")}
         </div>`
      : `<div class="text-muted">No activity has been logged for this legal case yet.</div>`;

    this.wrapper.find(".legal-desk-timeline-panel").html(this.panel("Timeline", body));
  }

  render_side_panel(legalCase, notices) {
    const noticeList = notices.length
      ? notices
          .map(
            (notice) => `
              <div style="padding:10px 0; border-bottom:1px solid #eef2f7;">
                <div style="font-weight:600;"><a href="/app/demand-notice/${notice.name}" style="color:#2563eb; text-decoration:none;">${frappe.utils.escape_html(notice.name)}</a></div>
                <div style="font-size:12px; color:#6b7280; margin-top:4px;">
                  ${notice.notice_date ? frappe.datetime.str_to_user(notice.notice_date) : "-"} | ${frappe.utils.escape_html(notice.status || "Draft")}
                </div>
                <div style="font-size:13px; color:#111827; margin-top:4px;">${format_currency(notice.grand_total_due || 0)}</div>
              </div>
            `
          )
          .join("")
      : `<div class="text-muted">No linked demand notices yet.</div>`;

    const summary = `
      <div style="display:flex; flex-direction:column; gap:12px;">
        <div>
          <div style="font-size:12px; color:#6b7280; text-transform:uppercase;">Legal Case</div>
          <div style="margin-top:4px; font-weight:700;"><a href="/app/legal-case/${legalCase.name}" style="color:#2563eb; text-decoration:none;">${frappe.utils.escape_html(legalCase.name)}</a></div>
          <div style="margin-top:2px; color:#111827;">${frappe.utils.escape_html(legalCase.case_title || "")}</div>
        </div>
        <div>
          <div style="font-size:12px; color:#6b7280; text-transform:uppercase;">Customer</div>
          <div style="margin-top:4px; font-weight:600;">${frappe.utils.escape_html(legalCase.customer || "-")}</div>
        </div>
        <div>
          <div style="font-size:12px; color:#6b7280; text-transform:uppercase;">Company</div>
          <div style="margin-top:4px;">${frappe.utils.escape_html(legalCase.company || "-")}</div>
        </div>
        <div>
          <div style="font-size:12px; color:#6b7280; text-transform:uppercase;">Summary</div>
          <div style="margin-top:4px; color:#111827; white-space:pre-wrap;">${frappe.utils.escape_html(legalCase.summary || "-")}</div>
        </div>
        <div>
          <div style="font-size:12px; color:#6b7280; text-transform:uppercase;">Demand Notices</div>
          <div style="margin-top:6px;">${noticeList}</div>
        </div>
      </div>
    `;

    this.wrapper.find(".legal-desk-side-panel").html(this.panel("Case Details", summary));
  }

  open_action_dialog(activityType) {
    if (!this.currentCase) {
      frappe.msgprint("Select a Legal Case first.");
      return;
    }

    const dialog = new frappe.ui.Dialog({
      title: activityType,
      fields: [
        {
          fieldname: "activity_date",
          fieldtype: "Date",
          label: "Action Date",
          reqd: 1,
          default: frappe.datetime.get_today(),
        },
        {
          fieldname: "amount",
          fieldtype: "Currency",
          label: "Amount",
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
          method: "snrg_credit_control.legal_case.log_legal_case_action",
          args: {
            legal_case: this.currentCase,
            activity_type: activityType,
            activity_date: values.activity_date,
            amount: values.amount,
            remarks: values.remarks,
          },
          freeze: true,
          freeze_message: "Logging legal action...",
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
    const remarks = row.remarks
      ? `<div style="margin-top: 6px; color: #4b5563; white-space: pre-wrap;">${frappe.utils.escape_html(row.remarks)}</div>`
      : "";
    const reference = row.reference_route
      ? `<div style="margin-top: 6px;"><a href="${row.reference_route}" style="color: #2563eb; text-decoration: none;">${frappe.utils.escape_html(row.reference_doctype)}: ${frappe.utils.escape_html(row.reference_name)}</a></div>`
      : "";
    const meta = [
      row.performed_by ? `By ${frappe.utils.escape_html(row.performed_by)}` : "",
      row.activity_date ? frappe.datetime.str_to_user(row.activity_date) : "",
    ]
      .filter(Boolean)
      .join(" | ");

    return `
      <div style="position: relative; margin: 0 0 14px 18px; padding: 12px 14px; border: 1px solid #e5e7eb; border-radius: 10px; background: #fff;">
        <div style="position: absolute; left: -23px; top: 16px; width: 10px; height: 10px; border-radius: 999px; background: #2563eb;"></div>
        <div style="font-weight: 700; color: #111827;">${frappe.utils.escape_html(row.activity_type || "Activity")}</div>
        <div style="margin-top: 2px; font-size: 12px; color: #6b7280;">${meta}</div>
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
}
