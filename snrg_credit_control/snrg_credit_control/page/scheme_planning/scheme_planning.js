frappe.pages["scheme-planning"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Scheme Planning",
    single_column: true,
  });

  wrapper.scheme_planning = new SnrgSchemePlanning(page, wrapper);
};

frappe.pages["scheme-planning"].on_page_show = function (wrapper) {
  wrapper.scheme_planning?.set_breadcrumb();
};

class SnrgSchemePlanning {
  constructor(page, wrapper) {
    this.page = page;
    this.wrapper = $(wrapper);
    this.controls = {};
    this.data = null;
    this.customerIndex = {};
    this.schemeTableIndex = {};
    this.tableFilters = {};
    this.tableSort = {};
    this.setup();
  }

  setup() {
    this.page.set_primary_action("Get Suggestions", () => this.refresh(), "search");
    this.set_breadcrumb();
    this.render_shell();
    this.make_filters();
    this.bind_events();
  }

  set_breadcrumb() {
    if (frappe.breadcrumbs) {
      try {
        frappe.breadcrumbs.clear?.();
        frappe.breadcrumbs.add("Scheme Management");
      } catch (error) {
        // Breadcrumb behavior differs slightly across Frappe versions.
      }
    }

    const updateLabel = () => {
      $(".breadcrumb-container a, .breadcrumbs a, .page-head a").each((_, element) => {
        const link = $(element);
        if (link.text().trim() === "Credit Control") {
          link.text("Scheme Management");
          link.attr("href", "/app/scheme-management");
        }
      });
    };

    setTimeout(updateLabel, 50);
    setTimeout(updateLabel, 250);
  }

