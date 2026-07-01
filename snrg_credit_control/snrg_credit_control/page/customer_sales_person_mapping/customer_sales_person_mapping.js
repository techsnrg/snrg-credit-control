frappe.pages["customer-sales-person-mapping"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Customer Sales Person Mapping",
    single_column: true,
  });

  wrapper.customer_sales_person_mapping = new SnrgCustomerSalesPersonMapping(page, wrapper);
};

class SnrgCustomerSalesPersonMapping {
  constructor(page, wrapper) {
    this.page = page;
    this.wrapper = $(wrapper);
    this.controls = {};
    this.rows = [];
    this.total = 0;
    this.limitStart = 0;
    this.pageLength = 50;
    this.selectedCustomers = new Set();
    this.setup();
  }

  setup() {
    this.page.set_primary_action("Refresh", () => this.refresh(), "refresh");
    this.renderShell();
    this.makeFilters();
    this.bindEvents();
    this.applyRouteOptions();
  }

  renderShell() {
    this.wrapper.find(".layout-main-section").html(`
      <style>
        .snrg-cspm-page { display:flex; flex-direction:column; gap:14px; color:#172033; }
        .snrg-cspm-toolbar { display:grid; grid-template-columns:minmax(220px, 300px) minmax(110px, 150px) repeat(3, minmax(180px, 1fr)); gap:12px; align-items:end; }
        .snrg-cspm-command-row { display:flex; justify-content:flex-end; gap:8px; flex-wrap:wrap; }
        .snrg-cspm-actions { display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
        .snrg-cspm-button { border:1px solid #d9e1ec; border-radius:6px; padding:8px 11px; background:#fff; color:#1f3a5f; font-size:12px; font-weight:700; cursor:pointer; }
        .snrg-cspm-button.primary { background:#1f6feb; border-color:#1f6feb; color:#fff; }
        .snrg-cspm-button.danger { color:#b42318; border-color:#f3c3bd; }
        .snrg-cspm-button:disabled { opacity:.55; cursor:not-allowed; }
        .snrg-cspm-panel { border:1px solid #e1e7ef; border-radius:8px; background:#fff; overflow:hidden; }
        .snrg-cspm-panel-head { display:flex; justify-content:space-between; align-items:center; gap:12px; padding:12px 14px; border-bottom:1px solid #e1e7ef; background:#f8fafc; }
        .snrg-cspm-panel-title { font-size:14px; font-weight:800; color:#101828; }
        .snrg-cspm-panel-subtitle { font-size:12px; color:#667085; margin-top:2px; }
        .snrg-cspm-table-wrap { overflow:auto; }
        .snrg-cspm-table { width:100%; border-collapse:collapse; min-width:860px; }
        .snrg-cspm-table th, .snrg-cspm-table td { padding:10px 12px; border-bottom:1px solid #edf1f7; vertical-align:middle; font-size:13px; }
        .snrg-cspm-table th { background:#fbfcfe; color:#475467; font-weight:800; text-align:left; white-space:nowrap; }
        .snrg-cspm-table tr:hover td { background:#f9fbff; }
        .snrg-cspm-customer { font-weight:800; color:#1849a9; cursor:pointer; }
        .snrg-cspm-sales-person { color:#1849a9; cursor:pointer; font-weight:700; }
        .snrg-cspm-status { display:inline-flex; align-items:center; border-radius:999px; padding:4px 8px; font-size:12px; font-weight:800; border:1px solid #d9e1ec; }
        .snrg-cspm-status.mapped { color:#047857; background:#ecfdf3; border-color:#abefc6; }
        .snrg-cspm-status.unmapped { color:#667085; background:#f8fafc; }
        .snrg-cspm-muted { color:#667085; font-size:12px; }
        .snrg-cspm-empty { padding:28px 16px; text-align:center; color:#667085; font-size:13px; }
        .snrg-cspm-footer { display:flex; justify-content:space-between; align-items:center; padding:10px 14px; gap:10px; border-top:1px solid #edf1f7; }
        @media (max-width: 900px) {
          .snrg-cspm-toolbar { grid-template-columns:1fr; }
          .snrg-cspm-actions { justify-content:flex-start; }
          .snrg-cspm-command-row { justify-content:flex-start; }
        }
      </style>
      <div class="snrg-cspm-page">
        <section class="snrg-cspm-toolbar">
          <div class="snrg-cspm-sales-person-action"></div>
          <div class="snrg-cspm-contribution-field"></div>
          <div class="snrg-cspm-customer-filter"></div>
          <div class="snrg-cspm-customer-group-filter"></div>
          <div class="snrg-cspm-territory-filter"></div>
        </section>
        <section class="snrg-cspm-command-row">
          <button class="snrg-cspm-button primary" data-action="add">Add Selected Customers</button>
          <button class="snrg-cspm-button danger" data-action="remove">Remove Selected</button>
        </section>
        <section class="snrg-cspm-panel">
          <div class="snrg-cspm-panel-head">
            <div>
              <div class="snrg-cspm-panel-title">Customers</div>
              <div class="snrg-cspm-panel-subtitle" data-role="table-summary">Select rows below, then add or remove the selected salesperson mapping.</div>
            </div>
            <button class="snrg-cspm-button" data-action="clear-selection">Clear Selection</button>
          </div>
          <div class="snrg-cspm-table-wrap">
            <table class="snrg-cspm-table">
              <thead>
                <tr>
                  <th style="width:36px;"><input type="checkbox" data-action="toggle-page"></th>
                  <th>Customer</th>
                  <th>Customer Group</th>
                  <th>Territory</th>
                  <th>Sales Person</th>
                  <th style="width:130px;">Allocation %</th>
                  <th style="width:120px;">Mapping Status</th>
                </tr>
              </thead>
              <tbody class="snrg-cspm-body"></tbody>
            </table>
          </div>
          <div class="snrg-cspm-footer">
            <div class="snrg-cspm-muted" data-role="range"></div>
            <div class="snrg-cspm-actions">
              <button class="snrg-cspm-button" data-action="prev">Previous</button>
              <button class="snrg-cspm-button" data-action="next">Next</button>
            </div>
          </div>
        </section>
      </div>
    `);
  }

