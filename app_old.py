from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import qrcode
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
import base64
from datetime import datetime, time, timedelta
import uuid
from twilio.rest import Client
import csv
from models import db, Admin, Staff, Student, Attendance
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize Twilio client
twilio_client = Client(app.config['TWILIO_ACCOUNT_SID'], app.config['TWILIO_AUTH_TOKEN'])

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
    try:
        message = twilio_client.messages.create(
            body=message,
            from_=app.config['TWILIO_PHONE_NUMBER'],
            to=phone_number
        )
        return True
    except Exception as e:
        print(f"SMS Error: {e}")
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
        flash('Access denied')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        department = request.form['department']
        password = request.form['password']
        
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
        
        flash('Staff registered successfully')
        return render_template('register_staff.html', 
                             success=True, 
                             barcode=barcode_str, 
                             qr_code=qr_code)
    
    return render_template('register_staff.html')

@app.route('/register_student', methods=['GET', 'POST'])
@login_required
def register_student():
    if request.method == 'POST':
        name = request.form['name']
        reg_no = request.form['reg_no']
        department = request.form['department']
        parent_phone = request.form['parent_phone']
        
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

@app.route('/scan_barcode', methods=['POST'])
def scan_barcode():
    barcode_data = request.json.get('barcode')
    
    if not barcode_data:
        return jsonify({'status': 'error', 'message': 'No barcode data received'})
    
    # Find student by barcode
    student = Student.query.filter_by(barcode=barcode_data).first()
    
    if not student:
        return jsonify({'status': 'error', 'message': 'Invalid barcode'})
    
    # Check if already marked today
    today = datetime.now().date()
    existing_attendance = Attendance.query.filter_by(
        student_id=student.id, 
        date=today
    ).first()
    
    if existing_attendance:
        return jsonify({
            'status': 'warning', 
            'message': f'Attendance already marked for {student.name} today'
        })
    
    # Determine attendance status based on time
    status = check_attendance_time()
    current_time = datetime.now().time()
    
    # Create attendance record
    attendance = Attendance(
        student_id=student.id,
        date=today,
        time=current_time,
        status=status
    )
    
    db.session.add(attendance)
    db.session.commit()
    
    # Send SMS notification to parent
    if status in ['absent', 'late']:
        if status == 'late':
            message = f"Dear Parent, {student.name} arrived late to school at {current_time.strftime('%H:%M')}. Please ensure punctuality."
        else:
            message = f"Dear Parent, {student.name} was marked absent today. Please contact school for details."
        
        send_sms_notification(student.parent_phone, message)
    
    return jsonify({
        'status': 'success', 
        'message': f'Attendance marked for {student.name} - Status: {status.upper()}',
        'student_name': student.name,
        'attendance_status': status,
        'time': current_time.strftime('%H:%M')
    })

@app.route('/download_reports')
@login_required
def download_reports():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('login'))
    
    # Create CSV response
    output = BytesIO()
    
    # Prepare CSV data
    csv_data = []
    csv_data.append(['Student Name', 'Reg No', 'Department', 'Date', 'Time', 'Status', 'Parent Phone'])
    
    # Write attendance data
    attendance_records = db.session.query(Attendance, Student).join(Student).all()
    
    for attendance, student in attendance_records:
        csv_data.append([
            student.name,
            student.reg_no,
            student.department,
            attendance.date.strftime('%Y-%m-%d'),
            attendance.time.strftime('%H:%M:%S'),
            attendance.status,
            student.parent_phone
        ])
    
    # Convert to CSV format
    output_text = '\n'.join([','.join(row) for row in csv_data])
    
    response = make_response(output_text)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=attendance_report_{datetime.now().strftime("%Y%m%d")}.csv'
    
    return response

@app.route('/all_students')
@login_required
def all_students():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('login'))
    
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create default admin if not exists
        admin = Admin.query.filter_by(username='admin').first()
        if not admin:
            print("[SETUP] Creating default admin user...")
            admin = Admin(username='admin')
            admin.set_password('admin123')
            admin.is_admin = True
            db.session.add(admin)
            db.session.commit()
            print("[SUCCESS] Default admin created: username=admin, password=admin123")
        else:
            print("[INFO] Default admin already exists")
    
    print("[STARTUP] Starting Flask application...")
    app.run(debug=True)
