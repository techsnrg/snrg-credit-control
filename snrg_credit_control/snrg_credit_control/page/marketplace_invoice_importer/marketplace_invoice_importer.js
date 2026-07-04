frappe.pages["marketplace-invoice-importer"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Marketplace Invoice Importer",
    single_column: true,
  });

  wrapper.marketplace_invoice_importer = new SnrgMarketplaceInvoiceImporter(page, wrapper);
};

class SnrgMarketplaceInvoiceImporter {
  constructor(page, wrapper) {
    this.page = page;
    this.wrapper = $(wrapper);
    this.preview = null;
    this.activeTab = "invoices";
    this.setup();
  }

  setup() {
    this.page.set_primary_action("Upload File", () => this.uploadFile(), "upload");
    this.page.set_secondary_action("Clear", () => this.clear(), "refresh");
    this.renderShell();
    this.bindEvents();
    this.renderEmptyState();
  }

  renderShell() {
    this.wrapper.find(".layout-main-section").html(`
      <style>
        .snrg-mii-page { display:flex; flex-direction:column; gap:14px; color:#172033; }
        .snrg-mii-panel { border:1px solid #e1e7ef; border-radius:8px; background:#fff; overflow:hidden; }
        .snrg-mii-head { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:14px 16px; border-bottom:1px solid #e1e7ef; background:#f8fafc; }
        .snrg-mii-title { font-size:15px; font-weight:800; color:#101828; }
        .snrg-mii-subtitle { margin-top:3px; color:#667085; font-size:12px; }
        .snrg-mii-actions { display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
        .snrg-mii-button { border:1px solid #d9e1ec; border-radius:6px; padding:8px 11px; background:#fff; color:#1f3a5f; font-size:12px; font-weight:800; cursor:pointer; }
        .snrg-mii-button.primary { background:#1f6feb; border-color:#1f6feb; color:#fff; }
        .snrg-mii-button:disabled { opacity:.55; cursor:not-allowed; }
        .snrg-mii-summary { display:grid; grid-template-columns:repeat(4, minmax(140px, 1fr)); gap:10px; padding:14px 16px; }
        .snrg-mii-metric { border:1px solid #e1e7ef; border-radius:8px; padding:11px 12px; background:#fff; min-height:76px; }
        .snrg-mii-metric-label { color:#667085; font-size:12px; font-weight:700; }
        .snrg-mii-metric-value { color:#101828; font-size:21px; line-height:1.25; font-weight:850; margin-top:7px; }
        .snrg-mii-metric-note { color:#667085; font-size:12px; margin-top:3px; }
        .snrg-mii-warnings { display:flex; flex-direction:column; gap:7px; padding:0 16px 14px; }
        .snrg-mii-warning { border:1px solid #fedf89; background:#fffaeb; color:#93370d; border-radius:7px; padding:8px 10px; font-size:12px; font-weight:700; }
        .snrg-mii-tabs { display:flex; gap:0; border-bottom:1px solid #e1e7ef; padding:0 16px; background:#fff; overflow:auto; }
        .snrg-mii-tab { border:0; border-bottom:3px solid transparent; background:transparent; color:#667085; padding:12px 11px 9px; font-size:12px; font-weight:850; cursor:pointer; white-space:nowrap; }
        .snrg-mii-tab.active { color:#1849a9; border-bottom-color:#1f6feb; }
        .snrg-mii-table-wrap { overflow:auto; }
        .snrg-mii-table { width:100%; min-width:1120px; border-collapse:collapse; }
        .snrg-mii-table th, .snrg-mii-table td { padding:10px 12px; border-bottom:1px solid #edf1f7; vertical-align:top; font-size:13px; }
        .snrg-mii-table th { background:#fbfcfe; color:#475467; font-weight:850; text-align:left; white-space:nowrap; }
        .snrg-mii-table tr:hover td { background:#f9fbff; }
        .snrg-mii-key { color:#1849a9; font-weight:850; }
        .snrg-mii-muted { color:#667085; font-size:12px; }
        .snrg-mii-pill { display:inline-flex; align-items:center; border:1px solid #d9e1ec; border-radius:999px; padding:3px 8px; font-size:11px; font-weight:850; color:#475467; background:#fff; }
        .snrg-mii-pill.b2b { color:#075985; background:#eff6ff; border-color:#bfdbfe; }
        .snrg-mii-pill.b2c { color:#047857; background:#ecfdf3; border-color:#abefc6; }
        .snrg-mii-pill.rtv { color:#93370d; background:#fffaeb; border-color:#fedf89; }
        .snrg-mii-pill.cancelled { color:#b42318; background:#fff1f0; border-color:#f3c3bd; }
        .snrg-mii-empty { padding:34px 18px; color:#667085; text-align:center; font-size:13px; }
        .snrg-mii-file { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
        .snrg-mii-file-name { color:#1849a9; font-weight:800; }
        @media (max-width: 980px) {
          .snrg-mii-summary { grid-template-columns:repeat(2, minmax(140px, 1fr)); }
          .snrg-mii-head { align-items:flex-start; flex-direction:column; }
          .snrg-mii-actions { justify-content:flex-start; }
        }
        @media (max-width: 640px) {
          .snrg-mii-summary { grid-template-columns:1fr; }
        }
      </style>
      <div class="snrg-mii-page">
        <section class="snrg-mii-panel">
          <div class="snrg-mii-head">
            <div>
              <div class="snrg-mii-title">Marketplace File Preview</div>
              <div class="snrg-mii-subtitle" data-role="file-summary">Upload a Moglix CSV or XLSX finance report to preview ERPNext invoice groups.</div>
            </div>
            <div class="snrg-mii-actions">
              <button class="snrg-mii-button" data-action="clear">Clear</button>
              <button class="snrg-mii-button primary" data-action="upload">Upload File</button>
            </div>
          </div>
          <div class="snrg-mii-summary" data-role="summary"></div>
          <div class="snrg-mii-warnings" data-role="warnings"></div>
        </section>
        <section class="snrg-mii-panel">
          <div class="snrg-mii-tabs">
            <button class="snrg-mii-tab active" data-tab="invoices">Invoice Groups</button>
            <button class="snrg-mii-tab" data-tab="rtv">RTV</button>
            <button class="snrg-mii-tab" data-tab="adjustments">Adjustments</button>
            <button class="snrg-mii-tab" data-tab="cancelled">Cancelled</button>
          </div>
          <div class="snrg-mii-table-wrap" data-role="table"></div>
        </section>
      </div>
    `);
  }

