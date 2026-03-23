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
}
