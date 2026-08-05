"""Core overtime logic for the Employee Overtime app.

Contains:
  * create_overtime_from_checkin  -> Employee Checkin "after_insert" hook
  * process_overtime_additional_salary -> whitelisted action behind the list button
  * rate / multiplier helpers shared by both
"""

import frappe
from frappe.utils import getdate, time_diff_in_hours

# Sanity ceiling: a single IN->OUT span longer than this is treated as a bad
# pair (forgot to punch out, overnight anomaly, etc.) and is ignored.
MAX_SPAN = 16.0
OTS = "Overtime Setting"


# ---------------------------------------------------------------------------
# Checkin -> Employee Overtime
# ---------------------------------------------------------------------------
def create_overtime_from_checkin(doc, method=None):
    """After Insert on Employee Checkin.

    On an OUT punch, find the immediately preceding punch. If it is an IN punch
    and the employee is OT-eligible, compute the overtime for that span and
    create a draft Employee Overtime record. Runs after insert so this check-in
    already has a name to store as the OUT reference. Never blocks the save.
    """
    if doc.log_type != "OUT":
        return

    last_punch = frappe.db.sql(
        """
        select name, `time` as t, log_type, shift
        from `tabEmployee Checkin`
        where employee = %s
          and `time` < %s
        order by `time` desc
        limit 1
        """,
        (doc.employee, doc.time),
        as_dict=True,
    )

    # No matching IN -> skip silently.
    if not (last_punch and last_punch[0].log_type == "IN"):
        return

    first_in = last_punch[0].t
    in_checkin = last_punch[0].name
    shift = doc.shift or last_punch[0].shift

    employee_check_in = first_in
    employee_check_out = doc.time

    worked = round(time_diff_in_hours(employee_check_out, employee_check_in), 2)

    ot_eligible = frappe.db.get_value("Employee", doc.employee, "custom_ot_eligible") or 0
    if not ot_eligible or worked > MAX_SPAN:
        return

    settings = frappe.get_cached_doc(OTS)

    # Standard working hours for this shift = Shift Type end_time - start_time.
    std = _shift_standard_hours(shift)
    if not std:
        # Fall back to the configured standard daily hours if the shift has no times.
        std = settings.standard_daily_hours or 0
    if not std:
        return

    break_hrs = settings.break_time_hours or 0
    worked_net = round(worked - break_hrs, 2)
    ot_hours = round(worked_net - std, 2)
    if ot_hours <= 0:
        return

    # One OT record per IN punch.
    if frappe.db.exists(
        "Employee Overtime",
        {"employee_checkin_id": in_checkin, "docstatus": ["<", 2]},
    ):
        return

    max_ot = settings.maximum_overtime_hours_allowed
    if max_ot and ot_hours > max_ot:
        ot_hours = max_ot

    day_hrs = std
    hourly = get_hourly_rate(doc.employee, day_hrs, settings)

    d = getdate(first_in)
    multiplier = get_multiplier(d, settings)

    ot_rate = hourly * multiplier
    ot_amount = ot_hours * ot_rate

    ot = frappe.new_doc("Employee Overtime")
    ot.employee_id = doc.employee
    ot.employee_checkin_id_out = doc.name
    ot.employee_checkin_id = in_checkin
    ot.date = d
    ot.total_hours = worked
    ot.standard_working_hours = std
    ot.overtime_hours = ot_hours
    ot.ot_multiplier = multiplier
    ot.ot_rate = ot_rate
    ot.ot_amount = ot_amount
    ot.approval_status = "Draft"
    ot.employee_check_in = employee_check_in
    ot.employee_check_out = employee_check_out
    ot.shift_type = shift
    ot.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Shift standard hours (from Shift Type start_time / end_time)
# ---------------------------------------------------------------------------
def _shift_standard_hours(shift):
    """Total working hours of a shift = Shift Type end_time - start_time.

    Handles overnight shifts (end earlier than start). Returns 0 when the shift
    or either time is not set.
    """
    if not shift:
        return 0
    times = frappe.db.get_value(
        "Shift Type", shift, ["start_time", "end_time"], as_dict=True
    )
    if not times or times.start_time is None or times.end_time is None:
        return 0

    diff = _time_to_seconds(times.end_time) - _time_to_seconds(times.start_time)
    if diff < 0:  # overnight shift, e.g. 22:00 -> 06:00
        diff += 24 * 3600
    return round(diff / 3600.0, 2)


def _time_to_seconds(t):
    """Seconds since midnight for a Time value.

    A Time field comes back from the DB as a datetime.timedelta, but may also be
    a 'HH:MM:SS' string depending on the caller; handle both.
    """
    if hasattr(t, "total_seconds"):
        return t.total_seconds()
    parts = str(t).split(":")
    hours = int(parts[0])
    minutes = int(parts[1]) if len(parts) > 1 else 0
    seconds = int(float(parts[2])) if len(parts) > 2 else 0
    return hours * 3600 + minutes * 60 + seconds


