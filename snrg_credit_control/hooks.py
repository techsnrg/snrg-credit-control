app_name = "snrg_credit_control"
app_title = "SNRG Credit Control"
app_publisher = "SNRG India"
app_description = "Credit Control workflow for Sales Orders"
app_email = "nikhil@snrgindia.com"
app_license = "MIT"

after_install = "snrg_credit_control.setup.after_install"
after_migrate = "snrg_credit_control.setup.after_migrate"

# Inject JS into the Sales Order form
doctype_js = {
    "Sales Order": "public/js/sales_order.js",
    "Quotation": "public/js/quotation.js",
}

doctype_list_js = {
    "Sales Order": "public/js/sales_order_list.js",
    "Quotation": "public/js/quotation_list.js",
}

override_doctype_class = {
    "Sales Invoice": "snrg_credit_control.overrides.sales_invoice.CustomSalesInvoice",
}

# Python event hooks for Sales Order
doc_events = {
    "Sales Order": {
        "validate":      "snrg_credit_control.overrides.sales_order.validate",
        "before_submit": "snrg_credit_control.overrides.sales_order.before_submit",
        "after_save":    "snrg_credit_control.overrides.sales_order.after_save",
    },
    "Quotation": {
        "validate": "snrg_credit_control.overrides.quotation.validate",
    },
    "Payment Entry": {
        "on_submit": "snrg_credit_control.ptp.auto_allocate_payment_entry_to_ptps",
        "on_cancel": "snrg_credit_control.ptp.remove_payment_entry_ptp_allocations",
    },
}
