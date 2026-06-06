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
          min-width: 980px;
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
          grid-template-columns: 1fr 1fr;
          gap: 14px;
        }
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
    this.detailKeyCounter = 0;

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
          ${this.render_customer_table(scheme)}
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

  render_customer_table(scheme) {
    const rows = scheme.customers || [];
    if (!rows.length) {
      return `<div class="snrg-scheme-empty">No eligible customer sales found.</div>`;
    }

    return `
      <table class="snrg-scheme-table">
        <thead>
          <tr>
            <th>Customer</th>
            <th class="snrg-scheme-right">Eligible Value</th>
            <th>Slab Achieved Till Now</th>
            <th>Next Achievable Slab</th>
            <th class="snrg-scheme-right">Shortfall</th>
            <th class="snrg-scheme-right">Invoices</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row, index) => this.render_customer_row(scheme, row, index)).join("")}
        </tbody>
      </table>
    `;
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
        <td class="snrg-scheme-right">${format_number(row.eligible_invoice_count || 0)}</td>
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
    frappe.msgprint({
      title: `${row.customer_name || row.customer} - ${scheme.scheme_name}`,
      wide: true,
      message: `
        <p>
          Eligible Value: <strong>${format_currency(row.eligible_amount || 0)}</strong><br>
          Slab Achieved Till Now: <strong>${frappe.utils.escape_html(this.format_slab(row.achieved_slab, "None"))}</strong><br>
          Next Achievable Slab: <strong>${frappe.utils.escape_html(this.format_slab(row.next_slab, "Highest slab achieved"))}</strong>
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
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${frappe.utils.escape_html(row.sales_invoice || "")}</td>
              <td>${frappe.utils.escape_html(row.posting_date || "")}</td>
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
