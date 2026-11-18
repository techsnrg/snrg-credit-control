frappe.pages["customer-workspace"].on_page_load = function(wrapper) {
  wrapper.classList.add("snrg-customer-workspace-page");
  const page = frappe.ui.make_app_page({parent: wrapper, title: __("Customer Workspace"), single_column: true});
  frappe.require(["/assets/snrg_credit_control/dist/customer_workspace.5fd754a8cc63.css", "/assets/snrg_credit_control/dist/customer_workspace.a3296beac254.js"], () => window.snrgCustomerWorkspace.mount(page.main[0]));
};
