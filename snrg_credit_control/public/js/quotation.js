function snrg_show_minimum_rate_check() {
  frappe.show_alert({
    message: "Checking minimum selling rates...",
    indicator: "blue",
  }, 8);
}

function snrg_hide_minimum_rate_check() {
  // Non-blocking alert auto-dismisses.
}

function get_quotation_credit_view_model(frm) {
  const status = frm.doc.custom_snrg_credit_check_status;
  return {
    status: status || "Not Run",
    reason: frm.doc.custom_snrg_credit_check_reason_code || "",
    overdueCount: Number(frm.doc.custom_snrg_overdue_count_terms || 0),
    overdueAmount: Number(frm.doc.custom_snrg_overdue_amount_terms || 0),
    exposure: Number(frm.doc.custom_snrg_exposure_at_check || 0),
    creditLimit: Number(frm.doc.custom_snrg_credit_limit_at_check || 0),
    quotationValue: Number(frm.doc.grand_total || frm.doc.rounded_total || 0),
    currency: frm.doc.currency || "INR",
    checkedOn: frm.doc.custom_snrg_credit_checked_on || "",
    details: frm.doc.custom_snrg_credit_check_details || "",
  };
}

function parse_credit_detail_preview(details) {
  if (!details) return [];
  return String(details)
    .split(";")
    .map(part => part.trim())
    .filter(Boolean)
    .slice(0, 2);
}

function get_quotation_credit_reason_ui(reason, overdueCount) {
  const hasOverdue = (reason || "").includes("Overdue>Terms");
  const hasLimit = (reason || "").includes("Over-Limit");

  if (hasOverdue && hasLimit) {
    return {
      badge: "Overdue + Over Limit",
      summary: "Multiple credit issues",
      detail: "Customer has overdue invoices beyond the allowed payment terms, and this quotation also exceeds the available credit limit.",
    };
  }

  if (hasOverdue) {
    const detail = overdueCount
      ? `${overdueCount} invoice${overdueCount === 1 ? " is" : "s are"} overdue beyond the allowed payment terms.`
      : "Customer has overdue invoices beyond the allowed payment terms.";
    return {
      badge: "Overdue Invoice",
      summary: "Overdue invoices beyond allowed terms",
      detail,
    };
  }

  if (hasLimit) {
    return {
      badge: "Over Credit Limit",
      summary: "Quotation exceeds available credit limit",
      detail: "Current exposure plus this quotation exceeds the customer's available credit limit.",
    };
  }

  return {
    badge: "",
    summary: "Within policy",
    detail: "Customer is within the configured credit policy.",
  };
}

