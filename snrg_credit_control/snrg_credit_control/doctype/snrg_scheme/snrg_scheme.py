import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class SNRGScheme(Document):
    def validate(self):
        self._validate_dates()
        self._validate_item_filters()
        self._validate_slabs()

    def _validate_dates(self):
        if self.valid_from and self.valid_upto and getdate(self.valid_upto) < getdate(self.valid_from):
            frappe.throw(_("Valid Upto cannot be before Valid From."))

    def _validate_item_filters(self):
        _throw_duplicate_rows(self.eligible_items, "item_code", _("Eligible Item Codes"))
        _throw_duplicate_rows(self.eligible_item_groups, "item_group", _("Eligible Item Groups"))
        _throw_duplicate_rows(self.excluded_items, "item_code", _("Excluded Item Codes"))

        included_items = {row.item_code for row in self.eligible_items if row.item_code}
        excluded_items = {row.item_code for row in self.excluded_items if row.item_code}
        overlap = sorted(included_items.intersection(excluded_items))
        if overlap:
            frappe.throw(
                _("Item {0} cannot be both included and excluded.").format(
                    frappe.bold(", ".join(overlap))
                )
            )

    def _validate_slabs(self):
        if not self.slabs:
            frappe.throw(_("At least one scheme slab is required."))

        previous_amount = 0
        for row in self.slabs:
            if flt(row.slab_amount) <= 0:
                frappe.throw(_("Slab amount must be greater than zero in row {0}.").format(row.idx))
            if flt(row.slab_amount) <= previous_amount:
                frappe.throw(_("Slab amounts must be in increasing order. Check row {0}.").format(row.idx))
            if not row.reward:
                frappe.throw(_("Reward is required in slab row {0}.").format(row.idx))
            previous_amount = flt(row.slab_amount)


def _throw_duplicate_rows(rows, fieldname, label):
    seen = set()
    duplicates = set()

    for row in rows:
        value = row.get(fieldname)
        if not value:
            continue
        if value in seen:
            duplicates.add(value)
        seen.add(value)

    if duplicates:
        frappe.throw(
            _("Duplicate values in {0}: {1}").format(
                frappe.bold(label),
                frappe.bold(", ".join(sorted(duplicates))),
            )
        )
