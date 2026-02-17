from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from datetime import date, datetime
from flask import jsonify

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DATABASE ----------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------- MODELS ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # Student fields
    roll_number = db.Column(db.String(20), nullable=True)
    branch = db.Column(db.String(100), nullable=True)
    semester = db.Column(db.String(20), nullable=True)

    # Teacher fields
    department = db.Column(db.String(100), nullable=True)
    subject = db.Column(db.String(100), nullable=True)


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    branch = db.Column(db.String(100), nullable=True)
    semester = db.Column(db.String(20), nullable=True)

    # added fields required by the templates / routes
    date = db.Column(db.Date, nullable=False, default=date.today)
    status = db.Column(db.String(20), nullable=False, default='absent')

    # optional convenience relationships
    student = db.relationship('User', foreign_keys=[student_id], backref='attendance_as_student')
    teacher = db.relationship('User', foreign_keys=[teacher_id], backref='attendance_as_teacher')


# ---------------- ROOT ----------------
@app.route('/')
def root():
    return redirect(url_for('login'))


# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get('role').lower()
        email = request.form.get('email').lower()
        password = request.form.get('password')

        user = User.query.filter(func.lower(User.email) == email).first()

        if not user or user.role != role or not check_password_hash(user.password, password):
            flash("Invalid login details!")
            return render_template("login.html")

        session['user_id'] = user.id
        session['role'] = user.role

        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        if user.role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        if user.role == 'student':
            return redirect(url_for('student_dashboard'))

    return render_template("login.html")


# ---------------- ADMIN ----------------
@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin': abort(403)

    students = User.query.filter_by(role='student').all()
    teachers = User.query.filter_by(role='teacher').all()
    total_attendance = Attendance.query.count()

    return render_template("admin.html",
                           students=students,
                           teachers=teachers,
                           total_attendance=total_attendance)


@app.route('/admin/students')
def manage_students():
    if session.get('role') != 'admin': abort(403)
    return render_template("manage_students.html",
                           students=User.query.filter_by(role='student').all())


@app.route('/admin/student/add', methods=['GET', 'POST'])
def add_student():
    if session.get('role') != 'admin': abort(403)

    if request.method == 'POST':
        u = User(
            name=request.form['name'],
            email=request.form['email'].lower(),
            password=generate_password_hash(request.form['password']),
            role='student',
            roll_number=request.form['roll_number']
        )
        db.session.add(u)
        db.session.commit()
        return redirect(url_for('manage_students'))

    return render_template("add_student.html")


@app.route('/admin/student/edit/<int:id>', methods=['GET', 'POST'])
def edit_student(id):
    if session.get('role') != 'admin': abort(403)
    student = User.query.get_or_404(id)
    if request.method == 'POST':
        student.name = request.form.get('name', student.name)
        student.email = request.form.get('email', student.email).lower()
        pwd = request.form.get('password', '').strip()
        if pwd:
            student.password = generate_password_hash(pwd)
        student.roll_number = request.form.get('roll_number', student.roll_number)
        db.session.commit()
        flash("Student updated.")
        return redirect(url_for('manage_students'))
    return render_template('edit_student.html', student=student)


@app.route('/admin/student/delete/<int:id>')
def delete_student(id):
    if session.get('role') != 'admin': abort(403)
    db.session.delete(User.query.get_or_404(id))
    db.session.commit()
    flash("Student deleted.")
    return redirect(url_for('manage_students'))


# ---------- TEACHERS ----------
@app.route('/admin/teachers')
def manage_teachers():
    if session.get('role') != 'admin': abort(403)
    return render_template("manage_teachers.html",
                           teachers=User.query.filter_by(role='teacher').all())


@app.route('/admin/teacher/add', methods=['GET', 'POST'])
def add_teacher():
    if session.get('role') != 'admin': abort(403)

    if request.method == 'POST':
        t = User(
            name=request.form['name'],
            email=request.form['email'].lower(),
            password=generate_password_hash(request.form['password']),
            role='teacher',
            department=request.form['department'],
            subject=request.form['subject']
        )
        db.session.add(t)
        db.session.commit()
        return redirect(url_for('manage_teachers'))

    return render_template("add_teacher.html")


