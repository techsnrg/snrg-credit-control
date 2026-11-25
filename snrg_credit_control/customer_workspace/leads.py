"""Shared Teamspace lead queue backed by CRM Lead records."""
from html import escape, unescape
import re

from pypika import CustomFunction, Order

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint, get_datetime, getdate, today

from snrg_credit_control.customer_workspace import lead_activity

DOCTYPE = "CRM Lead"
SHARED = "custom_teamspace_shared"
CLOSED = "custom_teamspace_closed"
FOLLOW_UP = "custom_teamspace_follow_up"
LAST_ACTIVITY = "custom_teamspace_last_activity"
DIVISION = "custom_teamspace_division"
CITY = "custom_teamspace_city"
STATE = "custom_teamspace_state"
DIVISIONS = ("Gold Coast", "Silver Prism (OEM)", "Blue Horizon (ODM)")
FIELDS = [
    "name", "lead_name", "organization", "email", "mobile_no", "source",
    "lead_owner", "converted", "modified", CLOSED, FOLLOW_UP, LAST_ACTIVITY, DIVISION, CITY, STATE,
]
NOTE_PREFIX = "Teamspace lead · "


def install_fields():
    if "crm" not in frappe.get_installed_apps():
        return
    create_custom_fields({DOCTYPE: [
        dict(fieldname=SHARED, label="Shared in Teamspace", fieldtype="Check", default="0", insert_after="lead_owner", read_only=1, permlevel=1),
        dict(fieldname=CLOSED, label="Closed in Teamspace", fieldtype="Check", default="0", insert_after=SHARED, read_only=1, permlevel=1),
        dict(fieldname=FOLLOW_UP, label="Teamspace Next Follow-up", fieldtype="Date", insert_after=CLOSED, read_only=1, permlevel=1),
        dict(fieldname=LAST_ACTIVITY, label="Teamspace Last Activity", fieldtype="Small Text", insert_after=FOLLOW_UP, read_only=1, permlevel=1),
        dict(fieldname=DIVISION, label="Division", fieldtype="Select", options="\n" + "\n".join(DIVISIONS), insert_after="organization"),
        dict(fieldname=CITY, label="City", fieldtype="Data", insert_after=DIVISION),
        dict(fieldname=STATE, label="State", fieldtype="Data", insert_after=CITY),
    ]})
    lead_activity.install_fields(create_custom_fields)


def allowed():
    return (
        "crm" in frappe.get_installed_apps()
        and all(frappe.get_meta(DOCTYPE).has_field(field) for field in (DIVISION, CITY, STATE))
        and all(frappe.has_permission(DOCTYPE, action) for action in ("read", "create", "write"))
    )


def _guard():
    from snrg_credit_control.customer_workspace.api import guard

    guard()
    if not allowed():
        frappe.throw(_("Leads are available to sales users with CRM access."), frappe.PermissionError)


def _text(value, limit):
    value = str(value or "").strip()
    if len(value) > limit:
        frappe.throw(_("Enter at most {0} characters.").format(limit))
    return value


def _row(doc):
    result = {field: doc.get(field) for field in FIELDS}
    result["closed"] = bool(doc.get(CLOSED) or doc.get("converted"))
    result["follow_up"] = doc.get(FOLLOW_UP)
    result["division"] = doc.get(DIVISION)
    result["city"] = doc.get(CITY)
    result["state"] = doc.get(STATE)
    result["last_activity"] = doc.get(LAST_ACTIVITY)
    return result


def _lead(name, *, lock=False):
    # Native CRM keeps Sales User records private. Share only explicitly
    # marked Teamspace leads through this guarded, task-specific API.
    lead = frappe.get_doc(DOCTYPE, name, for_update=lock)
    if not lead.get(SHARED):
        frappe.throw(_("This lead is outside the Teamspace queue."), frappe.PermissionError)
    return lead


def _contact_query():
    contact = frappe.qb.DocType("Contact")
    link = frappe.qb.DocType("Dynamic Link")
    query = (
        frappe.qb.from_(link).join(contact).on(link.parent == contact.name)
        .where((link.parenttype == "Contact") & (link.parentfield == "links") & (link.link_doctype == DOCTYPE))
    )
    return query, contact, link


