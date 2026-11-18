frappe.pages["customer-workspace"].on_page_load = function(wrapper) {
  wrapper.classList.add("snrg-customer-workspace-page");
  const page = frappe.ui.make_app_page({parent: wrapper, title: __("Teamspace"), single_column: true});
  frappe.require(["/assets/snrg_credit_control/dist/customer_workspace.00a454780ec4.css", "/assets/snrg_credit_control/dist/customer_workspace.f4aeafc04278.js"], () => window.snrgCustomerWorkspace.mount(page.main[0]));
};
