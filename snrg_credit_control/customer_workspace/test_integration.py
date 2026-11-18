"""Transactional integration checks. Run only on an isolated test/staging site.
bench --site TEST_SITE execute snrg_credit_control.customer_workspace.test_integration.run
"""
from unittest.mock import patch
import frappe
from frappe.utils import today, add_days
from snrg_credit_control.customer_workspace import api


def run():
    if not ("staging" in frappe.local.site or "test" in frappe.local.site):
        raise RuntimeError("Integration fixtures are restricted to test/staging sites")
    original = frappe.session.user
    results = []
    try:
        frappe.set_user("Administrator")
        employees = []
        for suffix in ("owner", "assignee", "other"):
            user = f"cw-{frappe.generate_hash(length=8)}-{suffix}@example.invalid"
            frappe.get_doc({"doctype": "User", "email": user, "first_name": suffix, "enabled": 1, "user_type": "System User", "send_welcome_email": 0, "roles": [{"role": "Employee"}]}).insert(ignore_permissions=True)
            employee = frappe.get_doc({"doctype": "Employee", "first_name": suffix, "employee_name": suffix, "status": "Active", "user_id": user, "company": frappe.db.get_value("Company", {}, "name"), "date_of_joining": today()})
            employee.flags.ignore_mandatory = True
            employee.insert(ignore_permissions=True)
            employees.append((user, employee.name))
        owner, assignee, other = [p[0] for p in employees]
        customer = frappe.get_doc({"doctype": "Customer", "customer_name": "Workspace integration " + frappe.generate_hash(length=8), "customer_type": "Company"})
        customer.flags.ignore_mandatory = True
        customer.insert(ignore_permissions=True)
        from snrg_credit_control.customer_workspace.directory import customer_directory
        from snrg_credit_control.customer_workspace.receivables import customer_ar, customer_ar_invoices
        contact = frappe.get_doc({"doctype": "Contact", "first_name": "Workspace directory test"}).insert(ignore_permissions=True)
        contact.db_set("mobile_no", "9876543210", update_modified=False)
        customer.db_set("customer_primary_contact", contact.name, update_modified=False)
        customer.db_set("mobile_no", "", update_modified=False)
        if frappe.get_meta("Customer").has_field("custom_mobile_number"):
            customer.db_set("custom_mobile_number", "", update_modified=False)
        found = customer_directory(search="9876543210", status="all")
        assert any(row.name == customer.name and row.mobile_number == "9876543210" for row in found["rows"])
        allowed = frappe.get_list("Company", fields=["name", "default_currency"], limit_page_length=1)
        if allowed:
            company = allowed[0].name
            # Exercise the real permission-checked engine against the staging ledger.
            actual = customer_ar(company, customer=customer.name, balance="all")
            assert actual["currency"] == allowed[0].default_currency
            assert customer_ar_invoices(company, customer.name, balance="all")["rows"] == []
            with patch("frappe.desk.query_report.run", return_value={"result": [{"party": customer.name, "outstanding": 1000, "total_due": 600, "range0": 400, "advance": 50, "range1": 400, "range2": 100, "range4": 40, "range5": 60}, {"party": "Total", "outstanding": 1000}]}):
                ar = customer_ar(company, balance="all", search="9876543210")
                assert len(ar["rows"]) == 1
                assert ar["totals"]["outstanding"] == 1000 and ar["totals"]["due_now"] == 600
                assert ar["totals"]["not_yet_due"] == 400 and ar["totals"]["advance"] == 50
                assert ar["rows"][0]["age_0_30"] == 400 and ar["rows"][0]["age_over_90"] == 100
                assert not customer_ar(company, balance="credit")["rows"]
            with patch("frappe.desk.query_report.run", return_value={"result": [{"voucher_type": "Sales Invoice", "voucher_no": "AGE-TEST", "posting_date": "2026-11-01", "due_date": "2026-11-10", "outstanding": 100}, {"voucher_type": "Sales Invoice", "voucher_no": "FUTURE-TEST", "posting_date": "2026-11-01", "due_date": "2026-11-26", "outstanding": 200}]}):
                aged = customer_ar_invoices(company, customer.name, report_date="2026-11-19")
                assert aged["rows"][0]["age_days"] == 9 and aged["rows"][1]["age_days"] == -7
            results.append("customer phone fallback/search + real AR engine + compact AR totals, ageing and filters")
        frappe.set_user(owner)
        assert not api.bootstrap()["can_ar"]
        if allowed:
            try:
                customer_ar(allowed[0].name)
                raise AssertionError("Employee could read financial balances without report access")
            except frappe.PermissionError:
                pass
        results.append("shared directory does not grant financial report access")
        with patch("frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification") as notifications:
            result = api.log_interaction({"customer": customer.name, "summary": "Discussed damaged cartons. @assignee arrange collection.", "mentions": [employees[1][1]], "actions": [{"subject": "Collect cartons", "assigned_to": assignee, "due_date": today(), "due_time": "14:00", "action_type": "Return pickup"}]})
            assert len(result["actions"]) == 1
            action = frappe.get_doc(api.ACTION, result["actions"][0])
            assert action.customer_name == customer.customer_name
            assert action.event and frappe.db.get_value("Event", action.event, "reference_docname") == action.name
            assert notifications.call_count >= 2
            results.append("interaction + mention notification + assigned action + calendar creation")
            assert api.history(customer.name)["interactions"][0].mentions[0].employee == employees[1][1]
            assert len(api.actions(scope="assigned", customer=customer.name)) == 1
            try:
                api.actions(scope="team")
                raise AssertionError("Non-manager could read team work")
            except frappe.PermissionError:
                pass
            results.append("shared history and non-manager team access denied")
            frappe.set_user(other)
            assert api.permission(action, permission_type="read")
            assert frappe.has_permission(api.ACTION, "read", doc=action)
            assert not api.permission(action, permission_type="write")
            try:
                api.update_action(action.name, {"status": "Completed", "update": "unauthorized"}, str(action.modified))
                raise AssertionError("Unrelated employee could mutate action")
            except frappe.PermissionError:
                pass
            frappe.set_user(assignee)
            assert len(api.actions(customer=customer.name)) == 1
            rescheduled = api.update_action(action.name, {"due_date": add_days(today(), 1), "due_time": "15:00", "update": "Customer requested tomorrow."}, str(action.modified))
            assert str(frappe.db.get_value("Event", action.event, "starts_on")).endswith("15:00:00")
            action = frappe.get_doc(api.ACTION, action.name)
            updated = api.update_action(action.name, {"status": "Completed", "update": "Collected all cartons."}, str(action.modified))
            assert updated["status"] == "Completed"
            assert frappe.db.get_value("Event", action.event, "status") == "Completed"
            assert len(api.history(customer.name)["interactions"]) == 3
            try:
                api.update_action(action.name, {"status": "Open", "update": "stale"}, str(action.modified))
                raise AssertionError("Stale save accepted")
            except frappe.TimestampMismatchError:
                pass
            results.append("assignee completion + calendar synchronization + audit history + stale save rejected")
            event = frappe.get_doc("Event", action.event)
            event.subject = "Changed directly"
            try:
                event.save(ignore_permissions=True)
                raise AssertionError("Calendar projection could be edited directly")
            except frappe.ValidationError:
                pass
            frappe.set_user("Guest")
            try:
                api.bootstrap()
                raise AssertionError("Guest could access directory")
            except frappe.PermissionError:
                pass
            results.append("calendar projection protected and guest directory denied")
    finally:
        frappe.db.rollback()
        frappe.set_user(original)
    print({"passed": results, "fixtures": "rolled back"})
