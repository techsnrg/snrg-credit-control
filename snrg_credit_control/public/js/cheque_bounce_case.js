frappe.ui.form.on("Cheque Bounce Case", {
  refresh(frm) {
    frm.remove_custom_button("Mark to Legal");
    frm.remove_custom_button("Open Legal Case");

    if (frm.doc.legal_case) {
      frm.add_custom_button("Open Legal Case", function () {
        frappe.set_route("Form", "Legal Case", frm.doc.legal_case);
      }).addClass("btn-primary");
      return;
    }

    frm.add_custom_button("Mark to Legal", function () {
      frappe.call({
        method: "snrg_credit_control.legal_case.create_or_open_legal_case_from_cheque_bounce",
        args: { cheque_bounce_case: frm.doc.name },
        freeze: true,
        freeze_message: "Opening legal case...",
        callback(r) {
          if (!r.message || !r.message.name) return;
          frm.reload_doc().then(() => {
            frappe.set_route("Form", "Legal Case", r.message.name);
          });
        },
      });
    });
  },
});
