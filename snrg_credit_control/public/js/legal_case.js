frappe.ui.form.on("Legal Case", {
  refresh(frm) {
    frm.remove_custom_button("Create Demand Notice");
    frm.remove_custom_button("Open Demand Notice");

    if (frm.doc.demand_notice) {
      frm.add_custom_button("Open Demand Notice", function () {
        frappe.set_route("Form", "Demand Notice", frm.doc.demand_notice);
      }).addClass("btn-primary");
      return;
    }

    frm.add_custom_button("Create Demand Notice", function () {
      frappe.call({
        method: "snrg_credit_control.legal_case.create_demand_notice_from_legal_case",
        args: { legal_case: frm.doc.name },
        freeze: true,
        freeze_message: "Creating demand notice...",
        callback(r) {
          if (!r.message || !r.message.name) return;
          frm.reload_doc().then(() => {
            frappe.set_route("Form", "Demand Notice", r.message.name);
          });
        },
      });
    });
  },
});
