frappe.pages["uom-conversion-manager"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "UOM Conversion Manager",
    single_column: true,
  });

  wrapper.uom_conversion_manager = new SnrgUomConversionManager(page, wrapper);
};

class SnrgUomConversionManager {
  constructor(page, wrapper) {
    this.page = page;
    this.wrapper = $(wrapper);
    this.controls = {};
    this.rows = [];
    this.total = 0;
    this.limitStart = 0;
    this.pageLength = 50;
    this.sortBy = "item_code";
    this.sortOrder = "asc";
    this.targetUoms = ["Nos", "Box", "Carton"];
    this.pendingChanges = new Map();
    this.setup();
  }

  setup() {
    this.page.set_primary_action("Save Changes", () => this.saveChanges(), "check");
    this.page.set_secondary_action("Refresh", () => this.refresh(), "refresh");
    this.renderShell();
    this.makeFilters();
    this.bindEvents();
    this.applyRouteOptions();
  }

  renderShell() {
    this.wrapper.find(".layout-main-section").html(`
      <style>
        .snrg-uom-page { display:flex; flex-direction:column; gap:14px; color:#172033; }
        .snrg-uom-filter-shell { position:sticky; top:0; z-index:5; display:flex; flex-direction:column; gap:12px; padding:0 0 10px; background:#fff; }
        .snrg-uom-toolbar { display:grid; grid-template-columns:minmax(180px, 1fr) minmax(180px, 1fr) minmax(220px, 1.25fr) minmax(140px, 180px); gap:12px; align-items:end; }
        .snrg-uom-command-row { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
        .snrg-uom-actions { display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
        .snrg-uom-button { border:1px solid #d9e1ec; border-radius:6px; padding:8px 11px; background:#fff; color:#1f3a5f; font-size:12px; font-weight:700; cursor:pointer; }
        .snrg-uom-button.primary { background:#1f6feb; border-color:#1f6feb; color:#fff; }
        .snrg-uom-button:disabled { opacity:.55; cursor:not-allowed; }
        .snrg-uom-panel { border:1px solid #e1e7ef; border-radius:8px; background:#fff; overflow:hidden; }
        .snrg-uom-panel-head { display:flex; justify-content:space-between; align-items:center; gap:12px; padding:12px 14px; border-bottom:1px solid #e1e7ef; background:#f8fafc; }
        .snrg-uom-panel-title { font-size:14px; font-weight:800; color:#101828; }
        .snrg-uom-panel-subtitle { font-size:12px; color:#667085; margin-top:2px; }
        .snrg-uom-table-wrap { overflow:auto; }
        .snrg-uom-table { width:100%; border-collapse:collapse; min-width:1080px; }
        .snrg-uom-table th, .snrg-uom-table td { padding:10px 12px; border-bottom:1px solid #edf1f7; vertical-align:top; font-size:13px; }
        .snrg-uom-table th { background:#fbfcfe; color:#475467; font-weight:800; text-align:left; white-space:nowrap; }
        .snrg-uom-table tr:hover td { background:#f9fbff; }
        .snrg-uom-sort { border:0; padding:0; background:transparent; color:#475467; font-weight:800; cursor:pointer; }
        .snrg-uom-sort.active { color:#1849a9; }
        .snrg-uom-item-code { font-weight:800; color:#1849a9; cursor:pointer; }
        .snrg-uom-item-name { color:#101828; margin-top:2px; }
        .snrg-uom-muted { color:#667085; font-size:12px; }
        .snrg-uom-disabled { display:inline-flex; align-items:center; border:1px solid #f3c3bd; color:#b42318; background:#fff1f0; border-radius:999px; padding:3px 7px; font-size:11px; font-weight:800; margin-top:6px; }
        .snrg-uom-factor { width:100%; border:1px solid #d9e1ec; border-radius:6px; padding:7px 8px; text-align:right; background:#fff; }
        .snrg-uom-factor::-webkit-outer-spin-button, .snrg-uom-factor::-webkit-inner-spin-button { -webkit-appearance:none; margin:0; }
        .snrg-uom-factor[type=number] { -moz-appearance:textfield; appearance:textfield; }
        .snrg-uom-factor.changed { border-color:#1f6feb; background:#eff6ff; }
        .snrg-uom-factor.missing { background:#fff; }
        .snrg-uom-empty { padding:28px 16px; text-align:center; color:#667085; font-size:13px; }
        .snrg-uom-footer { display:flex; justify-content:space-between; align-items:center; padding:10px 14px; gap:10px; border-top:1px solid #edf1f7; }
        @media (max-width: 900px) {
          .snrg-uom-toolbar { grid-template-columns:1fr; }
          .snrg-uom-actions { justify-content:flex-start; }
        }
      </style>
      <div class="snrg-uom-page">
        <section class="snrg-uom-filter-shell">
          <div class="snrg-uom-toolbar">
            <div class="snrg-uom-item-group-filter"></div>
            <div class="snrg-uom-item-code-filter"></div>
            <div class="snrg-uom-item-name-filter"></div>
            <div class="snrg-uom-page-length-filter"></div>
          </div>
          <div class="snrg-uom-command-row">
            <div class="snrg-uom-muted" data-role="dirty-summary">No unsaved changes.</div>
            <div class="snrg-uom-actions">
              <button class="snrg-uom-button" data-action="clear-filters">Clear Filters</button>
              <button class="snrg-uom-button primary" data-action="save">Save Changes</button>
            </div>
          </div>
        </section>
        <section class="snrg-uom-panel">
          <div class="snrg-uom-panel-head">
            <div>
              <div class="snrg-uom-panel-title">Items</div>
              <div class="snrg-uom-panel-subtitle" data-role="table-summary">Loading items...</div>
            </div>
          </div>
          <div class="snrg-uom-table-wrap">
            <table class="snrg-uom-table">
              <thead>
                <tr>
                  <th style="width:240px;"><button class="snrg-uom-sort" data-sort="item_code">Item Code</button></th>
                  <th><button class="snrg-uom-sort" data-sort="item_name">Item Name</button></th>
                  <th style="width:180px;"><button class="snrg-uom-sort" data-sort="item_group">Item Group</button></th>
                  <th style="width:120px;"><button class="snrg-uom-sort" data-sort="stock_uom">Stock UOM</button></th>
                  <th style="width:130px;">Nos</th>
                  <th style="width:130px;">Box</th>
                  <th style="width:130px;">Carton</th>
                </tr>
              </thead>
              <tbody class="snrg-uom-body"></tbody>
            </table>
          </div>
          <div class="snrg-uom-footer">
            <div class="snrg-uom-muted" data-role="range"></div>
            <div class="snrg-uom-actions">
              <button class="snrg-uom-button" data-action="prev">Previous</button>
              <button class="snrg-uom-button" data-action="next">Next</button>
            </div>
          </div>
        </section>
      </div>
    `);
  }