  render_shell() {
    this.wrapper.find(".layout-main-section").html(`
      <style>
        .snrg-scheme-page {
          display: grid;
          gap: 16px;
          color: #172033;
          font-family: Inter, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
          font-size: 13px;
          line-height: 1.45;
        }
        .snrg-scheme-filter-row {
          display: grid;
          grid-template-columns: minmax(220px, 1fr) minmax(260px, 1.2fr) minmax(160px, .7fr) minmax(140px, .45fr) minmax(170px, .55fr);
          gap: 12px;
          align-items: end;
        }
        .snrg-scheme-check-filter { padding-bottom: 7px; }
        .snrg-scheme-empty {
          padding: 28px;
          border: 1px solid #dfe5ef;
          background: #fff;
          border-radius: 8px;
          color: #5f6f83;
        }
        .snrg-scheme-grid { display: grid; gap: 14px; }
        .snrg-scheme-card {
          border: 1px solid #dfe5ef;
          background: #fff;
          border-radius: 8px;
          overflow: hidden;
        }
        .snrg-scheme-card-head {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          padding: 16px;
          background: #f8fafc;
          border-bottom: 1px solid #e6edf5;
        }
        .snrg-scheme-title { font-size: 17px; font-weight: 700; color: #101828; margin: 0; }
        .snrg-scheme-subtitle { margin-top: 4px; font-size: 12px; color: #667085; }
        .snrg-scheme-pill {
          display: inline-flex;
          align-items: center;
          height: 26px;
          padding: 0 10px;
          border-radius: 999px;
          background: #eef6ff;
          color: #175cd3;
          font-size: 12px;
          font-weight: 700;
          white-space: nowrap;
        }
        .snrg-scheme-metrics {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 10px;
          padding: 16px;
        }
        .snrg-scheme-metric {
          border: 1px solid #edf1f7;
          border-radius: 8px;
          padding: 12px;
          background: #fcfdff;
        }
        .snrg-scheme-label {
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: .04em;
          color: #667085;
          font-weight: 700;
        }
        .snrg-scheme-value {
          margin-top: 7px;
          font-size: 20px;
          line-height: 1.2;
          color: #101828;
          font-weight: 800;
        }
        .snrg-scheme-table-wrap { padding: 0 16px 16px; overflow: auto; }
        .snrg-scheme-table {
          width: 100%;
          min-width: 1540px;
          border-collapse: collapse;
          border: 1px solid #edf1f7;
          border-radius: 8px;
          overflow: hidden;
          background: #fff;
        }
        .snrg-scheme-table th,
        .snrg-scheme-table td {
          padding: 10px 12px;
          border-bottom: 1px solid #edf1f7;
          font-size: 13px;
          line-height: 1.45;
          vertical-align: top;
        }
        .snrg-scheme-table th { background: #f8fafc; color: #667085; font-weight: 800; }
        .snrg-scheme-table .snrg-scheme-group-row th {
          background: #fff;
          border-bottom: 1px solid #d0d5dd;
          color: #344054;
          font-size: 12px;
          letter-spacing: .03em;
          padding: 7px 12px;
          text-align: center;
          text-transform: uppercase;
        }
        .snrg-scheme-table .snrg-scheme-group-row th:first-child,
        .snrg-scheme-table .snrg-scheme-group-row th:nth-child(2),
        .snrg-scheme-table .snrg-scheme-group-row th:last-child {
          background: #f8fafc;
        }
        .snrg-scheme-table .snrg-scheme-group-achieved {
          box-shadow: inset 1px 0 0 #d0d5dd, inset -1px 0 0 #d0d5dd;
        }
        .snrg-scheme-table .snrg-scheme-group-projected {
          box-shadow: inset 1px 0 0 #d0d5dd, inset -1px 0 0 #d0d5dd;
        }
        .snrg-scheme-table tr:last-child td { border-bottom: 0; }
        .snrg-scheme-sort-btn {
          border: 0;
          background: transparent;
          color: inherit;
          font: inherit;
          font-weight: 800;
          padding: 0;
          text-align: inherit;
          width: 100%;
          cursor: pointer;
        }
        .snrg-scheme-sort-btn span { color: #98a2b3; margin-left: 4px; }
        .snrg-scheme-filter-input {
          width: 100%;
          min-width: 0;
          border: 0;
          border-radius: 8px;
          background: #f2f4f7;
          padding: 7px 9px;
          color: #344054;
          font-size: 12px;
          outline: none;
        }
        .snrg-scheme-filter-input:focus {
          background: #fff;
          box-shadow: inset 0 0 0 1px #98a2b3;
        }
        .snrg-scheme-right { text-align: right; }
        .snrg-scheme-detail-btn {
          border: 1px solid #d0d5dd;
          border-radius: 6px;
          background: #fff;
          color: #344054;
          padding: 5px 9px;
          font-size: 13px;
          font-weight: 700;
        }
        .snrg-scheme-detail-grid {
          display: grid;
          grid-template-columns: minmax(0, 1.1fr) minmax(0, .9fr);
          gap: 18px;
          align-items: start;
        }
        .snrg-scheme-detail-modal .modal-dialog {
          width: min(1440px, calc(100vw - 56px));
          max-width: min(1440px, calc(100vw - 56px));
        }
        .snrg-scheme-detail-modal .modal-content {
          font-family: Inter, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
          font-size: 13px;
          line-height: 1.45;
        }
        .snrg-scheme-detail-modal .modal-body {
          overflow-x: auto;
          padding: 0;
        }
        .snrg-scheme-detail-shell {
          display: grid;
          gap: 16px;
          padding: 18px;
        }
        .snrg-scheme-detail-summary {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 10px;
        }
        .snrg-scheme-detail-card {
          border: 1px solid #e4eaf2;
          border-radius: 8px;
          background: #fbfcff;
          padding: 11px 12px;
          min-height: 74px;
        }
        .snrg-scheme-detail-card-label {
          color: #667085;
          font-size: 11px;
          font-weight: 800;
          letter-spacing: .03em;
          line-height: 1.3;
          text-transform: uppercase;
        }
        .snrg-scheme-detail-card-value {
          margin-top: 7px;
          color: #101828;
          font-size: 15px;
          font-weight: 800;
          line-height: 1.25;
          overflow-wrap: anywhere;
        }
        .snrg-scheme-detail-section {
          min-width: 0;
        }
        .snrg-scheme-detail-section h5 {
          margin: 0 0 8px;
          color: #101828;
          font-size: 15px;
          font-weight: 800;
        }
        .snrg-scheme-detail-items {
          grid-column: 1 / -1;
        }
        .snrg-scheme-dialog-table {
          width: 100%;
          border-collapse: collapse;
          border: 1px solid #edf1f7;
          table-layout: auto;
        }
        .snrg-scheme-dialog-table th,
        .snrg-scheme-dialog-table td {
          padding: 9px 11px;
          border-bottom: 1px solid #edf1f7;
          font-size: 13px;
          line-height: 1.45;
        }
        .snrg-scheme-dialog-table th { background: #f8fafc; color: #667085; }
        .snrg-scheme-dialog-table td:first-child { min-width: 150px; }
        @media (max-width: 900px) {
          .snrg-scheme-filter-row,
          .snrg-scheme-metrics,
          .snrg-scheme-detail-summary,
          .snrg-scheme-detail-grid { grid-template-columns: 1fr; }
        }
      </style>
      <div class="snrg-scheme-page">
        <div class="snrg-scheme-filter-row" data-filter-row></div>
        <div data-results>
          <div class="snrg-scheme-empty">Choose a scheme or date, then fetch customer progress.</div>
        </div>
      </div>
    `);
  }

