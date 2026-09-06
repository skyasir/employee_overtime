# Overtime Categories — deploy notes

This build adds category-based overtime to the app.

## New files
- employee_overtime/employee_overtime/doctype/overtime_category/            (doctype: Overtime Category)
- employee_overtime/employee_overtime/doctype/overtime_category_rule/       (child doctype: Overtime Category Rule)

## Changed files
- employee_overtime/hooks.py                                                (registers the daily scheduler job; per-checkin hook disabled — see below)
- employee_overtime/overtime.py                                             (category helpers used by the live path)
- employee_overtime/setup/install.py                                        (adds custom_ot_category; seeds default categories + rules)
- employee_overtime/employee_overtime/doctype/employee_overtime/employee_overtime.json     (adds ot_category, break_hours)
- employee_overtime/employee_overtime/doctype/overtime_setting/overtime_setting.json       (adds category_rules table)
- employee_overtime/employee_overtime/doctype/overtime_setting/overtime_setting.py

## OT is created ONE way here: the daily scheduler job
`hooks.py` runs `run_daily_overtime_creation` from the app (via `scheduler_events`)
and has the live per-checkin creator commented out so the same day is not
recorded twice. Nothing is created in the desk's Server Script list. If you
prefer the live per-punch behaviour instead of the daily batch, remove the
scheduler_events entry and uncomment the doc_events block in hooks.py.

## Deploy
    cd ~/frappe-bench
    # commit these files to your app repo, then on the server:
    bench --site <your-site> migrate      # imports doctypes, custom fields, and seeds
    bench --site <your-site> scheduler enable   # daily OT job runs at 12:30
    bench --site <your-site> clear-cache

## Verify before go-live
- Employee master shows "OT Category"; assign Staff / Worker where needed.
- Overtime Setting > Category Rules is populated (Staff 8/9h, Worker 8/10/12h).
- Confirm the Employee Overtime field is `total_hours` and update the
  `ot.total__hours` line in `overtime.py` if your field differs.

## Manual backfill (Overtime Setting > Pull Records)
Overtime Setting now has a **Pull Records** checkbox. Tick it to reveal **Pull
From Date** / **Pull To Date**, set the range, and Save. Draft Employee Overtime
is created for every eligible check-in in that range using the same category +
grace logic as the scheduled run (rerun-safe: days that already have a record
are skipped). The checkbox clears itself after the run. Only HR Manager /
System Manager can trigger it.
