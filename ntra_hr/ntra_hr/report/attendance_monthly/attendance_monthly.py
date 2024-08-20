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
        {"label": _("Shift Duration"), "fieldname": "shift_duration", "fieldtype": "Time", "width": 180},
        {"label": _("Time Difference"), "fieldname": "time_diff", "fieldtype": "Data", "width": 80, "hidden": 1},
        {"label": _("Working Hours"), "fieldname": "working_hours", "fieldtype": "Time", "width": 80},
        {"label": _("Valid In/Valid Out"), "fieldname": "valid_in_valid_out", "fieldtype": "Time", "width": 80},
        {"label": _("Leave Type"), "fieldname": "leave_type", "fieldtype": "Link", "options": "Leave Type", "width": 150},
        {"label": _("Holiday List"), "fieldname": "holiday_list", "fieldtype": "Link", "options": "Holiday List", "width": 120},
        {"label": _("Hasala"), "fieldname": "hasala", "fieldtype": "Data"},
        {"label": _("actual dayes without holidays"), "fieldname": "adwh", "fieldtype": "Data", "hidden": 1},
        {"label": _("actual dayes"), "fieldname": "act", "fieldtype": "Data", "hidden": 1},
        {"label": _("att_days"), "fieldname": "att_days", "fieldtype": "Data", "hidden": 1},
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
        0 as shift_duration,        
        COALESCE(att.working_hours, leave_app.custom_absence_time) as working_hours,
        CASE WHEN att.leave_type IS NOT NULL THEN '' ELSE att.leave_type END AS leave_type,
        emp.holiday_list,
        CASE WHEN checkin.time IS NOT NULL THEN MIN(checkin.time) ELSE CAST(CONCAT(att.attendance_date, ' ', CAST('00:00:00' AS TIME)) AS DATETIME) END as check_in,
        CASE WHEN checkin.time IS NOT NULL THEN MAX(checkin.time) ELSE CAST(CONCAT(att.attendance_date, ' ', CAST('00:00:00' AS TIME)) AS DATETIME) END as check_out,
        0 as sort_order -- Add a sort order for regular attendance
    FROM `tabAttendance` att
    LEFT JOIN `tabLeave Application` leave_app ON att.leave_application = leave_app.name
    JOIN `tabEmployee` emp ON att.employee = emp.name
    LEFT JOIN `tabEmployee Checkin` checkin ON att.employee = checkin.employee AND DATE(checkin.time) = att.attendance_date
    WHERE att.docstatus = 1 {condition_str}
    AND att.status IN ("Present", "Absent")
    GROUP BY att.name

    UNION ALL

    SELECT
        att.name as attendance,
        leave_app.name AS leave_app,
        att.attendance_date,
        att.employee as employee,
        att.employee_name,
        att.shift,
        0 as shift_duration,        
        COALESCE(att.working_hours, leave_app.custom_absence_time) as working_hours,
        att.leave_type AS leave_type,
        emp.holiday_list,
        CASE WHEN leave_app.custom_f_time = 0 THEN CAST(CONCAT(att.attendance_date, ' ', CAST('00:00:00' AS TIME)) AS DATETIME) ELSE leave_app.custom_f_time END as check_in,
        CASE WHEN leave_app.custom_t_time = 0 THEN CAST(CONCAT(att.attendance_date, ' ', CAST('00:00:00' AS TIME)) AS DATETIME) ELSE leave_app.custom_t_time END as check_out,
        1 as sort_order -- Add a sort order for regular attendance
    FROM `tabAttendance` att
    LEFT JOIN `tabLeave Application` leave_app ON att.leave_application = leave_app.name
    JOIN `tabEmployee` emp ON att.employee = emp.name
    LEFT JOIN `tabEmployee Checkin` checkin ON att.employee = checkin.employee AND DATE(checkin.time) = att.attendance_date
    WHERE att.docstatus = 1  {condition_str}
    AND att.status="On Leave"
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
        0 AS working_hours,
        `tabHoliday`.description as leave_type,
        NULL as holiday_list,
        CAST(CONCAT(tabHoliday.holiday_date, ' ', CAST('00:00:00' AS TIME)) AS DATETIME) as check_in,
        CAST(CONCAT(tabHoliday.holiday_date, ' ', CAST('00:00:00' AS TIME)) AS DATETIME) as check_out,
        2 as sort_order
    FROM `tabHoliday`
    WHERE `tabHoliday`.parent = '{holiday_list}' AND `tabHoliday`.holiday_date BETWEEN '{datef}' AND '{datet}'

) AS combined_results

