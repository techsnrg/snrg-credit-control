"""Pure regression for filtering before pagination (no Frappe server required)."""
import importlib.util
import json
from pathlib import Path
import sys
import types
frappe = types.ModuleType("frappe")
frappe.parse_json = json.loads

def fail(message):
    raise ValueError(message)
frappe.throw = fail
sys.modules['frappe'] = frappe
spec = importlib.util.spec_from_file_location('sorting', Path(__file__).resolve().parents[1] / 'snrg_credit_control/customer_workspace/sorting.py')
sorting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sorting)
rows = [dict(name=str(n), customer_name=f'Customer {n}', outstanding=n, due_now=n, age_over_120=n) for n in range(70)]
filtered = sorting.filter_financial_rows(rows, json.dumps({'outstanding': {'min': 55, 'max': 65}, 'age_over_120': {'min': 60}}))
assert [row['outstanding'] for row in filtered] == list(range(60, 66))
sorting.financial_rows(filtered, 'age_over_120_desc', 'customer_name')
assert filtered[0]['outstanding'] == 65
assert len(sorting.filter_financial_rows(rows, {'outstanding': {'min': 0, 'max': 0}})) == 1
for invalid in [{'outstanding': {'min': 20, 'max': 10}}, {'wrong': {}}, {'outstanding': {'min': 'NaN'}}, {'outstanding': {'min': 'abc'}}]:
    try:
        sorting.filter_financial_rows(rows, invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(invalid)
print('PASS full-report ranges, intersected filters, zero bounds, bucket sorting, invalid inputs')
