frappe.ui.form.on("Item Price Request", {
  refresh(frm) {
    set_request_read_only(frm);
    add_approval_buttons(frm);
  },
});

function set_request_read_only(frm) {
  const locked = ["Approved", "Rejected"].includes(frm.doc.status);
  if (!locked) return;

  (frm.meta.fields || []).forEach((field) => {
    if (!field.fieldname) return;
    frm.set_df_property(field.fieldname, "read_only", 1);
  });
}

function add_approval_buttons(frm) {
  if (frm.is_new() || frm.doc.status !== "Pending") return;
  const canApprove = frappe.user_roles.includes("Pricing Approver")
    || frappe.user_roles.includes("System Manager");
  if (!canApprove) return;

  frm.add_custom_button("Approve", () => approve_price_request(frm), "Actions");
  frm.add_custom_button("Reject", () => reject_price_request(frm), "Actions");
}

async function approve_price_request(frm) {
  frappe.confirm(
    "Create the official Item Price from this request?",
    async () => {
      try {
        const { message } = await frappe.call({
          method: "snrg_credit_control.snrg_credit_control.doctype.item_price_request.item_price_request.approve_request",
          args: { name: frm.doc.name },
          freeze: true,
          freeze_message: "Approving item price request...",
        });
        await frm.reload_doc();
        frappe.show_alert({
          message: (message && message.message) || "Item Price created.",
          indicator: "green",
        });
      } catch (error) {
        frappe.msgprint({
          title: "Approval failed",
          message: (error && error.message) || String(error),
          indicator: "red",
        });
      }
    }
  );
}

function reject_price_request(frm) {
  const dialog = new frappe.ui.Dialog({
    title: "Reject Item Price Request",
    fields: [
      {
        fieldname: "rejection_reason",
        fieldtype: "Small Text",
        label: "Rejection Reason",
        reqd: 1,
      },
    ],
    primary_action_label: "Reject",
    primary_action: async () => {
      const values = dialog.get_values();
      if (!values) return;

      try {
        const { message } = await frappe.call({
          method: "snrg_credit_control.snrg_credit_control.doctype.item_price_request.item_price_request.reject_request",
          args: {
            name: frm.doc.name,
            rejection_reason: values.rejection_reason,
          },
          freeze: true,
          freeze_message: "Rejecting item price request...",
        });
        dialog.hide();
        await frm.reload_doc();
        frappe.show_alert({
          message: (message && message.message) || "Item Price Request rejected.",
          indicator: "orange",
        });
      } catch (error) {
        frappe.msgprint({
          title: "Rejection failed",
          message: (error && error.message) || String(error),
          indicator: "red",
        });
      }
    },
  });

  dialog.show();
}