ORDER BY combined_results.attendance_date, combined_results.sort_order;

    """, as_dict=True)  
    response = []
    list = []
    total_valid_in_valid_out = timedelta()
    total_mohtsba = timedelta()
    act = timedelta()
    for row in result:
        shift = frappe.db.get_value("Shift Type", row.shift, ["custom_shift_hours", "name"], as_dict=1)
        leave_type_duplication = frappe.db.get_value("Leave Type", row.leave_type, "custom_allow_duplication")
        shift_duration = shift.custom_shift_hours if leave_type_duplication == 0 or not row.leave_type else timedelta(hours=0)
        shift_row = row.shift if row.leave_type is None else ""
        check_in_time = row.check_in
        check_out_time = row.check_out
        valid_in_valid_out = check_out_time - check_in_time
        working_hours = get_working_hours(row.employee, row.check_in, row.check_out, row.leave_app, shift.name if shift else "", shift_duration)
        response.append({
            "attendance": row.attendance,
            "leave_app": row.leave_app,
            "attendance_date": row.attendance_date,
            "employee": row.employee,
            "employee_name": row.employee_name,
            "shift": shift_row,
            "shift_duration": shift_duration if row.leave_type !="إجازة رعاية طفل" else timedelta(hours=0),
            "check_in": row.check_in,
            "check_out": row.check_out,
            "time_diff": 0,
            "working_hours": working_hours,
            "valid_in_valid_out": valid_in_valid_out,
            "leave_type": row.leave_type,
            "holiday_list": row.holiday_list,
            "hasala": calculate_hasala(employee, row.check_out, row.check_in, row.leave_type),
        })
        total_valid_in_valid_out += valid_in_valid_out if not row.leave_type else timedelta(hours=0)
        total_mohtsba += working_hours
        act += shift_duration

    # Update the single values in the response list to reflect the total
    for item in response:
        item["th"] = total_valid_in_valid_out
        item["department"] = frappe.db.get_value("Employee", employee, "department")
        item["total_mohtsba"] = total_mohtsba
        item["act"] = act
        item["adwh"] = adwh(employee, datef, datet)
        # item["adwh"] = abs(days_between_dates(datef, datet) - get_holidays_days_count(holiday_list, datef, datet))
        item["att_days"] = att_days(employee, datef, datet)
        item["percent"] = percent(total_mohtsba, act)
    return response

def calculate_hasala(employee, check_out, check_in, leave_type):
    shift_type1 = frappe.get_all("Shift Assignment", filters={"employee": employee}, fields="shift_type")
    if not shift_type1:
        return timedelta(hours=0)
    is_hasala = frappe.db.get_value("Leave Type", leave_type, "custom_calculate_after_work_time")
    shift_type2 = frappe.get_doc("Shift Type", shift_type1[0].shift_type)
    shift_from = shift_type2.start_time
    shift_to = shift_type2.end_time
    if convert_datetime_to_timedelta(check_out) > shift_to and is_hasala == 1:
        return convert_datetime_to_timedelta(check_out) - shift_to - timedelta(hours=1)
    else:
        return timedelta(hours=0)

def get_working_hours(employee, check_in, check_out, leave_app=None, shift=None, duration=None):
    if not shift:
        return timedelta(hours=0, minutes=0, seconds=0)
    # for shiftx in shift_type12:
    shift_type2 = frappe.get_doc("Shift Type", shift)
    shift_from = shift_type2.start_time
    shift_to = shift_type2.end_time
    checkin = convert_datetime_to_timedelta(check_in)
    checkout = convert_datetime_to_timedelta(check_out)
    actual_in = checkin
    actual_out = checkout

    if leave_app:
        return timedelta(hours=0)
    elif checkout > timedelta(hours=7):
        return shift_type2.custom_shift_hours
    elif checkin == timedelta(hours=0) or checkout == timedelta(hours=0):
        return timedelta(hours=0)
    elif checkin == timedelta(hours=0):
        return timedelta(hours=0)
    elif actual_in > timedelta(hours=9):
        return shift_to - actual_in
    elif shift_to - shift_from > timedelta(hours=7) and shift!="شيفت 5 ساعات عمل رمضان":
        return timedelta(hours=7, minutes=0, seconds=0)
    elif not shift and actual_in and actual_out:
        return checkout - checkin
    elif not leave_app:
        return shift_type2.custom_shift_hours
    
        
    if actual_in > timedelta(hours=9) and shift=="شيفت 5 ساعات عمل رمضان":
        return shift_to - actual_in
    elif checkout > timedelta(hours=7):
        return shift_type2.custom_shift_hours
    elif shift_to - shift_from > timedelta(hours=5) and shift=="شيفت 5 ساعات عمل رمضان":
        return timedelta(hours=5, minutes=0, seconds=0)
    elif leave_app:
        return checkout - checkin
    if leave_app:
        return checkout - checkin
    else:
        return checkout - checkin

def convert_datetime_to_timedelta(time):
    check = frappe.utils.data.get_datetime(time).time()
    return timedelta(hours=check.hour, minutes=check.minute, seconds=check.second)

def adwh(employee, datef, datet):
    leave_types = frappe.db.get_all("Leave Type", filters={'custom_calculate_after_work_time':1, 'custom_allow_duplication':1}, fields=["name"], pluck="name")
    leave_types.append("راحة")
    x = frappe.db.sql("""
        SELECT COUNT(name) as count 
        FROM `tabAttendance` 
        WHERE employee=%s
        AND attendance_date BETWEEN %s AND %s
        AND docstatus=1
        AND (leave_type IS NULL OR leave_type NOT IN %s)
        
    """, (employee, datef, datet, tuple(leave_types)), as_dict=True)
    return x[0].count

def att_days(employee, datef, datet):
    x = frappe.db.sql("""
        SELECT COUNT(name) as count 
        FROM `tabAttendance` 
        WHERE employee=%s
        AND attendance_date BETWEEN %s AND %s
        AND docstatus=1
        AND status = "Present"
        
    """, (employee, datef, datet), as_dict=True)
    return x[0].count

def percent(total_mohtsba, act):
    if ((total_mohtsba / act)*100) > 100:
        return 100
    else:
        return round(((total_mohtsba / act)*100), 2)
    
def days_between_dates(datef, datet):
    date1 = datetime.strptime(datef, "%Y-%m-%d")
    date2 = datetime.strptime(datet, "%Y-%m-%d")

    # Calculate the difference between the dates
    delta = date2 - date1

    # Get the number of days
    days_between = delta.days +1
    print(days_between)
    return days_between

def get_holidays_days_count(holiday_list, datef, datet):
    count = frappe.db.sql("""
            select count(name) as count 
            from `tabHoliday` 
            where parent=%s 
            and holiday_date between %s and %s
        """, (holiday_list, datef, datet), as_dict=True)
    print(holiday_list)
    print(count[0].count)
    return count[0].count