  make_filters() {
    const filterRow = this.wrapper.find("[data-filter-row]");

    this.controls.company = frappe.ui.form.make_control({
      parent: filterRow,
      df: {
        fieldtype: "Link",
        fieldname: "company",
        label: "Company",
        options: "Company",
      },
      render_input: true,
    });

    this.controls.scheme = frappe.ui.form.make_control({
      parent: filterRow,
      df: {
        fieldtype: "Link",
        fieldname: "scheme",
        label: "Scheme",
        options: "SNRG Scheme",
      },
      render_input: true,
    });

    this.controls.as_on_date = frappe.ui.form.make_control({
      parent: filterRow,
      df: {
        fieldtype: "Date",
        fieldname: "as_on_date",
        label: "As On Date",
        default: frappe.datetime.get_today(),
      },
      render_input: true,
    });

    const draftWrapper = $(`<div class="snrg-scheme-check-filter"></div>`).appendTo(filterRow);
    this.controls.include_draft_quotations = frappe.ui.form.make_control({
      parent: draftWrapper,
      df: {
        fieldtype: "Check",
        fieldname: "include_draft_quotations",
        label: "Draft Quotations",
        default: 0,
      },
      render_input: true,
    });

    const submittedWrapper = $(`<div class="snrg-scheme-check-filter"></div>`).appendTo(filterRow);
    this.controls.include_submitted_quotations = frappe.ui.form.make_control({
      parent: submittedWrapper,
      df: {
        fieldtype: "Check",
        fieldname: "include_submitted_quotations",
        label: "Submitted Quotations",
        default: 1,
      },
      render_input: true,
    });
  }

  bind_events() {
    this.wrapper.on("click", "[data-show-details]", (event) => {
      const key = $(event.currentTarget).attr("data-show-details");
      this.open_customer_details(key);
    });
    this.wrapper.on("input", "[data-table-filter]", (event) => {
      const input = $(event.currentTarget);
      const tableKey = input.attr("data-table-filter");
      const field = input.attr("data-filter-field");
      this.tableFilters[tableKey] = this.tableFilters[tableKey] || {};
      this.tableFilters[tableKey][field] = input.val();
      this.render_customer_table_body(tableKey);
    });
    this.wrapper.on("click", "[data-sort-table]", (event) => {
      const button = $(event.currentTarget);
      const tableKey = button.attr("data-sort-table");
      const field = button.attr("data-sort-field");
      const current = this.tableSort[tableKey] || {};
      const direction = current.field === field && current.direction === "asc" ? "desc" : "asc";
      this.tableSort[tableKey] = { field, direction };
      this.render_results();
    });
  }

  get_values() {
    return {
      company: this.controls.company.get_value(),
      scheme: this.controls.scheme.get_value(),
      as_on_date: this.controls.as_on_date.get_value(),
      include_draft_quotations: this.controls.include_draft_quotations.get_value(),
      include_submitted_quotations: this.controls.include_submitted_quotations.get_value(),
    };
  }

  async refresh() {
    const values = this.get_values();

    try {
      const response = await frappe.call({
        method: "snrg_credit_control.scheme_engine.get_scheme_customer_progress",
        args: values,
        freeze: true,
        freeze_message: "Checking scheme progress...",
      });
      this.data = response.message || {};
      this.render_results();
    } catch (error) {
      frappe.msgprint({
        title: "Scheme Progress Failed",
        message: (error && error.message) || String(error),
        indicator: "red",
      });
    }
  }

  render_empty(message) {
    this.wrapper.find("[data-results]").html(`<div class="snrg-scheme-empty">${frappe.utils.escape_html(message)}</div>`);
  }

  render_results() {
    const schemes = this.data.schemes || [];
    this.customerIndex = {};
    this.schemeTableIndex = {};
    this.detailKeyCounter = 0;
    this.tableKeyCounter = 0;

    if (!schemes.length) {
      this.render_empty("No customers have eligible sales in the selected scheme period.");
      return;
    }

    this.wrapper.find("[data-results]").html(`
      <div class="snrg-scheme-grid">
        ${schemes.map((scheme) => this.render_scheme_card(scheme)).join("")}
      </div>
    `);
  }

