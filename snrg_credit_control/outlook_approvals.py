"""Disabled-by-default Outlook approvals. No bearer links or GET mutations."""
import json
from functools import lru_cache
from uuid import UUID

import frappe
from jwt import PyJWKClient
from werkzeug.wrappers import Response

from snrg_credit_control.outlook_security import (
    issue_request, signing_key, validate_identity, verify_request,
)

METHOD = 'snrg_credit_control.outlook_approvals.approve'
PATHS = {f'/api/method/{METHOD}', f'/api/v2/method/{METHOD}'}


def settings():
    config = frappe.conf.get('outlook_approvals') or {}
    if not config.get('enabled'):
        raise ValueError('Outlook approvals are not enabled')
    for field in ('tenant_id', 'client_id', 'provider_id'):
        UUID(config[field])
    if not config.get('app_id_uri') or not config.get('users'):
        raise ValueError('Outlook registration is incomplete')
    return config


@lru_cache(maxsize=4)
def _keys(tenant):
    # The tenant is a validated UUID, never a URL or value from token headers.
    return PyJWKClient(f'https://login.microsoftonline.com/{UUID(tenant)}/discovery/v2.0/keys',
                       cache_jwk_set=True, lifespan=300, timeout=5)


def authenticate():
    """Frappe auth hook; only this endpoint accepts Microsoft bearer tokens."""
    request = getattr(frappe.local, 'request', None)
    if not request or request.path not in PATHS:
        return
    if request.method != 'POST':
        frappe.throw('Only explicit POST approval actions are supported.', frappe.AuthenticationError)
    try:
        config = settings()
        header = request.headers.get('Authorization', '')
        scheme, token = header.split(' ', 1)
        if scheme.lower() != 'bearer' or len(token) > 16384:
            raise ValueError('Microsoft authentication required')
        key = _keys(config['tenant_id']).get_signing_key_from_jwt(token).key
        claims = validate_identity(token, key, tenant=config['tenant_id'],
                                   audiences=[config['client_id'], config['app_id_uri']])
        actor = config['users'].get(claims['oid'])
        if not actor or not frappe.db.get_value('User', actor, 'enabled'):
            raise ValueError('Microsoft user is not mapped to an active ERPNext user')
        if frappe.db.get_value('User', actor, 'user_type') != 'System User':
            raise ValueError('An ERPNext System User is required')
        frappe.set_user(actor)
        frappe.flags.snrg_outlook_actor = actor
    except Exception:
        # Never log the bearer token or request body.
        frappe.throw('Outlook approval authentication failed.', frappe.AuthenticationError)


def _response(text, status=200):
    card = {'$schema': 'http://adaptivecards.io/schemas/adaptive-card.json',
            'type': 'AdaptiveCard', 'version': '1.0', 'body': [
                {'type': 'TextBlock', 'text': text, 'wrap': True, 'weight': 'bolder'}]}
    return Response(json.dumps(card), status=status, content_type='application/json',
                    headers={'CARD-UPDATE-IN-BODY': 'true', 'CARD-ACTION-STATUS': text,
                             'Cache-Control': 'no-store'})


@frappe.whitelist(methods=['POST'])
def approve(request_token=None):
    actor = getattr(frappe.flags, 'snrg_outlook_actor', None)
    if not actor or actor != frappe.session.user:
        frappe.throw('A verified Outlook action is required.', frappe.PermissionError)
    try:
        if not request_token or len(request_token) > 8192:
            raise ValueError('Missing approval request')
        request = verify_request(request_token, key=signing_key(frappe.conf.encryption_key), actor=actor)
        # Lock the row: simultaneous actions cannot both apply the same request.
        frappe.db.get_value(request['doctype'], request['name'], 'name', for_update=True)
        doc = frappe.get_doc(request['doctype'], request['name'])
        doc.check_permission('read')
        if str(doc.modified) != request['version']:
            return _response('This request has changed or was already processed. Open ERPNext for its current status.', 409)
        if doc.doctype == 'Purchase Order':
            if doc.docstatus != 0 or doc.workflow_field != 'Pending Approval':
                return _response('This purchase order is no longer pending approval.', 409)
            # Standard workflow enforces roles, conditions and self-approval restrictions.
            from frappe.model.workflow import apply_workflow
            apply_workflow(doc.as_dict(), 'Approve')
        else:
            if doc.docstatus != 0 or doc.custom_credit_approval_status != 'Pending':
                return _response('This credit request is no longer pending approval.', 409)
            # Reuse the app's approval checks, amount cap and validity policy.
            from snrg_credit_control.overrides.sales_order import approve_from_email
            approve_from_email(doc.name)
            # That helper normally redirects a browser; Outlook needs an updated card.
            frappe.local.response.pop('type', None)
            frappe.local.response.pop('location', None)
        return _response(f'Approved {doc.name}. The decision has been recorded in ERPNext.')
    except Exception:
        frappe.db.rollback()
        return _response('Approval could not be completed. Open ERPNext to review the request.', 400)


