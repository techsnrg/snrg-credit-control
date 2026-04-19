import io
import os
import re

import frappe
from frappe import _
from frappe.utils import add_days, cstr, flt, getdate, now_datetime, today
from frappe.utils.file_manager import save_file

from snrg_credit_control.bank_account import APPROVAL_STATUS_FIELD


MANUAL_PARTY_TYPES = ("Supplier", "Employee")
INVOICE_SOURCE_DOCTYPES = ("Purchase Invoice", "Expense Claim", "Employee Advance", "Journal Entry")
PAYMENT_MODES = ("FT", "NEFT", "RTGS", "IMPS")
REFERENCE_CAPABLE_DOCTYPES = ("Purchase Invoice", "Journal Entry")
ICICI_EXPORTER_KEY = "ICICI_NPAB"
ICICI_COLUMNS = [
    "PYMT_PROD_TYPE_CODE",
    "PYMT_MODE",
    "DEBIT_ACC_NO",
    "BNF_NAME",
    "BENE_ACC_NO",
    "BENE_IFSC",
    "AMOUNT",
    "DEBIT_NARR",
    "CREDIT_NARR",
    "MOBILE_NUM",
    "EMAIL_ID",
    "REMARK",
    "PYMT_DATE",
    "REF_NO",
    "ADDL_INFO1",
    "ADDL_INFO2",
    "ADDL_INFO3",
    "ADDL_INFO4",
    "ADDL_INFO5",
]


def get_ap_settings():
    if not frappe.db.exists("DocType", "AP Payment Settings"):
        return frappe._dict(
            {
                "approver_user": None,
                "default_export_email_recipient": "",
                "debit_narration_prefix": "BULK",
                "icici_template_file": "",
            }
        )
    return frappe.get_cached_doc("AP Payment Settings", "AP Payment Settings")


def validate_payment_batch(doc):
    if not doc.email_recipient:
        doc.email_recipient = cstr(get_ap_settings().get("default_export_email_recipient") or "")

    if not doc.items:
        doc.status = "Draft"
        return

    _validate_debit_bank_account(doc)
    _validate_export_template(doc)

    for row in doc.items:
        _validate_batch_row(doc, row)

    if doc.status not in ("Exported", "Emailed"):
        doc.status = "Ready"


def _validate_debit_bank_account(doc):
    if not doc.debit_bank_account:
        frappe.throw(_("Debit Bank Account is required."))

    bank_doc = frappe.db.get_value(
        "Bank Account",
        doc.debit_bank_account,
        ["is_company_account", "company", "disabled", APPROVAL_STATUS_FIELD, "bank_account_no"],
        as_dict=True,
    )
    if not bank_doc:
        frappe.throw(_("Debit Bank Account {0} was not found.").format(doc.debit_bank_account))
    if not bank_doc.is_company_account:
        frappe.throw(_("Debit Bank Account must be a Company Bank Account."))
    if doc.company and bank_doc.company and bank_doc.company != doc.company:
        frappe.throw(_("Debit Bank Account {0} does not belong to company {1}.").format(doc.debit_bank_account, doc.company))
    if bank_doc.disabled:
        frappe.throw(_("Debit Bank Account {0} is disabled.").format(doc.debit_bank_account))
    if bank_doc.get(APPROVAL_STATUS_FIELD) != "Approved":
        frappe.throw(_("Debit Bank Account {0} must be approved before use.").format(doc.debit_bank_account))


def _validate_export_template(doc):
    if not doc.export_template:
        frappe.throw(_("Export Template is required."))

    template = frappe.db.get_value(
        "AP Bank Export Template",
        doc.export_template,
        ["bank", "is_active", "exporter_key"],
        as_dict=True,
    )
    if not template:
        frappe.throw(_("Export Template {0} was not found.").format(doc.export_template))
    if not template.is_active:
        frappe.throw(_("Export Template {0} is disabled.").format(doc.export_template))

    debit_bank = frappe.db.get_value("Bank Account", doc.debit_bank_account, "bank")
    if template.bank and debit_bank and template.bank != debit_bank:
        frappe.throw(_("Export Template {0} does not match the selected debit bank account.").format(doc.export_template))


