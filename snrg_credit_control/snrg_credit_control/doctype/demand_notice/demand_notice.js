// demand_notice.js — Client-side controller for the Demand Notice form

frappe.ui.form.on("Demand Notice", {

    // ------------------------------------------------------------------
    // Form lifecycle
    // ------------------------------------------------------------------

    setup(frm) {
        // Filter customer_address to show only addresses linked to the selected customer
        frm.set_query("customer_address", function () {
            return {
                filters: {
                    link_doctype: "Customer",
                    link_name: frm.doc.customer,
                },
            };
        });
    },

    onload(frm) {
        if (frm.is_new()) {
            _prefill_from_settings(frm);
            _prefill_signatory(frm);
        }
    },

    refresh(frm) {
        _set_fetch_button(frm);
    },

    // ------------------------------------------------------------------
    // Field change handlers
    // ------------------------------------------------------------------

    customer(frm) {
        // Reset address when customer changes
        frm.set_value("customer_address", null);
        frm.set_value("address_display", "");
        _set_fetch_button(frm);
    },

    company(frm) {
        _set_fetch_button(frm);
    },

    notice_date(frm) {
        // Recompute payment_deadline whenever notice_date changes
        if (!frm.doc.notice_date) return;
        frappe.call({
            method: "frappe.client.get_single_value",
            args: {
                doctype: "Demand Notice Settings",
                field: "payment_deadline_days",
            },
            callback(r) {
                const days = r.message || 7;
                const deadline = frappe.datetime.add_days(frm.doc.notice_date, days);
                frm.set_value("payment_deadline", deadline);
            },
        });
    },

    customer_address(frm) {
        if (!frm.doc.customer_address) {
            frm.set_value("address_display", "");
            return;
        }
        frappe.call({
            method: "frappe.contacts.doctype.address.address.get_address_display",
            args: { address_dict: frm.doc.customer_address },
            callback(r) {
                frm.set_value("address_display", r.message || "");
            },
        });
    },

});


// ------------------------------------------------------------------
// Private helpers
// ------------------------------------------------------------------

function _prefill_from_settings(frm) {
    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Demand Notice Settings",
            name: "Demand Notice Settings",
        },
        callback(r) {
            const s = r.message;
            if (!s) return;

            if (!frm.doc.interest_rate) {
                frm.set_value("interest_rate", s.default_interest_rate || 18);
            }

            if (!frm.doc.legal_consequences_text && s.default_legal_text) {
                frm.set_value("legal_consequences_text", s.default_legal_text);
            }

            // Set payment deadline based on today + deadline_days
            if (!frm.doc.payment_deadline && frm.doc.notice_date) {
                const days = s.payment_deadline_days || 7;
                const deadline = frappe.datetime.add_days(frm.doc.notice_date, days);
                frm.set_value("payment_deadline", deadline);
            }
        },
    });
}

function _prefill_signatory(frm) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Employee",
            filters: {
                user_id: frappe.session.user,
                status: "Active",
            },
            fields: [
                "employee_name",
                "designation",
                "custom_bar_council_number",
                "custom_official_mobile",
                "custom_signature_image",
            ],
            limit: 1,
        },
        callback(r) {
            if (!r.message || !r.message.length) return;
            const emp = r.message[0];
            if (!frm.doc.authorised_signatory) {
                frm.set_value("authorised_signatory", emp.employee_name || "");
            }
            if (!frm.doc.signatory_designation) {
                frm.set_value("signatory_designation", emp.designation || "");
            }
            if (!frm.doc.bar_council_number) {
                frm.set_value("bar_council_number", emp.custom_bar_council_number || "");
            }
            if (!frm.doc.official_mobile) {
                frm.set_value("official_mobile", emp.custom_official_mobile || "");
            }
            if (!frm.doc.signature_image) {
                frm.set_value("signature_image", emp.custom_signature_image || "");
            }
        },
    });
}

function _set_fetch_button(frm) {
    // Show the "Fetch Overdue Invoices" button only when the doc is editable
    // and the mandatory fields are present
    frm.remove_custom_button("Fetch Overdue Invoices");

    if (frm.doc.legal_case) return;
    if (frm.doc.docstatus !== 0) return;
    if (!frm.doc.customer || !frm.doc.company) return;

    frm.add_custom_button("Fetch Overdue Invoices", function () {
        _fetch_overdue_invoices(frm);
    }).addClass("btn-primary");
}

function _fetch_overdue_invoices(frm) {
    frappe.dom.freeze("Fetching overdue invoices…");

    frappe.call({
        doc: frm.doc,
        method: "get_overdue_invoices",
        callback(r) {
            frappe.dom.unfreeze();

            const rows = r.message;
            if (!rows || !rows.length) return;

            // Clear existing rows and populate fresh
            frm.clear_table("invoices");
            rows.forEach(function (inv) {
                const row = frm.add_child("invoices");
                row.sales_invoice    = inv.sales_invoice;
                row.posting_date     = inv.posting_date;
                row.due_date         = inv.due_date;
                row.outstanding_amount = inv.outstanding_amount;
                row.overdue_days     = inv.overdue_days;
                row.interest_amount  = inv.interest_amount;
                row.total_payable    = inv.total_payable;
            });

            frm.refresh_field("invoices");

            // Trigger a save so validate() recomputes the summary totals
            frm.save();
        },
        error() {
            frappe.dom.unfreeze();
        },
    });
}
