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
            with patch("frappe.desk.query_report.run", return_value={"result": [{"party": customer.name, "outstanding": 1000, "total_due": 600, "range0": 400, "advance": 50, "range1": 400, "range2": 100, "range4": 40, "range5": 60}, {"party": "Total", "outstanding": 1000}]}) as report_run:
                ar = customer_ar(company, balance="all", search="9876543210")
                assert report_run.call_args_list[0].kwargs["filters"]["ageing_based_on"] == "Due Date"
                assert report_run.call_args_list[1].kwargs["filters"]["ageing_based_on"] == "Posting Date"
                assert len(ar["rows"]) == 1
                assert ar["totals"]["outstanding"] == 1000 and ar["totals"]["due_now"] == 600
                assert ar["totals"]["not_yet_due"] == 400 and ar["totals"]["advance"] == 50
                assert ar["rows"][0]["age_0_30"] == 400 and ar["rows"][0]["age_91_120"] == 40 and ar["rows"][0]["age_over_120"] == 60
                assert not customer_ar(company, balance="credit")["rows"]
            with patch("frappe.desk.query_report.run", return_value={"result": [{"voucher_type": "Sales Invoice", "voucher_no": "AGE-TEST", "posting_date": "2026-11-01", "due_date": "2026-11-10", "outstanding": 100}, {"voucher_type": "Sales Invoice", "voucher_no": "FUTURE-TEST", "posting_date": "2026-11-01", "due_date": "2026-11-26", "outstanding": 200}]}):
                aged = customer_ar_invoices(company, customer.name, report_date="2026-11-19")
                assert aged["rows"][0]["age_days"] == 18 and aged["rows"][1]["age_days"] == 18
            results.append("customer phone fallback/search + real AR engine + compact AR totals, ageing and filters")
        supplier = frappe.get_doc({"doctype": "Supplier", "supplier_name": "Teamspace integration " + frappe.generate_hash(length=8), "supplier_type": "Company"})
        supplier.flags.ignore_mandatory = True
        supplier.insert(ignore_permissions=True)
        supplier.db_set("supplier_primary_contact", contact.name, update_modified=False)
        supplier.db_set("mobile_no", "", update_modified=False)
        from snrg_credit_control.customer_workspace.directory import supplier_directory
        from snrg_credit_control.customer_workspace.payables import supplier_ap
        from snrg_credit_control.customer_workspace.timeline import timeline
        from snrg_credit_control.customer_workspace.settings import save_visibility_settings, allowed as feature_allowed
        assert any(row.name == supplier.name and row.party_type == "Supplier" and row.mobile_number == "9876543210" for row in supplier_directory(search="9876543210", status="all")["rows"])
        if allowed:
            assert supplier_ap(allowed[0].name, supplier=supplier.name, balance="all")["rows"] == []
        # Active-only lists and ordering must hold on the server, before pagination.
        extra_customer = frappe.get_doc({"doctype": "Customer", "customer_name": customer.customer_name + " Z", "customer_type": "Company"})
        extra_customer.flags.ignore_mandatory = True
        extra_customer.insert(ignore_permissions=True)
        disabled_customer = frappe.get_doc({"doctype": "Customer", "customer_name": customer.customer_name + " Hidden", "customer_type": "Company", "disabled": 1})
        disabled_customer.flags.ignore_mandatory = True
        disabled_customer.insert(ignore_permissions=True)
        disabled_supplier = frappe.get_doc({"doctype": "Supplier", "supplier_name": supplier.supplier_name + " Hidden", "supplier_type": "Company", "disabled": 1})
        disabled_supplier.flags.ignore_mandatory = True
        disabled_supplier.insert(ignore_permissions=True)
        for status_filter in ("active", "all", "disabled"):
            assert disabled_customer.name not in [r.name for r in customer_directory(search=customer.customer_name, status=status_filter)["rows"]]
            assert not supplier_directory(search=disabled_supplier.name, status=status_filter)["rows"]
        assert [r.name for r in customer_directory(search=customer.customer_name, sort="name_desc")["rows"]] == [extra_customer.name, customer.name]
        assert customer_directory(search=customer.customer_name, sort="name_asc", start=1)["rows"][0].name == extra_customer.name
        if allowed:
            mocked = {"result": [{"party": customer.name, "outstanding": 100, "total_due": 70}, {"party": extra_customer.name, "outstanding": 200, "total_due": 120}, {"party": disabled_customer.name, "outstanding": 900, "total_due": 900}]}
            with patch("frappe.desk.query_report.run", return_value=mocked):
                rows = customer_ar(company, balance="all", search=customer.customer_name, sort="outstanding_asc")
                assert [r["name"] for r in rows["rows"]] == [customer.name, extra_customer.name]
                assert rows["totals"]["outstanding"] == 300
                assert customer_ar(company, balance="all", search=customer.customer_name, sort="outstanding_desc", start=1)["rows"][0]["name"] == customer.name
            with patch("frappe.desk.query_report.run", return_value={"result": [{"party": supplier.name, "outstanding": 100}, {"party": disabled_supplier.name, "outstanding": 900}]}):
                assert supplier_ap(company, balance="all", search=supplier.supplier_name)["totals"]["outstanding"] == 100
            from snrg_credit_control.customer_workspace.receivables import customer_ar_snapshot
            def snapshot_report(name, **kwargs):
                return {"result": [{"party": customer.name, "outstanding": 80, "total_due": 80}]} if name.endswith("Summary") else {"result": [
                    {"voucher_type": "Sales Invoice", "posting_date": add_days(today(), -40), "due_date": add_days(today(), -5), "outstanding": 80},
                    {"voucher_type": "Sales Invoice", "posting_date": add_days(today(), -90), "outstanding": 0},
                    {"voucher_type": "Sales Invoice", "posting_date": add_days(today(), -100), "outstanding": -10}]}
            with patch("frappe.desk.query_report.run", side_effect=snapshot_report):
                snapshot = customer_ar_snapshot(company, customer.name)
                assert snapshot["outstanding"] == 80 and snapshot["oldest_bill_days"] == 40
        results.append("disabled parties hidden across selectors and finance; stable sorting before pagination; oldest unpaid bill uses invoice date")
        frappe.set_user(owner)
        supplier_result = api.log_interaction({"supplier": supplier.name, "summary": "Supplier confirmed dispatch. @assignee coordinate delivery.", "mentions": [employees[1][1]], "actions": [{"subject": "Confirm supplier delivery", "assigned_to": assignee, "due_date": add_days(today(), 2), "due_time": "11:30", "action_type": "Delivery"}]})
        general = api.create_action({"subject": "File GST return", "assigned_to": assignee, "due_date": add_days(today(), 2), "due_time": "10:30:00"})
        assert general["party_type"] == "General" and general["party_name"] == "General task"
        general_doc = frappe.get_doc(api.ACTION, general["name"])
        assert not general_doc.customer and not general_doc.supplier and general_doc.event
        assert frappe.db.get_value("Event", general_doc.event, "subject") == "File GST return"
        frappe.set_user(assignee)
        assert any(row.name == general_doc.name for row in api.personal_agenda())
        api.update_action(general_doc.name, {"status": "Completed", "update": "Return filed"}, str(general_doc.modified))
        general_doc.reload()
        assert general_doc.status == "Completed" and general_doc.completed_on
        assert not frappe.db.exists(api.INTERACTION, {"action_reference": general_doc.name})
        assert frappe.db.exists("Comment", {"reference_doctype": api.ACTION, "reference_name": general_doc.name, "content": ["like", "%Return filed%"]})
        frappe.set_user(owner)
        results.append("general task creation, assignment, agenda, event and completion without fabricated interaction")
        standalone = api.create_action({"supplier": supplier.name, "subject": "Standalone supplier plan", "assigned_to": assignee, "due_date": add_days(today(), 3)})
        assert not standalone.interaction
        assert len(api.history(supplier=supplier.name)["interactions"]) == 1
        supplier_action = frappe.get_doc(api.ACTION, supplier_result["actions"][0])
        assert not supplier_action.customer and supplier_action.supplier == supplier.name
        assert supplier_action.supplier_name == supplier.supplier_name and supplier_action.event
        assert api.history(supplier=supplier.name)["interactions"][0].name == supplier_result["name"]
        assert all(row.supplier == supplier.name for row in api.actions(scope="customer", supplier=supplier.name))
        combined = timeline(supplier=supplier.name, include_transactions=0)
        assert {row["kind"] for row in combined["events"]} == {"interaction", "plan"}
        assert combined["events"][0]["kind"] == "plan" and combined["events"][0]["action"].assigned_to == assignee
        with patch("snrg_credit_control.customer_workspace.timeline._transactions") as hidden_transactions:
            timeline(supplier=supplier.name, include_transactions=0)
            hidden_transactions.assert_not_called()
        try:
            api.log_interaction({"customer": customer.name, "supplier": supplier.name, "summary": "invalid mixed party"})
            raise AssertionError("Mixed customer/supplier interaction was allowed")
        except frappe.ValidationError:
            pass
        try:
            save_visibility_settings({"restrict_ar": 1})
            raise AssertionError("Employee could change visibility settings")
        except frappe.PermissionError:
            pass
        frappe.set_user(assignee)
        assert any(row.party_type == "Supplier" and row.party == supplier.name for row in api.personal_agenda())
        api.update_action(supplier_action.name, {"status": "Completed", "update": "Delivery confirmed"}, str(supplier_action.modified))
        assert len(api.history(supplier=supplier.name)["interactions"]) == 2
        attachment = frappe.get_doc({"doctype": "File", "file_name": "teamspace-fixture-" + frappe.generate_hash(length=8) + ".txt", "is_private": 1, "content": "Private Teamspace fixture"}).insert(ignore_permissions=True)
        rich = api.log_interaction({"supplier": supplier.name, "summary": "Dispatch confirmed", "summary_html": "<p><strong>Dispatch confirmed</strong><script>alert(1)</script></p>", "attachments": [attachment.name]})
        rich_doc = frappe.get_doc(api.INTERACTION, rich["name"])
        assert "<strong>" in rich_doc.summary_html and "<script" not in rich_doc.summary_html
        saved_file = frappe.get_doc("File", attachment.name)
        assert saved_file.is_private and saved_file.attached_to_name == rich_doc.name and saved_file.attached_to_doctype == api.INTERACTION
        try:
            api.log_interaction({"supplier": supplier.name, "summary": "invalid reuse", "attachments": [attachment.name]})
            raise AssertionError("Already-linked file was reused")
        except frappe.PermissionError:
            pass
        try:
            api.log_interaction({"supplier": supplier.name, "summary": "invalid image", "summary_html": '<p><img src="https://example.invalid/track.png"></p>'})
            raise AssertionError("External image tracking was allowed")
        except frappe.ValidationError:
            pass
        frappe.set_user("Administrator")
        # A selected employee still needs native financial roles; excluded admins are blocked too.
        save_visibility_settings({"restrict_ar": 1, "restrict_ap": 1, "restrict_transactions": 1, "access": [{"feature": "AR", "user": owner}]})
        assert not feature_allowed("AR") and not api.bootstrap()["can_ar"]
        assert not api.bootstrap()["can_ap"]
        with patch("snrg_credit_control.customer_workspace.timeline._transactions") as hidden_transactions:
            timeline(supplier=supplier.name, include_transactions=1)
            hidden_transactions.assert_not_called()
        frappe.set_user(owner)
        assert feature_allowed("AR") and not api.bootstrap()["can_ar"]
        frappe.set_user("Administrator")
        save_visibility_settings({"access": []})
        save_visibility_settings({"excluded": [{"feature": "AR", "user": owner}, {"feature": "AP", "user": owner}, {"feature": "AP", "user": assignee}]})
        assert not feature_allowed("AR", owner) and not feature_allowed("AP", owner)
        assert feature_allowed("AR", assignee) and not feature_allowed("AP", assignee)
        assert feature_allowed("AR", other) and feature_allowed("AP", other) and feature_allowed("Transactions", other)
        save_visibility_settings({"restrict_ar": 1, "access": [{"feature": "AR", "user": "Administrator"}], "excluded": [{"feature": "AR", "user": "Administrator"}]})
        assert not feature_allowed("AR") and not api.bootstrap()["can_ar"]
        if allowed:
            try:
                customer_ar(allowed[0].name)
                raise AssertionError("Excluded administrator could read AR directly")
            except frappe.PermissionError:
                pass
        save_visibility_settings({"access": [], "excluded": []})
        results.append("per-user AR/AP exclusions, unaffected-user access and exclusion precedence over allowlist/native admin access")
        # The native document projection uses permission-checked get_list and keeps draft status explicit.
        from snrg_credit_control.customer_workspace.timeline import _transactions
        with patch("frappe.get_list", side_effect=lambda doctype, **kwargs: [frappe._dict(name="TIMELINE-INV", owner="Administrator", creation="2026-11-18 10:00:00", posting_date="2026-11-18", posting_time="10:00:00", status="Draft", docstatus=0, grand_total=20000, currency="INR")] if doctype == "Sales Invoice" else []):
            tx, sources = _transactions("Customer", customer.name, 51)
            assert len(tx) == 1 and tx[0]["amount"] == 20000 and tx[0]["status"] == "Draft"
        payment = frappe._dict(references=[frappe._dict(reference_doctype="Sales Invoice", reference_name="VISIBLE", allocated_amount=15000), frappe._dict(reference_doctype="Sales Invoice", reference_name="HIDDEN", allocated_amount=5000)])
        payment.check_permission = lambda permission: None
        original_get_doc = frappe.get_doc
        with patch("frappe.has_permission", side_effect=lambda doctype, ptype, **kwargs: doctype == "Payment Entry" or (doctype == "Sales Invoice" and kwargs.get("doc") == "VISIBLE")), patch("frappe.get_doc", side_effect=lambda *args, **kwargs: payment if args and args[0] == "Payment Entry" else original_get_doc(*args, **kwargs)), patch("frappe.get_list", return_value=[frappe._dict(name="PAY-TEST", owner="Administrator", creation="2026-11-18 10:00:00", posting_date="2026-11-18", status="Submitted", docstatus=1, payment_type="Receive", paid_amount=20000, received_amount=20000, paid_from_account_currency="INR", paid_to_account_currency="INR")]):
            tx, sources = _transactions("Customer", customer.name, 51)
            assert tx[0]["summary"] == "Payment received" and tx[0]["amount"] == 20000
            assert tx[0]["allocations"] == [{"doctype": "Sales Invoice", "name": "VISIBLE", "amount": 15000}]
        with patch("frappe.has_permission", return_value=False), patch("frappe.get_list") as unreadable:
            assert _transactions("Customer", customer.name, 51)[0] == []
            unreadable.assert_not_called()
        results.append("supplier directory, mentions, plans, unified agenda, completion audit, native AP and employee visibility restrictions")
        frappe.set_user(owner)
        assert not api.bootstrap()["can_ar"]
        if allowed:
            try:
                customer_ar(allowed[0].name)
                raise AssertionError("Employee could read financial balances without report access")
            except frappe.PermissionError:
                pass
        for outcome in ("Connected", "No answer", "Busy", "Call back", "Wrong number"):
            logged = api.log_interaction({"supplier": supplier.name, "channel": "Call", "call_outcome": outcome, "summary": "Connected discussion" if outcome == "Connected" else ""})
            assert frappe.get_doc(api.INTERACTION, logged["name"]).call_outcome == outcome
            assert any(row.get("call_outcome") == outcome for row in timeline(supplier=supplier.name, include_transactions=0)["events"])
        try:
            api.log_interaction({"supplier": supplier.name, "channel": "Call", "call_outcome": "Invalid", "summary": "Invalid outcome"})
            raise AssertionError("Invalid call outcome was accepted")
        except frappe.ValidationError:
            pass
        results.append("call outcomes saved and returned in timeline; unanswered calls allow an empty note; invalid outcomes rejected")
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
        frappe.clear_document_cache("Teamspace Settings", "Teamspace Settings")
        frappe.set_user(original)
    print({"passed": results, "fixtures": "rolled back"})
