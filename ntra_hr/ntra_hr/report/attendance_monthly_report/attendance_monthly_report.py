import frappe
from frappe import _
from frappe.query_builder.functions import Date

Filters = frappe._dict


def execute(filters: Filters = None) -> tuple:
    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns() -> list[dict]:
    return [
        {
            "label": _("Attendance"),
            "fieldname": "attendance",
            "fieldtype": "Link",
            "options": "Attendance",
            "width": 180, 
        },
        {
            "label": _("Leave Application"),
            "fieldname": "leave_app",
            "fieldtype": "Link",
            "options": "Leave Application",
            "width": 180,
        },
        {
            "label": _("Attendance Date"),
            "fieldname": "attendance_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 240,
        },
        {
            "label": _("Employee Name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "hidden": 1,
        },
        {
            "label": _("Check In"),
            "fieldname": "check_in",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Check Out"),
            "fieldname": "check_out",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Time Difference"),
            "fieldname": "time_diff",
            "fieldtype": "Float",
            "width": 80,
        },
        {
            "label": _("Working Hours"),
            "fieldname": "working_hours",
            "fieldtype": "Float",
            "width": 80,
        },
        {
            "label": _("Leave Type"),
            "fieldname": "leave_type",
            "fieldtype": "Link",
            "options": "Leave Type",
            "width": 150,
        },
        {
            "label": _("Holiday List"),
            "fieldname": "holiday_list",
            "fieldtype": "Link",
            "options": "Holiday List",
            "width": 150,
        },
    ]


def get_data(filters: Filters) -> list[dict]:

    conditions = ""
    if filters.get("from_date"):
        conditions += f" AND att.attendance_date >= '{filters.get('from_date')}'"
    if filters.get("to_date"):
        conditions += f" AND att.attendance_date <= '{filters.get('to_date')}'"
    if filters.get("employee"):
        conditions += f" AND att.employee = '{filters.get('employee')}'"

    result = frappe.db.sql("""
    SELECT	
                        att.name as attendance,
                        leave_app.name as leave_app,
                        att.attendance_date,
                        att.employee,
                        att.employee_name,
                        ifnull(att.working_hours, leave_app.custom_absence_time) as working_hours,
                        att.leave_type,
                        emp.holiday_list
                        FROM `tabAttendance` att
                        left JOIN `tabLeave Application` leave_app ON att.leave_application = leave_app.name		
                        JOIN `tabEmployee` emp ON att.employee = emp.name			
                        where att.docstatus = 1
                        {conditions}
    """.format(conditions=conditions), as_dict=True)
    frappe.msgprint(str(result))
    response = []
    for row in result:
        check_in = get_check_in(row.name, row.attendance_date, row.employee)
        check_out = get_check_out(row.name, row.attendance_date, row.employee)
        working_hours = get_working_hours(row.employee, row.attendance_date)
        response.append({
            "attendance": row.attendance,
            "leave_app": row.leave_app,
            "attendance_date": row.attendance_date,
            "employee": row.employee,
            "employee_name": row.employee_name,
            "check_in": check_in,
            "check_out": check_out,
            "time_diff": time_diff_in_hours(check_in, check_out) if check_in and check_out else 0,
            "working_hours": working_hours,
            "leave_type": row.leave_type,
            "holiday_list": row.holiday_list,
        })


    return response
import datetime

def get_working_hours(employee, attendance_date):
    emp = frappe.get_doc("Employee", employee)
    if emp.custom_emp_type:
        return 7
    if emp.custom_hour_count:
        return 6
    date_one = datetime.date(2024, 3, 11)  # replace with your actual date
    date_two = datetime.date(2024, 4, 10)  # replace with your actual date

    if date_one <= attendance_date <= date_two:
        return 5
    
    return 7

def get_check_in(attendance, attendance_date, employee):
    employee_checkin_logs = frappe.get_all("Employee Checkin", filters={"employee": employee, 
                                                                     "time":["between",(attendance_date, attendance_date)]}, fields=["time"], order_by="time")
    frappe.msgprint(str(employee_checkin_logs))
    if not employee_checkin_logs:
        return ""
    # get the first checkin
    return employee_checkin_logs[0].time

def get_check_out(attendance, attendance_date, employee):
    employee_checkin_logs = frappe.get_all("Employee Checkin", filters={"employee": employee, 
                                                                     "time":["between", (attendance_date, attendance_date)]}, fields=["time"], order_by="time DESC")
    if not employee_checkin_logs:
        return ""
    # get the last checkin
    return employee_checkin_logs[0].time
    
def time_diff_in_hours(start, end):
    return round(float((end - start).total_seconds()) / 3600, 2)

def add_total_row(result: list[dict], filters: Filters) -> list[dict]:
    add_total_row = False
    leave_type = filters.get("leave_type")

    if filters.get("employee") and filters.get("leave_type"):
        add_total_row = True

    if not add_total_row:
        if not filters.get("employee"):
            # check if all rows have the same employee
            employees_from_result = list(set([row.employee for row in result]))
            if len(employees_from_result) != 1:
                return result

        # check if all rows have the same leave type
        leave_types_from_result = list(set([row.leave_type for row in result]))
        if len(leave_types_from_result) == 1:
            leave_type = leave_types_from_result[0]
            add_total_row = True

    if not add_total_row:
        return result

    total_row = frappe._dict({"employee": _("Total Leaves ({0})").format(leave_type)})
    total_row["leaves"] = sum((row.get("leaves") or 0) for row in result)

    result.append(total_row)
    return result