function render_quotation_credit_chip(frm) {
  try {
    if (!frm || !frm.dashboard || !frm.dashboard.set_headline) return;
    if (frm.dashboard.clear_headline) frm.dashboard.clear_headline();

    const model = get_quotation_credit_view_model(frm);
    const { status, reason, overdueCount, overdueAmount, exposure, creditLimit, quotationValue, currency, checkedOn, details } = model;
    const reasonUi = get_quotation_credit_reason_ui(reason, overdueCount);
    const fmt = value => frappe.format(value, { fieldtype: "Currency", options: currency });
    const fmtSigned = value => {
      const formatted = fmt(Math.abs(value)).replace(/^-+/, "");
      return value < 0 ? `-\u00a0${formatted}` : formatted;
    };
    const formatCheckedOn = value => value ? frappe.datetime.str_to_user(value) : "Not refreshed yet";
    const metricCard = (label, value, valueStyle = "") => `
      <div style="min-width:0;padding:12px 14px;border-radius:8px;background:rgba(255,255,255,.7);border:1px solid rgba(148,163,184,.14);">
        <div style="font-size:10px;font-weight:700;opacity:.52;letter-spacing:.04em;text-transform:uppercase;margin-bottom:6px;">${label}</div>
        <div style="font-size:16px;font-weight:700;line-height:1.2;word-break:break-word;${valueStyle}">${value}</div>
      </div>
    `;
    const metricOp = symbol => `
      <div style="display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;opacity:.42;min-width:22px;">${symbol}</div>
    `;
    const infoCard = (label, value) => `
      <div style="min-width:0;padding:10px 12px;border-radius:8px;background:rgba(15,23,42,.04);border:1px solid rgba(148,163,184,.12);">
        <div style="font-size:10px;font-weight:700;opacity:.52;letter-spacing:.04em;text-transform:uppercase;margin-bottom:5px;">${label}</div>
        <div style="font-size:14px;font-weight:600;line-height:1.2;word-break:break-word;">${value}</div>
      </div>
    `;
    const overduePreview = parse_credit_detail_preview(details);
    const overduePreviewHtml = overduePreview.length
      ? overduePreview.map(line => `<div style="font-size:13px;font-weight:600;line-height:1.35;">${frappe.utils.escape_html(line)}</div>`).join("")
      : `<div style="font-size:13px;opacity:.72;">No overdue invoice lines</div>`;
    const availableCredit = creditLimit ? (creditLimit - exposure) : 0;
    const projectedAvailable = creditLimit ? (creditLimit - exposure - quotationValue) : 0;
    const availableTone = availableCredit < 0
      ? "color:#ef4444;"
      : (availableCredit === 0 ? "color:#f59e0b;" : "color:#22c55e;");
    const projectedTone = projectedAvailable < 0 ? "color:#ef4444;" : "color:#22c55e;";

    const themes = {
      "Not Run": {
        rgb: "100,116,139",
        title: "Credit Status",
        badge: "Not Run",
      },
      "Credit OK": {
        rgb: "34,197,94",
        title: "Credit Status",
        badge: "Healthy",
      },
      "Credit Hold": {
        rgb: "239,68,68",
        title: "Credit Hold",
        badge: reasonUi.badge || "Needs Review",
      },
    };

    const theme = themes[status];
    if (!theme) return;

    const pill = `<span style="display:inline-flex;align-items:center;background:rgba(${theme.rgb},.10);border:1px solid rgba(${theme.rgb},.22);color:rgba(${theme.rgb},1);font-size:10px;font-weight:700;padding:4px 10px;border-radius:999px;white-space:nowrap;">${frappe.utils.escape_html(theme.badge)}</span>`;

    frm.dashboard.set_headline(`
      <div style="background:var(--control-bg, #f8f9fa);border:1px solid var(--border-color, #d1d8dd);border-radius:10px;padding:12px 14px;line-height:1.35;color:var(--text-color, #36414c);box-shadow:none;">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;flex-wrap:wrap;">
          <div style="min-width:0;">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
              <div style="font-size:16px;font-weight:700;">${theme.title}</div>
              <div style="font-size:11px;opacity:.68;">Last Refresh: ${formatCheckedOn(checkedOn)}</div>
            </div>
          </div>
          ${pill}
        </div>
        <div style="margin-top:10px;overflow-x:auto;">
          <div style="display:grid;grid-template-columns:minmax(150px,1fr) 26px minmax(150px,1fr) 26px minmax(150px,1fr) 26px minmax(150px,1fr) 26px minmax(150px,1fr);gap:10px;align-items:stretch;min-width:900px;">
          ${metricCard("Credit Limit", fmt(creditLimit))}
          ${metricOp("-")}
          ${metricCard("Current Exposure", fmtSigned(exposure))}
          ${metricOp("=")}
          ${metricCard("Available Credit", fmtSigned(availableCredit), availableTone)}
          ${metricOp("-")}
          ${metricCard("Quotation Value", fmt(quotationValue))}
          ${metricOp("=")}
          ${metricCard("Projected Balance", fmtSigned(projectedAvailable), projectedTone)}
          </div>
        </div>
        <div style="margin-top:10px;display:grid;grid-template-columns:minmax(120px,.75fr) minmax(150px,.9fr) minmax(260px,1.35fr) minmax(260px,1.4fr);gap:10px 12px;align-items:stretch;">
          ${infoCard("Overdue Invoices", String(overdueCount))}
          ${infoCard("Overdue Amount", fmt(overdueAmount))}
          ${infoCard("Top Overdue Invoices", overduePreviewHtml)}
          ${infoCard("Reason", frappe.utils.escape_html(reasonUi.detail))}
        </div>
      </div>
    `);

    const box = frm.dashboard.wrapper.find(".dashboard-headline");
    box.css({ background: "transparent", padding: "0", "box-shadow": "none", border: "none" });
  } catch (e) {
    console.warn("[SNRG Quotation Credit Chip] render error:", e);
  }
}