@frappe.whitelist(methods=["GET"])
def list_leads(scope="all", start=0, search=None, division=None):
    _guard()
    filters = {SHARED: 1}
    if scope == "mine":
        filters["lead_owner"] = frappe.session.user
    elif scope == "due":
        filters.update({FOLLOW_UP: ["<=", today()], CLOSED: 0, "converted": 0})
    elif scope != "all":
        frappe.throw(_("Choose a valid lead view."))
    if division:
        if division not in DIVISIONS:
            frappe.throw(_("Choose a valid division."))
        filters[DIVISION] = division
    search = _text(search, 140)
    query = frappe.qb.get_query(
        DOCTYPE, filters=filters, fields=FIELDS, ignore_permissions=True,
        order_by=f"{FOLLOW_UP} asc, name asc" if scope == "due" else "modified desc, name desc",
        offset=max(0, cint(start)), limit=51,
    )
    if search:
        pattern = "%" + search.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
        lead = frappe.qb.DocType(DOCTYPE)
        contact_query, contact, link = _contact_query()
        matching_contacts = contact_query.select(link.link_name).where(
            contact.full_name.like(pattern) | contact.mobile_no.like(pattern) | contact.phone.like(pattern)
        )
        query = query.where(
            lead.name.like(pattern) | lead.lead_name.like(pattern) | lead.organization.like(pattern)
            | lead.mobile_no.like(pattern) | lead.phone.like(pattern) | lead.name.isin(matching_contacts)
        )
    rows = query.run(as_dict=True)
    return {"rows": [_row(row) for row in rows[:50]], "has_more": len(rows) > 50, "divisions": DIVISIONS}


@frappe.whitelist(methods=["GET"])
def sources():
    _guard()
    return frappe.get_all("CRM Lead Source", pluck="name", order_by="name asc")


@frappe.whitelist(methods=["GET"])
def intake_options():
    return {"sources": sources(), "divisions": DIVISIONS}


@frappe.whitelist(methods=["GET"])
def detail(name, start=0):
    _guard()
    return _detail(_lead(name), start)


def _can_edit(lead):
    return not (lead.get(CLOSED) or lead.converted) and frappe.session.user == (lead.lead_owner or lead.owner)


def _detail(lead, start=0):
    comments = frappe.get_all("Comment", filters={
        "reference_doctype": DOCTYPE, "reference_name": lead.name, "comment_type": "Comment",
        "content": ["like", NOTE_PREFIX + "%"],
    }, fields=["name", "content", "owner", "comment_by", "creation", *lead_activity.RATE_FIELDS],
        order_by="creation desc, name desc", start=max(0, cint(start)), limit_page_length=51)
    attachments = lead_activity.attachments_for([comment.name for comment in comments[:50]])
    for comment in comments:
        comment.update(lead_activity.rate_fields(comment))
        comment.attachments = attachments.get(comment.name, [])
        comment.content = unescape(comment.content.removeprefix(NOTE_PREFIX))
    contact_query, contact, link = _contact_query()
    contacts = contact_query.where(link.link_name == lead.name).select(
        contact.name, contact.full_name, contact.designation, contact.mobile_no, contact.phone, contact.email_id,
    ).orderby(contact.full_name, contact.name).run(as_dict=True)
    return {
        "lead": _row(lead), "history": comments[:50], "has_more": len(comments) > 50,
        "contacts": contacts,
        "can_add_contact": _can_edit(lead),
        "can_edit_details": _can_edit(lead),
    }


def _lead_values(contact, organization, mobile, email, source, division, city, state):
    required = {
        "organization": (_("Company"), organization),
        CITY: (_("City"), city),
        STATE: (_("State"), state),
        DIVISION: (_("Division"), division),
        "first_name": (_("Contact name"), contact),
        "mobile_no": (_("Phone"), mobile),
        "source": (_("Source"), source),
    }
    values = {field: _text(value, 140) for field, (_, value) in required.items()}
    missing = [label for field, (label, _) in required.items() if not values[field]]
    if missing:
        frappe.throw(_("Enter the required fields: {0}.").format(", ".join(missing)))
    if values[DIVISION] not in DIVISIONS:
        frappe.throw(_("Choose a valid division."))
    values["email"] = _text(email, 140)
    return values


