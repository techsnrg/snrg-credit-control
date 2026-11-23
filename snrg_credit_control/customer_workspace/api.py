"""Customer workspace API. Shared internal history; controlled mutations."""
import html
import re

import frappe
from frappe import _
from frappe.utils import now_datetime, today

MANAGER_ROLE = "Customer Workspace Manager"
INTERACTION = "Customer Interaction"
ACTION = "Customer Action"


def party_values(customer=None, supplier=None, optional=False):
    if optional and not customer and not supplier:
        return {"customer": None, "supplier": None, "customer_name": None, "supplier_name": None}
    if bool(customer) == bool(supplier):
        frappe.throw(_("Choose exactly one customer or supplier."))
    kind, name = ("Supplier", supplier) if supplier else ("Customer", customer)
    record = frappe.get_doc(kind, name)
    return {"customer": customer or None, "supplier": supplier or None,
            "customer_name": record.customer_name if customer else None,
            "supplier_name": record.supplier_name if supplier else None}


def present_action(row):
    row["party_type"] = "Supplier" if row.get("supplier") else "Customer" if row.get("customer") else "General"
    row["party"] = row.get("supplier") or row.get("customer")
    row["party_name"] = row.get("supplier_name") or row.get("customer_name") or "General task"
    return row


def manager(user=None):
    return bool(set(frappe.get_roles(user or frappe.session.user)) & {MANAGER_ROLE, "System Manager"})


def internal(user=None):
    user = user or frappe.session.user
    return user != "Guest" and bool(frappe.db.exists("User", {"name": user, "enabled": 1, "user_type": "System User"})) and (manager(user) or bool(frappe.db.exists("Employee", {"user_id": user, "status": "Active"})))


def guard():
    if not internal():
        frappe.throw(_("This workspace is for active internal team members."), frappe.PermissionError)


def permission(doc, user=None, permission_type=None, ptype=None, **kwargs):
    permission_type = permission_type or ptype
    user = user or frappe.session.user
    if not internal(user):
        return False
    if permission_type in ("read", "select", "report", "print"):
        return True
    if permission_type == "create":
        return True
    if permission_type == "write" and doc.doctype == ACTION:
        return manager(user) or user in (doc.owner, doc.assigned_to)
    return manager(user)


def query_conditions(user=None):
    return "" if internal(user) else "1=0"


def _directory():
    # Deliberately bypass Employee read permissions, projecting only directory fields.
    rows = frappe.get_all("Employee", filters={"status": "Active"}, fields=["name", "employee_name", "department", "company", "user_id"], order_by="employee_name asc", limit_page_length=0)
    enabled = set(frappe.get_all("User", filters={"enabled": 1, "user_type": "System User"}, pluck="name", limit_page_length=0))
    for row in rows:
        row.can_notify = bool(row.user_id and row.user_id in enabled)
    return rows


@frappe.whitelist()
def bootstrap():
    guard()
    from snrg_credit_control.customer_workspace.directory import filter_options
    from snrg_credit_control.customer_workspace.team_activity import allowed as activity_allowed
    from snrg_credit_control.customer_workspace.receivables import can_read, allowed_companies
    from snrg_credit_control.customer_workspace import payables
    from snrg_credit_control.customer_workspace.settings import allowed
    return {"user": frappe.session.user, "can_team_activity": activity_allowed(), "is_manager": manager(), "today": today(), "employees": _directory(), "can_ar": can_read(), "can_ar_detail": bool(can_read() and frappe.db.exists("Report", "Accounts Receivable") and not frappe.get_doc("Report", "Accounts Receivable").disabled and frappe.get_doc("Report", "Accounts Receivable").is_permitted()), "can_transactions": allowed("Transactions"), "can_ap": payables.can_read(), "can_ap_detail": payables.can_read_detail(), "ap_companies": payables.allowed_companies(), "companies": allowed_companies(), **filter_options()}


@frappe.whitelist()
def customers(search="", start=0):
    guard()
    from snrg_credit_control.customer_workspace.directory import customer_directory
    return customer_directory(search=search, start=start, status="all")["rows"]


@frappe.whitelist()
def actions(scope="mine", employee=None, customer=None, status="pending", start=0, supplier=None):
    guard()
    if scope not in ("mine", "assigned", "team", "customer"):
        frappe.throw(_("Invalid work view."))
    if scope == "team" and not manager():
        frappe.throw(_("Manager access required."), frappe.PermissionError)
    filters = {"status": ["in", ["Open", "In Progress"] if status == "pending" else ["Completed", "Cancelled"]]}
    if scope == "mine":
        filters["assigned_to"] = frappe.session.user
    elif scope == "assigned":
        filters["owner"] = frappe.session.user
    elif scope == "team" and employee:
        filters["assigned_to"] = employee
    if customer or supplier:
        party_values(customer, supplier)
        filters["supplier" if supplier else "customer"] = supplier or customer
    elif scope == "customer":
        frappe.throw(_("Choose a customer or supplier."))
    return [present_action(row) for row in frappe.get_all(ACTION, filters=filters, fields=["supplier", "supplier_name", "name", "customer", "customer_name", "subject", "assigned_to", "due_date", "due_time", "status", "action_type", "priority", "description", "whatsapp_summary", "interaction", "modified", "owner", "event"], order_by="due_date asc, due_time asc", start=max(0, int(start)), limit_page_length=100)]


