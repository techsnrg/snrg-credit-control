"""Private, read-only activity review. Every entry point checks the exact login."""
import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, getdate, get_datetime, today
from snrg_credit_control.customer_workspace.api import guard

VIEWER = "nikhil@snrgindia.com"
KINDS = ("Interaction", "Calls", "Connected calls", "Task created", "Task completed")
OUTCOMES = ("Connected", "No answer", "Busy", "Call back", "Wrong number")
LIMIT = 10000


def allowed():
    return frappe.session.user == VIEWER


def check_access():
    guard()
    if not allowed():
        frappe.throw(_("Team activity is available only to the designated account."), frappe.PermissionError)


def _options(from_date=None, to_date=None, user=None, activity_type=None, party_type=None, search=None, call_outcome=None):
    start, end = getdate(from_date or today()), getdate(to_date or today())
    if start > end or date_diff(end, start) > 92:
        frappe.throw(_("Choose a date range of up to 93 days, with the start before the end."))
    if activity_type and activity_type not in KINDS:
        frappe.throw(_("Choose a valid activity type."))
    if party_type and party_type not in ("Customer", "Supplier", "General"):
        frappe.throw(_("Choose a valid relationship type."))
    if call_outcome and call_outcome not in OUTCOMES:
        frappe.throw(_("Choose a valid call outcome."))
    return dict(start=str(start), end=str(end), until=str(add_days(end, 1)), user=user or "", activity_type=activity_type or "", party_type=party_type or "", search=str(search or "").strip().casefold()[:100], call_outcome=call_outcome or "")


def _read(doctype, fields, filters):
    rows = frappe.get_all(doctype, fields=fields, filters=filters, order_by="creation desc, name desc", limit_page_length=LIMIT + 1)
    if len(rows) > LIMIT:
        frappe.throw(_("Too many entries. Choose a shorter date range."))
    return rows


def _party(row):
    return dict(party_type="Supplier" if row.get("supplier") else "Customer" if row.get("customer") else "General", party=row.get("supplier") or row.get("customer") or "", party_name=row.get("supplier_name") or row.get("customer_name") or row.get("supplier") or row.get("customer") or "General task")


def _entries(options):
    period = [["creation", ">=", options["start"]], ["creation", "<", options["until"]]]
    entries = []
    interactions = _read("Customer Interaction", ["name", "creation", "owner", "customer", "customer_name", "supplier", "supplier_name", "summary", "channel", "call_outcome", "spoken_by", "interaction_on", "action_reference"], period)
    for row in interactions:
        if row.action_reference:  # Automatically generated task updates aren't conversations.
            continue
        entries.append(dict(key="interaction:" + row.name, doctype="Customer Interaction", name=row.name, timestamp=str(row.creation), actor=row.owner, logged_by=row.owner, spoken_by=row.spoken_by, happened_on=str(row.interaction_on), activity_type="Interaction", summary=row.summary, channel=row.channel, call_outcome=row.call_outcome or "", assigned_to="", due_date="", status="", **_party(row)))
    fields = ["name", "creation", "owner", "customer", "customer_name", "supplier", "supplier_name", "subject", "description", "assigned_to", "due_date", "status"]
    tasks = _read("Customer Action", fields, period)
    for row in tasks:
        entries.append(dict(key="created:" + row.name, doctype="Customer Action", name=row.name, timestamp=str(row.creation), actor=row.owner, logged_by=row.owner, spoken_by="", happened_on="", activity_type="Task created", summary=row.subject, instructions=row.description or "", channel="", call_outcome="", assigned_to=row.assigned_to, due_date=str(row.due_date or ""), status=row.status, **_party(row)))
    # Version records preserve who completed the task, even if someone edits it later
    # or reopens it. Never attribute completion to the current assignee/modified_by.
    versions = _read("Version", ["name", "creation", "owner", "docname", "data"], period + [["ref_doctype", "=", "Customer Action"]])
    completions = []
    for version in versions:
        try:
            data = json.loads(version.data or "{}")
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if any(isinstance(change, list) and len(change) >= 3 and change[0] == "status" and change[1] != "Completed" and change[2] == "Completed" for change in data.get("changed", [])):
            completions.append(version)
    task_names = list({v.docname for v in completions})
    records = {row.name: row for row in frappe.get_all("Customer Action", fields=fields, filters={"name": ["in", task_names]}, limit_page_length=0)} if task_names else {}
    for version in completions:
        row = records.get(version.docname)
        if not row:  # Deleted records cannot be reviewed reliably.
            continue
        entries.append(dict(key="completed:" + version.name, doctype="Customer Action", name=row.name, timestamp=str(version.creation), actor=version.owner, logged_by=row.owner, spoken_by="", happened_on="", activity_type="Task completed", summary=row.subject, instructions=row.description or "", channel="", call_outcome="", assigned_to=row.assigned_to, due_date=str(row.due_date or ""), status=row.status, **_party(row)))
    if len(entries) > LIMIT:
        frappe.throw(_("Too many entries. Choose a shorter date range."))
    return entries


