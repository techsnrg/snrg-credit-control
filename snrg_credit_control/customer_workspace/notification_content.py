"""Readable event snapshots shared by Teamspace email and device notifications."""
from datetime import datetime
from html import escape
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit

import frappe


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('br', 'p', 'div', 'li', 'tr', 'h3'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'div', 'li', 'tr', 'h3'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain(value):
    parser = _Text()
    parser.feed(str(value or ''))
    return '\n'.join(' '.join(line.split()) for line in ''.join(parser.parts).splitlines() if line.strip())


def date_label(value):
    if not value:
        return 'Not set'
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').strftime('%d %b %Y').lstrip('0')
    except ValueError:
        return str(value)


def time_label(value):
    if value in (None, ''):
        return 'No time set'
    try:
        hour, minute = map(int, str(value).split(':')[:2])
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError
        return f"{hour % 12 or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"
    except (ValueError, TypeError):
        return str(value)


def person(user):
    return frappe.utils.get_fullname(user) if user else 'Unassigned'


def snapshot(doc, subject, *, kind='Assignment', event='', changes=None, reason=None):
    """Capture at write time; a later edit must not rewrite a queued update."""
    actor = person(frappe.session.user)
    task = doc.doctype == 'Customer Action'
    label = doc.get('subject') if task else (doc.get('supplier_name') or doc.get('customer_name') or 'Conversation')
    if kind == 'Mention':
        subject = f'{actor} mentioned you: {label}'
    elif event == 'assigned':
        subject = f'{actor} assigned a task: {label}'
    elif event == 'updated':
        verb = 'completed' if (changes or {}).get('status', (None, None))[1] == 'Completed' else 'updated'
        subject = f'{actor} {verb}: {label}'
    lines = [('Updated by' if event == 'updated' else 'From', actor)]
    # The outcome is the most useful part of an update, so place it first.
    if reason:
        lines.append(('Outcome / reason', str(reason)[:4000]))
    labels = {'status': 'Status', 'assigned_to': 'Responsible team member', 'due_date': 'Due date', 'due_time': 'Due time'}
    for field, (before, after) in (changes or {}).items():
        formatter = person if field == 'assigned_to' else date_label if field == 'due_date' else time_label if field == 'due_time' else lambda v: str(v or 'Not set')
        lines.append((labels.get(field, field), f'{formatter(before)} → {formatter(after)}'))
    if task:
        lines.append(('Task', doc.get('subject') or 'Untitled task'))
    party = doc.get('supplier_name') or doc.get('customer_name')
    lines.append(('Supplier' if doc.get('supplier') else 'Customer' if doc.get('customer') else 'Related to', party or 'General task'))
    if task:
        lines.extend([('Responsible', person(doc.get('assigned_to'))),
            ('Due', date_label(doc.get('due_date')) + (' · ' + time_label(doc.get('due_time')) if doc.get('due_time') not in (None, '') else '')),
            ('Current status', doc.get('status') or 'Open')])
        if doc.get('description'):
            lines.append(('Instructions', str(doc.get('description'))[:4000]))
        link = frappe.utils.get_url('/teamspace?task=' + quote(doc.name, safe=''))
    else:
        lines.append(('Conversation', doc.get('summary') or ''))
        if doc.get('call_outcome'):
            lines.append(('Call outcome', doc.get('call_outcome')))
        # Native Form enforces the same document permissions when opened.
        link = frappe.utils.get_url('/desk/customer-interaction/' + quote(doc.name, safe=''))
    body = ''.join(f'<p><strong>{escape(key)}:</strong> {escape(str(value)).replace(chr(10), "<br>")}</p>' for key, value in lines)
    return dict(subject=escape(subject), email_content=body, link=link,
                email_header='Teamspace mention' if kind == 'Mention' else 'Teamspace task update' if task else 'Teamspace conversation')


def push_payload(log):
    title = ' '.join(plain(log.subject or log.get('title') or 'Teamspace update').split())
    body = plain(log.email_content or log.get('description') or '')
    # Preserve readable separators when compacting the email snapshot.
    body = ' · '.join(body.splitlines()) or title
    origin = urlsplit(frappe.utils.get_url())
    link = urlsplit(log.link or '/teamspace')
    safe = (not link.netloc or (link.scheme == origin.scheme and link.netloc == origin.netloc)) and (
        link.path == '/teamspace' or link.path.startswith('/desk/customer-interaction/'))
    url = link.path + ('?' + link.query if link.query else '') if safe else '/teamspace'
    return {'title': title[:119] + '…' if len(title) > 120 else title,
            'body': body[:279] + '…' if len(body) > 280 else body,
            'tag': log.name, 'url': url}
