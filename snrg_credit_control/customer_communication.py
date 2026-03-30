import frappe
from frappe import _
from frappe.utils import flt, get_datetime, now_datetime

from snrg_credit_control.legal_case import (
    add_legal_case_activity,
    get_active_legal_case,
    get_current_outstanding_balance,
    get_default_company,
    get_last_activity_date,
    get_last_notice_date,
    get_last_payment_date,
    get_legal_case_timeline,
)


MANUAL_COMMUNICATION_TYPES = {"Call", "Visit", "Email", "WhatsApp", "Notice"}


def get_last_customer_communication_at(customer):
    if not customer:
        return None

    return frappe.db.sql(
        """
        SELECT MAX(communication_at)
        FROM `tabCustomer Communication`
        WHERE customer = %s
        """,
        (customer,),
    )[0][0]


def build_customer_feed(customer, legal_case=None):
    customer_rows = frappe.get_all(
        "Customer Communication",
        filters={"customer": customer},
        fields=[
            "name",
            "customer",
            "company",
            "communication_type",
            "communication_at",
            "legal_case",
            "reference_doctype",
            "reference_name",
            "remarks",
            "performed_by",
            "creation",
        ],
        order_by="communication_at desc, creation desc",
    )

    feed = []
    for row in customer_rows:
        reference_route = ""
        if row.get("reference_doctype") and row.get("reference_name"):
            reference_route = f"/app/{frappe.scrub(row['reference_doctype'])}/{row['reference_name']}"

        feed.append(
            {
                "name": row.get("name"),
                "activity_type": row.get("communication_type"),
                "activity_date": row.get("communication_at"),
                "display_timestamp": row.get("communication_at") or row.get("creation"),
                "performed_by": row.get("performed_by"),
                "remarks": row.get("remarks"),
                "amount": 0,
                "source_label": "Communication",
                "reference_doctype": row.get("reference_doctype") or "",
                "reference_name": row.get("reference_name") or "",
                "reference_route": reference_route,
            }
        )

    if legal_case:
        legal_rows = get_legal_case_timeline(legal_case)
        for row in legal_rows:
            if row.get("activity_type") in MANUAL_COMMUNICATION_TYPES:
                continue

            feed.append(
                {
                    "name": row.get("name"),
                    "activity_type": row.get("activity_type"),
                    "activity_date": row.get("activity_date"),
                    "display_timestamp": row.get("creation") or row.get("activity_date"),
                    "performed_by": row.get("performed_by"),
                    "remarks": row.get("remarks"),
                    "amount": flt(row.get("amount")),
                    "source_label": "Legal Workflow",
                    "reference_doctype": row.get("reference_doctype") or "",
                    "reference_name": row.get("reference_name") or "",
                    "reference_route": row.get("reference_route") or "",
                }
            )

    return sorted(
        feed,
        key=lambda row: get_datetime(row.get("display_timestamp") or "1970-01-01 00:00:00"),
        reverse=True,
    )


@frappe.whitelist()
def get_customer_desk_context(customer):
    if not customer:
        frappe.throw(_("Customer is required."))

    legal_case = get_active_legal_case(customer)
    legal_case_doc = frappe.get_doc("Legal Case", legal_case) if legal_case else None
    company = legal_case_doc.company if legal_case_doc else get_default_company()

    timeline = build_customer_feed(customer, legal_case)
    last_communication_at = get_last_customer_communication_at(customer)

    return {
        "customer": {
            "name": customer,
            "display_name": frappe.db.get_value("Customer", customer, "customer_name") or customer,
            "company": company or "",
            "current_outstanding_balance": get_current_outstanding_balance(customer, company or ""),
            "last_payment_date": get_last_payment_date(customer, company or "", legal_case_doc.date_marked_legal if legal_case_doc else None),
            "last_communication_at": last_communication_at,
            "is_under_legal": 1 if legal_case_doc else 0,
        },
        "legal_case": (
            {
                "name": legal_case_doc.name,
                "case_title": legal_case_doc.case_title,
                "status": legal_case_doc.status,
                "assigned_counsel": legal_case_doc.assigned_counsel,
                "assigned_to": legal_case_doc.assigned_to,
                "original_legal_amount": legal_case_doc.original_legal_amount,
                "current_outstanding_balance": legal_case_doc.current_outstanding_balance,
                "amount_recovered": legal_case_doc.amount_recovered,
                "next_action_due_by": legal_case_doc.next_action_due_by,
                "next_action_due_by_reason": legal_case_doc.next_action_due_by_reason,
                "next_action_on_or_after": legal_case_doc.next_action_on_or_after,
                "next_action_on_or_after_reason": legal_case_doc.next_action_on_or_after_reason,
                "last_notice_date": get_last_notice_date(legal_case_doc.name),
                "last_payment_date": legal_case_doc.last_payment_date,
                "last_activity_date": get_last_activity_date(legal_case_doc.name),
                "summary": legal_case_doc.summary,
            }
            if legal_case_doc
            else None
        ),
        "timeline": timeline,
    }


@frappe.whitelist()
def log_customer_communication(customer, communication_type, remarks="", communication_at=None):
    if not customer:
        frappe.throw(_("Customer is required."))
    if communication_type not in MANUAL_COMMUNICATION_TYPES:
        frappe.throw(_("Unsupported communication type."))
    if not remarks:
        frappe.throw(_("Remarks are required."))

    legal_case = get_active_legal_case(customer)
    company = ""
    if legal_case:
        company = frappe.db.get_value("Legal Case", legal_case, "company") or ""
    if not company:
        company = get_default_company()

    communication_doc = frappe.get_doc(
        {
            "doctype": "Customer Communication",
            "customer": customer,
            "company": company,
            "communication_type": communication_type,
            "communication_at": communication_at or now_datetime(),
            "legal_case": legal_case or "",
            "remarks": remarks,
            "performed_by": frappe.session.user,
        }
    )
    communication_doc.insert(ignore_permissions=True)

    if legal_case:
        activity_date = get_datetime(communication_doc.communication_at).date()
        add_legal_case_activity(
            legal_case,
            communication_type,
            activity_date=activity_date,
            reference_doctype="Customer Communication",
            reference_name=communication_doc.name,
            remarks=remarks,
        )
        latest_activity_date = get_last_activity_date(legal_case)
        if latest_activity_date:
            frappe.db.set_value(
                "Legal Case",
                legal_case,
                "last_activity_date",
                latest_activity_date,
                update_modified=False,
            )

    return {"name": communication_doc.name}