@frappe.whitelist()
def history(customer=None, start=0, supplier=None):
    guard()
    party_values(customer, supplier)
    party_filter = {"supplier": supplier} if supplier else {"customer": customer}
    start = max(0, int(start))
    rows = frappe.get_all(INTERACTION, filters=party_filter, fields=["name", "summary", "channel", "contact_name", "spoken_by", "interaction_on", "owner", "creation", "action_reference"], order_by="interaction_on desc", start=start, limit_page_length=50)
    for row in rows:
        row.mentions = frappe.get_all("Customer Interaction Mention", filters={"parent": row.name, "parenttype": INTERACTION}, fields=["employee", "employee_name", "user"], limit_page_length=0)
    # Legacy calls are a separate paginated stream so neither history can starve the other.
    legacy = []
    if customer and frappe.db.exists("DocType", "Calls"):
        legacy = frappe.get_all("Calls", filters={"call_to": "Customer", "lead__party": customer}, fields=["name", "short_notes", "long_notes", "date", "call_time", "employee_id", "employee_name", "follow_up_date"], order_by="date desc, call_time desc", start=start, limit_page_length=50)
    return {"interactions": rows, "calls": legacy}


@frappe.whitelist(methods=["POST"])
def log_interaction(payload):
    guard()
    data = frappe.parse_json(payload)
    if not str(data.get("summary", "")).strip():
        if data.get("channel", "Call") == "Call" and data.get("call_outcome") in ("No answer", "Busy", "Call back", "Wrong number"):
            data["summary"] = data["call_outcome"]
        else:
            frappe.throw(_("Enter a discussion summary."))
    party = party_values(data.get("customer"), data.get("supplier"))
    spoken_by = data.get("spoken_by") or frappe.session.user
    if spoken_by != frappe.session.user and not manager():
        frappe.throw(_("Only managers may record a conversation on someone else's behalf."), frappe.PermissionError)
    if not internal(spoken_by):
        frappe.throw(_("Choose an active internal team member as the speaker."))
    from snrg_credit_control.customer_workspace.rich_text import attach_files, uploads
    files = uploads(data.get("attachments"))
    doc = frappe.get_doc({"doctype": INTERACTION, **party, "call_outcome": data.get("call_outcome") if data.get("channel", "Call") == "Call" else None, "summary_html": data.get("summary_html"), "summary": data["summary"].strip(), "channel": data.get("channel", "Call"), "contact_name": data.get("contact_name"), "spoken_by": spoken_by, "interaction_on": data.get("interaction_on") or now_datetime()})
    doc.flags.teamspace_uploads = files
    for employee in set(data.get("mentions") or []):
        doc.append("mentions", {"employee": employee})
    doc.insert(ignore_permissions=True)  # guard + controller validation enforce workspace policy
    attach_files(files, doc)
    created = []
    for item in data.get("actions") or []:
        created.extend(action.name for action in create_action_documents(item, party, interaction=doc.name))
    return {"name": doc.name, "actions": created}


def normalize_due_time(value):
    if value is None or value == "":
        return None
    match = re.fullmatch(r"([01]?[0-9]|2[0-3]):([0-5][0-9])(?::([0-5][0-9]))?", value) if isinstance(value, str) else None
    if not match:
        frappe.throw(_("Enter a valid due time in hours and minutes."))
    hour, minute, second = match.groups()
    return f"{int(hour):02d}:{minute}:{second or '00'}"


@frappe.whitelist()
def action_attachments(name):
    guard()
    from snrg_credit_control.customer_workspace.rich_text import attachment_rows

    doc = frappe.get_doc(ACTION, name)
    if not permission(doc, permission_type="read"):
        frappe.throw(_("You cannot view this action."), frappe.PermissionError)
    return attachment_rows(doc.name, ACTION)


@frappe.whitelist(methods=["POST"])
def update_action(name, payload, modified):
    guard()
    doc = frappe.get_doc(ACTION, name)
    if not permission(doc, permission_type="write"):
        frappe.throw(_("You cannot change this action."), frappe.PermissionError)
    from snrg_credit_control.customer_workspace.rich_text import attach_files, uploads

    data = frappe.parse_json(payload)
    # Let Frappe's save-time check catch edits since this read as well.
    if str(doc.modified) != str(modified):
        frappe.throw(_("This action changed. Refresh and try again."), frappe.TimestampMismatchError)
    doc.flags.workspace_update = True
    doc.flags.workspace_reason = str(data.get("update") or "").strip()
    for field in ("status", "due_date", "due_time", "assigned_to", "priority", "whatsapp_summary"):
        if field in data:
            if field in ("assigned_to", "whatsapp_summary") and data[field] != doc.get(field) and not (manager() or doc.owner == frappe.session.user):
                frappe.throw(_("Only the creator or a manager can change the assignment or its WhatsApp summary."), frappe.PermissionError)
            value = normalize_due_time(data[field]) if field == "due_time" else data[field]
            doc.set(field, value)
    files = uploads(data.get("attachments"))
    doc.save(ignore_permissions=True)
    attach_files(files, doc)
    return present_action(doc.as_dict())


