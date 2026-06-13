frappe.pages["production-planning"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Production Planning",
    single_column: true,
  });

  wrapper.productionPlanning = new SnrgProductionPlanning(page, wrapper);
};

class SnrgProductionPlanning {
  constructor(page, wrapper) {
    this.page = page;
    this.wrapper = $(wrapper);
    this.controls = {};
    this.data = null;
    this.refreshTimer = null;
    this.setup();
  }

  setup() {
    this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh");
    this.page.add_action_item(__("Open Pending Invoice Planning Report"), () => {
      frappe.set_route("query-report", "Pending Invoice Planning Report");
    });
    this.render_shell();
    this.make_filters();
    this.bind_events();
    this.refresh();
  }

  render_shell() {
    this.wrapper.find(".layout-main-section").html(`
      <style>
        .snrg-production-page {
          display: grid;
          gap: 16px;
          color: #172033;
          font-family: Inter, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
          font-size: 13px;
          line-height: 1.45;
        }
        .snrg-production-filter-row {
          display: grid;
          grid-template-columns: minmax(220px, 1fr) minmax(220px, 1fr) 160px;
          gap: 12px;
          align-items: end;
        }
        .snrg-production-summary {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 12px;
        }
        .snrg-production-metric {
          border: 1px solid #dfe5ef;
          border-radius: 10px;
          background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
          padding: 14px 16px;
        }
        .snrg-production-metric-label {
          color: #667085;
          font-size: 11px;
          font-weight: 800;
          letter-spacing: .04em;
          text-transform: uppercase;
        }
        .snrg-production-metric-value {
          margin-top: 8px;
          color: #101828;
          font-size: 22px;
          font-weight: 800;
          line-height: 1.2;
        }
        .snrg-production-metric-subvalue {
          margin-top: 5px;
          color: #475467;
          font-size: 12px;
        }
        .snrg-production-board {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 14px;
          align-items: start;
        }
        .snrg-production-column {
          border: 1px solid #dfe5ef;
          border-radius: 10px;
          background: #fff;
          min-height: 220px;
          overflow: hidden;
        }
        .snrg-production-column-head {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: center;
          padding: 14px 16px;
          border-bottom: 1px solid #e6edf5;
          background: #f8fafc;
        }
        .snrg-production-column-title {
          font-size: 15px;
          font-weight: 800;
          color: #101828;
        }
        .snrg-production-column-pill {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 28px;
          height: 28px;
          padding: 0 10px;
          border-radius: 999px;
          background: #eaf2ff;
          color: #175cd3;
          font-size: 12px;
          font-weight: 800;
        }
        .snrg-production-column-body {
          display: grid;
          gap: 12px;
          padding: 14px;
        }
        .snrg-production-empty {
          border: 1px dashed #d0d5dd;
          border-radius: 8px;
          padding: 18px;
          text-align: center;
          color: #667085;
          background: #fcfcfd;
        }
        .snrg-production-card {
          border: 1px solid #e4eaf2;
          border-radius: 10px;
          background: #fff;
          padding: 14px;
          box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
          display: grid;
          gap: 10px;
        }
        .snrg-production-card-head {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          align-items: flex-start;
        }
        .snrg-production-card-title {
          color: #101828;
          font-size: 14px;
          font-weight: 800;
          line-height: 1.35;
        }
        .snrg-production-card-subtitle {
          margin-top: 3px;
          color: #667085;
          font-size: 12px;
        }
        .snrg-production-status {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 4px 10px;
          border-radius: 999px;
          font-size: 11px;
          font-weight: 800;
          white-space: nowrap;
        }
        .snrg-production-status-open {
          background: #eef6ff;
          color: #175cd3;
        }
        .snrg-production-status-progress {
          background: #fff4e5;
          color: #b45309;
        }
        .snrg-production-status-completed {
          background: #ecfdf3;
          color: #027a48;
        }
        .snrg-production-status-cancelled {
          background: #f2f4f7;
          color: #475467;
        }
        .snrg-production-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 8px 12px;
        }
        .snrg-production-meta-label {
          color: #667085;
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: .03em;
        }
        .snrg-production-meta-value {
          margin-top: 2px;
          color: #101828;
          font-size: 13px;
          font-weight: 600;
          overflow-wrap: anywhere;
        }
        .snrg-production-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
        .snrg-production-btn {
          border: 1px solid #d0d5dd;
          border-radius: 8px;
          background: #fff;
          color: #344054;
          padding: 6px 10px;
          font-size: 12px;
          font-weight: 700;
          cursor: pointer;
        }
        .snrg-production-btn-primary {
          background: #175cd3;
          border-color: #175cd3;
          color: #fff;
        }
        .snrg-production-btn-success {
          background: #039855;
          border-color: #039855;
          color: #fff;
        }
        .snrg-production-loading {
          padding: 32px;
          border: 1px solid #dfe5ef;
          border-radius: 10px;
          background: #fff;
          color: #667085;
          text-align: center;
        }
        @media (max-width: 1100px) {
          .snrg-production-filter-row,
          .snrg-production-summary,
          .snrg-production-board {
            grid-template-columns: 1fr;
          }
        }
      </style>
      <div class="snrg-production-page">
        <div class="snrg-production-filter-row" data-filter-row></div>
        <div class="snrg-production-summary" data-summary></div>
        <div data-board>
          <div class="snrg-production-loading">Loading production requests...</div>
        </div>
      </div>
    `);
  }

