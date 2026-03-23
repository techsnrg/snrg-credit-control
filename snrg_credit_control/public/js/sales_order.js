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
    const fmt    = v => frappe.format(v, { fieldtype: "Currency", options: cur });
    const hasReq = !!frm.doc.custom_snrg_request_time;

    // ── Building blocks ────────────────────────────────────────────────────
    // Pill badge (flex works in dashboard headline area)
    const pill = (text, rgb) =>
      `<span style="background:rgba(${rgb},.18);border:1px solid rgba(${rgb},.45);
        color:rgba(${rgb},1);font-size:10px;font-weight:800;letter-spacing:1.2px;
        text-transform:uppercase;padding:3px 12px;border-radius:20px;
        white-space:nowrap;vertical-align:middle;">${text}</span>`;

    // Metric column — inline-block (100% reliable, no flex/grid needed)
    const stat = (label, value, valCss, w) =>
      `<div style="display:inline-block;vertical-align:top;width:${w};padding-right:12px;box-sizing:border-box;">
        <div style="font-size:10px;font-weight:700;letter-spacing:1.1px;text-transform:uppercase;
          opacity:.45;margin-bottom:4px;">${label}</div>
        <div style="${valCss}">${value}</div>
      </div>`;

    // Progress bar
    const bar = (pct, rgb) =>
      `<div style="height:4px;background:rgba(255,255,255,.1);border-radius:3px;
        overflow:hidden;margin:10px 0 4px;">
        <div style="width:${pct}%;height:100%;background:rgba(${rgb},1);border-radius:3px;"></div>
      </div>
      <div style="font-size:10px;letter-spacing:.5px;opacity:.35;text-align:right;
        margin-bottom:12px;">${pct}% OF CAP USED</div>`;

    // Outer card wrapper
    const card = (rgb, content) =>
      `<div style="border:1px solid rgba(${rgb},.22);border-left:4px solid rgba(${rgb},1);
        border-radius:0 8px 8px 0;padding:16px 20px;
        background:rgba(${rgb},.06);
        box-shadow:0 2px 12px rgba(0,0,0,.2);
        opacity:0;animation:snrgFadeIn .3s ease forwards;
        font-family:inherit;line-height:1.4;">${content}</div>`;

    const L18 = 'font-size:18px;font-weight:800;letter-spacing:-.5px;';
    const L15 = 'font-size:15px;font-weight:700;';
    const L13 = 'font-size:13px;font-weight:600;opacity:.75;';
    const hr  = rgb => `<div style="border-top:1px solid rgba(${rgb},.15);margin:13px 0 11px;"></div>`;

    // ── PENDING ────────────────────────────────────────────────────────────
    if (hasReq && !cap) {
      _set_chip(frm, card('59,130,246', `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
          <span style="font-size:13px;font-weight:700;">⏳ &nbsp;Credit Approval Pending</span>
          ${pill('Awaiting Review', '147,197,253')}
        </div>
        <div>
          ${stat('Order Value', fmt(amt), L18, '50%')}
          ${stat('Requested On', frappe.datetime.str_to_user(frm.doc.custom_snrg_request_time), L13, '50%')}
        </div>
        ${hr('59,130,246')}
        <div style="font-size:11px;opacity:.4;letter-spacing:.2px;">
          📬 &nbsp;Sent to Credit Approver — awaiting review
        </div>`));
      return;
    }

    if (!cap || !till) return;

    const today    = frappe.datetime.get_today();
    const isValid  = frappe.datetime.get_diff(till, today) >= 0;
    const daysLeft = frappe.datetime.get_diff(till, today);
    const tillFmt  = frappe.datetime.str_to_user(till);
    const headroom = Math.max(0, cap - amt);
    const deficit  = Math.max(0, amt - cap);
    const pct      = Math.min(100, Math.round((amt / cap) * 100));
    const isOver   = amt > cap;

    if (isValid && !isOver) {
      // ✅ Active approval
      _set_chip(frm, card('34,197,94', `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
          <span style="font-size:13px;font-weight:700;">✅ &nbsp;Credit Approved — Active</span>
          ${pill(daysLeft === 0 ? 'Expires Today' : daysLeft + 'd Remaining', '74,222,128')}
        </div>
        ${bar(pct, '34,197,94')}
        <div>
          ${stat('Approved Cap', fmt(cap), L13, '28%')}
          ${stat('Order Value', fmt(amt), L13, '28%')}
          ${stat('Headroom', fmt(headroom), 'font-size:20px;font-weight:800;color:#4ade80;', '44%')}
        </div>
        <div style="font-size:10px;opacity:.3;margin-top:10px;letter-spacing:.5px;text-transform:uppercase;">
          Valid till &nbsp;${tillFmt}
        </div>`));

    } else if (!isValid) {
      // ⚠️ Expired
      _set_chip(frm, card('249,115,22', `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
          <span style="font-size:13px;font-weight:700;">⚠️ &nbsp;Credit Approval Expired</span>
          ${pill('Expired', '251,146,60')}
        </div>
        <div>
          ${stat('Approved Cap', fmt(cap), L15, '28%')}
          ${stat('Order Value', fmt(amt), L15, '28%')}
          ${stat('Expired On', tillFmt, 'font-size:13px;font-weight:600;color:#fb923c;', '44%')}
        </div>
        ${hr('249,115,22')}
        <div style="font-size:11px;opacity:.4;">
          ⚡ &nbsp;Use Credit Control → Request Approval to renew
        </div>`));

    } else {
      // 🚫 Over cap
      _set_chip(frm, card('239,68,68', `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
          <span style="font-size:13px;font-weight:700;">🚫 &nbsp;Order Exceeds Approved Cap</span>
          ${pill('Over Cap', '248,113,113')}
        </div>
        ${bar(pct, '239,68,68')}
        <div>
          ${stat('Approved Cap', fmt(cap), L13, '28%')}
          ${stat('Order Value', fmt(amt), 'font-size:15px;font-weight:700;color:#f87171;', '28%')}
          ${stat('Exceeds By', fmt(deficit), 'font-size:20px;font-weight:800;color:#f87171;', '44%')}
        </div>
        <div style="font-size:10px;opacity:.3;margin-top:10px;letter-spacing:.5px;text-transform:uppercase;">
          Valid till &nbsp;${tillFmt} — cap must be increased
        </div>`));
    }
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

  const isApprover = frappe.user.has_role("Credit Approver");
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
