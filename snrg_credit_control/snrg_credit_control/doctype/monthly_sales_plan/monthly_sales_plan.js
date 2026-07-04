frappe.ui.form.on("Monthly Sales Plan", {
  refresh(frm) {
    setupMonthPicker(frm);

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

    if (!frm.is_new()) {
      frm.add_custom_button(__("Download PDF"), () => downloadPlanPdf(frm), __("Export"));
    }

    if (frm.doc.docstatus === 1 && frm.doc.status !== "Cancelled") {
      frm.add_custom_button(__("Create Revision"), () => createRevision(frm));
    }
  },

  onload(frm) {
    setupMonthPicker(frm);
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

  planned_amount(frm, cdt, cdn) {
    updateMinimumPayment(cdt, cdn);
  },
});

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
        team_members: (frm.doc.team_members || []).map((row) => row.sales_person).filter(Boolean),
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

function setupMonthPicker(frm) {
  if (!frm.doc.plan_month) {
    frm.set_value("plan_month", frappe.datetime.get_today().slice(0, 7));
  } else if (/^\d{4}-\d{2}-\d{2}$/.test(frm.doc.plan_month)) {
    frm.set_value("plan_month", frm.doc.plan_month.slice(0, 7));
  }

  setTimeout(() => {
    const control = frm.fields_dict.plan_month;
    if (!control || !control.$input) return;
    control.$input.attr("type", "month");
    control.$input.attr("placeholder", "YYYY-MM");
  }, 0);
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
    row.last_month_sales = customer.last_month_sales || 0;
    row.current_credit_limit = customer.current_credit_limit || 0;
    row.credit_limit_available = customer.credit_limit_available || 0;
    row.planned_amount = plannedByCustomer[customer.customer] || 0;
    row.minimum_payment_required = Math.max(
      Number(row.planned_amount || 0) - Number(row.credit_limit_available || 0),
      0
    );
    row.projected_75_plus_outstanding = customer.projected_75_plus_outstanding || 0;
    row.remarks = remarksByCustomer[customer.customer] || "";
  });

  manualRows.forEach((manualRow) => {
    const row = frm.add_child("customers");
    row.customer_name = manualRow.customer_name || "";
    row.planned_amount = manualRow.planned_amount || 0;
    row.minimum_payment_required = 0;
    row.remarks = manualRow.remarks || "";
  });

  frm.refresh_field("customers");
  frappe.show_alert({
    message: __("Fetched {0} customers. Manual lead rows preserved.", [customers.length]),
    indicator: "green",
  });
}

function updateMinimumPayment(cdt, cdn) {
  const row = locals[cdt][cdn];
  const required = Math.max(Number(row.planned_amount || 0) - Number(row.credit_limit_available || 0), 0);
  frappe.model.set_value(cdt, cdn, "minimum_payment_required", required);
}

async function downloadPlanPdf(frm) {
  if (frm.is_dirty()) {
    await frm.save();
  }

  const params = new URLSearchParams({
    doctype: frm.doctype,
    name: frm.doc.name,
    format: "Monthly Sales Plan",
    no_letterhead: "0",
  });

  const response = await fetch(`/api/method/frappe.utils.print_format.download_pdf?${params.toString()}`, {
    credentials: "same-origin",
  });

  if (!response.ok) {
    frappe.msgprint(__("Unable to download PDF. Please try again."));
    return;
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = getPlanPdfFilename(frm);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

function getPlanPdfFilename(frm) {
  const salesPerson = cleanFilenamePart(frm.doc.sales_person_name || frm.doc.sales_person || "Sales Person");
  const month = cleanFilenamePart(getPlanMonthLabel(frm.doc.plan_month));
  const planId = cleanFilenamePart(frm.doc.name || "Monthly Sales Plan");
  return `Monthly Sales Plan - ${salesPerson} - ${month} - ${planId}.pdf`;
}

function getPlanMonthLabel(planMonth) {
  if (!planMonth) return "Plan Month";

  const value = String(planMonth);
  const match = value.match(/^(\d{4})-(\d{2})/);
  if (!match) return value;

  const monthNames = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];
  const monthIndex = Number(match[2]) - 1;
  const monthName = monthNames[monthIndex] || match[2];
  return `${monthName} ${match[1]}`;
}

function cleanFilenamePart(value) {
  return String(value || "")
    .replace(/[\\/:*?"<>|]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
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
