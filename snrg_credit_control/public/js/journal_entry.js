frappe.ui.form.on("Journal Entry", {
  refresh(frm) {
    frm.remove_custom_button("Create Cheque Bounce Case");
    frm.remove_custom_button("Open Cheque Bounce Case");

    if (frm.is_new()) {
      return;
    }

    if (frm.doc.custom_cheque_bounce_case) {
      frm.add_custom_button("Open Cheque Bounce Case", function () {
        frappe.set_route("Form", "Cheque Bounce Case", frm.doc.custom_cheque_bounce_case);
      });
      return;
    }

    if (!frm.doc.custom_is_cheque_bounce) {
      return;
    }

    frm.add_custom_button("Create Cheque Bounce Case", function () {
      frappe.call({
        method: "snrg_credit_control.cheque_bounce.create_or_open_cheque_bounce_case",
        args: {
          journal_entry: frm.doc.name,
        },
        freeze: true,
        freeze_message: "Creating cheque bounce case...",
        callback(r) {
          if (!r.message || !r.message.name) {
            return;
          }
          frm.reload_doc().then(() => {
            frappe.set_route("Form", "Cheque Bounce Case", r.message.name);
          });
        },
      });
    }).addClass("btn-primary");
  },
});
