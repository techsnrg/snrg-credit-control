import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


CATEGORY_TARGET_SCHEME = "Period Cumulative Category Target Slab"


class SNRGScheme(Document):
    def validate(self):
        self._normalize_legacy_values()
        self._validate_scheme_type()
        self._validate_gst_treatment()
        self._validate_dates()
        self._validate_item_filters()
        self._validate_slabs()

    def _normalize_legacy_values(self):
        if self.scheme_type == "Single Invoice Amount Slab":
            self.scheme_type = "Invoice Amount Slab"
        if self.calculation_basis == "Eligible Item Value Before GST":
            self.calculation_basis = "Excluded"

    def _validate_scheme_type(self):
        if self.scheme_type not in ("Invoice Amount Slab", "Period Cumulative Amount Slab", CATEGORY_TARGET_SCHEME):
            frappe.throw(_("Invalid Scheme Type."))

    def _validate_gst_treatment(self):
        if self.calculation_basis not in ("Excluded", "Included"):
            frappe.throw(_("Invalid GST Treatment."))

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
        if self.scheme_type == CATEGORY_TARGET_SCHEME:
            self._validate_category_slabs()
            return

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

    def _validate_category_slabs(self):
        if not self.category_rules:
            frappe.throw(_("At least one category rule is required."))
        if not self.category_slabs:
            frappe.throw(_("At least one category target slab is required."))

        seen_rules = set()
        for row in self.category_rules:
            if row.apply_on == "Item Code":
                if not row.item_code:
                    frappe.throw(_("Item Code is required in category rule row {0}.").format(row.idx))
                key = (row.category, row.apply_on, row.item_code, row.uom, row.exclude)
            elif row.apply_on == "Item Group":
                if not row.item_group:
                    frappe.throw(_("Item Group is required in category rule row {0}.").format(row.idx))
                key = (row.category, row.apply_on, row.item_group, row.uom, row.exclude)
            else:
                frappe.throw(_("Invalid Apply On in category rule row {0}.").format(row.idx))

            if key in seen_rules:
                frappe.throw(_("Duplicate category rule in row {0}.").format(row.idx))
            seen_rules.add(key)

        slabs = {}
        seen_targets = set()
        for row in self.category_slabs:
            if not row.slab_id:
                frappe.throw(_("Slab ID is required in category slab row {0}.").format(row.idx))
            if not row.category:
                frappe.throw(_("Category is required in category slab row {0}.").format(row.idx))
            if flt(row.category_target) <= 0:
                frappe.throw(_("Category Target must be greater than zero in category slab row {0}.").format(row.idx))
            if flt(row.total_target) <= 0:
                frappe.throw(_("Total Target must be greater than zero in category slab row {0}.").format(row.idx))
            if flt(row.minimum_categories_required) <= 0:
                frappe.throw(_("Minimum Categories Required must be greater than zero in row {0}.").format(row.idx))
            if not row.reward:
                frappe.throw(_("Reward is required in category slab row {0}.").format(row.idx))

            key = (row.slab_id, row.category)
            if key in seen_targets:
                frappe.throw(_("Duplicate category target for Slab ID {0} and Category {1}.").format(row.slab_id, row.category))
            seen_targets.add(key)

            slab = slabs.setdefault(
                row.slab_id,
                {
                    "total_target": flt(row.total_target),
                    "minimum_categories_required": flt(row.minimum_categories_required),
                    "reward": row.reward,
                    "idx": row.idx,
                },
            )
            if slab["total_target"] != flt(row.total_target):
                frappe.throw(_("Rows with Slab ID {0} must have the same Total Target.").format(row.slab_id))
            if slab["minimum_categories_required"] != flt(row.minimum_categories_required):
                frappe.throw(_("Rows with Slab ID {0} must have the same Minimum Categories Required.").format(row.slab_id))
            if slab["reward"] != row.reward:
                frappe.throw(_("Rows with Slab ID {0} must have the same Reward.").format(row.slab_id))

        previous_total = 0
        for slab in sorted(slabs.values(), key=lambda value: value["total_target"]):
            if slab["total_target"] <= previous_total:
                frappe.throw(_("Total Targets must be in increasing order. Check row {0}.").format(slab["idx"]))
            previous_total = slab["total_target"]


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
