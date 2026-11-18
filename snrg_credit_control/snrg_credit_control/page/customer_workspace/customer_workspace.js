frappe.pages["customer-workspace"].on_page_load = function(wrapper) {
  wrapper.classList.add("snrg-customer-workspace-page");
  const page = frappe.ui.make_app_page({parent: wrapper, title: __("Teamspace"), single_column: true});
  frappe.require(["/assets/snrg_credit_control/dist/customer_workspace.7e1db5b05bcf.css", "/assets/snrg_credit_control/dist/customer_workspace.69ca648272b8.js"], () => window.snrgCustomerWorkspace.mount(page.main[0]));
};
