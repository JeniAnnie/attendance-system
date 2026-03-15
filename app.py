
# GoDigital Attendance System - Connected Backend
# Run with: python app.py
# Visit: http://localhost:5000

import os
import json
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, Blueprint
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config.from_object('config')
app.secret_key = "super-secret-key-change-this-in-production-2026"

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Define models before importing other modules
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
    employee = db.relationship('Employee', backref=db.backref('attendance', lazy=True))
    date = db.Column(db.Date, default=date.today)
    check_in = db.Column(db.String(10), nullable=True)  # Store as "HH:MM" format
    check_out = db.Column(db.String(10), nullable=True)  # Store as "HH:MM" format
    status = db.Column(db.String(20), default='Pending')  # 'Present', 'Late', 'Absent'
    attendance_type = db.Column(db.String(20))  # 'WFH', 'Field', 'Onsite'
    department = db.Column(db.String(100))
    total_hours = db.Column(db.Float, default=0.0)

# ────────────────────────────────────────────────
#   DATA MANAGEMENT FUNCTIONS
# ────────────────────────────────────────────────

def init_default_employees():
    """Initialize with default test employees if database is empty"""
    if Employee.query.count() == 0:
        default_employees = [
            Employee(
                emp_id="EMP001",
                name="John Doe",
                email="john@company.com",
                department="Engineering",
                password_hash=generate_password_hash("password123"),
                is_admin=False
            ),
            Employee(
                emp_id="EMP002",
                name="Jane Smith",
                email="jane@company.com",
                department="Finance",
                password_hash=generate_password_hash("password123"),
                is_admin=True
            ),
            Employee(
                emp_id="EMP003",
                name="Bob Johnson",
                email="bob@company.com",
                department="HR",
                password_hash=generate_password_hash("password123"),
                is_admin=False
            )
        ]
        db.session.add_all(default_employees)
        db.session.commit()

# Initialize database on app startup
@app.before_request
def init_db():
    """Initialize database tables on first request"""
    if not hasattr(app, 'db_initialized'):
        db.create_all()
        init_default_employees()
        app.db_initialized = True

# ────────────────────────────────────────────────
#   ATTENDANCE HELPER FUNCTIONS
# ────────────────────────────────────────────────

def get_attendance_status(check_in_time_str):
    """
    Determine if attendance is on-time or late
    On-time: 10:00 to 10:15
    Late: 10:16 onwards
    """
    try:
        check_in_hour, check_in_minute = map(int, check_in_time_str.split(':'))
        
        # Convert to minutes for easier comparison
        check_in_minutes = check_in_hour * 60 + check_in_minute
        on_time_limit = 10 * 60 + 15  # 10:15 in minutes
        
        if check_in_minutes <= on_time_limit:
            return "On-Time"
        else:
            return "Late"
    except:
        return "Unknown"

def calculate_total_hours(check_in_str, check_out_str):
    """Calculate total hours worked between check-in and check-out"""
    try:
        check_in = datetime.strptime(check_in_str, '%H:%M:%S')
        check_out = datetime.strptime(check_out_str, '%H:%M:%S')
        
        duration = check_out - check_in
        total_seconds = duration.total_seconds()
        total_hours = total_seconds / 3600
        
        return round(total_hours, 2)
    except:
        return 0.0

def verify_face_recognition(face_image_data):
    """
    Verify face recognition from image data
    This is a placeholder - integrate with actual face recognition library
    In production, use: face_recognition, deepface, or mediapipe
    """
    try:
        # For now, return True (mock verification)
        # In production, implement actual face recognition:
        # import face_recognition
        # import numpy as np
        # face_encodings = face_recognition.face_encodings(image)
        # known_face_encoding = face_recognition.face_encodings(known_image)[0]
        # results = face_recognition.compare_faces([known_face_encoding], face_encodings[0])
        
        return face_image_data is not None  # Mock verification
    except Exception as e:
        print(f"Face recognition error: {e}")
        return False

