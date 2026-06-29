frappe.ui.form.on("Monthly Sales Plan", {
  refresh(frm) {
    frm.set_query("previous_plan", () => ({
      filters: {
        company: frm.doc.company,
        plan_month: frm.doc.plan_month,
        sales_person: frm.doc.sales_person,
      },
    }));

    if (frm.doc.docstatus === 0) {
      frm.add_custom_button(__("Fetch Customers"), () => fetchCustomers(frm));
    }

    if (frm.doc.docstatus === 1 && frm.doc.status !== "Cancelled") {
      frm.add_custom_button(__("Create Revision"), () => createRevision(frm));
    }
  },

  plan_month(frm) {
    normalizePlanMonth(frm);
  },

  before_save(frm) {
    normalizePlanMonth(frm);
  },
});

frappe.ui.form.on("Monthly Sales Plan Customer", {
  customer(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.customer) return;

    frappe.db.get_value("Customer", row.customer, ["customer_name", "customer_group", "territory"]).then((result) => {
      const customer = result && result.message ? result.message : {};
      frappe.model.set_value(cdt, cdn, "customer_name", customer.customer_name || row.customer);
      frappe.model.set_value(cdt, cdn, "customer_group", customer.customer_group || "");
      frappe.model.set_value(cdt, cdn, "territory", customer.territory || "");
    });
  },
});

function normalizePlanMonth(frm) {
  if (!frm.doc.plan_month) return;
  const firstDay = frappe.datetime.month_start(frm.doc.plan_month);
  if (firstDay && firstDay !== frm.doc.plan_month) {
    frm.set_value("plan_month", firstDay);
  }
}

function fetchCustomers(frm) {
  const required = ["company", "plan_month", "sales_person"];
  const missing = required.filter((fieldname) => !frm.doc[fieldname]);
  if (missing.length) {
    frappe.msgprint(__("Please select Company, Plan Month, and Sales Person first."));
    return;
  }

  const existingCustomerRows = (frm.doc.customers || []).filter((row) => row.customer);
  const runFetch = () => {
    frappe.call({
      method: "snrg_credit_control.snrg_credit_control.doctype.monthly_sales_plan.monthly_sales_plan.fetch_customers",
      args: {
        company: frm.doc.company,
        plan_month: frm.doc.plan_month,
        sales_person: frm.doc.sales_person,
      },
      freeze: true,
      freeze_message: __("Fetching customers..."),
      callback(response) {
        mergeCustomerRows(frm, response.message || []);
      },
    });
  };

  if (existingCustomerRows.length) {
    frappe.confirm(
      __("Fetch will refresh mapped customer rows. Manual rows with blank Customer will remain untouched. Continue?"),
      runFetch
    );
    return;
  }

  runFetch();
}

function mergeCustomerRows(frm, customers) {
  const manualRows = (frm.doc.customers || []).filter((row) => !row.customer);
  const plannedByCustomer = {};
  const remarksByCustomer = {};

  (frm.doc.customers || []).forEach((row) => {
    if (!row.customer) return;
    plannedByCustomer[row.customer] = row.planned_amount || 0;
    remarksByCustomer[row.customer] = row.remarks || "";
  });

  frm.clear_table("customers");
  customers.forEach((customer) => {
    const row = frm.add_child("customers");
    row.customer = customer.customer;
    row.customer_name = customer.customer_name || customer.customer;
    row.customer_group = customer.customer_group || "";
    row.territory = customer.territory || "";
    row.planned_amount = plannedByCustomer[customer.customer] || 0;
    row.remarks = remarksByCustomer[customer.customer] || "";
  });

  manualRows.forEach((manualRow) => {
    const row = frm.add_child("customers");
    row.customer_name = manualRow.customer_name || "";
    row.planned_amount = manualRow.planned_amount || 0;
    row.remarks = manualRow.remarks || "";
  });

  frm.refresh_field("customers");
  frappe.show_alert({
    message: __("Fetched {0} customers. Manual lead rows preserved.", [customers.length]),
    indicator: "green",
  });
}

function createRevision(frm) {
  frappe.call({
    method: "snrg_credit_control.snrg_credit_control.doctype.monthly_sales_plan.monthly_sales_plan.make_revision",
    args: {
      source_name: frm.doc.name,
    },
    freeze: true,
    freeze_message: __("Creating revision..."),
    callback(response) {
      if (!response.message) return;
      frappe.set_route("Form", "Monthly Sales Plan", response.message);
    },
  });
}