@app.route('/admin/teacher/edit/<int:id>', methods=['GET', 'POST'])
def edit_teacher(id):
    if session.get('role') != 'admin': abort(403)
    teacher = User.query.get_or_404(id)
    if request.method == 'POST':
        teacher.name = request.form.get('name', teacher.name)
        teacher.email = request.form.get('email', teacher.email).lower()
        pwd = request.form.get('password', '').strip()
        if pwd:
            teacher.password = generate_password_hash(pwd)
        teacher.department = request.form.get('department', teacher.department)
        teacher.subject = request.form.get('subject', teacher.subject)
        db.session.commit()
        flash("Teacher updated.")
        return redirect(url_for('manage_teachers'))
    return render_template('edit_teacher.html', teacher=teacher)


@app.route('/admin/teacher/delete/<int:id>')
def delete_teacher(id):
    if session.get('role') != 'admin': abort(403)
    db.session.delete(User.query.get_or_404(id))
    db.session.commit()
    flash("Teacher deleted.")
    return redirect(url_for('manage_teachers'))


# ---------------- TEACHER ----------------
@app.route('/teacher')
def teacher_dashboard():
    if session.get('role') != 'teacher': abort(403)
    teacher = User.query.get(session['user_id'])
    students = User.query.filter_by(role='student').all()
    return render_template("teacher.html", teacher=teacher, students=students)


# SELECT BRANCH AND SEMESTER FOR MARKING
@app.route('/teacher/select-class-mark', methods=['GET', 'POST'])
def select_class_mark():
    if session.get('role') != 'teacher': abort(403)
    
    if request.method == 'POST':
        branch = request.form.get('branch')
        semester = request.form.get('semester')
        return redirect(url_for('mark_attendance', branch=branch, semester=semester))
    
    # Get unique branches and semesters from students
    branches = db.session.query(User.branch).filter_by(role='student').distinct().all()
    semesters = db.session.query(User.semester).filter_by(role='student').distinct().all()
    
    branches = sorted([b[0] for b in branches if b[0]])
    semesters = sorted([s[0] for s in semesters if s[0]])
    
    return render_template('select_class.html', 
                           page_title='Select Branch & Semester',
                           action='mark_attendance',
                           branches=branches,
                           semesters=semesters)


# SELECT BRANCH AND SEMESTER FOR VIEWING
@app.route('/teacher/select-class-view', methods=['GET', 'POST'])
def select_class_view():
    if session.get('role') != 'teacher': abort(403)
    
    if request.method == 'POST':
        branch = request.form.get('branch')
        semester = request.form.get('semester')
        return redirect(url_for('view_attendance', branch=branch, semester=semester))
    
    # Get unique branches and semesters from students
    branches = db.session.query(User.branch).filter_by(role='student').distinct().all()
    semesters = db.session.query(User.semester).filter_by(role='student').distinct().all()
    
    branches = sorted([b[0] for b in branches if b[0]])
    semesters = sorted([s[0] for s in semesters if s[0]])
    
    return render_template('select_class.html',
                           page_title='Select Branch & Semester',
                           action='view_attendance',
                           branches=branches,
                           semesters=semesters)


@app.route('/teacher/mark', methods=['GET', 'POST'])
def mark_attendance():
    if session.get('role') != 'teacher': abort(403)

    branch = request.args.get('branch')
    semester = request.args.get('semester')
    
    if not branch or not semester:
        return redirect(url_for('select_class_mark'))

    teacher = User.query.get(session['user_id'])
    students = User.query.filter_by(role='student', branch=branch, semester=semester).all()

    if request.method == 'POST':
        today = date.today()

        Attendance.query.filter_by(
            date=today,
            teacher_id=teacher.id,
            subject=teacher.subject,
            branch=branch,
            semester=semester
        ).delete()

        for s in students:
            status = request.form.get(str(s.id))
            if status:
                db.session.add(Attendance(
                    student_id=s.id,
                    teacher_id=teacher.id,
                    subject=teacher.subject,
                    branch=branch,
                    semester=semester,
                    date=today,
                    status=status
                ))

        db.session.commit()
        flash("Attendance Marked!")
        return redirect(url_for('teacher_dashboard'))

    return render_template("mark_attendance.html",
                           students=students,
                           subject=teacher.subject,
                           teacher=teacher,
                           branch=branch,
                           semester=semester)


