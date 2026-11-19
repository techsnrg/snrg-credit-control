"""Optional staff-only WhatsApp delivery for Teamspace assignments."""
import re
from urllib.parse import quote

import frappe
import requests
from frappe.utils import formatdate, get_fullname, get_time

JOB = f"{__name__}.deliver"
SUMMARY_LIMIT = 240


def enqueue_assignment(doc, actor):
    if not _recipient(doc.assigned_to) or not frappe.conf.get("teamspace_whatsapp_template"):
        return
    frappe.enqueue(
        JOB, enqueue_after_commit=True, name=doc.name, assignee=doc.assigned_to,
        revision=doc.whatsapp_assignment_revision, actor=actor,
    )


def _recipient(user):
    recipients = frappe.conf.get("teamspace_whatsapp_recipients") or {}
    phone = recipients.get(user) if isinstance(recipients, dict) else None
    return phone if isinstance(phone, str) and re.fullmatch(r"\+[1-9][0-9]{7,14}", phone) else None


def _line(value, limit=240):
    return " ".join(str(value or "").split())[:limit]


def _message(task, actor, template, language, button_url):
    title = _line(task.subject)
    assigned_by = _line(get_fullname(actor) or actor)
    due_date = formatdate(task.due_date, "dd MMM yyyy")
    due_time = get_time(task.due_time).strftime("%H:%M") if task.due_time not in (None, "") else "No time set"
    summary = _line(task.whatsapp_summary, SUMMARY_LIMIT) or "See task for details."
    return {
        "message_type": "outgoing",
        "private": False,
        "content_type": "text",
        "content": f"Teamspace task: {title}\nAssigned by: {assigned_by}\nDue date: {due_date}\nDue time: {due_time}\nSummary: {summary}",
        "template_params": {
            "name": template,
            "language": language,
            "category": "UTILITY",
            "processed_params": {
                "body": dict(zip(("1", "2", "3", "4", "5"), (title, assigned_by, due_date, due_time, summary))),
                "buttons": [{"type": "url", "parameter": quote(task.name, safe=""), "url": button_url, "variables": ["1"]}],
            },
        },
    }


def deliver(name, assignee, revision, actor):
    from snrg_credit_control.customer_workspace.api import ACTION, internal

    template = frappe.conf.get("teamspace_whatsapp_template")
    base_url = frappe.conf.get("teamspace_whatsapp_base_url") or ""
    phone = _recipient(assignee)
    if not (template and phone and re.fullmatch(r"https://[a-zA-Z0-9.-]+(?::[0-9]+)?", base_url) and internal(assignee)):
        return

    task = frappe.db.get_value(
        ACTION, name,
        ["name", "assigned_to", "whatsapp_assignment_revision", "status", "subject", "due_date", "due_time", "whatsapp_summary"],
        as_dict=True,
    )
    if not task or task.assigned_to != assignee or task.whatsapp_assignment_revision != revision or task.status not in ("Open", "In Progress"):
        return

    from snrg_whatsapp import api as whatsapp

    config = whatsapp._get_common_config()
    if not config:
        return
    contact = whatsapp._find_or_create_chatwoot_contact(config, recipient=phone, display_name=get_fullname(assignee))
    conversation = whatsapp._find_or_create_chatwoot_conversation(config, contact)
    conversation_id = conversation.get("id") or conversation.get("display_id")
    if not conversation_id:
        raise RuntimeError("Chatwoot did not return a conversation ID")
    payload = _message(task, actor, template, frappe.conf.get("teamspace_whatsapp_language") or "en", base_url + "/teamspace?task={{1}}")
    response = requests.post(
        whatsapp._chatwoot_url(config, f"conversations/{conversation_id}/messages"),
        headers=whatsapp._chatwoot_headers(config), json=payload, timeout=30,
    )
    whatsapp._parse_chatwoot_response(response, "send Teamspace assignment")
