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

frappe.ui.form.on("Sales Invoice", {
  refresh(frm) {
    toggle_fulfillment_fields_read_only(frm);
    if (frm.doc.docstatus !== 1) return;
    if (!can_use_fulfillment_update()) return;

    frm.add_custom_button("Update Fulfillment Details", () => {
      open_fulfillment_update_dialog(frm);
    }, "Fulfillment");
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
  const deliveryStatusField = frm.meta.get_field("custom_delivery_status") || {};
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
        options: deliveryStatusField.options || "\nPending\nIn Transit\nDelivered\nPartially Delivered\nReturned\nHold",
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
}
