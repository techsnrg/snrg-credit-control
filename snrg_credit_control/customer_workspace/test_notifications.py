"""Notification regression checks, isolated staging only; no outbound messages."""
import base64
import inspect
import json
from requests import Response
from unittest.mock import patch
import frappe
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from snrg_credit_control.customer_workspace import notifications as n, api


def run():
    if not any(word in frappe.local.site for word in ("staging", "test")):
        raise RuntimeError("Isolated staging only")
    original = frappe.session.user
    try:
        frappe.set_user("Administrator")
        preferences = frappe.get_doc("Notification Settings", "Administrator")
        preferences.set("email_notification_types", [{"notification_type": kind} for kind in ("Assignment", "Mention")])
        preferences.enabled = preferences.enable_email_notifications = 1
        preferences.save(ignore_permissions=True)
        frappe.clear_document_cache("Notification Settings", "Administrator")
        n.ensure_keys()
        key = n.status()["public_key"]
        n.ensure_keys()
        assert n.status()["public_key"] == key, "Upgrade rotated push key"
        key_bytes = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        encode = lambda raw: base64.urlsafe_b64encode(raw).decode().rstrip("=")
        subscription = {"endpoint": "https://fcm.googleapis.com/fcm/send/fixture-no-network", "keys": {"p256dh": encode(key_bytes), "auth": encode(b'1234567890abcdef')}}
        for endpoint in ("http://127.0.0.1", "https://169.254.169.254", "https://fcm.googleapis.com.evil.invalid", "https://user:pass@fcm.googleapis.com/x"):
            try:
                n.validated_subscription({**subscription, "endpoint": endpoint})
                raise AssertionError("Unsafe push endpoint accepted")
            except frappe.ValidationError:
                pass
        inspect.unwrap(n.subscribe)(subscription)
        identity = __import__('hashlib').sha256(subscription["endpoint"].encode()).hexdigest()
        assert frappe.get_doc(n.SUBSCRIPTION, identity).get_password("subscription") == json.dumps(subscription)
        with patch("frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification") as enqueue:
            api.notify(["Administrator"], "Due test", api.ACTION, "fixture", include_self=True, document=frappe._dict(doctype=api.ACTION, name="fixture", subject="Due test", assigned_to="Administrator"))
            assert enqueue.call_args.args[1]["type"] == "Assignment"
            assert enqueue.call_args.args[1]["from_user"] is None
            api.notify(["Administrator"], "Mention test", api.INTERACTION, "fixture", kind="Mention", include_self=True, document=frappe._dict(doctype=api.INTERACTION, name="fixture", summary="Mention test"))
            assert enqueue.call_args.args[1]["type"] == "Mention"
        with patch("frappe.desk.doctype.notification_log.notification_log.send_notification_email") as email, patch("frappe.enqueue"):
            log = frappe.get_doc({"doctype": "Notification Log", "type": "Assignment", "for_user": "Administrator", "document_type": api.ACTION, "subject": "Private customer/task name", "link": frappe.utils.get_url("/teamspace")}).insert(ignore_permissions=True)
            assert email.called, "Assignment did not take native email delivery path"
        # Run actual payload encryption and VAPID signing, but replace HTTP transport.
        from pywebpush import webpush
        def response(code):
            result = Response()
            result.status_code = code
            result._content = b""
            return result
        errors = []
        def inspect_webpush(*args, **kwargs):
            try:
                return webpush(*args, **kwargs)
            except Exception as exc:
                errors.append(type(exc).__name__ + ": " + str(exc))
                raise
        with patch("requests.Session.post", return_value=response(201)) as post, patch("pywebpush.webpush", side_effect=inspect_webpush):
            n.send_push(log.name)
            assert not errors, errors
            assert post.called and post.call_args.kwargs["allow_redirects"] is False
            assert b'Private customer/task name' not in post.call_args.kwargs["data"]
            assert frappe.db.get_value(n.SUBSCRIPTION, identity, "last_status") == "Accepted"
        with patch("requests.Session.post", return_value=response(410)):
            n.send_push(log.name)
            assert not frappe.db.get_value(n.SUBSCRIPTION, identity, "enabled")
        frappe.set_user("Guest")
        try:
            n.status()
            raise AssertionError("Guest accessed push settings")
        except frappe.PermissionError:
            pass
        return {"passed": ["stable private VAPID keys", "encrypted device subscription", "SSRF endpoint rejection", "emailable Assignment/Mention routing", "self reminders", "real Web Push encryption/signing", "no redirects or unencrypted transport content", "expired subscription disabled", "guest denied"], "fixtures": "rolled back; no network or email delivery"}
    finally:
        frappe.db.rollback()
        frappe.clear_document_cache("Notification Settings", "Administrator")
        frappe.set_user(original)
