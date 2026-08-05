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
        }
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
