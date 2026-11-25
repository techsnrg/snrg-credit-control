frappe.pages["customer-workspace"].on_page_load = function(wrapper) {
  wrapper.classList.add("snrg-customer-workspace-page");
  const page = frappe.ui.make_app_page({parent: wrapper, title: __("Teamspace"), single_column: true});
  frappe.require(["/assets/snrg_credit_control/dist/customer_workspace.816f6076743c.css", "/assets/snrg_credit_control/dist/customer_workspace.d777829e773e.js"], () => window.snrgCustomerWorkspace.mount(page.main[0]));
};
