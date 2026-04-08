import calendar

import frappe
from frappe.utils import add_days, cint, flt, formatdate, fmt_money, get_datetime, get_url_to_form, getdate, today

from snrg_credit_control.credit_status import zero


ACTIVE_PTP_STATUSES = {"Pending", "Partially Cleared"}
ACTIONABLE_PTP_STATUSES = ACTIVE_PTP_STATUSES | {"Broken"}
SECTION_ROW_LIMIT = 6


def val(value):
    return zero(value)


def build_ptp_reference_label(doc):
    parts = []
    if doc.get("ptp_by_name"):
        parts.append(doc.ptp_by_name)
    if doc.get("commitment_date"):
        parts.append(str(doc.commitment_date))
    if doc.get("committed_amount"):
        parts.append(fmt_money(val(doc.committed_amount), currency=doc.get("currency") or "INR"))
    return " | ".join(parts) or (doc.get("name") or "PTP")


def sync_credit_ptp(doc):
    payment_totals = {}
    payment_amount_totals = {}
    links = list(doc.get("payment_links") or [])

    for link in links:
        pe = frappe.db.get_value(
            "Payment Entry",
            link.payment_entry,
            ["posting_date", "paid_amount", "docstatus", "party_type", "party", "company"],
            as_dict=True,
        ) or {}
        if not pe:
            frappe.throw(f"Payment Entry {link.payment_entry} was not found.")
        if pe.get("docstatus") != 1:
            frappe.throw(f"Payment Entry {link.payment_entry} must be submitted before it can be linked to a PTP.")
        if pe.get("party_type") != "Customer" or pe.get("party") != doc.customer:
            frappe.throw(f"Payment Entry {link.payment_entry} must belong to customer {doc.customer}.")
        if pe.get("company") != doc.company:
            frappe.throw(f"Payment Entry {link.payment_entry} must belong to company {doc.company}.")

        link.posting_date = pe.get("posting_date")
        link.payment_entry_amount = val(pe.get("paid_amount"))
        link.allocated_amount = val(link.allocated_amount or link.payment_entry_amount)

        if link.allocated_amount <= 0:
            frappe.throw(f"Allocated amount for Payment Entry {link.payment_entry} must be greater than zero.")
        if link.allocated_amount > link.payment_entry_amount:
            frappe.throw(
                f"Allocated amount for Payment Entry {link.payment_entry} cannot exceed the Payment Entry amount."
            )

        payment_amount_totals[link.payment_entry] = payment_amount_totals.get(link.payment_entry, 0) + link.allocated_amount
        if payment_amount_totals[link.payment_entry] > link.payment_entry_amount:
            frappe.throw(
                f"Total allocated amount for Payment Entry {link.payment_entry} across this PTP "
                "cannot exceed the Payment Entry amount."
            )

        payment_totals.setdefault("received", 0)
        payment_totals["received"] += link.allocated_amount

    received = val(payment_totals.get("received"))
    committed = val(doc.committed_amount)
    difference = committed - received

    doc.received_amount = received
    doc.difference_amount = difference
    doc.linked_payment_entries = ", ".join(sorted({link.payment_entry for link in links if link.payment_entry}))

    if committed and received >= committed:
        doc.status = "Cleared"
    elif received > 0:
        doc.status = "Partially Cleared"
    elif doc.commitment_date and getdate(doc.commitment_date) < getdate(today()):
        doc.status = "Broken"
    elif doc.status == "Superseded":
        pass
    else:
        doc.status = "Pending"


def supersede_previous_ptps(current_doc):
    if current_doc.get("status") not in ACTIVE_PTP_STATUSES:
        return

    others = frappe.get_all(
        "Credit PTP",
        filters={
            "sales_order": current_doc.sales_order,
            "name": ["!=", current_doc.name],
            "status": ["in", list(ACTIVE_PTP_STATUSES)],
        },
        fields=["name", "calendar_event"],
        order_by="creation desc",
    )
    for row in others:
        frappe.db.set_value("Credit PTP", row.name, "status", "Superseded", update_modified=False)
        if row.get("calendar_event") and frappe.db.exists("Event", row.calendar_event):
            _update_ptp_event_status(row.calendar_event, "Cancelled")