def _validate_batch_row(doc, row):
    if row.source_mode not in ("Invoice", "Manual"):
        frappe.throw(_("Row #{0}: Source Mode must be Invoice or Manual.").format(row.idx))

    if row.source_mode == "Invoice":
        if not row.source_doctype or row.source_doctype not in INVOICE_SOURCE_DOCTYPES:
            frappe.throw(_("Row #{0}: Source DocType is required.").format(row.idx))
        if not row.source_name:
            frappe.throw(_("Row #{0}: Source Document is required.").format(row.idx))
        details = get_source_details(row.source_doctype, row.source_name, doc.company)
        row.party_type = details.party_type
        row.party = details.party
        row.outstanding_amount_snapshot = flt(details.outstanding_amount)
        if not row.amount:
            row.amount = row.outstanding_amount_snapshot
        if row.outstanding_amount_snapshot and flt(row.amount) > flt(row.outstanding_amount_snapshot):
            frappe.throw(
                _("Row #{0}: Amount cannot be greater than the outstanding/open amount for {1} {2}.").format(
                    row.idx, row.source_doctype, row.source_name
                )
            )
    else:
        if row.party_type not in MANUAL_PARTY_TYPES:
            frappe.throw(_("Row #{0}: Manual rows support Supplier or Employee only.").format(row.idx))
        if not row.party:
            frappe.throw(_("Row #{0}: Party is required for manual rows.").format(row.idx))
        row.outstanding_amount_snapshot = 0

    if flt(row.amount) <= 0:
        frappe.throw(_("Row #{0}: Amount must be greater than zero.").format(row.idx))
    if row.payment_mode not in PAYMENT_MODES:
        frappe.throw(_("Row #{0}: Payment Mode must be FT, NEFT, RTGS, or IMPS.").format(row.idx))
    if not row.beneficiary_bank_account:
        frappe.throw(_("Row #{0}: Beneficiary Bank Account is required.").format(row.idx))

    snapshot = get_bank_account_snapshot(row.beneficiary_bank_account, row.party_type, row.party)
    row.beneficiary_name = snapshot.account_name
    row.beneficiary_account_no = snapshot.bank_account_no
    row.beneficiary_ifsc = snapshot.branch_code
    if not row.mobile_number and snapshot.mobile_number:
        row.mobile_number = snapshot.mobile_number
    if not row.email_id and snapshot.email_id:
        row.email_id = snapshot.email_id


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_invoice_sources(doctype, txt, searchfield, start, page_len, filters):
    source_doctype = (filters or {}).get("source_doctype")
    company = (filters or {}).get("company")
    txt = txt or ""
    start = int(start or 0)
    page_len = int(page_len or 20)
    like_txt = f"%{txt}%"

    if source_doctype == "Purchase Invoice":
        return frappe.db.sql(
            """
            select
                name,
                concat(ifnull(supplier, ''), ' / Outstanding: ', ifnull(outstanding_amount, 0))
            from `tabPurchase Invoice`
            where docstatus = 1
              and company = %(company)s
              and ifnull(outstanding_amount, 0) > 0
              and (
                    name like %(txt)s
                    or ifnull(supplier, '') like %(txt)s
                    or ifnull(supplier_name, '') like %(txt)s
                  )
            order by posting_date desc, modified desc
            limit %(start)s, %(page_len)s
            """,
            {"company": company, "txt": like_txt, "start": start, "page_len": page_len},
        )

    if source_doctype == "Expense Claim" and frappe.db.exists("DocType", "Expense Claim"):
        return frappe.db.sql(
            """
            select
                name,
                concat(ifnull(employee, ''), ' / Outstanding: ',
                    greatest(ifnull(total_sanctioned_amount, 0) - ifnull(total_amount_reimbursed, 0), 0))
            from `tabExpense Claim`
            where docstatus = 1
              and company = %(company)s
              and greatest(ifnull(total_sanctioned_amount, 0) - ifnull(total_amount_reimbursed, 0), 0) > 0
              and ifnull(is_paid, 0) = 0
              and (name like %(txt)s or ifnull(employee, '') like %(txt)s or ifnull(employee_name, '') like %(txt)s)
            order by posting_date desc, modified desc
            limit %(start)s, %(page_len)s
            """,
            {"company": company, "txt": like_txt, "start": start, "page_len": page_len},
        )

    if source_doctype == "Employee Advance" and frappe.db.exists("DocType", "Employee Advance"):
        return frappe.db.sql(
            """
            select
                name,
                concat(ifnull(employee, ''), ' / Outstanding: ',
                    greatest(ifnull(advance_amount, 0) - ifnull(paid_amount, 0), 0))
            from `tabEmployee Advance`
            where docstatus = 1
              and company = %(company)s
              and greatest(ifnull(advance_amount, 0) - ifnull(paid_amount, 0), 0) > 0
              and (name like %(txt)s or ifnull(employee, '') like %(txt)s or ifnull(employee_name, '') like %(txt)s)
            order by posting_date desc, modified desc
            limit %(start)s, %(page_len)s
            """,
            {"company": company, "txt": like_txt, "start": start, "page_len": page_len},
        )

    if source_doctype == "Journal Entry":
        rows = frappe.db.sql(
            """
            select
                je.name as name,
                jea.party_type,
                jea.party,
                sum(jea.credit - jea.debit) as payable_amount
            from `tabJournal Entry Account` jea
            inner join `tabJournal Entry` je on je.name = jea.parent
            where je.docstatus = 1
              and je.company = %(company)s
              and jea.party_type in ('Supplier', 'Employee')
              and (
                    je.name like %(txt)s
                    or ifnull(jea.party, '') like %(txt)s
                  )
            group by je.name, jea.party_type, jea.party
            having sum(jea.credit - jea.debit) > 0
            order by je.posting_date desc, je.modified desc
            """,
            {"company": company, "txt": like_txt},
            as_dict=True,
        )
        deduped = []
        by_name = {}
        for row in rows:
            by_name.setdefault(row.name, []).append(row)
        for name, group in by_name.items():
            if len(group) != 1:
                continue
            row = group[0]
            deduped.append((name, f"{row.party_type}: {row.party} / Outstanding: {flt(row.payable_amount)}"))
        return deduped[start : start + page_len]

    return []


