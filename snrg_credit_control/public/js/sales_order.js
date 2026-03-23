// =============================================================================
// SNRG Credit Control — Sales Order client script
// Replaces Client Scripts 1, 2, and 3.
//
// Sections:
//   1. Credit Chip  — dashboard headline card showing current credit status
//   2. Form Events  — refresh handler, field watchers
//   3. Request Approval dialog — structured PTP entry
//   4. Approve Credit dialog  — cap + valid-till confirmation for approvers
//   5. CSS  — fadeIn animation
// =============================================================================


// =============================================================================
// 1. CREDIT CHIP
// =============================================================================

function render_credit_chip(frm) {
  try {
    if (!frm || !frm.dashboard || !frm.dashboard.set_headline) return;
    if (frm.is_new() || !frm.doc.name) return;
    if (frm.dashboard.clear_headline) frm.dashboard.clear_headline();

    const cap    = Number(frm.doc.custom_snrg_override_cap_amount || 0);
    const till   = frm.doc.custom_snrg_override_valid_till;
    const amt    = Number(frm.doc.grand_total || frm.doc.rounded_total || 0);
    const cur    = frm.doc.currency || "INR";
    const fmt    = (v) => frappe.format(v, { fieldtype: "Currency", options: cur });
    const hasReq = !!frm.doc.custom_snrg_request_time;

    // ── Case 1: Pending approval ───────────────────────────────────────────
    if (hasReq && !cap) {
      _set_chip(frm, `
        <div class="snrg-credit-chip" style="border-left:4px solid #0d6efd;">
          <div class="snrg-chip-title">⏳ Credit Approval Pending</div>
          <div class="snrg-chip-row">
            <span>Order Value</span><span>${fmt(amt)}</span>
          </div>
          <div class="snrg-chip-row">
            <span>Requested On</span>
            <span>${frappe.datetime.str_to_user(frm.doc.custom_snrg_request_time)}</span>
          </div>
          <div class="snrg-chip-note">Awaiting approval from Credit Control Team.</div>
        </div>`);
      return;
    }

    // ── Case 2: No override set ────────────────────────────────────────────
    if (!cap || !till) return;

    const today     = frappe.datetime.get_today();
    const isValid   = frappe.datetime.get_diff(till, today) >= 0;
    const tillUser  = frappe.datetime.str_to_user(till);
    const headroom  = Math.max(0, cap - amt);
    const deficit   = Math.max(0, amt - cap);
    const pct       = Math.min(100, Math.round((amt / cap) * 100));
    const isOver    = amt > cap;
    const barColor  = isOver ? "#dc3545" : "#28a745";

    const progressBar = `
      <div style="height:6px;background:rgba(128,128,128,0.25);
        border-radius:3px;overflow:hidden;margin:6px 0 10px;">
        <div style="width:${pct}%;height:100%;background:${barColor};transition:width 0.3s;"></div>
      </div>`;

    let borderColor, icon, title, rows;

    if (isValid && !isOver) {
      // ✅ Approved and within limit
      borderColor = "#28a745"; icon = "✅"; title = "Approved Credit Limit Active";
      rows = [
        ["Approved Cap",         fmt(cap)],
        ["Order Value",          fmt(amt)],
        ["Available Headroom",   `<b>${fmt(headroom)}</b>`],
        ["Valid Till",           tillUser],
      ];
    } else if (!isValid) {
      // ⚠️ Expired
      borderColor = "#ffc107"; icon = "⚠️"; title = "Credit Approval Expired";
      rows = [
        ["Approved Cap",         fmt(cap)],
        ["Order Value",          fmt(amt)],
        [isOver ? "Exceeded By" : "Headroom", `<b>${fmt(isOver ? deficit : headroom)}</b>`],
        ["Expired On",           tillUser],
      ];
    } else {
      // 🚫 Over limit
      borderColor = "#dc3545"; icon = "🚫"; title = "Credit Limit Exceeded";
      rows = [
        ["Approved Cap",         fmt(cap)],
        ["Order Value",          fmt(amt)],
        ["Exceeded By",          `<b>${fmt(deficit)}</b>`],
        ["Valid Till",           tillUser],
      ];
    }

    const body = rows.map(([label, value]) => {
      const isHighlight = label.startsWith("Available") || label.startsWith("Exceeded");
      return isHighlight
        ? `<div class="snrg-chip-row snrg-chip-highlight">
             <span style="text-transform:uppercase;">${label}</span>
             <span style="font-size:13.5px;">${value}</span>
           </div>`
        : label === "Valid Till" || label === "Expired On"
        ? `<div style="margin-top:6px;"></div>
           <div class="snrg-chip-row">
             <span>${label}</span><span style="opacity:.85;">${value}</span>
           </div>`
        : `<div class="snrg-chip-row">
             <span style="width:55%;display:inline-block;">${label}</span>
             <span>${value}</span>
           </div>`;
    }).join("");

    _set_chip(frm, `
      <div class="snrg-credit-chip" style="border-left:4px solid ${borderColor};">
        <div class="snrg-chip-title">${icon} ${title}</div>
        ${progressBar}
        ${body}
      </div>`);
  } catch (e) {
    console.warn("[SNRG Credit Chip] render error:", e);
  }
}

function _set_chip(frm, html) {
  frm.dashboard.set_headline(html);
  const box = frm.dashboard.wrapper.find(".dashboard-headline");
  box.css({ background: "transparent", padding: "0", "box-shadow": "none", border: "none" });
}


