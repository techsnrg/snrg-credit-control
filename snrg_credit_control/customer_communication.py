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


def build_reference_route(doctype, name):
    if not doctype or not name:
        return ""
    route_name = doctype.replace("_", "-").replace(" ", "-").lower()
    return f"/app/{route_name}/{name}"


def build_feed_row(
    *,
    name="",
    activity_type="",
    activity_date=None,
    display_timestamp=None,
    performed_by="",
    remarks="",
    amount=0,
    source_label="",
    reference_doctype="",
    reference_name="",
):
    return {
        "name": name,
        "activity_type": activity_type,
        "activity_date": activity_date,
        "display_timestamp": display_timestamp or activity_date,
        "performed_by": performed_by,
        "remarks": remarks,
        "amount": flt(amount),
        "source_label": source_label,
        "reference_doctype": reference_doctype or "",
        "reference_name": reference_name or "",
        "reference_route": build_reference_route(reference_doctype, reference_name),
    }


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


def get_customer_quotation_feed(customer):
    rows = frappe.get_all(
        "Quotation",
        filters={"quotation_to": "Customer", "party_name": customer, "docstatus": ("<", 2)},
        fields=[
            "name",
            "transaction_date",
            "creation",
            "docstatus",
            "status",
            "grand_total",
            "rounded_total",
            "owner",
        ],
        order_by="transaction_date desc, creation desc",
    )

    feed = []
    for row in rows:
        activity_type = "Quotation Submitted" if row.docstatus == 1 else "Quotation Drafted"
        remarks = f"Status: {row.status or 'Draft'}"
        feed.append(
            build_feed_row(
                name=row.name,
                activity_type=activity_type,
                activity_date=row.transaction_date,
                display_timestamp=row.creation or row.transaction_date,
                performed_by=row.owner,
                remarks=remarks,
                amount=row.grand_total or row.rounded_total,
                source_label="Quotation",
                reference_doctype="Quotation",
                reference_name=row.name,
            )
        )

    return feed


def get_customer_sales_invoice_feed(customer):
    rows = frappe.get_all(
        "Sales Invoice",
        filters={"customer": customer, "docstatus": ("<", 2)},
        fields=[
            "name",
            "posting_date",
            "creation",
            "docstatus",
            "status",
            "grand_total",
            "rounded_total",
            "outstanding_amount",
            "owner",
        ],
        order_by="posting_date desc, creation desc",
    )

    feed = []
    for row in rows:
        activity_type = "Sales Invoice Submitted" if row.docstatus == 1 else "Sales Invoice Drafted"
        detail_parts = [f"Status: {row.status or ('Draft' if row.docstatus == 0 else 'Submitted')}"]
        if flt(row.outstanding_amount):
            detail_parts.append(f"Outstanding: {frappe.utils.fmt_money(row.outstanding_amount)}")
        feed.append(
            build_feed_row(
                name=row.name,
                activity_type=activity_type,
                activity_date=row.posting_date,
                display_timestamp=row.creation or row.posting_date,
                performed_by=row.owner,
                remarks="\n".join(detail_parts),
                amount=row.grand_total or row.rounded_total,
                source_label="Sales Invoice",
                reference_doctype="Sales Invoice",
                reference_name=row.name,
            )
        )

    return feed


def get_customer_payment_feed(customer):
    rows = frappe.get_all(
        "Payment Entry",
        filters={
            "party_type": "Customer",
            "party": customer,
            "payment_type": "Receive",
            "docstatus": 1,
        },
        fields=[
            "name",
            "posting_date",
            "creation",
            "paid_amount",
            "received_amount",
            "mode_of_payment",
            "remarks",
            "owner",
        ],
        order_by="posting_date desc, creation desc",
    )

    feed = []
    for row in rows:
        remark_parts = []
        if row.mode_of_payment:
            remark_parts.append(f"Mode: {row.mode_of_payment}")
        if row.remarks:
            remark_parts.append(row.remarks)

        feed.append(
            build_feed_row(
                name=row.name,
                activity_type="Payment Received",
                activity_date=row.posting_date,
                display_timestamp=row.creation or row.posting_date,
                performed_by=row.owner,
                remarks="\n".join(remark_parts),
                amount=row.paid_amount or row.received_amount,
                source_label="Payment",
                reference_doctype="Payment Entry",
                reference_name=row.name,
            )
        )

    return feed


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
        feed.append(
            build_feed_row(
                name=row.get("name"),
                activity_type=row.get("communication_type"),
                activity_date=row.get("communication_at"),
                display_timestamp=row.get("communication_at") or row.get("creation"),
                performed_by=row.get("performed_by"),
                remarks=row.get("remarks"),
                source_label="Communication",
                reference_doctype=row.get("reference_doctype") or "",
                reference_name=row.get("reference_name") or "",
            )
        )

    feed.extend(get_customer_quotation_feed(customer))
    feed.extend(get_customer_sales_invoice_feed(customer))
    feed.extend(get_customer_payment_feed(customer))

    if legal_case:
        legal_rows = get_legal_case_timeline(legal_case)
        for row in legal_rows:
            if row.get("activity_type") in MANUAL_COMMUNICATION_TYPES:
                continue

            feed.append(
                build_feed_row(
                    name=row.get("name"),
                    activity_type=row.get("activity_type"),
                    activity_date=row.get("activity_date"),
                    display_timestamp=row.get("creation") or row.get("activity_date"),
                    performed_by=row.get("performed_by"),
                    remarks=row.get("remarks"),
                    amount=row.get("amount"),
                    source_label="Legal Workflow",
                    reference_doctype=row.get("reference_doctype") or "",
                    reference_name=row.get("reference_name") or "",
                )
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
