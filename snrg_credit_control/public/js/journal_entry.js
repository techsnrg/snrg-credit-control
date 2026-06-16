function patch_journal_entry_reference_query(frm) {
  if (!frm) return;

  frm.set_query("reference_name", "accounts", function (doc, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);

    if (row.reference_type === "Journal Entry") {
      frappe.model.validate_missing(row, "account");
      return {
        query: "erpnext.accounts.doctype.journal_entry.journal_entry.get_against_jv",
        filters: {
          account: row.account,
          party: row.party,
        },
      };
    }

    const out = {
      filters: [[row.reference_type, "docstatus", "=", 1]],
    };

    if (["Sales Invoice", "Purchase Invoice"].includes(row.reference_type)) {
      add_invoice_outstanding_filter(out.filters, row);

      if (row.cost_center) {
        out.filters.push([row.reference_type, "cost_center", "in", ["", row.cost_center]]);
      }

      frappe.model.validate_missing(row, "account");
      const party_account_field = row.reference_type === "Sales Invoice" ? "debit_to" : "credit_to";
      out.filters.push([row.reference_type, party_account_field, "=", row.account]);
    }

    if (["Sales Order", "Purchase Order"].includes(row.reference_type)) {
      frappe.model.validate_missing(row, "party_type");
      frappe.model.validate_missing(row, "party");
      out.filters.push([row.reference_type, "per_billed", "<", 100]);
    }

    if (row.party_type && row.party) {
      let party_field = "";
      if ((row.reference_type || "").indexOf("Sales") === 0) {
        party_field = "customer";
      } else if ((row.reference_type || "").indexOf("Purchase") === 0) {
        party_field = "supplier";
      }

      if (party_field) {
        out.filters.push([row.reference_type, party_field, "=", row.party]);
      }
    }

    return out;
  });
}

function add_invoice_outstanding_filter(filters, row) {
  if (row.reference_type === "Sales Invoice") {
    if (flt(row.credit) > 0) {
      filters.push([row.reference_type, "outstanding_amount", ">", 0]);
    } else if (flt(row.debit) > 0) {
      filters.push([row.reference_type, "outstanding_amount", "<", 0]);
    } else {
      filters.push([row.reference_type, "outstanding_amount", "!=", 0]);
    }
  } else if (row.reference_type === "Purchase Invoice") {
    if (flt(row.debit) > 0) {
      filters.push([row.reference_type, "outstanding_amount", ">", 0]);
    } else if (flt(row.credit) > 0) {
      filters.push([row.reference_type, "outstanding_amount", "<", 0]);
    } else {
      filters.push([row.reference_type, "outstanding_amount", "!=", 0]);
    }
  }
}

frappe.ui.form.on("Journal Entry", {
  setup(frm) {
    patch_journal_entry_reference_query(frm);
  },

  refresh(frm) {
    patch_journal_entry_reference_query(frm);
  },
});
