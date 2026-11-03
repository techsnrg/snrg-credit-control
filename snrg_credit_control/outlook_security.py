"""Cryptographic checks for Outlook actions. No Frappe dependencies."""
import hashlib
import hmac
import time
import uuid

import jwt

ACTION_CLIENT = '48af08dc-f6d2-435f-b2a7-069abd99c086'


def validate_identity(token, key, *, tenant, audiences, scope='Approval.Execute'):
    tenant = str(uuid.UUID(tenant))
    claims = jwt.decode(token, key, algorithms=['RS256'], audience=audiences,
                        options={'require': ['exp', 'iat', 'nbf', 'iss', 'aud', 'tid', 'oid']},
                        leeway=30)
    issuers = {f'https://login.microsoftonline.com/{tenant}/v2.0', f'https://sts.windows.net/{tenant}/'}
    if claims['iss'] not in issuers or claims['tid'] != tenant:
        raise ValueError('Untrusted Microsoft tenant')
    if (claims.get('azp') or claims.get('appid')) != ACTION_CLIENT:
        raise ValueError('Unexpected Microsoft client')
    if scope not in claims.get('scp', '').split():
        raise ValueError('Missing approval scope')
    return claims


def signing_key(encryption_key):
    if not encryption_key:
        raise ValueError('Site encryption key is required')
    return hmac.new(encryption_key.encode(), b'snrg-outlook-approval-v1', hashlib.sha256).digest()


def issue_request(*, key, actor, doctype, name, version, lifetime=86400):
    if doctype not in {'Purchase Order', 'Sales Order'}:
        raise ValueError('Unsupported approval type')
    now = int(time.time())
    return jwt.encode(dict(iss='snrg-erp', aud='snrg-outlook-approval', sub=actor,
                           doctype=doctype, name=name, version=version, iat=now,
                           exp=now + min(lifetime, 86400), jti=str(uuid.uuid4())), key, algorithm='HS256')


def verify_request(token, *, key, actor):
    claims = jwt.decode(token, key, algorithms=['HS256'], audience='snrg-outlook-approval',
                        issuer='snrg-erp', options={'require': ['exp', 'iat', 'sub', 'doctype', 'name', 'version', 'jti']})
    if claims['sub'] != actor or claims['doctype'] not in {'Purchase Order', 'Sales Order'}:
        raise ValueError('This approval belongs to a different recipient')
    return claims
