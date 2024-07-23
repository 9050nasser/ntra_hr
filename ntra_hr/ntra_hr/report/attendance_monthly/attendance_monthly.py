import frappe
from frappe import _
from frappe.query_builder.functions import Date
from datetime import datetime
from datetime import datetime, timedelta

Filters = frappe._dict
from hrms.hr.doctype.employee_checkin.employee_checkin import (
    calculate_working_hours,
    mark_attendance_and_link_log,
)

def execute(filters: Filters = None) -> tuple:
    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns() -> list[dict]:
    return [
        {"label": _("Attendance"), "fieldname": "attendance", "fieldtype": "Link", "options": "Attendance", "width": 180, "hidden": 1},
        {"label": _("Leave Application"), "fieldname": "leave_app", "fieldtype": "Link", "options": "Leave Application", "width": 140, "hidden": 1},
        {"label": _("Attendance Date"), "fieldname": "attendance_date", "fieldtype": "Date", "width": 120},
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 240, "reqd": 1, "hidden": 1},
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "hidden": 1},
        {"label": _("Check In"), "fieldname": "check_in", "fieldtype": "Data", "width": 180},
        {"label": _("Check Out"), "fieldname": "check_out", "fieldtype": "Data", "width": 180},
        {"label": _("Shift Type"), "fieldname": "shift", "fieldtype": "Data", "width": 180},
        {"label": _("Shift Duration"), "fieldname": "shift_duration", "fieldtype": "Data", "width": 180},
        {"label": _("Time Difference"), "fieldname": "time_diff", "fieldtype": "Time", "width": 80},
        {"label": _("Working Hours"), "fieldname": "working_hours", "fieldtype": "Data", "width": 80},
        {"label": _("Valid In/Valid Out"), "fieldname": "valid_in_valid_out", "fieldtype": "Time", "width": 80},
        {"label": _("Leave Type"), "fieldname": "leave_type", "fieldtype": "Link", "options": "Leave Type", "width": 150},
        {"label": _("Holiday List"), "fieldname": "holiday_list", "fieldtype": "Link", "options": "Holiday List", "width": 120},
        {"label": _("Hasala"), "fieldname": "hasala", "fieldtype": "Time"},
        {"label": _("Department"), "fieldname": "department", "fieldtype": "Data", "hidden": 1},
        {"label": _("actual dayes without holidays"), "fieldname": "adwh", "fieldtype": "Data", "hidden": 1},
        {"label": _("actual dayes"), "fieldname": "act", "fieldtype": "Data", "hidden": 1},
        {"label": _("days_bet"), "fieldname": "days_bet", "fieldtype": "Data", "hidden": 1},
        {"label": _("th"), "fieldname": "th", "fieldtype": "Data", "hidden": 1},
        {"label": _("total_mohtsba"), "fieldname": "total_mohtsba", "fieldtype": "Data", "hidden": 1},
        {"label": _("tpercent"), "fieldname": "percent", "fieldtype": "Data", "hidden": 1},
    ]


def get_data(filters: Filters) -> list[dict]:
    employee = filters.get("employee")
    holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")
    if not holiday_list:
        holiday_list = frappe.db.get_value("Company", frappe.defaults.get_user_default("Company"), "default_holiday_list")
    conditions = []
    if filters.get("from_date"):
        conditions.append(f"att.attendance_date >= '{filters.get('from_date')}'")
    if filters.get("to_date"):
        conditions.append(f"att.attendance_date <= '{filters.get('to_date')}'")
    if filters.get("employee"):
        conditions.append(f"att.employee = '{filters.get('employee')}'")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    condition_str = " AND ".join(conditions)
    if condition_str:
        condition_str = "AND " + condition_str
    response = []
     
    response.append({
			"attendance": "test",
            "leave_app": "test",
            "attendance_date": "test",
            "employee": "test",
            "employee_name": "test",
            "shift": "test",
            "shift_duration": "test",
            "check_in": "test",
            "check_out": "test",
            "time_diff": "test",
            "working_hours": "test",
            "valid_in_valid_out": "test",
            "leave_type": "test",
            "holiday_list": "test",
            "department": "test",
            "hasala": "test",
            "adwh": "test",
            "act": "test",
            "days_bet": "test",
            "th": "test",
            "total_mohtsba": "test",
            "percent": "test",
	})
    
    return response