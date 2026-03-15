from flask import Blueprint, render_template, request, redirect, session, url_for

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        emp_id = request.form['emp_id']
        password = request.form['password']
        if emp_id == "admin" and password == "admin":
            session['emp_id'] = emp_id
            session['role'] = "Admin"
            return redirect('/dashboard')
        elif emp_id == "emp" and password == "emp":
            session['emp_id'] = emp_id
            session['role'] = "Employee"
            return redirect('/dashboard')
        else:
            return "Invalid credentials. Try again"
    return render_template('login.html')

@auth_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/login')