function render_quotation_header_status(frm) {
  try {
    if (!frm || !frm.page || !frm.page.wrapper) return;

    const model = get_quotation_credit_view_model(frm);
    frm.page.wrapper.find(".snrg-credit-header-pill").remove();

    if (!model || !model.status || model.status === "Not Run") return;

    const status = model.status;
    const reason = model.reason || "";
    const config = {
      "Credit OK": {
        bg: "rgba(34,197,94,.14)",
        border: "rgba(34,197,94,.28)",
        color: "#22c55e",
        label: "Credit OK",
      },
      "Credit Hold": {
        bg: "rgba(239,68,68,.14)",
        border: "rgba(239,68,68,.28)",
        color: "#f87171",
        label: `Credit Hold · ${get_quotation_credit_reason_ui(reason, model.overdueCount).badge || "Needs Review"}`,
      },
    }[status];

    if (!config) return;

    const pill = $(`
      <span class="snrg-credit-header-pill" style="display:inline-flex;align-items:center;margin-left:8px;padding:4px 12px;border-radius:999px;border:1px solid ${config.border};background:${config.bg};color:${config.color};font-size:12px;font-weight:700;line-height:1.2;white-space:nowrap;">
        ${frappe.utils.escape_html(config.label)}
      </span>
    `);

    const primaryIndicator = frm.page.wrapper.find(".page-head .indicator-pill, .layout-main .indicator-pill").first();
    if (primaryIndicator.length) {
      pill.insertAfter(primaryIndicator);
      return;
    }

    const titleArea = frm.page.wrapper.find(".page-title, .title-area, .page-form-header").first();
    if (titleArea.length) {
      titleArea.append(pill);
    }
  } catch (e) {
    console.warn("[SNRG Quotation Header Status] render error:", e);
  }
}

frappe.ui.form.on("Quotation", {
  setup(frm) {
    frm._snrg_credit_preview = null;
  },
  refresh(frm) {
    render_quotation_credit_chip(frm);
    render_quotation_header_status(frm);
    add_quotation_credit_button(frm);
    add_item_price_request_button(frm);
  },
  party_name(frm) {
    clear_quotation_credit_preview(frm);
  },
  company(frm) {
    clear_quotation_credit_preview(frm);
  },
  quotation_to(frm) {
    clear_quotation_credit_preview(frm);
  },
  custom_snrg_credit_check_status(frm) {
    render_quotation_credit_chip(frm);
    render_quotation_header_status(frm);
  },
  custom_snrg_credit_check_reason_code(frm) {
    render_quotation_credit_chip(frm);
    render_quotation_header_status(frm);
  },
  custom_snrg_credit_checked_on(frm) {
    render_quotation_credit_chip(frm);
  },
  custom_snrg_overdue_count_terms(frm) {
    render_quotation_credit_chip(frm);
  },
  custom_snrg_overdue_amount_terms(frm) {
    render_quotation_credit_chip(frm);
  },
  custom_snrg_exposure_at_check(frm) {
    render_quotation_credit_chip(frm);
  },
  custom_snrg_credit_limit_at_check(frm) {
    render_quotation_credit_chip(frm);
  },
  before_save(frm) {
    snrg_show_minimum_rate_check();
    frm._snrg_credit_preview = null;
  },
  after_save() {
    snrg_hide_minimum_rate_check();
  },
  before_submit() {
    snrg_show_minimum_rate_check();
  },
  on_submit() {
    snrg_hide_minimum_rate_check();
  },
});

function clear_quotation_credit_preview(frm) {
  frm._snrg_credit_preview = null;
  render_quotation_credit_chip(frm);
  render_quotation_header_status(frm);
}

function add_quotation_credit_button(frm) {
  if (!frm.doc.party_name || !frm.doc.company || frm.doc.quotation_to !== "Customer") {
    return;
  }

  frm.add_custom_button("Refresh Credit Status", () => refresh_quotation_credit_status(frm), "Credit Control");
  frm.add_custom_button("Current Credit Details", () => open_quotation_credit_details(frm), "Credit Control");
}

function add_item_price_request_button(frm) {
  const canRequest = frappe.user_roles.includes("Price Request User")
    || frappe.user_roles.includes("Pricing Approver")
    || frappe.user_roles.includes("System Manager");
  if (!canRequest) return;

  frm.add_custom_button("Request Item Price", () => open_item_price_request_dialog(frm), "Pricing");
}

function get_quotation_item_options(frm) {
  return (frm.doc.items || [])
    .filter(row => row.item_code)
    .map(row => ({
      label: `${row.idx} - ${row.item_code}${row.item_name ? ` - ${row.item_name}` : ""}`,
      value: String(row.idx),
    }));
}

function get_quotation_row_by_idx(frm, idx) {
  const rowIdx = Number(idx || 0);
  return (frm.doc.items || []).find(row => Number(row.idx) === rowIdx);
}