# ---------------- TEACHER VIEW WITH FILTERS ----------------
@app.route('/teacher/view', methods=['GET', 'POST'])
def view_attendance():
    if session.get('role') != 'teacher':
        abort(403)
    
    branch = request.args.get('branch')
    semester = request.args.get('semester')
    
    if not branch or not semester:
        return redirect(url_for('select_class_view'))
        
    teacher = User.query.get(session.get('user_id'))

    # teacher's subject is fixed — do not allow choosing other subjects
    selected_subject = teacher.subject if teacher and teacher.subject else None

    # read date filter only
    selected_date = None
    if request.method == 'POST':
        sd = (request.form.get('selected_date') or '').strip()
        if sd:
            try:
                selected_date = date.fromisoformat(sd)
            except Exception:
                selected_date = None
    else:
        sd = request.args.get('date', '').strip()
        if sd:
            try:
                selected_date = date.fromisoformat(sd)
            except Exception:
                selected_date = None

    # build query — filter by teacher, teacher's subject, branch and semester
    q = Attendance.query.filter_by(teacher_id=teacher.id, branch=branch, semester=semester)
    if selected_subject:
        q = q.filter_by(subject=selected_subject)
    if selected_date:
        q = q.filter_by(date=selected_date)

    records = q.order_by(Attendance.date.desc(), Attendance.id.desc()).all()
    for r in records:
        r.student_obj = User.query.get(r.student_id)

    return render_template(
        'view_attendance.html',
        teacher=teacher,
        records=records,
        selected_date=(selected_date.isoformat() if selected_date else ''),
        selected_subject=selected_subject,
        branch=branch,
        semester=semester
    )


# ---------------- STUDENT ----------------
@app.route('/student', methods=['GET', 'POST'])
def student_dashboard():
    if session.get('role') != 'student':
        abort(403)

    student_id = session['user_id']
    student = User.query.get(student_id)

    teachers = User.query.filter_by(role='teacher').all()
    selected_subject = request.form.get("subject")
    selected_date = request.form.get("selected_date")

    query = Attendance.query.filter_by(student_id=student_id)

    if selected_subject:
        query = query.filter_by(subject=selected_subject)

    if selected_date:
        selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
        query = query.filter_by(date=selected_date)

    records = query.all()

    # Filtered stats
    total_days = len(records)
    present_days = sum(1 for r in records if r.status.lower() == "present")
    absent_days = total_days - present_days
    percentage = round((present_days / total_days) * 100, 2) if total_days > 0 else 0

    # ------------------------------------------
    # 1. OVERALL ATTENDANCE (All subjects, all dates)
    # ------------------------------------------
    all_records = Attendance.query.filter_by(student_id=student_id).all()
    all_total = len(all_records)
    all_present = sum(1 for r in all_records if r.status.lower() == "present")
    overall_percentage = round((all_present / all_total) * 100, 2) if all_total > 0 else 0

    # ------------------------------------------
    # 2. MONTHLY ATTENDANCE
    # ------------------------------------------
    today = date.today()
    first_day = today.replace(day=1)

    monthly_records = Attendance.query.filter(
        Attendance.student_id == student_id,
        Attendance.date >= first_day,
        Attendance.date <= today
    ).all()

    monthly_total = len(monthly_records)
    monthly_present = sum(1 for r in monthly_records if r.status.lower() == "present")
    monthly_percentage = round((monthly_present / monthly_total) * 100, 2) if monthly_total > 0 else 0

    today_record = Attendance.query.filter_by(student_id=student_id, date=date.today()).first()
    subjects = get_all_subjects()

    return render_template("student.html",
                           student=student,
                           teachers=teachers,
                           selected_subject=selected_subject,
                           selected_date=selected_date,
                           records=records,
                           total_days=total_days,
                           present_days=present_days,
                           absent_days=absent_days,
                           percentage=percentage,
                           today_record=today_record,
                           subjects=subjects,
                           overall_percentage=overall_percentage,
                           monthly_percentage=monthly_percentage)



