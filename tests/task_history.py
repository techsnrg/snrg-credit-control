"""Task history merge and permission regressions; no live writes."""
import importlib.util
from pathlib import Path
from datetime import datetime
import json,sys,types,unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
class Row(dict):
    __getattr__=dict.get
frappe=types.ModuleType('frappe');frappe.whitelist=lambda **kw: lambda fn:fn;frappe._=lambda x:x
frappe.PermissionError=PermissionError
frappe.throw=lambda message,*args: (_ for _ in ()).throw(PermissionError(message))
frappe.utils=types.SimpleNamespace(get_fullname=lambda u: {'a':'Ankit','b':'Kajal'}.get(u,u))
utils=types.ModuleType('frappe.utils');utils.cint=lambda v:int(v or 0);utils.get_datetime=lambda v:datetime.fromisoformat(str(v))
api=types.ModuleType('snrg_credit_control.customer_workspace.api');api.ACTION='Customer Action';api.INTERACTION='Customer Interaction';api.guard=Mock();api.permission=lambda *a,**k:True
sys.modules.update({'frappe':frappe,'frappe.utils':utils,'snrg_credit_control.customer_workspace.api':api})
spec=importlib.util.spec_from_file_location('snrg_credit_control.customer_workspace.notification_content',ROOT/'snrg_credit_control/customer_workspace/notification_content.py');content=importlib.util.module_from_spec(spec);spec.loader.exec_module(content);sys.modules[spec.name]=content
spec=importlib.util.spec_from_file_location('history',ROOT/'snrg_credit_control/customer_workspace/task_history.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
task=Row(name='CA-1',creation='2026-11-19 09:00:00',owner='a')
def comment(name='C1',text='Called; will pay tomorrow.',when='2026-11-20 11:00:00',actor='b'):
    return Row(name=name,creation=when,owner=actor,comment_email=actor,content=text)
def interaction(text,when='2026-11-20 11:00:00'):
    return Row(name='I1',creation=when,owner='b',summary='Task title\n'+text)
def version(changed,when='2026-11-20 11:00:01'):
    return Row(name='V1',creation=when,owner='b',data=json.dumps({'changed':changed}))

class HistoryTests(unittest.TestCase):
    def setUp(self):h.permission=lambda *a,**k:True;h.guard=Mock()
    def test_existing_general_and_party_notes_remain_visible(self):
        rows=h.assemble(task,[comment()],[interaction('Delivery confirmed',when='2026-11-20 12:00:00')],[])
        self.assertEqual(len(rows),3);self.assertEqual(rows[0]['text'],'Delivery confirmed');self.assertEqual(rows[1]['actor_name'],'Kajal');self.assertEqual(rows[-1]['title'],'Created task')
    def test_duplicate_sources_and_matching_audit_become_one_update(self):
        text='Delivered.<br>status: In Progress → Completed'
        note=comment(text=text);note['subject']='Teamspace update:I1'
        rows=h.assemble(task,[note],[interaction('Delivered.\nstatus: In Progress → Completed')],[version([['status','In Progress','Completed']])])
        self.assertEqual(len(rows),2);self.assertEqual(rows[0]['text'],'Delivered.');self.assertEqual(rows[0]['changes'][0]['after'],'Completed')
    def test_independent_comments_are_never_dropped(self):
        rows=h.assemble(task,[comment(),comment(name='C2')],[],[]);self.assertEqual(len(rows),3)
    def test_ambiguous_audit_is_retained_separately(self):
        text='status: Open → Completed'
        rows=h.assemble(task,[comment(text=text),comment(name='C2',text=text)],[],[version([['status','Open','Completed']])]);self.assertEqual(len(rows),4)
    def test_audit_only_edits_and_malformed_data(self):
        versions=[version([['priority','Low','High'],['secret_key','old','new'],[['invalid'],'x','y']]),Row(name='bad',data='{broken'),Row(name='null',data='{"changed":null}')]
        rows=h.assemble(task,[],[],versions);self.assertEqual(len(rows),2);self.assertEqual([c['field'] for c in rows[0]['changes']],['priority'])
    def test_read_denial_happens_before_history_queries(self):
        frappe.get_doc=Mock(return_value=task);frappe.get_all=Mock();h.permission=lambda *a,**k:False
        with self.assertRaises(PermissionError):h.history('CA-1')
        frappe.get_all.assert_not_called()
    def test_endpoint_scopes_queries_and_paginates(self):
        frappe.get_doc=Mock(return_value=task)
        def read(kind,**kw):
            filters=kw['filters'];self.assertEqual(filters.get('reference_name',filters.get('action_reference',filters.get('docname'))),'CA-1')
            return [comment(name=str(i),when=f'2026-11-20 11:{i:02d}:00') for i in range(55)] if kind=='Comment' else []
        frappe.get_all=Mock(side_effect=read)
        result=h.history('CA-1');self.assertEqual(result['count'],56);self.assertEqual(len(result['rows']),50);self.assertTrue(result['has_more'])
        result=h.history('CA-1',50);self.assertEqual(len(result['rows']),6);self.assertFalse(result['has_more'])
    def test_html_is_returned_as_text_not_executable_markup(self):
        rows=h.assemble(task,[comment(text='&lt;img src=x onerror=bad()&gt;')],[],[])
        self.assertEqual(rows[0]['text'],'<img src=x onerror=bad()>') # Vue uses interpolation, never v-html.

if __name__=='__main__':unittest.main()