  make_filters() {
    const filterRow = this.wrapper.find("[data-filter-row]");
    const routeCompany = frappe.route_options && frappe.route_options.company;

    this.controls.company = frappe.ui.form.make_control({
      parent: filterRow,
      df: {
        fieldtype: "Link",
        fieldname: "company",
        label: __("Company"),
        options: "Company",
        default: routeCompany || frappe.defaults.get_user_default("Company"),
        onchange: () => this.scheduleRefresh(),
      },
      render_input: true,
    });

    this.controls.search = frappe.ui.form.make_control({
      parent: filterRow,
      df: {
        fieldtype: "Data",
        fieldname: "search",
        label: __("Search"),
        placeholder: __("Search customer, item, quotation, request"),
        onchange: () => this.scheduleRefresh(),
      },
      render_input: true,
    });

    this.controls.show_completed = frappe.ui.form.make_control({
      parent: filterRow,
      df: {
        fieldtype: "Check",
        fieldname: "show_completed",
        label: __("Show Completed"),
        default: 1,
        onchange: () => this.scheduleRefresh(),
      },
      render_input: true,
    });

    frappe.route_options = null;
  }

  bind_events() {
    this.wrapper.on("click", "[data-action='set-status']", (event) => {
      const button = $(event.currentTarget);
      const name = button.attr("data-name");
      const status = button.attr("data-status");
      this.setStatus(name, status, button);
    });

    this.wrapper.on("click", "[data-action='open-form']", (event) => {
      const name = $(event.currentTarget).attr("data-name");
      if (name) {
        frappe.set_route("Form", "Production Request", name);
      }
    });
  }

  get_filters() {
    return {
      company: this.controls.company?.get_value() || "",
      search: this.controls.search?.get_value() || "",
      show_completed: this.controls.show_completed?.get_value() ? 1 : 0,
    };
  }

  scheduleRefresh() {
    clearTimeout(this.refreshTimer);
    this.refreshTimer = setTimeout(() => this.refresh(), 200);
  }

  refresh() {
    this.wrapper.find("[data-board]").html('<div class="snrg-production-loading">Loading production requests...</div>');
    frappe.call({
      method: "snrg_credit_control.snrg_credit_control.doctype.production_request.production_request.get_board_data",
      args: this.get_filters(),
      freeze: false,
      callback: ({ message }) => {
        this.data = message || {};
        this.render_summary();
        this.render_board();
      },
    });
  }

  render_summary() {
    const summary = this.data?.summary || {};
    const target = this.wrapper.find("[data-summary]");
    target.html([
      this.renderMetric("Open Requests", summary.open_count || 0, `Qty ${frappe.format(summary.open_qty || 0, { fieldtype: "Float", precision: 2 })}`),
      this.renderMetric("In Progress", summary.in_progress_count || 0, `Qty ${frappe.format(summary.in_progress_qty || 0, { fieldtype: "Float", precision: 2 })}`),
      this.renderMetric("Completed", summary.completed_count || 0, `Qty ${frappe.format(summary.completed_qty || 0, { fieldtype: "Float", precision: 2 })}`),
    ].join(""));
  }

  renderMetric(label, value, subvalue) {
    return `
      <div class="snrg-production-metric">
        <div class="snrg-production-metric-label">${frappe.utils.escape_html(label)}</div>
        <div class="snrg-production-metric-value">${frappe.utils.escape_html(String(value))}</div>
        <div class="snrg-production-metric-subvalue">${frappe.utils.escape_html(subvalue)}</div>
      </div>
    `;
  }

