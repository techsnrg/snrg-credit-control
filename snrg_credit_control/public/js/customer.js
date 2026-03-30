frappe.ui.form.on("Customer", {
  refresh(frm) {
    render_customer_legal_pill(frm);
    add_customer_legal_button(frm);
  },
  custom_is_under_legal(frm) {
    render_customer_legal_pill(frm);
    add_customer_legal_button(frm);
  },
  custom_active_legal_case(frm) {
    render_customer_legal_pill(frm);
    add_customer_legal_button(frm);
  },
});

function render_customer_legal_pill(frm) {
  try {
    if (!frm || !frm.page || !frm.page.wrapper) return;

    frm.page.wrapper.find(".snrg-customer-legal-pill").remove();
    if (!frm.doc.custom_is_under_legal) return;

    const pill = $(`
      <span class="snrg-customer-legal-pill" style="display:inline-flex;align-items:center;margin-left:8px;padding:4px 12px;border-radius:999px;border:1px solid rgba(220,38,38,.28);background:rgba(220,38,38,.12);color:#dc2626;font-size:12px;font-weight:700;line-height:1.2;white-space:nowrap;">
        Legal
      </span>
    `);

    const primaryIndicator = frm.page.wrapper.find(".page-head .indicator-pill, .layout-main .indicator-pill").first();
    if (primaryIndicator.length) {
      pill.insertAfter(primaryIndicator);
      return;
    }

    const titleArea = frm.page.wrapper.find(".page-title, .title-area, .page-form-header").first();
    if (titleArea.length) {
      titleArea.append(pill);
    }
  } catch (e) {
    console.warn("[SNRG Customer Legal Pill] render error:", e);
  }
}

function add_customer_legal_button(frm) {
  frm.remove_custom_button("Open Customer Desk");
  frm.remove_custom_button("Mark to Legal");
  frm.remove_custom_button("Open Legal Case");
  if (frm.is_new()) return;

  frm.add_custom_button("Open Customer Desk", function () {
    frappe.route_options = { customer: frm.doc.name };
    frappe.set_route("legal-desk");
  });

  if (frm.doc.custom_active_legal_case) {
    frm.add_custom_button("Open Legal Case", function () {
      frappe.set_route("Form", "Legal Case", frm.doc.custom_active_legal_case);
    }).addClass("btn-primary");
    return;
  }

  frm.add_custom_button("Mark to Legal", function () {
    frappe.call({
      method: "snrg_credit_control.legal_case.create_or_open_customer_legal_case",
      args: { customer: frm.doc.name },
      freeze: true,
      freeze_message: "Marking customer to legal...",
      callback(r) {
        if (!r.message || !r.message.name) return;
        frm.reload_doc().then(() => {
          frappe.set_route("Form", "Legal Case", r.message.name);
        });
      },
    });
  });
}
