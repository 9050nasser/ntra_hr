import frappe
from frappe import _
from frappe.query_builder.functions import Date
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
        {"label": _("Attendance"), "fieldname": "attendance", "fieldtype": "Link", "options": "Attendance", "width": 180},
        {"label": _("Leave Application"), "fieldname": "leave_app", "fieldtype": "Link", "options": "Leave Application", "width": 180},
        {"label": _("Attendance Date"), "fieldname": "attendance_date", "fieldtype": "Date", "width": 120},
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 240},
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "hidden": 1},
        {"label": _("Check In"), "fieldname": "check_in", "fieldtype": "Data", "width": 120},
        {"label": _("Check Out"), "fieldname": "check_out", "fieldtype": "Data", "width": 120},
        {"label": _("Time Difference"), "fieldname": "time_diff", "fieldtype": "Time", "width": 80},
        {"label": _("Working Hours"), "fieldname": "working_hours", "fieldtype": "Time", "width": 80},
        {"label": _("Valid In/Valid Out"), "fieldname": "valid_in_valid_out", "fieldtype": "Time", "width": 80},
        {"label": _("Leave Type"), "fieldname": "leave_type", "fieldtype": "Link", "options": "Leave Type", "width": 150},
        {"label": _("Holiday List"), "fieldname": "holiday_list", "fieldtype": "Link", "options": "Holiday List", "width": 150},
    ]


def get_data(filters: Filters) -> list[dict]:
    conditions = []
    if filters.get("from_date"):
        conditions.append(f"att.attendance_date >= '{filters.get('from_date')}'")
    if filters.get("to_date"):
        conditions.append(f"att.attendance_date <= '{filters.get('to_date')}'")
    if filters.get("employee"):
        conditions.append(f"att.employee = '{filters.get('employee')}'")

    condition_str = " AND ".join(conditions)
    if condition_str:
        condition_str = "AND " + condition_str
    
    result = frappe.db.sql(f"""
       SELECT * FROM (
    SELECT
        att.name as attendance,
        CASE WHEN att.leave_type IS NOT NULL THEN '' ELSE leave_app.name END AS leave_app,
        att.attendance_date,
        att.employee as employee,
        att.employee_name,
        COALESCE(att.working_hours, leave_app.custom_absence_time) as working_hours,
        CASE WHEN att.leave_type IS NOT NULL THEN '' ELSE att.leave_type END AS leave_type,
        emp.holiday_list,
        MIN(checkin.time) as check_in,
        MAX(checkin.time) as check_out,
        0 as sort_order -- Add a sort order for regular attendance
    FROM `tabAttendance` att
    LEFT JOIN `tabLeave Application` leave_app ON att.leave_application = leave_app.name
    JOIN `tabEmployee` emp ON att.employee = emp.name
    LEFT JOIN `tabEmployee Checkin` checkin ON att.employee = checkin.employee AND DATE(checkin.time) = att.attendance_date
    WHERE att.docstatus = 1 AND checkin.time IS NOT NULL {condition_str}
    GROUP BY att.name

    UNION ALL

    SELECT
        att.name as attendance,
        leave_app.name as leave_app,
        att.attendance_date,
        att.employee,
        att.employee_name,
        TIMEDIFF(leave_app.custom_t_time, leave_app.custom_f_time) as working_hours,
        att.leave_type as leave_type,
        emp.holiday_list,
        leave_app.custom_f_time as check_in,
        leave_app.custom_t_time as check_out,
        1 as sort_order
    FROM `tabAttendance` att
    LEFT JOIN `tabLeave Application` leave_app ON att.leave_application = leave_app.name
    JOIN `tabEmployee` emp ON att.employee = emp.name
    LEFT JOIN `tabEmployee Checkin` checkin ON att.employee = checkin.employee AND DATE(checkin.time) = att.attendance_date
    LEFT JOIN `tabLeave Type` lt ON att.leave_type = lt.name
    WHERE att.docstatus = 1 AND att.leave_type IS NOT NULL {condition_str}
    GROUP BY att.name


) AS combined_results

ORDER BY combined_results.attendance_date, combined_results.sort_order;

    """, as_dict=True)
        
    

    response = []
    for row in result:
        # get_employee_holiday_list(row.employee)
        working_hours = get_working_hours(row.employee, row.attendance_date, row.check_out, row.check_in, row.leave_type)
        valid_in_valid_out = get_valid_in_valid_out(row.check_in, row.check_out)
        response.append({
            "attendance": row.attendance,
            "leave_app": row.leave_app,
            "attendance_date": row.attendance_date,
            "employee": row.employee,
            "employee_name": row.employee_name,
            "check_in": row.check_in,
            "check_out": row.check_out,
            "time_diff": float_to_hours_minutes(time_diff_in_hours(row.check_in, row.check_out) if row.check_in and row.check_out else 0),
            "working_hours": working_hours,
            "valid_in_valid_out": float_to_hours_minutes(valid_in_valid_out),
            "leave_type": row.leave_type,
            "holiday_list": row.holiday_list,
        })

    return response

import datetime

# def get_employee_holiday_list(employee):
#     holiday_list = ("Holiday List", employee)
#     for hday in holiday_list.holidays:
#         hday.date
    # return holiday_list
def float_to_hours_minutes(time_diff):
  if isinstance(time_diff, str):
    hours, minutes = time_diff.split(':')
    return int(hours), int(minutes)
  else:
    # Handle case where time_diff is already a float (assuming it represents hours)
    hours = int(time_diff)
    minutes = int((time_diff - hours) * 60)  # Convert remaining decimal to minutes
    
    return f"{hours:02d}:{minutes:02d}"

def get_valid_in_valid_out(check_in, check_out):
    if not check_in or not check_out:
        return 0
    return time_diff_in_hours(check_in, check_out)

def get_working_hours(employee, attendance_date, leave_to, leave_from, is_leave):
    emp = frappe.get_doc("Employee", employee)
    if emp.custom_emp_type:
        return 7
    if emp.custom_hour_count:
        return 6
    
    if is_leave:
        time1_obj = frappe.utils.data.get_datetime(leave_from)
        time2_obj = frappe.utils.data.get_datetime(leave_to)
        duration = time2_obj - time1_obj
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        seconds = duration.seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    date_one = datetime.date(2024, 3, 11)
    date_two = datetime.date(2024, 4, 10)

    if date_one <= attendance_date <= date_two:
        return 5

    return 7

def time_diff_in_hours(start, end):
    if not start or not end:
        return 0
    return round(float((end - start).total_seconds()) / 3600, 2)

def add_total_row(result: list[dict], filters: Filters) -> list[dict]:
    add_total_row = False
    leave_type = filters.get("leave_type")

    if filters.get("employee") and filters.get("leave_type"):
        add_total_row = True

    if not add_total_row:
        if not filters.get("employee"):
            employees_from_result = list(set([row['employee'] for row in result]))
            if len(employees_from_result) != 1:
                return result

        leave_types_from_result = list(set([row['leave_type'] for row in result]))
        if len(leave_types_from_result) == 1:
            leave_type = leave_types_from_result[0]
            add_total_row = True

    if not add_total_row:
        return result

    total_row = frappe._dict({"employee": _("Total Leaves ({0})").format(leave_type)})
    total_row["leaves"] = sum((row.get("leaves") or 0) for row in result)

    result.append(total_row)
    return result
