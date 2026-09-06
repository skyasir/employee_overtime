frappe.ui.form.on("Employee Overtime", {
    refresh(frm) {
        const colors = { Approved: "green", Rejected: "red", Draft: "orange" };
        if (frm.doc.approval_status) {
            frm.dashboard.set_headline_alert(
                `Approval Status: <b>${frm.doc.approval_status}</b>`,
                colors[frm.doc.approval_status] || "blue"
            );
        }
        if (frm.doc.is_processed) {
            frm.dashboard.add_comment(
                __("Paid via Additional Salary."),
                "blue",
                true
            );
        }
    },
});
