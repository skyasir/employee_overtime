import frappe
from frappe.model.document import Document


class OvertimeSetting(Document):
    def validate(self):
        if self.days_divisor is not None and self.days_divisor <= 0:
            frappe.throw("Days Divisor must be greater than zero.")
        self.validate_category_rules()

    def validate_category_rules(self):
        """Keep the category matrix unambiguous.

        A category + shift length pair must resolve to exactly one row, because
        the first match decides both the standard hours and the break, and a
        second row for the same pair would silently never apply.
        """
        seen = set()
        for row in self.category_rules:
            if not row.shift_hours or row.shift_hours <= 0:
                frappe.throw(f"Row #{row.idx}: Shift Hours must be greater than zero.")

            key = (row.ot_category, round(row.shift_hours, 2))
            if key in seen:
                frappe.throw(
                    f"Row #{row.idx}: a rule for {row.ot_category} on a "
                    f"{row.shift_hours} hour shift already exists."
                )
            seen.add(key)

            if not row.deduct_break:
                row.break_hours = 0
            elif row.break_hours and row.break_hours >= row.shift_hours:
                frappe.throw(f"Row #{row.idx}: Break Hours must be less than Shift Hours.")
