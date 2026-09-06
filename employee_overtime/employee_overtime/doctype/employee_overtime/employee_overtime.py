import frappe
from frappe.model.document import Document


class EmployeeOvertime(Document):
    def before_submit(self):
        """Replaces the 'Employ OT Approve' server script.

        Only allow submission of Approved records, and only by users holding the
        configured approver role (System Managers are always allowed).
        """
        if self.approval_status != "Approved":
            frappe.throw("Set Approval Status to 'Approved' before submitting.")

        approver_role = frappe.db.get_single_value("Overtime Setting", "overtime_approver")
        if approver_role:
            has_role = frappe.db.exists(
                "Has Role",
                {"parent": frappe.session.user, "parenttype": "User", "role": approver_role},
            )
            is_sysmgr = frappe.db.exists(
                "Has Role",
                {"parent": frappe.session.user, "parenttype": "User", "role": "System Manager"},
            )
            if not has_role and not is_sysmgr:
                frappe.throw(
                    "Only users with the '" + approver_role + "' role can approve overtime."
                )

    def before_cancel(self):
        """Replaces the 'OT cancel' server script.

        Block cancellation once the OT has been paid out via Additional Salary.
        """
        if self.is_processed:
            frappe.throw(
                "This overtime is already paid via Additional Salary. "
                "Reverse that Additional Salary before cancelling."
            )
