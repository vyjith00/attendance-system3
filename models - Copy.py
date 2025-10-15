from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Staff(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    barcode = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    reg_no = db.Column(db.String(50), unique=True, nullable=False)
    department = db.Column(db.String(100), nullable=False)
    parent_phone = db.Column(db.String(15), nullable=False)
    barcode = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with attendance records
    attendance_records = db.relationship('Attendance', backref='student', lazy=True)
    
    def get_attendance_percentage(self):
        total_days = Attendance.query.filter_by(student_id=self.id).count()
        if total_days == 0:
            return 0
        # Use SQLAlchemy's in_ operator to check for multiple statuses
        present_days = Attendance.query.filter(
            Attendance.student_id == self.id,
            Attendance.status.in_(['present', 'late'])
        ).count()
        return round((present_days / total_days) * 100, 2)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    # Use callables so defaults are evaluated at instance creation time
    date = db.Column(db.Date, default=lambda: datetime.utcnow().date())
    time = db.Column(db.Time, default=lambda: datetime.utcnow().time())
    status = db.Column(db.String(20), nullable=False)  # present, absent, late
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
# Add this class at the end of models.py file
class StaffAttendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False)
    date = db.Column(db.Date, default=lambda: datetime.now().date())
    time = db.Column(db.Time, default=lambda: datetime.now().time())
    status = db.Column(db.String(20), nullable=False)  # present, absent, late
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationship
    staff = db.relationship('Staff', backref='staff_attendance_records')
    
    def __repr__(self):
        return f'<StaffAttendance {self.staff.name} - {self.date}>'

