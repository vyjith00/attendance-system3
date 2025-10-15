import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from a .env file located next to config.py (if present)
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///attendance.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Twilio Configuration - read from environment for safety
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')

    # Attendance Time Limits (in minutes)
    ATTENDANCE_TIME_LIMIT = int(os.environ.get('ATTENDANCE_TIME_LIMIT', '30'))  # 30 minutes after start time
    LATE_TIME_LIMIT = int(os.environ.get('LATE_TIME_LIMIT', '60'))       # 60 minutes for late marking
