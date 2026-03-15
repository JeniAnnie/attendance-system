from flask import Blueprint, render_template, request, redirect, jsonify, flash, send_file
from models.attendance_model import db, Attendance, Employee
from datetime import datetime, date, timedelta
from sqlalchemy import func, extract
import pandas as pd
import io

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/admin")
def admin_dashboard():
    """Admin dashboard with employee management and reports"""
    employees = Employee.query.all()
    today = date.today()

    # Today's attendance summary
    today_attendance = Attendance.query.filter(func.date(Attendance.date) == today).all()
    present_count = len([a for a in today_attendance if a.status in ["Present", "Late"]])
    late_count = len([a for a in today_attendance if a.status == "Late"])
    early_leave_count = len([a for a in today_attendance if a.status == "Early Leave"])

    return render_template("admin.html",
                         employees=employees,
                         present_count=present_count,
                         late_count=late_count,
                         early_leave_count=early_leave_count,
                         total_employees=len(employees),
                         today=today)

@admin_bp.route("/admin/employee/add", methods=["POST"])
def add_employee():
    """Add new employee"""
    try:
        emp_id = request.form["emp_id"]
        emp_name = request.form["emp_name"]
        department = request.form["department"]
        work_type = request.form["work_type"]

        # Check if employee already exists
        existing = Employee.query.filter_by(emp_id=emp_id).first()
        if existing:
            flash(f"Employee ID {emp_id} already exists!", "error")
            return redirect("/admin")

        employee = Employee(
            emp_id=emp_id,
            emp_name=emp_name,
            department=department,
            work_type=work_type,
            enrolled=False
        )
        db.session.add(employee)
        db.session.commit()

        flash(f"Employee {emp_name} added successfully!", "success")
        return redirect("/admin")

    except Exception as e:
        flash(f"Error adding employee: {str(e)}", "error")
        return redirect("/admin")

@admin_bp.route("/admin/employee/update/<emp_id>", methods=["POST"])
def update_employee(emp_id):
    """Update employee details"""
    try:
        employee = Employee.query.filter_by(emp_id=emp_id).first()
        if not employee:
            flash("Employee not found!", "error")
            return redirect("/admin")

        employee.emp_name = request.form["emp_name"]
        employee.department = request.form["department"]
        employee.work_type = request.form["work_type"]

        db.session.commit()
        flash(f"Employee {employee.emp_name} updated successfully!", "success")
        return redirect("/admin")

    except Exception as e:
        flash(f"Error updating employee: {str(e)}", "error")
        return redirect("/admin")

@admin_bp.route("/admin/employee/delete/<emp_id>", methods=["POST"])
def delete_employee(emp_id):
    """Delete employee"""
    try:
        employee = Employee.query.filter_by(emp_id=emp_id).first()
        if not employee:
            flash("Employee not found!", "error")
            return redirect("/admin")

        # Delete all attendance records for this employee
        Attendance.query.filter_by(emp_id=emp_id).delete()

        db.session.delete(employee)
        db.session.commit()

        flash(f"Employee {employee.emp_name} and all their records deleted!", "success")
        return redirect("/admin")

    except Exception as e:
        flash(f"Error deleting employee: {str(e)}", "error")
        return redirect("/admin")

@admin_bp.route("/admin/reports/daily")
def daily_report():
    """Generate daily attendance report"""
    selected_date = request.args.get('date', date.today().isoformat())
    report_date = date.fromisoformat(selected_date)

    attendance_records = Attendance.query.filter(
        func.date(Attendance.date) == report_date
    ).all()

    # Calculate summary
    total_present = len([r for r in attendance_records if r.status in ["Present", "Late"]])
    total_late = len([r for r in attendance_records if r.status == "Late"])
    total_early_leave = len([r for r in attendance_records if r.status == "Early Leave"])
    total_absent = len(Employee.query.all()) - total_present

    return render_template("daily_report.html",
                         records=attendance_records,
                         report_date=report_date,
                         total_present=total_present,
                         total_late=total_late,
                         total_early_leave=total_early_leave,
                         total_absent=total_absent)

