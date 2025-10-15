from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import qrcode
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
import base64
from datetime import datetime, time, timedelta
import uuid
try:
    from twilio.rest import Client
except ImportError:
    Client = None
import csv
from models import db, Admin, Staff, Student, Attendance, StaffAttendance
from config import Config


app = Flask(__name__)
app.config.from_object(Config)


# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# Initialize Twilio client safely
twilio_client = None
if Client and app.config.get('TWILIO_ACCOUNT_SID') and app.config.get('TWILIO_AUTH_TOKEN'):
    try:
        twilio_client = Client(app.config['TWILIO_ACCOUNT_SID'], app.config['TWILIO_AUTH_TOKEN'])
        print("[INFO] Twilio client initialized successfully")
    except Exception as e:
        print(f"[WARNING] Twilio initialization failed: {e}")


@login_manager.user_loader
def load_user(user_id):
    admin = Admin.query.get(int(user_id))
    if admin:
        return admin
    return Staff.query.get(int(user_id))


def generate_barcode_string():
    """Generate unique barcode string"""
    return str(uuid.uuid4())[:8].upper()


def create_qr_code(data):
    """Generate QR code and return base64 encoded string"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return img_str


def send_sms_notification(phone_number, message):
    """Send SMS notification using Twilio"""
    if not twilio_client:
        print("[WARNING] SMS skipped: Twilio not configured")
        return False
    
    try:
        twilio_client.messages.create(
            body=message,
            from_=app.config.get('TWILIO_PHONE_NUMBER'),
            to=phone_number
        )
        print(f"[SUCCESS] SMS sent to {phone_number}")
        return True
    except Exception as e:
        print(f"[ERROR] SMS failed: {e}")
        return False


def check_attendance_time():
    """Check if current time is within attendance window"""
    current_time = datetime.now().time()
    start_time = time(9, 0)  # 9:00 AM
    end_time = time(9, 30)   # 9:30 AM
    late_time = time(10, 0)  # 10:00 AM
    
    if start_time <= current_time <= end_time:
        return 'present'
    elif end_time < current_time <= late_time:
        return 'late'
    else:
        return 'absent'


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    print("[INFO] Login route accessed")
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_type = request.form.get('user_type')
        
        print(f"[DEBUG] Form data received:")
        print(f"   Username: '{username}'")
        print(f"   Password: '{password}'")
        print(f"   User Type: '{user_type}'")
        
        if not username or not password or not user_type:
            print("[ERROR] Missing form data!")
            flash('Please fill in all fields')
            return render_template('login.html')
        
        if user_type == 'admin':
            user = Admin.query.filter_by(username=username).first()
            print(f"[DEBUG] Admin search result: {user is not None}")
        else:
            user = Staff.query.filter_by(name=username).first()
            print(f"[DEBUG] Staff search result: {user is not None}")
        
        if user:
            password_check = user.check_password(password)
            print(f"[DEBUG] Password check result: {password_check}")
            
            if password_check:
                login_user(user)
                print(f"[SUCCESS] User logged in successfully! Redirecting...")
                
                if user_type == 'admin':
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('staff_dashboard'))
            else:
                print("[ERROR] Invalid password!")
                flash('Invalid password')
        else:
            print("[ERROR] User not found!")
            flash('User not found')
    
    print("[INFO] Rendering login template")
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('login'))
    
    total_students = Student.query.count()
    total_staff = Staff.query.count()
    today_attendance = Attendance.query.filter_by(date=datetime.now().date()).count()
    
    return render_template('admin_dashboard.html', 
                         total_students=total_students,
                         total_staff=total_staff,
                         today_attendance=today_attendance)


@app.route('/staff_dashboard')
@login_required
def staff_dashboard():
    students = Student.query.all()
    return render_template('staff_dashboard.html', students=students)


@app.route('/register_staff', methods=['GET', 'POST'])
@login_required
def register_staff():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash('Access denied - Admin only')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        department = request.form.get('department')
        password = request.form.get('password')
        
        print(f"[DEBUG] Staff registration attempt:")
        print(f"  Name: {name}")
        print(f"  Department: {department}")
        print(f"  Password: {'*' * len(password) if password else 'None'}")
        
        if not name or not department or not password:
            flash('Please fill in all fields')
            return render_template('register_staff.html')
        
        try:
            barcode_str = generate_barcode_string()
            
            staff = Staff(
                name=name,
                department=department,
                barcode=barcode_str
            )
            staff.set_password(password)
            
            db.session.add(staff)
            db.session.commit()
            
            # Generate QR code
            qr_code = create_qr_code(barcode_str)
            
            flash('Staff registered successfully!')
            print(f"[SUCCESS] Staff {name} registered with ID {staff.id}")
            
            return render_template('register_staff.html', 
                                 success=True, 
                                 barcode=barcode_str, 
                                 qr_code=qr_code,
                                 staff_name=name)
        except Exception as e:
            print(f"[ERROR] Staff registration failed: {e}")
            flash(f'Registration failed: {str(e)}')
            return render_template('register_staff.html')
    
    return render_template('register_staff.html')


@app.route('/register_student', methods=['GET', 'POST'])
@login_required
def register_student():
    # Allow both admin and staff to register students
    if request.method == 'POST':
        name = request.form.get('name')
        reg_no = request.form.get('reg_no')
        department = request.form.get('department')
        parent_phone = request.form.get('parent_phone')
        
        if not name or not reg_no or not department or not parent_phone:
            flash('Please fill in all fields')
            return render_template('register_student.html')
        
        # Check if student already exists
        existing_student = Student.query.filter_by(reg_no=reg_no).first()
        if existing_student:
            flash('Student with this registration number already exists')
            return render_template('register_student.html')
        
        barcode_str = generate_barcode_string()
        
        student = Student(
            name=name,
            reg_no=reg_no,
            department=department,
            parent_phone=parent_phone,
            barcode=barcode_str
        )
        
        db.session.add(student)
        db.session.commit()
        
        # Generate QR code
        qr_code = create_qr_code(barcode_str)
        
        flash('Student registered successfully')
        return render_template('register_student.html', 
                             success=True, 
                             barcode=barcode_str, 
                             qr_code=qr_code,
                             student_name=name)
    
    return render_template('register_student.html')


@app.route('/student_details/<int:student_id>')
@login_required
def student_details(student_id):
    student = Student.query.get_or_404(student_id)
    attendance_records = Attendance.query.filter_by(student_id=student_id).order_by(Attendance.date.desc()).limit(30).all()
    attendance_percentage = student.get_attendance_percentage()
    
    return render_template('student_details.html', 
                         student=student, 
                         attendance_records=attendance_records,
                         attendance_percentage=attendance_percentage)


@app.route('/staff_details/<int:staff_id>')
@login_required
def staff_details(staff_id):
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('login'))
    
    staff = Staff.query.get_or_404(staff_id)
    attendance_records = StaffAttendance.query.filter_by(staff_id=staff_id).order_by(StaffAttendance.date.desc()).limit(30).all()
    
    # Calculate statistics
    total_days = len(attendance_records)
    present_days = len([r for r in attendance_records if r.status == 'present'])
    late_days = len([r for r in attendance_records if r.status == 'late'])
    absent_days = len([r for r in attendance_records if r.status == 'absent'])
    
    attendance_percentage = ((present_days + late_days) / total_days * 100) if total_days > 0 else 0
    
    return render_template('staff_details.html', 
                         staff=staff, 
                         attendance_records=attendance_records,
                         attendance_percentage=round(attendance_percentage, 2),
                         total_days=total_days,
                         present_days=present_days,
                         late_days=late_days,
                         absent_days=absent_days)


@app.route('/staff_attendance')
@login_required
def staff_attendance():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('login'))
    
    print("[INFO] Loading staff attendance page...")
    
    # Get all staff attendance records
    staff_attendance_data = []
    staff_members = Staff.query.all()
    
    for staff in staff_members:
        attendance_records = StaffAttendance.query.filter_by(staff_id=staff.id).order_by(StaffAttendance.date.desc()).limit(30).all()
        
        # Calculate attendance percentage
        total_days = len(attendance_records)
        present_days = len([r for r in attendance_records if r.status in ['present', 'late']])
        attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
        
        staff_attendance_data.append({
            'id': staff.id,
            'name': staff.name,
            'department': staff.department,
            'attendance_percentage': round(attendance_percentage, 2),
            'total_days': total_days,
            'recent_records': attendance_records[:10]  # Last 10 records
        })
    
    return render_template('staff_attendance.html', staff_data=staff_attendance_data)


@app.route('/student_attendance')
@login_required
def student_attendance():
    """FIXED ROUTE: Student Attendance Reports - Redirect to All Students"""
    print("[INFO] Student attendance page requested - redirecting to All Students")
    flash("📊 Viewing comprehensive student data in All Students page", 'info')
    return redirect(url_for('all_students'))


# NEW ROUTES FOR TODAY'S FEATURES
@app.route('/todays_students')
@login_required
def todays_students():
    """Show today's student attendance records"""
    print("[INFO] Loading today's students attendance...")
    
    today = datetime.now().date()
    
    # Get today's student attendance records
    todays_records = db.session.query(Attendance, Student).join(Student).filter(
        Attendance.date == today
    ).order_by(Attendance.time.desc()).all()
    
    # Get students who haven't marked attendance yet
    all_students = Student.query.all()
    marked_student_ids = [record[0].student_id for record in todays_records]
    absent_students = [student for student in all_students if student.id not in marked_student_ids]
    
    # Calculate statistics
    total_students = Student.query.count()
    present_count = len([r for r in todays_records if r[0].status == 'present'])
    late_count = len([r for r in todays_records if r[0].status == 'late'])
    absent_count = len(absent_students)
    attendance_rate = ((present_count + late_count) / total_students * 100) if total_students > 0 else 0
    
    return render_template('todays_students.html',
                         todays_records=todays_records,
                         absent_students=absent_students,
                         total_students=total_students,
                         present_count=present_count,
                         late_count=late_count,
                         absent_count=absent_count,
                         attendance_rate=round(attendance_rate, 1),
                         today=today)


