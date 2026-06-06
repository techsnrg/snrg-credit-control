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
    this.setup();
  }

  setup() {
    this.page.set_primary_action("Get Suggestions", () => this.refresh(), "search");
    this.render_shell();
    this.make_filters();
  }

  render_shell() {
    this.wrapper.find(".layout-main-section").html(`
      <style>
        .snrg-scheme-page { display: grid; gap: 16px; color: #172033; }
        .snrg-scheme-filter-row {
          display: grid;
          grid-template-columns: minmax(240px, 1.2fr) minmax(200px, .9fr) minmax(220px, 1fr) minmax(150px, .6fr);
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
        .snrg-scheme-body {
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
          gap: 16px;
          padding: 0 16px 16px;
        }
        .snrg-scheme-section-title {
          font-size: 13px;
          font-weight: 800;
          color: #344054;
          margin: 0 0 8px;
        }
        .snrg-scheme-table {
          width: 100%;
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
        @media (max-width: 900px) {
          .snrg-scheme-filter-row,
          .snrg-scheme-metrics,
          .snrg-scheme-body { grid-template-columns: 1fr; }
        }
      </style>
      <div class="snrg-scheme-page">
        <div class="snrg-scheme-filter-row" data-filter-row></div>
        <div data-results>
          <div class="snrg-scheme-empty">Select a customer to see scheme progress and sales suggestions.</div>
        </div>
      </div>
    `);
  }

  make_filters() {
    const filterRow = this.wrapper.find("[data-filter-row]");

    this.controls.customer = frappe.ui.form.make_control({
      parent: filterRow,
      df: {
        fieldtype: "Link",
        fieldname: "customer",
        label: "Customer",
        options: "Customer",
        reqd: 1,
        change: () => this.refresh(),
      },
      render_input: true,
    });

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

  get_values() {
    return {
      customer: this.controls.customer.get_value(),
      company: this.controls.company.get_value(),
      scheme: this.controls.scheme.get_value(),
      as_on_date: this.controls.as_on_date.get_value(),
    };
  }

  async refresh() {
    const values = this.get_values();
    if (!values.customer) {
      this.render_empty("Select a customer to see scheme progress and sales suggestions.");
      return;
    }

    try {
      const response = await frappe.call({
        method: "snrg_credit_control.scheme_engine.get_customer_scheme_suggestions",
        args: values,
        freeze: true,
        freeze_message: "Checking scheme progress...",
      });
      this.data = response.message || {};
      this.render_results();
    } catch (error) {
      frappe.msgprint({
        title: "Scheme Suggestions Failed",
        message: (error && error.message) || String(error),
        indicator: "red",
      });
    }
  }

  render_empty(message) {
    this.wrapper.find("[data-results]").html(`<div class="snrg-scheme-empty">${frappe.utils.escape_html(message)}</div>`);
  }

  render_results() {
    const suggestions = this.data.suggestions || [];
    if (!suggestions.length) {
      this.render_empty("No active SNRG Scheme progress found for this customer.");
      return;
    }

    this.wrapper.find("[data-results]").html(`
      <div class="snrg-scheme-grid">
        ${suggestions.map((scheme) => this.render_scheme_card(scheme)).join("")}
      </div>
    `);
  }

  render_scheme_card(scheme) {
    const achieved = (scheme.achieved_slabs || []).map((row) => row.reward).join(", ") || "None";
    const nextReward = scheme.next_slab ? scheme.next_slab.reward : "Highest slab achieved";
    const shortfall = scheme.next_slab ? format_currency(scheme.shortfall_amount) : "0";

    return `
      <div class="snrg-scheme-card">
        <div class="snrg-scheme-card-head">
          <div>
            <h3 class="snrg-scheme-title">${frappe.utils.escape_html(scheme.scheme_name || "")}</h3>
            <div class="snrg-scheme-subtitle">
              ${frappe.utils.escape_html(scheme.period_from || "")} to ${frappe.utils.escape_html(scheme.period_upto || "")}
            </div>
          </div>
          <div class="snrg-scheme-pill">${frappe.utils.escape_html(nextReward)}</div>
        </div>
        <div class="snrg-scheme-metrics">
          ${this.render_metric("Eligible Value", format_currency(scheme.eligible_amount))}
          ${this.render_metric("Achieved", achieved)}
          ${this.render_metric("Shortfall", shortfall)}
          ${this.render_metric("Invoices", format_number(scheme.eligible_invoice_count || 0))}
        </div>
        <div class="snrg-scheme-body">
          <div>
            <h4 class="snrg-scheme-section-title">Suggested Additions</h4>
            ${this.render_suggestions_table(scheme.suggestions || [])}
          </div>
          <div>
            <h4 class="snrg-scheme-section-title">Eligible Item History</h4>
            ${this.render_history_table(scheme.top_items || [])}
          </div>
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

  render_suggestions_table(rows) {
    if (!rows.length) {
      return `<div class="snrg-scheme-empty">No next-slab suggestion available.</div>`;
    }

    return `
      <table class="snrg-scheme-table">
        <thead>
          <tr>
            <th>Item</th>
            <th class="snrg-scheme-right">Add Qty</th>
            <th class="snrg-scheme-right">Approx Value</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>
                ${frappe.utils.escape_html(row.item_code || "")}
                <div class="snrg-scheme-subtitle">${frappe.utils.escape_html(row.item_name || "")}</div>
              </td>
              <td class="snrg-scheme-right">${format_number(row.extra_qty || 0)} ${frappe.utils.escape_html(row.uom || "")}</td>
              <td class="snrg-scheme-right">${format_currency(row.extra_amount || 0)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  render_history_table(rows) {
    if (!rows.length) {
      return `<div class="snrg-scheme-empty">No eligible item history in this scheme period.</div>`;
    }

    return `
      <table class="snrg-scheme-table">
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
