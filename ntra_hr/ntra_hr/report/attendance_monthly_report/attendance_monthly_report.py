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
        {"label": _("Time Difference"), "fieldname": "time_diff", "fieldtype": "Time", "width": 80, "hidden": 1},
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
    datef = filters.get("from_date")
    datet = filters.get("to_date")
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
        att.shift,
        NULL as shift_duration,        
        COALESCE(att.working_hours, leave_app.custom_absence_time) as working_hours,
        CASE WHEN att.leave_type IS NOT NULL THEN '' ELSE att.leave_type END AS leave_type,
        emp.holiday_list,
        MIN(checkin.time) as check_in,
        MAX(checkin.time) as check_out,
        checkin.shift as chshift,
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
        att.shift,
        NULL as shift_duration,
        TIMEDIFF(leave_app.custom_t_time, leave_app.custom_f_time) as working_hours,
        att.leave_type as leave_type,
        emp.holiday_list,
        leave_app.custom_f_time as check_in,
        leave_app.custom_t_time as check_out,
        checkin.shift as chshift,
        1 as sort_order
    FROM `tabAttendance` att
    LEFT JOIN `tabLeave Application` leave_app ON att.leave_application = leave_app.name
    JOIN `tabEmployee` emp ON att.employee = emp.name
    LEFT JOIN `tabEmployee Checkin` checkin ON att.employee = checkin.employee AND DATE(checkin.time) = att.attendance_date
    LEFT JOIN `tabLeave Type` lt ON att.leave_type = lt.name
    WHERE att.docstatus = 1 AND att.leave_type IS NOT NULL {condition_str}
    GROUP BY att.name

    UNION ALL

    SELECT
        NULL as attendance,
        NULL as leave_app,
        `tabHoliday`.holiday_date as attendance_date,
        NULL as employee,
        NULL as employee_name,
        NULL as shift,
        0 as shift_duration,
        0 as working_hours,
        `tabHoliday`.description as leave_type,
        NULL as holiday_list,
        NULL as check_in,
        NULL as check_out,
        NULL as chshift,
        2 as sort_order
    FROM `tabHoliday`
    WHERE `tabHoliday`.parent = '{holiday_list}' AND `tabHoliday`.holiday_date BETWEEN '{datef}' AND '{datet}'


) AS combined_results

