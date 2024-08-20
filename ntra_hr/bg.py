import frappe


@frappe.whitelist()
def trigger_employee_checkin_validate():
    employee_checkin = frappe.db.get_all("Employee Checkin", filters={"shift": ["is", "not set"]}, fields=["name", "employee"])
    for checkin in employee_checkin:
        if frappe.db.get_value("Employee", checkin.employee, "status") != "Active":
            continue
        doc = frappe.get_doc("Employee Checkin", checkin.name)
        # generate random string
        doc.custom_employee_name_ar = frappe.generate_hash(length=8)
        doc.save()
        frappe.db.commit()
        print(f"Employee Checkin Validated: {doc.name}")
    return "Employee Checkin Validated"



@frappe.whitelist()
def trigger_leave_application_validate_submit():
    leave_application = frappe.db.get_all("Leave Application", filters={"docstatus": ["!=", "1"]}, fields=["name", "employee"])
    for checkin in leave_application:
        if frappe.db.get_value("Employee", checkin.employee, "status") != "Active":
            continue
        try:
            doc = frappe.get_doc("Leave Application", checkin.name)
            # generate random string
            doc.description = frappe.generate_hash(length=8)
            doc.status = "Approved"
            doc.save()
            doc.submit()
            frappe.db.commit()
            print(f"Leave Application Validated: {doc.name}")
        except Exception as e:
            print(f"Error: {e}")
    return "Leave Application Validated"

@frappe.whitelist()
def cancel_attendance():
    leave_application = frappe.db.get_all("Attendance", filters={"status": ["!=", "On Leave"], "docstatus":1}, fields=["name", "employee"])
    for name in leave_application:
        try:
            doc = frappe.get_doc("Attendance", name.name)
            # generate random string
            doc.cancel()
            # doc.delete()
            frappe.db.commit()
            print(f"Cancel Attendance: {doc.name}")
        except Exception as e:
            print(f"Error: {e}")
    return "Attendance Cancelled"

@frappe.whitelist()
def delete_attendance():
    leave_application = frappe.db.get_all("Attendance", filters={"status": ["!=", "On Leave"], "docstatus":2}, fields=["name", "employee"])
    for name in leave_application:
        try:
            doc = frappe.get_doc("Attendance", name.name)
            # generate random string
            # doc.cancel()
            doc.delete()
            frappe.db.commit()
            print(f"Delete Attendance: {doc.name}")
        except Exception as e:
            print(f"Error: {e} {doc.name}")
    return "Attendance Deleted"

    