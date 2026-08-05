import frappe
from frappe.model.document import Document


class OvertimeSetting(Document):
    def validate(self):
        if self.days_divisor is not None and self.days_divisor <= 0:
            frappe.throw("Days Divisor must be greater than zero.")