# ────────────────────────────────────────────────
#   DECORATORS
# ────────────────────────────────────────────────

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('emp_id') is None:
            flash('Please log in first', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('emp_id') is None:
            flash('Please log in first', 'error')
            return redirect(url_for('auth.login'))
        
        emp = Employee.query.filter_by(emp_id=session.get('emp_id')).first()
        
        if not emp or not emp.is_admin:
            flash('Admin access required', 'error')
            return redirect(url_for('attendance.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

# ────────────────────────────────────────────────
#   AUTH BLUEPRINT
# ────────────────────────────────────────────────

auth_bp = Blueprint('auth', __name__, url_prefix='')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        emp_id = request.form.get('emp_id', '').upper().strip()
        name = request.form.get('name', '').strip()

        if not emp_id or not name:
            flash('Please provide both Employee ID and Name', 'error')
            return render_template('login.html')

        employee = Employee.query.filter_by(emp_id=emp_id).first()

        if employee:
            if employee.name.strip().lower() == name.lower():
                session['emp_id'] = emp_id
                session['emp_name'] = employee.name
                session['department'] = employee.department
                session['is_admin'] = employee.is_admin
                flash(f'Welcome back, {employee.name}!', 'success')
                return redirect(url_for('attendance.dashboard'))
            else:
                flash('Employee ID and Name do not match', 'error')
        else:
            # Auto-register new employee (no password required)
            new_employee = Employee(
                emp_id=emp_id,
                name=name,
                email='',
                department='General',
                password_hash=generate_password_hash(name),
                is_admin=False
            )
            db.session.add(new_employee)
            db.session.commit()

            session['emp_id'] = emp_id
            session['emp_name'] = name
            session['department'] = 'General'
            session['is_admin'] = False
            flash('Account created and signed in successfully!', 'success')
            return redirect(url_for('attendance.dashboard'))

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        emp_id = request.form.get('emp_id', '').upper()
        name = request.form.get('name', '')
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if Employee.query.filter_by(emp_id=emp_id).first():
            flash('Employee ID already registered', 'error')
        elif password != confirm_password:
            flash('Passwords do not match', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
        else:
            new_employee = Employee(
                emp_id=emp_id,
                name=name,
                email=email,
                department='General',
                password_hash=generate_password_hash(password),
                is_admin=False
            )
            db.session.add(new_employee)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
    
    return render_template('register.html')

app.register_blueprint(auth_bp)

# ────────────────────────────────────────────────
#   ATTENDANCE BLUEPRINT
# ────────────────────────────────────────────────

attendance_bp = Blueprint('attendance', __name__, url_prefix='')

@attendance_bp.route('/')
@login_required
def dashboard():
    emp = Employee.query.filter_by(emp_id=session.get('emp_id')).first()
    
    # Get today's attendance
    today = date.today()
    today_attendance = Attendance.query.filter(
        Attendance.employee_id == emp.id,
        Attendance.date == today
    ).first()
    
    today_status = 'Not Marked'
    today_attendance_status = '-'
    today_hours = 0.0
    
    if today_attendance:
        if today_attendance.check_out:
            today_status = 'Checked Out'
            today_hours = today_attendance.total_hours or 0.0
        else:
            today_status = 'Checked In'
        
        today_attendance_status = today_attendance.status or 'Unknown'
    
    # Calculate monthly stats
    current_month = today.replace(day=1)
    next_month = current_month.replace(month=current_month.month % 12 + 1, year=current_month.year + (current_month.month // 12))
    
    month_attendance = Attendance.query.filter(
        Attendance.employee_id == emp.id,
        Attendance.date >= current_month,
        Attendance.date < next_month
    ).count()
    
    return render_template('dashboard.html',
                         emp=emp,
                         today_status=today_status,
                         today_attendance_status=today_attendance_status,
                         today_hours=today_hours,
                         monthly_days=month_attendance,
                         avg_hours='8.5')

@attendance_bp.route('/checkout/<emp_id>', methods=['POST'])
@login_required
def checkout(emp_id):
    emp = Employee.query.filter_by(emp_id=emp_id).first()
    if not emp:
        flash('Employee not found.', 'error')
        return redirect(url_for('attendance.profile'))

    today = date.today()
    today_attendance = Attendance.query.filter(
        Attendance.employee_id == emp.id,
        Attendance.date == today
    ).first()

    if today_attendance and today_attendance.check_in and not today_attendance.check_out:
        now = datetime.now()
        current_time_str = now.strftime('%H:%M')
        check_in_time = datetime.strptime(today_attendance.check_in, '%H:%M')
        check_out_time = datetime.strptime(current_time_str, '%H:%M')

        if check_out_time < check_in_time:
            check_out_time = check_out_time.replace(day=check_out_time.day + 1)

        total_hours = (check_out_time - check_in_time).total_seconds() / 3600
        today_attendance.check_out = current_time_str
        today_attendance.total_hours = total_hours
        db.session.commit()

        flash(f'Checked out successfully! Total hours: {total_hours:.2f} hrs', 'success')
    else:
        flash('No check-in found or already checked out.', 'error')

    return redirect(url_for('attendance.profile', emp_id=emp_id))

@attendance_bp.route('/face-attendance')
@login_required
def face_attendance():
    return render_template('face_attendance.html')

@attendance_bp.route('/profile')
@attendance_bp.route('/profile/<emp_id>')
@login_required
def profile(emp_id=None):
    # Support both path and query parameter for emp_id
    if not emp_id:
        emp_id = request.args.get('emp_id') or session.get('emp_id')

    emp = Employee.query.filter_by(emp_id=emp_id).first()
    if not emp:
        flash('Employee not found.', 'error')
        return redirect(url_for('attendance.dashboard'))

    emp_records = Attendance.query.filter_by(employee_id=emp.id).order_by(Attendance.date.desc()).limit(10).all()
    print(f"DEBUG profile: emp_id={emp_id}, employee_dept={emp.department}, records_count={len(emp_records)}")
    today = date.today()
    return render_template('profile.html', emp=emp, records=emp_records, today=today)

# Edit employee profile info (department, email)
@attendance_bp.route('/edit-profile', methods=['POST'])
@attendance_bp.route('/edit-profile/<emp_id>', methods=['POST'])
@login_required
def edit_profile(emp_id=None):
    if not emp_id:
        emp_id = request.form.get('emp_id') or session.get('emp_id')

    if not emp_id:
        flash('Employee not found.', 'error')
        return redirect(url_for('attendance.profile'))

    department = request.form.get('department', '').strip()
    email = request.form.get('email', '').strip()

    emp = Employee.query.filter_by(emp_id=emp_id).first()
    if not emp:
        flash('Employee not found.', 'error')
        return redirect(url_for('attendance.profile', emp_id=emp_id))

    emp.department = department
    emp.email = email
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('attendance.profile', emp_id=emp_id))

@attendance_bp.route('/enroll')
@login_required
def enroll():
    return render_template('fingerprint_enroll.html')

@attendance_bp.route('/enroll', methods=['POST'])
@login_required
def enroll_post():
    name = request.form.get('name', '').strip()
    emp_id = request.form.get('emp_id', '').upper().strip()
    department = request.form.get('department', 'General')
    
    if not name or not emp_id:
        flash('Please provide both name and employee ID', 'error')
        return redirect(url_for('attendance.enroll'))
    
    # Check if employee ID already exists
    existing_employee = Employee.query.filter_by(emp_id=emp_id).first()
    if existing_employee:
        flash('Employee ID already exists. Please use a different ID.', 'error')
        return redirect(url_for('attendance.enroll'))
    
    # Create new employee
    new_employee = Employee(
        emp_id=emp_id,
        name=name,
        email='',
        department=department,
        password_hash=generate_password_hash(name),  # Use name as default password
        is_admin=False
    )
    db.session.add(new_employee)
    db.session.commit()
    
    flash(f'Employee {name} enrolled successfully! Employee ID: {emp_id}', 'success')
    return redirect(url_for('attendance.enroll'))

@attendance_bp.route('/employee-list')
@login_required
def employee_list():
    employees = Employee.query.order_by(Employee.created_at.desc()).all()
    return render_template('employee_list.html', employees=employees)

@attendance_bp.route('/bulk-enroll', methods=['POST'])
@login_required
def bulk_enroll():
    bulk_data = request.form.get('bulk_data', '').strip()
    
    if not bulk_data:
        flash('Please provide employee data for bulk enrollment', 'error')
        return redirect(url_for('attendance.enroll'))
    
    lines = bulk_data.split('\n')
    success_count = 0
    error_messages = []
    
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        
        parts = [part.strip() for part in line.split(',')]
        if len(parts) < 2:
            error_messages.append(f"Line {line_num}: Invalid format. Use: Name,EmployeeID,Department")
            continue
        
        name = parts[0]
        emp_id = parts[1].upper()
        department = parts[2] if len(parts) > 2 else 'General'
        
        if not name or not emp_id:
            error_messages.append(f"Line {line_num}: Name and Employee ID are required")
            continue
        
        # Check if employee ID already exists
        existing_employee = Employee.query.filter_by(emp_id=emp_id).first()
        if existing_employee:
            error_messages.append(f"Line {line_num}: Employee ID {emp_id} already exists")
            continue
        
        # Create new employee
        new_employee = Employee(
            emp_id=emp_id,
            name=name,
            email='',
            department=department,
            password_hash=generate_password_hash(name),
            is_admin=False
        )
        db.session.add(new_employee)
        success_count += 1
    
    db.session.commit()
    
    if success_count > 0:
        flash(f'Successfully enrolled {success_count} employee(s)!', 'success')
    
    if error_messages:
        for error in error_messages[:5]:  # Show first 5 errors
            flash(error, 'error')
        if len(error_messages) > 5:
            flash(f'And {len(error_messages) - 5} more errors...', 'error')
    
    return redirect(url_for('attendance.employee_list'))

@attendance_bp.route('/api/verify-face', methods=['POST'])
@login_required
def verify_face():
    """Verify face recognition and return employee details if recognized"""
    try:
        data = request.get_json()
        if not data or 'image_data' not in data:
            return jsonify({'success': False, 'message': 'No face image data provided'}), 400

        image_data = data['image_data']

        # Mock face recognition - prioritize the logged-in employee for testing
        session_emp_id = session.get('emp_id')
        if session_emp_id:
            recognized_employee = Employee.query.filter_by(emp_id=session_emp_id).first()
            if recognized_employee:
                return jsonify({
                    'success': True,
                    'message': 'Face recognized successfully!',
                    'employee': {
                        'emp_id': recognized_employee.emp_id,
                        'name': recognized_employee.name,
                        'department': recognized_employee.department or 'General'
                    }
                })

        # Fallback to mock recognition
        employees = Employee.query.order_by(Employee.id).all()
        if not employees:
            return jsonify({
                'success': False,
                'message': 'No employees found. Please enroll first.',
                'recognized': False
            })

        # Pick pseudo-random employee based on image data
        import hashlib
        key = hashlib.md5(image_data.encode('utf-8')).hexdigest()
        index = int(key, 16) % len(employees)
        recognized_employee = employees[index]

        return jsonify({
            'success': True,
            'message': 'Face recognized successfully!',
            'employee': {
                'emp_id': recognized_employee.emp_id,
                'name': recognized_employee.name,
                'department': recognized_employee.department or 'General'
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'recognized': False
        }), 500

@attendance_bp.route('/api/enroll-face', methods=['POST'])
@login_required
def enroll_face():
    """Enroll new employee with face recognition"""
    try:
        emp_id = request.form.get('emp_id', '').upper().strip()
        name = request.form.get('name', '').strip()
        department = request.form.get('department', 'General')
        image_data = request.form.get('image_data')

        if not emp_id or not name:
            return jsonify({'success': False, 'message': 'Employee ID and name are required'}), 400

        # Check if employee ID already exists
        existing_employee = Employee.query.filter_by(emp_id=emp_id).first()
        if existing_employee:
            return jsonify({'success': False, 'message': 'Employee ID already exists'}), 400

        # Create new employee
        new_employee = Employee(
            emp_id=emp_id,
            name=name,
            email='',  # Can be updated later
            department=department,
            password_hash=generate_password_hash(name),  # Use name as default password
            is_admin=False
        )

        # In production, save face encoding
        # For now, just save the image data as a placeholder
        if image_data:
            os.makedirs('data/faces', exist_ok=True)
            # Save base64 image data
            import base64
            image_data = image_data.replace('data:image/jpeg;base64,', '')
            with open(f'data/faces/{emp_id}_face.jpg', 'wb') as f:
                f.write(base64.b64decode(image_data))

        db.session.add(new_employee)
        db.session.commit()

        # Now mark their first attendance
        today = date.today()
        now = datetime.now()
        current_time_str = now.strftime('%H:%M')
        status = get_attendance_status(current_time_str)

        new_attendance = Attendance(
            employee_id=new_employee.id,
            date=today,
            check_in=current_time_str,
            status=status,
            attendance_type='Onsite',  # Default for first check-in
            department=department or new_employee.department or 'General'
        )
        db.session.add(new_attendance)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Employee {name} enrolled and checked in successfully!',
            'employee': {
                'emp_id': emp_id,
                'name': name,
                'department': department
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Enrollment failed: {str(e)}'
        }), 500

@attendance_bp.route('/api/face-attendance', methods=['POST'])
@login_required
def face_attendance_api():
    """Mark attendance for recognized employee"""
    try:
        emp_id = request.form.get('emp_id')
        department = request.form.get('department')
        attendance_type = request.form.get('attendance_type', 'Onsite')

        print(f"DEBUG: Received emp_id={emp_id}, department={department}, attendance_type={attendance_type}")

        if not emp_id:
            return jsonify({'success': False, 'message': 'Employee ID is required'}), 400

        emp = Employee.query.filter_by(emp_id=emp_id).first()
        if not emp:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404

        today = date.today()
        now = datetime.now()
        current_time_str = now.strftime('%H:%M')

        # Check if already checked in today
        today_attendance = Attendance.query.filter(
            Attendance.employee_id == emp.id,
            Attendance.date == today
        ).first()

        if today_attendance:
            if today_attendance.check_out:
                return jsonify({'success': False, 'message': 'Already checked out today'}), 400
            else:
                # Mark check out - Calculate hours
                check_in_time = datetime.strptime(today_attendance.check_in, '%H:%M')
                check_out_time = datetime.strptime(current_time_str, '%H:%M')

                if check_out_time < check_in_time:
                    check_out_time = check_out_time.replace(day=check_out_time.day + 1)

                total_hours = (check_out_time - check_in_time).total_seconds() / 3600

                today_attendance.check_out = current_time_str
                today_attendance.total_hours = total_hours
                db.session.commit()

                message = f'Checked out successfully! Total hours: {total_hours:.2f} hrs'
        else:
            # New check in - Determine status (On-time or Late)
            status = get_attendance_status(current_time_str)

            # Update employee department if selected
            if department:
                emp.department = department

            new_attendance = Attendance(
                employee_id=emp.id,
                date=today,
                check_in=current_time_str,
                status=status,
                attendance_type=attendance_type,
                department=department or emp.department
            )
            db.session.add(new_attendance)
            db.session.commit()

            message = f'Checked in successfully! Status: {status}'
        return jsonify({
            'success': True,
            'message': message
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Attendance marking failed: {str(e)}'
        }), 500

app.register_blueprint(attendance_bp)

# ────────────────────────────────────────────────
#   ADMIN BLUEPRINT
# ────────────────────────────────────────────────

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    employees = Employee.query.all()
    attendance_records = Attendance.query.filter(Attendance.date == date.today()).all()
    
    # Get today's summary
    present = len([r for r in attendance_records if r.check_in])
    on_time = len([r for r in attendance_records if r.status == 'On-Time'])
    late = len([r for r in attendance_records if r.status == 'Late'])
    absent = len(employees) - present
    
    return render_template('admin.html',
                         employees=employees,
                         attendance_records=attendance_records,
                         today_present=present,
                         today_on_time=on_time,
                         today_late=late,
                         today_absent=absent)

@admin_bp.route('/attendance-list')
@admin_required
def attendance_list():
    attendance_records = Attendance.query.all()
    return render_template('daily_report.html', records=attendance_records)

app.register_blueprint(admin_bp)

# ────────────────────────────────────────────────
#   API ENDPOINTS
# ────────────────────────────────────────────────

@app.route('/api/employees-status')
@login_required
def employees_status():
    """API endpoint for employee status"""
    employees = Employee.query.all()
    today = date.today()
    
    results = []
    for emp in employees:
        attendance = Attendance.query.filter(
            Attendance.employee_id == emp.id,
            Attendance.date == today
        ).first()
        
        status = 'Absent'
        check_in = None
        
        if attendance and attendance.check_in:
            status = 'Present'
            check_in = attendance.check_in
        
        results.append({
            'emp_id': emp.emp_id,
            'name': emp.name,
            'status': status,
            'check_in': check_in
        })
    
    return jsonify(results)

@app.route('/api/attendance-today')
@login_required
def attendance_today():
    """API endpoint for today's attendance"""
    today_records = Attendance.query.filter(Attendance.date == date.today()).all()
    return jsonify([{
        'id': r.id,
        'emp_id': r.employee.emp_id,
        'name': r.employee.name,
        'check_in': r.check_in,
        'check_out': r.check_out,
        'status': r.status,
        'attendance_type': r.attendance_type,
        'total_hours': r.total_hours
    } for r in today_records])

# ────────────────────────────────────────────────
#   ERROR HANDLERS
# ────────────────────────────────────────────────

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "Page not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
    app.run(host='0.0.0.0', port=port, debug=debug)