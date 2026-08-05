app_name = "employee_overtime"
app_title = "Employee Overtime"
app_publisher = "Innosphere Consulting"
app_description = "Automated overtime capture, approval, and payout for Frappe HR."
app_email = "amol.pitale@innosphereconsulting.in"
app_license = "MIT"

# This app builds on Frappe HR (hrms): Employee, Employee Checkin, Shift Type,
# Salary Structure Assignment, Additional Salary, Salary Component, Holiday.
required_apps = ["hrms"]

# ---------------------------------------------------------------------------
# Document events
# ---------------------------------------------------------------------------
# On every OUT punch we pair it with the preceding IN punch and, if the
# employee is OT-eligible, spin up a draft Employee Overtime record. This runs
# on after_insert (not before_insert) so the check-in's name is already
# assigned and can be stored on the OT record.
doc_events = {
    "Employee Checkin": {
        "after_insert": "employee_overtime.overtime.create_overtime_from_checkin"
    }
}

# ---------------------------------------------------------------------------
# Install / migrate
# ---------------------------------------------------------------------------
# Custom fields (OT eligibility, gross pay, shift standard hours) are created
# on install and re-asserted on every migrate so they can never drift.
after_install = "employee_overtime.setup.install.after_install"
after_migrate = "employee_overtime.setup.install.after_install"