  makeFilters() {
    this.controls.salesPerson = frappe.ui.form.make_control({
      parent: this.wrapper.find(".snrg-cspm-sales-person-action"),
      df: {
        fieldtype: "Link",
        fieldname: "sales_person",
        label: "Sales Person Name",
        options: "Sales Person",
        placeholder: "Select sales person",
        change: () => {
          this.limitStart = 0;
          this.selectedCustomers.clear();
          this.refresh();
        },
      },
      render_input: true,
    });

    this.controls.contribution = frappe.ui.form.make_control({
      parent: this.wrapper.find(".snrg-cspm-contribution-field"),
      df: {
        fieldtype: "Float",
        fieldname: "contribution",
        label: "Contribution %",
        default: 100,
      },
      render_input: true,
    });
    this.controls.contribution.set_value(100);

    this.controls.customer = frappe.ui.form.make_control({
      parent: this.wrapper.find(".snrg-cspm-customer-filter"),
      df: {
        fieldtype: "Link",
        fieldname: "customer",
        label: "Customer Name",
        options: "Customer",
        change: () => {
          this.limitStart = 0;
          this.selectedCustomers.clear();
          this.refresh();
        },
      },
      render_input: true,
    });

    this.controls.customerGroup = frappe.ui.form.make_control({
      parent: this.wrapper.find(".snrg-cspm-customer-group-filter"),
      df: {
        fieldtype: "Link",
        fieldname: "customer_group",
        label: "Customer Group",
        options: "Customer Group",
        change: () => {
          this.limitStart = 0;
          this.selectedCustomers.clear();
          this.refresh();
        },
      },
      render_input: true,
    });

    this.controls.territory = frappe.ui.form.make_control({
      parent: this.wrapper.find(".snrg-cspm-territory-filter"),
      df: {
        fieldtype: "Link",
        fieldname: "territory",
        label: "Territory",
        options: "Territory",
        change: () => {
          this.limitStart = 0;
          this.selectedCustomers.clear();
          this.refresh();
        },
      },
      render_input: true,
    });
  }