@app.route('/todays_staff')
@login_required
def todays_staff():
    """Show today's staff attendance records"""
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash('Access denied - Admin only')
        return redirect(url_for('staff_dashboard'))
    
    print("[INFO] Loading today's staff attendance...")
    
    today = datetime.now().date()
    
    # Get today's staff attendance records
    todays_records = db.session.query(StaffAttendance, Staff).join(Staff).filter(
        StaffAttendance.date == today
    ).order_by(StaffAttendance.time.desc()).all()
    
    # Get staff who haven't marked attendance yet
    all_staff = Staff.query.all()
    marked_staff_ids = [record[0].staff_id for record in todays_records]
    absent_staff = [staff for staff in all_staff if staff.id not in marked_staff_ids]
    
    # Calculate statistics
    total_staff = Staff.query.count()
    present_count = len([r for r in todays_records if r[0].status == 'present'])
    late_count = len([r for r in todays_records if r[0].status == 'late'])
    absent_count = len(absent_staff)
    attendance_rate = ((present_count + late_count) / total_staff * 100) if total_staff > 0 else 0
    
    return render_template('todays_staff.html',
                         todays_records=todays_records,
                         absent_staff=absent_staff,
                         total_staff=total_staff,
                         present_count=present_count,
                         late_count=late_count,
                         absent_count=absent_count,
                         attendance_rate=round(attendance_rate, 1),
                         today=today)


