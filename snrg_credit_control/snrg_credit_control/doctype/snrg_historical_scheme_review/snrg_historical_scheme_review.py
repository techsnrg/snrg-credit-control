import hashlib

from frappe.model.document import Document


class SNRGHistoricalSchemeReview(Document):
    def autoname(self):
        self.name = hashlib.sha256(f"{self.scheme}\0{self.invoice}".encode()).hexdigest()
