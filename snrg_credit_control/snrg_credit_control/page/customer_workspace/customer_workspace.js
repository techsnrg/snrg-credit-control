frappe.pages["customer-workspace"].on_page_load = function(wrapper) {
  wrapper.classList.add("snrg-customer-workspace-page");
  const page = frappe.ui.make_app_page({parent: wrapper, title: __("Teamspace"), single_column: true});
  frappe.require(["/assets/snrg_credit_control/dist/customer_workspace.a842642f1180.css", "/assets/snrg_credit_control/dist/customer_workspace.51e999aac7f2.js"], () => window.snrgCustomerWorkspace.mount(page.main[0]));
};
