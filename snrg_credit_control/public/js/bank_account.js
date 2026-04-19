const SNRG_AP_BANK_FIELDS = [
  "account_name",
  "account",
  "bank",
  "account_type",
  "account_subtype",
  "is_default",
  "is_company_account",
  "company",
  "party_type",
  "party",
  "iban",
  "branch_code",
  "bank_account_no",
  "disabled",
];

frappe.ui.form.on("Bank Account", {
  refresh(frm) {
    _load_ap_context(frm);
  },
});

function _load_ap_context(frm) {
  frappe.call({
    method: "snrg_credit_control.bank_account.get_bank_account_approval_context",
    args: { bank_account: frm.doc.name || null },
    callback(r) {
      const ctx = r.message || {};
      _toggle_ap_bank_fields(frm, ctx);
      _set_ap_bank_buttons(frm, ctx);
    },
  });
}

function _toggle_ap_bank_fields(frm, ctx) {
  const isApproved = frm.doc.custom_snrg_ap_approval_status === "Approved";
  const lockFields = !!(isApproved && !ctx.can_approve && !frappe.user_roles.includes("System Manager"));

  SNRG_AP_BANK_FIELDS.forEach(fieldname => {
    if (frm.fields_dict[fieldname]) {
      frm.set_df_property(fieldname, "read_only", lockFields ? 1 : 0);
    }
  });
}

function _set_ap_bank_buttons(frm, ctx) {
  frm.remove_custom_button("Approve Bank Account");
  frm.remove_custom_button("Reject Bank Account");

  if (frm.is_new() || !ctx.can_approve) return;
  if (["Approved"].includes(frm.doc.custom_snrg_ap_approval_status)) return;

  frm.add_custom_button("Approve Bank Account", () => {
    frappe.call({
      method: "snrg_credit_control.bank_account.approve_bank_account",
      args: { name: frm.doc.name },
      freeze: true,
      freeze_message: "Approving Bank Account...",
      callback() {
        frm.reload_doc();
      },
    });
  }).addClass("btn-primary");

  frm.add_custom_button("Reject Bank Account", () => {
    frappe.prompt(
      [
        {
          fieldname: "reason",
          fieldtype: "Small Text",
          label: "Reason",
        },
      ],
      values => {
        frappe.call({
          method: "snrg_credit_control.bank_account.reject_bank_account",
          args: {
            name: frm.doc.name,
            reason: values.reason || "",
          },
          freeze: true,
          freeze_message: "Rejecting Bank Account...",
          callback() {
            frm.reload_doc();
          },
        });
      },
      "Reject Bank Account",
      "Reject"
    );
  });
}