@frappe.whitelist()
def get_source_details(source_doctype, source_name, company=None):
    if not source_doctype or not source_name:
        frappe.throw(_("Source document is required."))

    if source_doctype == "Purchase Invoice":
        fields = _safe_get_doc_values(
            "Purchase Invoice",
            source_name,
            ["company", "supplier", "supplier_name", "outstanding_amount", "currency", "bill_no", "remarks"],
        )
        _validate_same_company(company, fields.company, source_doctype, source_name)
        return frappe._dict(
            {
                "party_type": "Supplier",
                "party": fields.supplier,
                "party_name": fields.supplier_name,
                "outstanding_amount": flt(fields.outstanding_amount),
                "currency": fields.currency,
                "remark": fields.bill_no or fields.remarks or source_name,
            }
        )

    if source_doctype == "Expense Claim":
        _ensure_doctype_exists("Expense Claim")
        fields = _safe_get_doc_values(
            "Expense Claim",
            source_name,
            [
                "company",
                "employee",
                "employee_name",
                "currency",
                "total_sanctioned_amount",
                "total_amount_reimbursed",
                "remark",
            ],
        )
        _validate_same_company(company, fields.company, source_doctype, source_name)
        outstanding = max(flt(fields.total_sanctioned_amount) - flt(fields.total_amount_reimbursed), 0)
        return frappe._dict(
            {
                "party_type": "Employee",
                "party": fields.employee,
                "party_name": fields.employee_name,
                "outstanding_amount": outstanding,
                "currency": fields.currency,
                "remark": fields.remark or source_name,
            }
        )

    if source_doctype == "Employee Advance":
        _ensure_doctype_exists("Employee Advance")
        fields = _safe_get_doc_values(
            "Employee Advance",
            source_name,
            [
                "company",
                "employee",
                "employee_name",
                "currency",
                "advance_amount",
                "paid_amount",
                "purpose",
            ],
        )
        _validate_same_company(company, fields.company, source_doctype, source_name)
        outstanding = max(flt(fields.advance_amount) - flt(fields.paid_amount), 0)
        return frappe._dict(
            {
                "party_type": "Employee",
                "party": fields.employee,
                "party_name": fields.employee_name,
                "outstanding_amount": outstanding,
                "currency": fields.currency,
                "remark": fields.purpose or source_name,
            }
        )

    if source_doctype == "Journal Entry":
        rows = frappe.db.sql(
            """
            select
                je.company,
                jea.party_type,
                jea.party,
                sum(jea.credit - jea.debit) as payable_amount
            from `tabJournal Entry Account` jea
            inner join `tabJournal Entry` je on je.name = jea.parent
            where je.name = %(name)s
              and je.docstatus = 1
              and jea.party_type in ('Supplier', 'Employee')
            group by je.company, jea.party_type, jea.party
            having sum(jea.credit - jea.debit) > 0
            """,
            {"name": source_name},
            as_dict=True,
        )
        if len(rows) != 1:
            frappe.throw(_("Journal Entry {0} must have exactly one supported payable party row.").format(source_name))
        row = rows[0]
        _validate_same_company(company, row.company, source_doctype, source_name)
        return frappe._dict(
            {
                "party_type": row.party_type,
                "party": row.party,
                "party_name": _get_party_display_name(row.party_type, row.party),
                "outstanding_amount": flt(row.payable_amount),
                "currency": frappe.db.get_value("Company", row.company, "default_currency"),
                "remark": source_name,
            }
        )

    frappe.throw(_("Unsupported source document type: {0}").format(source_doctype))