def get_ptp_references_for_sales_order(sales_order, actionable_only=False):
    filters = {"sales_order": sales_order}
    if actionable_only:
        filters["status"] = ["in", list(ACTIVE_PTP_STATUSES)]
    else:
        filters["status"] = ["!=", "Superseded"]

    rows = frappe.get_all(
        "Credit PTP",
        filters=filters,
        fields=[
            "name",
            "ptp_by_name",
            "commitment_date",
            "committed_amount",
            "received_amount",
            "difference_amount",
            "status",
            "currency",
        ],
        order_by="creation desc",
    )

    refs = []
    for row in rows:
        row_doc = frappe._dict(row)
        refs.append(
            {
                "ptp_entry_id": row.name,
                "label": build_ptp_reference_label(row_doc),
                "committed_amount": val(row.committed_amount),
                "received_amount": val(row.received_amount),
                "difference_amount": val(row.difference_amount or row.committed_amount),
                "status": row.status or "Pending",
            }
        )
    return refs


def get_sales_order_ptp_docs(sales_order, include_superseded=False):
    filters = {"sales_order": sales_order}
    if not include_superseded:
        filters["status"] = ["!=", "Superseded"]
    return frappe.get_all(
        "Credit PTP",
        filters=filters,
        fields=[
            "name",
            "ptp_by_name",
            "ptp_date",
            "commitment_date",
            "committed_amount",
            "received_amount",
            "difference_amount",
            "payment_mode",
            "status",
            "remarks",
            "linked_payment_entries",
        ],
        order_by="creation desc",
    )


def get_active_credit_ptp(sales_order):
    return frappe.get_all(
        "Credit PTP",
        filters={"sales_order": sales_order, "status": ["in", list(ACTIVE_PTP_STATUSES)]},
        fields=["name"],
        order_by="creation desc",
        limit=1,
    )


def get_employee_notification_target(employee):
    if not employee:
        return {}

    row = frappe.db.get_value(
        "Employee",
        employee,
        ["employee_name", "user_id", "company_email", "personal_email"],
        as_dict=True,
    ) or {}

    user_id = row.get("user_id")
    email = (user_id if user_id and "@" in user_id else None) or row.get("company_email") or row.get("personal_email")

    return {
        "employee": employee,
        "employee_name": row.get("employee_name") or employee,
        "user_id": user_id,
        "email": email,
    }


def sync_ptp_calendar_event(doc):
    event_name = doc.get("calendar_event")
    target = get_employee_notification_target(doc.get("ptp_by"))
    target_user = target.get("user_id")

    if not target_user or not doc.get("commitment_date"):
        if event_name and frappe.db.exists("Event", event_name):
            _update_ptp_event_status(event_name, "Cancelled")
        if doc.get("calendar_event"):
            frappe.db.set_value("Credit PTP", doc.name, "calendar_event", "", update_modified=False)
            doc.calendar_event = ""
        return

    event_doc = _build_ptp_event_doc(doc, target)

    if event_name and frappe.db.exists("Event", event_name):
        event = frappe.get_doc("Event", event_name)
        for fieldname, value in event_doc.items():
            event.set(fieldname, value)
        event.save(ignore_permissions=True)
        frappe.db.set_value("Event", event.name, "owner", target_user, update_modified=False)
        return

    event = frappe.get_doc(event_doc).insert(ignore_permissions=True)
    frappe.db.set_value("Event", event.name, "owner", target_user, update_modified=False)
    frappe.db.set_value("Credit PTP", doc.name, "calendar_event", event.name, update_modified=False)
    frappe.share.add_docshare("Event", event.name, target_user, read=1, write=1, share=0, notify=0)
    doc.calendar_event = event.name


def clear_ptp_calendar_event(doc):
    event_name = doc.get("calendar_event")
    if event_name and frappe.db.exists("Event", event_name):
        _update_ptp_event_status(event_name, "Cancelled")


