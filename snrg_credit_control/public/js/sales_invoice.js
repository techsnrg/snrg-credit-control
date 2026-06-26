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

function snrg_show_minimum_rate_check(frm) {
  if (frm && Number(frm.doc.is_return || 0) === 1) return;

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
    render_pod_attachment_link(frm);
    if (frm.doc.docstatus !== 1) return;
    if (!can_use_fulfillment_update()) return;

    frm.add_custom_button("Update Fulfillment Details", () => {
      open_fulfillment_update_dialog(frm);
    });
  },
  before_save(frm) {
    snrg_show_minimum_rate_check(frm);
  },
  after_save() {
    snrg_hide_minimum_rate_check();
  },
  before_submit(frm) {
    snrg_show_minimum_rate_check(frm);
  },
  on_submit() {
    snrg_hide_minimum_rate_check();
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

async function render_pod_attachment_link(frm) {
  remove_pod_attachment_link(frm);

  if (!frm.doc.custom_pod_attachment) return;
  if (!frm.attachments?.parent) return;
  if (has_native_pod_attachment(frm)) return;

  try {
    const { message } = await frappe.call({
      method: "snrg_credit_control.overrides.sales_invoice.get_pod_preview",
      args: { name: frm.doc.name },
    });

    if (!message?.preview_url) return;

    insert_pod_attachment_link(frm, message);
  } catch (error) {
    console.warn("[SNRG POD] Unable to render POD attachment link", error);
  }
}

function remove_pod_attachment_link(frm) {
  frm.attachments?.parent?.find(".snrg-pod-attachment-row").remove();
}

function has_native_pod_attachment(frm) {
  const targetUrl = normalize_attachment_url(frm.doc.custom_pod_attachment);
  if (!targetUrl) return false;

  return (frm.get_docinfo()?.attachments || []).some((attachment) => {
    return normalize_attachment_url(attachment.file_url) === targetUrl;
  });
}

function normalize_attachment_url(url) {
  return encodeURI((url || "").trim());
}

function insert_pod_attachment_link(frm, preview) {
  const fileName = preview.file_name || "POD Attachment";
  const fileUrl = frappe.utils.escape_html(preview.preview_url || "");
  const icon = `
    <a href="${fileUrl}" target="_blank" rel="noopener noreferrer" class="attachment-icon">
      ${frappe.utils.icon(preview.is_private ? "es-line-lock" : "es-line-unlock", "sm ml-0")}
    </a>
  `;
  const fileLabel = `
    <a href="${fileUrl}" target="_blank" rel="noopener noreferrer" title="${frappe.utils.escape_html(fileName)}"
      class="ellipsis attachment-file-label ellipsis-width"
    >
      <span>${frappe.utils.xss_sanitise(fileName)}</span>
    </a>
  `;
  const $row = $('<div class="attachment-row snrg-pod-attachment-row"></div>')
    .append(frappe.get_data_pill(fileLabel, `snrg-pod-${frm.doc.name}`, null, icon));
  const $rows = frm.attachments.parent.find(".attachment-row");

  if ($rows.length) {
    $row.insertAfter($rows.last());
    return;
  }

  $row.insertAfter(frm.attachments.add_attachment_wrapper);
}
