import frappe


@frappe.whitelist()
def ping():
    return "ok"


@frappe.whitelist()
def get_register(company=None, as_on_date=None):
    from frappe.utils import getdate

    date = getdate(as_on_date)
    filters = {"company": ["in", [company, ""]]} if company else {}
    schemes = frappe.get_list(
        "SNRG Scheme", filters=filters, limit_page_length=0,
        fields=["name", "company", "scheme_type", "scheme_series", "supersedes",
                "valid_from", "valid_upto", "disabled", "track_invoice_items", "require_payment_clearance"],
        order_by="valid_from desc, name asc",
    )
    for scheme in schemes:
        scheme.status = (
            "Disabled" if scheme.disabled else
            "Upcoming" if getdate(scheme.valid_from) > date else
            "Closed" if getdate(scheme.valid_upto) < date else "Active"
        )
    companies = frappe.get_list("Company", pluck="name", limit_page_length=0, order_by="name")
    currencies = dict(frappe.get_all("Company", filters={"name": ["in", companies]},
                                     fields=["name", "default_currency"], as_list=True)) if companies else {}
    from snrg_credit_control.scheme_historical_review import access

    return {"schemes": schemes, "companies": companies, "currencies": currencies, "historical_review": access()}


@frappe.whitelist()
def get_scheme(name, company=None, as_on_date=None, quotations=0, customer=None, invoice=None, include_lines=0):
    return _get_scheme(name, company, as_on_date, quotations, customer, invoice, include_lines)


def _get_scheme(name, company=None, as_on_date=None, quotations=0, customer=None, invoice=None,
                include_lines=0, reminder_preview=False):
    from frappe.utils import cint, flt, getdate
    from snrg_credit_control import scheme_engine as engine, scheme_payments

    doc = frappe.get_doc("SNRG Scheme", name)
    doc.check_permission("read")
    company = company or doc.company
    if company:
        frappe.get_doc("Company", company).check_permission("read")
    if doc.company and doc.company != company:
        frappe.throw(frappe._("This scheme belongs to another company."))
    config = engine._get_scheme_config(name)
    date = getdate(as_on_date)
    start, end = getdate(config.valid_from), getdate(config.valid_upto)
    report_date = date if config.track_invoice_items else min(date, end)
    per_invoice = config.scheme_type == engine.INVOICE_AMOUNT_SLAB
    customers = []
    rules = scheme_payments.payment_rules(doc)

    if date >= start and (not doc.disabled or config.track_invoice_items):
        if per_invoice:
            rows = engine._planning_invoice_rows(config, company, start, min(date, end), date, customer=customer)
            items = engine._get_item_map([row.item_code for row in rows])
            bounds = engine._get_item_group_bounds([config], items)
            groups = {}
            for row in rows:
                if not engine._is_eligible_scheme_row(row, items.get(row.item_code) or {}, config, bounds):
                    continue
                group = groups.setdefault(row.sales_invoice, dict(
                    customer=row.customer, customer_name=row.customer_name, invoice=row.sales_invoice,
                    eligible_rows=[], eligible_amount=0, is_return=bool(row.is_return),
                ))
                amount = engine._get_scheme_amount(row, config.gst_treatment)
                group["eligible_amount"] += amount
                group["eligible_rows"].append(engine._build_scheme_detail_row(row, items.get(row.item_code) or {}, amount))
            for group in groups.values():
                reached, highest, next_slab = engine._get_slab_progress(config.slabs, group["eligible_amount"])
                if group["is_return"]:
                    next_slab = None
                group.update(achieved_rewards=engine._get_scheme_rewards(reached, config.reward_policy),
                             next_slab=next_slab, shortfall_amount=(
                                 flt(next_slab["amount"]) - group["eligible_amount"] if next_slab else 0))
            customers = list(groups.values())
        else:
            payload = engine.get_scheme_customer_progress(
                company=company, scheme=name, as_on_date=report_date, historical_review_as_on=date,
                include_draft_quotations=cint(quotations) == 2,
                include_submitted_quotations=bool(cint(quotations)),
                customer=customer,
            )
            if payload["schemes"]:
                customers = payload["schemes"][0]["customers"]
                for row in customers:
                    row["achieved_rewards"] = engine._get_scheme_rewards(row["achieved_slabs"], config.reward_policy)
                    row["projected_rewards"] = engine._get_scheme_rewards(row["projected_slabs"], config.reward_policy)

    if rules and customers:
        scheme_payments.attach_qualification(config, customers, rules, date)
    if per_invoice and invoice:
        customers = [row for row in customers if row["invoice"] == invoice]
    fields = {"customer", "customer_name", "invoice", "eligible_amount", "achieved_rewards", "next_slab",
              "shortfall_amount", "category_shortfalls", "projected_amount", "projected_rewards", "quotation_amount"}
    if rules:
        fields.update(("eligible_cleared", "claimable_rewards", "clearance_gap", "clearance_next_slab",
                       "clearance_category_shortfalls"))
    if customer and cint(include_lines):
        fields.update(("eligible_rows", "quotation_rows", "payment_invoices"))
    if reminder_preview:
        fields.add("payment_invoices")
    customers = [{key: row[key] for key in fields if key in row} for row in customers]
    return dict(
        customers=customers, per_invoice=per_invoice, report_date=report_date,
        currency=frappe.get_cached_value("Company", company, "default_currency") if company else None,
        gst=config.gst_treatment, reward_policy=config.reward_policy, slabs=config.category_slabs or config.slabs,
        items=config.eligible_items, groups=config.eligible_item_groups,
        exclusions=sorted(config.excluded_items), category_rules=config.category_rules, payment_rules=rules,
    )