@admin_bp.route("/admin/reports/monthly")
def monthly_report():
    """Generate monthly attendance report"""
    month = int(request.args.get('month', datetime.now().month))
    year = int(request.args.get('year', datetime.now().year))

    # Get all attendance records for the month
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    attendance_records = Attendance.query.filter(
        Attendance.date >= start_date,
        Attendance.date < end_date
    ).all()

    # Group by employee
    employee_reports = {}
    for record in attendance_records:
        emp_id = record.emp_id
        if emp_id not in employee_reports:
            employee_reports[emp_id] = {
                "emp_name": record.emp_name,
                "department": record.department,
                "work_type": record.work_type,
                "total_days": 0,
                "present_days": 0,
                "late_days": 0,
                "early_leave_days": 0,
                "total_hours": 0
            }

        employee_reports[emp_id]["total_days"] += 1
        if record.status in ["Present", "Late"]:
            employee_reports[emp_id]["present_days"] += 1
        if record.status == "Late":
            employee_reports[emp_id]["late_days"] += 1
        if record.status == "Early Leave":
            employee_reports[emp_id]["early_leave_days"] += 1
        if record.total_hours:
            employee_reports[emp_id]["total_hours"] += record.total_hours

    return render_template("monthly_report.html",
                         employee_reports=employee_reports,
                         month=month,
                         year=year)

@admin_bp.route("/admin/export/daily/<date_str>")
def export_daily_report(date_str):
    """Export daily attendance report to Excel"""
    try:
        report_date = date.fromisoformat(date_str)

        attendance_records = Attendance.query.filter(
            func.date(Attendance.date) == report_date
        ).all()

        # Create DataFrame
        data = []
        for record in attendance_records:
            data.append({
                "Employee ID": record.emp_id,
                "Employee Name": record.emp_name,
                "Department": record.department,
                "Work Type": record.work_type,
                "Status": record.status,
                "Attendance Type": record.attendance_type,
                "Check In": record.check_in,
                "Check Out": record.check_out,
                "Total Hours": record.total_hours,
                "Date": record.date.strftime("%Y-%m-%d")
            })

        df = pd.DataFrame(data)

        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Daily Attendance', index=False)

        output.seek(0)

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'attendance_report_{date_str}.xlsx'
        )

    except Exception as e:
        flash(f"Error exporting report: {str(e)}", "error")
        return redirect("/admin")

@admin_bp.route("/admin/export/monthly/<int:year>/<int:month>")
def export_monthly_report(year, month):
    """Export monthly attendance report to Excel"""
    try:
        # Get all attendance records for the month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        attendance_records = Attendance.query.filter(
            Attendance.date >= start_date,
            Attendance.date < end_date
        ).all()

        # Group by employee
        employee_reports = {}
        for record in attendance_records:
            emp_id = record.emp_id
            if emp_id not in employee_reports:
                employee_reports[emp_id] = {
                    "emp_name": record.emp_name,
                    "department": record.department,
                    "work_type": record.work_type,
                    "total_days": 0,
                    "present_days": 0,
                    "late_days": 0,
                    "early_leave_days": 0,
                    "total_hours": 0
                }

            employee_reports[emp_id]["total_days"] += 1
            if record.status in ["Present", "Late"]:
                employee_reports[emp_id]["present_days"] += 1
            if record.status == "Late":
                employee_reports[emp_id]["late_days"] += 1
            if record.status == "Early Leave":
                employee_reports[emp_id]["early_leave_days"] += 1
            if record.total_hours:
                employee_reports[emp_id]["total_hours"] += record.total_hours

        # Create DataFrame
        data = []
        for emp_id, report in employee_reports.items():
            data.append({
                "Employee ID": emp_id,
                "Employee Name": report["emp_name"],
                "Department": report["department"],
                "Work Type": report["work_type"],
                "Total Working Days": report["total_days"],
                "Present Days": report["present_days"],
                "Late Days": report["late_days"],
                "Early Leave Days": report["early_leave_days"],
                "Total Hours": round(report["total_hours"], 2),
                "Attendance Percentage": round((report["present_days"] / report["total_days"]) * 100, 2) if report["total_days"] > 0 else 0
            })

        df = pd.DataFrame(data)

        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Monthly Attendance', index=False)

        output.seek(0)

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'monthly_attendance_report_{year}_{month}.xlsx'
        )

    except Exception as e:
        flash(f"Error exporting report: {str(e)}", "error")
        return redirect("/admin")  