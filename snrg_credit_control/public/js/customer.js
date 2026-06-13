frappe.ui.form.on("Customer", {
  refresh(frm) {
    renderRecommendedSnapshotInfo(frm);
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

function renderRecommendedSnapshotInfo(frm) {
  const field = frm.get_field("custom_snrg_credit_limit_snapshot_info");
  if (!field || !field.$wrapper) return;

  const rows = (frm.doc.credit_limits || []).filter((row) => row.company);
  if (!rows.length) {
    field.$wrapper.html(
      `<div style="padding:8px 0 2px;color:#64748b;font-size:12px;">Add a company row in the Credit Limit table to store the recommended credit limit snapshot.</div>`
    );
    return;
  }

  const snapshotRows = rows.filter((row) => row.custom_snrg_recommended_credit_limit_updated_on);
  if (!snapshotRows.length) {
    field.$wrapper.html(
      `<div style="padding:8px 0 2px;color:#64748b;font-size:12px;">Snapshot not refreshed yet. Click <strong>Refresh Recommended Limits</strong> to calculate the latest recommendation.</div>`
    );
    return;
  }

  const latestRow = snapshotRows
    .slice()
    .sort((a, b) => {
      const left = frappe.datetime.str_to_obj(a.custom_snrg_recommended_credit_limit_updated_on);
      const right = frappe.datetime.str_to_obj(b.custom_snrg_recommended_credit_limit_updated_on);
      return right - left;
    })[0];

  const latestLabel = frappe.datetime.str_to_user(latestRow.custom_snrg_recommended_credit_limit_updated_on);
  const rowHtml = rows
    .map((row) => {
      const recommended = format_currency(row.custom_snrg_recommended_credit_limit || 0);
      const updated = row.custom_snrg_recommended_credit_limit_updated_on
        ? frappe.datetime.str_to_user(row.custom_snrg_recommended_credit_limit_updated_on)
        : "Not refreshed";
      return `
        <div style="display:flex;justify-content:space-between;gap:12px;padding:8px 10px;border:1px solid #e2e8f0;border-radius:10px;background:#fff;">
          <div style="font-weight:700;color:#334155;">${frappe.utils.escape_html(row.company || "")}</div>
          <div style="text-align:right;">
            <div style="font-weight:700;color:#0f172a;">${recommended}</div>
            <div style="font-size:11px;color:#64748b;">Updated: ${frappe.utils.escape_html(updated)}</div>
          </div>
        </div>
      `;
    })
    .join("");

  field.$wrapper.html(`
    <div style="padding:8px 0 2px;">
      <div style="display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:999px;background:#f8fafc;border:1px solid #dbe3ef;font-size:12px;color:#334155;font-weight:700;">
        Snapshot as of ${frappe.utils.escape_html(latestLabel)}
      </div>
      <div style="margin-top:10px;display:grid;gap:8px;">
        ${rowHtml}
      </div>
    </div>
  `);
}
