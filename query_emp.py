from app import app, Employee

with app.app_context():
    emp = Employee.query.filter_by(emp_id='31').first()
    if not emp:
        print('EMP NOT FOUND')
    else:
        print('emp_id', emp.emp_id)
        print('name', emp.name)
        print('department', emp.department)
        print('email', emp.email)