@frappe.whitelist()
def get_exclusions(name, company, customer, as_on_date=None, invoice=None):
    from frappe.utils import getdate
    from snrg_credit_control import scheme_engine as engine
    from snrg_credit_control import scheme_transactions as transactions

    scheme = frappe.get_doc("SNRG Scheme", name)
    scheme.check_permission("read")
    if not scheme.track_invoice_items or not frappe.has_permission("Sales Invoice", "read"):
        return []
    company = company or scheme.company
    if company:
        frappe.get_doc("Company", company).check_permission("read")
    if scheme.company and scheme.company != company:
        frappe.throw(frappe._("This scheme belongs to another company."))
    as_on = getdate(as_on_date)
    start, end = getdate(scheme.valid_from), getdate(scheme.valid_upto)
    filters = {"customer": customer, "docstatus": 1, "is_return": 0}
    if company:
        filters["company"] = company
    period_filters = {**filters, "posting_date": ["between", [start, min(as_on, end)]]}
    if invoice:
        period_filters["name"] = invoice
    invoice_names = frappe.get_list("Sales Invoice", filters=period_filters, pluck="name", limit_page_length=0)
    if as_on > end:
        late = {row.parent for row in transactions.posted_contributions(company, as_on, customer, name)
                if row.posting_date > end and row.exception_reason and (not invoice or row.parent == invoice)}
        if late:
            invoice_names.extend(frappe.get_list(
                "Sales Invoice", filters={**filters, "name": ["in", sorted(late)]},
                pluck="name", limit_page_length=0,
            ))
    if not invoice_names:
        return []
    rows = frappe.get_all("Sales Invoice Item", filters={"parent": ["in", invoice_names]},
                          fields=["name", "parent", "idx", "item_code", "uom", transactions.STATE_FIELD],
                          order_by="parent desc, idx")
    config = engine._get_scheme_config(name)
    items = engine._get_item_map([row.item_code for row in rows])
    bounds = engine._get_item_group_bounds([config], items)
    from snrg_credit_control.scheme_corrections import latest

    corrections = latest(invoice_names, name)
    result = []
    for row in rows:
        correction = corrections.get((row.parent, row.name))
        if correction:
            if correction.action == "Exclude":
                result.append({"parent": row.parent, "idx": row.idx, "item_code": row.item_code,
                               "reasons": [correction.reason]})
            continue
        rules = transactions._state(row).get("exclusions", [])
        reasons = [rule["reason"] for rule in rules if transactions._excluded(config, [rule])]
        if reasons and transactions._category(row, items.get(row.item_code) or {}, config, bounds) is not None:
            result.append({"parent": row.parent, "idx": row.idx, "item_code": row.item_code, "reasons": reasons})
    return result


