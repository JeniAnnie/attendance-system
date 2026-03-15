from flask import Blueprint, send_file
import sqlite3
import pandas as pd

report_bp = Blueprint("report", __name__)

@report_bp.route("/report")

def report():

    conn = sqlite3.connect("attendance.db")

    df = pd.read_sql_query("SELECT * FROM attendance", conn)

    file = "attendance_report.xlsx"
    df.to_excel(file, index=False)

    return send_file(file, as_attachment=True)