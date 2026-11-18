"""Customer workspace API. Shared internal history; controlled mutations."""
import html

import frappe
from frappe import _
from frappe.utils import now_datetime, today

MANAGER_ROLE = "Customer Workspace Manager"
INTERACTION = "Customer Interaction"
ACTION = "Customer Action"


def party_values(customer=None, supplier=None):
    if bool(customer) == bool(supplier):
        frappe.throw(_("Choose exactly one customer or supplier."))
    kind, name = ("Supplier", supplier) if supplier else ("Customer", customer)
    record = frappe.get_doc(kind, name)
    return {"customer": customer or None, "supplier": supplier or None,
            "customer_name": record.customer_name if customer else None,
            "supplier_name": record.supplier_name if supplier else None}


def present_action(row):
    row["party_type"] = "Supplier" if row.get("supplier") else "Customer"
    row["party"] = row.get("supplier") or row.get("customer")
    row["party_name"] = row.get("supplier_name") or row.get("customer_name")
    return row


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
    from snrg_credit_control.customer_workspace.directory import filter_options
    from snrg_credit_control.customer_workspace.receivables import can_read, allowed_companies
    from snrg_credit_control.customer_workspace import payables
    from snrg_credit_control.customer_workspace.settings import allowed
    return {"user": frappe.session.user, "is_manager": manager(), "today": today(), "employees": _directory(), "can_ar": can_read(), "can_ar_detail": bool(can_read() and frappe.db.exists("Report", "Accounts Receivable") and not frappe.get_doc("Report", "Accounts Receivable").disabled and frappe.get_doc("Report", "Accounts Receivable").is_permitted()), "can_transactions": allowed("Transactions"), "can_ap": payables.can_read(), "can_ap_detail": payables.can_read_detail(), "ap_companies": payables.allowed_companies(), "companies": allowed_companies(), **filter_options()}


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
    return [present_action(row) for row in frappe.get_all(ACTION, filters=filters, fields=["supplier", "supplier_name", "name", "customer", "customer_name", "subject", "assigned_to", "due_date", "due_time", "status", "action_type", "priority", "description", "interaction", "modified", "owner", "event"], order_by="due_date asc, due_time asc", start=max(0, int(start)), limit_page_length=100)]


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
        frappe.throw(_("Enter a discussion summary."))
    party = party_values(data.get("customer"), data.get("supplier"))
    spoken_by = data.get("spoken_by") or frappe.session.user
    if spoken_by != frappe.session.user and not manager():
        frappe.throw(_("Only managers may record a conversation on someone else's behalf."), frappe.PermissionError)
    if not internal(spoken_by):
        frappe.throw(_("Choose an active internal employee as the speaker."))
    from snrg_credit_control.customer_workspace.rich_text import uploads
    files = uploads(data.get("attachments"))
    doc = frappe.get_doc({"doctype": INTERACTION, **party, "summary_html": data.get("summary_html"), "summary": data["summary"].strip(), "channel": data.get("channel", "Call"), "contact_name": data.get("contact_name"), "spoken_by": spoken_by, "interaction_on": data.get("interaction_on") or now_datetime()})
    doc.flags.teamspace_uploads = files
    for employee in set(data.get("mentions") or []):
        doc.append("mentions", {"employee": employee})
    doc.insert(ignore_permissions=True)  # guard + controller validation enforce workspace policy
    for file in files:
        file.attached_to_doctype = INTERACTION
        file.attached_to_name = doc.name
        file.save(ignore_permissions=True)
    created = []
    for item in data.get("actions") or []:
        created.append(frappe.get_doc({"doctype": ACTION, **party, "interaction": doc.name, **{k: item.get(k) for k in ("subject", "assigned_to", "due_date", "due_time", "action_type", "priority", "description") if item.get(k)}}).insert(ignore_permissions=True).name)
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
    return present_action(doc.as_dict())


def notify(users, subject, doctype, name):
    from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
    users = sorted(set(u for u in users if u and u != frappe.session.user and internal(u)))
    if users:
        enqueue_create_notification(users, {"type": "Alert", "subject": html.escape(subject), "document_type": doctype, "document_name": name, "from_user": frappe.session.user})


@frappe.whitelist()
def personal_agenda():
    """All personal pending deadlines, so the calendar never hides later pages."""
    guard()
    return [present_action(row) for row in frappe.get_all(ACTION, filters={"assigned_to": frappe.session.user, "status": ["in", ["Open", "In Progress"]]}, fields=["supplier", "supplier_name", "name", "customer", "customer_name", "subject", "assigned_to", "due_date", "due_time", "status", "action_type", "priority", "description", "interaction", "modified", "owner", "event"], order_by="due_date asc, due_time asc", limit_page_length=0)]


@frappe.whitelist(methods=["POST"])
def create_action(payload):
    """Create a plan without fabricating a conversation."""
    guard()
    data = frappe.parse_json(payload)
    party = party_values(data.get("customer"), data.get("supplier"))
    if not str(data.get("subject") or "").strip():
        frappe.throw(_("Enter what needs to happen."))
    doc = frappe.get_doc({"doctype": ACTION, **party, **{key: data.get(key) for key in ("subject", "assigned_to", "due_date", "due_time", "action_type", "priority", "description") if data.get(key)}})
    doc.insert(ignore_permissions=True)
    return present_action(doc.as_dict())


@frappe.whitelist()
def employee_mentions(search_term=""):
    guard()
    query = str(search_term or "").casefold()
    return [{"id": row.name, "value": row.employee_name, "email": row.department or "", "can_notify": row.can_notify} for row in _directory() if query in (row.employee_name or "").casefold()]