function open_item_price_request_dialog(frm) {
  const itemOptions = get_quotation_item_options(frm);
  if (!itemOptions.length) {
    frappe.msgprint({
      title: "No Items",
      message: "Add at least one item row before requesting an item price.",
      indicator: "orange",
    });
    return;
  }

  const dialog = new frappe.ui.Dialog({
    title: "Request Item Price",
    fields: [
      {
        fieldname: "quotation_item_row",
        fieldtype: "Select",
        label: "Quotation Item Row",
        options: itemOptions.map(option => option.label).join("\n"),
        reqd: 1,
      },
      {
        fieldname: "item_preview",
        fieldtype: "HTML",
      },
      {
        fieldname: "price_list",
        fieldtype: "Link",
        label: "Price List",
        options: "Price List",
        reqd: 1,
        default: frm.doc.selling_price_list || "",
        get_query() {
          return {
            filters: {
              enabled: 1,
              selling: 1,
            },
          };
        },
      },
      {
        fieldname: "requested_rate",
        fieldtype: "Currency",
        label: "Requested Rate",
        reqd: 1,
      },
      {
        fieldname: "uom",
        fieldtype: "Link",
        label: "UOM",
        options: "UOM",
        reqd: 1,
      },
      {
        fieldname: "currency",
        fieldtype: "Link",
        label: "Currency",
        options: "Currency",
        reqd: 1,
        default: frm.doc.currency || "",
      },
      {
        fieldname: "valid_from",
        fieldtype: "Date",
        label: "Valid From",
        default: frappe.datetime.get_today(),
      },
      {
        fieldname: "valid_upto",
        fieldtype: "Date",
        label: "Valid Upto",
      },
      {
        fieldname: "rate_communication_attachment",
        fieldtype: "Attach",
        label: "Rate Communication Attachment",
        description: "Attach WhatsApp/email screenshot or any communication proof for the quoted rate.",
      },
      {
        fieldname: "reason",
        fieldtype: "Small Text",
        label: "Reason / Notes",
      },
    ],
    primary_action_label: "Create Request",
    primary_action: async () => {
      const values = dialog.get_values();
      if (!values) return;

      const row = get_quotation_row_by_dialog_value(frm, values.quotation_item_row);
      if (!row) {
        frappe.msgprint({
          title: "Invalid Row",
          message: "Select a valid quotation item row.",
          indicator: "red",
        });
        return;
      }

      try {
        const { message } = await frappe.call({
          method: "snrg_credit_control.snrg_credit_control.doctype.item_price_request.item_price_request.create_from_quotation",
          args: {
            quotation: frm.is_new() ? null : frm.doc.name,
            quotation_item_row: row.idx,
            item_code: row.item_code,
            item_name: row.item_name,
            customer: frm.doc.quotation_to === "Customer" ? frm.doc.party_name : null,
            company: frm.doc.company,
            price_list: values.price_list,
            requested_rate: values.requested_rate,
            uom: values.uom,
            currency: values.currency,
            valid_from: values.valid_from,
            valid_upto: values.valid_upto,
            reason: values.reason,
            rate_communication_attachment: values.rate_communication_attachment,
          },
          freeze: true,
          freeze_message: "Creating item price request...",
        });

        dialog.hide();
        frappe.show_alert({
          message: (message && message.message) || "Item Price Request created.",
          indicator: "green",
        });
        if (message && message.name && frm.is_new()) {
          const requestLink = `/app/item-price-request/${encodeURIComponent(message.name)}`;
          frappe.msgprint({
            title: "Item Price Request Created",
            message: `Request <a href="${requestLink}">${frappe.utils.escape_html(message.name)}</a> has been sent for approval. This quotation is still not saved.`,
            indicator: "green",
          });
        } else if (message && message.name) {
          frappe.set_route("Form", "Item Price Request", message.name);
        }
      } catch (error) {
        frappe.msgprint({
          title: "Request failed",
          message: (error && error.message) || String(error),
          indicator: "red",
        });
      }
    },
  });

  dialog.show();
  dialog.set_value("quotation_item_row", itemOptions[0].label);
  sync_item_price_request_dialog(frm, dialog);

  dialog.fields_dict.quotation_item_row.df.onchange = () => {
    sync_item_price_request_dialog(frm, dialog);
  };
}

function get_quotation_row_by_dialog_value(frm, value) {
  const idx = String(value || "").split(" - ")[0];
  return get_quotation_row_by_idx(frm, idx);
}