  render_board() {
    const board = this.wrapper.find("[data-board]");
    const groups = this.data?.groups || {};
    const columns = [
      { key: "Open", label: __("Open"), rows: groups.Open || [] },
      { key: "In Progress", label: __("In Progress"), rows: groups["In Progress"] || [] },
      { key: "Completed", label: __("Completed"), rows: groups.Completed || [] },
    ];

    board.html(`
      <div class="snrg-production-board">
        ${columns.map((column) => this.render_column(column)).join("")}
      </div>
    `);
  }

  render_column(column) {
    const rows = column.rows || [];
    return `
      <div class="snrg-production-column">
        <div class="snrg-production-column-head">
          <div class="snrg-production-column-title">${frappe.utils.escape_html(column.label)}</div>
          <div class="snrg-production-column-pill">${rows.length}</div>
        </div>
        <div class="snrg-production-column-body">
          ${rows.length ? rows.map((row) => this.render_card(row)).join("") : '<div class="snrg-production-empty">No requests in this stage.</div>'}
        </div>
      </div>
    `;
  }

  render_card(row) {
    const statusClass =
      row.status === "Completed"
        ? "snrg-production-status-completed"
        : row.status === "In Progress"
          ? "snrg-production-status-progress"
          : row.status === "Cancelled"
            ? "snrg-production-status-cancelled"
            : "snrg-production-status-open";

    return `
      <div class="snrg-production-card">
        <div class="snrg-production-card-head">
          <div>
            <div class="snrg-production-card-title">${frappe.utils.escape_html(row.item_name || row.item_code || row.name)}</div>
            <div class="snrg-production-card-subtitle">${frappe.utils.escape_html(row.name || "")}</div>
          </div>
          <div class="snrg-production-status ${statusClass}">${frappe.utils.escape_html(row.status || "Open")}</div>
        </div>
        <div class="snrg-production-grid">
          ${this.renderMeta("Quotation", row.quotation)}
          ${this.renderMeta("Quote Date", row.quotation_date)}
          ${this.renderMeta("Customer", row.customer)}
          ${this.renderMeta("Customer Name", row.customer_name)}
          ${this.renderMeta("Item Code", row.item_code)}
          ${this.renderMeta("Qty", frappe.format(row.requested_qty || 0, { fieldtype: "Float", precision: 2 }))}
          ${this.renderMeta("Requested By", row.requested_by)}
          ${this.renderMeta("Age (Days)", String(row.age_days || 0))}
        </div>
        <div class="snrg-production-actions">
          ${this.renderStatusActions(row)}
          <button class="snrg-production-btn" data-action="open-form" data-name="${frappe.utils.escape_html(row.name)}">${__("Open")}</button>
        </div>
      </div>
    `;
  }

  renderMeta(label, value) {
    return `
      <div>
        <div class="snrg-production-meta-label">${frappe.utils.escape_html(label)}</div>
        <div class="snrg-production-meta-value">${frappe.utils.escape_html(value || "-")}</div>
      </div>
    `;
  }

  renderStatusActions(row) {
    const name = frappe.utils.escape_html(row.name);
    if (row.status === "Open") {
      return `
        <button class="snrg-production-btn snrg-production-btn-primary" data-action="set-status" data-name="${name}" data-status="In Progress">${__("Start")}</button>
        <button class="snrg-production-btn snrg-production-btn-success" data-action="set-status" data-name="${name}" data-status="Completed">${__("Complete")}</button>
      `;
    }
    if (row.status === "In Progress") {
      return `
        <button class="snrg-production-btn" data-action="set-status" data-name="${name}" data-status="Open">${__("Move to Open")}</button>
        <button class="snrg-production-btn snrg-production-btn-success" data-action="set-status" data-name="${name}" data-status="Completed">${__("Mark Completed")}</button>
      `;
    }
    if (row.status === "Completed") {
      return `
        <button class="snrg-production-btn" data-action="set-status" data-name="${name}" data-status="Open">${__("Reopen")}</button>
      `;
    }
    return `
      <button class="snrg-production-btn" data-action="set-status" data-name="${name}" data-status="Open">${__("Move to Open")}</button>
    `;
  }

  setStatus(name, status, button) {
    if (!name || !status) {
      return;
    }

    button.prop("disabled", true);
    frappe.call({
      method: "snrg_credit_control.snrg_credit_control.doctype.production_request.production_request.set_request_status",
      args: { name, status },
      freeze: false,
      callback: ({ message }) => {
        frappe.show_alert({
          message: (message && message.message) || __("Production Request updated."),
          indicator: "green",
        });
        this.refresh();
      },
      error: () => {
        button.prop("disabled", false);
      },
    });
  }
}