def _build_ptp_event_doc(doc, target):
    customer_label = doc.get("customer_name") or doc.get("customer") or "Customer"
    subject = f"PTP Follow-up: {customer_label}"
    if doc.get("sales_order"):
        subject = f"{subject} / {doc.sales_order}"

    status = "Open" if doc.get("status") in ACTIVE_PTP_STATUSES or doc.get("status") == "Broken" else "Closed"
    start_dt = get_datetime(f"{doc.commitment_date} 09:00:00")
    description = (
        f"Credit PTP: {doc.name}\n"
        f"Sales Order: {doc.get('sales_order') or '—'}\n"
        f"Customer: {customer_label}\n"
        f"Committed By: {target.get('employee_name') or doc.get('ptp_by') or '—'}\n"
        f"Committed Amount: {fmt_money(val(doc.get('committed_amount')), currency=doc.get('currency') or 'INR')}\n"
        f"Status: {doc.get('status') or 'Pending'}\n"
        f"Open PTP: {get_url_to_form('Credit PTP', doc.name)}"
    )

    return {
        "doctype": "Event",
        "subject": subject,
        "event_type": "Private",
        "event_category": "Event",
        "status": status,
        "starts_on": start_dt,
        "all_day": 1,
        "description": description,
        "reference_doctype": "Credit PTP",
        "reference_docname": doc.name,
        "event_participants": _build_ptp_event_participants(target),
    }


def _update_ptp_event_status(event_name, status):
    event = frappe.get_doc("Event", event_name)
    if event.status == status:
        return
    event.status = status
    event.save(ignore_permissions=True)


def _build_ptp_event_participants(target):
    if not target:
        return []

    participant_id = target.get("user_id") or target.get("employee")
    if not participant_id:
        return []

    return [
        {
            "reference_doctype": "User" if target.get("user_id") else "Employee",
            "reference_docname": participant_id,
            "email": target.get("email"),
        }
    ]


@frappe.whitelist()
def get_ptp_dashboard_data(filters=None, calendar_month=None):
    rows = get_ptp_dashboard_rows(filters)
    month_anchor = getdate(calendar_month) if calendar_month else getdate(today())
    return {
        "summary": get_ptp_dashboard_summary(rows),
        "sections": get_ptp_dashboard_sections(rows),
        "queue": [serialize_ptp_dashboard_row(row) for row in rows],
        "calendar": build_ptp_calendar_payload(rows, month_anchor),
    }


def get_ptp_dashboard_rows(filters=None):
    filters = _normalize_dashboard_filters(filters)
    report_filters = {}
    if filters.get("company"):
        report_filters["company"] = filters.company
    if filters.get("ptp_by"):
        report_filters["ptp_by"] = filters.ptp_by
    if filters.get("requested_to_employee"):
        report_filters["requested_to_employee"] = filters.requested_to_employee
    if filters.get("status"):
        status_values = list(filters.status)
        if not filters.get("show_superseded"):
            status_values = [value for value in status_values if value != "Superseded"]
        if status_values:
            report_filters["status"] = ["in", status_values]
        elif not filters.get("show_superseded"):
            report_filters["status"] = ["!=", "Superseded"]
    elif not filters.get("show_superseded"):
        report_filters["status"] = ["!=", "Superseded"]

    rows = frappe.get_all(
        "Credit PTP",
        filters=report_filters,
        fields=[
            "name",
            "sales_order",
            "customer",
            "customer_name",
            "company",
            "ptp_by",
            "ptp_by_name",
            "requested_to_employee",
            "commitment_date",
            "status",
            "committed_amount",
            "received_amount",
            "difference_amount",
            "payment_mode",
            "calendar_event",
            "remarks",
        ],
        order_by="commitment_date asc, modified desc",
    )

    employee_ids = {row.ptp_by for row in rows if row.get("ptp_by")}
    employee_ids.update({row.requested_to_employee for row in rows if row.get("requested_to_employee")})
    employee_meta_map = _get_employee_meta_map(employee_ids)

    today_date = getdate(today())
    week_end = add_days(today_date, 7)
    bucket_filter = filters.get("bucket")
    from_date = getdate(filters.from_date) if filters.get("from_date") else None
    to_date = getdate(filters.to_date) if filters.get("to_date") else None
    filtered_rows = []

    for row in rows:
        row = frappe._dict(row)
        row.committed_amount = flt(row.committed_amount)
        row.received_amount = flt(row.received_amount)
        row.difference_amount = flt(row.difference_amount)
        row.commitment_date = getdate(row.commitment_date) if row.commitment_date else None
        row.bucket = _get_ptp_bucket(row, today_date, week_end)
        row.ptp_by_name = row.ptp_by_name or employee_meta_map.get(row.ptp_by, {}).get("employee_name")
        row.requested_to_employee_name = employee_meta_map.get(row.requested_to_employee, {}).get("employee_name")
        row.ptp_user_id = employee_meta_map.get(row.ptp_by, {}).get("user_id")
        row.requested_to_user_id = employee_meta_map.get(row.requested_to_employee, {}).get("user_id")
        row.has_event = bool(row.calendar_event)
        row.has_user_mapping = bool(row.ptp_user_id)
        row.issue_flags = _get_ptp_issue_flags(row)

        if bucket_filter and row.bucket != bucket_filter:
            continue
        if from_date and row.commitment_date and row.commitment_date < from_date:
            continue
        if to_date and row.commitment_date and row.commitment_date > to_date:
            continue
        filtered_rows.append(row)

    return filtered_rows