def _possible_duplicates(values):
    lead = frappe.qb.DocType(DOCTYPE)
    contacts, contact, link = _contact_query()
    regexp_replace = CustomFunction("REGEXP_REPLACE", ["value", "pattern", "replacement"])
    prefix = r"^(91|0)(?=[0-9]{10}$)"
    phone = re.sub(prefix, "", re.sub(r"[^0-9]", "", values["mobile_no"]))

    def matches_phone(field):
        digits = regexp_replace(field, "[^0-9]", "")
        return regexp_replace(digits, prefix, "") == phone

    match = (lead.organization == values["organization"]) & (lead[CITY] == values[CITY])
    if phone:
        linked = contacts.select(link.link_name).where(
            matches_phone(contact.mobile_no) | matches_phone(contact.phone)
        )
        match |= matches_phone(lead.mobile_no) | matches_phone(lead.phone) | lead.name.isin(linked)
    return (
        frappe.qb.from_(lead).select(lead.name, lead.organization, lead.lead_name, lead[CITY].as_("city"))
        .where((lead[SHARED] == 1) & match).orderby(lead.name, order=Order.desc)
        .limit(10).run(as_dict=True)
    )


@frappe.whitelist(methods=["POST"])
def create_lead(contact, organization=None, mobile=None, email=None, source=None, division=None, city=None, state=None, confirm_duplicate=0, initial_discussion=None, rate=None, currency=None, rate_basis=None):
    _guard()
    values = _lead_values(contact, organization, mobile, email, source, division, city, state)
    if not cint(confirm_duplicate):
        matches = _possible_duplicates(values)
        if matches:
            return {"possible_duplicates": matches}
    discussion = _text(initial_discussion, 2000)
    rate_values, files = lead_activity.activity_extras(rate, currency, rate_basis)
    activity = (_("Initial discussion: {0}").format(discussion) if discussion else _("Initial discussion")) if discussion or rate_values or files else None
    lead = frappe.get_doc({
        "doctype": DOCTYPE, **values, SHARED: 1, LAST_ACTIVITY: activity or _("Lead added"),
    }).insert(ignore_permissions=True)
    if activity:
        lead_activity.add_activity(lead, activity, rate_values, files)
    return _detail(lead)


@frappe.whitelist(methods=["POST"])
def edit_details(name, modified, contact, organization=None, mobile=None, email=None, source=None, division=None, city=None, state=None):
    _guard()
    lead = _lead(name, lock=True)
    if not _can_edit(lead):
        frappe.throw(_("Only the person responsible for an open lead can edit its details."), frappe.PermissionError)
    if get_datetime(modified) != get_datetime(lead.modified):
        frappe.throw(_("This lead changed. Reopen it and try again."), frappe.TimestampMismatchError)

    values = _lead_values(contact, organization, mobile, email, source, division, city, state)
    if values["first_name"] == lead.lead_name:
        values.pop("first_name")
    else:
        values.update(salutation=None, middle_name=None, last_name=None)
    if any((lead.get(field) or "") != (value or "") for field, value in values.items()):
        activity = _("Lead details updated")
        lead.update(values)
        lead.set(LAST_ACTIVITY, activity)
        lead.save(ignore_permissions=True)
        lead.add_comment("Comment", NOTE_PREFIX + escape(activity))
    return _detail(lead)


