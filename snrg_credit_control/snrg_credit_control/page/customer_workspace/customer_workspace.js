frappe.pages["customer-workspace"].on_page_load = function(wrapper) {
  wrapper.classList.add("snrg-customer-workspace-page");
  const page = frappe.ui.make_app_page({parent: wrapper, title: __("Teamspace"), single_column: true});
  frappe.require(["/assets/snrg_credit_control/dist/customer_workspace.21f796ce826a.css", "/assets/snrg_credit_control/dist/customer_workspace.b2b561dc4efb.js"], () => window.snrgCustomerWorkspace.mount(page.main[0]));
};