  render_scheme_card(scheme) {
    const tableKey = `scheme-table-${this.tableKeyCounter++}`;
    this.schemeTableIndex[tableKey] = scheme;

    return `
      <div class="snrg-scheme-card">
        <div class="snrg-scheme-card-head">
          <div>
            <h3 class="snrg-scheme-title">${frappe.utils.escape_html(scheme.scheme_name || "")}</h3>
            <div class="snrg-scheme-subtitle">
              ${frappe.utils.escape_html(scheme.period_from || "")} to ${frappe.utils.escape_html(scheme.period_upto || "")}
            </div>
          </div>
          <div class="snrg-scheme-pill">${format_number(scheme.customer_count || 0)} Customers</div>
        </div>
        <div class="snrg-scheme-metrics">
          ${scheme.scheme_type === "Period Cumulative Category Target Slab"
            ? this.render_metric("Invoice Category Value", format_currency(scheme.eligible_amount))
            : this.render_metric("Invoice Eligible Value", format_currency(scheme.eligible_amount))}
          ${this.render_metric("Quotation Eligible Value", format_currency(scheme.quotation_amount || 0))}
          ${this.render_metric("Projected Eligible Value", format_currency(scheme.projected_amount || scheme.eligible_amount || 0))}
          ${this.render_metric("Customers", format_number(scheme.customer_count || 0))}
        </div>
        <div class="snrg-scheme-table-wrap">
          ${this.render_customer_table(scheme, tableKey)}
        </div>
      </div>
    `;
  }

  render_metric(label, value) {
    return `
      <div class="snrg-scheme-metric">
        <div class="snrg-scheme-label">${frappe.utils.escape_html(label)}</div>
        <div class="snrg-scheme-value">${frappe.utils.escape_html(String(value || ""))}</div>
      </div>
    `;
  }

  render_customer_table(scheme, tableKey) {
    const rows = scheme.customers || [];
    if (!rows.length) {
      return `<div class="snrg-scheme-empty">No eligible customer sales found.</div>`;
    }

    if (scheme.scheme_type === "Period Cumulative Category Target Slab") {
      return this.render_category_customer_table(scheme, tableKey);
    }

    return `
      <table class="snrg-scheme-table">
        <thead>
          <tr class="snrg-scheme-group-row">
            <th></th>
            <th></th>
            <th class="snrg-scheme-group-achieved" colspan="3">Achieved</th>
            <th class="snrg-scheme-group-projected" colspan="4">Projected</th>
            <th></th>
          </tr>
          <tr>
            ${this.render_sort_header(tableKey, "customer_name", "Customer")}
            ${this.render_sort_header(tableKey, "eligible_amount", "Invoice Eligible", true)}
            ${this.render_sort_header(tableKey, "achieved_slab", "Slab Achieved Till Now")}
            ${this.render_sort_header(tableKey, "next_slab", "Next Achievable Slab")}
            ${this.render_sort_header(tableKey, "shortfall_amount", "Shortfall", true)}
            ${this.render_sort_header(tableKey, "quotation_amount", "Quotation Eligible", true)}
            ${this.render_sort_header(tableKey, "projected_slab", "Projected Slab")}
            ${this.render_sort_header(tableKey, "projected_amount", "Projected Eligible", true)}
            ${this.render_sort_header(tableKey, "projected_shortfall_amount", "Projected Shortfall", true)}
            <th></th>
          </tr>
          <tr>
            ${this.render_filter_cell(tableKey, "customer", "Search customer")}
            ${this.render_filter_cell(tableKey, "eligible_amount", "Search invoice", true)}
            ${this.render_filter_cell(tableKey, "achieved_slab", "Search slab")}
            ${this.render_filter_cell(tableKey, "next_slab", "Search next slab")}
            ${this.render_filter_cell(tableKey, "shortfall_amount", "Search shortfall", true)}
            ${this.render_filter_cell(tableKey, "quotation_amount", "Search quotation", true)}
            ${this.render_filter_cell(tableKey, "projected_slab", "Search projected slab")}
            ${this.render_filter_cell(tableKey, "projected_amount", "Search projected", true)}
            ${this.render_filter_cell(tableKey, "projected_shortfall_amount", "Search projected shortfall", true)}
            <th></th>
          </tr>
        </thead>
        <tbody data-customer-body="${frappe.utils.escape_html(tableKey)}">
          ${this.render_customer_rows(scheme, tableKey)}
        </tbody>
      </table>
    `;
  }