@app.route('/student_daily_report')
@login_required
def student_daily_report():
    """Generate today's student attendance report"""
    print("[INFO] Generating student daily report...")
    
    today = datetime.now().date()
    
    # Get today's student attendance data
    todays_records = db.session.query(Attendance, Student).join(Student).filter(
        Attendance.date == today
    ).order_by(Student.name).all()
    
    # Create CSV content
    csv_lines = []
    csv_lines.append('Student Name,Registration No,Department,Time,Status,Parent Phone')
    
    for attendance, student in todays_records:
        line = f'"{student.name}","{student.reg_no}","{student.department}","{attendance.time.strftime("%H:%M:%S")}","{attendance.status}","{student.parent_phone or ""}"'
        csv_lines.append(line)
    
    # Add absent students
    all_students = Student.query.all()
    marked_student_ids = [record[0].student_id for record in todays_records]
    absent_students = [student for student in all_students if student.id not in marked_student_ids]
    
    for student in absent_students:
        line = f'"{student.name}","{student.reg_no}","{student.department}","Not Marked","Absent","{student.parent_phone or ""}"'
        csv_lines.append(line)
    
    csv_content = '\n'.join(csv_lines)
    
    # Create response
    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=student_daily_report_{today.strftime("%Y%m%d")}.csv'
    
    return response