@app.route('/student/subjects')
def student_subjects():
    if session.get('role') != 'student':
        abort(403)

    student = User.query.get(session.get('user_id'))
    if not student:
        abort(404)

    # --- subjects where this student has any record ---
    rows = db.session.query(Attendance.subject).filter_by(student_id=student.id).distinct().all()
    subjects = [r[0] for r in rows]

    fallback = False

    # fallback: if student has no records, show all subjects in system
    if not subjects:
        rows_all = db.session.query(Attendance.subject).distinct().all()
        subjects = [r[0] for r in rows_all]
        fallback = True

    subjects_info = []

    for s in subjects:
        # total distinct dates (classes)
        total_sessions = db.session.query(func.count(func.distinct(Attendance.date))) \
                                   .filter_by(subject=s).scalar() or 0

        # FIXED: present count ignoring case differences
        present_count = db.session.query(Attendance).filter(
            Attendance.subject == s,
            Attendance.student_id == student.id,
            func.lower(Attendance.status) == 'present'
        ).count()

        # last class date
        last_rec = db.session.query(Attendance.date).filter_by(subject=s) \
                        .order_by(Attendance.date.desc()).first()
        last_date = last_rec[0].isoformat() if last_rec else None

        # teacher names for this subject
        teacher_rows = db.session.query(User.name).join(
            Attendance, Attendance.teacher_id == User.id
        ).filter(Attendance.subject == s).distinct().all()
        teacher_names = ', '.join([t[0] for t in teacher_rows]) if teacher_rows else ''

        # calculate percentage
        percent = round((present_count / total_sessions) * 100, 1) if total_sessions > 0 else 0

        # check if student has any attendance in this subject
        enrolled = Attendance.query.filter_by(subject=s, student_id=student.id).count() > 0

        subjects_info.append({
            'subject': s,
            'total_sessions': total_sessions,
            'present_count': present_count,
            'present_percent': percent,
            'last_date': last_date,
            'teachers': teacher_names,
            'enrolled': enrolled
        })

    return render_template('student_subjects.html',
                           student=student,
                           subjects_info=subjects_info,
                           fallback=fallback)


@app.route('/student/subject/<path:subject>/details')
def student_subject_details(subject):
    if session.get('role') != 'student':
        abort(403)
    student_id = session.get('user_id')

    # total distinct session dates for this subject (class-wide)
    total_sessions = db.session.query(func.count(func.distinct(Attendance.date))).filter_by(subject=subject).scalar() or 0

    # count present for this student
    present_count = Attendance.query.filter_by(subject=subject, student_id=student_id, status='present').count()

    # per-session history for this student (date + status)
    hist_rows = db.session.query(Attendance.date, Attendance.status) \
               .filter_by(subject=subject, student_id=student_id) \
               .order_by(Attendance.date).all()
    history = [{'date': r[0].isoformat(), 'status': r[1]} for r in hist_rows]

    return jsonify({
        'subject': subject,
        'total_sessions': total_sessions,
        'present_count': present_count,
        'present_percent': round((present_count / total_sessions) * 100, 1) if total_sessions > 0 else 0.0,
        'history': history
    })


@app.route('/student/classes')
def student_classes():
    if session.get('role') != 'student':
        abort(403)
    student = User.query.get(session.get('user_id'))
    # build per-subject attendance stats for this student
    rows = db.session.query(Attendance.subject).filter_by(student_id=student.id).distinct().all()
    subjects = [r[0] for r in rows if r[0]]
    classes_stats = []
    for subj in subjects:
        total = Attendance.query.filter_by(student_id=student.id, subject=subj).count()
        present = Attendance.query.filter(Attendance.student_id==student.id,
                                          Attendance.subject==subj,
                                          func.lower(Attendance.status)=='present').count()
        pct = round((present/total)*100,2) if total>0 else 0
        classes_stats.append({'subject': subj, 'total': total, 'present': present, 'percentage': pct})
    return render_template('student_classes.html', student=student, classes_stats=classes_stats)


@app.route('/student/attendance')
def student_attendance():
    if session.get('role') != 'student':
        abort(403)
    student = User.query.get(session.get('user_id'))
    records = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.date.desc()).all()
    for r in records:
        r.teacher_obj = User.query.get(r.teacher_id)
    return render_template('student_attendance.html', student=student, records=records)


