frappe.pages["scheme-planning"].on_page_load = function (wrapper) {
  frappe.require("/assets/snrg_credit_control/js/scheme_planning_view.js", () => {
    const page = frappe.ui.make_app_page({
      parent: wrapper,
      title: "Amount Scheme Planning",
      single_column: true,
    });

    wrapper.scheme_planning = new SnrgSchemePlanningView(page, wrapper, {
      title: "Amount Scheme Planning",
      method: "snrg_credit_control.scheme_engine.get_amount_scheme_customer_progress",
      schemeTypeFilter: "Period Cumulative Amount Slab",
      mode: "amount",
    });
  });
};

frappe.pages["scheme-planning"].on_page_show = function (wrapper) {
  wrapper.scheme_planning?.set_breadcrumb();
};
