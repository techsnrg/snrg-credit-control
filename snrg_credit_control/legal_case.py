import frappe
from frappe import _
from frappe.utils import flt, today


ACTIVE_LEGAL_STATUSES = {
    "Marked to Legal",
    "Documents Pending",
    "Under Review",
    "Notice Preparation",
    "Notice Sent",
    "Follow-up in Progress",
    "Settlement Discussion",
    "Partially Recovered",
    "Complaint / Case Filing",
    "In Proceedings",
}


def is_active_status(status):
    return status in ACTIVE_LEGAL_STATUSES


def get_default_company():
    return (
        frappe.defaults.get_user_default("Company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
        or ""
    )


def get_active_legal_case(customer, company=None, exclude_name=None):
    filters = {
        "customer": customer,
        "status": ("in", list(ACTIVE_LEGAL_STATUSES)),
    }
    if company:
        filters["company"] = company
    if exclude_name:
        filters["name"] = ("!=", exclude_name)
    return frappe.db.get_value("Legal Case", filters, "name")


def sync_customer_legal_marker(customer):
    active_case_name = frappe.db.get_value(
        "Legal Case",
        {
            "customer": customer,
            "status": ("in", list(ACTIVE_LEGAL_STATUSES)),
        },
        "name",
        order_by="modified desc",
    )

    values = {
        "custom_is_under_legal": 0,
        "custom_active_legal_case": "",
        "custom_legal_status": "",
        "custom_legal_marked_on": None,
        "custom_legal_marked_by": "",
    }

    if active_case_name:
        case_doc = frappe.get_doc("Legal Case", active_case_name)
        values.update(
            {
                "custom_is_under_legal": 1,
                "custom_active_legal_case": case_doc.name,
                "custom_legal_status": case_doc.status,
                "custom_legal_marked_on": case_doc.date_marked_legal,
                "custom_legal_marked_by": case_doc.marked_by or case_doc.owner,
            }
        )

    frappe.db.set_value("Customer", customer, values, update_modified=False)


def build_legal_case_title(customer_name, case_type):
    if not case_type:
        return customer_name
    return f"{customer_name} - {case_type}"


def create_or_open_legal_case(
    customer,
    company="",
    case_type="Outstanding Recovery",
    source_reference_type="",
    source_reference_name="",
    total_claim_amount=0,
):
    existing = get_active_legal_case(customer, company or None)
    if existing:
        return existing

    customer_name = frappe.db.get_value("Customer", customer, "customer_name") or customer
    case_doc = frappe.get_doc(
        {
            "doctype": "Legal Case",
            "case_title": build_legal_case_title(customer_name, case_type),
            "customer": customer,
            "company": company or get_default_company(),
            "case_type": case_type,
            "source_reference_type": source_reference_type,
            "source_reference_name": source_reference_name,
            "date_marked_legal": today(),
            "status": "Marked to Legal",
            "marked_by": frappe.session.user,
            "total_claim_amount": flt(total_claim_amount),
        }
    )
    case_doc.insert(ignore_permissions=True)
    return case_doc.name


@frappe.whitelist()
def create_or_open_customer_legal_case(customer):
    case_name = create_or_open_legal_case(customer=customer)
    return {"name": case_name}


@frappe.whitelist()
def create_or_open_legal_case_from_cheque_bounce(cheque_bounce_case):
    bounce_case = frappe.get_doc("Cheque Bounce Case", cheque_bounce_case)
    case_name = bounce_case.legal_case or create_or_open_legal_case(
        customer=bounce_case.customer,
        company=bounce_case.company,
        case_type="Cheque Bounce",
        source_reference_type="Cheque Bounce Case",
        source_reference_name=bounce_case.name,
        total_claim_amount=bounce_case.bounce_amount,
    )

    if not bounce_case.legal_case:
        frappe.db.set_value(
            "Cheque Bounce Case",
            bounce_case.name,
            "legal_case",
            case_name,
            update_modified=False,
        )

    return {"name": case_name}
