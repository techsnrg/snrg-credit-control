import frappe
from frappe import _
from frappe.utils import flt


AUTO_STATUSES = {
    "Entry Marked",
    "Documents Pending",
    "Ready for Legal Review",
}


def get_cheque_bounce_customer_row(journal_entry):
    candidate_rows = []
    for row in journal_entry.accounts or []:
        debit_amount = flt(row.debit or row.debit_in_account_currency)
        if debit_amount <= 0:
            continue
        if row.party_type != "Customer" or not row.party:
            continue
        candidate_rows.append(row)

    if not candidate_rows:
        frappe.throw(
            _("Cheque bounce entry requires exactly one debit row against a Customer.")
        )

    if len(candidate_rows) > 1:
        frappe.throw(
            _("Multiple debit customer rows found. Please keep exactly one debit row against a Customer for cheque bounce tracking.")
        )

    return candidate_rows[0]


def build_cheque_bounce_case_values(journal_entry):
    row = get_cheque_bounce_customer_row(journal_entry)
    return {
        "journal_entry": journal_entry.name,
        "company": journal_entry.company,
        "customer": row.party,
        "bounce_entry_date": journal_entry.posting_date,
        "bounce_amount": flt(row.debit or row.debit_in_account_currency),
        "narration": journal_entry.user_remark or "",
    }


def get_initial_cheque_bounce_status(case_doc):
    has_cheque_scan = bool(case_doc.cheque_scan)
    has_bank_memo = bool(case_doc.bank_memo_scan)
    if not has_cheque_scan and not has_bank_memo:
        return "Entry Marked"
    if not has_cheque_scan or not has_bank_memo:
        return "Documents Pending"
    return "Ready for Legal Review"


def sync_cheque_bounce_case_from_journal_entry(journal_entry):
    if not journal_entry.name or str(journal_entry.name).startswith("new-"):
        return None

    if not journal_entry.custom_is_cheque_bounce:
        if not journal_entry.custom_cheque_bounce_case and journal_entry.custom_cheque_bounce_status:
            frappe.db.set_value(
                "Journal Entry",
                journal_entry.name,
                "custom_cheque_bounce_status",
                "",
                update_modified=False,
            )
        return None

    values = build_cheque_bounce_case_values(journal_entry)
    case_name = journal_entry.custom_cheque_bounce_case or frappe.db.get_value(
        "Cheque Bounce Case", {"journal_entry": journal_entry.name}
    )

    if case_name and frappe.db.exists("Cheque Bounce Case", case_name):
        case_doc = frappe.get_doc("Cheque Bounce Case", case_name)
        for fieldname, value in values.items():
            case_doc.set(fieldname, value)
        if case_doc.status in AUTO_STATUSES or not case_doc.status:
            case_doc.status = get_initial_cheque_bounce_status(case_doc)
        case_doc.save(ignore_permissions=True)
    else:
        case_doc = frappe.get_doc(
            {
                "doctype": "Cheque Bounce Case",
                **values,
                "status": "Entry Marked",
            }
        )
        case_doc.insert(ignore_permissions=True)

    frappe.db.set_value(
        "Journal Entry",
        journal_entry.name,
        {
            "custom_cheque_bounce_case": case_doc.name,
            "custom_cheque_bounce_status": case_doc.status,
        },
        update_modified=False,
    )

    return case_doc.name


@frappe.whitelist()
def create_or_open_cheque_bounce_case(journal_entry):
    journal_entry_doc = frappe.get_doc("Journal Entry", journal_entry)
    if not journal_entry_doc.custom_is_cheque_bounce:
        frappe.throw(_("Please mark this Journal Entry as a cheque bounce first."))
    case_name = sync_cheque_bounce_case_from_journal_entry(journal_entry_doc)
    return {"name": case_name}
