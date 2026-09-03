frappe.listview_settings["Employee Overtime"] = {
    onload: function (listview) {
        listview.page.add_inner_button(__("Process OT → Additional Salary"), function () {
            frappe.prompt(
                [
                    { fieldname: "from_date", label: __("From Date"), fieldtype: "Date", reqd: 1 },
                    { fieldname: "to_date", label: __("To Date"), fieldtype: "Date", reqd: 1 },
                ],
                function (values) {
                    frappe.call({
                        method: "employee_overtime.overtime.process_overtime_additional_salary",
                        args: { from_date: values.from_date, to_date: values.to_date },
                        freeze: true,
                        freeze_message: __("Processing approved overtime..."),
                        callback: function (r) {
                            frappe.msgprint(r.message);
                            listview.refresh();
                        },
                    });
                },
                __("Process Overtime"),
                __("Process")
            );
        });
    },
};
