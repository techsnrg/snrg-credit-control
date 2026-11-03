import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).parents[1]
# Load pure validation code and adapter without installing a Frappe bench.
package=ModuleType('snrg_credit_control');package.__path__=[str(ROOT/'snrg_credit_control')]
sys.modules.setdefault('snrg_credit_control',package)
from snrg_credit_control import outlook_security as security
fake=ModuleType('frappe')
fake.whitelist=lambda **kw:lambda f:f
fake.PermissionError=PermissionError
fake.AuthenticationError=PermissionError
fake.throw=lambda msg,*args:(_ for _ in ()).throw(PermissionError(msg))
sys.modules['frappe']=fake
# Minimal Response for environments without werkzeug; real Frappe supplies it.
try:
 from werkzeug.wrappers import Response
except ImportError:
 class Response:
  def __init__(self,data,status=200,**kw):self.data=data;self.status_code=status
 wrappers=ModuleType('werkzeug.wrappers');wrappers.Response=Response
 sys.modules['werkzeug.wrappers']=wrappers
from snrg_credit_control import outlook_approvals as api

class EndpointTests(unittest.TestCase):
 def setUp(self):
  fake.session=SimpleNamespace(user='approver@example.test')
  fake.flags=SimpleNamespace(snrg_outlook_actor=fake.session.user)
  fake.conf=SimpleNamespace(encryption_key='test-key')
  fake.local=SimpleNamespace(response={})
  fake.db=SimpleNamespace(get_value=Mock(return_value='PO-1'),rollback=Mock())
  self.doc=SimpleNamespace(doctype='Purchase Order',name='PO-1',modified='v1',docstatus=0,workflow_field='Pending Approval',check_permission=Mock())
  self.doc.as_dict=lambda:{'doctype':'Purchase Order','name':'PO-1'}
  fake.get_doc=Mock(return_value=self.doc)
  workflow=ModuleType('frappe.model.workflow');workflow.apply_workflow=Mock()
  self.workflow=workflow
  sys.modules['frappe.model.workflow']=workflow
 def token(self,**changes):
  d=dict(key=security.signing_key(fake.conf.encryption_key),actor=fake.session.user,doctype=self.doc.doctype,name=self.doc.name,version='v1');d.update(changes)
  return security.issue_request(**d)
 def test_po_uses_standard_workflow_and_row_lock(self):
  r=api.approve(self.token());self.assertEqual(r.status_code,200)
  self.workflow.apply_workflow.assert_called_once_with(self.doc.as_dict(),'Approve')
  fake.db.get_value.assert_called_once_with('Purchase Order','PO-1','name',for_update=True)
 def test_changed_document_rejects_before_workflow(self):
  self.doc.modified='v2';r=api.approve(self.token());self.assertEqual(r.status_code,409);self.workflow.apply_workflow.assert_not_called()
 def test_already_processed_rejects(self):
  self.doc.docstatus=1;self.doc.workflow_field='Approved'
  self.assertEqual(api.approve(self.token()).status_code,409);self.workflow.apply_workflow.assert_not_called()
 def test_wrong_recipient_and_expiry(self):
  for options in [dict(actor='other@example.test'),dict(lifetime=-1)]:
   with self.subTest(options=options):self.assertEqual(api.approve(self.token(**options)).status_code,400)
  self.workflow.apply_workflow.assert_not_called()
 def test_plain_session_cannot_call_action(self):
  fake.flags.snrg_outlook_actor=None
  with self.assertRaises(PermissionError):api.approve(self.token())
 def test_workflow_error_rolls_back(self):
  self.workflow.apply_workflow.side_effect=PermissionError('Not authorized')
  self.assertEqual(api.approve(self.token()).status_code,400);fake.db.rollback.assert_called_once()
 def test_credit_uses_existing_app_policy(self):
  self.doc.doctype='Sales Order';self.doc.name='SO-1';self.doc.custom_credit_approval_status='Pending'
  credit=ModuleType('snrg_credit_control.overrides.sales_order');credit.approve_from_email=Mock()
  sys.modules['snrg_credit_control.overrides.sales_order']=credit
  fake.local.response={'type':'redirect','location':'/old'}
  self.assertEqual(api.approve(self.token()).status_code,200)
  credit.approve_from_email.assert_called_once_with('SO-1');self.assertNotIn('location',fake.local.response)
 def test_credit_no_longer_pending(self):
  self.doc.doctype='Sales Order';self.doc.custom_credit_approval_status='Approved'
  self.assertEqual(api.approve(self.token()).status_code,409)
 def test_auth_does_not_change_other_endpoints(self):
  fake.local.request=SimpleNamespace(path='/api/method/another.method',method='POST')
  api.authenticate();self.assertEqual(fake.session.user,'approver@example.test')
 def test_get_cannot_authenticate(self):
  fake.local.request=SimpleNamespace(path=next(iter(api.PATHS)),method='GET')
  with self.assertRaises(PermissionError):api.authenticate()

if __name__=='__main__':unittest.main()
