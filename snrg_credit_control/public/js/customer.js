frappe.ui.form.on("Customer", {
  refresh(frm) {
    addRecommendedRefreshButton(frm);
    if (!frm.is_new()) frm.add_custom_button(__("Teamspace"), () => {
      frappe.route_options = {customer: frm.doc.name};
      frappe.set_route("customer-workspace");
    });
  },
});

function addRecommendedRefreshButton(frm) {
  frm.remove_custom_button("Refresh Recommended Limits");

  if (frm.is_new()) return;

  frm.add_custom_button("Refresh Recommended Limits", () => {
    frappe.call({
      method: "snrg_credit_control.recommended_credit_limit.refresh_customer_recommended_limits",
      args: { customer: frm.doc.name },
      freeze: true,
      freeze_message: "Refreshing recommended credit limits...",
      callback: (r) => {
        const result = r.message || {};
        const count = (result.updated_rows || []).length;
        frappe.show_alert({
          message: __("{0} company row(s) refreshed.", [count]),
          indicator: "green",
        });
        frm.reload_doc();
      },
    });
  }).addClass("btn-primary");
}

frappe.ui.form.on("Customer", {
  async refresh(frm) {
    if (frm.is_new()) return;
    const name = frm.doc.name;
    const {message: guides} = await frappe.call({
      method: "snrg_credit_control.customer_workspace.knowledge.search",
      args: {reference_doctype: "Customer"},
      type: "GET",
    });
    if (frm.doc.name !== name || !guides?.length) return;
    const open = guide => window.location.assign("/teamspace?guide=" + encodeURIComponent(guide.name));
    if (guides.length === 1) {
      frm.add_custom_button(__("View guide"), () => open(guides[0]));
      return;
    }
    for (const guide of guides) {
      frm.add_custom_button(guide.title, () => open(guide), __("View guide"));
    }
  },
});
