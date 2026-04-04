// =============================================================================
// SNRG Credit Control — Sales Order client script
// =============================================================================

function get_sales_order_credit_view_model(frm) {
  const status = frm.doc.custom_snrg_credit_check_status;
  if (!status || status === "Not Run") {
    return null;
  }

  return {
    status,
    reason: frm.doc.custom_snrg_credit_check_reason_code || "",
    overdueCount: Number(frm.doc.custom_snrg_overdue_count_terms || 0),
    overdueAmount: Number(frm.doc.custom_snrg_overdue_amount_terms || 0),
    exposure: Number(frm.doc.custom_snrg_exposure_at_check || 0),
    creditLimit: Number(frm.doc.custom_snrg_credit_limit_at_check || 0),
    orderValue: Number(frm.doc.grand_total || frm.doc.rounded_total || 0),
    currency: frm.doc.currency || "INR",
    approvalStatus: frm.doc.custom_credit_approval_status || "",
    overrideCap: Number(frm.doc.custom_snrg_override_cap_amount || 0),
    overrideValidTill: frm.doc.custom_snrg_override_valid_till || "",
  };
}

function render_sales_order_credit_chip(frm) {
  try {
    if (!frm || !frm.dashboard || !frm.dashboard.set_headline) return;
    if (frm.dashboard.clear_headline) frm.dashboard.clear_headline();

    const model = get_sales_order_credit_view_model(frm);
    if (!model) return;

    const {
      status,
      reason,
      overdueCount,
      overdueAmount,
      exposure,
      creditLimit,
      orderValue,
      currency,
      approvalStatus,
      overrideCap,
      overrideValidTill,
    } = model;
    const hasOverdueTerms = reason.includes("Overdue>Terms");
    const hasOverLimit = reason.includes("Over-Limit");

    const availableCredit = creditLimit ? (creditLimit - exposure) : 0;
    const projectedBalance = creditLimit ? (creditLimit - exposure - orderValue) : 0;
    const fmt = value => frappe.format(value, { fieldtype: "Currency", options: currency });
    const fmtSigned = value => {
      const formatted = fmt(Math.abs(value));
      return value < 0 ? `-${formatted}` : formatted;
    };

    const themes = {
      "Credit OK": {
        rgb: "34,197,94",
        title: "Credit OK",
        badge: "Healthy",
        subtitle: "Customer is currently within the configured credit policy.",
      },
      "Credit Hold": {
        rgb: "239,68,68",
        title: "Credit Hold",
        badge: reason || "Review",
        subtitle: hasOverdueTerms && hasOverLimit
          ? "Customer has overdue invoices beyond the configured threshold and the current exposure plus this order crosses the assigned credit limit."
          : hasOverLimit
          ? "Current exposure plus this order crosses the customer's credit limit."
          : "Customer has overdue invoices beyond the configured threshold.",
      },
    };

    const theme = themes[status];
    if (!theme) return;

    const pill = `<span style="display:inline-flex;align-items:center;background:rgba(${theme.rgb},.10);border:1px solid rgba(${theme.rgb},.22);color:rgba(${theme.rgb},1);font-size:10px;font-weight:700;padding:3px 9px;border-radius:999px;white-space:nowrap;">${frappe.utils.escape_html(theme.badge)}</span>`;
    const metric = (label, value, valueStyle = "", accent = "") =>
      `<div style="position:relative;min-width:0;padding-right:${accent ? "14px" : "0"};">
        <div style="font-size:10px;font-weight:700;opacity:.52;margin-bottom:3px;letter-spacing:.03em;text-transform:uppercase;">${label}</div>
        <div style="font-size:16px;font-weight:700;letter-spacing:-0.2px;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;${valueStyle}">${value}</div>
        ${accent ? `<div style="position:absolute;right:0;top:18px;font-size:13px;font-weight:800;opacity:.26;">${accent}</div>` : ""}
      </div>`;

    const availableTone = projectedBalance < 0
      ? "color:#fca5a5;"
      : (availableCredit <= 0 ? "color:#fdba74;" : `color:rgba(${theme.rgb},1);`);
    const projectedTone = projectedBalance < 0
      ? "color:#f87171;font-weight:800;"
      : (status === "Credit OK" ? "color:#22c55e;font-weight:800;" : "color:#f8fafc;font-weight:800;");

    let approvalLine = "";
    if (approvalStatus || overrideCap || overrideValidTill) {
      const parts = [];
      if (approvalStatus) parts.push(`<span><strong>Approval:</strong> ${frappe.utils.escape_html(approvalStatus)}</span>`);
      if (overrideCap) parts.push(`<span><strong>Cap:</strong> ${fmt(overrideCap)}</span>`);
      if (overrideValidTill) parts.push(`<span><strong>Valid Till:</strong> ${frappe.datetime.str_to_user(overrideValidTill)}</span>`);
      approvalLine = `<div style="display:flex;gap:12px 16px;flex-wrap:wrap;font-size:11px;opacity:.8;">${parts.join("")}</div>`;
    }

    frm.dashboard.set_headline(`
      <div style="background:var(--control-bg, #f8f9fa);border:1px solid var(--border-color, #d1d8dd);border-radius:10px;padding:12px 14px;line-height:1.35;color:var(--text-color, #36414c);box-shadow:none;">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;flex-wrap:wrap;">
          <div style="min-width:0;">
            <div style="font-size:16px;font-weight:700;margin-bottom:1px;">${theme.title}</div>
            <div style="font-size:11px;opacity:.7;max-width:780px;">${theme.subtitle}</div>
          </div>
          ${pill}
        </div>
        <div style="margin-top:10px;padding:10px 12px;border-radius:8px;background:rgba(255,255,255,.55);border:1px solid rgba(140,140,140,.10);">
          <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));gap:10px 14px;align-items:start;">
            ${metric("Credit Limit", fmt(creditLimit), "", "−")}
            ${metric("Current Exposure", fmt(exposure), "", "=")}
            ${metric("Available Credit", fmtSigned(availableCredit), availableTone, "−")}
            ${metric("Order Value", fmt(orderValue), "", "=")}
            ${metric("Projected Balance", fmtSigned(projectedBalance), projectedTone)}
          </div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:10px;font-size:11px;opacity:.85;">
          <span style="display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:rgba(15,23,42,.05);"><strong>Overdue:</strong>&nbsp;${overdueCount}</span>
          <span style="display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:rgba(15,23,42,.05);"><strong>Amount:</strong>&nbsp;${fmt(overdueAmount)}</span>
          <span style="display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:rgba(15,23,42,.05);"><strong>Status:</strong>&nbsp;${frappe.utils.escape_html(reason || "Within policy")}</span>
          ${approvalLine}
        </div>
      </div>
    `);

    const box = frm.dashboard.wrapper.find(".dashboard-headline");
    box.css({ background: "transparent", padding: "0", "box-shadow": "none", border: "none" });
  } catch (e) {
    console.warn("[SNRG Sales Order Credit Chip] render error:", e);
  }
}

