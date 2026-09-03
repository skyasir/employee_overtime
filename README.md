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
5. **Never blocks a punch** — overtime is computed inside a savepoint. If it
   fails for any reason, its partial writes are rolled back, the traceback goes
   to the Error Log, and the Employee Checkin still saves. A biometric sync is
   never held up by an overtime problem.

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
| Employee                      | `custom_ot_category`             | Link     | Staff / Worker — drives standard hours and break     |
| Salary Structure Assignment   | `custom_gross_pay`               | Currency | Gross basis for the gross-pay OT rate                |

It also seeds the two **Overtime Category** records (Staff, Worker) and the
**Category Rules** matrix below. Both are seeded only when missing, so nothing
you edit is ever overwritten on a later migrate.

## Configure

Open **Overtime Setting** (single doctype) and set:

- **Overtime Salary Component** (required) — the earning OT is paid through.
- **Overtime Amount Calculation** — *Gross Pay Based* (default), *Salary
  Component Based*, or *Fixed Hourly Rate*.
- **Days Divisor**, **Break Time**, **Maximum Overtime Hours/Day**,
  **Maximum Shift Span** (a longer IN→OUT pair is treated as a bad punch).
- **Overtime Grace Period (Minutes)** — extra time must cross this before any
  OT is earned. Defaults to 30.
- **Category Rules** — the standard-hours matrix, see below.
- **Standard / Public Holiday / Weekend Multipliers**.
- **OverTime Approver** — the role allowed to approve and submit OT.

## Categories and standard hours

Standard hours and the break deduction are not fixed in code — they come from
the employee's **OT Category** and the length of their shift, matched against
the **Category Rules** table in Overtime Setting. Installed defaults:

| Category | Shift Hours | Break Deducted |
|----------|-------------|----------------|
| Staff    | 9           | No             |
| Staff    | 8           | Yes (0.5)      |
| Worker   | 8           | Yes (0.5)      |
| Worker   | 10          | No             |
| Worker   | 12          | No             |

The shift length is the Shift Type's `end_time - start_time`, matched to a row
within about a minute. The matched row's **Shift Hours** is also the divisor
that turns per-day pay into an hourly rate — a worker on 20,000/month works out
at `20000 / 31 / 8`. Add categories, shift lengths, or break values as your
policy changes; no code change is needed.

An employee with no category, or on a shift length no row matches, falls back to
the shift length with the global **Break Time** — the behaviour from before
category rules existed.

### Grace period

Overtime only starts once the extra time crosses the grace period, so on an
8-hour shift OT is earned from 8:30 onwards. The grace is a **gate, not a
deduction**: at 8:45 the full 45 minutes is paid, not 15.

### Holiday and weekly-off working

**Overtime Category** carries an *Allow Overtime on Holiday / Weekly Off* flag.
It is off for Staff, so a staff member working a weekly off (Saturday) or a
holiday on their holiday list produces no OT record — that day is repaid as
compensatory off, granted by HR outside this app. It is on for Workers, who are
paid at the holiday/weekend multiplier as usual.

The holiday list is resolved **as of the overtime date**: via **Holiday List
Assignment** on hrms v16, falling back to the employee's — then the company's —
`holiday_list` field, which is how v15 and not-yet-migrated v16 sites store it.
If neither resolves, the day is treated as an ordinary working day. So on a v16
site, make sure staff either have a Holiday List Assignment or a `holiday_list`
on their Employee record, otherwise Saturday working will be paid as OT rather
than held back for comp-off.

## Rate calculation

```
std, break  = Category Rule for (OT Category, shift length)
worked_net  = (OUT - IN) - break
ot_hours    = worked_net - std                   (nil below grace, capped at max)
hourly_rate = per configured method (see below), divided by std
multiplier  = public-holiday / weekend / standard
ot_amount   = ot_hours * hourly_rate * multiplier
```

The shift length used to pick the rule is the shift's `end_time` - `start_time`
(from Shift Type; overnight shifts handled). If the shift has no times set, the
hidden **Standard Daily Hours** fallback in Overtime Setting is used.

Hourly rate by method:

- **Gross Pay Based** — `(gross / days_divisor) / std`, using
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