ORDER BY combined_results.attendance_date, combined_results.sort_order;

    """, as_dict=True)
        
    total_working_hours = timedelta()
    shift_duration = timedelta()
    total_shift_duration = timedelta()
    total_mohtsba = timedelta()
    tt = timedelta()
    response = []
    for row in result:
        mamorya = frappe.db.get_all("Leave Type", filters={"custom_calculate_after_work_time": 0}, pluck="name")

        shift = frappe.db.get_value("Shift Type", row.shift, ["start_time", "end_time", "name"], as_dict=1)
        
        shift2 = frappe.db.get_value("Attendance", row.attendance, "shift")
        shift_duration = timedelta()
        if shift and row.holiday_list and not row.leave_type:
            shift_duration = shift.end_time - shift.start_time - timedelta(hours=1)
        elif row.leave_type in mamorya:
            shift_duration = shift.end_time - shift.start_time - timedelta(hours=1)
        chshift = frappe.db.get_value("Shift Type", row.chshift, ["start_time", "end_time", "name"], as_dict=1)
        chshift_duration = timedelta()
        if chshift and row.holiday_list and not row.leave_app:
            chshift_duration = chshift.end_time - chshift.start_time - timedelta(hours=1)

        
        
        time_diff = float_to_hours_minutes(time_diff_in_hours(row.check_in, row.check_out) if row.check_in and row.check_out else 0)
        working_hours = get2_working_hours(row.employee, row.check_in, row.check_out, row.leave_app, shift.name if shift else "", shift_duration)
        time_deltas = convert_to_timedelta(working_hours)
        tt += time_deltas
        wh = convert_to_timedelta(working_hours) if convert_to_timedelta(working_hours) and not row.leave_app else timedelta(hours=0)
        valid_in_valid_out = get_valid_in_valid_out(row.check_in, row.check_out)
        total_working_hours += convert_str_to_timedelta(float_to_hours_minutes(valid_in_valid_out))
        total_shift_duration += shift_duration if shift_duration else timedelta(hours=0) 
        percent = calc_percent(convert_str_to_float(convert_sec_to_hm(tt.total_seconds())), convert_str_to_float(convert_sec_to_hm(total_shift_duration.total_seconds())))
        response.append({
            "attendance": row.attendance,
            "leave_app": row.leave_app,
            "attendance_date": row.attendance_date,
            "employee": row.employee, #delete
            "employee_name": row.employee_name,
            "shift": row.shift,
            "shift_duration": shift_duration if row.shift else timedelta(hours=0),
            "check_in": row.check_in,
            "check_out": row.check_out,
            "time_diff": time_diff,
            "working_hours": working_hours if shift else convert_checkin_to_time(row.check_out) - convert_checkin_to_time(row.check_in),
            "valid_in_valid_out": float_to_hours_minutes(valid_in_valid_out),
            "leave_type": row.leave_type,
            "holiday_list": row.holiday_list,
            "department": frappe.db.get_value("Employee", employee, "department"),
            "hasala": calculate_hasala(row.employee, row.check_out, row.check_in, row.leave_type),
            "adwh": adwh(employee, datef, datet),
            "act": act(employee, datef, datet),
            "days_bet": convert_sec_to_hm(total_shift_duration.total_seconds()) if convert_sec_to_hm(total_shift_duration.total_seconds()) and not row.leave_app else '',
            "th": convert_sec_to_hm(total_working_hours.total_seconds()),
            "total_mohtsba": convert_sec_to_hm(tt.total_seconds()),
            "percent": round(percent, 2)
        })
        
        # print(convert_str_to_float(convert_sec_to_hm(tt.total_seconds())) / convert_str_to_float(convert_sec_to_hm(total_shift_duration.total_seconds())) * 100)
    return response
def calc_percent(one, two):
    result = one / two
    return result *100
def convert_str_to_float(time_str):
    hours, minutes = map(int, time_str.split(':'))

    total_minutes = hours * 60 + minutes

    total_minutes_float = float(total_minutes)

    return total_minutes_float
def convert_sec_to_hm(total_seconds):
    hours = int(total_seconds) // 3600
    minutes = int((total_seconds % 3600)) // 60
    return f"{hours:02}:{minutes:02}"

def convert_str_to_timedelta(time):
    time = datetime.strptime(time, "%H:%M")
    time_delta = timedelta(hours=time.hour, minutes=time.minute)

    return time_delta

def convert_to_timedelta(working_hours):
    if working_hours is None:
        # Handle the case where working_hours is None
        # You can either return a default value or raise an exception
        # Here, I'm choosing to return a default timedelta of 0
        return timedelta(hours=0, minutes=0, seconds=0)
    h, m, s = map(int, working_hours.split(':'))
    return timedelta(hours=h, minutes=m, seconds=s)



def get_onleave_days(employee, datef, datet):
    on_leave_days = frappe.db.sql("""
        select count(att.name) as count 
        from `tabAttendance` att
        left join `tabLeave Type` lt on att.leave_type = lt.name
        where att.employee= %s
        and att.attendance_date between %s and %s
        and att.status='On Leave' and att.docstatus=1
        and att.leave_type <> 'مأمورية ساعات'
    """, (employee, datef, datet), as_dict=True)
    return on_leave_days[0].count

def get_holidays_days_count(holiday_list, datef, datet):
    count = frappe.db.sql("""
            select count(name) as count 
            from `tabHoliday` 
            where parent=%s 
            and holiday_date between %s and %s
        """, (holiday_list, datef, datet), as_dict=True)
    return count[0].count
    

def count_days_diff(datef, datet):
    date1_str = datef
    date2_str = datet

    # Convert the strings to datetime objects
    date1 = datetime.strptime(date1_str, "%Y-%m-%d")
    date2 = datetime.strptime(date2_str, "%Y-%m-%d")

    # Calculate the difference between the two dates
    difference = date2 - date1

    # Get the number of days
    days_between = difference.days
    return days_between

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
