import sqlite3

conn = sqlite3.connect('attendance.db')
cur = conn.cursor()

print('Employee 27:')
cur.execute("SELECT id, emp_id, name, department FROM employee WHERE emp_id='27'")
print(cur.fetchone())

print('\nAttendance rows for emp_id 27:')
cur.execute("SELECT id, date, check_in, check_out, department FROM attendance WHERE employee_id=(SELECT id FROM employee WHERE emp_id='27') ORDER BY id DESC LIMIT 5")
for r in cur.fetchall():
    print(r)

conn.close()