  render_category_customer_table(scheme, tableKey) {
    const categories = this.get_scheme_categories(scheme);
    const categoryHeaders = categories.map((category) => (
      this.render_sort_header(tableKey, this.get_category_field(category), category, true)
    )).join("");
    const categoryFilters = categories.map((category) => (
      this.render_filter_cell(tableKey, this.get_category_field(category), `Search ${category}`, true)
    )).join("");
    const invoiceColspan = categories.length + 2;

    return `
      <table class="snrg-scheme-table">
        <thead>
          <tr class="snrg-scheme-group-row">
            <th></th>
            <th colspan="${invoiceColspan}" class="snrg-scheme-group-achieved">Invoice Achievement</th>
            <th colspan="3" class="snrg-scheme-group-projected">Projected</th>
            <th></th>
          </tr>
          <tr>
            ${this.render_sort_header(tableKey, "customer_name", "Customer")}
            ${categoryHeaders}
            ${this.render_sort_header(tableKey, "eligible_amount", "Invoice Total", true)}
            ${this.render_sort_header(tableKey, "achieved_rewards", "Rewards Achieved")}
            ${this.render_sort_header(tableKey, "projected_amount", "Projected Total", true)}
            ${this.render_sort_header(tableKey, "projected_rewards", "Projected Rewards")}
            ${this.render_sort_header(tableKey, "projected_shortfall_amount", "Next Gap", true)}
            <th></th>
          </tr>
          <tr>
            ${this.render_filter_cell(tableKey, "customer", "Search customer")}
            ${categoryFilters}
            ${this.render_filter_cell(tableKey, "eligible_amount", "Search invoice", true)}
            ${this.render_filter_cell(tableKey, "achieved_rewards", "Search rewards")}
            ${this.render_filter_cell(tableKey, "projected_amount", "Search projected", true)}
            ${this.render_filter_cell(tableKey, "projected_rewards", "Search projected rewards")}
            ${this.render_filter_cell(tableKey, "projected_shortfall_amount", "Search gap", true)}
            <th></th>
          </tr>
        </thead>
        <tbody data-customer-body="${frappe.utils.escape_html(tableKey)}">
          ${this.render_customer_rows(scheme, tableKey)}
        </tbody>
      </table>
    `;
  }

  get_scheme_categories(scheme) {
    return (scheme.categories || []).filter(Boolean);
  }

  get_category_field(category) {
    return `category:${category}`;
  }

  get_field_category(field) {
    return String(field || "").startsWith("category:") ? String(field).slice(9) : null;
  }

  render_sort_header(tableKey, field, label, right = false) {
    const sort = this.tableSort[tableKey] || {};
    const marker = sort.field === field ? (sort.direction === "asc" ? "▲" : "▼") : "↕";
    return `
      <th class="${right ? "snrg-scheme-right" : ""}">
        <button class="snrg-scheme-sort-btn" data-sort-table="${frappe.utils.escape_html(tableKey)}" data-sort-field="${frappe.utils.escape_html(field)}">
          ${frappe.utils.escape_html(label)}<span>${marker}</span>
        </button>
      </th>
    `;
  }

  render_filter_cell(tableKey, field, placeholder, right = false) {
    const value = ((this.tableFilters[tableKey] || {})[field]) || "";
    return `
      <th class="${right ? "snrg-scheme-right" : ""}">
        <input
          class="snrg-scheme-filter-input ${right ? "snrg-scheme-right" : ""}"
          data-table-filter="${frappe.utils.escape_html(tableKey)}"
          data-filter-field="${frappe.utils.escape_html(field)}"
          placeholder="${frappe.utils.escape_html(placeholder)}"
          value="${frappe.utils.escape_html(value)}"
        >
      </th>
    `;
  }

  render_customer_table_body(tableKey) {
    const scheme = this.schemeTableIndex[tableKey];
    if (!scheme) return;

    this.wrapper
      .find(`[data-customer-body="${tableKey}"]`)
      .html(this.render_customer_rows(scheme, tableKey));
  }