# ---------------------------------------------------------------------------
# Rate helpers
# ---------------------------------------------------------------------------
def get_hourly_rate(employee, day_hrs, settings):
    """Resolve the base hourly rate per the configured calculation method.

    Falls back to Gross Pay Based whenever the chosen method can't be resolved,
    so an OT record is never created with a silently-zero rate when data exists.
    """
    method = settings.overtime_calculation_method or "Gross Pay Based"
    days_div = settings.days_divisor or 31

    if method == "Fixed Hourly Rate":
        return settings.hourly_rate or 0

    if method == "Salary Component Based":
        amount = _component_amount(employee, settings.applicable_salary_component)
        if amount and day_hrs:
            return (amount / days_div) / day_hrs
        # else fall through to gross-based

    # Gross Pay Based (default and universal fallback)
    gross = _latest_assignment_value(employee, "custom_gross_pay")
    if not gross:
        gross = _latest_assignment_value(employee, "base")

    if day_hrs and gross:
        return (gross / days_div) / day_hrs
    return 0


def _latest_assignment_value(employee, fieldname):
    return frappe.db.get_value(
        "Salary Structure Assignment",
        {"employee": employee, "docstatus": 1},
        fieldname,
        order_by="from_date desc",
    ) or 0


def _component_amount(employee, component):
    """Amount of a given salary component on the employee's latest structure."""
    if not component:
        return 0
    salary_structure = frappe.db.get_value(
        "Salary Structure Assignment",
        {"employee": employee, "docstatus": 1},
        "salary_structure",
        order_by="from_date desc",
    )
    if not salary_structure:
        return 0
    return frappe.db.get_value(
        "Salary Detail",
        {
            "parent": salary_structure,
            "parentfield": "earnings",
            "salary_component": component,
        },
        "amount",
    ) or 0


def get_multiplier(d, settings):
    """Pick the pay multiplier for the OT date (public holiday > weekend > standard)."""
    multiplier = settings.standard_multiplier or 1.0

    if settings.applicable_for_public_holiday and frappe.db.exists(
        "Holiday", {"holiday_date": d}
    ):
        multiplier = settings.public_holiday_multiplier or multiplier
    elif settings.applicable_for_weekend and d.weekday() >= 5:
        multiplier = settings.weekend_multiplier or multiplier

    return multiplier


# ---------------------------------------------------------------------------
# Employee Overtime -> Additional Salary
# ---------------------------------------------------------------------------
@frappe.whitelist()
def process_overtime_additional_salary(from_date=None, to_date=None):
    """Roll up approved, submitted, unprocessed overtime for a period into one
    Additional Salary per employee (summed), then flag each source OT as
    processed.

    Triggered by the "Process OT -> Additional Salary" list button. If dates are
    omitted, the current month is used.
    """
    roles = set(frappe.get_roles(frappe.session.user))
    if not ({"HR Manager", "System Manager"} & roles):
        frappe.throw("Only HR Manager or System Manager can process overtime.")

    if not from_date or not to_date:
        today = frappe.utils.today()
        from_date = frappe.utils.get_first_day(today)
        to_date = frappe.utils.get_last_day(today)

    component = frappe.db.get_single_value(OTS, "overtime_salary_component")
    if not component:
        frappe.throw("Set an <b>Overtime Salary Component</b> in Overtime Setting first.")

    ot_records = frappe.get_all(
        "Employee Overtime",
        filters={
            "docstatus": 1,
            "approval_status": "Approved",
            "is_processed": 0,
            "date": ["between", [from_date, to_date]],
        },
        fields=["name", "employee_id", "ot_amount"],
    )

    if not ot_records:
        return f"No approved, unprocessed overtime found for {from_date} to {to_date}."

    # Aggregate per employee: one Additional Salary each, covering the period.
    agg = {}
    for r in ot_records:
        bucket = agg.setdefault(r.employee_id, {"amount": 0.0, "names": []})
        bucket["amount"] += r.ot_amount or 0
        bucket["names"].append(r.name)

    created, errors = 0, []

    for emp_id, data in agg.items():
        if data["amount"] <= 0:
            continue
        try:
            add_sal = frappe.new_doc("Additional Salary")
            add_sal.employee = emp_id
            add_sal.salary_component = component
            add_sal.amount = data["amount"]
            add_sal.payroll_date = to_date
            add_sal.overwrite_salary_structure_amount = 1
            add_sal.company = frappe.db.get_value("Employee", emp_id, "company")
            add_sal.insert(ignore_permissions=True)
            add_sal.submit()

            # is_processed is read-only on a submitted OT; write it directly.
            for nm in data["names"]:
                frappe.db.set_value("Employee Overtime", nm, "is_processed", 1)
            created += 1
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"OT processing failed for {emp_id}")
            errors.append(emp_id)

    entry_word = "entry" if created == 1 else "entries"
    msg = f"Created <b>{created}</b> Additional Salary {entry_word} for {from_date} to {to_date}."
    if errors:
        msg += f"<br>Failed for: {', '.join(errors)} (see Error Log)."
    return msg
