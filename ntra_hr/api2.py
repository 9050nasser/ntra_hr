import frappe

@frappe.whitelist(allow_guest=True)
def delete_all():
    x = frappe.db.get_all("Shift Assignment", fields="name")

    for y in x:
        frappe.delete_doc("Shift Assignment", y.name)

    return "test okay"


@frappe.whitelist(allow_guest=True)
def update():
    checkins = frappe.db.get_all("Employee Checkin", fields="name")
    
    for checkin in checkins:
        doc = frappe.get_doc("Employee Checkin", checkin.name)
        
        # Fetch the employee status
        employee_status = frappe.db.get_value("Employee", doc.employee, "status")
        
        # Check if the employee is active
        if employee_status == "Active":
            doc.shift = "شيفت 7 ساعات"
            doc.save()
        else:
            pass
    
    return "Update completed"
