"""Stable financial ordering, applied before pagination."""
import frappe


def financial_rows(rows, sort, label):
    choices = {"due_desc": ("due_now", True), "due_asc": ("due_now", False),
               "outstanding_desc": ("outstanding", True), "outstanding_asc": ("outstanding", False),
               "name_asc": (label, False), "name_desc": (label, True)}
    for field in ("age_0_30", "age_31_60", "age_61_90", "age_91_120", "age_over_120"):
        choices[field + "_asc"] = (field, False)
        choices[field + "_desc"] = (field, True)
    if sort not in choices:
        frappe.throw("Choose a valid sort order.")
    field, reverse = choices[sort]
    rows.sort(key=lambda row: (str(row[label]).casefold(), row["name"]))
    rows.sort(key=lambda row: str(row[field]).casefold() if field == label else row[field], reverse=reverse)


def filter_financial_rows(rows, column_filters=None):
    """Validate ranges and filter the complete permission-checked report before pagination."""
    import math
    filters = frappe.parse_json(column_filters) if isinstance(column_filters, str) else column_filters
    if not filters:
        return rows
    allowed = {"outstanding", "due_now", "age_0_30", "age_31_60", "age_61_90", "age_91_120", "age_over_120"}
    if not isinstance(filters, dict) or set(filters) - allowed:
        frappe.throw("Choose valid amount filters.")
    for field, bounds in filters.items():
        if not isinstance(bounds, dict) or set(bounds) - {"min", "max"}:
            frappe.throw("Choose a valid amount range.")
        parsed = {}
        for key, value in bounds.items():
            if value is None or value == "":
                continue
            try:
                parsed[key] = float(value)
            except (ValueError, TypeError):
                frappe.throw("Enter a valid amount.")
            if not math.isfinite(parsed[key]):
                frappe.throw("Enter a finite amount.")
        if "min" in parsed and "max" in parsed and parsed["min"] > parsed["max"]:
            frappe.throw("Minimum amount cannot exceed maximum amount.")
        rows = [row for row in rows if ("min" not in parsed or row[field] >= parsed["min"]) and ("max" not in parsed or row[field] <= parsed["max"])]
    return rows