@frappe.whitelist(methods=["POST"])
def add_contact(name, contact, designation=None, mobile=None, email=None):
    _guard()
    lead = _lead(name, lock=True)
    if lead.get(CLOSED) or lead.converted:
        frappe.throw(_("This lead is closed."))
    if frappe.session.user != (lead.lead_owner or lead.owner):
        frappe.throw(_("Only the person handling the lead can add contacts."), frappe.PermissionError)

    contact, designation = _text(contact, 140), _text(designation, 140)
    mobile, email = _text(mobile, 140), _text(email, 140)
    if not contact or not (mobile or email):
        frappe.throw(_("Enter a contact name and either a phone number or an email."))
    existing = _detail(lead)["contacts"]
    people = [(lead.lead_name, lead.mobile_no or lead.phone, lead.email)] + [
        (row.full_name, row.mobile_no or row.phone, row.email_id) for row in existing
    ]
    if any(
        person and person.casefold() == contact.casefold()
        and ((mobile and mobile == phone) or (email and email.casefold() == (address or "").casefold()))
        for person, phone, address in people
    ):
        frappe.throw(_("This contact is already on the lead."))
    frappe.get_doc({
        "doctype": "Contact", "first_name": contact, "designation": designation,
        "company_name": lead.organization,
        "links": [{"link_doctype": DOCTYPE, "link_name": lead.name}],
        "phone_nos": [{"phone": mobile, "is_primary_mobile_no": 1}] if mobile else [],
        "email_ids": [{"email_id": email, "is_primary": 1}] if email else [],
    }).insert(ignore_permissions=True)
    activity = _("Contact added: {0}").format(contact)
    lead.set(LAST_ACTIVITY, activity)
    lead.save(ignore_permissions=True)
    lead.add_comment("Comment", NOTE_PREFIX + escape(activity))
    return _detail(lead)


@frappe.whitelist(methods=["POST"])
def update_lead(name, modified, action, follow_up=None, note=None, kind="Note", spoke_with=None, rate=None, currency=None, rate_basis=None):
    _guard()
    lead = _lead(name, lock=True)
    if get_datetime(modified) != get_datetime(lead.modified):
        frappe.throw(_("This lead changed. Reopen it and try again."), frappe.TimestampMismatchError)
    if lead.get(CLOSED) or lead.converted:
        frappe.throw(_("This lead is closed."))
    user = frappe.session.user
    rate_values, files = {}, []
    if action == "pick_up":
        if lead.lead_owner:
            frappe.throw(_("Someone already picked up this lead."))
        lead.lead_owner = user
        activity = _("Picked up")
    else:
        if lead.lead_owner != user:
            frappe.throw(_("Only the person handling the lead can update it."), frappe.PermissionError)
        if action == "close":
            lead.set(CLOSED, 1)
            lead.set(FOLLOW_UP, None)
            activity = _("Lead closed")
        elif action == "follow_up":
            note = _text(note, 2000)
            rate_values, files = lead_activity.activity_extras(rate, currency, rate_basis)
            if kind not in ("Call", "Note"):
                frappe.throw(_("Choose Call or Note."))
            if not (note or follow_up or lead.get(FOLLOW_UP) or rate_values or files):
                frappe.throw(_("Add a note, date, rate, or attachment."))
            date = getdate(follow_up) if follow_up else None
            date_changed = date != (getdate(lead.get(FOLLOW_UP)) if lead.get(FOLLOW_UP) else None)
            if not (note or date_changed or rate_values or files):
                return _detail(lead)
            lead.set(FOLLOW_UP, date)
            activity = f"{kind}: {note}" if note else _("Follow-up date updated")
            if kind == "Call" and (note or rate_values or files):
                person = lead.lead_name
                if spoke_with:
                    query, contact, link = _contact_query()
                    people = query.select(contact.full_name).where(
                        (link.link_name == lead.name) & (contact.name == spoke_with)
                    ).run(pluck=True)
                    if not people:
                        frappe.throw(_("Choose a contact linked to this lead."))
                    person = people[0]
                activity = _("Call with {0}").format(person)
                if note:
                    activity += f": {note}"
            elif not note and (rate_values or files):
                activity = _("Follow-up")
            if date_changed:
                activity += f" · {date}" if date else " · " + _("Follow-up cleared")
        else:
            frappe.throw(_("Choose a valid lead action."))
    lead.set(LAST_ACTIVITY, activity)
    lead.save(ignore_permissions=True)
    lead_activity.add_activity(lead, activity, rate_values, files)
    return _detail(lead)
