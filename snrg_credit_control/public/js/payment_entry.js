function patch_payment_entry_outstanding_invoice_default(frm) {
  if (!frm || !frm.events || frm._snrg_payment_entry_invoice_patch_applied) return;
  if (
    typeof frm.events.get_outstanding_documents !== "function" ||
    typeof frm.events.validate_filters_data !== "function"
  ) {
    return;
  }

  frm._snrg_payment_entry_invoice_patch_applied = true;

  frm.events.get_outstanding_invoices = function (frm) {
    const today = frappe.datetime.get_today();

    let fields = [
      { fieldtype: "Section Break", label: __("Posting Date") },
      {
        fieldtype: "Date",
        label: __("From Date"),
        fieldname: "from_posting_date",
        default: frappe.datetime.add_days(today, -365),
      },
      { fieldtype: "Column Break" },
      { fieldtype: "Date", label: __("To Date"), fieldname: "to_posting_date", default: today },
      { fieldtype: "Section Break", label: __("Due Date") },
      { fieldtype: "Date", label: __("From Date"), fieldname: "from_due_date" },
      { fieldtype: "Column Break" },
      { fieldtype: "Date", label: __("To Date"), fieldname: "to_due_date" },
      { fieldtype: "Section Break", label: __("Outstanding Amount") },
      {
        fieldtype: "Float",
        label: __("Greater Than Amount"),
        fieldname: "outstanding_amt_greater_than",
        default: 0,
      },
      { fieldtype: "Column Break" },
      { fieldtype: "Float", label: __("Less Than Amount"), fieldname: "outstanding_amt_less_than" },
    ];

    if (frm.dimension_filters) {
      const column_break_insertion_point = Math.ceil(frm.dimension_filters.length / 2);

      fields.push({ fieldtype: "Section Break" });
      frm.dimension_filters.map((elem, idx) => {
        fields.push({
          fieldtype: "Link",
          label: elem.document_type == "Cost Center" ? "Cost Center" : elem.label,
          options: elem.document_type,
          fieldname: elem.fieldname || elem.document_type,
        });

        if (idx + 1 == column_break_insertion_point) {
          fields.push({ fieldtype: "Column Break" });
        }
      });
    }

    fields = fields.concat([
      { fieldtype: "Section Break" },
      {
        fieldtype: "Check",
        label: __("Allocate Payment Amount"),
        fieldname: "allocate_payment_amount",
        default: 1,
      },
    ]);

    frappe.prompt(
      fields,
      function (filters) {
        frappe.flags.allocate_payment_amount = true;
        frm.events.validate_filters_data(frm, filters);
        frm.doc.cost_center = filters.cost_center;
        frm.events.get_outstanding_documents(frm, filters, true, false);
      },
      __("Filters"),
      __("Get Outstanding Invoices")
    );
  };
}

frappe.ui.form.on("Payment Entry", {
  setup(frm) {
    patch_payment_entry_outstanding_invoice_default(frm);
  },

  refresh(frm) {
    patch_payment_entry_outstanding_invoice_default(frm);
  },
});
