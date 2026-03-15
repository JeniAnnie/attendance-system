import sqlite3

conn = sqlite3.connect('attendance.db')
c = conn.cursor()
c.execute('UPDATE attendance SET department = ? WHERE department IS NULL', ('General',))
conn.commit()
conn.close()
print('Updated attendance departments to General where NULL')