@frappe.whitelist()
def get_bank_account_snapshot(bank_account, party_type=None, party=None):
    if not bank_account:
        frappe.throw(_("Bank Account is required."))

    fields = frappe.db.get_value(
        "Bank Account",
        bank_account,
        [
            "account_name",
            "bank",
            "bank_account_no",
            "branch_code",
            "party_type",
            "party",
            "company",
            "is_company_account",
            "disabled",
            APPROVAL_STATUS_FIELD,
        ],
        as_dict=True,
    )
    if not fields:
        frappe.throw(_("Bank Account {0} was not found.").format(bank_account))
    if fields.disabled:
        frappe.throw(_("Bank Account {0} is disabled.").format(bank_account))
    if fields.get(APPROVAL_STATUS_FIELD) != "Approved":
        frappe.throw(_("Bank Account {0} is not approved for AP use.").format(bank_account))
    if party_type and fields.party_type and fields.party_type != party_type:
        frappe.throw(_("Bank Account {0} does not belong to party type {1}.").format(bank_account, party_type))
    if party and fields.party and fields.party != party:
        frappe.throw(_("Bank Account {0} does not belong to party {1}.").format(bank_account, party))

    contact = _get_party_contact_defaults(party_type or fields.party_type, party or fields.party)

    return frappe._dict(
        {
            "account_name": fields.account_name or _get_party_display_name(fields.party_type, fields.party),
            "bank": fields.bank,
            "bank_account_no": fields.bank_account_no,
            "branch_code": fields.branch_code,
            "party_type": fields.party_type,
            "party": fields.party,
            "company": fields.company,
            "is_company_account": fields.is_company_account,
            "mobile_number": contact.get("mobile_number"),
            "email_id": contact.get("email_id"),
        }
    )


