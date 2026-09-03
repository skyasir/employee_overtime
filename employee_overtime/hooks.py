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
# OT records are created by the daily "Overtime Creation Logic" Server Script
# (a Scheduler Event, shipped as a fixture below), which sums the whole day's
# punches and applies the Overtime Category rules.
#
# The live per-checkin creator is therefore DISABLED to avoid creating two OT
# records for the same day. Re-enable it ONLY if you switch off the daily
# Server Script, by uncommenting the block below.
#
# doc_events = {
#     "Employee Checkin": {
#         "after_insert": "employee_overtime.overtime.create_overtime_from_checkin"
#     }
# }

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
# Ship the daily OT Server Script with the app so it deploys and imports on
# migrate (bench --site <site> migrate) instead of being re-created by hand.
fixtures = [
    {"dt": "Server Script", "filters": [["name", "=", "Overtime Creation Logic"]]}
]

# ---------------------------------------------------------------------------
# Install / migrate
# ---------------------------------------------------------------------------
# Custom fields (OT eligibility, OT category, gross pay) are created on install
# and re-asserted on every migrate so they can never drift. The default
# categories and their standard-hours rules are seeded there too, only when
# missing.
after_install = "employee_overtime.setup.install.after_install"
after_migrate = "employee_overtime.setup.install.after_install"