  bindEvents() {
    this.wrapper.on("click", "[data-action='add']", () => this.addSelectedCustomers());
    this.wrapper.on("click", "[data-action='remove']", () => this.removeSelected());
    this.wrapper.on("click", "[data-action='clear-selection']", () => {
      this.selectedCustomers.clear();
      this.render();
    });
    this.wrapper.on("click", "[data-action='prev']", () => {
      if (this.limitStart <= 0) return;
      this.limitStart = Math.max(0, this.limitStart - this.pageLength);
      this.refresh();
    });
    this.wrapper.on("click", "[data-action='next']", () => {
      if (this.limitStart + this.pageLength >= this.total) return;
      this.limitStart += this.pageLength;
      this.refresh();
    });
    this.wrapper.on("change", "[data-action='toggle-page']", (event) => {
      const checked = $(event.currentTarget).prop("checked");
      this.rows.forEach((row) => {
        if (checked) this.selectedCustomers.add(row.customer);
        else this.selectedCustomers.delete(row.customer);
      });
      this.render();
    });
    this.wrapper.on("change", "[data-role='row-check']", (event) => {
      const customer = $(event.currentTarget).data("customer");
      if ($(event.currentTarget).prop("checked")) this.selectedCustomers.add(customer);
      else this.selectedCustomers.delete(customer);
      this.updateSummary();
    });
    this.wrapper.on("click", "[data-role='open-customer']", (event) => {
      frappe.set_route("Form", "Customer", $(event.currentTarget).data("customer"));
    });
    this.wrapper.on("click", "[data-role='select-sales-person']", (event) => {
      const salesPerson = $(event.currentTarget).data("sales-person");
      if (!salesPerson) return;
      this.controls.salesPerson.set_value(salesPerson);
      frappe.show_alert({
        message: `Sales Person selected: ${frappe.utils.escape_html(salesPerson)}`,
        indicator: "blue",
      });
    });
  }

  applyRouteOptions() {
    const salesPerson = frappe.route_options && frappe.route_options.sales_person;
    if (salesPerson) {
      this.controls.salesPerson.set_value(salesPerson);
      frappe.route_options = null;
      return;
    }
    this.refresh();
  }

  getSalesPerson() {
    return this.controls.salesPerson.get_value();
  }

  getContributionPercentage() {
    const value = this.controls.contribution.get_value();
    if (value === null || value === undefined || value === "") {
      return 100;
    }
    return value;
  }

  refresh() {
    frappe.call({
      method: "snrg_credit_control.customer_sales_person_mapping.get_mapped_customers",
      args: {
        sales_person: this.getSalesPerson(),
        customer: this.controls.customer.get_value(),
        customer_group: this.controls.customerGroup.get_value(),
        territory: this.controls.territory.get_value(),
        limit_start: this.limitStart,
        limit_page_length: this.pageLength,
      },
      freeze: true,
      freeze_message: "Loading customers...",
      callback: (r) => {
        const message = r.message || {};
        this.rows = message.rows || [];
        this.total = message.total || 0;
        this.render();
      },
    });
  }

  render() {
    const body = this.wrapper.find(".snrg-cspm-body");
    if (!this.rows.length) {
      body.html(`<tr><td colspan="7"><div class="snrg-cspm-empty">No customers found for the selected filters.</div></td></tr>`);
      this.wrapper.find("[data-action='toggle-page']").prop("checked", false);
      this.updateSummary();
      this.updatePagination();
      return;
    }

    body.html(this.rows.map((row) => `
      <tr>
        <td><input type="checkbox" data-role="row-check" data-customer="${frappe.utils.escape_html(row.customer)}" ${this.selectedCustomers.has(row.customer) ? "checked" : ""}></td>
        <td>
          <div class="snrg-cspm-customer" data-role="open-customer" data-customer="${frappe.utils.escape_html(row.customer)}">${frappe.utils.escape_html(row.customer_name || row.customer)}</div>
          <div class="snrg-cspm-muted">${frappe.utils.escape_html(row.customer)}</div>
        </td>
        <td>${frappe.utils.escape_html(row.customer_group || "")}</td>
        <td>${frappe.utils.escape_html(row.territory || "")}</td>
        <td>
          <div class="snrg-cspm-sales-person" data-role="select-sales-person" data-sales-person="${frappe.utils.escape_html(row.sales_person || "")}">${row.is_mapped ? frappe.utils.escape_html(row.sales_person_name || row.sales_person || "") : "-"}</div>
          <div class="snrg-cspm-muted">${row.is_mapped ? frappe.utils.escape_html(row.sales_person || "") : "Not mapped to selected sales person"}</div>
        </td>
        <td>${row.is_mapped ? frappe.format(row.allocated_percentage || 0, { fieldtype: "Percent" }) : "-"}</td>
        <td>
          <span class="snrg-cspm-status ${row.is_mapped ? "mapped" : "unmapped"}">${row.is_mapped ? "Mapped" : "Not Mapped"}</span>
          ${row.disabled ? `<div class="snrg-cspm-muted">Disabled</div>` : ""}
        </td>
      </tr>
    `).join(""));

    const allChecked = this.rows.every((row) => this.selectedCustomers.has(row.customer));
    this.wrapper.find("[data-action='toggle-page']").prop("checked", allChecked);
    this.updateSummary();
    this.updatePagination();
  }

