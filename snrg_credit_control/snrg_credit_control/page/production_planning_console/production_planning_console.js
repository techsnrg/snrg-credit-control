frappe.pages["production-planning-console"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Production Planning Console"),
    single_column: true,
  });

  wrapper.page = page;

  if (frappe.boot.developer_mode) {
    frappe.hot_update = frappe.hot_update || [];
    frappe.hot_update.push(() => load_production_planning_console(wrapper));
  }
};

frappe.pages["production-planning-console"].on_page_show = function (wrapper) {
  load_production_planning_console(wrapper);
};

function load_production_planning_console(wrapper) {
  set_production_planning_console_breadcrumb();

  const $parent = $(wrapper).find(".layout-main-section");
  $parent.empty();

  frappe.require("production_planning_console.bundle.js").then(() => {
    if (wrapper.__snrgProductionPlanningConsole?.destroy) {
      wrapper.__snrgProductionPlanningConsole.destroy();
    }

    wrapper.__snrgProductionPlanningConsole = new frappe.ui.SnrgProductionPlanningConsole({
      wrapper: $parent,
      page: wrapper.page,
      routeOptions: Object.assign({}, frappe.route_options || {}),
    });

    frappe.route_options = null;
  });
}

function set_production_planning_console_breadcrumb() {
  if (frappe.breadcrumbs) {
    try {
      frappe.breadcrumbs.clear?.();
      frappe.breadcrumbs.add("Stock");
    } catch (error) {
      // Breadcrumb behavior differs slightly across Frappe versions.
    }
  }

  const updateLabel = () => {
    $(".breadcrumb-container a, .breadcrumbs a, .page-head a").each((_, element) => {
      const link = $(element);
      const text = link.text().trim();
      if (text === "Selling" || text === "Credit Control") {
        link.text("Stock");
        link.attr("href", "/app/stock");
      }
    });
  };

  setTimeout(updateLabel, 50);
  setTimeout(updateLabel, 250);
}