@frappe.whitelist()
def get_customer_detail(name, customer, company=None, as_on_date=None, quotations=0, invoice=None):
    if not customer:
        frappe.throw(frappe._("Select a customer first."))
    frappe.get_doc("Customer", customer).check_permission("read")
    report = get_scheme(name, company, as_on_date, quotations, customer=customer, invoice=invoice, include_lines=1)
    entry = next(iter(report["customers"]), None)
    if not entry:
        frappe.throw(frappe._("No transactions for this customer in the selected scheme."))
    return {
        "customer": entry, "currency": report["currency"], "report_date": report["report_date"],
        "exclusions": get_exclusions(name, company, customer, as_on_date, invoice),
        "payment_rules": report["payment_rules"],
    }


@frappe.whitelist()
def export_customer(name, customer, company=None, as_on_date=None, quotations=0, invoice=None, export_format="xlsx"):
    from html import escape
    from frappe import _
    from frappe.utils import cint, flt, formatdate

    if export_format not in ("pdf", "xlsx"):
        frappe.throw(_("Choose PDF or Excel."))
    detail = get_customer_detail(name, customer, company, as_on_date, quotations, invoice)
    entry = detail["customer"]
    currency = detail["currency"] or ""
    customer_name = entry.get("customer_name") or customer
    summary = [
        [_("Customer"), customer_name],
        [_("Scheme"), name],
        [_("As of"), formatdate(detail["report_date"])],
        [_("Currency"), currency],
        [_("Eligible invoiced"), flt(entry["eligible_amount"])],
        [_("Invoiced reward") if detail["payment_rules"] else _("Reward reached"),
         ", ".join(entry.get("achieved_rewards") or []) or _("None yet")],
        [_("Next target gap"), flt(entry.get("shortfall_amount")) if entry.get("next_slab") else "—"],
    ]
    if detail["payment_rules"]:
        summary.extend([
            [_("Eligible cleared"), flt(entry.get("eligible_cleared"))],
            [_("Claimable reward"), ", ".join(entry.get("claimable_rewards") or []) or _("None yet")],
            [_("Cleared value gap"), flt(entry.get("clearance_gap")) if entry.get("clearance_next_slab") else "—"],
            [_("Hard clearance deadline"), formatdate(detail["payment_rules"]["hard_deadline"])],
        ])
    for category, gap in (entry.get("category_shortfalls") or {}).items():
        if flt(gap) > 0:
            summary.append([_("Category gap · {0}").format(category), flt(gap)])
    if cint(quotations) and "projected_amount" in entry:
        summary.extend([[_("Open quotations"), flt(entry.get("quotation_amount"))],
                        [_("Projected total"), flt(entry.get("projected_amount"))]])
    headers = [_("Source"), _("Document"), _("Line"), _("Item"), _("Category"), _("Quantity"),
               _("Eligible value"), _("Exception or exclusion")]
    rows = []
    for line in [*entry.get("eligible_rows", []), *entry.get("quotation_rows", [])]:
        rows.append([
            _("Quotation") if line.get("quotation") else _("Invoice"),
            line.get("quotation") or line.get("sales_invoice"), line.get("invoice_line") or "",
            line.get("item_code"), line.get("category"), flt(line.get("qty")), flt(line.get("amount")),
            " · ".join(filter(None, [line.get("exception_reason"), line.get("exception_by")])),
        ])
    rows.extend([_("Excluded"), row["parent"], row["idx"], row["item_code"], "", "", 0,
                 " · ".join(row["reasons"])] for row in detail["exclusions"])
    filename = "scheme-customer-progress"
    if export_format == "xlsx":
        from frappe.utils.xlsxutils import make_xlsx

        def safe_cell(value):
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                return "'" + value
            return value

        data = [[_("Scheme progress")], *summary, [], headers, *rows]
        content = make_xlsx([[safe_cell(value) for value in row] for row in data], "Scheme progress").getvalue()
    else:
        from frappe.utils.pdf import get_pdf

        def cells(row, tag):
            return "".join(f"<{tag}>{escape(str(value if value is not None else ''))}</{tag}>" for value in row)

        metadata = "".join(f"<tr>{cells(row, 'td')}</tr>" for row in summary)
        table = "".join(f"<tr>{cells(row, 'td')}</tr>" for row in rows)
        html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
        body {{ font: 10pt 'DejaVu Sans', sans-serif; color: #18242a; }}
        h1 {{ font-size: 20pt; margin: 0 0 12px; }}
        h2 {{ font-size: 13pt; margin: 18px 0 8px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        td, th {{ padding: 6px; text-align: left; vertical-align: top; word-wrap: break-word; }}
        th {{ color: #fff; background: #253743; }}
        .summary td:first-child {{ width: 25%; font-weight: bold; }}
        .lines td {{ border-bottom: 1px solid #ccd6dc; }}
        .lines {{ table-layout: fixed; }} thead {{ display: table-header-group; }}
        tr {{ page-break-inside: avoid; }}
        </style></head><body><h1>{escape(_("Scheme progress"))}</h1>
        <table class="summary">{metadata}</table>
        <h2>{escape(_("Transaction lines"))}</h2>
        <table class="lines"><thead><tr>{cells(headers, 'th')}</tr></thead><tbody>{table}</tbody></table>
        </body></html>"""
        content = get_pdf(html, options={"orientation": "Landscape", "page-size": "A4"})
    frappe.response.update(filename=f"{filename}.{export_format}", filecontent=content, type="download")


@frappe.whitelist()
def get_customer_overview(customer, company=None, as_on_date=None, quotations=1):
    customer_doc = frappe.get_doc("Customer", customer)
    customer_doc.check_permission("read")
    schemes = get_register(company, as_on_date)["schemes"]
    results = []
    for scheme in schemes:
        if scheme.status == "Upcoming" or (scheme.disabled and not scheme.track_invoice_items):
            continue
        report = get_scheme(scheme.name, company, as_on_date, quotations, customer=customer)
        for row in report["customers"]:
            results.append(dict(
                row, scheme=scheme.name, status=scheme.status, currency=report["currency"],
                valid_upto=scheme.valid_upto,
            ))
    status_order = {"Active": 0, "Closed": 1, "Disabled": 2}
    results.sort(key=lambda row: status_order[row["status"]])
    return dict(customer=customer, customer_name=customer_doc.customer_name, schemes=results)


@frappe.whitelist()
def preview_payment_reminders(name, company=None, as_on_date=None, customer=None):
    from frappe.utils import fmt_money, formatdate, getdate

    day = getdate(as_on_date)
    selected = frappe.get_doc("SNRG Scheme", name)
    selected.check_permission("read")
    company = company or selected.company
    if customer:
        frappe.get_doc("Customer", customer).check_permission("read")
    scheme_rows = get_register(company, day)["schemes"]
    due_customers = set()
    groups = {}
    for row in scheme_rows:
        if not row.require_payment_clearance or row.status in ("Disabled", "Upcoming"):
            continue
        report = _get_scheme(row.name, company, day, customer=customer, reminder_preview=True)
        for entry in report["customers"]:
            for invoice in entry.get("payment_invoices", []):
                if not invoice["reminder_due"]:
                    continue
                if not frappe.has_permission("Sales Invoice", "read", doc=invoice["invoice"]):
                    continue
                group = groups.setdefault(entry["customer"], {
                    "customer": entry["customer"], "customer_name": entry["customer_name"], "invoices": {},
                })
                item = group["invoices"].setdefault(invoice["invoice"], {
                    "invoice": invoice["invoice"], "outstanding": invoice["outstanding"], "currency": invoice["currency"],
                    "schemes": {},
                })
                item["schemes"][row.name] = invoice["hard_deadline"]
                if row.name == name:
                    due_customers.add(entry["customer"])
    previews = []
    for key in sorted(due_customers):
        group = groups[key]
        lines = [frappe._("Hello {0},").format(group["customer_name"] or key), "",
                 frappe._("Please clear the outstanding invoices below by the listed deadlines for their eligible value to count towards your scheme rewards."), ""]
        for item in group["invoices"].values():
            lines.append(f'{item["invoice"]} · {fmt_money(item["outstanding"], currency=item["currency"])}')
            lines.extend(f'  {scheme} · {formatdate(deadline)}' for scheme, deadline in sorted(item["schemes"].items()))
        previews.append(dict(customer=key, customer_name=group["customer_name"],
                             subject=frappe._("Payment reminder for scheme eligibility"),
                             body="\n".join(lines), invoice_count=len(group["invoices"])))
    return {"as_on_date": day, "previews": previews}
