from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models.attendance_model import db, Employee, Attendance, calculate_attendance_status, calculate_total_hours

# Face recognition is optional; if not installed (e.g. on Heroku without dlib), the app still runs.
try:
    import face_recognition
    FACE_RECOG_AVAILABLE = True
except ImportError:
    face_recognition = None
    FACE_RECOG_AVAILABLE = False

import base64
import cv2
import numpy as np
import pickle
from datetime import datetime

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

# Edit employee profile info (department, email)
@attendance_bp.route('/edit-profile', methods=['POST'])
@login_required
def edit_profile():
    emp_id = current_user.emp_id if hasattr(current_user, 'emp_id') else None
    if not emp_id:
        flash('Employee not found.', 'error')
        return redirect(url_for('attendance.profile'))

    department = request.form.get('department', '').strip()
    email = request.form.get('email', '').strip()

    emp = Employee.query.filter_by(emp_id=emp_id).first()
    if not emp:
        flash('Employee not found.', 'error')
        return redirect(url_for('attendance.profile'))

    emp.department = department
    emp.email = email
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('attendance.profile'))

# Enroll new employee with face capture
@attendance_bp.route('/enroll-face', methods=['GET', 'POST'])
@login_required  # or admin only
def enroll_face():
    if not FACE_RECOG_AVAILABLE:
        flash('Face recognition is not available on this deployment.', 'error')
        return redirect(url_for('attendance.dashboard'))

    if request.method == 'POST':
        emp_id = request.form.get('emp_id', '').upper().strip()
        name = request.form.get('name', '').strip()
        department = request.form.get('department', '')

        if not emp_id or not name:
            flash('Please provide an Employee ID and Name.', 'error')
            return redirect(url_for('attendance.enroll_face'))

        # Get base64 image from frontend
        image_data = request.form.get('image', '')
        if not image_data:
            flash('No face image provided.', 'error')
            return redirect(url_for('attendance.enroll_face'))

        try:
            _, encoded = image_data.split(',', 1)
            img_bytes = base64.b64decode(encoded)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        except Exception:
            flash('Unable to process the uploaded image. Please try again.', 'error')
            return redirect(url_for('attendance.enroll_face'))

        # Detect faces
        face_locations = face_recognition.face_locations(rgb_img)
        if not face_locations:
            flash('No face detected in the image. Please try again.', 'error')
            return redirect(url_for('attendance.enroll_face'))

        # Get encoding (first face)
        face_encoding = face_recognition.face_encodings(rgb_img, face_locations)[0]

        # Check if employee already exists
        existing = Employee.query.filter_by(emp_id=emp_id).first()
        if existing:
            flash('Employee ID already exists.', 'warning')
            return redirect(url_for('attendance.enroll_face'))

        # Save new employee with face encoding
        new_emp = Employee(
            emp_id=emp_id,
            name=name,
            department=department,
            face_encoding=pickle.dumps(face_encoding)
        )
        db.session.add(new_emp)
        db.session.commit()

        flash(f'Employee {name} ({emp_id}) enrolled successfully with face recognition!', 'success')
        return redirect(url_for('attendance.dashboard'))

    return render_template('attendance/enroll_face.html')

# Face recognition for attendance (called from JS)
@attendance_bp.route('/recognize-face', methods=['POST'])
def recognize_face():
    if not FACE_RECOG_AVAILABLE:
        return jsonify({'success': False, 'message': 'Face recognition is not available on this deployment.'}), 503

    # Get image from frontend (base64)
    data = request.get_json(silent=True) or {}
    image_data = data.get('image')
    if not image_data:
        return jsonify({'success': False, 'message': 'No face image data provided.'}), 400

    try:
        _, encoded = image_data.split(',', 1)
        img_bytes = base64.b64decode(encoded)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except Exception:
        return jsonify({'success': False, 'message': 'Unable to decode image.'}), 400

    # Find face encodings in the image
    face_encodings = face_recognition.face_encodings(rgb_img)
    if not face_encodings:
        return jsonify({'success': False, 'message': 'No face detected'})

    unknown_encoding = face_encodings[0]

    # Compare with all enrolled employees
    employees = Employee.query.all()
    for emp in employees:
        if emp.face_encoding:
            known_encoding = pickle.loads(emp.face_encoding)
            match = face_recognition.compare_faces([known_encoding], unknown_encoding)[0]
            if match:
                # Found match - auto check-in / check-out
                today = datetime.now().date()
                record = Attendance.query.filter_by(employee_id=emp.id, date=today).first()

                now = datetime.now()
                if not record or not record.check_in:
                    # Check-in
                    status = calculate_attendance_status(now)
                    if not record:
                        record = Attendance(employee_id=emp.id, date=today, check_in=now, status=status)
                        db.session.add(record)
                    else:
                        record.check_in = now
                        record.status = status
                    db.session.commit()
                    return jsonify({
                        'success': True,
                        'message': f'Welcome {emp.name}! Checked in at {now.strftime("%I:%M %p")} ({status})',
                        'status': status,
                        'action': 'check-in'
                    })

                elif not record.check_out:
                    # Check-out
                    record.check_out = now
                    record.total_hours = calculate_total_hours(record.check_in, now)
                    db.session.commit()
                    return jsonify({
                        'success': True,
                        'message': f'Goodbye {emp.name}! Checked out at {now.strftime("%I:%M %p")}. Total: {record.total_hours:.2f} hrs',
                        'status': 'Checked Out',
                        'action': 'check-out'
                    })

                else:
                    return jsonify({'success': False, 'message': f'{emp.name} already completed today'})

    return jsonify({'success': False, 'message': 'Face not recognized. Please enroll first.'})
