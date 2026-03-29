frappe.ui.form.on("Legal Case", {
  refresh(frm) {
    frm.remove_custom_button("Create Demand Notice");
    frm.remove_custom_button("Open Demand Notice");
    render_legal_timeline(frm);

    if (frm.doc.demand_notice) {
      frm.add_custom_button("Open Demand Notice", function () {
        frappe.set_route("Form", "Demand Notice", frm.doc.demand_notice);
      }).addClass("btn-primary");
      return;
    }

    frm.add_custom_button("Create Demand Notice", function () {
      frappe.call({
        method: "snrg_credit_control.legal_case.create_demand_notice_from_legal_case",
        args: { legal_case: frm.doc.name },
        freeze: true,
        freeze_message: "Creating demand notice...",
        callback(r) {
          if (!r.message || !r.message.name) return;
          frm.reload_doc().then(() => {
            frappe.set_route("Form", "Demand Notice", r.message.name);
          });
        },
      });
    });
  },
});

function render_legal_timeline(frm) {
  const wrapper = frm.get_field("timeline_html");
  if (!wrapper) {
    return;
  }

  if (frm.is_new()) {
    wrapper.$wrapper.html(
      `<div class="text-muted" style="padding: 12px 0;">Timeline will appear after the legal case is saved.</div>`
    );
    return;
  }

  wrapper.$wrapper.html(
    `<div class="text-muted" style="padding: 12px 0;">Loading timeline...</div>`
  );

  frappe.call({
    method: "snrg_credit_control.legal_case.get_legal_case_timeline",
    args: { legal_case: frm.doc.name },
    callback(r) {
      const rows = r.message || [];
      wrapper.$wrapper.html(build_timeline_html(rows));
    },
    error() {
      wrapper.$wrapper.html(
        `<div class="text-danger" style="padding: 12px 0;">Unable to load timeline right now.</div>`
      );
    },
  });
}

function build_timeline_html(rows) {
  if (!rows.length) {
    return `<div class="text-muted" style="padding: 12px 0;">No activity has been logged for this legal case yet.</div>`;
  }

  const items = rows
    .map((row) => {
      const amount = row.amount
        ? `<div style="margin-top: 6px; font-weight: 600; color: #1f2937;">Amount: ${format_currency(row.amount)}</div>`
        : "";
      const remarks = row.remarks
        ? `<div style="margin-top: 6px; color: #4b5563; white-space: pre-wrap;">${frappe.utils.escape_html(row.remarks)}</div>`
        : "";
      const reference = row.reference_route
        ? `<div style="margin-top: 6px;"><a href="${row.reference_route}" style="color: #2563eb; text-decoration: none;">${frappe.utils.escape_html(row.reference_doctype)}: ${frappe.utils.escape_html(row.reference_name)}</a></div>`
        : "";
      const meta = [
        row.performed_by ? `By ${frappe.utils.escape_html(row.performed_by)}` : "",
        row.activity_date ? frappe.datetime.str_to_user(row.activity_date) : "",
      ]
        .filter(Boolean)
        .join(" | ");

      return `
        <div style="position: relative; margin: 0 0 14px 18px; padding: 12px 14px; border: 1px solid #e5e7eb; border-radius: 10px; background: #fff;">
          <div style="position: absolute; left: -23px; top: 16px; width: 10px; height: 10px; border-radius: 999px; background: #2563eb;"></div>
          <div style="font-weight: 700; color: #111827;">${frappe.utils.escape_html(row.activity_type || "Activity")}</div>
          <div style="margin-top: 2px; font-size: 12px; color: #6b7280;">${meta}</div>
          ${amount}
          ${remarks}
          ${reference}
        </div>
      `;
    })
    .join("");

  return `
    <div style="position: relative; margin: 8px 0 4px 0; padding-left: 14px;">
      <div style="position: absolute; left: 4px; top: 8px; bottom: 8px; width: 2px; background: #dbe3f0;"></div>
      ${items}
    </div>
  `;
}
