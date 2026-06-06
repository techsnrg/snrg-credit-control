const SNRG_FULFILLMENT_FIELDS = [
  "custom_shipping_date",
  "custom_awb_number",
  "custom_no_of_cartons",
  "custom_delivery_status",
  "custom_delivery_date",
  "custom_pod_attachment",
  "custom_dispatch_delivery_remarks",
];

const SNRG_FULFILLMENT_ROLE = "Fulfillment User";
const SNRG_SYSTEM_MANAGER_ROLE = "System Manager";

function snrg_show_minimum_rate_check() {
  frappe.show_alert({
    message: "Checking minimum selling rates...",
    indicator: "blue",
  }, 8);
}

function snrg_hide_minimum_rate_check() {
  // Non-blocking alert auto-dismisses.
}

frappe.ui.form.on("Sales Invoice", {
  refresh(frm) {
    toggle_fulfillment_fields_read_only(frm);
    refresh_scheme_suggestions(frm);

    if (frm.doc.docstatus === 0) {
      frm.add_custom_button("Check Scheme Suggestions", () => refresh_scheme_suggestions(frm, true), "Schemes");
    }

    if (frm.doc.docstatus !== 1) return;
    if (!can_use_fulfillment_update()) return;

    frm.add_custom_button("Update Fulfillment Details", () => {
      open_fulfillment_update_dialog(frm);
    });
  },
  before_save() {
    snrg_show_minimum_rate_check();
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
  posting_date(frm) {
    refresh_scheme_suggestions(frm);
  },
  customer(frm) {
    refresh_scheme_suggestions(frm);
  },
  items_add(frm) {
    refresh_scheme_suggestions(frm);
  },
  items_remove(frm) {
    refresh_scheme_suggestions(frm);
  },
});

frappe.ui.form.on("Sales Invoice Item", {
  item_code(frm) {
    refresh_scheme_suggestions(frm);
  },
  qty(frm) {
    refresh_scheme_suggestions(frm);
  },
  rate(frm) {
    refresh_scheme_suggestions(frm);
  },
  discount_percentage(frm) {
    refresh_scheme_suggestions(frm);
  },
  discount_amount(frm) {
    refresh_scheme_suggestions(frm);
  },
});

function can_use_fulfillment_update() {
  return frappe.user_roles.includes(SNRG_FULFILLMENT_ROLE)
    || frappe.user_roles.includes(SNRG_SYSTEM_MANAGER_ROLE);
}

function toggle_fulfillment_fields_read_only(frm) {
  const lockDirectEditing = frm.doc.docstatus === 1
    && frappe.user_roles.includes(SNRG_FULFILLMENT_ROLE)
    && !frappe.user_roles.includes(SNRG_SYSTEM_MANAGER_ROLE);

  SNRG_FULFILLMENT_FIELDS.forEach((fieldname) => {
    frm.set_df_property(fieldname, "read_only", lockDirectEditing ? 1 : 0);
  });
}

function open_fulfillment_update_dialog(frm) {
  try {
    const dialog = new frappe.ui.Dialog({
      title: "Update Fulfillment Details",
      fields: [
        {
          fieldname: "custom_shipping_date",
          fieldtype: "Date",
          label: "Shipping Date",
          default: frm.doc.custom_shipping_date || "",
        },
        {
          fieldname: "custom_awb_number",
          fieldtype: "Data",
          label: "AWB Number",
          default: frm.doc.custom_awb_number || "",
        },
        {
          fieldname: "custom_no_of_cartons",
          fieldtype: "Int",
          label: "No. of Cartons",
          default: frm.doc.custom_no_of_cartons || "",
        },
        {
          fieldname: "custom_delivery_status",
          fieldtype: "Select",
          label: "Delivery Status",
          options: get_delivery_status_options(frm),
          default: frm.doc.custom_delivery_status || "",
        },
        {
          fieldname: "custom_delivery_date",
          fieldtype: "Date",
          label: "Delivery Date",
          default: frm.doc.custom_delivery_date || "",
        },
        {
          fieldname: "custom_pod_attachment",
          fieldtype: "Attach",
          label: "POD Attachment",
          default: frm.doc.custom_pod_attachment || "",
        },
        {
          fieldname: "custom_dispatch_delivery_remarks",
          fieldtype: "Small Text",
          label: "Dispatch / Delivery Remarks",
          default: frm.doc.custom_dispatch_delivery_remarks || "",
        },
      ],
      primary_action_label: "Update",
      primary_action: async () => {
        const values = dialog.get_values();
        if (!values) return;

        try {
          const { message } = await frappe.call({
            method: "snrg_credit_control.overrides.sales_invoice.update_fulfillment_details",
            args: {
              name: frm.doc.name,
              values,
            },
            freeze: true,
            freeze_message: "Updating fulfillment details...",
          });

          dialog.hide();
          await frm.reload_doc();

          frappe.show_alert({
            message: (message && message.message) || "Fulfillment details updated.",
            indicator: "green",
          });
        } catch (error) {
          frappe.msgprint({
            title: "Update failed",
            message: (error && error.message) || String(error),
            indicator: "red",
          });
        }
      },
    });

    dialog.show();
  } catch (error) {
    frappe.msgprint({
      title: "Dialog failed",
      message: (error && error.message) || String(error),
      indicator: "red",
    });
    console.error("[SNRG Fulfillment] dialog error", error);
  }
}

function get_delivery_status_options(frm) {
  return (
    frm.get_field("custom_delivery_status")?.df?.options
    || frappe.meta.get_docfield(frm.doctype, "custom_delivery_status", frm.doc.name)?.options
    || "\nPending\nIn Transit\nDelivered\nPartially Delivered\nReturned\nHold"
  );
}

let snrg_scheme_refresh_timer = null;

function refresh_scheme_suggestions(frm, show_dialog = false) {
  if (!frm || frm.doc.docstatus !== 0) return;

  clearTimeout(snrg_scheme_refresh_timer);
  snrg_scheme_refresh_timer = setTimeout(() => {
    fetch_scheme_suggestions(frm, show_dialog);
  }, show_dialog ? 0 : 500);
}

async function fetch_scheme_suggestions(frm, show_dialog = false) {
  try {
    const { message } = await frappe.call({
      method: "snrg_credit_control.scheme_engine.evaluate_sales_invoice_schemes",
      args: { doc: frm.doc },
    });

    if (!message) {
      clear_scheme_headline(frm);
      if (show_dialog) {
        frappe.msgprint({
          title: "Scheme Suggestions",
          message: "No active SNRG Scheme applies to the current invoice items.",
          indicator: "orange",
        });
      }
      return;
    }

    render_scheme_headline(frm, message);
    if (show_dialog) open_scheme_suggestions_dialog(message);
  } catch (error) {
    console.error("[SNRG Schemes] suggestion refresh failed", error);
    if (show_dialog) {
      frappe.msgprint({
        title: "Scheme Check Failed",
        message: (error && error.message) || String(error),
        indicator: "red",
      });
    }
  }
}

function render_scheme_headline(frm, scheme) {
  if (!frm || !frm.dashboard || !frm.dashboard.set_headline || !scheme) return;

  const hasEligibleAmount = flt(scheme.eligible_amount) > 0;
  if (!hasEligibleAmount) {
    clear_scheme_headline(frm);
    return;
  }

  const achieved = (scheme.achieved_slabs || []).map((slab) => slab.reward).join(", ");
  const nextSlab = scheme.next_slab;
  const status = !scheme.is_in_period
    ? `<span class="indicator-pill red">Outside Scheme Period</span>`
    : achieved
      ? `<span class="indicator-pill green">Eligible: ${frappe.utils.escape_html(achieved)}</span>`
      : `<span class="indicator-pill orange">Not Yet Eligible</span>`;

  const nextText = nextSlab
    ? `Short by ${format_currency(scheme.shortfall_amount)} for ${frappe.utils.escape_html(nextSlab.reward)}`
    : "Highest slab achieved";

  frm.dashboard.set_headline(`
    <div class="snrg-scheme-headline">
      <div><strong>${frappe.utils.escape_html(scheme.scheme_name)}</strong> ${status}</div>
      <div>Eligible pre-GST value: <strong>${format_currency(scheme.eligible_amount)}</strong>. ${nextText}.</div>
    </div>
  `);
}

function clear_scheme_headline(frm) {
  if (!frm || !frm.dashboard || !frm.dashboard.wrapper) return;

  const headline = frm.dashboard.wrapper.find(".dashboard-headline");
  if (!headline.find(".snrg-scheme-headline").length) return;

  if (frm.dashboard.clear_headline) {
    frm.dashboard.clear_headline();
  } else {
    headline.empty();
  }
}

function open_scheme_suggestions_dialog(scheme) {
  if (!scheme) return;

  const achievedRows = (scheme.achieved_slabs || []).map((slab) => `
    <tr>
      <td>${format_currency(slab.amount)}</td>
      <td>${frappe.utils.escape_html(slab.reward || "")}</td>
    </tr>
  `).join("") || `<tr><td colspan="2">No slab achieved yet.</td></tr>`;

  const suggestionRows = (scheme.suggestions || []).map((row) => `
    <tr>
      <td>${frappe.utils.escape_html(row.item_code || "")}</td>
      <td class="text-right">${format_number(row.current_qty)}</td>
      <td class="text-right">${format_number(row.extra_qty)}</td>
      <td class="text-right">${format_number(row.new_qty)}</td>
      <td>${frappe.utils.escape_html(row.reward || "")}</td>
    </tr>
  `).join("") || `<tr><td colspan="5">No quantity suggestion available. Add an eligible plate item with a valid rate.</td></tr>`;

  const periodWarning = scheme.is_in_period ? "" : `
    <p class="text-danger">
      Invoice date ${frappe.utils.escape_html(scheme.posting_date || "")} is outside the scheme period
      ${frappe.utils.escape_html(scheme.valid_from)} to ${frappe.utils.escape_html(scheme.valid_upto)}.
    </p>
  `;

  frappe.msgprint({
    title: scheme.scheme_name,
    indicator: scheme.is_in_period ? "blue" : "orange",
    wide: true,
    message: `
      ${periodWarning}
      <p>
        Eligible pre-GST plate value:
        <strong>${format_currency(scheme.eligible_amount)}</strong>
      </p>
      <h5>Achieved Rewards</h5>
      <table class="table table-bordered table-condensed">
        <thead><tr><th>Slab</th><th>Reward</th></tr></thead>
        <tbody>${achievedRows}</tbody>
      </table>
      <h5>Suggestions for Next Slab</h5>
      <table class="table table-bordered table-condensed">
        <thead>
          <tr>
            <th>Item</th>
            <th class="text-right">Current Qty</th>
            <th class="text-right">Add Qty</th>
            <th class="text-right">New Qty</th>
            <th>Target Reward</th>
          </tr>
        </thead>
        <tbody>${suggestionRows}</tbody>
      </table>
      <p class="text-muted">${frappe.utils.escape_html((scheme.notes || []).join(" "))}</p>
    `,
  });
}