  bindEvents() {
    this.wrapper.on("click", "[data-action='upload']", () => this.uploadFile());
    this.wrapper.on("click", "[data-action='clear']", () => this.clear());
    this.wrapper.on("click", "[data-tab]", (event) => {
      this.activeTab = $(event.currentTarget).data("tab");
      this.renderTabs();
      this.renderTable();
    });
  }

  uploadFile() {
    new frappe.ui.FileUploader({
      restrictions: {
        allowed_file_types: [".csv", ".xlsx"],
      },
      on_success: (file) => {
        const fileUrl = file.file_url || file.file_url_private;
        if (!fileUrl) {
          frappe.msgprint("The upload succeeded, but ERPNext did not return a file URL.");
          return;
        }
        this.previewFile(fileUrl);
      },
    });
  }

  previewFile(fileUrl) {
    frappe.call({
      method: "snrg_credit_control.marketplace_invoice_importer.preview_file",
      args: { file_url: fileUrl },
      freeze: true,
      freeze_message: "Reading marketplace file...",
      callback: (response) => {
        this.preview = response.message;
        this.activeTab = "invoices";
        this.render();
      },
    });
  }

  clear() {
    this.preview = null;
    this.activeTab = "invoices";
    this.renderEmptyState();
  }

  render() {
    this.renderFileSummary();
    this.renderSummary();
    this.renderWarnings();
    this.renderTabs();
    this.renderTable();
  }

  renderEmptyState() {
    this.wrapper.find("[data-role='file-summary']").html("Upload a Moglix CSV or XLSX finance report to preview ERPNext invoice groups.");
    this.wrapper.find("[data-role='summary']").html(`
      ${this.metric("Invoice Groups", "-", "Waiting for file")}
      ${this.metric("B2B Invoices", "-", "Moglix B2B")}
      ${this.metric("B2C Invoices", "-", "Moglix B2C")}
      ${this.metric("RTV Rows", "-", "Tracked separately")}
    `);
    this.wrapper.find("[data-role='warnings']").empty();
    this.renderTabs();
    this.wrapper.find("[data-role='table']").html(`<div class="snrg-mii-empty">No file preview loaded.</div>`);
  }

