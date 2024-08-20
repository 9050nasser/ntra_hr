import frappe
from frappe import _
from frappe.query_builder.functions import Date
from datetime import datetime
from datetime import datetime, timedelta
from frappe.utils import getdate


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
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "align": "center"},
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data"},
        {"label": _("Total WD Without Holidays"), "fieldname": "total_wd", "fieldtype": "Float"},
        {"label": _("Actual Attendance Days"), "fieldname": "actual_att_days", "fieldtype": "Float"},
        {"label": _("Days Difference"), "fieldname": "days_diff", "fieldtype": "Float"},
        {"label": _("Total Required Hours"), "fieldname": "total_req_hours", "fieldtype": "Data"},
        {"label": _("Total Actual Hours"), "fieldname": "total_actual_hours", "fieldtype": "Data"},
        {"label": _("Hours Differnce"), "fieldname": "hours_diff", "fieldtype": "Data"},
        {"label": _("Day Average"), "fieldname": "day_avg", "fieldtype": "Data"},
        {"label": _("Attendance Percentage"), "fieldname": "att_perc", "fieldtype": "Percent", "align": "center"},
        
    ]


def get_data(filters: Filters) -> list[dict]:
    
    datef = filters.get("from_date")
    datet = filters.get("to_date")
    from_emp = filters.get("from_emp")
    to_emp = filters.get("to_emp")
    
    result = frappe.db.sql(f"""
       SELECT
        emp.employee,
        emp.custom_employee_name_ar as employee_name,
        att.shift as shift,
        att.attendance_date as attd,
        SUM(att.working_hours) as actual_working_hours
		FROM `tabEmployee` emp
        LEFT JOIN `tabAttendance` att ON emp.name = att.employee
		WHERE emp.employee BETWEEN '{from_emp}' AND '{to_emp}'
        AND att.attendance_date BETWEEN '{datef}' AND '{datet}'
        AND att.docstatus = 1
        AND emp.status = "Active"
        GROUP BY att.employee
		ORDER BY CAST(emp.employee AS UNSIGNED) ASC;

    """, as_dict=True)
    response = []
    for row in result:
        total_wd = act(row.employee, datef, datet)
        actual_att_days = act(row.employee, datef, datet) - adwh(row.employee, datef, datet)
        days_diff = adwh(row.employee, datef, datet)
        total_req_hours = float_to_hhmmss(get_req_hours(row.employee, datef, datet))
        total_actual_hours = float_to_hhmmss(row.actual_working_hours)
        hours_diff = float_to_hhmmss(abs(get_req_hours(row.employee, datef, datet) - row.actual_working_hours))
        day_avg = float_to_hhmmss(abs(row.actual_working_hours / (total_wd if total_wd != 0 else 1)))
        att_perc = abs(row.actual_working_hours / get_req_hours(row.employee, datef, datet) * 100)
        response.append({
            "employee": row.employee,
            "employee_name": row.employee_name,
            "total_wd": total_wd,
            "actual_att_days": actual_att_days,
            "days_diff": days_diff,
            "total_req_hours": total_req_hours,
            "total_actual_hours": total_actual_hours,
            "hours_diff": hours_diff,
            "day_avg": day_avg if day_avg != 0 else 1,
            "att_perc": att_perc,
        })

    return response

def get_req_hours(employee, datef, datet):
    start_date = getdate(datef)
    end_date = getdate(datet)
    total_hours = timedelta()
    
    # Retrieve the holiday list
    holiday_days = set()
    holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")
    if not holiday_list:
        holiday_list = frappe.db.get_value("Company", frappe.defaults.get_user_default("Company"), "default_holiday_list")

    if holiday_list:
        holiday_list_details = frappe.get_doc("Holiday List", holiday_list)
        holiday_days = {holiday.holiday_date.strftime('%Y-%m-%d') for holiday in holiday_list_details.holidays}
    
    # Total days excluding holidays
    current_date = start_date
    total_days = 0
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        
        # Check if the current date is not a holiday
        if date_str not in holiday_days:
            # Fetch shift assignment for the current date
            shift_assignment = frappe.db.get_value("Shift Assignment", {
                "employee": employee, 
                "docstatus": 1, 
                "start_date": ["<=", current_date], 
                "end_date": [">=", current_date]
            }, ["shift_type"])
            
            if shift_assignment:
                shift_type = frappe.get_doc("Shift Type", shift_assignment)
                start_time = shift_type.start_time
                end_time = shift_type.end_time
                
                # Calculate shift duration
                shift_duration = end_time - start_time - timedelta(hours=1)  # Assuming 1 hour break
                total_hours += shift_duration
            
            total_days += 1
        
        current_date += timedelta(days=1)
    
    # Print and return the total required hours
    print(f"Total Required Hours: {total_hours.total_seconds() / 3600} For {employee}")
    total = total_hours.total_seconds() / 3600
    return total

def float_to_hhmmss(hours_float):
    # Extract hours, minutes, and seconds
    hours = int(hours_float)
    minutes = int((hours_float - hours) * 60)
    seconds = int(((hours_float - hours) * 60 - minutes) * 60)
    
    # Format the time as hh:mm:ss
    time_str = f"{hours:02}:{minutes:02}:{seconds:02}"
    return time_str       

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

def adwh(employee, datef, datet):
    x = frappe.db.sql("""
        SELECT COUNT(name) as count,
        leave_type
        FROM `tabAttendance` 
        WHERE employee=%s
        AND attendance_date BETWEEN %s AND %s
        AND leave_type <> "مأمورية ساعات"
        AND docstatus=1
        """, (employee, datef, datet), as_dict=True)
    return x[0].count

def act(employee, datef, datet):
    x = frappe.db.sql("""
        SELECT COUNT(name) as count 
        FROM `tabAttendance` 
        WHERE employee=%s
        AND attendance_date BETWEEN %s AND %s
        AND docstatus=1
        
    """, (employee, datef, datet), as_dict=True)
    return x[0].count