def get_ptp_dashboard_summary(rows):
    active_rows = [row for row in rows if row.status in ACTIVE_PTP_STATUSES]
    actionable_rows = [row for row in rows if row.status in ACTIONABLE_PTP_STATUSES]
    active_count = len(active_rows)
    due_today = sum(1 for row in actionable_rows if row.bucket == "Due Today")
    due_tomorrow = sum(1 for row in actionable_rows if row.commitment_date == add_days(getdate(today()), 1))
    overdue = sum(1 for row in actionable_rows if row.bucket == "Overdue")
    broken = sum(1 for row in rows if row.status == "Broken")
    partially_cleared = sum(1 for row in rows if row.status == "Partially Cleared")
    committed = sum(row.committed_amount for row in active_rows)
    received = sum(row.received_amount for row in active_rows)
    difference = sum(row.difference_amount for row in active_rows)

    return {
        "active_ptps": active_count,
        "due_today": due_today,
        "due_tomorrow": due_tomorrow,
        "overdue": overdue,
        "broken": broken,
        "partially_cleared": partially_cleared,
        "committed_amount": committed,
        "received_amount": received,
        "difference_amount": difference,
    }


def get_ptp_dashboard_sections(rows):
    actionable_rows = [row for row in rows if row.status in ACTIONABLE_PTP_STATUSES]
    due_today_rows = [row for row in actionable_rows if row.bucket == "Due Today"]
    overdue_rows = [row for row in actionable_rows if row.bucket == "Overdue"]
    upcoming_rows = [row for row in actionable_rows if row.bucket == "Upcoming This Week"]
    exception_rows = [row for row in actionable_rows if row.issue_flags]

    return {
        "due_today": [serialize_ptp_dashboard_row(row) for row in due_today_rows[:SECTION_ROW_LIMIT]],
        "overdue": [serialize_ptp_dashboard_row(row) for row in overdue_rows[:SECTION_ROW_LIMIT]],
        "upcoming_this_week": [serialize_ptp_dashboard_row(row) for row in upcoming_rows[:SECTION_ROW_LIMIT]],
        "exceptions": [serialize_ptp_dashboard_row(row) for row in exception_rows[:SECTION_ROW_LIMIT]],
        "exception_counts": {
            "broken": sum(1 for row in rows if row.status == "Broken"),
            "missing_event": sum(1 for row in rows if "No Event" in row.issue_flags),
            "missing_user_mapping": sum(1 for row in rows if "Missing User Mapping" in row.issue_flags),
        },
    }


