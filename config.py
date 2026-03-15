import os

# In production (e.g. Heroku), set a secure SECRET_KEY and DATABASE_URL.
SECRET_KEY = os.environ.get("SECRET_KEY", "attendance_secret")

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    # Heroku provides DATABASE_URL for Postgres
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
else:
    # Local sqlite fallback (file stored in repo folder)
    DATABASE = "attendance.db"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.abspath(DATABASE)}"

SQLALCHEMY_TRACK_MODIFICATIONS = False