# Employee Overtime

A Frappe HR app that automatically captures overtime from check-ins, routes it
through an approval workflow, and pays it out via Additional Salary.

## What it does

1. **Auto-capture** — when an employee's `OUT` check-in is saved, the app pairs
   it with the preceding `IN` punch, and if the employee is OT-eligible, creates
   a **draft Employee Overtime** record with the computed hours, rate, and amount.
2. **Approve & submit** — HR sets *Approval Status = Approved* and submits. Only
   users holding the configured approver role (or System Manager) may submit.
3. **Pay out** — from the Employee Overtime **list view**, the *Process OT →
   Additional Salary* button turns approved, submitted, unprocessed OT in a date
   range into submitted **Additional Salary** records and flags each as processed.
4. **Protected** — a processed OT record cannot be cancelled until its Additional
   Salary is reversed.

## Requirements

- Frappe Framework
- Frappe HR (`hrms`) — provides Employee, Employee Checkin, Shift Type, Salary
  Structure Assignment, Additional Salary, Salary Component, and Holiday.

## Install

```bash
# from your bench directory
bench get-app employee_overtime /path/to/employee_overtime
bench --site your-site install-app employee_overtime
bench --site your-site migrate
```

Installing also creates a **Document Naming Rule** so Employee Overtime records are named `EMP-<MM>-#####` (e.g. `EMP-08-00001`). If a naming rule for this doctype already exists on your site, it is left untouched (its counter is preserved).

Installing creates the required custom fields automatically:

| DocType                       | Field                            | Type     | Purpose                                              |
|-------------------------------|----------------------------------|----------|------------------------------------------------------|
| Employee                      | `custom_ot_eligible`             | Check    | Turns auto-capture on for the employee               |
| Salary Structure Assignment   | `custom_gross_pay`               | Currency | Gross basis for the gross-pay OT rate                |

## Configure

Open **Overtime Setting** (single doctype) and set:

- **Overtime Salary Component** (required) — the earning OT is paid through.
- **Overtime Amount Calculation** — *Gross Pay Based* (default), *Salary
  Component Based*, or *Fixed Hourly Rate*.
- **Days Divisor**, **Break Time**, **Maximum Overtime Hours/Day**.
- **Standard / Public Holiday / Weekend Multipliers**.
- **OverTime Approver** — the role allowed to approve and submit OT.

## Rate calculation

```
worked_net  = (OUT - IN) - break_time
ot_hours    = worked_net - shift_hours           (capped at max, min 0)
hourly_rate = per configured method (see below)
multiplier  = public-holiday / weekend / standard
ot_amount   = ot_hours * hourly_rate * multiplier
```

`shift_hours` = the shift's `end_time` - `start_time` (from Shift Type; overnight
shifts handled). If the shift has no times set, the hidden **Standard Daily
Hours** fallback in Overtime Setting is used.

Hourly rate by method:

- **Gross Pay Based** — `(gross / days_divisor) / shift_hours`, using
  `custom_gross_pay` from the latest submitted Salary Structure Assignment
  (falls back to `base`).
- **Salary Component Based** — the *Applicable Salary Component* amount on the
  employee's latest salary structure, divided the same way. Falls back to gross
  if the component amount can't be resolved.
- **Fixed Hourly Rate** — the flat rate entered in settings.

## Notes on the migration from Server/Client Scripts

This app replaces the earlier database scripts with versioned app code:

- *OT Creation* → `after_insert` hook on Employee Checkin
  (`employee_overtime.overtime.create_overtime_from_checkin`).
- *Employ OT Approve* → `EmployeeOvertime.before_submit`.
- *OT cancel* → `EmployeeOvertime.before_cancel`.
- *OT Scheduler Button* → `employee_overtime_list.js`, calling the whitelisted
  method `employee_overtime.overtime.process_overtime_additional_salary`.
- *Process OT - Additional Salary* (API server script) → the same whitelisted
  method. It keeps the original behaviour — one aggregated Additional Salary per
  employee for the period, `payroll_date = to_date`,
  `overwrite_salary_structure_amount = 1`, defaulting to the current month — and
  adds a role guard and per-employee error isolation.

Two data fixes were made while porting: the Total Hours field is now
`total_hours` (the old `total__hours` never received a value), and `ot_rate` /
`ot_multiplier` are now real fields so the computed values persist.

## License

MIT
