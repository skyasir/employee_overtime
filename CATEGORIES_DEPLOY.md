# Overtime Categories — deploy notes

This build adds category-based overtime to the app.

## New files
- employee_overtime/employee_overtime/doctype/overtime_category/            (doctype: Overtime Category)
- employee_overtime/employee_overtime/doctype/overtime_category_rule/       (child doctype: Overtime Category Rule)
- employee_overtime/fixtures/server_script.json                             (daily "Overtime Creation Logic" Server Script, with category logic)
- employee_overtime/server_scripts/overtime_creation_logic.py              (readable copy of that script)

## Changed files
- employee_overtime/hooks.py                                                (registers the Server Script fixture; per-checkin hook disabled — see below)
- employee_overtime/overtime.py                                             (category helpers used by the live path)
- employee_overtime/setup/install.py                                        (adds custom_ot_category; seeds default categories + rules)
- employee_overtime/employee_overtime/doctype/employee_overtime/employee_overtime.json     (adds ot_category, break_hours)
- employee_overtime/employee_overtime/doctype/overtime_setting/overtime_setting.json       (adds category_rules table)
- employee_overtime/employee_overtime/doctype/overtime_setting/overtime_setting.py

## OT is created ONE way here: the daily Server Script
`hooks.py` has the live per-checkin creator commented out so the same day is not
recorded twice. If you prefer the live per-punch behaviour instead of the daily
batch, disable the "Overtime Creation Logic" Server Script and uncomment the
doc_events block in hooks.py.

## Deploy
    cd ~/frappe-bench
    # commit these files to your app repo, then on the server:
    bench --site <your-site> migrate      # imports doctypes, custom fields, seeds, and the Server Script fixture
    bench --site <your-site> clear-cache

## Verify before go-live
- Employee master shows "OT Category"; assign Staff / Worker where needed.
- Overtime Setting > Category Rules is populated (Staff 8/9h, Worker 8/10/12h).
- Confirm the Employee Overtime field is `total_hours` and update the Server Script
  line `ot.total__hours` if your field differs.

## Manual backfill (Overtime Setting > Pull Records)
Overtime Setting now has a **Pull Records** checkbox. Tick it to reveal **Pull
From Date** / **Pull To Date**, set the range, and Save. Draft Employee Overtime
is created for every eligible check-in in that range using the same category +
grace logic as the scheduled run (rerun-safe: days that already have a record
are skipped). The checkbox clears itself after the run. Only HR Manager /
System Manager can trigger it. This replaces the need for the separate
"Month End checking overtime" Server Script.
