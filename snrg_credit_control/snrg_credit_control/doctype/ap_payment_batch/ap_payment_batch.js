frappe.ui.form.on("AP Payment Batch", {
  onload(frm) {
    _set_ap_batch_queries(frm);
  },

  refresh(frm) {
    _set_ap_batch_queries(frm);
    _set_ap_batch_buttons(frm);
    _refresh_debit_bank_filter(frm);
  },

  company(frm) {
    frm.set_value("debit_bank_account", null);
    frm.set_value("export_template", null);
    _refresh_debit_bank_filter(frm);
  },

  debit_bank_account(frm) {
    _refresh_debit_bank_filter(frm);
  },
});

frappe.ui.form.on("AP Payment Batch Item", {
  source_mode(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (row.source_mode === "Manual") {
      frappe.model.set_value(cdt, cdn, "source_doctype", "");
      frappe.model.set_value(cdt, cdn, "source_name", "");
      frappe.model.set_value(cdt, cdn, "outstanding_amount_snapshot", 0);
    } else {
      frappe.model.set_value(cdt, cdn, "party_type", "");
      frappe.model.set_value(cdt, cdn, "party", "");
    }
    frappe.model.set_value(cdt, cdn, "beneficiary_bank_account", "");
  },

  source_doctype(frm, cdt, cdn) {
    frappe.model.set_value(cdt, cdn, "source_name", "");
    _clear_source_snapshot(cdt, cdn);
  },

  source_name(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.source_doctype || !row.source_name) return;

    frappe.call({
      method: "snrg_credit_control.payables.get_source_details",
      args: {
        source_doctype: row.source_doctype,
        source_name: row.source_name,
        company: frm.doc.company,
      },
      callback(r) {
        const data = r.message || {};
        frappe.model.set_value(cdt, cdn, "party_type", data.party_type || "");
        frappe.model.set_value(cdt, cdn, "party", data.party || "");
        frappe.model.set_value(cdt, cdn, "outstanding_amount_snapshot", data.outstanding_amount || 0);
        if (!row.amount) {
          frappe.model.set_value(cdt, cdn, "amount", data.outstanding_amount || 0);
        }
        if (!row.remark && data.remark) {
          frappe.model.set_value(cdt, cdn, "remark", data.remark);
        }
      },
    });
  },

  beneficiary_bank_account(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.beneficiary_bank_account) {
      _clear_bank_snapshot(cdt, cdn);
      return;
    }

    frappe.call({
      method: "snrg_credit_control.payables.get_bank_account_snapshot",
      args: {
        bank_account: row.beneficiary_bank_account,
        party_type: row.party_type || null,
        party: row.party || null,
      },
      callback(r) {
        const data = r.message || {};
        frappe.model.set_value(cdt, cdn, "beneficiary_name", data.account_name || "");
        frappe.model.set_value(cdt, cdn, "beneficiary_account_no", data.bank_account_no || "");
        frappe.model.set_value(cdt, cdn, "beneficiary_ifsc", data.branch_code || "");
        if (!row.mobile_number && data.mobile_number) {
          frappe.model.set_value(cdt, cdn, "mobile_number", data.mobile_number);
        }
        if (!row.email_id && data.email_id) {
          frappe.model.set_value(cdt, cdn, "email_id", data.email_id);
        }
      },
    });
  },

  amount(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (row.source_mode === "Invoice" && row.outstanding_amount_snapshot && flt(row.amount) > flt(row.outstanding_amount_snapshot)) {
      frappe.msgprint(__("Amount cannot exceed the outstanding/open amount for invoice-based rows."));
      frappe.model.set_value(cdt, cdn, "amount", row.outstanding_amount_snapshot);
    }
  },
});

function _set_ap_batch_queries(frm) {
  frm.set_query("debit_bank_account", () => {
    const filters = {
      is_company_account: 1,
      disabled: 0,
      custom_snrg_ap_approval_status: "Approved",
    };
    if (frm.doc.company) filters.company = frm.doc.company;
    return { filters };
  });

  frm.set_query("export_template", () => {
    const filters = { is_active: 1 };
    if (frm._snrg_bank_name) filters.bank = frm._snrg_bank_name;
    return { filters };
  });

  const grid = frm.fields_dict.items.grid;
  grid.get_field("source_name").get_query = function (doc, cdt, cdn) {
    const row = locals[cdt][cdn];
    return {
      query: "snrg_credit_control.payables.search_invoice_sources",
      filters: {
        source_doctype: row.source_doctype,
        company: doc.company,
      },
    };
  };

  grid.get_field("beneficiary_bank_account").get_query = function (doc, cdt, cdn) {
    const row = locals[cdt][cdn];
    const filters = {
      disabled: 0,
      custom_snrg_ap_approval_status: "Approved",
    };
    if (row.party_type) filters.party_type = row.party_type;
    if (row.party) filters.party = row.party;
    return {
      filters,
    };
  };
}

function _refresh_debit_bank_filter(frm) {
  if (!frm.doc.debit_bank_account) {
    frm._snrg_bank_name = null;
    return;
  }

  frappe.db.get_value("Bank Account", frm.doc.debit_bank_account, "bank").then(r => {
    frm._snrg_bank_name = r.message ? r.message.bank : null;
  });
}

function _set_ap_batch_buttons(frm) {
  frm.remove_custom_button("Generate Export");
  frm.remove_custom_button("Create Draft Payment Entries");
  frm.remove_custom_button("Download Export");
  frm.remove_custom_button("Send Export by Email");

  if (frm.is_new()) return;

  frm.add_custom_button("Generate Export", () => {
    frappe.call({
      doc: frm.doc,
      method: "generate_export",
      freeze: true,
      freeze_message: "Generating bank export...",
      callback() {
        frm.reload_doc();
      },
    });
  }).addClass("btn-primary");

  frm.add_custom_button("Create Draft Payment Entries", () => {
    frappe.call({
      doc: frm.doc,
      method: "create_draft_payment_entries",
      freeze: true,
      freeze_message: "Creating draft Payment Entries...",
      callback(r) {
        if (r.message && r.message.message) {
          frappe.show_alert({ message: r.message.message, indicator: "green" });
        }
        frm.reload_doc();
      },
    });
  });

  if (frm.doc.generated_export_file) {
    frm.add_custom_button("Download Export", () => {
      window.open(frm.doc.generated_export_file, "_blank");
    });

    frm.add_custom_button("Send Export by Email", () => {
      frappe.call({
        doc: frm.doc,
        method: "send_export_by_email",
        freeze: true,
        freeze_message: "Sending export email...",
        callback() {
          frm.reload_doc();
        },
      });
    });
  }
}

function _clear_source_snapshot(cdt, cdn) {
  frappe.model.set_value(cdt, cdn, "party_type", "");
  frappe.model.set_value(cdt, cdn, "party", "");
  frappe.model.set_value(cdt, cdn, "outstanding_amount_snapshot", 0);
  frappe.model.set_value(cdt, cdn, "amount", 0);
}

function _clear_bank_snapshot(cdt, cdn) {
  frappe.model.set_value(cdt, cdn, "beneficiary_name", "");
  frappe.model.set_value(cdt, cdn, "beneficiary_account_no", "");
  frappe.model.set_value(cdt, cdn, "beneficiary_ifsc", "");
}
