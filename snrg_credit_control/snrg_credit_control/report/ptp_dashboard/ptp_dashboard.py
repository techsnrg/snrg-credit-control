import frappe
from frappe.utils import add_days, getdate, today


def execute(filters=None):
    filters = frappe._dict(filters or {})
    rows = _get_rows(filters)
    chart = _get_chart(rows)
    summary = _get_summary(rows)
    return _get_columns(), rows, None, chart, summary


def _get_columns():
    return [
        {"label": "PTP", "fieldname": "name", "fieldtype": "Link", "options": "Credit PTP", "width": 150},
        {"label": "Sales Order", "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 150},
        {"label": "Customer", "fieldname": "customer_name", "fieldtype": "Data", "width": 220},
        {"label": "Committed By", "fieldname": "ptp_by_name", "fieldtype": "Data", "width": 170},
        {"label": "Commitment Date", "fieldname": "commitment_date", "fieldtype": "Date", "width": 120},
        {"label": "Bucket", "fieldname": "bucket", "fieldtype": "Data", "width": 160},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 130},
        {"label": "Committed Amount", "fieldname": "committed_amount", "fieldtype": "Currency", "width": 140},
        {"label": "Received Amount", "fieldname": "received_amount", "fieldtype": "Currency", "width": 140},
        {"label": "Difference Amount", "fieldname": "difference_amount", "fieldtype": "Currency", "width": 140},
        {"label": "Payment Mode", "fieldname": "payment_mode", "fieldtype": "Data", "width": 120},
        {"label": "Remarks", "fieldname": "remarks", "fieldtype": "Small Text", "width": 240},
    ]


def _get_rows(filters):
    report_filters = {}
    if filters.get("company"):
        report_filters["company"] = filters.company
    if filters.get("ptp_by"):
        report_filters["ptp_by"] = filters.ptp_by
    if filters.get("status"):
        report_filters["status"] = ["in", filters.status]

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
            "commitment_date",
            "status",
            "committed_amount",
            "received_amount",
            "difference_amount",
            "payment_mode",
            "remarks",
        ],
        order_by="commitment_date asc, modified desc",
    )

    today_date = getdate(today())
    week_end = add_days(today_date, 7)
    bucket_filter = filters.get("bucket")
    filtered_rows = []

    for row in rows:
        commitment_date = getdate(row.commitment_date) if row.commitment_date else None

        if row.status == "Partially Cleared":
            bucket = "Partially Cleared"
        elif not commitment_date:
            bucket = "No Date"
        elif commitment_date < today_date:
            bucket = "Overdue"
        elif commitment_date == today_date:
            bucket = "Due Today"
        elif commitment_date <= week_end:
            bucket = "Upcoming This Week"
        else:
            bucket = "Upcoming Later"

        row.bucket = bucket

        if bucket_filter and row.bucket != bucket_filter:
            continue
        filtered_rows.append(row)

    return filtered_rows


def _get_chart(rows):
    counts = {}
    order = ["Due Today", "Overdue", "Upcoming This Week", "Partially Cleared", "Upcoming Later", "No Date"]
    for row in rows:
        counts[row.bucket] = counts.get(row.bucket, 0) + 1

    labels = [label for label in order if counts.get(label)]
    values = [counts[label] for label in labels]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": "PTPs", "values": values}],
        },
        "type": "bar",
        "height": 260,
        "colors": ["#2563eb"],
    }


def _get_summary(rows):
    active_statuses = {"Pending", "Partially Cleared"}
    due_today = sum(1 for row in rows if row.bucket == "Due Today")
    overdue = sum(1 for row in rows if row.bucket == "Overdue")
    partially_cleared = sum(1 for row in rows if row.status == "Partially Cleared")
    committed = sum(frappe.utils.flt(row.committed_amount) for row in rows if row.status in active_statuses)
    received = sum(frappe.utils.flt(row.received_amount) for row in rows if row.status in active_statuses)
    difference = sum(frappe.utils.flt(row.difference_amount) for row in rows if row.status in active_statuses)
    active_count = sum(1 for row in rows if row.status in active_statuses)

    return [
        {"label": "Active PTPs", "value": active_count, "indicator": "Blue"},
        {"label": "Committed Amount", "value": committed, "indicator": "Blue", "datatype": "Currency"},
        {"label": "Received Amount", "value": received, "indicator": "Green", "datatype": "Currency"},
        {"label": "Difference Amount", "value": difference, "indicator": "Orange" if difference > 0 else "Green", "datatype": "Currency"},
        {"label": "Due Today", "value": due_today, "indicator": "Orange"},
        {"label": "Overdue", "value": overdue, "indicator": "Red"},
        {"label": "Partially Cleared", "value": partially_cleared, "indicator": "Teal"},
    ]
