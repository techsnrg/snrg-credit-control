import frappe
from frappe import _
from frappe.utils import flt, today

from snrg_credit_control.credit_status import get_total_outstanding

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


def get_current_outstanding_balance(customer, company=""):
    if not customer:
        return 0
    resolved_company = company or get_default_company()
    if not resolved_company:
        return 0
    return max(flt(get_total_outstanding(customer, resolved_company)), 0)


def resolve_initial_legal_amount(customer, company="", fallback=0):
    snapshot_amount = get_current_outstanding_balance(customer, company)
    if snapshot_amount > 0:
        return snapshot_amount
    return max(flt(fallback), 0)


def get_last_payment_date(customer, company="", from_date=None):
    if not customer:
        return None

    filters = {
        "docstatus": 1,
        "party_type": "Customer",
        "party": customer,
        "payment_type": "Receive",
    }
    if company:
        filters["company"] = company
    if from_date:
        filters["posting_date"] = (">=", from_date)

    return frappe.db.get_value(
        "Payment Entry",
        filters,
        "posting_date",
        order_by="posting_date desc, modified desc",
    )


def get_last_notice_date(legal_case):
    if not legal_case:
        return None

    return frappe.db.sql(
        """
        SELECT MAX(notice_date)
        FROM `tabDemand Notice`
        WHERE legal_case = %s
          AND docstatus = 1
        """,
        (legal_case,),
    )[0][0]


def get_last_activity_date(legal_case):
    if not legal_case:
        return None

    return frappe.db.sql(
        """
        SELECT MAX(activity_date)
        FROM `tabLegal Case Activity`
        WHERE legal_case = %s
        """,
        (legal_case,),
    )[0][0]


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

    resolved_company = company or get_default_company()
    opening_amount = resolve_initial_legal_amount(
        customer=customer,
        company=resolved_company,
        fallback=total_claim_amount,
    )
    customer_name = frappe.db.get_value("Customer", customer, "customer_name") or customer
    case_doc = frappe.get_doc(
        {
            "doctype": "Legal Case",
            "case_title": build_legal_case_title(customer_name, case_type),
            "customer": customer,
            "company": resolved_company,
            "case_type": case_type,
            "source_reference_type": source_reference_type,
            "source_reference_name": source_reference_name,
            "date_marked_legal": today(),
            "status": "Marked to Legal",
            "marked_by": frappe.session.user,
            "original_legal_amount": opening_amount,
            "total_claim_amount": opening_amount,
        }
    )
    case_doc.insert(ignore_permissions=True)
    add_legal_case_activity(
        case_doc.name,
        "Marked to Legal",
        activity_date=case_doc.date_marked_legal,
        reference_doctype=source_reference_type or "",
        reference_name=source_reference_name or "",
        amount=case_doc.original_legal_amount,
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

    legal_case_doc.demand_notice = notice_doc.name
    legal_case_doc.status = "Notice Preparation"
    legal_case_doc.save(ignore_permissions=True)
    add_legal_case_activity(
        legal_case_doc.name,
        "Demand Notice Created",
        reference_doctype="Demand Notice",
        reference_name=notice_doc.name,
        amount=notice_doc.grand_total_due or legal_case_doc.original_legal_amount,
        remarks="Demand Notice created from Legal Case.",
    )

    sync_customer_legal_marker(legal_case_doc.customer)
    return {"name": notice_doc.name}


@frappe.whitelist()
def get_legal_case_timeline(legal_case):
    if not legal_case:
        return []

    activities = frappe.get_all(
        "Legal Case Activity",
        filters={"legal_case": legal_case},
        fields=[
            "name",
            "activity_date",
            "activity_type",
            "reference_doctype",
            "reference_name",
            "amount",
            "remarks",
            "performed_by",
            "creation",
        ],
        order_by="activity_date desc, creation desc",
    )

    for row in activities:
        row["reference_route"] = ""
        if row.get("reference_doctype") and row.get("reference_name"):
            row["reference_route"] = f"/app/{frappe.scrub(row['reference_doctype'])}/{row['reference_name']}"

    return activities


@frappe.whitelist()
def get_legal_desk_context(legal_case):
    if not legal_case:
        frappe.throw("Legal Case is required.")

    case_doc = frappe.get_doc("Legal Case", legal_case)
    timeline = get_legal_case_timeline(legal_case)

    notices = frappe.get_all(
        "Demand Notice",
        filters={"legal_case": legal_case},
        fields=["name", "notice_date", "status", "grand_total_due", "docstatus"],
        order_by="notice_date desc, modified desc",
    )

    return {
        "case": {
            "name": case_doc.name,
            "case_title": case_doc.case_title,
            "customer": case_doc.customer,
            "company": case_doc.company,
            "status": case_doc.status,
            "assigned_counsel": case_doc.assigned_counsel,
            "assigned_to": case_doc.assigned_to,
            "original_legal_amount": case_doc.original_legal_amount,
            "current_outstanding_balance": case_doc.current_outstanding_balance,
            "amount_recovered": case_doc.amount_recovered,
            "next_action_due_by": case_doc.next_action_due_by,
            "next_action_due_by_reason": case_doc.next_action_due_by_reason,
            "next_action_on_or_after": case_doc.next_action_on_or_after,
            "next_action_on_or_after_reason": case_doc.next_action_on_or_after_reason,
            "last_notice_date": case_doc.last_notice_date,
            "last_payment_date": case_doc.last_payment_date,
            "last_activity_date": case_doc.last_activity_date,
            "summary": case_doc.summary,
        },
        "timeline": timeline,
        "notices": notices,
    }


@frappe.whitelist()
def log_legal_case_action(legal_case, activity_type, remarks="", amount=0, activity_date=None):
    if not legal_case:
        frappe.throw("Legal Case is required.")
    if not activity_type:
        frappe.throw("Activity Type is required.")

    allowed_manual_actions = {
        "Call Made",
        "Visit Done",
        "Email Sent",
        "WhatsApp Sent",
        "Meeting Held",
        "Settlement Discussed",
        "Counsel Note Added",
    }
    if activity_type not in allowed_manual_actions:
        frappe.throw("Unsupported manual legal activity type.")

    activity_doc = frappe.get_doc(
        {
            "doctype": "Legal Case Activity",
            "legal_case": legal_case,
            "activity_type": activity_type,
            "activity_date": activity_date or today(),
            "amount": flt(amount),
            "remarks": remarks or "",
            "performed_by": frappe.session.user,
        }
    )
    activity_doc.insert(ignore_permissions=True)

    latest_activity_date = get_last_activity_date(legal_case)
    if latest_activity_date:
        frappe.db.set_value(
            "Legal Case",
            legal_case,
            "last_activity_date",
            latest_activity_date,
            update_modified=False,
        )

    return {"name": activity_doc.name}
