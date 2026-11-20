import frappe

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def install_fields():
    fields = {}
    for doctype, child in (
        ("Quotation", "Quotation Item"),
        ("Sales Order", "Sales Order Item"),
        ("Sales Invoice", "Sales Invoice Item"),
    ):
        fields[doctype] = [
            dict(fieldname="custom_scheme_tab", label="Schemes", fieldtype="Tab Break",
                 insert_after=frappe.get_doc("DocType", doctype).fields[-1].fieldname, print_hide=1),
            dict(fieldname="custom_scheme_panel", label="Scheme Eligibility", fieldtype="HTML",
                 insert_after="custom_scheme_tab", print_hide=1),
        ]
        fields[child] = [
            dict(fieldname="custom_scheme_state", label="Scheme Line State", fieldtype="Long Text",
                 hidden=1, read_only=1, no_copy=1),
            dict(fieldname="custom_scheme_quotation_item", label="Scheme Quotation Item ID",
                 fieldtype="Data", hidden=1, read_only=1),
        ]
    fields["Sales Invoice"].extend([
        dict(fieldname="custom_scheme_section", label="Scheme Achievement", fieldtype="Section Break",
             insert_after="items"),
        dict(fieldname="custom_scheme_summary", label="Scheme Achievement at Submission",
             fieldtype="Text Editor", read_only=1, no_copy=1, print_hide=1, insert_after="custom_scheme_section"),
        dict(fieldname="custom_scheme_contributions", label="Scheme Contributions",
             fieldtype="Table", options="SNRG Scheme Contribution", read_only=1, no_copy=1,
             print_hide=1, insert_after="custom_scheme_summary"),
    ])
    create_custom_fields(fields, update=True)
