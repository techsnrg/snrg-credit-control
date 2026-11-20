(() => {
  const api = "snrg_credit_control.snrg_credit_control.page.scheme_planning.scheme_planning";
  const esc = value => frappe.utils.escape_html(String(value ?? ""));
  const date = value => value ? frappe.datetime.str_to_user(String(value)) : "—";
  const number = value => Number(value || 0);
  const modes = ["Active", "Upcoming", "Closed", "Disabled", "All"];

  window.snrgSchemeWorkspace = {
    mount(host, embedded = false, fixedCustomer = null) {
      return new SchemeWorkspace(host, embedded, fixedCustomer);
    },
  };

  class SchemeWorkspace {
    constructor(host, embedded, fixedCustomer) {
      this.embedded = embedded;
      this.fixedCustomer = fixedCustomer;
      this.company = frappe.defaults.get_user_default("Company") || "";
      this.asOn = frappe.datetime.get_today();
      this.status = "Active";
      this.tab = "progress";
      this.quotations = "0";
      this.customerQuotations = "1";
      this.view = fixedCustomer ? "customer" : "scheme";
      this.register = [];
      this.root = $('<div class="scheme-workspace"></div>').appendTo(host);
      this.root.toggleClass("sw-embedded", embedded);
      const filters = `
        <label>${__("Company")}<select data-field="company"><option value="">${__("All companies")}</option></select></label>
        <label>${__("As of")}<input data-field="asOn" type="date" value="${esc(this.asOn)}"></label>
        <button data-action="reload">${__("Refresh")}</button>`;
      this.root.html(embedded ? `
        ${fixedCustomer ? "" : `<div class="sw-view-switch" role="group" aria-label="${esc(__("Scheme perspective"))}">
          <button data-action="view" data-value="scheme" aria-pressed="true">${__("By scheme")}</button>
          <button data-action="view" data-value="customer" aria-pressed="false">${__("By customer")}</button>
        </div>`}
        <div class="sw-command">
          ${fixedCustomer ? "" : `<label class="sw-picker"><span class="sr-only">${__("Select scheme")}</span>
            <select data-field="selected" aria-label="${esc(__("Select scheme"))}"></select>
          </label>
          <div class="sw-customer-picker" hidden></div>`}
          <details class="sw-filter-menu"><summary>${__("Filters")}</summary>
            <div class="sw-filter-fields">${filters}</div>
          </details>
          ${fixedCustomer ? "" : `<button data-action="new" class="sw-primary">${__("New scheme")}</button>`}
        </div>
        <section class="sw-detail" aria-label="${esc(__("Selected scheme"))}" aria-busy="true"></section>` : `
        <div class="sw-toolbar">
          <label>${__("Company")}<select data-field="company"><option value="">${__("All companies")}</option></select></label>
          <label>${__("As of")}<input data-field="asOn" type="date" value="${esc(this.asOn)}"></label>
          <div class="sw-actions"><button data-action="reload">${__("Refresh")}</button>
          <button data-action="new" class="sw-primary">${__("New scheme")}</button></div>
        </div>
        <div class="sw-layout">
          <section class="sw-register" aria-label="${esc(__("Scheme register"))}">
            <h2>${__("Schemes")}</h2>
            <label class="sw-search"><span>${__("Find a scheme")}</span><input type="search" data-field="schemeSearch" placeholder="${esc(__("Name or series"))}"></label>
            <div class="sw-filters" aria-label="${esc(__("Scheme status"))}"></div>
            <div class="sw-list"></div>
          </section>
          <section class="sw-detail" aria-label="${esc(__("Selected scheme"))}" aria-busy="true"></section>
        </div>`);
      this.detail = this.root.find(".sw-detail");
      this.root.on("change", "[data-field]", ({ currentTarget: event }) => this.change(event));
      this.root.on("input", "[data-field=schemeSearch]", ({ currentTarget: event }) => {
        this.schemeSearch = event.value;
        this.renderRegister();
      });
      this.root.on("input", "[data-field=customerSearch]", ({ currentTarget: event }) => {
        this.customerSearch = event.value;
        this.renderRows();
      });
      this.root.on("click", "[data-action]", ({ currentTarget: event }) => this.action(event.dataset));
      this.load();
    }

    change(input) {
      const field = input.dataset.field;
      if (field === "selected") return this.select(input.value);
      if (field === "asOn" && !input.value) {
        input.value = this.asOn;
        return;
      }
      this[field] = input.value;
      if (field === "quotations") this.loadScheme();
      if (field === "customerQuotations") this.loadCustomerOverview();
      if (field === "reminderDate" && input.value) this.loadReminderPreviews();
      if (field === "company" || field === "asOn") this.load();
    }

    action({ action, value, index }) {
      if (action === "reload") return this.load();
      if (action === "view") return this.switchView(value);
      if (action === "overview-detail") {
        this.customer = Number(value);
        return this.openCustomer(this.overview.schemes[this.customer]);
      }
      if (action === "new") return frappe.new_doc("SNRG Scheme", {
        track_invoice_items: 1, ...(this.company ? { company: this.company } : {}),
      });
      if (action === "configure") return frappe.set_route("Form", "SNRG Scheme", this.selected);
      if (action === "series") return frappe.set_route("List", "SNRG Scheme Series");
      if (action === "status") {
        this.status = value;
        this.renderRegister();
        return;
      }
      if (action === "select") return this.select(value);
      if (action === "tab") {
        this.customer = null;
        this.tab = value;
        return this.renderDetail();
      }
      if (action === "customer") {
        this.customer = Number(value);
        return this.openCustomer();
      }
      if (action === "close-customer") {
        const index = this.customer;
        this.customer = null;
        this.detail.find(".sw-customer-panel").remove();
        const trigger = this.view === "customer" ? "overview-detail" : "customer";
        this.detail.removeClass("sw-has-customer").find(`[data-action=${trigger}][data-value="${index}"]`).trigger("focus");
        return;
      }
      if (action === "document") return frappe.set_route("Form", value, this.documents[Number(index)]);
      if (action === "download") {
        const person = this.view === "customer" ? this.overview.schemes[this.customer] : this.report.customers[this.customer];
        const params = new URLSearchParams({ ...this.customerArgs(person), export_format: value });
        window.open(`/api/method/${api}.export_customer?${params}`, "_blank", "noopener");
      }
    }

    customerArgs(person) {
      return {
        name: person.scheme || this.selected, company: this.company, customer: person.customer,
        as_on_date: this.asOn, quotations: person.scheme ? this.customerQuotations : this.quotations,
        ...(person.invoice ? { invoice: person.invoice } : {}),
      };
    }

    async load() {
      const request = this.registerRequest = (this.registerRequest || 0) + 1;
      this.schemeRequest = (this.schemeRequest || 0) + 1;
      this.detail.attr("aria-busy", "true").html(this.message(__("Loading schemes…")));
      try {
        const { message } = await frappe.call({ method: `${api}.get_register`, args: {
          company: this.company, as_on_date: this.asOn,
        }});
        if (request !== this.registerRequest) return;
        this.register = message.schemes;
        this.currencies = message.currencies;
        this.root.find("[data-field=company]").html(
          `<option value="">${__("All companies")}</option>` + message.companies
            .map(company => `<option value="${esc(company)}">${esc(company)}</option>`).join("")
        ).val(this.company);
        const previous = this.register.find(row => row.name === this.selected);
        const next = previous || this.register.find(row => row.status === "Active") || this.register[0];
        if (next && !this.register.some(row => row.status === this.status)) this.status = next.status;
        if (this.view === "customer") {
          this.overviewKey = null;
          return this.loadCustomerOverview();
        }
        if (next) await this.select(next.name);
        else {
          this.selected = null;
          this.renderRegister();
          this.detail.attr("aria-busy", "false").html(this.message(
            __("No schemes for this company"), __("Create a scheme or select another company.")
          ));
        }
      } catch {
        if (request === this.registerRequest) this.detail.attr("aria-busy", "false")
          .html(this.message(__("Could not load schemes"), __("Refresh to try again.")));
      }
    }

    async switchView(view) {
      if (this.view === view) return;
      this.view = view;
      this.overviewKey = null;
      this.customer = null;
      this.root.find("[data-action=view]").each((_, button) =>
        button.setAttribute("aria-pressed", button.dataset.value === view));
      this.root.find(".sw-picker").prop("hidden", view === "customer");
      const host = this.root.find(".sw-customer-picker").prop("hidden", view !== "customer");
      if (view === "scheme") return this.load();
      if (!this.customerPicker) {
        await frappe.require("controls.bundle.js");
        if (this.view !== "customer" || !host[0].isConnected) return;
        this.customerPicker = frappe.ui.form.make_control({
          parent: host, render_input: true,
          df: {fieldtype: "Link", options: "Customer", fieldname: "overview_customer",
            label: __("Customer"), hide_label: true, placeholder: __("Find customer"),
            change: () => this.loadCustomerOverview()},
        });
        this.customerPicker.$input.attr("aria-label", __("Customer"));
      }
      return this.loadCustomerOverview();
    }

    async loadCustomerOverview() {
      if (this.view !== "customer") return;
      const customer = this.fixedCustomer || this.customerPicker?.get_value();
      const key = JSON.stringify([customer, this.company, this.asOn, this.customerQuotations]);
      if (key === this.overviewKey) return;
      this.overviewKey = key;
      const request = this.schemeRequest = (this.schemeRequest || 0) + 1;
      this.detail.removeClass("sw-has-customer");
      if (!customer) {
        return this.detail.attr("aria-busy", "false").html(this.message(__("Select a customer to see their scheme progress.")));
      }
      this.detail.attr("aria-busy", "true").html(this.message(__("Loading customer schemes…")));
      try {
        const { message } = await frappe.call({method: `${api}.get_customer_overview`, args: {
          customer, company: this.company, as_on_date: this.asOn, quotations: this.customerQuotations,
        }});
        if (request !== this.schemeRequest || this.view !== "customer") return;
        this.overview = message;
        this.detail.attr("aria-busy", "false");
        this.renderCustomerOverview();
      } catch {
        if (request === this.schemeRequest) {
          this.overviewKey = null;
          this.detail.attr("aria-busy", "false").html(this.message(__("Could not load customer schemes")));
        }
      }
    }

    renderCustomerOverview() {
      const rows = this.overview.schemes;
      const showProjected = this.customerQuotations !== "0";
      const payments = rows.some(row => row.eligible_cleared != null);
      this.detail.html(`<div class="sw-content">
        <div class="sw-content-tools"><label>${__("Quotation projection")}
          <select data-field="customerQuotations">
            <option value="0">${__("Invoices only")}</option>
            <option value="1">${__("Include submitted quotations")}</option>
            <option value="2">${__("Include draft and submitted quotations")}</option>
          </select></label></div>
        <div class="sw-results">${rows.length ? this.table([
          __("Scheme"), __("Status"), __("Eligible invoiced"), payments ? __("Invoiced reward") : __("Reward reached"),
          ...(payments ? [__("Eligible cleared"), __("Claimable reward")] : []), __("Next target gap"),
          ...(showProjected ? [__("Projected total")] : []),
        ], rows.map((row, index) => [
          `<button class="sw-link" data-action="overview-detail" data-value="${index}">${esc(row.scheme)}</button>
          <small>${row.invoice ? esc(row.invoice) : `${__("Closes")} ${date(row.valid_upto)}`}</small>`,
          `<span class="sw-status sw-${row.status.toLowerCase()}">${esc(__(row.status))}</span>`,
          this.money(row.eligible_amount, row.currency), esc(row.achieved_rewards?.join(", ") || __("None yet")),
          ...(payments ? [row.eligible_cleared == null ? "—" : this.money(row.eligible_cleared, row.currency),
            row.eligible_cleared == null ? "—" : esc(row.claimable_rewards.join(", ") || __("None yet"))] : []),
          row.eligible_cleared != null ? this.clearanceGap(row, row.currency)
            : row.next_slab ? this.money(row.shortfall_amount, row.currency) : "—",
          ...(showProjected ? [row.projected_amount == null ? "—" : this.money(row.projected_amount, row.currency)] : []),
        ])) : this.message(__("No eligible scheme activity through this date"))}</div></div>`);
      this.content = this.detail.find(".sw-content");
      this.content.find("[data-field=customerQuotations]").val(this.customerQuotations);
    }

    async loadReminderPreviews() {
      const target = this.content.find(".sw-reminder-results");
      target.html(this.message(__("Loading reminder previews…")));
      try {
        const { message } = await frappe.call({ method: `${api}.preview_payment_reminders`, args: {
          name: this.selected, company: this.company, as_on_date: this.reminderDate || this.asOn,
        } });
        if (!target[0]?.isConnected) return;
        target.html(message.previews.length ? message.previews.map(row => `
          <details class="sw-reminder-preview">
            <summary><strong>${esc(row.customer_name || row.customer)}</strong>
              <small>${esc(__("{0} invoice(s)", [row.invoice_count]))}</small></summary>
            <p><strong>${esc(row.subject)}</strong></p>
            <pre>${esc(row.body)}</pre>
          </details>`).join("") : this.message(__("No payment reminders due on this date")));
      } catch {
        target.html(this.message(__("Could not load reminder previews")));
      }
    }

    renderReminderPreviews() {
      const { hard_deadline: hard, reminder_days: reminders } = this.report.payment_rules;
      this.content.html(`<div class="sw-content-tools"><label>${__("Preview date")}
        <input type="date" data-field="reminderDate" value="${esc(this.reminderDate || this.asOn)}"></label></div>
        <p class="sw-source">${esc(__("Preview only. No email will be sent."))}
          · ${esc(__("Reminder days {0} · Final clearance date {1}", [reminders.join(", "), date(hard)]))}</p>
        <div class="sw-reminder-results"></div>`);
      return this.loadReminderPreviews();
    }

    renderRegister() {
      if (this.embedded) {
        const picker = this.root.find("[data-field=selected]");
        const choices = modes.filter(status => status !== "All").map(status => {
          const rows = this.register.filter(row => row.status === status);
          return rows.length ? `<optgroup label="${esc(__(status))}">${rows.map(row =>
            `<option value="${esc(row.name)}">${esc(row.name)}</option>`).join("")}</optgroup>` : "";
        }).join("");
        picker.html(choices || `<option value="">${__("No schemes")}</option>`)
          .prop("disabled", !choices).val(this.selected || "");
        return;
      }
      this.root.find(".sw-filters").html(modes.map(status => {
        const total = status === "All" ? this.register.length : this.register.filter(row => row.status === status).length;
        return `<button data-action="status" data-value="${status}" aria-pressed="${this.status === status}">
          ${esc(__(status))} <span>${total}</span></button>`;
      }).join(""));
      const search = (this.schemeSearch || "").trim().toLowerCase();
      const matching = this.register.filter(row => (this.status === "All" || row.status === this.status)
        && [row.name, row.scheme_series].some(text => String(text || "").toLowerCase().includes(search)));
      this.root.find(".sw-list").html(matching.map(row => `
        <button class="sw-entry" data-action="select" data-value="${esc(row.name)}" aria-pressed="${row.name === this.selected}">
          <strong>${esc(row.name)}</strong><span>${date(row.valid_from)} – ${date(row.valid_upto)}</span>
          <span>${esc(row.scheme_series || row.company || __("All companies"))}</span>
        </button>`).join("") || this.message(__("No matching schemes")));
    }

    select(name) {
      this.selected = name;
      this.tab = "progress";
      this.customer = null;
      this.customerSearch = "";
      this.renderRegister();
      return this.loadScheme();
    }

    async loadScheme() {
      const request = this.schemeRequest = (this.schemeRequest || 0) + 1;
      this.detail.attr("aria-busy", "true").html(this.message(__("Loading scheme…")));
      try {
        const { message } = await frappe.call({ method: `${api}.get_scheme`, args: {
          name: this.selected, company: this.company, as_on_date: this.asOn, quotations: this.quotations,
        }});
        if (request !== this.schemeRequest) return;
        this.report = message;
        this.customer = null;
        this.detail.attr("aria-busy", "false");
        this.renderDetail();
      } catch {
        if (request === this.schemeRequest) this.detail.attr("aria-busy", "false")
          .html(this.message(__("Could not load this scheme"), __("Refresh to try again.")));
      }
    }

    message(title, body = "") {
      return `<div class="sw-message" role="status"><strong>${esc(title)}</strong>${body ? `<p>${esc(body)}</p>` : ""}</div>`;
    }

    money(value, currency = this.report?.currency) {
      return esc(format_currency(number(value), currency || undefined));
    }

    renderDetail() {
      this.detail.removeClass("sw-has-customer");
      const scheme = this.register.find(row => row.name === this.selected);
      const report = this.report;
      const { customers, per_invoice: perInvoice, payment_rules: paymentRules } = report;
      const stat = (label, value) => `<div><span>${esc(label)}</span><strong>${value}</strong></div>`;
      const sum = key => customers.reduce((total, row) => total + number(row[key]), 0);
      const qualificationCount = customers.filter(row => row.achieved_rewards?.length).length;
      const projection = !perInvoice && this.quotations !== "0";
      const showQuoteOption = !perInvoice && scheme.status === "Active";
      const coverage = report.report_date !== this.asOn
        ? __("Through {0}", [date(report.report_date)]) : "";
      this.detail.html(`
        ${this.embedded ? `<div class="sw-overview">
          <div class="sw-compact-meta">
            <span class="sw-status sw-${scheme.status.toLowerCase()}">${esc(__(scheme.status))}</span>
            <span>${date(scheme.valid_from)} – ${date(scheme.valid_upto)}</span>
            ${scheme.scheme_series ? `<span>${esc(scheme.scheme_series)}</span>` : ""}
            ${scheme.track_invoice_items ? "" : `<span>${esc(coverage || __("Historical calculation"))}</span>`}
            <button data-action="configure">${__("Open setup")}</button>
          </div>
          ${customers.length ? `<div class="sw-stats">
            ${stat(perInvoice ? __("Invoices") : __("Customers"), customers.length)}
            ${stat(__("Eligible invoiced"), this.money(sum("eligible_amount")))}
            ${paymentRules ? stat(__("Eligible cleared"), this.money(sum("eligible_cleared"))) : stat(__("Qualified"), qualificationCount)}
            ${projection && showQuoteOption ? stat(__("Open quotations"), this.money(sum("quotation_amount"))) : ""}
          </div>` : ""}
        </div>` : `
        <div class="sw-overview">
          <div class="sw-heading"><div>
            <div class="sw-meta"><span class="sw-status sw-${scheme.status.toLowerCase()}">${esc(__(scheme.status))}</span>
            <span>${esc(scheme.scheme_type)}</span></div>
            <h2>${esc(scheme.name)}</h2>
            <p>${date(scheme.valid_from)} – ${date(scheme.valid_upto)}${scheme.scheme_series ? ` · ${esc(scheme.scheme_series)}` : ""}</p>
          </div><button data-action="configure">${__("Open setup")}</button></div>
          <p class="sw-source">${scheme.track_invoice_items ? __("Source: submitted invoice lines") : __("Source: historical rule-based calculation")}
          ${report.report_date !== this.asOn ? ` · ${__("Calculated through {0}", [date(report.report_date)])}` : ""}</p>
          <div class="sw-stats">
            ${stat(perInvoice ? __("Invoices") : __("Customers"), customers.length)}
            ${stat(__("Eligible invoiced"), this.money(sum("eligible_amount")))}
            ${stat(perInvoice ? __("Invoices qualified") : __("Customers qualified"), qualificationCount)}
            ${projection && showQuoteOption ? stat(__("Open quotation value"), this.money(sum("quotation_amount"))) : ""}
          </div>
        </div>`}
        <div class="sw-tabs" aria-label="${esc(__("Scheme views"))}">
          ${[["progress", perInvoice ? __("Invoice progress") : __("Customer progress")],
            ["terms", __("Scheme rules")], ...(paymentRules ? [["reminders", __("Reminder previews")]] : [])].map(([value, text]) =>
              `<button data-action="tab" data-value="${value}" aria-pressed="${this.tab === value}">${esc(text)}</button>`
          ).join("")}
        </div>
        <div class="sw-content"></div>`);
      this.content = this.detail.find(".sw-content");
      if (this.tab === "terms") return this.renderTerms(scheme);
      if (this.tab === "reminders") return this.renderReminderPreviews();
      this.content.html(`<div class="sw-content-tools">
        ${!this.embedded || customers.length ? `<label>${esc(perInvoice ? __("Find invoice or customer") : __("Find customer"))}
          <input type="search" data-field="customerSearch" value="${esc(this.customerSearch)}"></label>` : ""}
        ${showQuoteOption ? `<label>${__("Quotation projection")}
          <select data-field="quotations">
            <option value="0">${__("Invoices only")}</option>
            <option value="1">${__("Include submitted quotations")}</option>
            <option value="2">${__("Include draft and submitted quotations")}</option>
          </select></label>` : ""}
      </div><div class="sw-results"></div>`);
      this.content.find("[data-field=quotations]").val(this.quotations);
      this.renderRows();
    }

    table(headers, rows) {
      return `<div class="sw-table" tabindex="0"><table><thead><tr>${headers.map(value => `<th scope="col">${esc(value)}</th>`).join("")}</tr></thead>
        <tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }

    renderRows() {
      const term = (this.customerSearch || "").trim().toLowerCase();
      const projection = this.quotations !== "0" && this.register.find(row => row.name === this.selected)?.status === "Active"
        && !this.report.per_invoice;
      const payments = Boolean(this.report.payment_rules);
      const rows = this.report.customers.map((row, index) => [row, index]).filter(([row]) =>
        [row.customer, row.customer_name, row.invoice].some(value => String(value || "").toLowerCase().includes(term)));
      this.content.find(".sw-results").html(rows.length ? this.table([
        this.report.per_invoice ? __("Invoice / customer") : __("Customer"),
        __("Eligible invoiced"), payments ? __("Invoiced reward") : __("Reward reached"),
        ...(payments ? [__("Eligible cleared"), __("Claimable reward"), __("Clearance gap")] : [__("Next target gap")]),
        ...(projection ? [__("Projected total"), __("Projected reward")] : []),
      ], rows.map(([row, index]) => [
        `<button class="sw-link" data-action="customer" data-value="${index}">${esc(row.invoice || row.customer_name || row.customer)}</button>
        <small>${esc(row.invoice ? row.customer_name || row.customer : row.customer !== row.customer_name ? row.customer : "")}</small>`,
        this.money(row.eligible_amount),
        esc(row.achieved_rewards?.join(", ") || __("None yet")),
        ...(payments ? [this.money(row.eligible_cleared), esc(row.claimable_rewards?.join(", ") || __("None yet")),
          this.clearanceGap(row)] : [row.next_slab ? `${this.money(row.shortfall_amount)}${this.gaps(row.category_shortfalls, row.next_slab)}` : "—"]),
        ...(projection ? [this.money(row.projected_amount), esc(row.projected_rewards?.join(", ") || __("None yet"))] : []),
      ])) : this.message(term ? __("No matching results") : __("No eligible transactions through this date"),
        term || this.embedded ? "" : __("Customer progress appears after eligible invoices are submitted.")));
    }

    clearanceGap(row, currency) {
      return row.clearance_next_slab
        ? this.money(row.clearance_gap, currency) + this.gaps(row.clearance_category_shortfalls, row.clearance_next_slab, currency)
        : "—";
    }

    gaps(gaps, slab, currency) {
      const needed = number(slab?.minimum_categories_required) - number(slab?.qualified_categories);
      const entries = Object.entries(gaps || {}).filter(([, gap]) => number(gap) > 0);
      return needed > 0 && entries.length ? `<small>${esc(__("{0} more category targets", [needed]))}<br>
        ${entries.map(([key, value]) => `${esc(key)} ${this.money(value, currency)}`).join(" · ")}</small>` : "";
    }

    async openCustomer(person = this.report.customers[this.customer]) {
      this.detail.find(".sw-customer-panel").remove();
      this.detail.addClass("sw-has-customer");
      const panel = $(`<section class="sw-customer-panel" aria-label="${esc(__("Customer transaction detail"))}">
        <div class="sw-panel-heading"><h3>${esc(person.invoice || person.customer_name || person.customer)}</h3>
          <button data-action="close-customer">${__("Close")}</button></div>
        <p>${__("Eligible invoiced")} <strong>${this.money(person.eligible_amount, person.currency)}</strong></p>
        <div class="sw-panel-lines"></div><div class="sw-panel-exclusions"></div>
      </section>`).appendTo(this.content);
      panel.find("[data-action=close-customer]").trigger("focus");
      const lines = panel.find(".sw-panel-lines");
      const target = panel.find(".sw-panel-exclusions");
      lines.html(this.message(__("Loading invoice details…")));
      try {
        const { message } = await frappe.call({ method: `${api}.get_customer_detail`, args: this.customerArgs(person) });
        if (!panel[0].isConnected) return;
        this.renderLines(lines, message.customer, message.currency);
        if (message.payment_rules) this.renderPayments(lines, message.customer, message.currency);
        if (!this.register.find(row => row.name === (person.scheme || this.selected))?.track_invoice_items) return;
        target.html(`<h4>${__("Excluded invoice lines")}</h4>${message.exclusions.length ? `<ul>${message.exclusions.map(row =>
          `<li><strong>${esc(row.item_code)}</strong><small>${esc(row.parent)} · ${__("Line {0}", [row.idx])}</small>
          <span>${esc(row.reasons.join(" · "))}</span></li>`).join("")}</ul>`
          : `<p>${__("No recorded exclusions for this scheme.")}</p>`}`);
      } catch {
        lines.html(this.message(__("Could not load customer transactions")));
      }
    }

    renderPayments(target, person, currency) {
      target.prepend(`<div class="sw-payment-detail">
        <h4>${__("Payment clearance")}</h4>
        <p>${__("Eligible cleared")} <strong>${this.money(person.eligible_cleared, currency)}</strong>
          · ${esc(person.claimable_rewards.join(", ") || __("No claimable reward yet"))}</p>
        <ul>${(person.payment_invoices || []).map(row => `<li>
          <strong>${esc(row.invoice)} · ${esc(__(row.status))}</strong>
          <small>${__("Soft")} ${date(row.soft_deadline)} · ${__("Hard")} ${date(row.hard_deadline)}</small>
          ${row.clearance_date ? `<small>${__("Cleared on")} ${date(row.clearance_date)}</small>` : ""}
          ${row.outstanding != null && row.outstanding > 0 ? `<small>${__("Outstanding")} ${this.money(row.outstanding, row.currency)}</small>` : ""}
        </li>`).join("")}</ul>
      </div>`);
    }

    renderLines(target, person, currency) {
      const rows = [...(person.eligible_rows || []), ...(person.quotation_rows || [])];
      this.documents = rows.map(row => row.quotation || row.sales_invoice);
      target.html(`<div class="sw-line-tools">
        <strong>${__("Eligible transactions")}</strong>
        <div><button data-action="download" data-value="pdf">${__("PDF")}</button>
          <button data-action="download" data-value="xlsx">${__("Excel")}</button></div>
      </div>${rows.length ? `<ul class="sw-panel-list">${rows.map((row, index) =>
        `<li><strong>${esc(row.item_code)} · ${this.money(row.amount, currency)}</strong>
          <small>${esc(row.item_name)}${row.category ? ` · ${esc(row.category)}` : ""}</small>
          <button class="sw-link" data-action="document" data-value="${row.quotation ? "Quotation" : "Sales Invoice"}" data-index="${index}">${esc(this.documents[index])}</button>
          <small>${date(row.posting_date || row.transaction_date)}${row.invoice_line ? ` · ${__("Line {0}", [row.invoice_line])}` : ""}</small>
          ${row.exception_reason ? `<span>${esc(row.exception_reason)} · ${esc(row.exception_by)}</span>` : ""}</li>`).join("")}</ul>`
        : this.message(__("No transaction lines"))}`);
    }

    renderTerms(scheme) {
      const { gst, reward_policy: policy, slabs, items, groups, exclusions, category_rules: categories } = this.report;
      const pill = value => `<span class="sw-tag">${esc(value)}</span>`;
      this.content.html(`
        <div class="sw-terms">
          ${this.report.payment_rules ? `<div><h3>${__("Payment qualification")}</h3>
            <p>${pill(__("{0} days from invoice", [this.report.payment_rules.soft_days]))}
              ${pill(__("Final clearance: {0}", [date(this.report.payment_rules.hard_deadline)]))}
              ${pill(__("Reminders: {0}", [this.report.payment_rules.reminder_days.join(", ")]))}</p>
          </div>` : ""}
          <div><h3>${__("Reward rules")}</h3><p>${pill(__("GST {0}", [gst.toLowerCase()]))} ${pill(policy)}</p>
            ${this.table([__("Spend target"), __("Reward"), __("Category targets")], slabs.map(slab => [
              this.money(slab.amount), esc(slab.reward),
              slab.targets ? `${esc(__("At least {0} categories", [slab.minimum_categories_required]))}
                <small>${Object.entries(slab.targets).map(([key, value]) => `${esc(key)} ${this.money(value)}`).join(" · ")}</small>` : "—",
            ]))}
          </div>
          <div><h3>${__("Eligibility")}</h3>
            ${items.length ? `<p><strong>${__("Items")}</strong><br>${items.map(row => pill([row.item_code, row.uom].filter(Boolean).join(" · "))).join(" ")}</p>` : ""}
            ${groups.length ? `<p><strong>${__("Item groups")}</strong><br>${groups.map(row => pill([row.item_group,
              Number(row.include_descendants ?? 1) ? __("Includes subgroups") : "", row.uom].filter(Boolean).join(" · "))).join(" ")}</p>` : ""}
            ${categories.length ? this.table([__("Category"), __("Rule"), __("Scope")], categories.map(row => [
              esc(row.category), esc(row.item_code || row.item_group),
              esc([row.exclude ? __("Exclude") : __("Include"), row.uom,
                row.item_group && Number(row.include_descendants ?? 1) ? __("Includes subgroups") : ""].filter(Boolean).join(" · ")),
            ])) : ""}
            ${exclusions.length ? `<p><strong>${__("Excluded items")}</strong><br>${exclusions.map(pill).join(" ")}</p>` : ""}
            ${!items.length && !groups.length && !categories.length ? `<p>${__("No eligible item rules configured.")}</p>` : ""}
          </div>
          <div><h3>${__("Scheme succession")}</h3>
            <p>${esc(scheme.scheme_series || __("Independent scheme"))}</p>
            ${scheme.supersedes ? `<p>${esc(__("Supersedes {0}", [scheme.supersedes]))}</p>` : ""}
            <button data-action="series">${__("Manage scheme series")}</button>
          </div>
        </div>`);
    }
  }
})();
