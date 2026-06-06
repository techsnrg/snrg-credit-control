frappe.pages["scheme-suggestions"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Scheme Suggestions",
    single_column: true,
  });

  wrapper.scheme_suggestions = new SnrgSchemeSuggestions(page, wrapper);
};

class SnrgSchemeSuggestions {
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
    this.render_shell();
    this.make_filters();
    this.bind_events();
  }

  render_shell() {
    this.wrapper.find(".layout-main-section").html(`
      <style>
        .snrg-scheme-page { display: grid; gap: 16px; color: #172033; }
        .snrg-scheme-filter-row {
          display: grid;
          grid-template-columns: minmax(220px, 1fr) minmax(260px, 1.2fr) minmax(160px, .7fr);
          gap: 12px;
          align-items: end;
        }
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
          grid-template-columns: repeat(3, minmax(0, 1fr));
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
          min-width: 1320px;
          border-collapse: collapse;
          border: 1px solid #edf1f7;
          border-radius: 8px;
          overflow: hidden;
          background: #fff;
        }
        .snrg-scheme-table th,
        .snrg-scheme-table td {
          padding: 9px 10px;
          border-bottom: 1px solid #edf1f7;
          font-size: 12px;
          vertical-align: top;
        }
        .snrg-scheme-table th { background: #f8fafc; color: #667085; font-weight: 800; }
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
          font-size: 12px;
          font-weight: 700;
        }
        .snrg-scheme-detail-grid {
          display: grid;
          grid-template-columns: minmax(620px, 1.2fr) minmax(520px, 1fr);
          gap: 18px;
          align-items: start;
        }
        .snrg-scheme-detail-modal .modal-dialog {
          width: min(1280px, calc(100vw - 64px));
          max-width: min(1280px, calc(100vw - 64px));
        }
        .snrg-scheme-detail-modal .modal-body { overflow-x: auto; }
        .snrg-scheme-dialog-table {
          width: 100%;
          border-collapse: collapse;
          border: 1px solid #edf1f7;
        }
        .snrg-scheme-dialog-table th,
        .snrg-scheme-dialog-table td {
          padding: 8px 9px;
          border-bottom: 1px solid #edf1f7;
          font-size: 12px;
        }
        .snrg-scheme-dialog-table th { background: #f8fafc; color: #667085; }
        @media (max-width: 900px) {
          .snrg-scheme-filter-row,
          .snrg-scheme-metrics,
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
          ${this.render_metric("Total Eligible Value", format_currency(scheme.eligible_amount))}
          ${this.render_metric("Customers", format_number(scheme.customer_count || 0))}
          ${this.render_metric("As On", this.data.as_on_date || "")}
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

    return `
      <table class="snrg-scheme-table">
        <thead>
          <tr>
            ${this.render_sort_header(tableKey, "customer_name", "Customer")}
            ${this.render_sort_header(tableKey, "eligible_amount", "Eligible Value", true)}
            ${this.render_sort_header(tableKey, "achieved_slab", "Slab Achieved Till Now")}
            ${this.render_sort_header(tableKey, "next_slab", "Next Achievable Slab")}
            ${this.render_sort_header(tableKey, "shortfall_amount", "Shortfall", true)}
            ${this.render_sort_header(tableKey, "paid_amount", "Paid", true)}
            ${this.render_sort_header(tableKey, "outstanding_amount", "Outstanding", true)}
            ${this.render_sort_header(tableKey, "payment_status", "Payment Status")}
            <th></th>
          </tr>
          <tr>
            ${this.render_filter_cell(tableKey, "customer", "Search customer")}
            ${this.render_filter_cell(tableKey, "eligible_amount", "Search value", true)}
            ${this.render_filter_cell(tableKey, "achieved_slab", "Search slab")}
            ${this.render_filter_cell(tableKey, "next_slab", "Search next slab")}
            ${this.render_filter_cell(tableKey, "shortfall_amount", "Search shortfall", true)}
            ${this.render_filter_cell(tableKey, "paid_amount", "Search paid", true)}
            ${this.render_filter_cell(tableKey, "outstanding_amount", "Search outstanding", true)}
            ${this.render_filter_cell(tableKey, "payment_status", "Search status")}
            <th></th>
          </tr>
        </thead>
        <tbody data-customer-body="${frappe.utils.escape_html(tableKey)}">
          ${this.render_customer_rows(scheme, tableKey)}
        </tbody>
      </table>
    `;
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
      return `<tr><td colspan="9" class="snrg-scheme-empty">No rows match the current search.</td></tr>`;
    }

    return rows.map((row, index) => this.render_customer_row(scheme, row, index)).join("");
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
    if (field === "customer") {
      return `${row.customer_name || ""} ${row.customer || ""}`;
    }
    if (field === "achieved_slab") {
      return this.format_slab(row.achieved_slab, "None");
    }
    if (field === "next_slab") {
      return this.format_slab(row.next_slab, "Highest slab achieved");
    }
    if (field === "eligible_amount" || field === "shortfall_amount" || field === "paid_amount" || field === "outstanding_amount") {
      const value = field === "paid_amount"
        ? row.payment_summary?.paid_amount
        : field === "outstanding_amount"
          ? row.payment_summary?.outstanding_amount
          : row[field];
      return `${format_currency(value || 0)} ${value || 0}`;
    }
    if (field === "payment_status") {
      return row.payment_summary?.payment_status || "";
    }
    return String(row[field] || "");
  }

  get_sort_value(row, field) {
    if (field === "customer_name") return row.customer_name || row.customer || "";
    if (field === "achieved_slab") return row.achieved_slab ? row.achieved_slab.amount || 0 : 0;
    if (field === "next_slab") return row.next_slab ? row.next_slab.amount || 0 : Infinity;
    if (field === "paid_amount") return Number(row.payment_summary?.paid_amount || 0);
    if (field === "outstanding_amount") return Number(row.payment_summary?.outstanding_amount || 0);
    if (field === "payment_status") return row.payment_summary?.payment_status || "";
    if (field === "eligible_amount" || field === "shortfall_amount") {
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
        <td class="snrg-scheme-right">${format_currency(row.payment_summary?.paid_amount || 0)}</td>
        <td class="snrg-scheme-right">${format_currency(row.payment_summary?.outstanding_amount || 0)}</td>
        <td>${frappe.utils.escape_html(row.payment_summary?.payment_status || "")}</td>
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

  open_customer_details(key) {
    const entry = this.customerIndex[key];
    if (!entry) return;

    const { scheme, row } = entry;
    const dialog = frappe.msgprint({
      title: `${row.customer_name || row.customer} - ${scheme.scheme_name}`,
      wide: true,
      message: `
        <p>
          Eligible Value: <strong>${format_currency(row.eligible_amount || 0)}</strong><br>
          Slab Achieved Till Now: <strong>${frappe.utils.escape_html(this.format_slab(row.achieved_slab, "None"))}</strong><br>
          Next Achievable Slab: <strong>${frappe.utils.escape_html(this.format_slab(row.next_slab, "Highest slab achieved"))}</strong><br>
          Invoices: <strong>${format_number(row.eligible_invoice_count || 0)}</strong><br>
          Paid Against Scheme Invoices: <strong>${format_currency(row.payment_summary?.paid_amount || 0)}</strong><br>
          Outstanding Against Scheme Invoices: <strong>${format_currency(row.payment_summary?.outstanding_amount || 0)}</strong>
        </p>
        <div class="snrg-scheme-detail-grid">
          <div>
            <h5>Invoice-wise Sales</h5>
            ${this.render_invoice_details(row.invoice_details || [])}
          </div>
          <div>
            <h5>Item-wise Sales</h5>
            ${this.render_item_details(row.top_items || [])}
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