function sync_item_price_request_dialog(frm, dialog) {
  const row = get_quotation_row_by_dialog_value(frm, dialog.get_value("quotation_item_row"));
  if (!row) return;

  dialog.set_value("uom", row.uom || row.stock_uom || "");
  if (!dialog.get_value("requested_rate") && row.rate) {
    dialog.set_value("requested_rate", row.rate);
  }
  if (!dialog.get_value("currency") && frm.doc.currency) {
    dialog.set_value("currency", frm.doc.currency);
  }

  const html = `
    <div style="padding:10px 12px;border:1px solid #e5e7eb;border-radius:6px;background:#f8fafc;margin-bottom:4px;">
      <div style="font-weight:700;margin-bottom:4px;">${frappe.utils.escape_html(row.item_code || "")}</div>
      <div style="font-size:12px;color:#64748b;">${frappe.utils.escape_html(row.item_name || "")}</div>
      <div style="font-size:12px;color:#64748b;margin-top:4px;">Quotation row ${frappe.utils.escape_html(String(row.idx || ""))}</div>
    </div>
  `;
  dialog.fields_dict.item_preview.$wrapper.html(html);
}

async function open_quotation_credit_details(frm) {
  if (!frm.doc.party_name || !frm.doc.company) {
    frappe.msgprint({
      title: "Missing Customer",
      message: "Select a customer and company first to view credit details.",
      indicator: "orange",
    });
    return;
  }

  try {
    const { message } = await frappe.call({
      method: "snrg_credit_control.overrides.quotation.get_credit_details",
      args: {
        customer: frm.doc.party_name,
        customer_name: frm.doc.customer_name || frm.doc.party_name,
        company: frm.doc.company,
        currency: frm.doc.currency,
        amount: frm.doc.grand_total || frm.doc.rounded_total || 0,
      },
    });

    if (!message || !message.html) {
      return;
    }

    frappe.msgprint({
      title: message.title || "Customer Credit Details",
      message: message.html,
      wide: true,
    });
  } catch (e) {
    console.warn("[SNRG Quotation Credit Details] dialog error:", e);
    frappe.msgprint({
      title: "Unable to load credit details",
      message: (e && e.message) || String(e),
      indicator: "red",
    });
  }
}

async function refresh_quotation_credit_status(frm) {
  if (!frm.doc.party_name || !frm.doc.company) {
    frappe.msgprint({
      title: "Missing Customer",
      message: "Select a customer and company first to refresh credit status.",
      indicator: "orange",
    });
    return;
  }

  try {
    const { message } = await frappe.call({
      method: "snrg_credit_control.overrides.quotation.refresh_credit_status",
      args: {
        quotation_name: frm.doc.name,
        customer: frm.doc.party_name,
        company: frm.doc.company,
        currency: frm.doc.currency,
        amount: frm.doc.grand_total || frm.doc.rounded_total || 0,
      },
    });

    if (!message) return;

    frm._snrg_credit_preview = null;
    frm.doc.custom_snrg_credit_check_status = message.status || "Not Run";
    frm.doc.custom_snrg_credit_check_reason_code = message.reason_code || "";
    frm.doc.custom_snrg_overdue_count_terms = message.overdue_count || 0;
    frm.doc.custom_snrg_overdue_amount_terms = message.total_overdue || 0;
    frm.doc.custom_snrg_exposure_at_check = message.effective_ar || 0;
    frm.doc.custom_snrg_credit_limit_at_check = message.credit_limit || 0;
    frm.doc.custom_snrg_credit_check_details = message.details || "";
    frm.doc.custom_snrg_credit_checked_on = message.checked_on || "";
    frm.doc.custom_credit_clearance_date = message.credit_clearance_date || frm.doc.custom_credit_clearance_date || "";

    render_quotation_credit_chip(frm);
    render_quotation_header_status(frm);
    frm.refresh_fields([
      "custom_snrg_credit_check_status",
      "custom_snrg_credit_check_reason_code",
      "custom_snrg_overdue_count_terms",
      "custom_snrg_overdue_amount_terms",
      "custom_snrg_exposure_at_check",
      "custom_snrg_credit_limit_at_check",
      "custom_snrg_credit_check_details",
      "custom_snrg_credit_checked_on",
      "custom_credit_clearance_date",
    ]);

    frappe.show_alert({
      message: "Credit status refreshed",
      indicator: message.status === "Credit Hold" ? "orange" : "green",
    });
  } catch (e) {
    console.warn("[SNRG Quotation Credit Refresh] error:", e);
    frappe.msgprint({
      title: "Unable to refresh credit status",
      message: (e && e.message) || String(e),
      indicator: "red",
    });
  }
}