def generate_batch_export_file(batch_doc):
    template_doc = frappe.get_doc("AP Bank Export Template", batch_doc.export_template)
    if template_doc.exporter_key != ICICI_EXPORTER_KEY:
        frappe.throw(_("Unsupported exporter key: {0}").format(template_doc.exporter_key))

    debit_snapshot = get_bank_account_snapshot(batch_doc.debit_bank_account)
    rows = build_icici_export_rows(batch_doc, debit_snapshot)
    content = render_icici_xls(rows, template_doc)
    filename = f"{batch_doc.name}-{now_datetime().strftime('%Y%m%d%H%M%S')}.xls"
    return save_file(
        filename,
        content,
        batch_doc.doctype,
        batch_doc.name,
        is_private=1,
    )


def build_icici_export_rows(batch_doc, debit_snapshot):
    settings = get_ap_settings()
    debit_narration_prefix = cstr(settings.get("debit_narration_prefix") or "BULK").strip() or "BULK"
    debit_account_no = cstr(debit_snapshot.bank_account_no or "").strip()

    if not debit_account_no.isdigit() or len(debit_account_no) != 12:
        frappe.throw(_("Debit Bank Account must have a 12-digit numeric Bank Account No for ICICI export."))

    payment_date = getdate(batch_doc.batch_date or today())
    if payment_date < getdate(today()) or payment_date > getdate(add_days(today(), 365)):
        frappe.throw(_("Batch Date must be today or a future date within one year for ICICI export."))

    rows = []
    for index, row in enumerate(batch_doc.items, start=1):
        beneficiary_name = _normalize_beneficiary_name(row.beneficiary_name)
        bene_account_no = _digits_only(row.beneficiary_account_no)
        bene_ifsc = cstr(row.beneficiary_ifsc or "").strip().upper()
        debit_narr = _normalize_alphanumeric(row.debit_narration or f"{debit_narration_prefix}{index}", 30)
        credit_narr = _normalize_alphanumeric(row.credit_narration, 30)
        remark = _normalize_alphanumeric(row.remark, 30)
        ref_no = _normalize_alphanumeric(row.reference_no, 30)
        mobile = _normalize_numeric(row.mobile_number, 10)
        email_id = cstr(row.email_id or "").strip()

        if row.payment_mode == "FT":
            bene_ifsc = bene_ifsc or ""
        elif not bene_ifsc:
            frappe.throw(_("Row #{0}: IFSC is required unless Payment Mode is FT.").format(row.idx))

        if bene_ifsc and not re.fullmatch(r"[A-Z0-9]{1,11}", bene_ifsc):
            frappe.throw(_("Row #{0}: IFSC must be alphanumeric and at most 11 characters.").format(row.idx))
        if not bene_account_no.isdigit() or len(bene_account_no) > 32:
            frappe.throw(_("Row #{0}: Beneficiary Account No must be numeric and at most 32 digits.").format(row.idx))

        amount = round(flt(row.amount), 2)
        if amount <= 0:
            frappe.throw(_("Row #{0}: Amount must be greater than zero.").format(row.idx))

        rows.append(
            [
                "PAB_VENDOR",
                row.payment_mode,
                debit_account_no,
                beneficiary_name,
                bene_account_no,
                bene_ifsc,
                amount,
                debit_narr,
                credit_narr,
                mobile,
                email_id,
                remark,
                payment_date.strftime("%d-%m-%Y"),
                ref_no,
                cstr(row.addl_info1 or "").strip(),
                cstr(row.addl_info2 or "").strip(),
                cstr(row.addl_info3 or "").strip(),
                cstr(row.addl_info4 or "").strip(),
                cstr(row.addl_info5 or "").strip(),
            ]
        )

    return rows