@app.route('/staff_daily_report')
@login_required
def staff_daily_report():
    """Generate today's staff attendance report"""
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash('Access denied - Admin only')
        return redirect(url_for('staff_dashboard'))
    
    print("[INFO] Generating staff daily report...")
    
    today = datetime.now().date()
    
    # Get today's staff attendance data
    todays_records = db.session.query(StaffAttendance, Staff).join(Staff).filter(
        StaffAttendance.date == today
    ).order_by(Staff.name).all()
    
    # Create CSV content
    csv_lines = []
    csv_lines.append('Staff Name,Department,Time,Status')
    
    for attendance, staff in todays_records:
        line = f'"{staff.name}","{staff.department}","{attendance.time.strftime("%H:%M:%S")}","{attendance.status}"'
        csv_lines.append(line)
    
    # Add absent staff
    all_staff = Staff.query.all()
    marked_staff_ids = [record[0].staff_id for record in todays_records]
    absent_staff = [staff for staff in all_staff if staff.id not in marked_staff_ids]
    
    for staff in absent_staff:
        line = f'"{staff.name}","{staff.department}","Not Marked","Absent"'
        csv_lines.append(line)
    
    csv_content = '\n'.join(csv_lines)
    
    # Create response
    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=staff_daily_report_{today.strftime("%Y%m%d")}.csv'
    
    return response


@app.route('/scan_barcode', methods=['POST'])
def scan_barcode():
    """Enhanced QR scanner route for both students and staff"""
    data = request.get_json(silent=True) or {}
    barcode_data = data.get('barcode')
    
    if not barcode_data:
        return jsonify({
            'status': 'error', 
            'message': '❌ No QR code data received',
            'icon': 'fas fa-exclamation-circle',
            'color': 'danger'
        }), 400
    
    print(f"[INFO] 🎯 QR code scan attempt: {barcode_data}")
    
    # Try to find student first, then staff
    student = Student.query.filter_by(barcode=barcode_data).first()
    staff = Staff.query.filter_by(barcode=barcode_data).first()
    
    person = None
    person_type = None
    
    if student:
        person = student
        person_type = 'student'
        print(f"[INFO] 👨‍🎓 Student found: {student.name}")
    elif staff:
        person = staff
        person_type = 'staff'
        print(f"[INFO] 👨‍💼 Staff found: {staff.name}")
    else:
        print(f"[ERROR] ❌ No person found for QR code: {barcode_data}")
        return jsonify({
            'status': 'error', 
            'message': '❌ Invalid QR Code - Person not found in system',
            'subtitle': 'Please ensure the QR code belongs to a registered student or staff member',
            'icon': 'fas fa-user-slash',
            'color': 'danger',
            'sound': 'error'
        }), 404
    
    # Check if already marked today
    today = datetime.now().date()
    
    if person_type == 'student':
        existing_attendance = Attendance.query.filter_by(
            student_id=person.id, 
            date=today
        ).first()
        attendance_model = Attendance
        person_id_field = 'student_id'
    else:  # staff
        existing_attendance = StaffAttendance.query.filter_by(
            staff_id=person.id, 
            date=today
        ).first()
        attendance_model = StaffAttendance
        person_id_field = 'staff_id'
    
    if existing_attendance:
        return jsonify({
            'status': 'warning', 
            'message': f'⚠️ Already Marked Today',
            'subtitle': f'{person.name} ({person_type.title()}) attendance already recorded at {existing_attendance.time.strftime("%H:%M")}',
            'person_name': person.name,
            'person_type': person_type,
            'already_marked': True,
            'existing_time': existing_attendance.time.strftime("%H:%M"),
            'existing_status': existing_attendance.status,
            'icon': 'fas fa-clock',
            'color': 'warning',
            'sound': 'warning'
        }), 200
    
    # Determine attendance status based on time
    status = check_attendance_time()
    current_time = datetime.now().time()
    
    # Create attendance record
    attendance_data = {
        person_id_field: person.id,
        'date': today,
        'time': current_time,
        'status': status
    }
    
    attendance_record = attendance_model(**attendance_data)
    
    try:
        db.session.add(attendance_record)
        db.session.commit()
        print(f"[SUCCESS] ✅ Attendance marked for {person.name} ({person_type}) - Status: {status}")
        
        # Send SMS notification for students (if parent phone available)
        sms_sent = False
        if person_type == 'student' and hasattr(person, 'parent_phone') and person.parent_phone:
            if status in ['late', 'absent']:
                if status == 'late':
                    message = f"Dear Parent, {person.name} arrived late to school at {current_time.strftime('%H:%M')}. Please ensure punctuality."
                else:
                    message = f"Dear Parent, {person.name} was marked absent today. Please contact school for details."
                
                sms_sent = send_sms_notification(person.parent_phone, message)
        
        # Prepare success response with enhanced data
        status_config = {
            'present': {
                'emoji': '✅',
                'icon': 'fas fa-check-circle',
                'color': 'success',
                'sound': 'success',
                'title': 'Attendance Marked Successfully!'
            },
            'late': {
                'emoji': '⚠️',
                'icon': 'fas fa-exclamation-triangle', 
                'color': 'warning',
                'sound': 'warning',
                'title': 'Marked as Late'
            },
            'absent': {
                'emoji': '❌',
                'icon': 'fas fa-times-circle',
                'color': 'danger', 
                'sound': 'error',
                'title': 'Marked as Absent'
            }
        }
        
        config = status_config.get(status, status_config['present'])
        
        return jsonify({
            'status': 'success', 
            'message': f'{config["emoji"]} {config["title"]}',
            'subtitle': f'{person.name} ({person_type.title()}) - {status.upper()} at {current_time.strftime("%H:%M")}',
            'person_name': person.name,
            'person_type': person_type,
            'attendance_status': status,
            'time': current_time.strftime('%H:%M'),
            'date': today.strftime('%B %d, %Y'),
            'sms_sent': sms_sent,
            'icon': config['icon'],
            'color': config['color'],
            'sound': config['sound'],
            'department': person.department if hasattr(person, 'department') else 'N/A',
            'auto_close': True  # Auto close scanner after success
        }), 201
        
    except Exception as e:
        print(f"[ERROR] ❌ Failed to mark attendance: {e}")
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': '❌ Database Error',
            'subtitle': 'Failed to mark attendance. Please try again.',
            'error_details': str(e),
            'icon': 'fas fa-database',
            'color': 'danger',
            'sound': 'error'
        }), 500