  renderFileSummary() {
    const fileUrl = this.preview?.file_url || "";
    const fileName = fileUrl.split("/").pop() || fileUrl;
    this.wrapper.find("[data-role='file-summary']").html(`
      <div class="snrg-mii-file">
        <span>${this.esc(this.preview.marketplace)} file loaded:</span>
        <span class="snrg-mii-file-name">${this.esc(fileName)}</span>
      </div>
    `);
  }

  renderSummary() {
    const summary = this.preview.summary || {};
    this.wrapper.find("[data-role='summary']").html(`
      ${this.metric("Invoice Groups", summary.invoice_groups, `${summary.invoiceable_rows || 0} invoiceable rows`)}
      ${this.metric("B2B Invoices", summary.b2b_invoices, "Customer: Moglix B2B")}
      ${this.metric("B2C Invoices", summary.b2c_invoices, "Customer: Moglix B2C")}
      ${this.metric("RTV Rows", summary.rtv_rows, "Held out of invoices")}
      ${this.metric("Gross Value", this.money(summary.gross_invoice_value), "Invoice value")}
      ${this.metric("Taxable Value", this.money(summary.taxable_value), "Gross less GST")}
      ${this.metric("GST Value", this.money(summary.gst_value), "IGST/CGST/SGST")}
      ${this.metric("Net Payout", this.money(summary.net_payout), "Marketplace payout")}
    `);
  }

  renderWarnings() {
    const warnings = this.preview.warnings || [];
    this.wrapper.find("[data-role='warnings']").html(
      warnings.map((warning) => `<div class="snrg-mii-warning">${this.esc(warning)}</div>`).join("")
    );
  }

  renderTabs() {
    this.wrapper.find("[data-tab]").each((_, tab) => {
      $(tab).toggleClass("active", $(tab).data("tab") === this.activeTab);
    });
  }

  renderTable() {
    if (!this.preview) {
      this.wrapper.find("[data-role='table']").html(`<div class="snrg-mii-empty">No file preview loaded.</div>`);
      return;
    }

    if (this.activeTab === "invoices") {
      this.renderInvoiceGroups();
    } else if (this.activeTab === "rtv") {
      this.renderRows("RTV rows", this.preview.rtv_rows || [], "rtv");
    } else if (this.activeTab === "adjustments") {
      this.renderRows("Adjustment rows", this.preview.adjustment_rows || [], "adjustment");
    } else {
      this.renderRows("Cancelled rows", this.preview.cancelled_rows || [], "cancelled");
    }
  }

  renderInvoiceGroups() {
    const groups = this.preview.invoice_groups || [];
    if (!groups.length) {
      this.wrapper.find("[data-role='table']").html(`<div class="snrg-mii-empty">No invoiceable rows found.</div>`);
      return;
    }

    this.wrapper.find("[data-role='table']").html(`
      <table class="snrg-mii-table">
        <thead>
          <tr>
            <th>Invoice</th>
            <th>Customer</th>
            <th>Date</th>
            <th>Buyer</th>
            <th>Orders</th>
            <th>Supplier Invoice</th>
            <th class="text-right">Lines</th>
            <th class="text-right">Qty</th>
            <th class="text-right">Taxable</th>
            <th class="text-right">GST</th>
            <th class="text-right">Gross</th>
            <th class="text-right">Payout</th>
          </tr>
        </thead>
        <tbody>
          ${groups.map((group) => this.invoiceGroupRow(group)).join("")}
        </tbody>
      </table>
    `);
  }

