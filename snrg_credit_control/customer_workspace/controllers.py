import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, today, add_to_date, get_fullname
from snrg_credit_control.customer_workspace.api import ACTION, INTERACTION, guard, internal, manager, notify, party_values


class CustomerInteraction(Document):
    def validate(self):
        guard()
        self.update(party_values(self.customer, self.supplier))
        if not self.is_new():
            frappe.throw(_("Interactions are permanent history. Add a new update instead of editing."))
        if self.call_outcome and (self.channel != "Call" or self.call_outcome not in ("Connected", "No answer", "Busy", "Call back", "Wrong number")):
            frappe.throw(_("Choose a valid call outcome for a Call interaction."))
        if self.summary_html:
            from snrg_credit_control.customer_workspace.rich_text import clean
            self.summary_html = clean(self.summary_html, self.flags.teamspace_uploads or [])
        if not (self.summary or "").strip():
            frappe.throw(_("A discussion summary is required."))
        if self.spoken_by != frappe.session.user and not manager():
            frappe.throw(_("Only managers may record a conversation for another team member."), frappe.PermissionError)
        if not internal(self.spoken_by):
            frappe.throw(_("The speaker must be an active internal team member."))
        for row in self.mentions:
            employee = frappe.get_doc("Employee", row.employee)
            if employee.status != "Active":
                frappe.throw(_("Only active team members can be mentioned."))
            row.employee_name = employee.employee_name
            row.user = employee.user_id if employee.user_id and internal(employee.user_id) else None

    def after_insert(self):
        notify([row.user for row in self.mentions], f"{get_fullname()} mentioned you: {self.supplier_name or self.customer_name}", self.doctype, self.name, kind="Mention")


class CustomerAction(Document):
    def validate(self):
        guard()
        self.update(party_values(self.customer, self.supplier, optional=True))
        if not internal(self.assigned_to):
            frappe.throw(_("Assign the action to an active team member with an enabled internal login."))
        if self.interaction and tuple(value or None for value in (frappe.db.get_value(INTERACTION, self.interaction, ["customer", "supplier"]) or ())) != (self.customer or None, self.supplier or None):
            frappe.throw(_("The originating interaction belongs to a different customer or supplier."))
        old = self.get_doc_before_save()
        if old:
            if self.customer != old.customer or self.supplier != old.supplier or self.interaction != old.interaction:
                frappe.throw(_("An action's customer/supplier and origin cannot be changed."))
            if not (manager() or frappe.session.user in (old.owner, old.assigned_to)):
                frappe.throw(_("You cannot change this action."), frappe.PermissionError)
            if self.assigned_to != old.assigned_to and not (manager() or old.owner == frappe.session.user):
                frappe.throw(_("Only the creator or a manager can reassign an action."), frappe.PermissionError)
            changed = any(self.get(f) != old.get(f) for f in ("due_date", "due_time", "status", "assigned_to"))
            if changed and not (self.flags.workspace_reason or "").strip():
                frappe.throw(_("Add an outcome or reason for the status, schedule or assignment change."))
        self.completed_on = now_datetime() if self.status == "Completed" and not self.completed_on else self.completed_on
        if self.status != "Completed":
            self.completed_on = None

    def on_update(self):
        old = self.get_doc_before_save()
        self.sync_event()
        if not old or old.assigned_to != self.assigned_to:
            notify([self.assigned_to], f"Assigned: {self.subject}", self.doctype, self.name)
        if old and (self.flags.workspace_reason or any(self.get(f) != old.get(f) for f in ("status", "due_date", "due_time", "assigned_to"))):
            changes = [f"{f.replace('_', ' ')}: {old.get(f) or '—'} → {self.get(f) or '—'}" for f in ("status", "due_date", "due_time", "assigned_to") if self.get(f) != old.get(f)]
            summary = self.flags.workspace_reason or "Action updated"
            if changes:
                summary += "\n" + "\n".join(changes)
            if self.customer or self.supplier:
                frappe.get_doc({"doctype": INTERACTION, "customer": self.customer, "supplier": self.supplier, "channel": "Update", "summary": f"{self.subject}\n{summary}", "spoken_by": frappe.session.user, "interaction_on": now_datetime(), "action_reference": self.name}).insert(ignore_permissions=True)
            else:
                self.add_comment("Comment", text=frappe.utils.escape_html(summary).replace("\n", "<br>"))
            notify([self.owner, self.assigned_to], f"Action updated: {self.subject}", self.doctype, self.name)

    def sync_event(self):
        # Event is only a calendar projection. Actions remain authoritative.
        existing = frappe.db.get_value("Event", {"reference_doctype": ACTION, "reference_docname": self.name}, "name")
        if not self.due_time and not existing:
            return
        event = frappe.get_doc("Event", existing) if existing else frappe.new_doc("Event")
        event.update({"subject": f"{self.supplier_name or self.customer_name}: {self.subject}" if self.customer or self.supplier else self.subject, "event_type": "Private", "starts_on": f"{self.due_date} {self.due_time or '00:00:00'}", "ends_on": add_to_date(f"{self.due_date} {self.due_time or '00:00:00'}", minutes=30), "all_day": not bool(self.due_time), "status": {"Completed": "Completed", "Cancelled": "Cancelled"}.get(self.status, "Open"), "reference_doctype": ACTION, "reference_docname": self.name, "description": "Managed by Teamspace. Change the action to update this event."})
        event.flags.customer_workspace_sync = True
        event.set("event_participants", [{"reference_doctype": "User", "reference_docname": self.assigned_to}])
        event.save(ignore_permissions=True)
        self.db_set("event", event.name, update_modified=False)


def protect_event(doc, method=None):
    old = doc.get_doc_before_save()
    linked = doc.reference_doctype == ACTION or (old and old.reference_doctype == ACTION)
    if linked and not doc.flags.customer_workspace_sync:
        frappe.throw(_("Update the linked Customer Action to change this calendar entry."))
