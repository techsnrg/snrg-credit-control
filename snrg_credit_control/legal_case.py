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


def add_legal_case_activity(
    legal_case,
    activity_type,
    activity_date=None,
    reference_doctype="",
    reference_name="",
    amount=0,
    remarks="",
):
    if not legal_case:
        return None

    exists = frappe.db.exists(
        "Legal Case Activity",
        {
            "legal_case": legal_case,
            "activity_type": activity_type,
            "activity_date": activity_date or today(),
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "remarks": remarks,
        },
    )
    if exists:
        return exists

    activity_doc = frappe.get_doc(
        {
            "doctype": "Legal Case Activity",
            "legal_case": legal_case,
            "activity_date": activity_date or today(),
            "activity_type": activity_type,
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "amount": flt(amount),
            "remarks": remarks,
            "performed_by": frappe.session.user,
        }
    )
    activity_doc.insert(ignore_permissions=True)
    return activity_doc.name


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
    add_legal_case_activity(
        case_doc.name,
        "Marked to Legal",
        activity_date=case_doc.date_marked_legal,
        reference_doctype=source_reference_type or "",
        reference_name=source_reference_name or "",
        amount=case_doc.total_claim_amount,
        remarks=f"Case opened as {case_doc.case_type}.",
    )
    return case_doc.name


def get_legal_case_settings():
    if frappe.db.exists("DocType", "Legal Case Settings"):
        return frappe.get_single("Legal Case Settings")
    return frappe._dict(
        {
            "default_notice_period_days": 15,
            "default_payment_wait_days": 15,
            "default_complaint_filing_days": 30,
        }
    )


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
        add_legal_case_activity(
            case_name,
            "Cheque Bounce Intake",
            reference_doctype="Cheque Bounce Case",
            reference_name=bounce_case.name,
            amount=bounce_case.bounce_amount,
            remarks=bounce_case.narration or "",
        )

    return {"name": case_name}


@frappe.whitelist()
def create_demand_notice_from_legal_case(legal_case):
    legal_case_doc = frappe.get_doc("Legal Case", legal_case)
    existing_notice = frappe.db.get_value("Demand Notice", {"legal_case": legal_case_doc.name})
    if existing_notice:
        return {"name": existing_notice}

    notice_doc = frappe.get_doc(
        {
            "doctype": "Demand Notice",
            "customer": legal_case_doc.customer,
            "company": legal_case_doc.company,
            "notice_date": today(),
            "legal_case": legal_case_doc.name,
        }
    )
    notice_doc.insert(ignore_permissions=True)

    frappe.db.set_value(
        "Legal Case",
        legal_case_doc.name,
        {
            "demand_notice": notice_doc.name,
            "status": "Notice Preparation",
        },
        update_modified=False,
    )
    add_legal_case_activity(
        legal_case_doc.name,
        "Demand Notice Created",
        reference_doctype="Demand Notice",
        reference_name=notice_doc.name,
        amount=notice_doc.grand_total_due or legal_case_doc.total_claim_amount,
        remarks="Demand Notice created from Legal Case.",
    )

    sync_customer_legal_marker(legal_case_doc.customer)
    return {"name": notice_doc.name}