  render_customer_rows(scheme, tableKey) {
    const rows = this.get_visible_customer_rows(scheme, tableKey);
    if (!rows.length) {
      const colspan = scheme.scheme_type === "Period Cumulative Category Target Slab"
        ? this.get_scheme_categories(scheme).length + 6
        : 10;
      return `<tr><td colspan="${colspan}" class="snrg-scheme-empty">No rows match the current search.</td></tr>`;
    }

    return rows.map((row, index) => (
      scheme.scheme_type === "Period Cumulative Category Target Slab"
        ? this.render_category_customer_row(scheme, row, index)
        : this.render_customer_row(scheme, row, index)
    )).join("");
  }

  get_visible_customer_rows(scheme, tableKey) {
    const filters = this.tableFilters[tableKey] || {};
    const sort = this.tableSort[tableKey] || {};
    let rows = [...(scheme.customers || [])];

    rows = rows.filter((row) => {
      return Object.keys(filters).every((field) => {
        const term = String(filters[field] || "").trim().toLowerCase();
        if (!term) return true;
        return this.get_filter_value(row, field).toLowerCase().includes(term);
      });
    });

    if (sort.field) {
      rows.sort((a, b) => {
        const aValue = this.get_sort_value(a, sort.field);
        const bValue = this.get_sort_value(b, sort.field);
        if (typeof aValue === "number" && typeof bValue === "number") {
          return sort.direction === "asc" ? aValue - bValue : bValue - aValue;
        }
        return sort.direction === "asc"
          ? String(aValue).localeCompare(String(bValue))
          : String(bValue).localeCompare(String(aValue));
      });
    }

    return rows;
  }

  get_filter_value(row, field) {
    const category = this.get_field_category(field);
    if (category) {
      const value = row.category_amounts?.[category] || 0;
      return `${format_currency(value)} ${value}`;
    }
    if (field === "customer") {
      return `${row.customer_name || ""} ${row.customer || ""}`;
    }
    if (field === "achieved_slab") {
      return this.format_slab(row.achieved_slab, "None");
    }
    if (field === "projected_slab") {
      return this.format_slab(row.projected_slab, "None");
    }
    if (field === "next_slab") {
      return this.format_slab(row.next_slab, "Highest slab achieved");
    }
    if (field === "achieved_rewards") {
      return (row.achieved_rewards || []).join(", ");
    }
    if (field === "projected_rewards") {
      return (row.projected_rewards || []).join(", ");
    }
    if (
      field === "eligible_amount"
      || field === "quotation_amount"
      || field === "projected_amount"
      || field === "shortfall_amount"
      || field === "projected_shortfall_amount"
    ) {
      const value = row[field];
      return `${format_currency(value || 0)} ${value || 0}`;
    }
    return String(row[field] || "");
  }

  get_sort_value(row, field) {
    const category = this.get_field_category(field);
    if (category) return Number(row.category_amounts?.[category] || 0);
    if (field === "customer_name") return row.customer_name || row.customer || "";
    if (field === "achieved_rewards") return (row.achieved_rewards || []).join(", ");
    if (field === "projected_rewards") return (row.projected_rewards || []).join(", ");
    if (field === "achieved_slab") return row.achieved_slab ? row.achieved_slab.amount || 0 : 0;
    if (field === "projected_slab") return row.projected_slab ? row.projected_slab.amount || 0 : 0;
    if (field === "next_slab") return row.next_slab ? row.next_slab.amount || 0 : Infinity;
    if (
      field === "eligible_amount"
      || field === "quotation_amount"
      || field === "projected_amount"
      || field === "shortfall_amount"
      || field === "projected_shortfall_amount"
    ) {
      return Number(row[field] || 0);
    }
    return row[field] || "";
  }

  render_customer_row(scheme, row, index) {
    const key = `row-${this.detailKeyCounter++}`;
    this.customerIndex[key] = { scheme, row };

    return `
      <tr>
        <td>
          ${frappe.utils.escape_html(row.customer_name || row.customer || "")}
          <div class="snrg-scheme-subtitle">${frappe.utils.escape_html(row.customer || "")}</div>
        </td>
        <td class="snrg-scheme-right">${format_currency(row.eligible_amount || 0)}</td>
        <td>${frappe.utils.escape_html(this.format_slab(row.achieved_slab, "None"))}</td>
        <td>${frappe.utils.escape_html(this.format_slab(row.next_slab, "Highest slab achieved"))}</td>
        <td class="snrg-scheme-right">${row.next_slab ? format_currency(row.shortfall_amount || 0) : "0"}</td>
        <td class="snrg-scheme-right">${format_currency(row.quotation_amount || 0)}</td>
        <td>${frappe.utils.escape_html(this.format_slab(row.projected_slab, "None"))}</td>
        <td class="snrg-scheme-right">${format_currency(row.projected_amount || row.eligible_amount || 0)}</td>
        <td class="snrg-scheme-right">${row.projected_next_slab ? format_currency(row.projected_shortfall_amount || 0) : "0"}</td>
        <td class="snrg-scheme-right">
          <button class="snrg-scheme-detail-btn" data-show-details="${frappe.utils.escape_html(key)}">Details</button>
        </td>
      </tr>
    `;
  }

