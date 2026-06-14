frappe.ui.form.on("Customer", {
  refresh(frm) {
    addRecommendedRefreshButton(frm);
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
