

conn = sqlite3.connect("attendance.db")
cursor = conn.cursor()

# Create employee table
cursor.execute("""
CREATE TABLE IF NOT EXISTS employee (
id INTEGER PRIMARY KEY AUTOINCREMENT,
emp_id TEXT UNIQUE NOT NULL,
emp_name TEXT NOT NULL,
department TEXT,
work_type TEXT,
fingerprint_data TEXT,
enrolled BOOLEAN DEFAULT 0,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Create attendance table
cursor.execute("""
CREATE TABLE IF NOT EXISTS attendance (
id INTEGER PRIMARY KEY AUTOINCREMENT,
emp_id TEXT,
emp_name TEXT,
department TEXT,
work_type TEXT,
status TEXT,
attendance_type TEXT,
check_in TEXT,
check_out TEXT,
total_hours REAL,
date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

print("Database and tables created successfully")