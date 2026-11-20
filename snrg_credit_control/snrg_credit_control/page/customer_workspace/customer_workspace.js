frappe.pages["customer-workspace"].on_page_load = function(wrapper) {
  wrapper.classList.add("snrg-customer-workspace-page");
  const page = frappe.ui.make_app_page({parent: wrapper, title: __("Teamspace"), single_column: true});
  frappe.require(["/assets/snrg_credit_control/dist/customer_workspace.c958dcb778dd.css", "/assets/snrg_credit_control/dist/customer_workspace.7170ec814f90.js"], () => window.snrgCustomerWorkspace.mount(page.main[0]));
};
