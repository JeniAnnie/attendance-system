from flask import Blueprint, render_template
import sqlite3

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route("/analytics")
def analytics():

    conn = sqlite3.connect("attendance.db")
    conn.row_factory = sqlite3.Row

    data = conn.execute("""
    SELECT status, COUNT(*) as count
    FROM attendance
    GROUP BY status
    """).fetchall()

    conn.close()

    labels = []
    values = []

    for row in data:
        labels.append(row["status"])
        values.append(row["count"])

    chart_data = {
        "labels": labels,
        "values": values
    }

    return render_template("analytics.html", data=chart_data)