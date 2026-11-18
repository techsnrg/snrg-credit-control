frappe.pages["customer-workspace"].on_page_load = function(wrapper) {
  wrapper.classList.add("snrg-customer-workspace-page");
  const page = frappe.ui.make_app_page({parent: wrapper, title: __("Customer Workspace"), single_column: true});
  frappe.require(["/assets/snrg_credit_control/dist/customer_workspace.db848d95312d.css", "/assets/snrg_credit_control/dist/customer_workspace.47330461bb22.js"], () => window.snrgCustomerWorkspace.mount(page.main[0]));
};