def _report(options):
    entries = _entries(options)
    users = {row.name: row.full_name or row.name for row in frappe.get_all("User", fields=["name", "full_name"], limit_page_length=0)}
    people = {row.user_id: row.employee_name for row in frappe.get_all("Employee", filters={"status": "Active", "user_id": ["is", "set"]}, fields=["user_id", "employee_name"], limit_page_length=0)}
    for entry in entries:
        people.setdefault(entry["actor"], users.get(entry["actor"], entry["actor"]))
    rows = []
    for row in entries:
        if options["user"] and row["actor"] != options["user"]:
            continue
        kind = options["activity_type"]
        if kind in ("Calls", "Connected calls"):
            if row["activity_type"] != "Interaction" or row["channel"] != "Call" or (kind == "Connected calls" and row["call_outcome"] != "Connected"):
                continue
        elif kind and row["activity_type"] != kind:
            continue
        if options["party_type"] and row["party_type"] != options["party_type"]:
            continue
        if options["search"] and options["search"] not in (row["party"] + " " + row["party_name"]).casefold():
            continue
        if options["call_outcome"] and (row["channel"] != "Call" or row["call_outcome"] != options["call_outcome"]):
            continue
        row.update(actor_name=people.get(row["actor"], users.get(row["actor"], row["actor"])), logged_by_name=users.get(row["logged_by"], row["logged_by"]), assigned_to_name=users.get(row["assigned_to"], row["assigned_to"]), spoken_by_name=users.get(row["spoken_by"], row["spoken_by"]))
        rows.append(row)
    rows.sort(key=lambda row: (get_datetime(row["timestamp"]), row["key"]), reverse=True)
    summary = {user: dict(user=user, name=name, interactions=0, calls=0, connected=0, created=0, completed=0) for user, name in people.items() if not options["user"] or user == options["user"]}
    for row in rows:
        counts = summary[row["actor"]]
        if row["activity_type"] == "Interaction":
            counts["interactions"] += 1
            counts["calls"] += int(row["channel"] == "Call")
            counts["connected"] += int(row["channel"] == "Call" and row["call_outcome"] == "Connected")
        else:
            counts["created" if row["activity_type"] == "Task created" else "completed"] += 1
    return dict(rows=rows, summary=sorted(summary.values(), key=lambda row: row["name"].casefold()), people=[dict(user=user, name=name) for user, name in sorted(people.items(), key=lambda pair: pair[1].casefold())])


@frappe.whitelist()
def report(from_date=None, to_date=None, user=None, activity_type=None, party_type=None, search=None, call_outcome=None, start=0):
    check_access()
    options = _options(from_date, to_date, user, activity_type, party_type, search, call_outcome)
    result = _report(options)
    offset = max(0, cint(start))
    rows = result.pop("rows")
    return dict(**result, rows=rows[offset:offset + 50], count=len(rows), start=offset, has_more=len(rows) > offset + 50)


def _excel_text(value):
    text = str(value or "")
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


@frappe.whitelist()
def export(from_date=None, to_date=None, user=None, activity_type=None, party_type=None, search=None, call_outcome=None):
    check_access()
    from frappe.utils.xlsxutils import make_xlsx
    options = _options(from_date, to_date, user, activity_type, party_type, search, call_outcome)
    result = _report(options)
    summary = [["Team member", "Login", "Interactions", "Calls attempted", "Connected", "Tasks created", "Task completions"]] + [[row[key] for key in ("name", "user", "interactions", "calls", "connected", "created", "completed")] for row in result["summary"]]
    keys = ("timestamp", "activity_type", "actor_name", "actor", "logged_by_name", "spoken_by_name", "party_type", "party_name", "party", "summary", "channel", "call_outcome", "assigned_to_name", "due_date", "status", "name", "instructions")
    detail = [["Recorded at", "Activity", "Actor", "Actor login", "Task creator / logged by", "Spoke with customer", "Relationship", "Customer / supplier", "Code", "Summary", "Channel", "Call outcome", "Responsible member (current)", "Due date (current)", "Status (current)", "Record", "Instructions"]] + [[_excel_text(row.get(key)) for key in keys] for row in result["rows"]]
    workbook = make_xlsx([[_excel_text(cell) if isinstance(cell, str) else cell for cell in row] for row in summary], "Summary")
    workbook.seek(0)
    import openpyxl
    book = openpyxl.load_workbook(workbook)
    sheet = book.create_sheet("Entries")
    for row in detail:
        sheet.append(row)
    from io import BytesIO
    output = BytesIO()
    book.save(output)
    frappe.response.update(filename="team-activity-" + options["start"] + ".xlsx", filecontent=output.getvalue(), type="binary")
