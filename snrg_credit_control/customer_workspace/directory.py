"""Minimal customer directory, including mobile fallbacks and server-side filters."""
import frappe
from frappe.utils import cint
from frappe.utils.nestedset import get_descendants_of
from snrg_credit_control.customer_workspace.api import guard


def filter_options():
    return {
        "supplier_groups": frappe.get_all("Supplier Group", pluck="name", order_by="name", limit_page_length=0),
        "countries": frappe.get_all("Country", pluck="name", order_by="name", limit_page_length=0),
        "territories": frappe.get_all("Territory", pluck="name", order_by="name", limit_page_length=0),
        "customer_groups": frappe.get_all("Customer Group", pluck="name", order_by="name", limit_page_length=0),
    }


def _query(search="", territory=None, customer_group=None, status="active", names=None):
    customer = frappe.qb.DocType("Customer")
    contact = frappe.qb.DocType("Contact")
    fields = [customer.name, customer.customer_name, customer.territory, customer.customer_group,
              customer.disabled, customer.mobile_no, customer.customer_primary_contact,
              contact.mobile_no.as_("contact_mobile"), contact.phone.as_("contact_phone")]
    meta = frappe.get_meta("Customer")
    for field in ("custom_mobile_number", "custom_city", "custom_state"):
        if meta.has_field(field):
            fields.append(customer[field])
    query = frappe.qb.from_(customer).left_join(contact).on(customer.customer_primary_contact == contact.name).select(*fields)
    if names is not None:
        query = query.where(customer.name.isin(names))
    if territory:
        query = query.where(customer.territory.isin([territory, *get_descendants_of("Territory", territory)]))
    if customer_group:
        query = query.where(customer.customer_group.isin([customer_group, *get_descendants_of("Customer Group", customer_group)]))
    if status in ("active", "disabled"):
        query = query.where(customer.disabled == (1 if status == "disabled" else 0))
    if search:
        pattern = "%" + str(search).strip()[:100] + "%"
        condition = customer.name.like(pattern) | customer.customer_name.like(pattern) | customer.mobile_no.like(pattern) | contact.mobile_no.like(pattern) | contact.phone.like(pattern)
        if meta.has_field("custom_mobile_number"):
            condition |= customer.custom_mobile_number.like(pattern)
        query = query.where(condition)
    return query.orderby(customer.customer_name)


def cards(rows):
    for row in rows:
        row.party_type = "Customer"
        row.party_name = row.customer_name
        row.location = row.territory
        row.group_name = row.customer_group
        row.mobile_number = row.mobile_no or row.get("custom_mobile_number") or row.contact_mobile or row.contact_phone or ""
        row.city = row.get("custom_city") or ""
        row.state = row.get("custom_state") or ""
        # Only the resolved customer contact number is exposed.
        for field in ("contact_mobile", "contact_phone", "custom_mobile_number"):
            row.pop(field, None)
    return rows


def customer_cards(names):
    if not names:
        return {}
    return {row.name: row for row in cards(_query(names=names, status="all").run(as_dict=True))}


@frappe.whitelist()
def customer_directory(search="", territory=None, customer_group=None, status="active", start=0):
    guard()
    if status not in ("active", "disabled", "all"):
        frappe.throw("Choose a valid customer status.")
    start = max(0, cint(start))
    rows = _query(search, territory, customer_group, status).offset(start).limit(51).run(as_dict=True)
    return {"rows": cards(rows[:50]), "has_more": len(rows) > 50, "start": start}


def _supplier_query(search="", country=None, supplier_group=None, status="active", names=None):
    supplier, contact = frappe.qb.DocType("Supplier"), frappe.qb.DocType("Contact")
    fields = [supplier.name, supplier.supplier_name, supplier.country, supplier.supplier_group,
              supplier.disabled, supplier.mobile_no, contact.mobile_no.as_("contact_mobile"),
              contact.phone.as_("contact_phone")]
    meta = frappe.get_meta("Supplier")
    if meta.has_field("custom_mobile_number"):
        fields.append(supplier.custom_mobile_number)
    query = frappe.qb.from_(supplier).left_join(contact).on(supplier.supplier_primary_contact == contact.name).select(*fields)
    if names is not None:
        query = query.where(supplier.name.isin(names))
    if country:
        query = query.where(supplier.country == country)
    if supplier_group:
        query = query.where(supplier.supplier_group.isin([supplier_group, *get_descendants_of("Supplier Group", supplier_group)]))
    if status in ("active", "disabled"):
        query = query.where(supplier.disabled == (1 if status == "disabled" else 0))
    if search:
        pattern = "%" + str(search).strip()[:100] + "%"
        condition = supplier.name.like(pattern) | supplier.supplier_name.like(pattern) | supplier.mobile_no.like(pattern) | contact.mobile_no.like(pattern) | contact.phone.like(pattern)
        if meta.has_field("custom_mobile_number"):
            condition |= supplier.custom_mobile_number.like(pattern)
        query = query.where(condition)
    return query.orderby(supplier.supplier_name)


def supplier_card_rows(rows):
    for row in rows:
        row.party_type, row.party_name = "Supplier", row.supplier_name
        row.location, row.group_name = row.country, row.supplier_group
        row.mobile_number = row.mobile_no or row.get("custom_mobile_number") or row.contact_mobile or row.contact_phone or ""
        for key in ("contact_mobile", "contact_phone", "custom_mobile_number"):
            row.pop(key, None)
    return rows


def supplier_cards(names):
    return {row.name: row for row in supplier_card_rows(_supplier_query(names=names, status="all").run(as_dict=True))} if names else {}


@frappe.whitelist()
def supplier_directory(search="", country=None, supplier_group=None, status="active", start=0):
    guard()
    if status not in ("active", "disabled", "all"):
        frappe.throw("Choose a valid supplier status.")
    start = max(0, cint(start))
    rows = _supplier_query(search, country, supplier_group, status).offset(start).limit(51).run(as_dict=True)
    return {"rows": supplier_card_rows(rows[:50]), "has_more": len(rows) > 50, "start": start}