# ---------------- REPORTS ----------------
@app.route('/reports')
def reports():
    if session.get('role') != 'admin':
        abort(403)

    # totals (existing)
    total_students = User.query.filter_by(role='student').count()
    total_teachers = User.query.filter_by(role='teacher').count()
    total_attendance = Attendance.query.count()

    # Attendance by subject
    subjects = [row[0] for row in db.session.query(Attendance.subject).distinct().all()]
    attendance_by_subject = []
    for subj in subjects:
        total = Attendance.query.filter_by(subject=subj).count()
        present = Attendance.query.filter(Attendance.subject==subj, func.lower(Attendance.status)=='present').count()
        pct = round((present / total) * 100, 2) if total > 0 else 0
        attendance_by_subject.append({'subject': subj, 'total': total, 'present': present, 'percentage': pct})

    # Attendance by teacher
    teachers = User.query.filter_by(role='teacher').all()
    attendance_by_teacher = []
    for t in teachers:
        total = Attendance.query.filter_by(teacher_id=t.id).count()
        present = Attendance.query.filter(Attendance.teacher_id==t.id, func.lower(Attendance.status)=='present').count()
        pct = round((present / total) * 100, 2) if total > 0 else 0
        attendance_by_teacher.append({'teacher': t.name, 'total': total, 'present': present, 'percentage': pct})

    # Students with lowest attendance (overall) - top 10
    students = User.query.filter_by(role='student').all()
    student_stats = []
    for s in students:
        total = Attendance.query.filter_by(student_id=s.id).count()
        present = Attendance.query.filter(Attendance.student_id==s.id, func.lower(Attendance.status)=='present').count()
        pct = round((present / total) * 100, 2) if total > 0 else None
        student_stats.append({'id': s.id, 'name': s.name, 'email': s.email, 'total': total, 'present': present, 'percentage': pct})
    low_attendance = sorted([x for x in student_stats if x['percentage'] is not None], key=lambda r: r['percentage'])[:10]

    # Recent attendance entries
    recent_records = Attendance.query.order_by(Attendance.date.desc(), Attendance.id.desc()).limit(12).all()
    # attach student & teacher names for display
    for r in recent_records:
        r.student_obj = User.query.get(r.student_id)
        r.teacher_obj = User.query.get(r.teacher_id)

    return render_template(
        'reports.html',
        total_students=total_students,
        total_teachers=total_teachers,
        total_attendance=total_attendance,
        attendance_by_subject=attendance_by_subject,
        attendance_by_teacher=attendance_by_teacher,
        low_attendance=low_attendance,
        recent_records=recent_records
    )


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------------- TEACHER CLASSES ----------------
@app.route('/teacher/classes')
def teacher_classes():
    if session.get('role') != 'teacher':
        abort(403)
    teacher = User.query.get(session.get('user_id'))

    # build unique class list (teacher.subject + subjects from attendance)
    classes = []
    if teacher and teacher.subject:
        classes.append(teacher.subject)
    if teacher:
        subjects = [row[0] for row in db.session.query(Attendance.subject)
                    .filter_by(teacher_id=teacher.id).distinct().all() or []]
        for s in subjects:
            if s and s not in classes:
                classes.append(s)

    # build richer info for each class (sessions count, distinct students, last session date)
    classes_info = []
    for s in classes:
        total_sessions = Attendance.query.filter_by(teacher_id=teacher.id, subject=s).count()
        last_rec = Attendance.query.filter_by(teacher_id=teacher.id, subject=s).order_by(Attendance.date.desc()).first()
        last_date = last_rec.date.isoformat() if last_rec else None
        students_count = db.session.query(Attendance.student_id).filter_by(teacher_id=teacher.id, subject=s).distinct().count()
        classes_info.append({
            'subject': s,
            'total_sessions': total_sessions,
            'last_date': last_date,
            'students_count': students_count
        })

    return render_template('teacher_classes.html', teacher=teacher, classes_info=classes_info)


# ---------------- UTILITY FUNCTIONS ----------------
def get_all_subjects():
    subs = set()
    # from attendance table
    rows = db.session.query(Attendance.subject).distinct().all()
    for r in rows:
        s = (r[0] or "").strip()
        if s:
            subs.add(s)
    # from teacher records
    for t in User.query.filter_by(role='teacher').all():
        s = (t.subject or "").strip()
        if s:
            subs.add(s)
    return sorted(subs)


