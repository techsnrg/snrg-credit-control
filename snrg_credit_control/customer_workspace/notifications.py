"""Private, opt-in browser Web Push alongside native notification emails."""
import base64
import hashlib
import json
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime
from snrg_credit_control.customer_workspace.api import ACTION, INTERACTION, guard, internal

SUBSCRIPTION = "Teamspace Push Subscription"
SETTINGS = "Teamspace Push Settings"


def ensure_keys():
    """Initialize once; never rotate keys or invalidate devices during upgrades."""
    if not frappe.db.exists("DocType", SETTINGS):
        return
    settings = frappe.get_doc(SETTINGS)
    if settings.public_key and settings.get_password("private_key", raise_exception=False):
        return
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    key = ec.generate_private_key(ec.SECP256R1())
    settings.public_key = base64.urlsafe_b64encode(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)).decode().rstrip("=")
    settings.private_key = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    settings.save(ignore_permissions=True)


def validated_subscription(value):
    data = frappe.parse_json(value) if isinstance(value, str) else value
    if not isinstance(data, dict):
        frappe.throw(_("Invalid push subscription."))
    url = urlparse(str(data.get("endpoint") or ""))
    host = (url.hostname or "").lower()
    approved = host in {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"} or host.endswith(".notify.windows.com")
    if not approved or url.scheme != "https" or url.port not in (None, 443) or url.username or url.password or url.fragment or len(url.geturl()) > 4096:
        frappe.throw(_("Unsupported push service."))
    keys = data.get("keys") or {}
    for field, length in (("p256dh", 65), ("auth", 16)):
        try:
            raw = base64.urlsafe_b64decode(keys[field] + "=" * (-len(keys[field]) % 4))
            if len(raw) != length or (field == "p256dh" and raw[0] != 4):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            frappe.throw(_("Invalid push encryption keys."))
    return {"endpoint": url.geturl(), "keys": {k: keys[k] for k in ("p256dh", "auth")}}


@frappe.whitelist()
def status():
    guard()
    public_key = frappe.db.get_single_value(SETTINGS, "public_key")
    from frappe.desk.doctype.notification_settings.notification_settings import is_email_notifications_enabled_for_type
    return {"configured": bool(public_key), "public_key": public_key, "email": {kind.lower(): is_email_notifications_enabled_for_type(frappe.session.user, kind) for kind in ("Assignment", "Mention")}}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60)
def subscribe(subscription):
    guard()
    if not frappe.db.get_single_value(SETTINGS, "public_key"):
        frappe.throw(_("Push notifications are not configured yet."))
    data = validated_subscription(subscription)
    identity = hashlib.sha256(data["endpoint"].encode()).hexdigest()
    if frappe.db.exists(SUBSCRIPTION, identity):
        doc = frappe.get_doc(SUBSCRIPTION, identity)
    else:
        if frappe.db.count(SUBSCRIPTION, {"user": frappe.session.user, "enabled": 1}) >= 20:
            frappe.throw(_("Too many registered devices. Remove an old device first."))
        doc = frappe.new_doc(SUBSCRIPTION)
        doc.name = identity
    doc.update({"user": frappe.session.user, "subscription": json.dumps(data), "enabled": 1})
    doc.save(ignore_permissions=True)
    return {"enabled": True}


@frappe.whitelist(methods=["POST"])
def unsubscribe(endpoint):
    guard()
    identity = hashlib.sha256(str(endpoint).encode()).hexdigest()
    if frappe.db.get_value(SUBSCRIPTION, identity, "user") == frappe.session.user:
        frappe.db.set_value(SUBSCRIPTION, identity, "enabled", 0)
    return {"enabled": False}


def queue_push(doc, method=None):
    if doc.document_type not in (ACTION, INTERACTION) or not internal(doc.for_user):
        return
    if frappe.db.exists(SUBSCRIPTION, {"user": doc.for_user, "enabled": 1}):
        frappe.enqueue("snrg_credit_control.customer_workspace.notifications.send_push", notification=doc.name, enqueue_after_commit=True)


def send_push(notification):
    from pywebpush import webpush, WebPushException
    from py_vapid import Vapid
    from requests import Session
    from frappe.desk.doctype.notification_settings.notification_settings import is_notifications_enabled
    doc = frappe.get_doc("Notification Log", notification)
    if doc.document_type not in (ACTION, INTERACTION) or not internal(doc.for_user) or not is_notifications_enabled(doc.for_user):
        return
    settings = frappe.get_doc(SETTINGS)
    private_key = settings.get_password("private_key", raise_exception=False)
    if not private_key:
        return
    # Push service endpoints must never redirect into the private network.
    class PushSession(Session):
        def post(self, *args, **kwargs):
            kwargs["allow_redirects"] = False
            return super().post(*args, **kwargs)
    contact = frappe.db.get_value("Email Account", {"default_outgoing": 1, "enable_outgoing": 1}, "email_id") or "nikhil@snrgindia.com"
    with PushSession() as session:
        for name in frappe.get_all(SUBSCRIPTION, filters={"user": doc.for_user, "enabled": 1}, pluck="name", limit_page_length=20):
            subscription = frappe.get_doc(SUBSCRIPTION, name)
            data = validated_subscription(subscription.get_password("subscription"))
            try:
                # Use the original event snapshot, not the task’s later current state.
                from snrg_credit_control.customer_workspace.notification_content import push_payload
                response = webpush(subscription_info=data, data=json.dumps(push_payload(doc)), vapid_private_key=Vapid.from_pem(private_key.encode()), vapid_claims={"sub": "mailto:" + contact}, ttl=3600, timeout=10, requests_session=session)
                if not 200 <= response.status_code < 300:
                    raise WebPushException("Push service rejected notification", response=response)
                subscription.db_set({"last_status": "Accepted", "last_delivered_on": now_datetime()}, update_modified=False)
            except WebPushException as exc:
                code = exc.response.status_code if exc.response is not None else None
                subscription.db_set("last_status", f"HTTP {code}" if code else "Network error", update_modified=False)
                if code in (404, 410):
                    subscription.db_set("enabled", 0, update_modified=False)
            except Exception:
                # Never persist endpoint tokens or authorization headers in error logs.
                subscription.db_set("last_status", "Delivery error", update_modified=False)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=2, seconds=60)
def send_test():
    """Self-only test, explicitly initiated from this user's notification panel."""
    guard()
    from frappe.desk.doctype.notification_settings.notification_settings import is_notifications_enabled, is_email_notifications_enabled_for_type
    if not is_notifications_enabled(frappe.session.user):
        frappe.throw(_("Enable system notifications in your notification settings first."))
    doc = frappe.get_doc({"doctype": "Notification Log", "type": "Assignment", "for_user": frappe.session.user, "document_type": ACTION, "subject": "Teamspace notification test", "email_content": "This is your requested delivery test. No customer or accounting records were changed.", "link": frappe.utils.get_url("/teamspace"), "email_header": "Teamspace test"}).insert(ignore_permissions=True)
    return {"name": doc.name, "email_enabled": is_email_notifications_enabled_for_type(frappe.session.user, "Assignment"), "push_devices": frappe.db.count(SUBSCRIPTION, {"user": frappe.session.user, "enabled": 1})}
