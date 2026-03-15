from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, time
import pickle  # For storing face encodings
import numpy as np

db = SQLAlchemy()

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100))
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    face_encoding = db.Column(db.LargeBinary)  # Pickled numpy array for face encoding
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    employee = db.relationship('Employee', backref=db.backref('attendances', lazy=True))
    date = db.Column(db.Date, default=datetime.utcnow().date)
    check_in = db.Column(db.String(10), nullable=True)  # Store as "HH:MM" format
    check_out = db.Column(db.String(10), nullable=True)  # Store as "HH:MM" format
    status = db.Column(db.String(20), default='Pending')  # 'Present', 'Late', 'Absent'
    attendance_type = db.Column(db.String(50), default='Onsite')  # Onsite, WFH, Field
    department = db.Column(db.String(100))  # Store department at time of attendance
    total_hours = db.Column(db.Float, default=0.0)

# Helper function to calculate status and hours
def calculate_attendance_status(check_in_time):
    cutoff_correct = time(10, 15)  # 10:15 AM correct
    cutoff_late = time(10, 16)     # After 10:16 late

    if check_in_time.time() <= cutoff_correct:
        return 'Present'
    elif check_in_time.time() > cutoff_late:
        return 'Late'
    return 'Pending'

def calculate_total_hours(check_in, check_out):
    if check_in and check_out:
        delta = check_out - check_in
        return round(delta.total_seconds() / 3600, 2)
    return 0.0  