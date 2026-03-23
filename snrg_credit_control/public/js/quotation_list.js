frappe.listview_settings["Quotation"] = {
  add_fields: ["custom_snrg_credit_check_status", "custom_snrg_credit_check_reason_code", "docstatus", "status"],
  has_indicator_for_draft: true,

  get_indicator(doc) {
    const creditStatus = doc.custom_snrg_credit_check_status;
    const reason = doc.custom_snrg_credit_check_reason_code;

    if (creditStatus === "Credit Hold") {
      return [__("Credit Hold"), "red", "custom_snrg_credit_check_status,=,Credit Hold"];
    }

    if (creditStatus === "Credit OK") {
      return [__("Credit OK"), "green", "custom_snrg_credit_check_status,=,Credit OK"];
    }

    if (doc.docstatus === 0) {
      return [__("Draft"), "red", "docstatus,=,0"];
    }

    if (doc.docstatus === 1) {
      return [__(doc.status || "Submitted"), "blue", `status,=,${doc.status || "Submitted"}`];
    }

    if (doc.docstatus === 2) {
      return [__("Cancelled"), "gray", "docstatus,=,2"];
    }

    return null;
  },
};