@app.route('/scan_staff_barcode', methods=['POST'])
def scan_staff_barcode():
    """Specific route for staff barcode scanning from staff attendance page"""
    data = request.get_json(silent=True) or {}
    barcode_data = data.get('barcode')
    
    if not barcode_data:
        return jsonify({'status': 'error', 'message': 'No barcode data received'}), 400
    
    print(f"[INFO] Staff barcode scan attempt: {barcode_data}")
    
    # Find staff by barcode
    staff = Staff.query.filter_by(barcode=barcode_data).first()
    
    if not staff:
        print(f"[ERROR] Staff not found for barcode: {barcode_data}")
        return jsonify({'status': 'error', 'message': 'Invalid staff barcode'}), 404
    
    # Check if already marked today
    today = datetime.now().date()
    existing_attendance = StaffAttendance.query.filter_by(
        staff_id=staff.id, 
        date=today
    ).first()
    
    if existing_attendance:
        return jsonify({
            'status': 'warning', 
            'message': f'Attendance already marked for {staff.name} today at {existing_attendance.time.strftime("%H:%M")}'
        }), 200
    
    # Determine attendance status based on time
    status = check_attendance_time()
    current_time = datetime.now().time()
    
    # Create staff attendance record
    attendance = StaffAttendance(
        staff_id=staff.id,
        date=today,
        time=current_time,
        status=status
    )
    
    try:
        db.session.add(attendance)
        db.session.commit()
        print(f"[SUCCESS] Staff attendance marked for {staff.name}")
        
        return jsonify({
            'status': 'success', 
            'message': f'Staff attendance marked for {staff.name} - Status: {status.upper()}',
            'staff_name': staff.name,
            'attendance_status': status,
            'time': current_time.strftime('%H:%M')
        }), 201
        
    except Exception as e:
        print(f"[ERROR] Failed to mark staff attendance: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to mark attendance'
        }), 500


