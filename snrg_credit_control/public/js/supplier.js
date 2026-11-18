frappe.ui.form.on('Supplier', {
  refresh(frm) {
    if (!frm.is_new()) frm.add_custom_button(__('Teamspace'), () => {
      frappe.route_options = {supplier: frm.doc.name};
      frappe.set_route('customer-workspace');
    });
  },
});
