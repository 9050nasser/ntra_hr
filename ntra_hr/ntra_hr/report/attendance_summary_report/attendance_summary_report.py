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
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee"},
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data"},
        {"label": _("Total WD Without Holidays"), "fieldname": "total_wd", "fieldtype": "Data"},
        {"label": _("Actual Attendance Days"), "fieldname": "actual_att_days", "fieldtype": "Data"},
        {"label": _("Days Difference"), "fieldname": "days_diff", "fieldtype": "Data"},
        {"label": _("Total Required Hours"), "fieldname": "total_req_hours", "fieldtype": "Data"},
        {"label": _("Total Actual Hours"), "fieldname": "total_actual_hours", "fieldtype": "Data"},
        {"label": _("Hours Differnce"), "fieldname": "hours_diff", "fieldtype": "Data"},
        {"label": _("Day Average"), "fieldname": "day_avg", "fieldtype": "Data"},
        {"label": _("Attendance Percentage"), "fieldname": "att_perc", "fieldtype": "Data"},
        
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
    if filters.get("from_emp") and filters.get("to_emp"):
        conditions.append(f"att.employee BETWEEN '{filters.get('from_emp')}' AND '{filters.get('to_emp')}'")
    datef = filters.get("from_date")
    datet = filters.get("to_date")
    from_emp = filters.get("from_emp")
    to_emp = filters.get("to_emp")
    condition_str = " AND ".join(conditions)
    if condition_str:
        condition_str = "AND " + condition_str
    result = frappe.db.sql(f"""
       SELECT
        emp.employee,
        emp.custom_employee_name_ar as employee_name,
        att.shift as shift
		FROM `tabEmployee` emp
        LEFT JOIN `tabAttendance` att ON emp.name = att.employee
		WHERE emp.employee BETWEEN {from_emp} AND {to_emp}
        GROUP BY att.employee
		ORDER BY CAST(emp.employee AS UNSIGNED) ASC;

    """, as_dict=True)
        
    

    response = []
    for row in result:
        mamorya = frappe.db.get_all("Leave Type", filters={"custom_calculate_after_work_time": 0}, pluck="name")
        shift = frappe.db.get_value("Shift Type", row.shift, ["start_time", "end_time", "name"], as_dict=1)
        time_diff = float_to_hours_minutes(time_diff_in_hours(row.check_in, row.check_out) if row.check_in and row.check_out else 0)
        shift2 = frappe.db.get_value("Attendance", row.attendance, "shift")
        shift_duration = timedelta()
        if shift and row.holiday_list and not row.leave_type:
            shift_duration = shift.end_time - shift.start_time - timedelta(hours=1)
        elif row.leave_type in mamorya:
            shift_duration = shift.end_time - shift.start_time - timedelta(hours=1)
        working_hours = get2_working_hours(row.employee, row.check_in, row.check_out, row.leave_app)
        print(working_hours)
        valid_in_valid_out = get_valid_in_valid_out(row.check_in, row.check_out)
        response.append({
            "employee": row.employee,
            "employee_name": row.employee_name,
            "total_wd": act(row.employee, datef, datet),
            "actual_att_days": act(row.employee, datef, datet) - adwh(row.employee, datef, datet),
            "days_diff": adwh(row.employee, datef, datet),
            "total_req_hours": working_hours if shift else convert_checkin_to_time(row.check_out) - convert_checkin_to_time(row.check_in),
            "total_actual_hours": time_diff,
            "hours_diff": 0,
            "day_avg": 0,
            "att_perc": 0,
        })

    return response
def calculate_hasala(employee, check_out, check_in, leave_type):
    shift_type1 = frappe.get_all("Shift Assignment", filters={"employee": employee}, fields="shift_type")
    if not shift_type1:
        return f"{0:02d}:{0:02d}:{0:02d}"
    is_hasala = frappe.db.get_value("Leave Type", leave_type, "custom_calculate_after_work_time")
    shift_type2 = frappe.get_doc("Shift Type", shift_type1[0].shift_type)
    shift_from = shift_type2.start_time
    shift_to = shift_type2.end_time
    if convert_checkin_to_time(check_out) > shift_to and is_hasala == 1:
        return convert_checkin_to_time(check_out) - shift_to
    else:
        return f"{0:02d}:{0:02d}:{0:02d}"

def float_to_hours_minutes(time_diff):
  if isinstance(time_diff, str):
    hours, minutes = time_diff.split(':')
    return int(hours), int(minutes)
  else:
    hours = int(time_diff)
    minutes = int((time_diff - hours) * 60)
    return f"{hours:02d}:{minutes:02d}"

def get_valid_in_valid_out(check_in, check_out):
    if not check_in or not check_out:
        return 0
    return time_diff_in_hours(check_in, check_out)


    
def get2_working_hours(employee, check_in, check_out, leave_app=None, shift=None, duration=None):
    # shift_type1 = frappe.get_all("Shift Assignment", filters={"employee": employee, "docstatus":1}, fields="shift_type")

    # unique_set = {tuple(item.items()) for item in shift_type1}

    # shift_type12 = [dict(item) for item in unique_set]
    
    if not shift:
        return f"{0:02d}:{0:02d}:{0:02d}"
    # for shiftx in shift_type12:
    shift_type2 = frappe.get_doc("Shift Type", shift)
    shift_from = shift_type2.start_time
    shift_to = shift_type2.end_time
    checkin = convert_checkin_to_time(check_in)
    checkout = convert_checkin_to_time(check_out)
    actual_in = checkin
    actual_out = checkout

    if leave_app:
        return convert_to_hh(checkout - checkin)
    elif actual_in > timedelta(hours=9):
        return convert_to_hh(shift_to - actual_in)
    elif shift_to - shift_from > timedelta(hours=7) and shift!="شيفت 5 ساعات عمل رمضان":
        return f"{7:02d}:{0:02d}:{0:02d}"
    elif not shift and actual_in and actual_out:
        return convert_to_hh(checkout - checkin)
    
        
    if actual_in > timedelta(hours=9) and shift=="شيفت 5 ساعات عمل رمضان":
        return convert_to_hh(shift_to - actual_in)
    elif shift_to - shift_from > timedelta(hours=5) and shift=="شيفت 5 ساعات عمل رمضان":
        return f"{5:02d}:{0:02d}:{0:02d}"
    elif leave_app:
        return convert_to_hh(checkout - checkin)
    if leave_app:
        return convert_to_hh(checkout - checkin)
    else:
        return convert_to_hh(checkout - checkin)

    
def convert_to_hh(time2):
    check2 = time2.total_seconds()
    hours = int(check2 // 3600)
    minutes = int((check2 % 3600) // 60)
    seconds = int(check2 % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def convert_checkin_to_time(time):
    check = frappe.utils.data.get_datetime(time).time()
    return timedelta(hours=check.hour, minutes=check.minute, seconds=check.second)

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