  updateSummary() {
    const mapped = this.rows.filter((row) => row.is_mapped).length;
    const selected = this.selectedCustomers.size;
    this.wrapper.find("[data-role='table-summary']").text(
      `${this.total} customer(s) found. ${mapped} mapped on this page. ${selected} selected.`
    );
  }

  updatePagination() {
    const from = this.total ? this.limitStart + 1 : 0;
    const to = Math.min(this.limitStart + this.pageLength, this.total);
    this.wrapper.find("[data-role='range']").text(`${from}-${to} of ${this.total}`);
    this.wrapper.find("[data-action='prev']").prop("disabled", this.limitStart <= 0);
    this.wrapper.find("[data-action='next']").prop("disabled", this.limitStart + this.pageLength >= this.total);
  }

  addSelectedCustomers() {
    const salesPerson = this.getSalesPerson();
    if (!salesPerson) {
      frappe.msgprint("Please select a Sales Person Name first.");
      return;
    }
    const customers = Array.from(this.selectedCustomers);
    if (!customers.length) {
      frappe.msgprint("Please select customer rows from the table first.");
      return;
    }
    const contribution = this.getContributionPercentage();
    if (contribution < 0 || contribution > 100) {
      frappe.msgprint("Contribution % must be between 0 and 100.");
      return;
    }

    this.addCustomers(customers, contribution);
  }

  addCustomers(customers, allocatedPercentage) {
    const salesPerson = this.getSalesPerson();
    frappe.call({
      method: "snrg_credit_control.customer_sales_person_mapping.add_sales_person_to_customers",
      args: {
        sales_person: salesPerson,
        customers,
        allocated_percentage: allocatedPercentage,
      },
      freeze: true,
      freeze_message: "Adding sales person to customers...",
      callback: (r) => {
        const result = r.message || {};
        this.showResult("Customers Added", result.added || [], result.skipped || [], result.failed || []);
        this.selectedCustomers.clear();
        this.refresh();
      },
    });
  }

  removeSelected() {
    const salesPerson = this.getSalesPerson();
    if (!salesPerson) {
      frappe.msgprint("Please select a Sales Person Name first.");
      return;
    }
    const customers = Array.from(this.selectedCustomers);
    if (!customers.length) {
      frappe.msgprint("Please select at least one mapped customer.");
      return;
    }

    frappe.confirm(`Remove ${customers.length} customer mapping(s) for the selected sales person?`, () => {
      frappe.call({
        method: "snrg_credit_control.customer_sales_person_mapping.remove_sales_person_from_customers",
        args: { sales_person: salesPerson, customers },
        freeze: true,
        freeze_message: "Removing customer mappings...",
        callback: (r) => {
          const result = r.message || {};
          this.selectedCustomers.clear();
          this.showResult("Customers Removed", result.removed || [], result.skipped || [], result.failed || []);
          this.refresh();
        },
      });
    });
  }

  showResult(title, successful, skipped, failed) {
    const indicator = failed.length ? "orange" : "green";
    frappe.show_alert({
      message: `${title}: ${successful.length} done, ${skipped.length} skipped, ${failed.length} failed`,
      indicator,
    });

    if (failed.length) {
      frappe.msgprint({
        title,
        indicator: "orange",
        message: failed.map((row) => `${frappe.utils.escape_html(row.customer)}: ${frappe.utils.escape_html(row.reason)}`).join("<br>"),
      });
    }
  }
}
