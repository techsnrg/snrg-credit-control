frappe.pages["scheme-planning"].on_page_load = wrapper => {
  const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Scheme Planning"), single_column: true });
  frappe.require([
    "/assets/snrg_credit_control/customer_workspace/scheme_workspace.css",
    "/assets/snrg_credit_control/customer_workspace/scheme_workspace.js",
  ], () => window.snrgSchemeWorkspace.mount(page.main[0]));
};
