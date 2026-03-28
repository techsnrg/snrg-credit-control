import frappe
from frappe.model.document import Document

from snrg_credit_control.cheque_bounce import (
    AUTO_STATUSES,
    build_cheque_bounce_case_values,
    get_initial_cheque_bounce_status,
)


class ChequeBounceCase(Document):
    def validate(self):
        self._validate_unique_journal_entry()
        self._sync_from_journal_entry()
        self._set_status()

    def on_update(self):
        self._sync_journal_entry()

    def _sync_from_journal_entry(self):
        if not self.journal_entry:
            return

        values = build_cheque_bounce_case_values(
            frappe.get_doc("Journal Entry", self.journal_entry)
        )
        for fieldname, value in values.items():
            self.set(fieldname, value)

    def _validate_unique_journal_entry(self):
        if not self.journal_entry:
            return

        existing = frappe.db.get_value(
            "Cheque Bounce Case",
            {"journal_entry": self.journal_entry, "name": ("!=", self.name)},
            "name",
        )
        if existing:
            frappe.throw(
                f"Journal Entry {self.journal_entry} is already linked to Cheque Bounce Case {existing}."
            )

    def _set_status(self):
        if self.status and self.status not in AUTO_STATUSES:
            return

        self.status = get_initial_cheque_bounce_status(self)

    def _sync_journal_entry(self):
        if not self.journal_entry:
            return

        frappe.db.set_value(
            "Journal Entry",
            self.journal_entry,
            {
                "custom_is_cheque_bounce": 1,
                "custom_cheque_bounce_case": self.name,
                "custom_cheque_bounce_status": self.status,
            },
            update_modified=False,
        )
