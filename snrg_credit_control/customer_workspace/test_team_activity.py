"""Rollback-only integration tests for the private activity review. Staging only."""
from io import BytesIO
from unittest.mock import patch
import frappe
from frappe.utils import today
from snrg_credit_control.customer_workspace import api, team_activity as activity


def run():
    if not any(word in frappe.local.site for word in ("staging", "test")):
        raise RuntimeError("Isolated staging only")
    original = frappe.session.user
    try:
        frappe.set_user("Administrator")
        if not frappe.db.exists("User", activity.VIEWER):
            frappe.get_doc(dict(doctype="User", email=activity.VIEWER, first_name="Nikhil", enabled=1, user_type="System User", send_welcome_email=0, roles=[dict(role="System Manager")])).insert(ignore_permissions=True)
        user = "activity-" + frappe.generate_hash(length=8) + "@example.invalid"
        frappe.get_doc(dict(doctype="User", email=user, first_name="Activity junior", enabled=1, user_type="System User", send_welcome_email=0, roles=[dict(role="Employee")])).insert(ignore_permissions=True)
        employee = frappe.get_doc(dict(doctype="Employee", first_name="Activity junior", employee_name="Activity junior", user_id=user, status="Active", company=frappe.db.get_value("Company", {}, "name"), date_of_joining=today()))
        employee.flags.ignore_mandatory = True
        employee.insert(ignore_permissions=True)
        customer = frappe.get_doc(dict(doctype="Customer", customer_name="Activity fixture " + frappe.generate_hash(length=8), customer_type="Company"))
        customer.flags.ignore_mandatory = True
        customer.insert(ignore_permissions=True)
        with patch("snrg_credit_control.customer_workspace.api.notify"), patch("snrg_credit_control.customer_workspace.controllers.notify"):
            records = []
            for i in range(51):
                doc = frappe.get_doc(dict(doctype=api.INTERACTION, customer=customer.name, spoken_by=user, channel="Call", call_outcome="Connected" if i == 0 else "No answer", summary="=Fixture " + str(i), interaction_on="2089-12-01 10:00:00")).insert(ignore_permissions=True)
                frappe.db.set_value(api.INTERACTION, doc.name, "creation", "2090-01-01 00:00:00" if i == 0 else "2090-01-01 23:59:59", update_modified=False)
                records.append(doc.name)
            outside = frappe.get_doc(dict(doctype=api.INTERACTION, customer=customer.name, spoken_by=user, channel="Note", summary="Outside range", interaction_on="2090-01-02 00:00:00")).insert(ignore_permissions=True)
            frappe.db.set_value(api.INTERACTION, outside.name, "creation", "2090-01-02 00:00:00", update_modified=False)
            task = api.create_action(dict(subject="File GST", assigned_to=user, due_date=today(), description="General task"))
            doc = frappe.get_doc(api.ACTION, task["name"])
            frappe.db.set_value(api.ACTION, doc.name, "creation", "2090-01-01 12:00:00", update_modified=False)
            frappe.set_user(user)
            api.update_action(doc.name, dict(status="Completed", update="Filed"), str(doc.modified))
            versions = frappe.get_all("Version", filters={"ref_doctype": api.ACTION, "docname": doc.name}, fields=["name", "data"])
            assert versions, "Completion must have native Version audit history"
            for version in versions:
                frappe.db.set_value("Version", version.name, "creation", "2090-01-01 14:00:00", update_modified=False)
            audit_update = frappe.get_doc(dict(doctype=api.INTERACTION, customer=customer.name, spoken_by=user, channel="Update", summary="Automatic task update", action_reference=doc.name, interaction_on="2090-01-01 14:00:00")).insert(ignore_permissions=True)
            frappe.db.set_value(api.INTERACTION, audit_update.name, "creation", "2090-01-01 14:00:00", update_modified=False)
            for denied in ("Guest", "Administrator", user):
                frappe.set_user(denied)
                assert not activity.allowed()
                if denied != "Guest":
                    assert not api.bootstrap()["can_team_activity"]
                for endpoint in (activity.report, activity.export):
                    try:
                        endpoint(from_date="2090-01-01", to_date="2090-01-01")
                    except frappe.PermissionError:
                        pass
                    else:
                        raise AssertionError("Private endpoint allowed " + denied)
            frappe.set_user(activity.VIEWER)
            assert api.bootstrap()["can_team_activity"]
            args=dict(from_date="2090-01-01", to_date="2090-01-01")
            result=activity.report(**args)
            assert result["count"] == 53, result["count"]
            assert len(result["rows"]) == 50 and result["has_more"]
            second=activity.report(**args, start=50)
            assert len(second["rows"]) == 3 and not second["has_more"]
            assert not ({r["key"] for r in result["rows"]} & {r["key"] for r in second["rows"]})
            counts={r["user"]:r for r in result["summary"]}
            assert counts["Administrator"]["interactions"]==51 and counts["Administrator"]["calls"]==51 and counts["Administrator"]["connected"]==1 and counts["Administrator"]["created"]==1
            assert counts[user]["completed"]==1 and counts[user]["interactions"]==0
            completion=activity.report(**args, activity_type="Task completed")["rows"][0]
            assert completion["actor"]==user and completion["logged_by"]=="Administrator" and completion["party_type"]=="General"
            assert activity.report(**args, party_type="General")["count"]==2
            assert activity.report(**args, search=customer.customer_name.lower())["count"]==51
            assert activity.report(**args, call_outcome="Connected")["count"]==1
            assert activity.report(**args, activity_type="Calls")["count"]==51
            assert activity.report(**args, activity_type="Connected calls")["count"]==1
            assert activity.report(**args, user=user)["count"]==1
            assert activity.report(**args, activity_type="Task completed", party_type="Supplier")["count"]==0
            for invalid in (dict(from_date="2090-01-02",to_date="2090-01-01"),dict(from_date="2090-01-01",to_date="2091-01-01"),dict(activity_type="Injected")):
                try:activity.report(**invalid)
                except frappe.ValidationError:pass
                else:raise AssertionError("Invalid filter accepted")
            activity.export(**args, call_outcome="Connected")
            import openpyxl
            workbook=openpyxl.load_workbook(BytesIO(frappe.response["filecontent"]))
            assert workbook.sheetnames==["Summary","Entries"]
            assert workbook["Entries"].max_row==2
            assert workbook["Entries"]["J2"].value.startswith("'="), "Excel formulas must be escaped"
        return dict(passed=["exact-login access (including Administrator denied)","recorder vs speaker vs completer attribution", "general tasks", "full filtered totals before pagination", "date boundaries and backdated interactions", "filter drilldowns", "filtered Excel export and formula escaping"], fixtures="rolled back")
    finally:
        frappe.db.rollback()
        frappe.set_user(original)
