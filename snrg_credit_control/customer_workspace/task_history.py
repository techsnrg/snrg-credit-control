"""Permission-checked task history from existing notes and native audit records."""
import json

import frappe
from frappe import _
from frappe.utils import cint, get_datetime
from snrg_credit_control.customer_workspace.api import ACTION, INTERACTION, guard, permission
from snrg_credit_control.customer_workspace.notification_content import plain, date_label, time_label, person

FIELDS = {'status': 'Status', 'due_date': 'Due date', 'due_time': 'Due time',
    'assigned_to': 'Responsible team member', 'priority': 'Priority',
    'subject': 'Task', 'description': 'Instructions', 'action_type': 'Type',
    'whatsapp_summary': 'WhatsApp summary'}


def display(field, value):
    if field == 'assigned_to':
        return person(value)
    if field == 'due_date':
        return date_label(value)
    if field == 'due_time':
        return time_label(value)
    return str(value) if value not in (None, '') else 'Not set'


def assemble(task, comments, interactions, versions):
    """Keep source attribution; never substitute the task's current modified_by."""
    entries = [dict(key='created:' + task.name, timestamp=str(task.creation), actor=task.owner,
        title='Created task', text='', changes=[])]
    notes = []
    linked_interactions = set()
    for row in comments:
        text = plain(row.content)
        if text:
            if str(row.get('subject') or '').startswith('Teamspace update:'):
                linked_interactions.add(row.subject.split(':', 1)[1])
            notes.append(dict(key='comment:' + row.name, timestamp=str(row.creation),
                actor=row.comment_email or row.owner, title='Update', text=text, changes=[]))
    for row in interactions:
        # Automatically generated task updates prefix the task title on its own line.
        text = (row.summary or '').partition('\n')[2] or row.summary or ''
        note = dict(key='interaction:' + row.name, timestamp=str(row.creation), actor=row.owner,
            title='Update', text=text.strip(), changes=[])
        # New notes explicitly reference their mirrored relationship entry. Do not
        # guess that two independent notes are duplicates based on timing or text.
        if row.name not in linked_interactions:
            notes.append(note)
    entries.extend(notes)
    for version in versions:
        try:
            data = json.loads(version.data or '{}')
        except (TypeError, ValueError):
            continue
        changed = data.get('changed') if isinstance(data, dict) else None
        if not isinstance(changed, list):
            continue
        changed = [row for row in changed if isinstance(row, list) and len(row) >= 3
            and isinstance(row[0], str) and row[0] in FIELDS and (row[1] or None) != (row[2] or None)]
        changes = [dict(field=row[0], label=FIELDS[row[0]], before=display(row[0], row[1]), after=display(row[0], row[2]))
            for row in changed]
        if not changes:
            continue
        # Merge only a unique note matching actor, time and every raw transition.
        # Ambiguous history stays separate rather than guessing or dropping evidence.
        raw_lines = [f"{row[0].replace('_', ' ')}: {row[1] or '—'} → {row[2] or '—'}" for row in changed]
        matches = [n for n in notes if n['actor'] == version.owner and not n['changes']
            and abs((get_datetime(n['timestamp']) - get_datetime(version.creation)).total_seconds()) <= 5
            and all(line in n['text'] for line in raw_lines)]
        if len(matches) == 1:
            note = matches[0]
            note['changes'] = changes
            for line in raw_lines:
                note['text'] = note['text'].replace(line, '')
            note['text'] = note['text'].strip()
        else:
            entries.append(dict(key='version:' + version.name, timestamp=str(version.creation),
                actor=version.owner, title='Fields changed', text='', changes=changes))
    for entry in entries:
        entry['actor_name'] = person(entry['actor'])
    return sorted(entries, key=lambda entry: (get_datetime(entry['timestamp']), entry['key']), reverse=True)


@frappe.whitelist(methods=['GET', 'POST'])
def history(name, start=0):
    guard()
    task = frappe.get_doc(ACTION, name)
    if not permission(task, permission_type='read'):
        frappe.throw(_('You cannot view this task.'), frappe.PermissionError)
    # Native Comment/Version access is not granted to the caller. Return only this
    # permitted task's notes and a fixed whitelist of task fields, as plain text.
    comments = frappe.get_all('Comment', filters={'reference_doctype': ACTION,
        'reference_name': task.name, 'comment_type': 'Comment'},
        fields=['name', 'creation', 'owner', 'comment_email', 'content', 'subject'], limit_page_length=0)
    interactions = frappe.get_all(INTERACTION, filters={'action_reference': task.name},
        fields=['name', 'creation', 'owner', 'summary'], limit_page_length=0)
    versions = frappe.get_all('Version', filters={'ref_doctype': ACTION, 'docname': task.name},
        fields=['name', 'creation', 'owner', 'data'], limit_page_length=0)
    rows = assemble(task, comments, interactions, versions)
    offset = max(0, cint(start))
    return dict(rows=rows[offset:offset + 50], count=len(rows), has_more=len(rows) > offset + 50,
        note='History uses retained notes and audit records. Deleted or purged history cannot be reconstructed.')