def render_icici_xls(rows, template_doc):
    try:
        import xlrd
        from xlutils.copy import copy as xl_copy
    except ImportError as exc:
        frappe.throw(_("ICICI export dependencies are missing: {0}").format(exc))

    template_path = resolve_template_path(template_doc)
    if not os.path.exists(template_path):
        frappe.throw(_("ICICI template file was not found: {0}").format(template_path))

    workbook = xlrd.open_workbook(template_path, formatting_info=True)
    writable_book = xl_copy(workbook)
    sheet = writable_book.get_sheet(0)

    for row_idx in range(1, max(12, len(rows) + 8)):
        for col_idx in range(len(ICICI_COLUMNS)):
            sheet.write(row_idx, col_idx, "")

    for row_idx, values in enumerate(rows, start=1):
        for col_idx, value in enumerate(values):
            sheet.write(row_idx, col_idx, value)

    output = io.BytesIO()
    writable_book.save(output)
    return output.getvalue()


def resolve_template_path(template_doc):
    if template_doc.master_template_file:
        file_name = frappe.db.get_value("File", {"file_url": template_doc.master_template_file}, "name")
        if file_name:
            return frappe.get_doc("File", file_name).get_full_path()
        if os.path.exists(template_doc.master_template_file):
            return template_doc.master_template_file

    settings = get_ap_settings()
    if settings.get("icici_template_file"):
        file_name = frappe.db.get_value("File", {"file_url": settings.icici_template_file}, "name")
        if file_name:
            return frappe.get_doc("File", file_name).get_full_path()

    return frappe.get_app_path("snrg_credit_control", "templates", "npab_fmt.xls")


def create_payment_entries_for_batch(batch_doc):
    created = []
    skipped = []

    for row in batch_doc.items:
        if row.linked_payment_entry:
            skipped.append(row.idx)
            continue
        payment_entry = _create_payment_entry(batch_doc, row)
        row.linked_payment_entry = payment_entry.name
        created.append(payment_entry.name)

    if created:
        batch_doc.save(ignore_permissions=True)

    return created, skipped


def _create_payment_entry(batch_doc, row):
    details = {
        "doctype": "Payment Entry",
        "payment_type": "Pay",
        "company": batch_doc.company,
        "posting_date": batch_doc.batch_date or today(),
        "party_type": row.party_type,
        "party": row.party,
        "bank_account": batch_doc.debit_bank_account,
        "party_bank_account": row.beneficiary_bank_account,
        "paid_amount": flt(row.amount),
        "received_amount": flt(row.amount),
        "reference_no": batch_doc.name,
        "reference_date": batch_doc.batch_date or today(),
        "remarks": _build_payment_entry_remarks(batch_doc, row),
    }

    payment_entry = frappe.get_doc(details)
    if row.source_mode == "Invoice" and row.source_doctype in REFERENCE_CAPABLE_DOCTYPES:
        payment_entry.append(
            "references",
            {
                "reference_doctype": row.source_doctype,
                "reference_name": row.source_name,
                "allocated_amount": flt(row.amount),
            },
        )

    payment_entry.insert(ignore_permissions=True)
    return payment_entry


def _build_payment_entry_remarks(batch_doc, row):
    parts = [f"AP Batch {batch_doc.name}"]
    if row.source_mode == "Invoice" and row.source_doctype and row.source_name:
        parts.append(f"Source: {row.source_doctype} {row.source_name}")
    return " | ".join(parts)


def send_export_email(batch_doc):
    if not batch_doc.email_recipient:
        frappe.throw(_("Email Recipient is required before sending the export."))
    if not batch_doc.generated_export_file:
        frappe.throw(_("Generate the export file before emailing it."))

    file_doc = _get_attached_file_doc(batch_doc.generated_export_file)
    attachments = [{"fname": file_doc.file_name, "fcontent": file_doc.get_content()}]
    frappe.sendmail(
        recipients=[batch_doc.email_recipient],
        subject=f"AP Payment Export {batch_doc.name}",
        message=_build_export_email_message(batch_doc),
        attachments=attachments,
        now=True,
    )


def _get_attached_file_doc(file_url):
    file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not file_name:
        frappe.throw(_("Generated export file could not be located."))
    return frappe.get_doc("File", file_name)