  makeFilters() {
    this.controls.itemGroup = frappe.ui.form.make_control({
      parent: this.wrapper.find(".snrg-uom-item-group-filter"),
      df: {
        fieldtype: "Link",
        fieldname: "item_group",
        label: "Item Group",
        options: "Item Group",
        change: () => this.resetAndRefresh(),
      },
      render_input: true,
    });

    this.controls.itemCode = frappe.ui.form.make_control({
      parent: this.wrapper.find(".snrg-uom-item-code-filter"),
      df: {
        fieldtype: "Link",
        fieldname: "item_code",
        label: "Item Code",
        options: "Item",
        change: () => this.resetAndRefresh(),
      },
      render_input: true,
    });

    this.controls.itemName = frappe.ui.form.make_control({
      parent: this.wrapper.find(".snrg-uom-item-name-filter"),
      df: {
        fieldtype: "Data",
        fieldname: "item_name",
        label: "Item Name",
        placeholder: "Type part of item name",
        change: () => this.resetAndRefresh(),
      },
      render_input: true,
    });

    this.controls.pageLength = frappe.ui.form.make_control({
      parent: this.wrapper.find(".snrg-uom-page-length-filter"),
      df: {
        fieldtype: "Select",
        fieldname: "page_length",
        label: "Rows",
        options: "25\n50\n100\n200",
        default: "50",
        change: () => {
          this.pageLength = this.toInt(this.controls.pageLength.get_value()) || 50;
          this.resetAndRefresh();
        },
      },
      render_input: true,
    });
    this.controls.pageLength.set_value("50");
  }