@app.route('/download_reports')
@login_required
def download_reports():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('login'))
    
    print("[INFO] Generating comprehensive attendance report...")
    
    # Create CSV content as string
    csv_lines = []
    csv_lines.append('Type,Name,ID/Reg No,Department,Date,Time,Status,Contact Phone')
    
    # Get student attendance data
    student_records = db.session.query(Attendance, Student).join(Student).all()
    for attendance, student in student_records:
        line = f'"Student","{student.name}","{student.reg_no}","{student.department}","{attendance.date.strftime("%Y-%m-%d")}","{attendance.time.strftime("%H:%M:%S")}","{attendance.status}","{student.parent_phone}"'
        csv_lines.append(line)
    
    # Get staff attendance data
    staff_records = db.session.query(StaffAttendance, Staff).join(Staff).all()
    for attendance, staff in staff_records:
        line = f'"Staff","{staff.name}","{staff.id}","{staff.department}","{attendance.date.strftime("%Y-%m-%d")}","{attendance.time.strftime("%H:%M:%S")}","{attendance.status}","N/A"'
        csv_lines.append(line)
    
    # Join all lines with newlines
    csv_content = '\n'.join(csv_lines)
    
    # Create response
    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=comprehensive_attendance_report_{datetime.now().strftime("%Y%m%d")}.csv'
    
    print("[SUCCESS] Comprehensive report generated successfully")
    return response


@app.route('/all_students')
@login_required
def all_students():
    # Allow both admin and staff to view students
    students = Student.query.all()
    student_data = []
    
    for student in students:
        student_data.append({
            'id': student.id,
            'name': student.name,
            'reg_no': student.reg_no,
            'department': student.department,
            'parent_phone': student.parent_phone,
            'attendance_percentage': student.get_attendance_percentage(),
            'total_days': len(student.attendance_records)
        })
    
    return render_template('all_students.html', students=student_data)


@app.route('/attendance_statistics')
@login_required
def attendance_statistics():
    """Get real-time attendance statistics for dashboard"""
    today = datetime.now().date()
    
    # Student statistics
    total_students = Student.query.count()
    students_present_today = Attendance.query.filter_by(date=today, status='present').count()
    students_late_today = Attendance.query.filter_by(date=today, status='late').count()
    students_marked_today = Attendance.query.filter_by(date=today).count()
    students_absent_today = total_students - students_marked_today
    
    # Staff statistics
    total_staff = Staff.query.count()
    staff_present_today = StaffAttendance.query.filter_by(date=today, status='present').count()
    staff_late_today = StaffAttendance.query.filter_by(date=today, status='late').count()
    staff_marked_today = StaffAttendance.query.filter_by(date=today).count()
    staff_absent_today = total_staff - staff_marked_today
    
    return jsonify({
        'students': {
            'total': total_students,
            'present': students_present_today,
            'late': students_late_today,
            'absent': students_absent_today,
            'marked': students_marked_today
        },
        'staff': {
            'total': total_staff,
            'present': staff_present_today,
            'late': staff_late_today,
            'absent': staff_absent_today,
            'marked': staff_marked_today
        },
        'date': today.strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M:%S')
    })


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('login.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('login.html'), 500


if __name__ == '__main__':
    with app.app_context():
        print("[INFO] 🚀 Initializing enhanced attendance management system...")
        db.create_all()
        
        # Create default admin if not exists
        admin = Admin.query.filter_by(username='admin').first()
        if not admin:
            print("[SETUP] 👤 Creating default admin user...")
            admin = Admin(username='admin')
            admin.set_password('admin123')
            admin.is_admin = True
            db.session.add(admin)
            db.session.commit()
            print("[SUCCESS] ✅ Default admin created: username=admin, password=admin123")
        else:
            print("[INFO] ℹ️ Default admin already exists")
    
    print("[STARTUP] 🎯 Starting ENHANCED attendance system with TODAY'S FEATURES...")
    print("[INFO] 📷 Real-time QR scanner with proper camera shutdown")
    print("[INFO] 🎨 Enhanced login page with modern design")
    print("[INFO] 📊 Student attendance reports FIXED - redirects to All Students")
    print("[INFO] 🔄 Fixed navigation back to dashboard")
    print("[INFO] ✨ NEW: Today's Students feature enabled")
    print("[INFO] ⭐ NEW: Today's Staff feature enabled")
    print("[INFO] 📥 NEW: Daily reports download enabled")
    print("[INFO] 🌐 Access your app at: http://127.0.0.1:5000")
    print("[INFO] 🔐 Admin login: admin / admin123")
    print("[SUCCESS] ✅ ALL FEATURES WORKING - Quick Actions fully enabled!")
    app.run(debug=True, host='127.0.0.1', port=5000)