// =============================================================================
// 2. FORM EVENTS
// =============================================================================

frappe.ui.form.on("Sales Order", {

  refresh(frm) {
    render_credit_chip(frm);
    _add_credit_buttons(frm);
  },

  // Re-render chip when any relevant field changes
  custom_snrg_override_cap_amount: (frm) => render_credit_chip(frm),
  custom_snrg_override_valid_till:  (frm) => render_credit_chip(frm),
  custom_snrg_request_time:         (frm) => render_credit_chip(frm),
  custom_credit_approval_status:    (frm) => render_credit_chip(frm),
  grand_total:                      (frm) => render_credit_chip(frm),
  rounded_total:                    (frm) => render_credit_chip(frm),
});

function _add_credit_buttons(frm) {
  if (frm.doc.docstatus !== 0) return;   // Draft only

  const isApprover = frappe.user.has_role("Credit Approver") ||
                     frappe.user.has_role("System Manager");
  const hasRequest = !!frm.doc.custom_snrg_request_time;

  // "Request Approval" — visible to everyone on a draft
  frm.add_custom_button("Request Approval", () => open_request_dialog(frm), "Credit Control");

  // "Approve Credit" — only for Credit Approvers when a request exists
  if (isApprover && hasRequest) {
    frm.add_custom_button("Approve Credit", () => open_approve_dialog(frm), "Credit Control");
  }
}


// =============================================================================
// 3. REQUEST APPROVAL DIALOG  (structured PTP)
// =============================================================================

function open_request_dialog(frm) {
  const d = new frappe.ui.Dialog({
    title: "Request Credit Approval",
    fields: [
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
        default: frm.doc.grand_total || frm.doc.rounded_total || 0,
        description: "Amount the customer has committed to pay",
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
    primary_action(values) {
      try {
        const now = frappe.datetime.now_datetime();
        const amt = frm.doc.grand_total || frm.doc.rounded_total || 0;

        // Stamp request fields
        frm.doc.custom_snrg_request_time   = now;
        frm.doc.custom_snrg_request_amount = amt;

        // Add a new PTP entry row
        const row = frappe.model.add_child(frm.doc, "Credit PTP Entry", "custom_snrg_ptp_entries");
        row.ptp_by           = values.ptp_by;
        row.ptp_date         = values.ptp_date;
        row.commitment_date  = values.commitment_date;
        row.committed_amount = values.committed_amount;
        row.payment_mode     = values.payment_mode;
        row.cheque_number    = values.cheque_number || "";
        row.remarks          = values.remarks || "";
        row.status           = "Pending";
        frm.refresh_field("custom_snrg_ptp_entries");

        frm.dirty();
        d.set_message("Saving and sending request…");

        frm.save()
          .then(() => {
            d.hide();
            frappe.show_alert({ message: "Approval request sent to Credit Control team.", indicator: "green" });
            frm.reload_doc();
          })
          .catch((err) => {
            console.error("[SNRG] Request save error", err);
            frappe.msgprint({
              title: "Failed to send request",
              message: (err && (err.message || err._server_messages)) || "Unknown error",
              indicator: "red",
            });
          });
      } catch (e) {
        console.error("[SNRG] Request dialog exception", e);
        frappe.msgprint({ title: "Error", message: (e && e.message) || String(e), indicator: "red" });
      }
    },
  });
  d.show();
}


// =============================================================================
// 4. APPROVE CREDIT DIALOG  (cap + validity confirmation for Credit Approvers)
// =============================================================================

function open_approve_dialog(frm) {
  const reqAmt = Number(frm.doc.custom_snrg_request_amount || 0);
  const soAmt  = Number(frm.doc.grand_total || frm.doc.rounded_total || 0);
  const defaultCap  = Math.min(reqAmt || soAmt, soAmt);
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
        await frm.set_value("custom_snrg_override_valid_till",  values.valid_till);
        await frm.set_value("custom_snrg_approver",             frappe.session.user);
        await frm.set_value("custom_snrg_approval_time",        frappe.datetime.now_datetime());
        await frm.set_value("custom_credit_approval_status",    "Approved");
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


// =============================================================================
// 5. CSS — chip styles + fadeIn animation
// =============================================================================

(function _inject_styles() {
  if (document.getElementById("snrg-credit-chip-styles")) return;
  const style = document.createElement("style");
  style.id = "snrg-credit-chip-styles";
  style.innerHTML = `
    @keyframes snrgFadeIn {
      from { opacity:0; transform:translateY(-2px); }
      to   { opacity:1; transform:translateY(0); }
    }
    .snrg-credit-chip {
      font-size: 13px;
      line-height: 1.5;
      border-radius: 6px;
      padding: 10px 14px;
      background: rgba(255,255,255,0.02);
      box-shadow: 0 0 2px rgba(0,0,0,0.2);
      opacity: 0;
      animation: snrgFadeIn 0.25s ease forwards;
    }
    .snrg-chip-title {
      font-weight: 600;
      margin-bottom: 6px;
    }
    .snrg-chip-row {
      display: flex;
      justify-content: space-between;
      margin: 2px 0;
    }
    .snrg-chip-highlight {
      font-weight: 600;
      margin: 4px 0 6px;
    }
    .snrg-chip-note {
      margin-top: 8px;
      font-size: 12.5px;
      opacity: 0.85;
    }
  `;
  document.head.appendChild(style);
}());