def notify(users, subject, doctype, name, kind="Assignment", include_self=False, *, document=None, event="", changes=None, reason=None):
    from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
    users = sorted(set(u for u in users if u and (include_self or u != frappe.session.user) and internal(u)))
    if users:
        from snrg_credit_control.customer_workspace.notification_content import snapshot
        content = snapshot(document or frappe.get_doc(doctype, name), subject, kind=kind, event=event, changes=changes, reason=reason)
        enqueue_create_notification(users, {"type": kind, "document_type": doctype, "document_name": name, "from_user": None if include_self else frappe.session.user, **content})


@frappe.whitelist()
def personal_agenda():
    """All personal pending deadlines, so the calendar never hides later pages."""
    guard()
    return [present_action(row) for row in frappe.get_all(ACTION, filters={"assigned_to": frappe.session.user, "status": ["in", ["Open", "In Progress"]]}, fields=["supplier", "supplier_name", "name", "customer", "customer_name", "subject", "assigned_to", "due_date", "due_time", "status", "action_type", "priority", "description", "whatsapp_summary", "interaction", "modified", "owner", "event"], order_by="due_date asc, due_time asc", limit_page_length=0)]


@frappe.whitelist(methods=["POST"])
def create_action(payload):
    """Create a plan without fabricating a conversation."""
    guard()
    data = frappe.parse_json(payload)
    party = party_values(data.get("customer"), data.get("supplier"), optional=True)
    if not str(data.get("subject") or "").strip():
        frappe.throw(_("Enter what needs to happen."))
    docs = create_action_documents(data, party)
    result = present_action(docs[0].as_dict())
    result["actions"] = [doc.name for doc in docs]
    return result


def create_action_documents(data, party, interaction=None):
    """One authoritative task and calendar entry per recipient, atomically created."""
    recipients = data.get("assigned_users")
    if recipients is None:
        recipients = [data.get("assigned_to")]
    if not isinstance(recipients, list) or not 1 <= len(recipients) <= 20 or any(not isinstance(user, str) or not internal(user) for user in recipients):
        frappe.throw(_("Choose between 1 and 20 active internal team members."))
    recipients = list(dict.fromkeys(recipients))
    mentions = data.get("mentions") or []
    if not isinstance(mentions, list) or len(mentions) > 50 or any(not isinstance(employee, str) for employee in mentions):
        frappe.throw(_("Choose valid instruction mentions."))
    group = frappe.generate_hash(length=16) if len(recipients) > 1 else None
    docs = []
    for user in recipients:
        doc = frappe.get_doc({"doctype": ACTION, **party, "interaction": interaction,
            "assigned_to": user, "assignment_group": group,
            **{key: data.get(key) for key in ("subject", "due_date", "due_time", "action_type", "priority", "description", "whatsapp_summary") if data.get(key)}})
        for employee in dict.fromkeys(mentions):
            doc.append("mentions", {"employee": employee})
        doc.flags.defer_instruction_mentions = True
        doc.insert(ignore_permissions=True)
        docs.append(doc)
    notify([row.user for row in docs[0].get("mentions") or [] if row.user not in recipients], f"{frappe.utils.get_fullname()} mentioned you in a task: {docs[0].subject}", ACTION, docs[0].name, kind="Mention")
    return docs


@frappe.whitelist()
def employee_mentions(search_term=""):
    guard()
    query = str(search_term or "").casefold()
    return [{"id": row.name, "value": row.employee_name, "email": row.department or "", "can_notify": row.can_notify} for row in _directory() if query in (row.employee_name or "").casefold()]


@frappe.whitelist(methods=["GET", "POST"])
def open_task(name):
    guard()
    doc = frappe.get_doc(ACTION, name)
    if not permission(doc, permission_type="read"):
        frappe.throw(_("You cannot view this task."), frappe.PermissionError)
    return present_action(doc.as_dict())


@frappe.whitelist()
def linked_actions(name):
    guard()
    doc = frappe.get_doc(ACTION, name)
    if not permission(doc, permission_type="read"):
        frappe.throw(_("You cannot read this action."), frappe.PermissionError)
    if not doc.assignment_group:
        return []
    return [present_action(row) for row in frappe.get_all(ACTION, filters={"assignment_group": doc.assignment_group, "name": ["!=", doc.name]}, fields=["name", "subject", "customer", "customer_name", "supplier", "supplier_name", "assigned_to", "due_date", "due_time", "description", "whatsapp_summary", "status", "priority", "owner", "modified", "action_type"], limit_page_length=20)]