# ---------------- MAIN ----------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # ONLY CREATE DEFAULT USERS IF DB IS EMPTY
        if User.query.count() == 0:
            admin = User(
                name="Admin",
                email="admin@gmail.com",
                password=generate_password_hash("admin123"),
                role="admin"
            )
            teacher = User(
                name="Mr. Sharma",
                email="teacher@gmail.com",
                password=generate_password_hash("teacher123"),
                role="teacher",
                department="CS",
                subject="Web Development"
            )
            
            # Create 75 students - 5 from each branch, each for semester 2, 4, and 6
            students_data = [
                # Computer Science
                ("Amit Kumar", "amit1@gmail.com", "CS101", "Computer Science", "2"),
                ("Priya Singh", "priya1@gmail.com", "CS102", "Computer Science", "2"),
                ("Rajesh Patel", "rajesh1@gmail.com", "CS103", "Computer Science", "2"),
                ("Deepak Verma", "deepak1@gmail.com", "CS104", "Computer Science", "2"),
                ("Ananya Sharma", "ananya1@gmail.com", "CS105", "Computer Science", "2"),
                
                ("Arjun Kumar", "arjun1@gmail.com", "CS201", "Computer Science", "4"),
                ("Divya Sharma", "divya1@gmail.com", "CS202", "Computer Science", "4"),
                ("Vikram Singh", "vikram1@gmail.com", "CS203", "Computer Science", "4"),
                ("Sneha Gupta", "sneha1@gmail.com", "CS204", "Computer Science", "4"),
                ("Harsh Verma", "harsh1@gmail.com", "CS205", "Computer Science", "4"),
                
                ("Yash Malhotra", "yash1@gmail.com", "CS301", "Computer Science", "6"),
                ("Zara Khan", "zara1@gmail.com", "CS302", "Computer Science", "6"),
                ("Abhishek Roy", "abhishek1@gmail.com", "CS303", "Computer Science", "6"),
                ("Bhavna Desai", "bhavna1@gmail.com", "CS304", "Computer Science", "6"),
                ("Chirag Joshi", "chirag1@gmail.com", "CS305", "Computer Science", "6"),
                
                # Electronics
                ("Aman Nair", "aman1@gmail.com", "EC101", "Electronics", "2"),
                ("Bhavya Gupta", "bhavya1@gmail.com", "EC102", "Electronics", "2"),
                ("Chhavi Singh", "chhavi1@gmail.com", "EC103", "Electronics", "2"),
                ("Disha Sharma", "disha1@gmail.com", "EC104", "Electronics", "2"),
                ("Esha Kapoor", "esha1@gmail.com", "EC105", "Electronics", "2"),
                
                ("Faisal Khan", "faisal1@gmail.com", "EC201", "Electronics", "4"),
                ("Geet Patel", "geet1@gmail.com", "EC202", "Electronics", "4"),
                ("Harsh Yadav", "harsh2@gmail.com", "EC203", "Electronics", "4"),
                ("Isha Reddy", "isha1@gmail.com", "EC204", "Electronics", "4"),
                ("Jay Pillai", "jay1@gmail.com", "EC205", "Electronics", "4"),
                
                ("Karim Ahmed", "karim1@gmail.com", "EC301", "Electronics", "6"),
                ("Laxmi Roy", "laxmi1@gmail.com", "EC302", "Electronics", "6"),
                ("Mona Singh", "mona1@gmail.com", "EC303", "Electronics", "6"),
                ("Nina Sharma", "nina1@gmail.com", "EC304", "Electronics", "6"),
                ("Omprakash Rao", "omprakash1@gmail.com", "EC305", "Electronics", "6"),
                
                # Electrical
                ("Pankaj Kumar", "pankaj1@gmail.com", "EE101", "Electrical", "2"),
                ("Qureshi Ali", "qureshi1@gmail.com", "EE102", "Electrical", "2"),
                ("Rahul Singh", "rahul1@gmail.com", "EE103", "Electrical", "2"),
                ("Seema Gupta", "seema1@gmail.com", "EE104", "Electrical", "2"),
                ("Tarun Verma", "tarun1@gmail.com", "EE105", "Electrical", "2"),
                
                ("Uma Sharma", "uma1@gmail.com", "EE201", "Electrical", "4"),
                ("Varun Reddy", "varun1@gmail.com", "EE202", "Electrical", "4"),
                ("Wanira Khan", "wanira1@gmail.com", "EE203", "Electrical", "4"),
                ("Xander Nair", "xander1@gmail.com", "EE204", "Electrical", "4"),
                ("Yasmin Kapoor", "yasmin1@gmail.com", "EE205", "Electrical", "4"),
                
                ("Zahra Ahmed", "zahra1@gmail.com", "EE301", "Electrical", "6"),
                ("Anil Desai", "anil1@gmail.com", "EE302", "Electrical", "6"),
                ("Bharti Singh", "bharti1@gmail.com", "EE303", "Electrical", "6"),
                ("Chandan Yadav", "chandan1@gmail.com", "EE304", "Electrical", "6"),
                ("Dipti Joshi", "dipti1@gmail.com", "EE305", "Electrical", "6"),
                
                # Instrumentation
                ("Ekansh Roy", "ekansh1@gmail.com", "IN101", "Instrumentation", "2"),
                ("Farida Khan", "farida1@gmail.com", "IN102", "Instrumentation", "2"),
                ("Gaurav Patel", "gaurav1@gmail.com", "IN103", "Instrumentation", "2"),
                ("Hetal Sharma", "hetal1@gmail.com", "IN104", "Instrumentation", "2"),
                ("Ishan Verma", "ishan1@gmail.com", "IN105", "Instrumentation", "2"),
                
                ("Jawahar Singh", "jawahar1@gmail.com", "IN201", "Instrumentation", "4"),
                ("Kavya Gupta", "kavya1@gmail.com", "IN202", "Instrumentation", "4"),
                ("Lalit Reddy", "lalit1@gmail.com", "IN203", "Instrumentation", "4"),
                ("Meera Kapoor", "meera1@gmail.com", "IN204", "Instrumentation", "4"),
                ("Naveen Rao", "naveen1@gmail.com", "IN205", "Instrumentation", "4"),
                
                ("Opinder Singh", "opinder1@gmail.com", "IN301", "Instrumentation", "6"),
                ("Pooja Desai", "pooja1@gmail.com", "IN302", "Instrumentation", "6"),
                ("Quentin Nair", "quentin1@gmail.com", "IN303", "Instrumentation", "6"),
                ("Riya Khan", "riya1@gmail.com", "IN304", "Instrumentation", "6"),
                ("Sanjay Joshi", "sanjay1@gmail.com", "IN305", "Instrumentation", "6"),
                
                # Mechanical
                ("Tejwant Singh", "tejwant1@gmail.com", "ME101", "Mechanical", "2"),
                ("Usha Sharma", "usha1@gmail.com", "ME102", "Mechanical", "2"),
                ("Vikrant Patel", "vikrant1@gmail.com", "ME103", "Mechanical", "2"),
                ("Wridha Gupta", "wridha1@gmail.com", "ME104", "Mechanical", "2"),
                ("Xenith Roy", "xenith1@gmail.com", "ME105", "Mechanical", "2"),
                
                ("Yuki Sharma", "yuki1@gmail.com", "ME201", "Mechanical", "4"),
                ("Zainab Khan", "zainab1@gmail.com", "ME202", "Mechanical", "4"),
                ("Arun Reddy", "arun1@gmail.com", "ME203", "Mechanical", "4"),
                ("Bina Kapoor", "bina1@gmail.com", "ME204", "Mechanical", "4"),
                ("Chitra Rao", "chitra1@gmail.com", "ME205", "Mechanical", "4"),
                
                ("Darius Singh", "darius1@gmail.com", "ME301", "Mechanical", "6"),
                ("Elena Desai", "elena1@gmail.com", "ME302", "Mechanical", "6"),
                ("Finnegan Nair", "finnegan1@gmail.com", "ME303", "Mechanical", "6"),
                ("Gaia Ahmed", "gaia1@gmail.com", "ME304", "Mechanical", "6"),
                ("Hans Joshi", "hans1@gmail.com", "ME305", "Mechanical", "6"),
            ]
            
            students = []
            for name, email, roll_num, branch, semester in students_data:
                student = User(
                    name=name,
                    email=email,
                    password=generate_password_hash("student123"),
                    role="student",
                    roll_number=roll_num,
                    branch=branch,
                    semester=semester
                )
                students.append(student)
            
            db.session.add_all([admin, teacher] + students)
            db.session.commit()

    app.run(debug=True)