function render_sales_order_header_status(frm) {
  try {
    if (!frm || !frm.page || !frm.page.wrapper) return;

    const model = get_sales_order_credit_view_model(frm);
    frm.page.wrapper.find(".snrg-so-credit-header-pill").remove();
    if (!model || !model.status || model.status === "Not Run") return;

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
        label: model.reason ? `Credit Hold · ${model.reason}` : "Credit Hold",
      },
    }[model.status];

    if (!config) return;

    const pill = $(`
      <span class="snrg-so-credit-header-pill" style="display:inline-flex;align-items:center;margin-left:8px;padding:4px 12px;border-radius:999px;border:1px solid ${config.border};background:${config.bg};color:${config.color};font-size:12px;font-weight:700;line-height:1.2;white-space:nowrap;">
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
    console.warn("[SNRG Sales Order Header Status] render error:", e);
  }
}

frappe.ui.form.on("Sales Order", {
  refresh(frm) {
    render_sales_order_credit_chip(frm);
    render_sales_order_header_status(frm);
    add_sales_order_credit_buttons(frm);
  },
  custom_snrg_credit_check_status(frm) {
    render_sales_order_credit_chip(frm);
    render_sales_order_header_status(frm);
  },
  custom_snrg_credit_check_reason_code(frm) {
    render_sales_order_credit_chip(frm);
    render_sales_order_header_status(frm);
  },
  custom_snrg_override_cap_amount(frm) {
    render_sales_order_credit_chip(frm);
  },
  custom_snrg_override_valid_till(frm) {
    render_sales_order_credit_chip(frm);
  },
  custom_credit_approval_status(frm) {
    render_sales_order_credit_chip(frm);
  },
  custom_snrg_overdue_count_terms(frm) {
    render_sales_order_credit_chip(frm);
  },
  custom_snrg_overdue_amount_terms(frm) {
    render_sales_order_credit_chip(frm);
  },
  custom_snrg_exposure_at_check(frm) {
    render_sales_order_credit_chip(frm);
  },
  custom_snrg_credit_limit_at_check(frm) {
    render_sales_order_credit_chip(frm);
  },
  grand_total(frm) {
    render_sales_order_credit_chip(frm);
  },
  rounded_total(frm) {
    render_sales_order_credit_chip(frm);
  },
});

function add_sales_order_credit_buttons(frm) {
  if (frm.doc.docstatus !== 0) return;

  const isApprover = frappe.user.has_role("Credit Approver");
  const hasRequest = !!frm.doc.custom_snrg_request_time;

  frm.add_custom_button("Check Credit Status", () => refresh_sales_order_credit_status(frm), "Credit Control");
  frm.add_custom_button("Request Approval", () => open_request_dialog(frm), "Credit Control");
  if (!frm.is_new()) {
    frm.add_custom_button("Link Payment Entry", () => open_payment_link_dialog(frm), "Credit Control");
  }

  if (isApprover && hasRequest) {
    frm.add_custom_button("Approve Credit", () => open_approve_dialog(frm), "Credit Control");
  }
}

async function refresh_sales_order_credit_status(frm) {
  if (!frm.doc.customer || !frm.doc.company) {
    frappe.msgprint({
      title: "Missing Customer",
      message: "Select a customer and company first to check credit status.",
      indicator: "orange",
    });
    return;
  }

  try {
    const { message } = await frappe.call({
      method: "snrg_credit_control.overrides.sales_order.get_credit_status",
      args: {
        customer: frm.doc.customer,
        company: frm.doc.company,
        currency: frm.doc.currency,
        amount: frm.doc.grand_total || frm.doc.rounded_total || 0,
      },
    });

    if (!message) return;

    frm.doc.custom_snrg_credit_check_status = message.status || "Not Run";
    frm.doc.custom_snrg_credit_check_reason_code = message.reason_code || "";
    frm.doc.custom_snrg_overdue_count_terms = message.overdue_count || 0;
    frm.doc.custom_snrg_overdue_amount_terms = message.total_overdue || 0;
    frm.doc.custom_snrg_exposure_at_check = message.effective_ar || 0;
    frm.doc.custom_snrg_credit_limit_at_check = message.credit_limit || 0;
    frm.doc.custom_snrg_credit_check_details = message.details || "";

    render_sales_order_credit_chip(frm);
    render_sales_order_header_status(frm);

    frappe.show_alert({
      message: `Credit status refreshed: ${message.status || "Not Run"}`,
      indicator: message.status === "Credit Hold" ? "orange" : "green",
    });
  } catch (e) {
    console.warn("[SNRG Sales Order Credit Check] refresh error:", e);
    frappe.msgprint({
      title: "Unable to check credit status",
      message: (e && e.message) || String(e),
      indicator: "red",
    });
  }
}

function open_request_dialog(frm) {
  const d = new frappe.ui.Dialog({
    title: "Request Credit Approval",
    fields: [
      {
        fieldtype: "Section Break",
        label: "Approval Routing",
      },
      {
        fieldtype: "Link",
        fieldname: "approver_employee",
        label: "Send Approval Request To",
        options: "Employee",
        reqd: 1,
        description: "Internal employee who should receive the approval request through ERPNext notification and email",
        get_query: () => ({
          filters: {
            status: "Active",
            user_id: ["is", "set"],
          },
        }),
      },
      {
        fieldtype: "Section Break",
        label: "Promise to Pay Details",
      },
      {
        fieldtype: "Link",
        fieldname: "ptp_by",
        label: "Committed By (Employee)",
        options: "Employee",
        reqd: 1,
        description: "The customer contact / employee who is making the payment commitment",
      },
      {
        fieldtype: "Column Break",
      },
      {
        fieldtype: "Date",
        fieldname: "ptp_date",
        label: "Promise Date",
        reqd: 1,
        default: frappe.datetime.get_today(),
        description: "Date when this promise was given",
      },
      {
        fieldtype: "Section Break",
      },
      {
        fieldtype: "Date",
        fieldname: "commitment_date",
        label: "Payment By Date",
        reqd: 1,
        description: "Date by which the customer commits to pay",
      },
      {
        fieldtype: "Column Break",
      },
      {
        fieldtype: "Currency",
        fieldname: "committed_amount",
        label: "Committed Amount",
        reqd: 1,
        default: frm.doc.custom_snrg_overdue_amount_terms || 0,
        description: "Amount the customer has committed to pay (defaults to total overdue)",
      },
      {
        fieldtype: "Section Break",
      },
      {
        fieldtype: "Select",
        fieldname: "payment_mode",
        label: "Payment Mode",
        reqd: 1,
        options: "\nNEFT\nRTGS\nCheque\nCash\nUPI\nOther",
      },
      {
        fieldtype: "Column Break",
      },
      {
        fieldtype: "Data",
        fieldname: "cheque_number",
        label: "Cheque / UTR Number",
        depends_on: "eval:['Cheque','NEFT','RTGS'].includes(doc.payment_mode)",
        description: "Cheque number or UTR reference if applicable",
      },
      {
        fieldtype: "Section Break",
      },
      {
        fieldtype: "Small Text",
        fieldname: "remarks",
        label: "Remarks",
        description: "Any additional context or notes",
      },
    ],
    primary_action_label: "Submit Request",
    async primary_action(values) {
      try {
        if (frm.is_new()) {
          await frm.save();
        }
        d.set_message("Saving and sending request…");

        await frappe.call({
          method: "snrg_credit_control.overrides.sales_order.request_credit_approval",
          args: {
            sales_order: frm.doc.name,
            approver_employee: values.approver_employee,
            ptp_by: values.ptp_by,
            ptp_date: values.ptp_date,
            commitment_date: values.commitment_date,
            committed_amount: values.committed_amount,
            payment_mode: values.payment_mode,
            cheque_number: values.cheque_number || "",
            remarks: values.remarks || "",
          },
        });

        d.hide();
        frappe.show_alert({ message: "Approval request sent to the selected approver.", indicator: "green" });
        frm.reload_doc();
      } catch (e) {
        console.error("[SNRG] Request dialog exception", e);
        frappe.msgprint({
          title: "Failed to send request",
          message: (e && (e.message || e._server_messages)) || String(e),
          indicator: "red",
        });
      }
    },
  });
  d.show();
}

function open_payment_link_dialog(frm) {
  frappe.call({
    method: "snrg_credit_control.overrides.sales_order.get_ptp_references",
    args: { sales_order: frm.doc.name },
    callback: ({ message }) => {
      const refs = message || [];
      if (!refs.length) {
        frappe.msgprint({
          title: "No Active PTP",
          message: "Create a PTP request first, then link Payment Entries against it.",
          indicator: "orange",
        });
        return;
      }

      const refMap = {};
      const options = refs.map(ref => {
        const label = `${ref.label} | Remaining ${frappe.format(ref.difference_amount || 0, { fieldtype: "Currency", options: frm.doc.currency || "INR" })} | ${ref.status}`;
        refMap[label] = ref;
        return label;
      });

      const d = new frappe.ui.Dialog({
        title: "Link Payment Entry to PTP",
        fields: [
          {
            fieldtype: "Select",
            fieldname: "ptp_label",
            label: "PTP Reference",
            reqd: 1,
            options: ["", ...options].join("\n"),
          },
          {
            fieldtype: "Link",
            fieldname: "payment_entry",
            label: "Payment Entry",
            options: "Payment Entry",
            reqd: 1,
            get_query: () => ({
              filters: {
                docstatus: 1,
                party_type: "Customer",
                party: frm.doc.customer,
              },
            }),
          },
          {
            fieldtype: "Currency",
            fieldname: "allocated_amount",
            label: "Allocated Amount",
            reqd: 1,
          },
          {
            fieldtype: "Small Text",
            fieldname: "remarks",
            label: "Remarks",
          },
        ],
        primary_action_label: "Add Payment Link",
        primary_action(values) {
          const ref = refMap[values.ptp_label];
          if (!ref) {
            frappe.msgprint({ title: "Missing PTP", message: "Select a valid PTP reference.", indicator: "red" });
            return;
          }

          frappe.call({
            method: "snrg_credit_control.overrides.sales_order.link_payment_entry_from_report",
            args: {
              ptp_entry_id: ref.ptp_entry_id,
              payment_entry: values.payment_entry,
              allocated_amount: values.allocated_amount,
              remarks: values.remarks || "",
            },
            callback: () => {
              d.hide();
              frappe.show_alert({ message: "Payment Entry linked to PTP.", indicator: "green" });
              frm.reload_doc();
            },
            error: (err) => {
              console.error("[SNRG] Payment link save error", err);
              frappe.msgprint({
                title: "Failed to link Payment Entry",
                message: (err && (err.message || err._server_messages)) || "Unknown error",
                indicator: "red",
              });
            },
          });
        },
      });

      d.show();

      d.get_field("ptp_label").$input.on("change", () => {
        const ref = refMap[d.get_value("ptp_label")];
        if (!ref) return;
        d.set_value("allocated_amount", Math.max(0, Number(ref.difference_amount || 0)));
      });
    },
  });
}

function open_approve_dialog(frm) {
  const reqAmt = Number(frm.doc.custom_snrg_request_amount || 0);
  const soAmt = Number(frm.doc.grand_total || frm.doc.rounded_total || 0);
  const defaultCap = Math.min(reqAmt || soAmt, soAmt);
  const defaultTill = frappe.datetime.add_days(frappe.datetime.get_today(), 7);

  const d = new frappe.ui.Dialog({
    title: "Approve Credit",
    fields: [
      {
        fieldtype: "HTML",
        options: `
          <div style="background:#f8f9fa;border-radius:6px;padding:10px 14px;margin-bottom:6px;font-size:13px;">
            <b>Customer:</b> ${frappe.utils.escape_html(frm.doc.customer_name || frm.doc.customer)}<br>
            <b>Order Value:</b> ${frappe.format(soAmt, { fieldtype: "Currency", options: frm.doc.currency || "INR" })}<br>
            <b>Requested Amount:</b> ${frappe.format(reqAmt, { fieldtype: "Currency", options: frm.doc.currency || "INR" })}
          </div>`,
      },
      {
        fieldtype: "Currency",
        fieldname: "approved_cap",
        label: "Approve Up To (Cap Amount)",
        reqd: 1,
        default: defaultCap,
        description: "Maximum order value you are approving. Cannot exceed the order value.",
      },
      {
        fieldtype: "Date",
        fieldname: "valid_till",
        label: "Approval Valid Till",
        reqd: 1,
        default: defaultTill,
        description: "The approval expires after this date.",
      },
    ],
    primary_action_label: "Confirm Approval",
    async primary_action(values) {
      try {
        if (values.approved_cap > soAmt) {
          frappe.msgprint({
            title: "Invalid Amount",
            message: `Approved cap (${values.approved_cap}) cannot exceed the order value (${soAmt}).`,
            indicator: "red",
          });
          return;
        }
        if (frappe.datetime.get_diff(values.valid_till, frappe.datetime.get_today()) < 0) {
          frappe.msgprint({ title: "Invalid Date", message: "Valid Till date must be today or in the future.", indicator: "red" });
          return;
        }

        await frm.set_value("custom_snrg_override_cap_amount", values.approved_cap);
        await frm.set_value("custom_snrg_override_valid_till", values.valid_till);
        await frm.set_value("custom_snrg_approver", frappe.session.user);
        await frm.set_value("custom_snrg_approval_time", frappe.datetime.now_datetime());
        await frm.set_value("custom_credit_approval_status", "Approved");
        await frm.save();

        d.hide();
        frappe.show_alert({ message: "Credit approved. The sales team has been notified.", indicator: "green" });
      } catch (e) {
        console.error("[SNRG] Approve dialog error:", e);
        frappe.msgprint({ title: "Approval failed", message: (e && e.message) || String(e), indicator: "red" });
      }
    },
  });
  d.show();
}
