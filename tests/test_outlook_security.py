import importlib.util
import time
import unittest
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

spec = importlib.util.spec_from_file_location('security', Path(__file__).parents[1] / 'snrg_credit_control/outlook_security.py')
sec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sec)
TENANT='68d0c4b0-c411-42b3-8c46-a37f2afe69aa'
APP='03273ef2-6545-4f9d-9d8b-a6c447bbaa07'

class SecurityTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  cls.public=cls.private.public_key()
 def claims(self,**changes):
  now=int(time.time())
  c=dict(iss=f'https://login.microsoftonline.com/{TENANT}/v2.0',tid=TENANT,aud=APP,oid='test-user-object-id',azp=sec.ACTION_CLIENT,scp='Approval.Execute',iat=now,nbf=now,exp=now+600)
  c.update(changes);return c
 def check_identity(self,c):
  token=jwt.encode(c,self.private,algorithm='RS256')
  return sec.validate_identity(token,self.public,tenant=TENANT,audiences=[APP])
 def test_valid_identity(self):self.assertEqual(self.check_identity(self.claims())['oid'],'test-user-object-id')
 def test_wrong_tenant_issuer_client_audience_scope_expiry(self):
  for changes in [dict(tid='another-tenant'),dict(iss='https://attacker.invalid'),dict(azp='not-outlook'),dict(aud='another-app'),dict(scp='User.Read'),dict(exp=int(time.time())-120)]:
   with self.subTest(changes=changes),self.assertRaises(Exception):self.check_identity(self.claims(**changes))
 def test_missing_oid(self):
  c=self.claims();del c['oid']
  with self.assertRaises(Exception):self.check_identity(c)
 def test_wrong_signature(self):
  key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  token=jwt.encode(self.claims(),key,algorithm='RS256')
  with self.assertRaises(Exception):sec.validate_identity(token,self.public,tenant=TENANT,audiences=[APP])
 def test_request_binding_and_tampering(self):
  key=sec.signing_key('test-encryption-key')
  token=sec.issue_request(key=key,actor='approver@example.test',doctype='Purchase Order',name='PO-1',version='version-1')
  self.assertEqual(sec.verify_request(token,key=key,actor='approver@example.test')['version'],'version-1')
  with self.assertRaises(Exception):sec.verify_request(token,key=key,actor='forwarded@example.test')
  parts=token.split('.');parts[1]=parts[1][:-1]+('A' if parts[1][-1]!='A' else 'B')
  with self.assertRaises(Exception):sec.verify_request('.'.join(parts),key=key,actor='approver@example.test')
 def test_expired_request(self):
  key=sec.signing_key('key');t=sec.issue_request(key=key,actor='a',doctype='Sales Order',name='SO-1',version='v',lifetime=-1)
  with self.assertRaises(Exception):sec.verify_request(t,key=key,actor='a')
 def test_unsupported_document_and_missing_key(self):
  with self.assertRaises(ValueError):sec.issue_request(key=b'k',actor='a',doctype='User',name='Administrator',version='v')
  with self.assertRaises(ValueError):sec.signing_key('')

if __name__=='__main__':unittest.main()
