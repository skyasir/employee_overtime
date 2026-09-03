"""Setup run on install and re-asserted on every migrate.

Creates the custom fields the app relies on and ensures the Employee Overtime
naming rule (EMP-<MM>-#####) exists.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
    "Employee": [
        {
            "fieldname": "custom_ot_eligible",
            "label": "OT Eligible",
            "fieldtype": "Check",
            "default": "0",
            "description": "If checked, overtime is auto-calculated for this employee.",
        },
        {
            "fieldname": "custom_ot_category",
            "label": "OT Category",
            "fieldtype": "Link",
            "options": "Overtime Category",
            "insert_after": "custom_ot_eligible",
            "description": (
                "Decides the standard hours and break deduction used for overtime "
                "(Overtime Setting > Category Rules), and whether holiday working "
                "earns OT or compensatory off."
            ),
        },
    ],
    "Salary Structure Assignment": [
        {
            "fieldname": "custom_gross_pay",
            "label": "Gross Pay",
            "fieldtype": "Currency",
            "insert_after": "base",
            "description": "Monthly gross used as the basis for the gross-pay OT rate.",
        }
    ],
}

# The two categories shipped by default. Staff do not earn OT for holiday or weekly
# off working - that is repaid as compensatory off - so the flag is off for them.
CATEGORIES = [
    {"category_name": "Staff", "allow_overtime_on_holiday": 0},
    {"category_name": "Worker", "allow_overtime_on_holiday": 1},
]

# Category Rules are left for HR to enter manually in Overtime Setting, so the
# table is seeded empty. (Add rows here if you later want an out-of-the-box set.)
CATEGORY_RULES = []

# Policy: overtime only starts 30 minutes past the end of the regular shift.
DEFAULT_GRACE_MINUTES = 30

# Employee Overtime records are named EMP-<MM>-##### (e.g. EMP-08-00001).
NAMING_RULE = {
    "document_type": "Employee Overtime",
    "prefix": "EMP-.MM.-",
    "prefix_digits": 5,
    "priority": 0,
}


def after_install():
    create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
    _ensure_naming_rule()
    _seed_categories()
    _seed_category_rules()


def _ensure_naming_rule():
    """Create the Document Naming Rule for Employee Overtime if absent.

    Idempotent: if a rule for this doctype already exists (e.g. one you created
    manually), it is left untouched so its running counter is preserved and no
    naming collisions occur.
    """
    if frappe.db.exists(
        "Document Naming Rule", {"document_type": NAMING_RULE["document_type"]}
    ):
        return

    rule = frappe.new_doc("Document Naming Rule")
    rule.update(NAMING_RULE)
    rule.disabled = 0
    rule.insert(ignore_permissions=True)


def _seed_categories():
    """Create the default categories if they are missing, never touching existing ones.

    Runs on every migrate as well as install, so an edited flag or a renamed
    category must survive: only an absent name is created.
    """
    for category in CATEGORIES:
        if frappe.db.exists("Overtime Category", category["category_name"]):
            continue
        doc = frappe.new_doc("Overtime Category")
        doc.update(category)
        doc.insert(ignore_permissions=True)


def _seed_category_rules():
    """Fill the Category Rules table with the defaults, once.

    This also runs on every migrate, so it must only ever populate an empty
    table: re-adding a row HR deliberately deleted would quietly change what
    people get paid. Seeding is best-effort - Overtime Setting has mandatory
    fields that are still blank on a fresh install, so the save skips them, and
    a failure here must not abort the install or the migrate.
    """
    settings = frappe.get_single("Overtime Setting")
    if settings.get("category_rules"):
        return

    for row in CATEGORY_RULES:
        settings.append("category_rules", row)

    if not settings.overtime_grace_period_minutes:
        settings.overtime_grace_period_minutes = DEFAULT_GRACE_MINUTES

    try:
        settings.flags.ignore_mandatory = True
        settings.save(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Seeding OT category rules failed")