def _build_export_email_message(batch_doc):
    return f"""
<p>Hello,</p>
<p>Please find attached the AP payment export file for batch <strong>{batch_doc.name}</strong>.</p>
<table border='1' cellpadding='0' cellspacing='0' style='border-collapse:collapse;width:100%;margin-bottom:16px;'>
  <tbody>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Company</td><td style='padding:6px 8px;'>{batch_doc.company}</td></tr>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Batch Date</td><td style='padding:6px 8px;'>{batch_doc.batch_date}</td></tr>
    <tr><td style='padding:6px 8px;font-weight:600;background:#f5f5f5;'>Rows</td><td style='padding:6px 8px;'>{len(batch_doc.items or [])}</td></tr>
  </tbody>
</table>
<p>This is an automated notification from SNRG ERPNext.</p>
"""


def _safe_get_doc_values(doctype, name, fields):
    _ensure_doctype_exists(doctype)
    meta = frappe.get_meta(doctype)
    valid_fields = [field for field in fields if meta.has_field(field)]
    if not valid_fields:
        frappe.throw(_("Unable to read fields from {0}.").format(doctype))
    values = frappe.db.get_value(doctype, name, valid_fields, as_dict=True)
    if not values:
        frappe.throw(_("{0} {1} was not found.").format(doctype, name))
    for field in fields:
        values.setdefault(field, None)
    return values


def _ensure_doctype_exists(doctype):
    if not frappe.db.exists("DocType", doctype):
        frappe.throw(_("{0} is not available on this site.").format(doctype))


def _validate_same_company(expected, actual, doctype, name):
    if expected and actual and expected != actual:
        frappe.throw(_("{0} {1} does not belong to company {2}.").format(doctype, name, expected))


def _get_party_display_name(party_type, party):
    if not party_type or not party:
        return ""
    fieldname = "title" if party_type == "Shareholder" else f"{party_type.lower()}_name"
    values = _safe_get_doc_values(party_type, party, [fieldname])
    return values.get(fieldname) or party


def _get_party_contact_defaults(party_type, party):
    if not party_type or not party or not frappe.db.exists("DocType", party_type):
        return frappe._dict({"mobile_number": "", "email_id": ""})

    field_map = {
        "Supplier": ["mobile_no", "email_id"],
        "Employee": ["cell_number", "personal_email", "company_email"],
    }
    candidates = field_map.get(party_type, [])
    if not candidates:
        return frappe._dict({"mobile_number": "", "email_id": ""})

    values = _safe_get_doc_values(party_type, party, candidates)
    mobile_number = values.get("mobile_no") or values.get("cell_number") or ""
    email_id = values.get("email_id") or values.get("company_email") or values.get("personal_email") or ""
    return frappe._dict({"mobile_number": mobile_number, "email_id": email_id})


def _normalize_beneficiary_name(value):
    value = cstr(value or "").strip()
    value = re.sub(r"\s+", " ", value)
    if not value:
        frappe.throw(_("Beneficiary Name is required for ICICI export."))
    if not re.fullmatch(r"[A-Za-z ]{1,500}", value):
        frappe.throw(_("Beneficiary Name must contain only alphabets and spaces for ICICI export."))
    return value


def _normalize_alphanumeric(value, max_len):
    value = cstr(value or "").strip()
    if not value:
        return ""
    value = re.sub(r"\s+", " ", value)
    if len(value) > max_len:
        frappe.throw(_("Value {0} exceeds the maximum length of {1}.").format(value, max_len))
    if not re.fullmatch(r"[A-Za-z0-9 ]*", value):
        frappe.throw(_("Value {0} can only contain letters, numbers, and spaces.").format(value))
    return value


def _normalize_numeric(value, max_len):
    value = _digits_only(value)
    if not value:
        return ""
    if len(value) > max_len:
        frappe.throw(_("Numeric value {0} exceeds the maximum length of {1}.").format(value, max_len))
    return value


def _digits_only(value):
    value = cstr(value or "").strip()
    value = re.sub(r"\s+", "", value)
    if not value:
        return ""
    if not value.isdigit():
        frappe.throw(_("Value {0} must be numeric.").format(value))
    return value
