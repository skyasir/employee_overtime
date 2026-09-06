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
# OT records are created by the daily overtime job registered under
# scheduler_events below (employee_overtime.overtime.run_daily_overtime_creation),
# which sums the whole day's punches and applies the Overtime Category rules.
# It runs entirely from the app - no Server Script is created in the desk.
#
# The live per-checkin creator is therefore DISABLED to avoid creating two OT
# records for the same day. Re-enable it ONLY if you switch off the daily
# scheduler job, by uncommenting the block below.
#
# doc_events = {
#     "Employee Checkin": {
#         "after_insert": "employee_overtime.overtime.create_overtime_from_checkin"
#     }
# }

# ---------------------------------------------------------------------------
# Scheduler events
# ---------------------------------------------------------------------------
# The daily overtime creation runs from the app itself - nothing is shipped or
# created in the desk's Server Script list. At 12:30 every day it processes the
# previous day's punches using the same whole-day logic as the manual pull.
scheduler_events = {
    "cron": {
        "30 12 * * *": [
            "employee_overtime.overtime.run_daily_overtime_creation"
        ]
    }
}

# ---------------------------------------------------------------------------
# Install / migrate
# ---------------------------------------------------------------------------
# Custom fields (OT eligibility, OT category, gross pay) are created on install
# and re-asserted on every migrate so they can never drift. The default
# categories and their standard-hours rules are seeded there too, only when
# missing.
after_install = "employee_overtime.setup.install.after_install"
after_migrate = "employee_overtime.setup.install.after_install"