  render_category_customer_row(scheme, row, index) {
    const key = `row-${this.detailKeyCounter++}`;
    this.customerIndex[key] = { scheme, row };
    const categoryCells = this.get_scheme_categories(scheme).map((category) => `
      <td class="snrg-scheme-right">${format_currency(row.category_amounts?.[category] || 0)}</td>
    `).join("");

    return `
      <tr>
        <td>
          ${frappe.utils.escape_html(row.customer_name || row.customer || "")}
          <div class="snrg-scheme-subtitle">${frappe.utils.escape_html(row.customer || "")}</div>
        </td>
        ${categoryCells}
        <td class="snrg-scheme-right">${format_currency(row.eligible_amount || 0)}</td>
        <td>${frappe.utils.escape_html((row.achieved_rewards || []).join(", ") || "None")}</td>
        <td class="snrg-scheme-right">${format_currency(row.projected_amount || 0)}</td>
        <td>${frappe.utils.escape_html((row.projected_rewards || []).join(", ") || "None")}</td>
        <td class="snrg-scheme-right">${row.projected_next_slab ? format_currency(row.projected_shortfall_amount || 0) : "0"}</td>
        <td class="snrg-scheme-right">
          <button class="snrg-scheme-detail-btn" data-show-details="${frappe.utils.escape_html(key)}">Details</button>
        </td>
      </tr>
    `;
  }

  format_slab(slab, fallback) {
    if (!slab) return fallback;
    return `${format_currency(slab.amount || 0)} - ${slab.reward || ""}`;
  }

  render_detail_card(label, value) {
    return `
      <div class="snrg-scheme-detail-card">
        <div class="snrg-scheme-detail-card-label">${frappe.utils.escape_html(label)}</div>
        <div class="snrg-scheme-detail-card-value">${frappe.utils.escape_html(String(value || ""))}</div>
      </div>
    `;
  }

  open_customer_details(key) {
    const entry = this.customerIndex[key];
    if (!entry) return;

    const { scheme, row } = entry;
    const categoryCards = this.get_scheme_categories(scheme).map((category) => (
      this.render_detail_card(category, format_currency(row.category_amounts?.[category] || 0))
    )).join("");
    const summaryCards = scheme.scheme_type === "Period Cumulative Category Target Slab"
      ? `
          ${categoryCards}
          ${this.render_detail_card("Invoice Total", format_currency(row.eligible_amount || 0))}
          ${this.render_detail_card("Rewards Achieved", (row.achieved_rewards || []).join(", ") || "None")}
          ${this.render_detail_card("Projected Rewards", (row.projected_rewards || []).join(", ") || "None")}
          ${this.render_detail_card("Projected Total", format_currency(row.projected_amount || 0))}
          ${this.render_detail_card("Next Gap", row.projected_next_slab ? format_currency(row.projected_shortfall_amount || 0) : "0")}
          ${this.render_detail_card("Invoices", format_number(row.eligible_invoice_count || 0))}
          ${this.render_detail_card("Quotations", format_number(row.eligible_quotation_count || 0))}
          ${this.render_detail_card("Paid", format_currency(row.payment_summary?.paid_amount || 0))}
          ${this.render_detail_card("Outstanding", format_currency(row.payment_summary?.outstanding_amount || 0))}
        `
      : `
          ${this.render_detail_card("Invoice Eligible", format_currency(row.eligible_amount || 0))}
          ${this.render_detail_card("Quotation Eligible", format_currency(row.quotation_amount || 0))}
          ${this.render_detail_card("Projected Eligible", format_currency(row.projected_amount || row.eligible_amount || 0))}
          ${this.render_detail_card("Shortfall", row.next_slab ? format_currency(row.shortfall_amount || 0) : "0")}
          ${this.render_detail_card("Slab Achieved", this.format_slab(row.achieved_slab, "None"))}
          ${this.render_detail_card("Projected Slab", this.format_slab(row.projected_slab, "None"))}
          ${this.render_detail_card("Next Slab", this.format_slab(row.next_slab, "Highest slab achieved"))}
          ${this.render_detail_card("Payment Status", row.payment_summary?.payment_status || "")}
          ${this.render_detail_card("Invoices", format_number(row.eligible_invoice_count || 0))}
          ${this.render_detail_card("Quotations", format_number(row.eligible_quotation_count || 0))}
          ${this.render_detail_card("Paid", format_currency(row.payment_summary?.paid_amount || 0))}
          ${this.render_detail_card("Outstanding", format_currency(row.payment_summary?.outstanding_amount || 0))}
        `;
    const dialog = frappe.msgprint({
      title: `${row.customer_name || row.customer} - ${scheme.scheme_name}`,
      wide: true,
      message: `
        <div class="snrg-scheme-detail-shell">
          <div class="snrg-scheme-detail-summary">
            ${summaryCards}
          </div>
          <div class="snrg-scheme-detail-grid">
            <div class="snrg-scheme-detail-section">
              <h5>Invoice-wise Sales</h5>
              ${this.render_invoice_details(row.invoice_details || [])}
            </div>
            <div class="snrg-scheme-detail-section">
              <h5>Quotation-wise Pipeline</h5>
              ${this.render_quotation_details(row.quotation_details || [])}
            </div>
          </div>
          <div class="snrg-scheme-detail-section snrg-scheme-detail-items">
            <h5>Projected Item-wise Sales</h5>
            ${this.render_item_details(row.projected_top_items || row.top_items || [])}
          </div>
        </div>
      `,
    });
    dialog.$wrapper.addClass("snrg-scheme-detail-modal");
  }

