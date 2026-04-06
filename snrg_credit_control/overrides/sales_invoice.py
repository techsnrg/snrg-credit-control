import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice


class CustomSalesInvoice(SalesInvoice):
    def check_credit_limit(self):
        if self._is_backed_by_approved_sales_orders():
            return
        return super().check_credit_limit()

    def _is_backed_by_approved_sales_orders(self):
        sales_orders = {
            row.sales_order
            for row in (self.items or [])
            if getattr(row, "sales_order", None)
        }

        if not sales_orders:
            return False

        rows = frappe.get_all(
            "Sales Order",
            filters={"name": ["in", list(sales_orders)]},
            fields=["name", "docstatus", "custom_credit_approval_status"],
        )

        if len(rows) != len(sales_orders):
            return False

        for row in rows:
            if row.docstatus != 1:
                return False
            if (row.custom_credit_approval_status or "").strip().lower() != "approved":
                return False

        return True
