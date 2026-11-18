"""Stable financial ordering, applied before pagination."""
import frappe


def financial_rows(rows, sort, label):
    choices = {"due_desc": ("due_now", True), "due_asc": ("due_now", False),
               "outstanding_desc": ("outstanding", True), "outstanding_asc": ("outstanding", False),
               "name_asc": (label, False), "name_desc": (label, True)}
    if sort not in choices:
        frappe.throw("Choose a valid sort order.")
    field, reverse = choices[sort]
    rows.sort(key=lambda row: (str(row[label]).casefold(), row["name"]))
    rows.sort(key=lambda row: str(row[field]).casefold() if field == label else row[field], reverse=reverse)