  render_invoice_details(rows) {
    if (!rows.length) return `<div class="snrg-scheme-empty">No invoice details available.</div>`;

    return `
      <table class="snrg-scheme-dialog-table">
        <thead>
          <tr>
            <th>Invoice</th>
            <th>Date</th>
            <th class="snrg-scheme-right">Items</th>
            <th class="snrg-scheme-right">Value</th>
            <th class="snrg-scheme-right">Paid</th>
            <th class="snrg-scheme-right">Outstanding</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${frappe.utils.escape_html(row.sales_invoice || "")}</td>
              <td>${frappe.utils.escape_html(row.posting_date || "")}</td>
              <td class="snrg-scheme-right">${format_number(row.item_count || 0)}</td>
              <td class="snrg-scheme-right">${format_currency(row.amount || 0)}</td>
              <td class="snrg-scheme-right">${format_currency(row.paid_amount || 0)}</td>
              <td class="snrg-scheme-right">${format_currency(row.outstanding_amount || 0)}</td>
              <td>${frappe.utils.escape_html(row.payment_status || "")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  render_quotation_details(rows) {
    if (!rows.length) return `<div class="snrg-scheme-empty">No quotation details available.</div>`;

    return `
      <table class="snrg-scheme-dialog-table">
        <thead>
          <tr>
            <th>Quotation</th>
            <th>Date</th>
            <th>Status</th>
            <th class="snrg-scheme-right">Items</th>
            <th class="snrg-scheme-right">Value</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${frappe.utils.escape_html(row.quotation || "")}</td>
              <td>${frappe.utils.escape_html(row.transaction_date || "")}</td>
              <td>${frappe.utils.escape_html(row.quotation_status || "")}</td>
              <td class="snrg-scheme-right">${format_number(row.item_count || 0)}</td>
              <td class="snrg-scheme-right">${format_currency(row.amount || 0)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  render_item_details(rows) {
    if (!rows.length) return `<div class="snrg-scheme-empty">No item details available.</div>`;

    return `
      <table class="snrg-scheme-dialog-table">
        <thead>
          <tr>
            <th>Item</th>
            <th class="snrg-scheme-right">Qty</th>
            <th class="snrg-scheme-right">Value</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>
                ${frappe.utils.escape_html(row.item_code || "")}
                <div class="snrg-scheme-subtitle">${frappe.utils.escape_html(row.item_name || "")}</div>
              </td>
              <td class="snrg-scheme-right">${format_number(row.qty || 0)} ${frappe.utils.escape_html(row.uom || "")}</td>
              <td class="snrg-scheme-right">${format_currency(row.amount || 0)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }
}