def build_ptp_calendar_payload(rows, month_anchor):
    month_anchor = getdate(month_anchor)
    month_start = month_anchor.replace(day=1)
    _, month_last_day = calendar.monthrange(month_start.year, month_start.month)
    month_end = month_start.replace(day=month_last_day)

    entries = []
    for row in rows:
        if row.status not in ACTIONABLE_PTP_STATUSES:
            continue
        if not row.commitment_date:
            continue
        if row.commitment_date < month_start or row.commitment_date > month_end:
            continue
        entries.append(
            {
                "date": str(row.commitment_date),
                "ptp": row.name,
                "sales_order": row.sales_order,
                "customer_name": row.customer_name or row.customer,
                "status": row.status,
                "bucket": row.bucket,
                "committed_amount": row.committed_amount,
                "calendar_event": row.calendar_event,
            }
        )

    return {
        "month": month_start.month,
        "year": month_start.year,
        "month_start": str(month_start),
        "month_label": formatdate(month_start, "MMMM yyyy"),
        "entries": entries,
    }


def serialize_ptp_dashboard_row(row):
    return {
        "name": row.name,
        "sales_order": row.sales_order,
        "customer": row.customer,
        "customer_name": row.customer_name,
        "company": row.company,
        "ptp_by": row.ptp_by,
        "ptp_by_name": row.ptp_by_name,
        "requested_to_employee": row.requested_to_employee,
        "requested_to_employee_name": row.requested_to_employee_name,
        "commitment_date": str(row.commitment_date) if row.commitment_date else "",
        "status": row.status,
        "bucket": row.bucket,
        "committed_amount": row.committed_amount,
        "received_amount": row.received_amount,
        "difference_amount": row.difference_amount,
        "payment_mode": row.payment_mode,
        "calendar_event": row.calendar_event,
        "remarks": row.remarks,
        "issue_flags": row.issue_flags,
    }


def _normalize_dashboard_filters(filters):
    filters = frappe.parse_json(filters) if isinstance(filters, str) else filters
    filters = frappe._dict(filters or {})
    status = filters.get("status")
    if status:
        if isinstance(status, str):
            filters.status = [status]
        else:
            filters.status = [value for value in status if value]
    else:
        filters.status = []
    from_date, to_date = _extract_date_range(filters.get("date_range"))
    if from_date and not filters.get("from_date"):
        filters.from_date = from_date
    if to_date and not filters.get("to_date"):
        filters.to_date = to_date
    filters.show_superseded = cint(filters.get("show_superseded")) if filters.get("show_superseded") is not None else 0
    return filters


def _get_ptp_bucket(row, today_date, week_end):
    if row.status == "Partially Cleared":
        return "Partially Cleared"
    if not row.commitment_date:
        return "No Date"
    if row.commitment_date < today_date:
        return "Overdue"
    if row.commitment_date == today_date:
        return "Due Today"
    if row.commitment_date <= week_end:
        return "Upcoming This Week"
    return "Upcoming Later"


def _get_ptp_issue_flags(row):
    issues = []
    if row.status == "Broken":
        issues.append("Broken")
    if row.status in ACTIVE_PTP_STATUSES and not row.has_event:
        issues.append("No Event")
    if row.status in ACTIVE_PTP_STATUSES and not row.has_user_mapping:
        issues.append("Missing User Mapping")
    return issues


def _get_employee_meta_map(employee_ids):
    employee_ids = [employee for employee in employee_ids if employee]
    if not employee_ids:
        return {}

    rows = frappe.get_all(
        "Employee",
        filters={"name": ["in", employee_ids]},
        fields=["name", "user_id", "employee_name"],
    )
    return {
        row.name: {
            "user_id": row.user_id,
            "employee_name": row.employee_name,
        }
        for row in rows
    }


def _extract_date_range(value):
    if not value:
        return None, None

    if isinstance(value, (list, tuple)) and len(value) >= 2:
        start = getdate(value[0]) if value[0] else None
        end = getdate(value[1]) if value[1] else None
        return start, end

    if isinstance(value, dict):
        start = value.get("from") or value.get("from_date") or value.get("start")
        end = value.get("to") or value.get("to_date") or value.get("end")
        return (getdate(start) if start else None, getdate(end) if end else None)

    if isinstance(value, str):
        for separator in [",", " to ", " - ", "|"]:
            if separator in value:
                parts = [part.strip() for part in value.split(separator) if part.strip()]
                if len(parts) >= 2:
                    return getdate(parts[0]), getdate(parts[1])
        try:
            parsed = frappe.parse_json(value)
        except Exception:
            parsed = None
        if parsed:
            return _extract_date_range(parsed)

    return None, None