def build_card(doc, actor):
    config = settings()
    if actor not in config['users'].values():
        raise ValueError('Approver is not in the Outlook pilot')
    token = issue_request(key=signing_key(frappe.conf.encryption_key), actor=actor,
                          doctype=doc.doctype, name=doc.name, version=str(doc.modified))
    if doc.doctype == 'Purchase Order':
        if doc.docstatus != 0 or doc.workflow_field != 'Pending Approval':
            raise ValueError('Purchase order is not awaiting approval')
        label, party = 'Purchase Order', doc.supplier_name
    else:
        if doc.docstatus != 0 or doc.custom_credit_approval_status != 'Pending':
            raise ValueError('Credit approval is not pending')
        label, party = 'Credit approval', doc.customer_name
    facts = [{'title': 'Document', 'value': doc.name}, {'title': 'Party', 'value': party},
             {'title': 'Company', 'value': doc.company},
             {'title': 'Order value', 'value': frappe.utils.fmt_money(doc.grand_total, currency=doc.currency)}]
    if doc.doctype == 'Sales Order':
        facts.append({'title': 'Requested credit cap', 'value': frappe.utils.fmt_money(doc.custom_snrg_request_amount, currency=doc.currency)})
        facts.append({'title': 'Approval policy', 'value': 'Up to requested/order amount, valid for 7 days'})
    else:
        facts.append({'title': 'Required by', 'value': str(doc.schedule_date)})
    return {'$schema': 'http://adaptivecards.io/schemas/adaptive-card.json', 'type': 'AdaptiveCard',
            'version': '1.0', 'originator': config['provider_id'], 'hideOriginalBody': False,
            'body': [{'type': 'TextBlock', 'text': f'{label} approval required', 'weight': 'bolder', 'wrap': True},
                     {'type': 'FactSet', 'facts': facts},
                     {'type': 'TextBlock', 'text': 'Approve the displayed request using your existing ERPNext permissions. If it changes, open ERPNext to review it again.', 'wrap': True}],
            'actions': [{'type': 'Action.Http', 'title': 'Approve', 'method': 'POST',
                         'url': frappe.utils.get_url('/api/method/' + METHOD),
                         'headers': [{'name': 'Content-Type', 'value': 'application/json'}],
                         'body': json.dumps({'request_token': token})},
                        {'type': 'Action.OpenUrl', 'title': 'View full details',
                         'url': frappe.utils.get_url_to_form(doc.doctype, doc.name)}]}


def email_html(doc, actor):
    card = build_card(doc, actor)
    # Avoid allowing document text to terminate the embedded JSON script element.
    encoded = json.dumps(card).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    from html import escape
    url = escape(frappe.utils.get_url_to_form(doc.doctype, doc.name), quote=True)
    return ('<!doctype html><html><head><meta charset="utf-8">'
            '<script type="application/adaptivecard+json">' + encoded + '</script></head><body>'
            '<p>Approval required for ' + escape(doc.name) + '.</p><p>If your email client does not support '
            'in-email approvals, <a href="' + url + '">open the request in ERPNext</a>.</p></body></html>')


def send_pilot_card(doctype, name, actor):
    """Explicit pilot entrypoint, not whitelisted. Invoke from bench after rollout review."""
    if doctype not in {'Purchase Order', 'Sales Order'}:
        raise ValueError('Unsupported document')
    doc = frappe.get_doc(doctype, name)
    doc.check_permission('read')
    html = email_html(doc, actor)
    frappe.sendmail(recipients=[actor], sender='notifications@snrgindia.com',
                    subject=f'Approval required: {name}', message=html, raw_html=True,
                    reference_doctype=doctype, reference_name=name)


def on_request_saved(doc, method=None):
    """Optional request delivery; existing notifications are unchanged until pilot is enabled."""
    config = frappe.conf.get('outlook_approvals') or {}
    if not config.get('enabled') or not config.get('send_on_request'):
        return
    previous = doc.get_doc_before_save()
    if doc.doctype == 'Purchase Order':
        if doc.docstatus != 0 or doc.workflow_field != 'Pending Approval':
            return
        if previous and previous.workflow_field == 'Pending Approval':
            return
        order = doc
    elif doc.doctype == 'Credit PTP':
        if not doc.sales_order:
            return
        order = frappe.get_doc('Sales Order', doc.sales_order)
        if order.custom_credit_approval_status != 'Pending':
            return
    else:
        # Covers older request buttons that save the SO instead of creating a PTP.
        if doc.docstatus != 0 or doc.custom_credit_approval_status != 'Pending':
            return
        if not doc.custom_snrg_request_time:
            return
        if previous and str(previous.custom_snrg_request_time) == str(doc.custom_snrg_request_time):
            return
        order = doc
    try:
        config = settings()
    except Exception:
        frappe.log_error(title='Outlook approval configuration incomplete', message='Check the opt-in Outlook approval site settings. No card was sent.')
        return
    for actor in set(config['users'].values()):
        # Only send to users who can perform this specific approval now.
        original_user = frappe.session.user
        try:
            frappe.set_user(actor)
            if not order.has_permission('read'):
                continue
            if order.doctype == 'Purchase Order':
                from frappe.model.workflow import get_transitions
                if not any(t.action == 'Approve' for t in get_transitions(order)):
                    continue
            else:
                from snrg_credit_control.overrides.sales_order import _can_approve_request
                if not _can_approve_request(order):
                    continue
            send_pilot_card(order.doctype, order.name, actor)
        except Exception:
            # A mail failure must not block submitting a request for approval.
            frappe.log_error(title='Outlook approval card could not be queued',
                             message=f'{order.doctype} {order.name}: check registration and outgoing email configuration.')
        finally:
            frappe.set_user(original_user)
