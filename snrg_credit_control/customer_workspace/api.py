"""Customer workspace API. Shared internal history; controlled mutations."""
import html

import frappe
from frappe import _
from frappe.utils import now_datetime, today

MANAGER_ROLE = "Customer Workspace Manager"
INTERACTION = "Customer Interaction"
ACTION = "Customer Action"


def manager(user=None):
    return bool(set(frappe.get_roles(user or frappe.session.user)) & {MANAGER_ROLE, "System Manager"})


def internal(user=None):
    user = user or frappe.session.user
    return user != "Guest" and bool(frappe.db.exists("User", {"name": user, "enabled": 1, "user_type": "System User"})) and (manager(user) or bool(frappe.db.exists("Employee", {"user_id": user, "status": "Active"})))


def guard():
    if not internal():
        frappe.throw(_("This workspace is for active internal employees."), frappe.PermissionError)


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
    return {"user": frappe.session.user, "is_manager": manager(), "today": today(), "employees": _directory()}


@frappe.whitelist()
def customers(search="", start=0):
    guard()
    return frappe.get_all("Customer", or_filters={"name": ["like", f"%{search}%"], "customer_name": ["like", f"%{search}%"]}, fields=["name", "customer_name", "territory", "mobile_no", "customer_primary_contact"], order_by="customer_name asc", start=max(0, int(start)), limit_page_length=50)


@frappe.whitelist()
def actions(scope="mine", employee=None, customer=None, status="pending", start=0):
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
    if customer:
        filters["customer"] = customer
    elif scope == "customer":
        frappe.throw(_("Choose a customer."))
    return frappe.get_all(ACTION, filters=filters, fields=["name", "customer", "customer_name", "subject", "assigned_to", "due_date", "due_time", "status", "action_type", "priority", "description", "interaction", "modified", "owner", "event"], order_by="due_date asc, due_time asc", start=max(0, int(start)), limit_page_length=100)


@frappe.whitelist()
def history(customer, start=0):
    guard()
    frappe.get_doc("Customer", customer)  # validate existence without exposing the full record
    start = max(0, int(start))
    rows = frappe.get_all(INTERACTION, filters={"customer": customer}, fields=["name", "summary", "channel", "contact_name", "spoken_by", "interaction_on", "owner", "creation", "action_reference"], order_by="interaction_on desc", start=start, limit_page_length=50)
    for row in rows:
        row.mentions = frappe.get_all("Customer Interaction Mention", filters={"parent": row.name, "parenttype": INTERACTION}, fields=["employee", "employee_name", "user"], limit_page_length=0)
    # Legacy calls are a separate paginated stream so neither history can starve the other.
    legacy = []
    if frappe.db.exists("DocType", "Calls"):
        legacy = frappe.get_all("Calls", filters={"call_to": "Customer", "lead__party": customer}, fields=["name", "short_notes", "long_notes", "date", "call_time", "employee_id", "employee_name", "follow_up_date"], order_by="date desc, call_time desc", start=start, limit_page_length=50)
    return {"interactions": rows, "calls": legacy}


@frappe.whitelist(methods=["POST"])
def log_interaction(payload):
    guard()
    data = frappe.parse_json(payload)
    if not str(data.get("summary", "")).strip():
        frappe.throw(_("Enter a discussion summary."))
    customer = data.get("customer")
    frappe.get_doc("Customer", customer)
    spoken_by = data.get("spoken_by") or frappe.session.user
    if spoken_by != frappe.session.user and not manager():
        frappe.throw(_("Only managers may record a conversation on someone else's behalf."), frappe.PermissionError)
    if not internal(spoken_by):
        frappe.throw(_("Choose an active internal employee as the speaker."))
    doc = frappe.get_doc({"doctype": INTERACTION, "customer": customer, "summary": data["summary"].strip(), "channel": data.get("channel", "Call"), "contact_name": data.get("contact_name"), "spoken_by": spoken_by, "interaction_on": data.get("interaction_on") or now_datetime()})
    for employee in set(data.get("mentions") or []):
        doc.append("mentions", {"employee": employee})
    doc.insert(ignore_permissions=True)  # guard + controller validation enforce workspace policy
    created = []
    for item in data.get("actions") or []:
        created.append(frappe.get_doc({"doctype": ACTION, "customer": customer, "interaction": doc.name, **{k: item.get(k) for k in ("subject", "assigned_to", "due_date", "due_time", "action_type", "priority", "description") if item.get(k)}}).insert(ignore_permissions=True).name)
    return {"name": doc.name, "actions": created}


@frappe.whitelist(methods=["POST"])
def update_action(name, payload, modified):
    guard()
    doc = frappe.get_doc(ACTION, name)
    if not permission(doc, permission_type="write"):
        frappe.throw(_("You cannot change this action."), frappe.PermissionError)
    data = frappe.parse_json(payload)
    # Let Frappe's save-time check catch edits since this read as well.
    if str(doc.modified) != str(modified):
        frappe.throw(_("This action changed. Refresh and try again."), frappe.TimestampMismatchError)
    doc.flags.workspace_update = True
    doc.flags.workspace_reason = str(data.get("update") or "").strip()
    for field in ("status", "due_date", "due_time", "assigned_to", "priority"):
        if field in data:
            if field == "assigned_to" and data[field] != doc.assigned_to and not (manager() or doc.owner == frappe.session.user):
                frappe.throw(_("Only the creator or a manager can reassign an action."), frappe.PermissionError)
            doc.set(field, data[field])
    doc.save(ignore_permissions=True)
    return doc.as_dict()


def notify(users, subject, doctype, name):
    from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
    users = sorted(set(u for u in users if u and u != frappe.session.user and internal(u)))
    if users:
        enqueue_create_notification(users, {"type": "Alert", "subject": html.escape(subject), "document_type": doctype, "document_name": name, "from_user": frappe.session.user})


@frappe.whitelist()
def personal_agenda():
    """All personal pending deadlines, so the calendar never hides later pages."""
    guard()
    return frappe.get_all(ACTION, filters={"assigned_to": frappe.session.user, "status": ["in", ["Open", "In Progress"]]}, fields=["name", "customer", "customer_name", "subject", "assigned_to", "due_date", "due_time", "status", "action_type", "priority", "description", "interaction", "modified", "owner", "event"], order_by="due_date asc, due_time asc", limit_page_length=0)
