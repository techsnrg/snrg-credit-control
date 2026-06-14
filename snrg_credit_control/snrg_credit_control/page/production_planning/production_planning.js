frappe.pages["production-planning"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Production Planning",
    single_column: true,
  });

  wrapper.productionPlanning = new SnrgProductionPlanning(page, wrapper);
};

frappe.pages["production-planning"].on_page_show = function (wrapper) {
  wrapper.productionPlanning?.set_breadcrumb();
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
    this.page.set_primary_action(__("Open Production Planning Console"), () => {
      frappe.route_options = {
        company: this.controls.company?.get_value() || frappe.defaults.get_user_default("Company") || "",
      };
      frappe.set_route("production-planning-console");
    });
    this.page.set_secondary_action(__("Refresh"), () => this.refresh(), "refresh");
    this.page.add_inner_button(__("Open Pending Invoice Planning Report"), () => {
      frappe.set_route("query-report", "Pending Invoice Planning Report");
    });
    this.set_breadcrumb();
    this.render_shell();
    this.make_filters();
    this.bind_events();
    this.refresh();
  }

  set_breadcrumb() {
    if (frappe.breadcrumbs) {
      try {
        frappe.breadcrumbs.clear?.();
        frappe.breadcrumbs.add("Stock");
      } catch (error) {
        // Breadcrumb behavior differs slightly across Frappe versions.
      }
    }

    const updateLabel = () => {
      $(".breadcrumb-container a, .breadcrumbs a, .page-head a").each((_, element) => {
        const link = $(element);
        const text = link.text().trim();
        if (text === "Credit Control" || text === "Selling") {
          link.text("Stock");
          link.attr("href", "/app/stock");
        }
      });
    };

    setTimeout(updateLabel, 50);
    setTimeout(updateLabel, 250);
  }

  render_shell() {
    this.wrapper.find(".layout-main-section").html(`
      <style>
        .snrg-production-page {
          display: grid;
          gap: 12px;
          color: #172033;
          font-family: Inter, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
          font-size: 12px;
          line-height: 1.4;
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
          gap: 10px;
        }
        .snrg-production-metric {
          border: 1px solid #dfe5ef;
          border-radius: 8px;
          background: #fff;
          padding: 10px 12px;
          display: grid;
          gap: 4px;
        }
        .snrg-production-metric-head {
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          gap: 10px;
        }
        .snrg-production-metric-label {
          color: #667085;
          font-size: 11px;
          font-weight: 800;
          letter-spacing: .04em;
          text-transform: uppercase;
        }
        .snrg-production-metric-value {
          color: #101828;
          font-size: 18px;
          font-weight: 800;
          line-height: 1;
          margin-top: 0;
        }
        .snrg-production-metric-subvalue {
          color: #475467;
          font-size: 12px;
          margin-top: 0;
        }
        .snrg-production-board {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 12px;
          align-items: start;
        }
        .snrg-production-column {
          border: 1px solid #dfe5ef;
          border-radius: 8px;
          background: #fff;
          min-height: 180px;
          overflow: hidden;
        }
        .snrg-production-column-head {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: center;
          padding: 10px 12px;
          border-bottom: 1px solid #e6edf5;
          background: #f8fafc;
        }
        .snrg-production-column-title {
          font-size: 14px;
          font-weight: 800;
          color: #101828;
        }
        .snrg-production-column-pill {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 24px;
          height: 24px;
          padding: 0 8px;
          border-radius: 999px;
          background: #eaf2ff;
          color: #175cd3;
          font-size: 11px;
          font-weight: 800;
        }
        .snrg-production-column-body {
          display: grid;
          gap: 10px;
          padding: 10px;
        }
        .snrg-production-empty {
          border: 1px dashed #d0d5dd;
          border-radius: 8px;
          padding: 14px;
          text-align: center;
          color: #667085;
          background: #fcfcfd;
          font-size: 12px;
        }
        .snrg-production-card {
          border: 1px solid #e4eaf2;
          border-left-width: 4px;
          border-radius: 8px;
          background: #fff;
          padding: 12px;
          box-shadow: none;
          display: grid;
          gap: 8px;
          cursor: pointer;
          transition: box-shadow 0.16s ease, border-color 0.16s ease;
        }
        .snrg-production-card:hover {
          box-shadow: 0 3px 10px rgba(16, 24, 40, 0.06);
        }
        .snrg-production-card:focus-within {
          box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
        }
        .snrg-production-card-open {
          border-left-color: #2563eb;
        }
        .snrg-production-card-progress {
          border-left-color: #d97706;
        }
        .snrg-production-card-completed {
          border-left-color: #16a34a;
        }
        .snrg-production-card-cancelled {
          border-left-color: #98a2b3;
        }
        .snrg-production-card-top {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          align-items: flex-start;
        }
        .snrg-production-card-code {
          color: #0f172a;
          font-size: 13px;
          font-weight: 800;
          line-height: 1.2;
          letter-spacing: .01em;
        }
        .snrg-production-item-name {
          color: #101828;
          font-size: 14px;
          font-weight: 800;
          line-height: 1.28;
          margin-top: -1px;
        }
        .snrg-production-qty-pill {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 62px;
          padding: 5px 10px;
          border-radius: 999px;
          border: 1px solid transparent;
          font-size: 12px;
          font-weight: 800;
          white-space: nowrap;
        }
        .snrg-production-qty-open {
          background: #eef4ff;
          border-color: #c7d7fe;
          color: #175cd3;
        }
        .snrg-production-qty-progress {
          background: #fff4e8;
          border-color: #f6d2a8;
          color: #b45309;
        }
        .snrg-production-qty-completed {
          background: #ecfdf3;
          border-color: #b7e6c0;
          color: #027a48;
        }
        .snrg-production-qty-cancelled {
          background: #f4f6f8;
          border-color: #d5dae0;
          color: #475467;
        }
        .snrg-production-card-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 8px 14px;
        }
        .snrg-production-card-meta-row {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 8px 14px;
          align-items: start;
        }
        .snrg-production-card-stack {
          display: grid;
          gap: 1px;
          min-width: 0;
        }
        .snrg-production-card-link {
          color: inherit;
          text-decoration: none;
        }
        .snrg-production-card-link:hover {
          text-decoration: underline;
        }
        .snrg-production-card-primary {
          color: #101828;
          font-size: 13px;
          font-weight: 700;
          line-height: 1.3;
          overflow-wrap: anywhere;
        }
        .snrg-production-card-secondary {
          color: #667085;
          font-size: 12px;
          font-weight: 600;
          line-height: 1.3;
          overflow-wrap: anywhere;
        }
        .snrg-production-inline-label {
          color: #667085;
          font-size: 11px;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: .05em;
        }
        .snrg-production-due-line {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          align-items: baseline;
        }
        .snrg-production-due-text {
          color: #101828;
          font-size: 12px;
          font-weight: 800;
          line-height: 1.25;
        }
        .snrg-production-due-note {
          color: #667085;
          font-size: 11px;
          font-weight: 700;
          line-height: 1.25;
        }
        .snrg-production-assignee-block {
          display: grid;
          gap: 4px;
          min-width: 0;
        }
        .snrg-production-assignee-display {
          display: inline-flex;
          align-items: center;
          justify-content: flex-start;
          width: 100%;
          min-height: 22px;
          padding: 0;
          border: 0;
          background: transparent;
          color: #101828;
          font-size: 12px;
          font-weight: 700;
          text-align: left;
          cursor: pointer;
          overflow-wrap: anywhere;
        }
        .snrg-production-assignee-display.is-empty {
          color: #667085;
          font-weight: 600;
        }
        .snrg-production-assignee-display:hover {
          color: #175cd3;
        }
        .snrg-production-assignee-editor {
          display: none;
        }
        .snrg-production-assignee-editor.is-open {
          display: block;
        }
        .snrg-production-card-footer-line {
          display: flex;
          flex-wrap: wrap;
          gap: 6px 10px;
          color: #667085;
          font-size: 11px;
          font-weight: 700;
          line-height: 1.25;
        }
        .snrg-production-card-footer-accent {
          color: #475467;
        }
        .snrg-production-assignee-control .control-label,
        .snrg-production-assignee-control label {
          display: none !important;
        }
        .snrg-production-assignee-control .form-group,
        .snrg-production-assignee-control .control-input-wrapper {
          margin-bottom: 0;
        }
        .snrg-production-assignee-control .form-control {
          min-height: 30px;
          font-size: 12px;
        }
        .snrg-production-required-by-overdue {
          color: #b42318;
        }
        .snrg-production-required-by-soon {
          color: #b54708;
        }
        .snrg-production-card-due-overdue {
          box-shadow: 0 0 0 1px rgba(180, 35, 24, 0.12);
        }
        .snrg-production-card-due-soon {
          box-shadow: 0 0 0 1px rgba(181, 71, 8, 0.12);
        }
        .snrg-production-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
        .snrg-production-btn {
          border: 1px solid #d0d5dd;
          border-radius: 7px;
          background: #fff;
          color: #344054;
          padding: 5px 9px;
          font-size: 11px;
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
          padding: 24px;
          border: 1px solid #dfe5ef;
          border-radius: 8px;
          background: #fff;
          color: #667085;
          text-align: center;
          font-size: 13px;
        }
        @media (max-width: 1100px) {
          .snrg-production-filter-row,
          .snrg-production-summary,
          .snrg-production-board {
            grid-template-columns: 1fr;
          }
        }
        @media (max-width: 640px) {
          .snrg-production-card-grid,
          .snrg-production-card-meta-row {
            grid-template-columns: 1fr;
            gap: 8px;
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
    this.wrapper.on("click", (event) => {
      if (!$(event.target).closest("[data-assignee-block]").length) {
        this.closeAssigneeEditors();
      }
    });

    this.wrapper.on("click", "[data-action='set-status']", (event) => {
      const button = $(event.currentTarget);
      const name = button.attr("data-name");
      const status = button.attr("data-status");
      this.setStatus(name, status, button);
    });

    this.wrapper.on("click", "[data-action='open-card']", (event) => {
      if ($(event.target).closest("a, button, input, .form-control, .frappe-control, .awesomplete").length) {
        return;
      }

      const name = $(event.currentTarget).attr("data-name");
      this.openForm(name);
    });

    this.wrapper.on("keydown", "[data-action='open-card']", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      if ($(event.target).closest("a, button, input, .form-control, .frappe-control, .awesomplete").length) {
        return;
      }

      event.preventDefault();
      const name = $(event.currentTarget).attr("data-name");
      this.openForm(name);
    });

    this.wrapper.on("click", "[data-action='toggle-assignee']", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const block = $(event.currentTarget).closest("[data-assignee-block]");
      this.toggleAssigneeEditor(block);
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
      this.renderMetric("Open Requests", summary.open_count || 0, `Qty ${this.format_qty(summary.open_qty || 0)}`),
      this.renderMetric("In Progress", summary.in_progress_count || 0, `Qty ${this.format_qty(summary.in_progress_qty || 0)}`),
      this.renderMetric("Completed", summary.completed_count || 0, `Qty ${this.format_qty(summary.completed_qty || 0)}`),
    ].join(""));
  }

  renderMetric(label, value, subvalue) {
    return `
      <div class="snrg-production-metric">
        <div class="snrg-production-metric-head">
          <div class="snrg-production-metric-label">${frappe.utils.escape_html(label)}</div>
          <div class="snrg-production-metric-value">${frappe.utils.escape_html(String(value))}</div>
        </div>
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
    const rows = this.sort_rows_by_urgency(column.rows || []);
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
    const tone = this.getStatusTone(row.status);
    const requestedBy = row.requested_by_name || row.requested_by || "-";
    const assigneeText = row.assigned_to_name || row.assigned_to || __("Assign user");
    const dueInfo = this.getDueInfo(row.required_by_date);
    const dueClass = dueInfo.overdue
      ? "snrg-production-card-due-overdue"
      : dueInfo.dueSoon || dueInfo.dueToday
        ? "snrg-production-card-due-soon"
        : "";
    const requiredByClass = dueInfo.overdue
      ? "snrg-production-required-by-overdue"
      : dueInfo.dueSoon || dueInfo.dueToday
        ? "snrg-production-required-by-soon"
        : "";
    const requiredByText = this.format_date(row.required_by_date) || "-";
    const dueMeta = this.getDueMetaText(dueInfo);

    return `
      <div class="snrg-production-card snrg-production-card-${tone} ${dueClass}" data-action="open-card" data-name="${frappe.utils.escape_html(row.name || "")}" tabindex="0" role="button">
        <div class="snrg-production-card-top">
          <div class="snrg-production-card-code">
            <a class="snrg-production-card-link" href="/app/item/${encodeURIComponent(row.item_code || "")}">
              ${frappe.utils.escape_html(row.item_code || "-")}
            </a>
          </div>
          <div class="snrg-production-qty-pill snrg-production-qty-${tone}">${frappe.utils.escape_html(this.format_qty(row.requested_qty || 0))}</div>
        </div>
        <div class="snrg-production-item-name">${frappe.utils.escape_html(row.item_name || row.item_code || row.name)}</div>
        <div class="snrg-production-card-grid">
          <div class="snrg-production-card-stack">
            <div class="snrg-production-card-primary">
              <a class="snrg-production-card-link" href="/app/quotation/${encodeURIComponent(row.quotation || "")}">
                ${frappe.utils.escape_html(row.quotation || "-")}
              </a>
            </div>
            <div class="snrg-production-card-secondary">${frappe.utils.escape_html(row.quotation_date || "-")}</div>
          </div>
          <div class="snrg-production-card-stack">
            <div class="snrg-production-card-primary">
              <a class="snrg-production-card-link" href="/app/customer/${encodeURIComponent(row.customer || "")}">
                ${frappe.utils.escape_html(row.customer || "-")}
              </a>
            </div>
            <div class="snrg-production-card-secondary">${frappe.utils.escape_html(row.customer_name || "-")}</div>
          </div>
        </div>
        <div class="snrg-production-card-meta-row">
          <div class="snrg-production-card-stack">
            <div class="snrg-production-inline-label ${requiredByClass}">${__("Required By")}</div>
            <div class="snrg-production-due-line ${requiredByClass}">
              <span class="snrg-production-due-text ${requiredByClass}">${frappe.utils.escape_html(requiredByText)}</span>
              <span class="snrg-production-due-note ${requiredByClass}">${frappe.utils.escape_html(dueMeta)}</span>
            </div>
          </div>
          <div class="snrg-production-assignee-block" data-assignee-block>
            <div class="snrg-production-inline-label">${__("Assigned To")}</div>
            <button class="snrg-production-assignee-display ${row.assigned_to ? "" : "is-empty"}" type="button" data-action="toggle-assignee">
              <span data-assignee-display-text>${frappe.utils.escape_html(assigneeText)}</span>
            </button>
            <div class="snrg-production-assignee-editor" data-assignee-editor>
              <div
                class="snrg-production-assignee-control"
                data-assignee-control
                data-name="${frappe.utils.escape_html(row.name || "")}"
                data-assigned-to="${frappe.utils.escape_html(row.assigned_to || "")}"
                data-assigned-to-name="${frappe.utils.escape_html(row.assigned_to_name || "")}"
              ></div>
            </div>
          </div>
        </div>
        <div class="snrg-production-card-footer-line">
          <span>${frappe.utils.escape_html(__("By"))} <span class="snrg-production-card-footer-accent">${frappe.utils.escape_html(requestedBy)}</span></span>
          <span>${frappe.utils.escape_html(row.name || "-")}</span>
          <span>${frappe.utils.escape_html(__("Days"))} ${frappe.utils.escape_html(String(row.age_days || 0))}</span>
        </div>
        <div class="snrg-production-actions">
          ${this.renderStatusActions(row)}
        </div>
      </div>
    `;
  }

  getStatusTone(status) {
    if (status === "Completed") {
      return "completed";
    }
    if (status === "In Progress") {
      return "progress";
    }
    if (status === "Cancelled") {
      return "cancelled";
    }
    return "open";
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

  openForm(name) {
    if (name) {
      frappe.set_route("Form", "Production Request", name);
    }
  }

  toggleAssigneeEditor(block) {
    if (!block || !block.length) {
      return;
    }

    const isOpen = block.hasClass("is-editing");
    this.closeAssigneeEditors(block);
    if (isOpen) {
      block.removeClass("is-editing");
      block.find("[data-assignee-editor]").removeClass("is-open");
      return;
    }

    const target = block.find("[data-assignee-control]");
    const control = this.ensureAssigneeControl(target);
    block.addClass("is-editing");
    block.find("[data-assignee-editor]").addClass("is-open");

    setTimeout(() => {
      if (control?.$input?.length) {
        control.$input.trigger("focus");
      }
    }, 0);
  }

  closeAssigneeEditors(exceptBlock = null) {
    this.wrapper.find("[data-assignee-block].is-editing").each((_, element) => {
      const block = $(element);
      if (exceptBlock && block.is(exceptBlock)) {
        return;
      }
      block.removeClass("is-editing");
      block.find("[data-assignee-editor]").removeClass("is-open");
    });
  }

  ensureAssigneeControl(target) {
    if (!target || !target.length) {
      return null;
    }

    const mounted = target.data("control-instance");
    if (mounted) {
      return mounted;
    }

    const name = target.attr("data-name") || "";
    const assignedTo = target.attr("data-assigned-to") || "";
    target.attr("data-saved-assigned-to", assignedTo);

    let isBootstrapping = true;
    const control = frappe.ui.form.make_control({
      parent: target.get(0),
      df: {
        fieldtype: "Link",
        fieldname: `assigned_to_${name}`,
        label: __("Assigned To"),
        options: "User",
        placeholder: __("Assign user"),
        default: assignedTo,
        onchange: () => {
          if (isBootstrapping) {
            return;
          }
          const nextValue = String(control.get_value() || "").trim();
          const savedValue = String(target.attr("data-saved-assigned-to") || "").trim();
          if (nextValue === savedValue || target.attr("data-assignee-updating") === "1") {
            return;
          }
          this.setAssignee(name, nextValue, control, target);
        },
      },
      render_input: true,
    });
    control.refresh();
    control.set_value(assignedTo);
    setTimeout(() => {
      isBootstrapping = false;
    }, 0);

    target.attr("data-control-mounted", "1");
    target.data("control-instance", control);
    return control;
  }

  format_qty(value) {
    return new Intl.NumberFormat("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(value || 0) || 0);
  }

  format_date(value) {
    if (!value) {
      return "";
    }
    return frappe.datetime.str_to_user ? frappe.datetime.str_to_user(value) : value;
  }

  getDueInfo(requiredByDate) {
    if (!requiredByDate) {
      return {
        hasDate: false,
        overdue: false,
        dueToday: false,
        dueSoon: false,
        daysUntil: null,
      };
    }

    const today = frappe.datetime.get_today ? frappe.datetime.get_today() : "";
    if (!today) {
      return {
        hasDate: true,
        overdue: false,
        dueToday: false,
        dueSoon: false,
        daysUntil: null,
      };
    }

    const dueDate = new Date(`${requiredByDate}T00:00:00`);
    const todayDate = new Date(`${today}T00:00:00`);
    const millisecondsPerDay = 24 * 60 * 60 * 1000;
    const daysUntil = Math.round((dueDate - todayDate) / millisecondsPerDay);

    return {
      hasDate: true,
      overdue: daysUntil < 0,
      dueToday: daysUntil === 0,
      dueSoon: daysUntil > 0 && daysUntil <= 2,
      daysUntil,
    };
  }

  getDueMetaText(dueInfo) {
    if (!dueInfo || !dueInfo.hasDate) {
      return __("No due date set");
    }
    if (dueInfo.overdue) {
      return __("{0} day(s) overdue", [Math.abs(dueInfo.daysUntil)]);
    }
    if (dueInfo.dueToday) {
      return __("Due today");
    }
    if (dueInfo.dueSoon) {
      return __("Due in {0} day(s)", [dueInfo.daysUntil]);
    }
    return __("Due in {0} day(s)", [dueInfo.daysUntil]);
  }

  sort_rows_by_urgency(rows) {
    return [...rows].sort((left, right) => this.compareRowsByUrgency(left, right));
  }

  compareRowsByUrgency(left, right) {
    const leftDue = this.getDueInfo(left.required_by_date);
    const rightDue = this.getDueInfo(right.required_by_date);

    const leftPriority = this.getDuePriority(leftDue);
    const rightPriority = this.getDuePriority(rightDue);
    if (leftPriority !== rightPriority) {
      return leftPriority - rightPriority;
    }

    const leftDaysUntil = leftDue.hasDate ? leftDue.daysUntil : Number.POSITIVE_INFINITY;
    const rightDaysUntil = rightDue.hasDate ? rightDue.daysUntil : Number.POSITIVE_INFINITY;
    if (leftDaysUntil !== rightDaysUntil) {
      return leftDaysUntil - rightDaysUntil;
    }

    const leftAge = Number(left.age_days || 0);
    const rightAge = Number(right.age_days || 0);
    if (leftAge !== rightAge) {
      return rightAge - leftAge;
    }

    return String(left.name || "").localeCompare(String(right.name || ""));
  }

  getDuePriority(dueInfo) {
    if (!dueInfo || !dueInfo.hasDate) {
      return 3;
    }
    if (dueInfo.overdue) {
      return 0;
    }
    if (dueInfo.dueToday) {
      return 1;
    }
    if (dueInfo.dueSoon) {
      return 2;
    }
    return 3;
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

  setAssignee(name, assignedTo, control, target) {
    if (!name || !control || !target) {
      return;
    }

    const input = control.$input;
    target.attr("data-assignee-updating", "1");
    if (input && input.length) {
      input.prop("disabled", true);
    }

    frappe.call({
      method: "snrg_credit_control.snrg_credit_control.doctype.production_request.production_request.set_request_assignee",
      args: {
        name,
        assigned_to: assignedTo || "",
      },
      freeze: false,
      callback: ({ message }) => {
        const updatedAssignedTo = String((message && message.assigned_to) || assignedTo || "").trim();
        const updatedAssignedToName = String((message && message.assigned_to_name) || updatedAssignedTo || "").trim();
        const block = target.closest("[data-assignee-block]");
        target.attr("data-assigned-to", updatedAssignedTo);
        target.attr("data-saved-assigned-to", updatedAssignedTo);
        target.attr("data-assigned-to-name", updatedAssignedToName);
        target.attr("data-assignee-updating", "0");
        if (input && input.length) {
          input.prop("disabled", false);
        }
        block.find("[data-assignee-display-text]").text(updatedAssignedToName || __("Assign user"));
        block.find("[data-action='toggle-assignee']").toggleClass("is-empty", !updatedAssignedTo);
        this.closeAssigneeEditors();
        frappe.show_alert({
          message: (message && message.message) || __("Production Request assignee updated."),
          indicator: "green",
        });
      },
      error: () => {
        target.attr("data-assignee-updating", "0");
        if (input && input.length) {
          input.prop("disabled", false);
        }
        control.set_value(target.attr("data-saved-assigned-to") || "");
      },
    });
  }
}
