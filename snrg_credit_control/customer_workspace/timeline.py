"""One chronological activity stream; transaction reads retain native permissions."""
import frappe
from frappe.utils import cint, flt, getdate, now_datetime
from snrg_credit_control.customer_workspace.api import guard, party_values, present_action, ACTION, INTERACTION


def _stamp(row, field):
    date = str(row.get(field) or row.get("creation") or "")[:10]
    time = str(row.get("posting_time") or "")[:8]
    if not time and str(row.get("creation") or "")[:10] == date:
        time = str(row.get("creation"))[11:19]
    if time:
        time = ":".join(part.zfill(2) for part in time.split(":"))
    return date + " " + (time or "00:00:00")


def _transactions(kind, party, limit):
    events, readable = [], []
    sources = [("Quotation", "party_name", "transaction_date"), ("Sales Order", "customer", "transaction_date"), ("Delivery Note", "customer", "posting_date"), ("Sales Invoice", "customer", "posting_date")] if kind == "Customer" else [("Supplier Quotation", "supplier", "transaction_date"), ("Purchase Order", "supplier", "transaction_date"), ("Purchase Receipt", "supplier", "posting_date"), ("Purchase Invoice", "supplier", "posting_date")]
    sources.append(("Payment Entry", "party", "posting_date"))
    for doctype, link, date in sources:
        if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
            continue
        meta = frappe.get_meta(doctype)
        candidates = ["name", "owner", "creation", "docstatus", date, "posting_time", "status", "grand_total", "currency", "is_return", "return_against"]
        if doctype == "Payment Entry":
            candidates += ["payment_type", "paid_amount", "received_amount", "paid_from_account_currency", "paid_to_account_currency"]
        fields = list(dict.fromkeys(f for f in candidates if f in ("name", "owner", "creation", "docstatus") or meta.has_field(f)))
        filters = {link: party}
        if doctype == "Quotation":
            filters["quotation_to"] = kind
        if doctype == "Payment Entry":
            filters["party_type"] = kind
        try:
            # get_list enforces role, field-level, company and user permissions.
            rows = frappe.get_list(doctype, filters=filters, fields=fields, order_by=f"{date} desc, creation desc, name desc", limit_page_length=limit)
        except frappe.PermissionError:
            continue
        readable.append(doctype)
        for row in rows:
            title = doctype
            amount, currency = row.get("grand_total"), row.get("currency")
            allocations = []
            if doctype == "Payment Entry":
                received = row.payment_type == "Receive"
                title = "Payment received" if received else "Payment sent"
                amount = row.received_amount if received else row.paid_amount
                currency = row.paid_to_account_currency if received else row.paid_from_account_currency
                # Child data is read only through its permission-checked parent.
                payment = frappe.get_doc(doctype, row.name)
                payment.check_permission("read")
                for ref in payment.get("references") or []:
                    if ref.reference_doctype not in ("Sales Invoice", "Purchase Invoice", "Sales Order", "Purchase Order") or not ref.reference_name:
                        continue
                    if frappe.has_permission(ref.reference_doctype, "read", doc=ref.reference_name):
                        allocations.append({"doctype": ref.reference_doctype, "name": ref.reference_name, "amount": flt(ref.allocated_amount)})
            elif row.get("is_return"):
                title = {"Sales Invoice": "Credit note", "Purchase Invoice": "Debit note", "Delivery Note": "Sales return", "Purchase Receipt": "Purchase return"}.get(doctype, doctype)
            state = "Draft" if row.docstatus == 0 else "Cancelled" if row.docstatus == 2 else row.get("status") or "Submitted"
            events.append({"kind": "transaction", "name": doctype + ":" + row.name, "document_type": doctype, "document_name": row.name, "summary": title, "spoken_by": row.owner, "interaction_on": _stamp(row, date), "sort": _stamp(row, date), "status": state, "docstatus": row.docstatus, "amount": amount, "currency": currency, "allocations": allocations})
    return events, readable


@frappe.whitelist()
def timeline(customer=None, supplier=None, start=0, include_transactions=True):
    guard()
    party_values(customer, supplier)
    kind, party = ("Supplier", supplier) if supplier else ("Customer", customer)
    filters = {"supplier" if supplier else "customer": party}
    start = max(0, cint(start))
    limit = start + 51
    events = []
    interactions = frappe.get_all(INTERACTION, filters=filters, fields=["name", "summary", "summary_html", "channel", "contact_name", "spoken_by", "interaction_on", "action_reference"], order_by="interaction_on desc, name desc", limit_page_length=limit)
    for row in interactions:
        from snrg_credit_control.customer_workspace.rich_text import attachment_rows
        row.attachments = attachment_rows(row.name)
        row.kind, row.sort = "interaction", str(row.interaction_on)
        row.mentions = frappe.get_all("Customer Interaction Mention", filters={"parent": row.name, "parenttype": INTERACTION}, fields=["employee", "employee_name", "user"], limit_page_length=0)
        events.append(row)
    if customer and frappe.db.exists("DocType", "Calls"):
        calls = frappe.get_all("Calls", filters={"call_to": "Customer", "lead__party": customer}, fields=["name", "short_notes", "long_notes", "date", "call_time", "employee_id", "follow_up_date"], order_by="date desc, call_time desc", limit_page_length=limit)
        for call in calls:
            events.append({"kind": "interaction", "legacy": True, "name": call.name, "summary": "\n".join(filter(None, [call.short_notes, call.long_notes])), "channel": "Legacy call", "spoken_by": call.employee_id, "interaction_on": f"{call.date} {call.call_time or '00:00:00'}", "sort": f"{call.date} {call.call_time or '00:00:00'}", "follow_up_date": call.follow_up_date})
    # Pending actions are plans, never portrayed as completed conversations.
    plans = frappe.get_all(ACTION, filters={**filters, "status": ["in", ["Open", "In Progress"]]}, fields=["name", "customer", "customer_name", "supplier", "supplier_name", "subject", "assigned_to", "due_date", "due_time", "status", "action_type", "priority", "description", "interaction", "modified", "owner", "event"], order_by="due_date desc, due_time desc, name desc", limit_page_length=limit)
    for row in plans:
        present_action(row)
        row.due_time = str(row.due_time) if row.due_time else ""
        stamp = str(row.due_date) + " " + (":".join(part.zfill(2) for part in row.due_time.split(":")) if row.due_time else "00:00:00")
        events.append({"kind": "plan", "name": "plan:" + row.name, "summary": row.subject, "spoken_by": row.owner, "interaction_on": stamp, "sort": stamp, "action": row, "overdue": getdate(row.due_date) < getdate(now_datetime())})
    readable = []
    from snrg_credit_control.customer_workspace.settings import allowed
    if cint(include_transactions) and allowed("Transactions"):
        transactions, readable = _transactions(kind, party, limit)
        events.extend(transactions)
    events.sort(key=lambda e: (str(e["sort"]), e["name"]), reverse=True)
    return {"events": events[start:start + 50], "has_more": len(events) > start + 50, "transaction_sources": readable}
