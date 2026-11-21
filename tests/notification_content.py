"""Event snapshot regression tests; no Frappe site or outbound delivery."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

frappe = types.ModuleType('frappe')
frappe.session = types.SimpleNamespace(user='junior@example.test')
frappe.utils = types.SimpleNamespace(get_fullname=lambda user: {'junior@example.test':'Kajal', 'owner@example.test':'Nikhil'}.get(user,user),get_url=lambda path='':'https://erp.example.test'+path)
sys.modules['frappe'] = frappe
spec = importlib.util.spec_from_file_location('content',Path(__file__).resolve().parents[1]/'snrg_credit_control/customer_workspace/notification_content.py')
c = importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class Doc(dict):
    __getattr__ = dict.get


def task(**values):
    return Doc(doctype='Customer Action',name='CA-2026-00009',subject='Collect email addresses',assigned_to='junior@example.test',due_date='2026-11-22',due_time='14:30:00',status='Completed',description='Confirm the customer list',**values)


class ContentTests(unittest.TestCase):
    def test_task_update_shows_actor_outcome_changes_and_deadline(self):
        result=c.snapshot(task(customer='CUST-1',customer_name='Example Customer'),'Old subject',event='updated',reason='Collected 24 email addresses.',changes={'status':('In Progress','Completed'),'due_date':('2026-11-21','2026-11-22'),'assigned_to':('owner@example.test','junior@example.test')})
        self.assertEqual(result['subject'],'Kajal completed: Collect email addresses')
        body=c.plain(result['email_content'])
        for detail in ['Kajal','Collected 24 email addresses.','In Progress → Completed','21 Nov 2026 → 22 Nov 2026','Nikhil → Kajal','Example Customer','22 Nov 2026 · 2:30 PM','Confirm the customer list']:
            self.assertIn(detail,body)
        self.assertEqual(result['link'],'https://erp.example.test/teamspace?task=CA-2026-00009')
        self.assertNotIn('due_time:',body)

    def test_general_assignment_and_mentions(self):
        self.assertIn('General task', c.plain(c.snapshot(task(),'Assigned',event='assigned')['email_content']))
        self.assertEqual(c.snapshot(task(),'Mention',kind='Mention')['subject'],'Kajal mentioned you: Collect email addresses')

    def test_no_change_is_invented_and_html_is_escaped(self):
        doc=task();doc['description']='<img src=x onerror=alert(1)> & notes'
        result=c.snapshot(doc,'Update',event='updated',reason='<script>bad()</script>')
        self.assertNotIn('→', result['email_content'])
        self.assertNotIn('<script>', result['email_content'])
        self.assertNotIn('<img', result['email_content'])
        self.assertIn('&lt;img',result['email_content'])

    def test_event_snapshot_survives_later_task_edit(self):
        doc=task();result=c.snapshot(doc,'Update',event='updated',reason='First outcome')
        doc['subject']='A later title';doc['description']='Later instructions'
        log=Doc(name='LOG-1',**result)
        payload=c.push_payload(log)
        self.assertIn('Collect email addresses',payload['title'])
        self.assertIn('First outcome',payload['body'])
        self.assertNotIn('Later instructions',payload['body'])
        self.assertEqual(payload['url'],'/teamspace?task=CA-2026-00009')

    def test_push_limits_and_foreign_links(self):
        log=Doc(name='LOG-1',subject='x'*400,email_content='<p>text</p>'*200,link='https://evil.example/teamspace')
        payload=c.push_payload(log)
        self.assertLessEqual(len(payload['title']),120)
        self.assertLessEqual(len(payload['body']),280)
        self.assertEqual(payload['url'],'/teamspace')
        for url in ['javascript:alert(1)','//evil.example/teamspace','https://erp.example.test:9999/teamspace']:
            log['link']=url;self.assertEqual(c.push_payload(log)['url'],'/teamspace')

    def test_interaction_has_conversation_and_outcome(self):
        doc=Doc(doctype='Customer Interaction',name='CI-1',customer='CUST-1',customer_name='Example Customer',summary='Please call tomorrow.',call_outcome='Call back')
        result=c.snapshot(doc,'Mention',kind='Mention')
        self.assertIn('Please call tomorrow.',c.plain(result['email_content']))
        self.assertIn('Call back',c.plain(result['email_content']))
        self.assertEqual(c.push_payload(Doc(name='LOG-1',**result))['url'],'/desk/customer-interaction/CI-1')

if __name__=='__main__':unittest.main()
