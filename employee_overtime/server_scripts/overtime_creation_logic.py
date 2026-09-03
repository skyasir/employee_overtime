MAX_SPAN = 16.0
OTS = "Overtime Setting"

target   = frappe.utils.add_days(frappe.utils.getdate(frappe.utils.nowdate()), -1)
next_day = frappe.utils.add_days(target, 1)


win_start = frappe.utils.get_datetime("%s 00:00:00" % target)
win_end   = frappe.utils.get_datetime("%s 12:00:00" % next_day)

break_hrs = frappe.db.get_single_value(OTS, "break_time_hours") or 0
grace_min = frappe.db.get_single_value(OTS, "overtime_grace_period_minutes") or 0
max_ot    = frappe.db.get_single_value(OTS, "maximum_overtime_hours_allowed")
days_div  = frappe.db.get_single_value(OTS, "days_divisor") or 31
base_mult = frappe.db.get_single_value(OTS, "standard_multiplier") or 1.0
apply_ph  = frappe.db.get_single_value(OTS, "applicable_for_public_holiday")
apply_we  = frappe.db.get_single_value(OTS, "applicable_for_weekend")
ph_mult   = frappe.db.get_single_value(OTS, "public_holiday_multiplier")
we_mult   = frappe.db.get_single_value(OTS, "weekend_multiplier")

# --- Overtime Category: load the Category Rules table from Overtime Setting once.
# Each row = (category, shift length, whether to deduct a break, break hours).
HOURS_TOLERANCE = 0.02
category_rules = frappe.get_all(
    "Overtime Category Rule",
    filters={"parenttype": OTS, "parentfield": "category_rules"},
    fields=["ot_category", "shift_hours", "deduct_break", "break_hours"],
)

is_ph = frappe.db.exists("Holiday", {"holiday_date": target})
is_we = target.weekday() >= 5

issues = []

rows = frappe.db.sql("""
    select name, employee, `time` as t, log_type, shift
    from `tabEmployee Checkin`
    where `time` >= %s and `time` < %s
    order by employee, `time`
""", (win_start, win_end), as_dict=True)

by_emp = {}
for r in rows:
    by_emp.setdefault(r.employee, []).append(r)

for employee, punches in by_emp.items():

    if frappe.db.exists("Employee Overtime",
        {"employee_id": employee, "date": target, "docstatus": ["<", 2]}):
        continue

    if not (frappe.db.get_value("Employee", employee, "custom_ot_eligible") or 0):
        continue

    # --- Overtime Category: the employee's category drives the break/std rule
    # and the holiday policy below.
    category = frappe.db.get_value("Employee", employee, "custom_ot_category")

    # --- Overtime Category: some categories (e.g. Staff) do not earn OT on a
    # holiday or weekly off - that is repaid as compensatory off outside this
    # app. A category with Allow Overtime on Holiday ticked (e.g. Worker), or an
    # employee with no category, keeps the normal behaviour.
    if category and (is_ph or is_we):
        allow_holiday_ot = frappe.db.get_value(
            "Overtime Category", category, "allow_overtime_on_holiday") or 0
        if not allow_holiday_ot:
            continue

    worked = 0.0
    pending_in = None
    first_in = None
    first_in_name = None
    last_out = None
    last_out_name = None
    shift = None

    for p in punches:
        if not shift and p.shift:
            shift = p.shift

        if p.log_type == "IN":
            if pending_in:
                issues.append(
                    "%s: IN at %s had no matching OUT (overwritten by IN at %s)"
                    % (employee, pending_in.t, p.t)
                )
            pending_in = p
            if not first_in:
                first_in = p.t
                first_in_name = p.name

        elif p.log_type == "OUT" and pending_in:
            span = frappe.utils.time_diff_in_hours(p.t, pending_in.t)
            if span > MAX_SPAN:
                issues.append(
                    "%s: session %s -> %s = %.2f hrs exceeds MAX_SPAN, skipped"
                    % (employee, pending_in.t, p.t, span)
                )
            elif span > 0:
                worked = worked + span
                last_out = p.t
                last_out_name = p.name
            pending_in = None

    if pending_in:
        issues.append(
            "%s: IN at %s had no OUT by end of window (missed punch)"
            % (employee, pending_in.t)
        )

    worked = round(worked, 2)
    if not first_in or not last_out or worked <= 0:
        continue

    std = 0
    if shift:
        std = frappe.db.get_value("Shift Type", shift, "custom_standard_working_hours") or 0
    if not std:
        issues.append("%s: no standard hours found for shift '%s', skipped" % (employee, shift))
        continue

    # --- Overtime Category: match this employee's category and shift length
    # against the Category Rules table. A match sets the standard hours and the
    # unpaid break for this shift (e.g. Staff 8h deducts 0.5h, Staff 9h deducts
    # nothing). No category / no matching row -> keep the global break above.
    emp_std = std
    emp_break = break_hrs
    if category:
        for rule in category_rules:
            if rule.ot_category != category:
                continue
            if abs((rule.shift_hours or 0) - std) < HOURS_TOLERANCE:
                emp_std = rule.shift_hours or std
                emp_break = (rule.break_hours or break_hrs) if rule.deduct_break else 0
                break

    worked_net = round(worked - emp_break, 2)
    ot_hours = round(worked_net - emp_std, 2)

    # Grace period: OT applies only once the extra time exceeds the grace
    # threshold (e.g. 30 min), so an 8h shift starts earning at 8:30. It is a
    # gate, not a deduction - once crossed, the whole extra span is paid.
    grace = (grace_min or 0) / 60.0
    if ot_hours <= 0 or ot_hours < grace:
        continue

    if max_ot and ot_hours > max_ot:
        ot_hours = max_ot

    gross = frappe.db.get_value("Salary Structure Assignment",
        {"employee": employee, "docstatus": 1},
        "custom_gross_pay", order_by="from_date desc") or 0
    if not gross:
        gross = frappe.db.get_value("Salary Structure Assignment",
            {"employee": employee, "docstatus": 1},
            "base", order_by="from_date desc") or 0

    hourly = (gross / days_div) / emp_std if (emp_std and gross) else 0

    multiplier = base_mult
    if apply_ph and is_ph:
        multiplier = ph_mult or multiplier
    elif apply_we and is_we:
        multiplier = we_mult or multiplier

    ot_rate = hourly * multiplier
    ot_amount = ot_hours * ot_rate

    ot = frappe.new_doc("Employee Overtime")
    ot.employee_id             = employee
    ot.employee_checkin_id     = first_in_name
    ot.employee_checkin_id_out = last_out_name
    ot.date                    = target
    ot.total__hours            = worked
    ot.standard_working_hours  = emp_std
    ot.overtime_hours          = ot_hours
    ot.ot_multiplier           = multiplier
    ot.ot_rate                 = ot_rate
    ot.ot_amount               = ot_amount
    ot.approval_status         = "Draft"
    ot.employee_check_in       = first_in
    ot.employee_check_out      = last_out
    ot.shift_type              = shift
    ot.ot_category             = category
    ot.insert(ignore_permissions=True)

if issues:
    frappe.log_error(
        message="\n".join(issues),
        title="OT Creation - punch anomalies %s" % target
    )
