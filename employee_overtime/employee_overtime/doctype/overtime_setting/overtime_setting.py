import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class OvertimeSetting(Document):
    def validate(self):
        if self.days_divisor is not None and self.days_divisor <= 0:
            frappe.throw("Days Divisor must be greater than zero.")
        self.validate_category_rules()
        self.validate_pull_dates()

    def validate_pull_dates(self):
        """Pull From/To must be sane before a backfill runs."""
        if not self.pull_records:
            return
        if not self.pull_from_date or not self.pull_to_date:
            return  # mandatory_depends_on already forces these in the form
        if getdate(self.pull_from_date) > getdate(self.pull_to_date):
            frappe.throw("Pull From Date cannot be after Pull To Date.")

    def on_update(self):
        """Backfill overtime for the chosen range when Pull Records is ticked.

        Runs after the save that turned the box on, then clears the box (via
        db_set, which does not re-trigger on_update) so the same range is not
        pulled again on the next save.
        """
        if not (self.pull_records and self.pull_from_date and self.pull_to_date):
            return

        from employee_overtime.overtime import pull_overtime_for_range

        created = pull_overtime_for_range(self.pull_from_date, self.pull_to_date)

        # Clear the trigger so a later save does not re-run the pull.
        self.db_set("pull_records", 0, update_modified=False)

        frappe.msgprint(
            f"Created {created} overtime record(s) for {self.pull_from_date} "
            f"to {self.pull_to_date}.",
            title="Overtime Pull Complete",
            indicator="green",
        )

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