  bindEvents() {
    this.wrapper.on("click", "[data-action='save']", () => this.saveChanges());
    this.wrapper.on("click", "[data-action='clear-filters']", () => this.clearFilters());
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
    this.wrapper.on("click", "[data-sort]", (event) => this.setSort($(event.currentTarget).data("sort")));
    this.wrapper.on("click", "[data-role='open-item']", (event) => {
      frappe.set_route("Form", "Item", $(event.currentTarget).data("item"));
    });
    this.wrapper.on("change", "[data-role='factor-input']", (event) => this.trackFactorChange(event.currentTarget));
  }

  applyRouteOptions() {
    if (frappe.route_options) {
      if (frappe.route_options.item_group) this.controls.itemGroup.set_value(frappe.route_options.item_group);
      if (frappe.route_options.item_code) this.controls.itemCode.set_value(frappe.route_options.item_code);
      if (frappe.route_options.item_name) this.controls.itemName.set_value(frappe.route_options.item_name);
      frappe.route_options = null;
    }
    this.refresh();
  }

  getFilterArgs() {
    return {
      item_group: this.controls.itemGroup.get_value(),
      item_code: this.controls.itemCode.get_value(),
      item_name: this.controls.itemName.get_value(),
      sort_by: this.sortBy,
      sort_order: this.sortOrder,
      limit_start: this.limitStart,
      limit_page_length: this.pageLength,
    };
  }

  resetAndRefresh() {
    this.limitStart = 0;
    this.refresh();
  }

  clearFilters() {
    this.controls.itemGroup.set_value("");
    this.controls.itemCode.set_value("");
    this.controls.itemName.set_value("");
    this.resetAndRefresh();
  }

  setSort(sortBy) {
    if (this.sortBy === sortBy) {
      this.sortOrder = this.sortOrder === "asc" ? "desc" : "asc";
    } else {
      this.sortBy = sortBy;
      this.sortOrder = "asc";
    }
    this.resetAndRefresh();
  }

  refresh() {
    frappe.call({
      method: "snrg_credit_control.uom_conversion_manager.get_items",
      args: this.getFilterArgs(),
      freeze: true,
      freeze_message: "Loading item UOM conversion factors...",
      callback: (r) => {
        const message = r.message || {};
        this.rows = message.rows || [];
        this.total = message.total || 0;
        this.render();
      },
    });
  }

  render() {
    this.renderSortState();
    const body = this.wrapper.find(".snrg-uom-body");
    if (!this.rows.length) {
      body.html(`<tr><td colspan="7"><div class="snrg-uom-empty">No items found for the selected filters.</div></td></tr>`);
      this.updateSummary();
      this.updatePagination();
      return;
    }

    body.html(this.rows.map((row) => this.renderRow(row)).join(""));
    this.pendingChanges.forEach((change, key) => {
      const input = this.wrapper.find(`[data-change-key='${this.escapeAttr(key)}']`);
      input.val(change.conversion_factor);
      input.addClass("changed");
    });
    this.updateSummary();
    this.updatePagination();
  }

  renderRow(row) {
    return `
      <tr>
        <td>
          <div class="snrg-uom-item-code" data-role="open-item" data-item="${this.escapeAttr(row.item_code)}">${this.escape(row.item_code)}</div>
          ${row.disabled ? `<div class="snrg-uom-disabled">Disabled</div>` : ""}
        </td>
        <td><div class="snrg-uom-item-name">${this.escape(row.item_name || "")}</div></td>
        <td>${this.escape(row.item_group || "")}</td>
        <td>${this.escape(row.stock_uom || "")}</td>
        ${this.targetUoms.map((uom) => `<td>${this.renderUomInput(row, uom)}</td>`).join("")}
      </tr>
    `;
  }

  renderUomInput(row, uom) {
    const value = this.getUomFactor(row, uom);
    const key = this.getChangeKey(row.item_code, uom);
    return `
      <input
        class="snrg-uom-factor ${value === "" ? "missing" : ""}"
        data-role="factor-input"
        data-change-key="${this.escapeAttr(key)}"
        data-item="${this.escapeAttr(row.item_code)}"
        data-uom="${this.escapeAttr(uom)}"
        data-original="${this.escapeAttr(String(value))}"
        type="number"
        step="any"
        min="0"
        placeholder="Add"
        value="${this.escapeAttr(String(value))}"
      >
    `;
  }

  getUomFactor(row, uom) {
    const matchingRow = (row.uoms || []).find((uomRow) => uomRow.uom === uom);
    if (matchingRow) {
      return matchingRow.conversion_factor;
    }
    return row.stock_uom === uom ? 1 : "";
  }

