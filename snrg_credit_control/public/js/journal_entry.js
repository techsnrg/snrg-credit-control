frappe.ui.form.on("Journal Entry", {
  refresh(frm) {
    setup_cheque_bounce_action(frm);
  },

  custom_is_cheque_bounce(frm) {
    setup_cheque_bounce_action(frm);
  },
});

function setup_cheque_bounce_action(frm) {
  const fieldname = "custom_cheque_bounce_action";
  const field = frm.get_field(fieldname);
  if (!field) {
    return;
  }

  const should_show = Boolean(
    !frm.is_new() && frm.doc.docstatus === 1 && frm.doc.custom_is_cheque_bounce
  );

  frm.toggle_display(fieldname, should_show);

  if (!should_show || !field.$input) {
    return;
  }

  const label = frm.doc.custom_cheque_bounce_case
    ? "Open Cheque Bounce Case"
    : "Create Cheque Bounce Case";

  frm.set_df_property(fieldname, "label", label);
  field.refresh();

  field.$input
    .text(label)
    .removeClass("btn-default")
    .addClass("btn-primary")
    .off("click")
    .on("click", () => handle_cheque_bounce_action(frm));
}

function handle_cheque_bounce_action(frm) {
  if (frm.doc.custom_cheque_bounce_case) {
    frappe.set_route("Form", "Cheque Bounce Case", frm.doc.custom_cheque_bounce_case);
    return;
  }

  frappe.call({
    method: "snrg_credit_control.cheque_bounce.create_or_open_cheque_bounce_case",
    args: {
      journal_entry: frm.doc.name,
    },
    freeze: true,
    freeze_message: "Creating cheque bounce case...",
    callback(r) {
      if (!r.message || !r.message.name) {
        return;
      }
      frm.reload_doc().then(() => {
        frappe.set_route("Form", "Cheque Bounce Case", r.message.name);
      });
    },
  });
}