  invoiceGroupRow(group) {
    const segment = group.customer_type === "B2B" ? "b2b" : "b2c";
    return `
      <tr>
        <td><div class="snrg-mii-key">${this.esc(group.invoice_number)}</div></td>
        <td><span class="snrg-mii-pill ${segment}">${this.esc(group.customer)}</span></td>
        <td>${this.esc(group.invoice_date || "")}</td>
        <td>
          <div>${this.esc(this.joinValues(group.buyer_names))}</div>
          <div class="snrg-mii-muted">${this.esc(this.joinValues(group.buyer_cities))}${this.buyerLocationSuffix(group)}</div>
        </td>
        <td>${this.esc((group.orders || []).join(", "))}</td>
        <td>${this.esc(this.joinValues(group.supplier_invoices))}</td>
        <td class="text-right">${this.number(group.line_count)}</td>
        <td class="text-right">${this.number(group.quantity)}</td>
        <td class="text-right">${this.money(group.taxable_value)}</td>
        <td class="text-right">${this.money(group.gst_value)}</td>
        <td class="text-right">${this.money(group.gross_invoice_value)}</td>
        <td class="text-right">${this.money(group.net_payout)}</td>
      </tr>
    `;
  }

  renderRows(title, rows, statusClass) {
    if (!rows.length) {
      this.wrapper.find("[data-role='table']").html(`<div class="snrg-mii-empty">No ${this.esc(title.toLowerCase())}.</div>`);
      return;
    }

    this.wrapper.find("[data-role='table']").html(`
      <table class="snrg-mii-table">
        <thead>
          <tr>
            <th>Source Row</th>
            <th>Invoice</th>
            <th>Order</th>
            <th>Buyer</th>
            <th>Item</th>
            <th>Status</th>
            <th>Supplier Invoice</th>
            <th class="text-right">Qty</th>
            <th class="text-right">Gross</th>
            <th class="text-right">GST</th>
            <th class="text-right">Payout</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => this.detailRow(row, statusClass)).join("")}
        </tbody>
      </table>
    `);
  }

  detailRow(row, statusClass) {
    const status = [row.current_status, row.transition_status].filter(Boolean).join(" / ");
    return `
      <tr>
        <td>${this.number(row.source_row)}</td>
        <td><div class="snrg-mii-key">${this.esc(row.invoice_number)}</div><div class="snrg-mii-muted">${this.esc(row.invoice_date || "")}</div></td>
        <td>${this.esc(row.order_number || "")}<div class="snrg-mii-muted">${this.esc(row.suborder_number || "")}</div></td>
        <td>
          <div>${this.esc(row.customer_name || "")}</div>
          <div class="snrg-mii-muted">${this.esc([row.customer_city, row.customer_state, row.customer_pincode].filter(Boolean).join(", "))}</div>
        </td>
        <td><div>${this.esc(row.product_name || "")}</div><div class="snrg-mii-muted">${this.esc(row.marketplace_sku || "")}</div></td>
        <td><span class="snrg-mii-pill ${statusClass}">${this.esc(status || "-")}</span></td>
        <td>${this.esc(row.supplier_invoice || "")}</td>
        <td class="text-right">${this.number(row.quantity)}</td>
        <td class="text-right">${this.money(row.invoice_value)}</td>
        <td class="text-right">${this.money(row.gst_value)}</td>
        <td class="text-right">${this.money(row.net_payout)}</td>
      </tr>
    `;
  }

  metric(label, value, note) {
    return `
      <div class="snrg-mii-metric">
        <div class="snrg-mii-metric-label">${this.esc(label)}</div>
        <div class="snrg-mii-metric-value">${this.esc(value)}</div>
        <div class="snrg-mii-metric-note">${this.esc(note || "")}</div>
      </div>
    `;
  }

  money(value) {
    const numeric = Number(value || 0);
    if (!Number.isFinite(numeric)) return "0.00";
    return numeric.toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  number(value) {
    const numeric = Number(value || 0);
    if (!Number.isFinite(numeric)) return "0";
    return numeric.toLocaleString("en-IN", {
      maximumFractionDigits: 4,
    });
  }

  joinValues(values) {
    return (values || []).filter(Boolean).join(", ");
  }

  buyerLocationSuffix(group) {
    const parts = [
      this.joinValues(group.buyer_states),
      this.joinValues(group.buyer_pincodes),
    ].filter(Boolean);
    if (!parts.length) return "";
    return `, ${this.esc(parts.join(", "))}`;
  }

  esc(value) {
    return frappe.utils.escape_html(String(value ?? ""));
  }
}