  renderSortState() {
    this.wrapper.find("[data-sort]").removeClass("active").each((index, button) => {
      const label = $(button).text().replace(/\s\((ASC|DESC)\)$/, "");
      $(button).text(label);
    });
    const active = this.wrapper.find(`[data-sort='${this.sortBy}']`);
    active.addClass("active");
    active.text(`${active.text()} (${this.sortOrder.toUpperCase()})`);
  }

  trackFactorChange(input) {
    const itemCode = $(input).data("item");
    const uom = $(input).data("uom");
    const originalRaw = String($(input).attr("data-original") || "");
    const currentRaw = String($(input).val() || "").trim();
    const original = this.toFloat(originalRaw);
    const conversionFactor = this.toFloat(currentRaw);
    const key = this.getChangeKey(itemCode, uom);

    if (!currentRaw) {
      this.pendingChanges.delete(key);
      $(input).val(originalRaw);
      $(input).removeClass("changed");
      this.updateDirtySummary();
      return;
    }

    if (conversionFactor <= 0) {
      frappe.msgprint("Conversion Factor must be greater than zero.");
      $(input).val(originalRaw);
      $(input).removeClass("changed");
      this.pendingChanges.delete(key);
      this.updateDirtySummary();
      return;
    }

    if (originalRaw && conversionFactor === original) {
      this.pendingChanges.delete(key);
      $(input).removeClass("changed");
    } else {
      this.pendingChanges.set(key, { item_code: itemCode, uom, conversion_factor: conversionFactor });
      $(input).addClass("changed");
    }
    this.updateDirtySummary();
  }

  saveChanges() {
    const changes = Array.from(this.pendingChanges.values());
    if (!changes.length) {
      frappe.show_alert({ message: "No unsaved UOM changes.", indicator: "blue" });
      return;
    }

    frappe.call({
      method: "snrg_credit_control.uom_conversion_manager.save_conversion_factors",
      args: { changes },
      freeze: true,
      freeze_message: "Saving UOM conversion factors...",
      callback: (r) => {
        const result = r.message || {};
        const updated = result.updated || [];
        const failed = result.failed || [];

        if (failed.length) {
          frappe.msgprint({
            title: "Some UOM changes were not saved",
            indicator: "orange",
            message: failed.map((row) => `${this.escape(row.item_code)}: ${this.escape(row.reason)}`).join("<br>"),
          });
        }

        frappe.show_alert({
          message: `UOM changes saved for ${updated.length} item(s). ${failed.length} failed.`,
          indicator: failed.length ? "orange" : "green",
        });

        if (failed.length) {
          const failedItems = new Set(failed.map((row) => row.item_code));
          this.pendingChanges.forEach((change, key) => {
            if (!failedItems.has(change.item_code)) {
              this.pendingChanges.delete(key);
            }
          });
        } else {
          this.pendingChanges.clear();
        }
        this.updateDirtySummary();
        this.refresh();
      },
    });
  }

  updateSummary() {
    this.wrapper.find("[data-role='table-summary']").text(`${this.total} item(s) found. Sorted by ${this.sortBy.replace("_", " ")} ${this.sortOrder}.`);
    this.updateDirtySummary();
  }

  updateDirtySummary() {
    const count = this.pendingChanges.size;
    this.wrapper.find("[data-role='dirty-summary']").text(count ? `${count} unsaved UOM change(s).` : "No unsaved changes.");
    this.wrapper.find("[data-action='save']").prop("disabled", !count);
  }

  updatePagination() {
    const from = this.total ? this.limitStart + 1 : 0;
    const to = Math.min(this.limitStart + this.pageLength, this.total);
    this.wrapper.find("[data-role='range']").text(`${from}-${to} of ${this.total}`);
    this.wrapper.find("[data-action='prev']").prop("disabled", this.limitStart <= 0);
    this.wrapper.find("[data-action='next']").prop("disabled", this.limitStart + this.pageLength >= this.total);
  }

  getChangeKey(itemCode, uom) {
    return `${encodeURIComponent(itemCode)}::${encodeURIComponent(uom)}`;
  }

  escape(value) {
    return frappe.utils.escape_html(value == null ? "" : String(value));
  }

  escapeAttr(value) {
    return this.escape(value).replace(/"/g, "&quot;");
  }

  toInt(value) {
    const parsed = parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  toFloat(value) {
    const parsed = parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
}
