"""Custom fields this app relies on, created on install and re-asserted on migrate."""

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


def after_install():
    create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
