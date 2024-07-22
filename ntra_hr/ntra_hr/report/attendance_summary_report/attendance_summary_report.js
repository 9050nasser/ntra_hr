// Copyright (c) 2024, Mansy and contributors
// For license information, please see license.txt

frappe.query_reports["Attendance Summary Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.defaults.get_default("year_start_date"),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.defaults.get_default("year_end_date"),
		},
		// {
		// 	fieldname: "leave_type",
		// 	label: __("Leave Type"),
		// 	fieldtype: "Link",
		// 	options: "Leave Type",
		// },
		{
			fieldname: "from_emp",
			label: __("From Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "to_emp",
			label: __("To Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			label: __("Company"),
			fieldname: "company",
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
	],
	formatter: (value, row, column, data, default_formatter) => {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "leaves") {
			if (data?.leaves < 0) value = `<span style='color:red!important'>${value}</span>`;
			else value = `<span style='color:green!important'>${value}</span>`;
		}
		return value;
	},
	onload: () => {
		if (
			frappe.query_report.get_filter_value("from_date") &&
			frappe.query_report.get_filter_value("to_date")
		)
			return;

		const today = frappe.datetime.now_date();

		frappe.call({
			type: "GET",
			method: "hrms.hr.utils.get_leave_period",
			args: {
				from_date: today,
				to_date: today,
				company: frappe.defaults.get_user_default("Company"),
			},
			freeze: true,
			callback: (data) => {
				frappe.query_report.set_filter_value("from_date", data.message[0].from_date);
				frappe.query_report.set_filter_value("to_date", data.message[0].to_date);
			},
		});
	},
};

