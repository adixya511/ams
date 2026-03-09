import csv
from datetime import date, datetime
from io import StringIO
# saving the day

from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DATABASE ----------------
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///attendance.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
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
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    branch = db.Column(db.String(100), nullable=True)
    semester = db.Column(db.String(20), nullable=True)

    # added fields required by the templates / routes
    date = db.Column(db.Date, nullable=False, default=date.today)
    status = db.Column(db.String(20), nullable=False, default="absent")

    # optional convenience relationships
    student = db.relationship(
        "User", foreign_keys=[student_id], backref="attendance_as_student"
    )
    teacher = db.relationship(
        "User", foreign_keys=[teacher_id], backref="attendance_as_teacher"
    )


# ---------------- ROOT ----------------
@app.route("/")
def root():
    return redirect(url_for("login"))


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role").lower()
        email = request.form.get("email").lower()
        password = request.form.get("password")

        user = User.query.filter(func.lower(User.email) == email).first()

        if (
            not user
            or user.role != role
            or not check_password_hash(user.password, password)
        ):
            flash("Invalid login details!")
            return render_template("login.html")

        session["user_id"] = user.id
        session["role"] = user.role

        if user.role == "admin":
            return redirect(url_for("admin_dashboard"))
        if user.role == "teacher":
            return redirect(url_for("teacher_dashboard"))
        if user.role == "student":
            return redirect(url_for("student_dashboard"))

    return render_template("login.html")


# ---------------- ADMIN ----------------
@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        abort(403)

    students = User.query.filter_by(role="student").all()
    teachers = User.query.filter_by(role="teacher").all()
    total_attendance = Attendance.query.count()

    return render_template(
        "admin.html",
        students=students,
        teachers=teachers,
        total_attendance=total_attendance,
    )


@app.route("/admin/students")
def manage_students():
    if session.get("role") != "admin":
        abort(403)

    # Get selected branch and semester from query parameters
    selected_branch = request.args.get("branch", "").strip()
    selected_semester = request.args.get("semester", "").strip()

    # Get all unique branches and semesters from students
    branches = db.session.query(User.branch).filter_by(role="student").distinct().all()
    semesters = (
        db.session.query(User.semester).filter_by(role="student").distinct().all()
    )

    branches = sorted([b[0] for b in branches if b[0]])
    semesters = sorted([s[0] for s in semesters if s[0]])

    # Filter students by branch and/or semester if selected
    query = User.query.filter_by(role="student")
    if selected_branch:
        query = query.filter_by(branch=selected_branch)
    if selected_semester:
        query = query.filter_by(semester=selected_semester)

    students = query.all()

    return render_template(
        "manage_students.html",
        students=students,
        branches=branches,
        semesters=semesters,
        selected_branch=selected_branch,
        selected_semester=selected_semester,
    )


@app.route("/admin/student/add", methods=["GET", "POST"])
def add_student():
    if session.get("role") != "admin":
        abort(403)

    if request.method == "POST":
        u = User(
            name=request.form["name"],
            email=request.form["email"].lower(),
            password=generate_password_hash(request.form["password"]),
            role="student",
            roll_number=request.form["roll_number"],
            branch=request.form.get("branch"),
            semester=request.form.get("semester"),
        )
        db.session.add(u)
        db.session.commit()
        return redirect(url_for("manage_students"))

    # Get unique branches and semesters from existing students
    branches = db.session.query(User.branch).filter_by(role="student").distinct().all()
    semesters = (
        db.session.query(User.semester).filter_by(role="student").distinct().all()
    )

    branches = sorted([b[0] for b in branches if b[0]])
    semesters = sorted([s[0] for s in semesters if s[0]])

    return render_template("add_student.html", branches=branches, semesters=semesters)


@app.route("/admin/student/edit/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    if session.get("role") != "admin":
        abort(403)
    student = User.query.get_or_404(id)
    if request.method == "POST":
        student.name = request.form.get("name", student.name)
        student.email = request.form.get("email", student.email).lower()
        pwd = request.form.get("password", "").strip()
        if pwd:
            student.password = generate_password_hash(pwd)
        student.roll_number = request.form.get("roll_number", student.roll_number)
        student.branch = request.form.get("branch", student.branch)
        student.semester = request.form.get("semester", student.semester)
        db.session.commit()
        flash("Student updated.")
        return redirect(url_for("manage_students"))

    # Get unique branches and semesters from existing students
    branches = db.session.query(User.branch).filter_by(role="student").distinct().all()
    semesters = (
        db.session.query(User.semester).filter_by(role="student").distinct().all()
    )

    branches = sorted([b[0] for b in branches if b[0]])
    semesters = sorted([s[0] for s in semesters if s[0]])

    return render_template(
        "edit_student.html", student=student, branches=branches, semesters=semesters
    )


@app.route("/admin/student/delete/<int:id>")
def delete_student(id):
    if session.get("role") != "admin":
        abort(403)
    db.session.delete(User.query.get_or_404(id))
    db.session.commit()
    flash("Student deleted.")
    return redirect(url_for("manage_students"))


# ---------- TEACHERS ----------
@app.route("/admin/teachers")
def manage_teachers():
    if session.get("role") != "admin":
        abort(403)
    return render_template(
        "manage_teachers.html", teachers=User.query.filter_by(role="teacher").all()
    )


@app.route("/admin/teacher/add", methods=["GET", "POST"])
def add_teacher():
    if session.get("role") != "admin":
        abort(403)

    if request.method == "POST":
        t = User(
            name=request.form["name"],
            email=request.form["email"].lower(),
            password=generate_password_hash(request.form["password"]),
            role="teacher",
            department=request.form["department"],
            subject=request.form["subject"],
        )
        db.session.add(t)
        db.session.commit()
        return redirect(url_for("manage_teachers"))

    return render_template("add_teacher.html")


@app.route("/admin/teacher/edit/<int:id>", methods=["GET", "POST"])
def edit_teacher(id):
    if session.get("role") != "admin":
        abort(403)
    teacher = User.query.get_or_404(id)
    if request.method == "POST":
        teacher.name = request.form.get("name", teacher.name)
        teacher.email = request.form.get("email", teacher.email).lower()
        pwd = request.form.get("password", "").strip()
        if pwd:
            teacher.password = generate_password_hash(pwd)
        teacher.department = request.form.get("department", teacher.department)
        teacher.subject = request.form.get("subject", teacher.subject)
        db.session.commit()
        flash("Teacher updated.")
        return redirect(url_for("manage_teachers"))
    return render_template("edit_teacher.html", teacher=teacher)


@app.route("/admin/teacher/delete/<int:id>")
def delete_teacher(id):
    if session.get("role") != "admin":
        abort(403)
    db.session.delete(User.query.get_or_404(id))
    db.session.commit()
    flash("Teacher deleted.")
    return redirect(url_for("manage_teachers"))


# ---------------- TEACHER ----------------
@app.route("/teacher")
def teacher_dashboard():
    if session.get("role") != "teacher":
        abort(403)
    teacher = User.query.get(session["user_id"])
    students = User.query.filter_by(role="student").all()
    return render_template("teacher.html", teacher=teacher, students=students)


# SELECT BRANCH AND SEMESTER FOR MARKING
@app.route("/teacher/select-class-mark", methods=["GET", "POST"])
def select_class_mark():
    if session.get("role") != "teacher":
        abort(403)

    if request.method == "POST":
        branch = request.form.get("branch")
        semester = request.form.get("semester")
        return redirect(url_for("mark_attendance", branch=branch, semester=semester))

    # Get unique branches and semesters from students
    branches = db.session.query(User.branch).filter_by(role="student").distinct().all()
    semesters = (
        db.session.query(User.semester).filter_by(role="student").distinct().all()
    )

    branches = sorted([b[0] for b in branches if b[0]])
    semesters = sorted([s[0] for s in semesters if s[0]])

    return render_template(
        "select_class.html",
        page_title="Select Branch & Semester",
        action="mark_attendance",
        branches=branches,
        semesters=semesters,
    )


# SELECT BRANCH AND SEMESTER FOR VIEWING
@app.route("/teacher/select-class-view", methods=["GET", "POST"])
def select_class_view():
    if session.get("role") != "teacher":
        abort(403)

    if request.method == "POST":
        branch = request.form.get("branch")
        semester = request.form.get("semester")
        return redirect(url_for("view_attendance", branch=branch, semester=semester))

    # Get unique branches and semesters from students
    branches = db.session.query(User.branch).filter_by(role="student").distinct().all()
    semesters = (
        db.session.query(User.semester).filter_by(role="student").distinct().all()
    )

    branches = sorted([b[0] for b in branches if b[0]])
    semesters = sorted([s[0] for s in semesters if s[0]])

    return render_template(
        "select_class.html",
        page_title="Select Branch & Semester",
        action="view_attendance",
        branches=branches,
        semesters=semesters,
    )


@app.route("/teacher/mark", methods=["GET", "POST"])
def mark_attendance():
    if session.get("role") != "teacher":
        abort(403)

    branch = request.args.get("branch")
    semester = request.args.get("semester")

    if not branch or not semester:
        return redirect(url_for("select_class_mark"))

    teacher = User.query.get(session["user_id"])
    students = User.query.filter_by(
        role="student", branch=branch, semester=semester
    ).all()

    if request.method == "POST":
        today = date.today()

        Attendance.query.filter_by(
            date=today,
            teacher_id=teacher.id,
            subject=teacher.subject,
            branch=branch,
            semester=semester,
        ).delete()

        for s in students:
            status = request.form.get(str(s.id))
            if status:
                db.session.add(
                    Attendance(
                        student_id=s.id,
                        teacher_id=teacher.id,
                        subject=teacher.subject,
                        branch=branch,
                        semester=semester,
                        date=today,
                        status=status,
                    )
                )

        db.session.commit()
        flash("Attendance Marked!")
        return redirect(url_for("teacher_dashboard"))

    return render_template(
        "mark_attendance.html",
        students=students,
        subject=teacher.subject,
        teacher=teacher,
        branch=branch,
        semester=semester,
    )


# ---------------- TEACHER VIEW WITH FILTERS ----------------
@app.route("/teacher/view", methods=["GET", "POST"])
def view_attendance():
    if session.get("role") != "teacher":
        abort(403)

    branch = request.args.get("branch")
    semester = request.args.get("semester")

    if not branch or not semester:
        return redirect(url_for("select_class_view"))

    teacher = User.query.get(session.get("user_id"))

    # teacher's subject is fixed — do not allow choosing other subjects
    selected_subject = teacher.subject if teacher and teacher.subject else None

    # read date filter only
    selected_date = None
    if request.method == "POST":
        sd = (request.form.get("selected_date") or "").strip()
        if sd:
            try:
                selected_date = date.fromisoformat(sd)
            except Exception:
                selected_date = None
    else:
        sd = request.args.get("date", "").strip()
        if sd:
            try:
                selected_date = date.fromisoformat(sd)
            except Exception:
                selected_date = None

    # build query — filter by teacher, teacher's subject, branch and semester
    q = Attendance.query.filter_by(
        teacher_id=teacher.id, branch=branch, semester=semester
    )
    if selected_subject:
        q = q.filter_by(subject=selected_subject)
    if selected_date:
        q = q.filter_by(date=selected_date)

    records = q.order_by(Attendance.date.desc(), Attendance.id.desc()).all()
    for r in records:
        r.student_obj = User.query.get(r.student_id)

    return render_template(
        "view_attendance.html",
        teacher=teacher,
        records=records,
        selected_date=(selected_date.isoformat() if selected_date else ""),
        selected_subject=selected_subject,
        branch=branch,
        semester=semester,
    )


@app.route("/teacher/download-csv")
def download_attendance_csv():
    if session.get("role") != "teacher":
        abort(403)

    teacher = User.query.get(session.get("user_id"))

    branch = request.args.get("branch")
    semester = request.args.get("semester")
    date_filter = request.args.get("date")

    if not branch or not semester:
        abort(400)

    query = Attendance.query.filter_by(
        teacher_id=teacher.id, branch=branch, semester=semester, subject=teacher.subject
    )

    if date_filter:
        try:
            selected_date = date.fromisoformat(date_filter)
            query = query.filter_by(date=selected_date)
        except:
            pass

    records = query.order_by(Attendance.date.desc()).all()

    si = StringIO()
    cw = csv.writer(si)

    cw.writerow(
        [
            "Student Name",
            "Roll Number",
            "Branch",
            "Semester",
            "Subject",
            "Date",
            "Status",
        ]
    )

    for r in records:
        student = User.query.get(r.student_id)
        cw.writerow(
            [
                student.name,
                student.roll_number,
                r.branch,
                r.semester,
                r.subject,
                r.date,
                r.status,
            ]
        )

    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance.csv"},
    )


# ---------------- STUDENT ----------------
@app.route("/student", methods=["GET", "POST"])
def student_dashboard():
    if session.get("role") != "student":
        abort(403)

    student_id = session["user_id"]
    student = User.query.get(student_id)

    teachers = User.query.filter_by(role="teacher").all()
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
    overall_percentage = (
        round((all_present / all_total) * 100, 2) if all_total > 0 else 0
    )

    # ------------------------------------------
    # 2. MONTHLY ATTENDANCE
    # ------------------------------------------
    today = date.today()
    first_day = today.replace(day=1)

    monthly_records = Attendance.query.filter(
        Attendance.student_id == student_id,
        Attendance.date >= first_day,
        Attendance.date <= today,
    ).all()

    monthly_total = len(monthly_records)
    monthly_present = sum(1 for r in monthly_records if r.status.lower() == "present")
    monthly_percentage = (
        round((monthly_present / monthly_total) * 100, 2) if monthly_total > 0 else 0
    )

    today_record = Attendance.query.filter_by(
        student_id=student_id, date=date.today()
    ).first()
    subjects = get_all_subjects()

    return render_template(
        "student.html",
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
        monthly_percentage=monthly_percentage,
    )


@app.route("/student/subjects")
def student_subjects():
    if session.get("role") != "student":
        abort(403)

    student = User.query.get(session.get("user_id"))
    if not student:
        abort(404)

    # --- subjects where this student has any record ---
    rows = (
        db.session.query(Attendance.subject)
        .filter_by(student_id=student.id)
        .distinct()
        .all()
    )
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
        total_sessions = (
            db.session.query(func.count(func.distinct(Attendance.date)))
            .filter_by(subject=s)
            .scalar()
            or 0
        )

        # FIXED: present count ignoring case differences
        present_count = (
            db.session.query(Attendance)
            .filter(
                Attendance.subject == s,
                Attendance.student_id == student.id,
                func.lower(Attendance.status) == "present",
            )
            .count()
        )

        # last class date
        last_rec = (
            db.session.query(Attendance.date)
            .filter_by(subject=s)
            .order_by(Attendance.date.desc())
            .first()
        )
        last_date = last_rec[0].isoformat() if last_rec else None

        # teacher names for this subject
        teacher_rows = (
            db.session.query(User.name)
            .join(Attendance, Attendance.teacher_id == User.id)
            .filter(Attendance.subject == s)
            .distinct()
            .all()
        )
        teacher_names = ", ".join([t[0] for t in teacher_rows]) if teacher_rows else ""

        # calculate percentage
        percent = (
            round((present_count / total_sessions) * 100, 1)
            if total_sessions > 0
            else 0
        )

        # check if student has any attendance in this subject
        enrolled = (
            Attendance.query.filter_by(subject=s, student_id=student.id).count() > 0
        )

        subjects_info.append(
            {
                "subject": s,
                "total_sessions": total_sessions,
                "present_count": present_count,
                "present_percent": percent,
                "last_date": last_date,
                "teachers": teacher_names,
                "enrolled": enrolled,
            }
        )

    return render_template(
        "student_subjects.html",
        student=student,
        subjects_info=subjects_info,
        fallback=fallback,
    )


@app.route("/student/subject/<path:subject>/details")
def student_subject_details(subject):
    if session.get("role") != "student":
        abort(403)
    student_id = session.get("user_id")

    # total distinct session dates for this subject (class-wide)
    total_sessions = (
        db.session.query(func.count(func.distinct(Attendance.date)))
        .filter_by(subject=subject)
        .scalar()
        or 0
    )

    # count present for this student
    present_count = Attendance.query.filter_by(
        subject=subject, student_id=student_id, status="present"
    ).count()

    # per-session history for this student (date + status)
    hist_rows = (
        db.session.query(Attendance.date, Attendance.status)
        .filter_by(subject=subject, student_id=student_id)
        .order_by(Attendance.date)
        .all()
    )
    history = [{"date": r[0].isoformat(), "status": r[1]} for r in hist_rows]

    return jsonify(
        {
            "subject": subject,
            "total_sessions": total_sessions,
            "present_count": present_count,
            "present_percent": (
                round((present_count / total_sessions) * 100, 1)
                if total_sessions > 0
                else 0.0
            ),
            "history": history,
        }
    )


@app.route("/student/classes")
def student_classes():
    if session.get("role") != "student":
        abort(403)
    student = User.query.get(session.get("user_id"))
    # build per-subject attendance stats for this student
    rows = (
        db.session.query(Attendance.subject)
        .filter_by(student_id=student.id)
        .distinct()
        .all()
    )
    subjects = [r[0] for r in rows if r[0]]
    classes_stats = []
    for subj in subjects:
        total = Attendance.query.filter_by(student_id=student.id, subject=subj).count()
        present = Attendance.query.filter(
            Attendance.student_id == student.id,
            Attendance.subject == subj,
            func.lower(Attendance.status) == "present",
        ).count()
        pct = round((present / total) * 100, 2) if total > 0 else 0
        classes_stats.append(
            {"subject": subj, "total": total, "present": present, "percentage": pct}
        )
    return render_template(
        "student_classes.html", student=student, classes_stats=classes_stats
    )


@app.route("/student/attendance")
def student_attendance():
    if session.get("role") != "student":
        abort(403)
    student = User.query.get(session.get("user_id"))
    records = (
        Attendance.query.filter_by(student_id=student.id)
        .order_by(Attendance.date.desc())
        .all()
    )
    for r in records:
        r.teacher_obj = User.query.get(r.teacher_id)
    return render_template("student_attendance.html", student=student, records=records)


# ---------------- REPORTS ----------------
@app.route("/reports")
def reports():
    if session.get("role") != "admin":
        abort(403)

    # totals (existing)
    total_students = User.query.filter_by(role="student").count()
    total_teachers = User.query.filter_by(role="teacher").count()
    total_attendance = Attendance.query.count()

    # Attendance by subject
    subjects = [row[0] for row in db.session.query(Attendance.subject).distinct().all()]
    attendance_by_subject = []
    for subj in subjects:
        total = Attendance.query.filter_by(subject=subj).count()
        present = Attendance.query.filter(
            Attendance.subject == subj, func.lower(Attendance.status) == "present"
        ).count()
        pct = round((present / total) * 100, 2) if total > 0 else 0
        attendance_by_subject.append(
            {"subject": subj, "total": total, "present": present, "percentage": pct}
        )

    # Attendance by teacher
    teachers = User.query.filter_by(role="teacher").all()
    attendance_by_teacher = []
    for t in teachers:
        total = Attendance.query.filter_by(teacher_id=t.id).count()
        present = Attendance.query.filter(
            Attendance.teacher_id == t.id, func.lower(Attendance.status) == "present"
        ).count()
        pct = round((present / total) * 100, 2) if total > 0 else 0
        attendance_by_teacher.append(
            {"teacher": t.name, "total": total, "present": present, "percentage": pct}
        )

    # Students with lowest attendance (overall) - top 10
    students = User.query.filter_by(role="student").all()
    student_stats = []
    for s in students:
        total = Attendance.query.filter_by(student_id=s.id).count()
        present = Attendance.query.filter(
            Attendance.student_id == s.id, func.lower(Attendance.status) == "present"
        ).count()
        pct = round((present / total) * 100, 2) if total > 0 else None
        student_stats.append(
            {
                "id": s.id,
                "name": s.name,
                "email": s.email,
                "total": total,
                "present": present,
                "percentage": pct,
            }
        )
    low_attendance = sorted(
        [x for x in student_stats if x["percentage"] is not None],
        key=lambda r: r["percentage"],
    )[:10]

    # Recent attendance entries
    recent_records = (
        Attendance.query.order_by(Attendance.date.desc(), Attendance.id.desc())
        .limit(12)
        .all()
    )
    # attach student & teacher names for display
    for r in recent_records:
        r.student_obj = User.query.get(r.student_id)
        r.teacher_obj = User.query.get(r.teacher_id)

    return render_template(
        "reports.html",
        total_students=total_students,
        total_teachers=total_teachers,
        total_attendance=total_attendance,
        attendance_by_subject=attendance_by_subject,
        attendance_by_teacher=attendance_by_teacher,
        low_attendance=low_attendance,
        recent_records=recent_records,
    )


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- TEACHER CLASSES ----------------
@app.route("/teacher/classes")
def teacher_classes():
    if session.get("role") != "teacher":
        abort(403)
    teacher = User.query.get(session.get("user_id"))

    # build unique class list (teacher.subject + subjects from attendance)
    classes = []
    if teacher and teacher.subject:
        classes.append(teacher.subject)
    if teacher:
        subjects = [
            row[0]
            for row in db.session.query(Attendance.subject)
            .filter_by(teacher_id=teacher.id)
            .distinct()
            .all()
            or []
        ]
        for s in subjects:
            if s and s not in classes:
                classes.append(s)

    # build richer info for each class (sessions count, distinct students, last session date)
    classes_info = []
    for s in classes:
        total_sessions = Attendance.query.filter_by(
            teacher_id=teacher.id, subject=s
        ).count()
        last_rec = (
            Attendance.query.filter_by(teacher_id=teacher.id, subject=s)
            .order_by(Attendance.date.desc())
            .first()
        )
        last_date = last_rec.date.isoformat() if last_rec else None
        students_count = (
            db.session.query(Attendance.student_id)
            .filter_by(teacher_id=teacher.id, subject=s)
            .distinct()
            .count()
        )
        classes_info.append(
            {
                "subject": s,
                "total_sessions": total_sessions,
                "last_date": last_date,
                "students_count": students_count,
            }
        )

    return render_template(
        "teacher_classes.html", teacher=teacher, classes_info=classes_info
    )


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
    for t in User.query.filter_by(role="teacher").all():
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
                role="admin",
            )
            default_teacher = User(
                name="Mr. Sharma",
                email="teacher@gmail.com",
                password=generate_password_hash("teacher123"),
                role="teacher",
                department="CS",
                subject="Web Development",
            )

            # Additional teacher/staff teaching accounts
            # password kept common for first login; they can change later from profile/admin edit
            teachers_data = [
                (
                    "Naresh Kumar",
                    "nareshkumarspch@gmail.com",
                    "CS",
                    "Computer Engineering",
                ),
                (
                    "Rajesh Sharma",
                    "rsharma72@gmail.com",
                    "Electrical",
                    "Electrical Engineering",
                ),
                (
                    "Hari Singh Thakur",
                    "hsthakur09@gmail.com",
                    "ECE",
                    "Electronics Engineering",
                ),
                ("Kamlesh Chand", "kchand78@gmail.com", "AS&H", "Applied Science"),
                (
                    "Pawan Chandel",
                    "pawanchandel13@gmail.com",
                    "Instrumentation",
                    "Instrumentation Engineering",
                ),
                ("Talvinder Singh", "talvinder.m@gmail.com", "CS", "Computer Science"),
                ("Jagdeep Singh", "jagdeep9906@gmail.com", "CS", "Computer Science"),
                (
                    "Sudhir Dhiman",
                    "sudhir.dhiman85@gmail.com",
                    "CS",
                    "Computer Science",
                ),
                ("Onkar Singh", "onkar.singh26970@gmail.com", "CS", "Computer Science"),
                ("Saroop Chand", "saroop2388@gmail.com", "CS", "Computer Science"),
                (
                    "Sachin Sehota",
                    "sachin.sehota@gmail.com",
                    "ECE",
                    "Electronics Engineering",
                ),
                ("Rohit Kumar", "rohit06d@gmail.com", "ECE", "Electronics Engineering"),
                (
                    "Nishant Kaushal",
                    "nishant.1987@gmail.com",
                    "ECE",
                    "Electronics Engineering",
                ),
                (
                    "Raman Kumar",
                    "ramankumar89@gmail.com",
                    "ECE",
                    "Electronics Engineering",
                ),
                (
                    "Rajeev Kumar",
                    "rajeev.kumar357@gmail.com",
                    "ECE",
                    "Electronics Engineering",
                ),
                ("Avinash Sharma", "avinash.acet@yahoo.com", "CE", "Civil Engineering"),
                (
                    "Surbhi Sharma",
                    "surbhisharma.jmj@gmail.com",
                    "CE",
                    "Civil Engineering",
                ),
                ("Tamanna", "er.tamanna14@gmail.com", "CE", "Civil Engineering"),
                ("Ashima Sharma", "ashima143188@gmail.com", "CE", "Civil Engineering"),
                (
                    "Vijay Kumar Sharma",
                    "vijay2122@gmail.com",
                    "CE",
                    "Civil Engineering",
                ),
                (
                    "Vikal Sharma",
                    "vikal.in.sharma@gmail.com",
                    "IE",
                    "Instrumentation Engineering",
                ),
                (
                    "Karan Singh Thakur",
                    "karansingh.thakur89@gmail.com",
                    "IE",
                    "Instrumentation Engineering",
                ),
                ("Varun", "varunkrr72@gmail.com", "IE", "Instrumentation Engineering"),
                (
                    "Ritika Sharma",
                    "ritika30purohit30@gmail.com",
                    "IE",
                    "Instrumentation Engineering",
                ),
                (
                    "Munish Kumar",
                    "munishsharma198@gmail.com",
                    "IE",
                    "Instrumentation Engineering",
                ),
                (
                    "Santosh Kumar",
                    "kumarsantosh9606@gmail.com",
                    "ME",
                    "Mechanical Engineering",
                ),
                (
                    "Mohan Lal",
                    "mohanpathania6747@gmail.com",
                    "ME",
                    "Mechanical Engineering",
                ),
                (
                    "Subash Chand",
                    "swastiksneha@gmail.com",
                    "ME",
                    "Mechanical Engineering",
                ),
                (
                    "Satbir Singh",
                    "satbirsuru@gmail.com",
                    "ME",
                    "Mechanical Engineering",
                ),
                (
                    "Sameer Sharma",
                    "sameer30132@gmail.com",
                    "ME",
                    "Mechanical Engineering",
                ),
                ("Ina Gupta", "guptaina24@gmail.com", "EE", "Electrical Engineering"),
                ("Iela Bharti", "iela.b89@gmail.com", "EE", "Electrical Engineering"),
                ("Pritam Chand", "pritam777018@gmail.com", "Physics", "Physics"),
                ("Richa Sharma", "richathakur121@gmail.com", "English", "English"),
                ("Vijay Thakur", "thakurviju454@gmail.com", "Physics", "Physics"),
                ("Anil Kumar", "prashanil77@gmail.com", "Chemistry", "Chemistry"),
            ]

            # Create students data
            students_data = [
                # Computer Science - 2nd Semester (47 students)
                ("Aarkit Sharma", "aarkit@gmail.com", "1", "Computer Science", "2"),
                ("Abansik", "abansik@gmail.com", "2", "Computer Science", "2"),
                ("Abhay Dogra", "abhay.dogra@gmail.com", "3", "Computer Science", "2"),
                ("Abhay Verma", "abhay.verma@gmail.com", "4", "Computer Science", "2"),
                ("Aditya", "aditya@gmail.com", "5", "Computer Science", "2"),
                ("Akshit Dev", "akshit@gmail.com", "6", "Computer Science", "2"),
                ("Anmol Saklani", "anmol@gmail.com", "7", "Computer Science", "2"),
                ("Anshil", "anshil@gmail.com", "8", "Computer Science", "2"),
                ("Anshuman", "anshuman@gmail.com", "9", "Computer Science", "2"),
                ("Arun Kumar", "arun.kumar@gmail.com", "10", "Computer Science", "2"),
                ("Arush Patiyal", "arush@gmail.com", "11", "Computer Science", "2"),
                ("Aryan", "aryan@gmail.com", "12", "Computer Science", "2"),
                ("Ayush", "ayush@gmail.com", "13", "Computer Science", "2"),
                ("Divyansh", "divyansh@gmail.com", "14", "Computer Science", "2"),
                ("Hemant Koundal", "hemant@gmail.com", "15", "Computer Science", "2"),
                ("Harshit", "harshit@gmail.com", "16", "Computer Science", "2"),
                ("Ishan Sagar", "ishan@gmail.com", "17", "Computer Science", "2"),
                ("Isharit Dogra", "isharit@gmail.com", "18", "Computer Science", "2"),
                ("Ishita Sugha", "ishita@gmail.com", "19", "Computer Science", "2"),
                ("Kajal", "kajal@gmail.com", "20", "Computer Science", "2"),
                ("Krish Bharti", "krish@gmail.com", "21", "Computer Science", "2"),
                ("Manan Sharma", "manan@gmail.com", "22", "Computer Science", "2"),
                ("Manisha Dhiman", "manisha@gmail.com", "23", "Computer Science", "2"),
                ("Mayank Baggae", "mayank@gmail.com", "24", "Computer Science", "2"),
                ("Muskan", "muskan@gmail.com", "25", "Computer Science", "2"),
                ("Nitsh Kumar", "nitsh@gmail.com", "26", "Computer Science", "2"),
                ("Paras", "paras@gmail.com", "27", "Computer Science", "2"),
                ("Radhika", "radhika@gmail.com", "28", "Computer Science", "2"),
                ("Raj Sharma", "raj@gmail.com", "29", "Computer Science", "2"),
                (
                    "Ridhima Choudhary",
                    "ridhima@gmail.com",
                    "30",
                    "Computer Science",
                    "2",
                ),
                (
                    "Rudrasish Singh Rana",
                    "rudrasish@gmail.com",
                    "31",
                    "Computer Science",
                    "2",
                ),
                ("Sahil Guleria", "sahil@gmail.com", "32", "Computer Science", "2"),
                ("Sanjeev Kumar", "sanjeev@gmail.com", "33", "Computer Science", "2"),
                ("Sanvi Mahajan", "sanvi@gmail.com", "34", "Computer Science", "2"),
                ("Sheetal", "sheetal@gmail.com", "35", "Computer Science", "2"),
                ("Shivam", "shivam@gmail.com", "36", "Computer Science", "2"),
                (
                    "Shivam Sharma",
                    "shivam.sharma@gmail.com",
                    "37",
                    "Computer Science",
                    "2",
                ),
                (
                    "Shivam Thakur",
                    "shivam.thakur@gmail.com",
                    "38",
                    "Computer Science",
                    "2",
                ),
                ("Shivend Gautam", "shivend@gmail.com", "39", "Computer Science", "2"),
                ("Simran Choudhary", "simran@gmail.com", "40", "Computer Science", "2"),
                ("Sohani Dogra", "sohani@gmail.com", "41", "Computer Science", "2"),
                (
                    "Surya Kumar Koundal",
                    "surya@gmail.com",
                    "42",
                    "Computer Science",
                    "2",
                ),
                ("Swastik Naryal", "swastik@gmail.com", "43", "Computer Science", "2"),
                ("Tamanna Sharma", "tamanna@gmail.com", "44", "Computer Science", "2"),
                (
                    "Utkarsh Choudhary",
                    "utkarsh@gmail.com",
                    "45",
                    "Computer Science",
                    "2",
                ),
                ("Yashita Mehra", "yashita@gmail.com", "46", "Computer Science", "2"),
                ("Yogesh Raj", "yogesh@gmail.com", "47", "Computer Science", "2"),
                # Computer Science - 4th Semester (52 students)
                ("Aarshit Rana", "aarshit@gmail.com", "1", "Computer Science", "4"),
                ("Aavya Parmar", "aavya@gmail.com", "2", "Computer Science", "4"),
                ("Aayush Parmar", "aayush@gmail.com", "3", "Computer Science", "4"),
                ("Abhishek Chalib", "abhishek@gmail.com", "4", "Computer Science", "4"),
                (
                    "Aditya Sharma",
                    "aditya.sharma@gmail.com",
                    "5",
                    "Computer Science",
                    "4",
                ),
                ("Akash", "akash@gmail.com", "6", "Computer Science", "4"),
                ("Akhil Sharma", "akhil@gmail.com", "7", "Computer Science", "4"),
                ("Amartya", "amartya@gmail.com", "8", "Computer Science", "4"),
                ("Ankush", "ankush@gmail.com", "9", "Computer Science", "4"),
                (
                    "Antriksh Choudhary",
                    "antriksh@gmail.com",
                    "10",
                    "Computer Science",
                    "4",
                ),
                ("Anush Kumar", "anush@gmail.com", "11", "Computer Science", "4"),
                ("Anushaka", "anushaka@gmail.com", "12", "Computer Science", "4"),
                ("Anushka Bhatta", "anushka@gmail.com", "13", "Computer Science", "4"),
                ("Apoorva Dogra", "apoorva@gmail.com", "14", "Computer Science", "4"),
                ("Arfan", "arfan@gmail.com", "15", "Computer Science", "4"),
                (
                    "Ayush Thakur",
                    "ayush.thakur@gmail.com",
                    "16",
                    "Computer Science",
                    "4",
                ),
                (
                    "Bhuvaneshwar",
                    "bhuvaneshwar@gmail.com",
                    "17",
                    "Computer Science",
                    "4",
                ),
                (
                    "Chaitanya Sharma",
                    "chaitanya@gmail.com",
                    "18",
                    "Computer Science",
                    "4",
                ),
                ("Hardev Singh", "hardev@gmail.com", "19", "Computer Science", "4"),
                ("Harish Mondga", "harish@gmail.com", "20", "Computer Science", "4"),
                ("Janvi", "janvi@gmail.com", "21", "Computer Science", "4"),
                ("Karun Shiva", "karun@gmail.com", "22", "Computer Science", "4"),
                ("Kavya", "kavya@gmail.com", "23", "Computer Science", "4"),
                ("Kriti Rana", "kriti@gmail.com", "24", "Computer Science", "4"),
                ("Lakshay Sharma", "lakshay@gmail.com", "25", "Computer Science", "4"),
                ("Manish", "manish@gmail.com", "26", "Computer Science", "4"),
                (
                    "Maninder Uldeen",
                    "maninder@gmail.com",
                    "27",
                    "Computer Science",
                    "4",
                ),
                ("Manvi Rana", "manvi@gmail.com", "28", "Computer Science", "4"),
                ("Mohit Bharti", "mohit@gmail.com", "29", "Computer Science", "4"),
                ("Mridul", "mridul@gmail.com", "30", "Computer Science", "4"),
                ("Muskan", "muskan.cs4@gmail.com", "31", "Computer Science", "4"),
                ("Nikhil Choudhary", "nikhil@gmail.com", "32", "Computer Science", "4"),
                ("Nishant Kumar", "nishant@gmail.com", "33", "Computer Science", "4"),
                ("Palak Bhangale", "palak@gmail.com", "34", "Computer Science", "4"),
                ("Ridhim Kumar", "ridhim@gmail.com", "35", "Computer Science", "4"),
                ("Rishabh Kaundal", "rishabh@gmail.com", "36", "Computer Science", "4"),
                (
                    "Shrishti Sharma",
                    "shrishti@gmail.com",
                    "37",
                    "Computer Science",
                    "4",
                ),
                ("Sneha", "sneha@gmail.com", "38", "Computer Science", "4"),
                ("Suhaan Mehra", "suhaan@gmail.com", "39", "Computer Science", "4"),
                ("Tanvi Sharma", "tanvi@gmail.com", "40", "Computer Science", "4"),
                ("Uday Singh", "uday@gmail.com", "41", "Computer Science", "4"),
                ("Vipul", "vipul@gmail.com", "42", "Computer Science", "4"),
                ("Anshika", "anshika@gmail.com", "43", "Computer Science", "4"),
                ("Jeeya Patiyal", "jeeya@gmail.com", "44", "Computer Science", "4"),
                ("Kamlesh Kumari", "kamlesh@gmail.com", "45", "Computer Science", "4"),
                (
                    "Manish Kumar",
                    "manish.kumar@gmail.com",
                    "46",
                    "Computer Science",
                    "4",
                ),
                ("Diksha", "diksha@gmail.com", "47", "Computer Science", "4"),
                ("Harshit Rai", "harshit.rai@gmail.com", "48", "Computer Science", "4"),
                ("Ashish", "ashish@gmail.com", "49", "Computer Science", "4"),
                ("Nalin Koundal", "nalin@gmail.com", "50", "Computer Science", "4"),
                ("Ankita Kumari", "ankita@gmail.com", "51", "Computer Science", "4"),
                ("Dhruv", "dhruv@gmail.com", "52", "Computer Science", "4"),
                # Computer Science - 6th Semester (50 students)
                (
                    "Aarush Koundal",
                    "aarush.koundal@gmail.com",
                    "1",
                    "Computer Science",
                    "6",
                ),
                ("Aditya", "aditya.6@gmail.com", "2", "Computer Science", "6"),
                ("Aditya", "aditya.6b@gmail.com", "3", "Computer Science", "6"),
                (
                    "Aditya Thakur",
                    "aditya.thakur@gmail.com",
                    "4",
                    "Computer Science",
                    "6",
                ),
                (
                    "Aditya Katoch",
                    "aditya.katoch@gmail.com",
                    "5",
                    "Computer Science",
                    "6",
                ),
                (
                    "Aditya Sharma",
                    "aditya.sharma.6@gmail.com",
                    "6",
                    "Computer Science",
                    "6",
                ),
                ("Akasshi Mehra", "akasshi@gmail.com", "7", "Computer Science", "6"),
                ("Akshara Thakur", "akshara@gmail.com", "8", "Computer Science", "6"),
                ("Arkshit Sharma", "arkshit@gmail.com", "9", "Computer Science", "6"),
                ("Anita", "anita@gmail.com", "10", "Computer Science", "6"),
                ("Areen", "areen@gmail.com", "11", "Computer Science", "6"),
                (
                    "Aryan Dhiman",
                    "aryan.dhiman@gmail.com",
                    "12",
                    "Computer Science",
                    "6",
                ),
                (
                    "Aryan Jamwal",
                    "aryan.jamwal@gmail.com",
                    "13",
                    "Computer Science",
                    "6",
                ),
                ("Ayush", "ayush.6@gmail.com", "14", "Computer Science", "6"),
                ("Banshul Kumar", "banshul@gmail.com", "15", "Computer Science", "6"),
                (
                    "Diksha Chauhan",
                    "diksha.chauhan@gmail.com",
                    "16",
                    "Computer Science",
                    "6",
                ),
                ("Divyanshi", "divyanshi@gmail.com", "17", "Computer Science", "6"),
                ("Harsh", "harsh@gmail.com", "18", "Computer Science", "6"),
                ("Harshi", "harshi@gmail.com", "19", "Computer Science", "6"),
                (
                    "Harshit Kapoor",
                    "harshit.kapoor@gmail.com",
                    "20",
                    "Computer Science",
                    "6",
                ),
                ("Isha Kumari", "isha.kumari@gmail.com", "21", "Computer Science", "6"),
                ("Ishaan Kumar", "ishaan@gmail.com", "22", "Computer Science", "6"),
                (
                    "Muskan Choudhary",
                    "muskan.choudhary@gmail.com",
                    "23",
                    "Computer Science",
                    "6",
                ),
                ("Piyush", "piyush@gmail.com", "24", "Computer Science", "6"),
                ("Priya", "priya@gmail.com", "25", "Computer Science", "6"),
                (
                    "Pushkar Pathania",
                    "pushkar@gmail.com",
                    "26",
                    "Computer Science",
                    "6",
                ),
                ("Rasik Jarwal", "rasik@gmail.com", "27", "Computer Science", "6"),
                ("Riya Dhiman", "riya.dhiman@gmail.com", "28", "Computer Science", "6"),
                ("Sarshi Koundal", "sarshi@gmail.com", "29", "Computer Science", "6"),
                ("Saniya", "saniya@gmail.com", "30", "Computer Science", "6"),
                ("Sejal", "sejal@gmail.com", "31", "Computer Science", "6"),
                ("Shagun", "shagun@gmail.com", "32", "Computer Science", "6"),
                ("Shiven Sharma", "shiven@gmail.com", "33", "Computer Science", "6"),
                ("Shreya", "shreya@gmail.com", "34", "Computer Science", "6"),
                (
                    "Simran Bharti",
                    "simran.bharti@gmail.com",
                    "35",
                    "Computer Science",
                    "6",
                ),
                ("Sneha", "sneha.6@gmail.com", "36", "Computer Science", "6"),
                ("Tanisha", "tanisha@gmail.com", "37", "Computer Science", "6"),
                (
                    "Vanshika Naryal",
                    "vanshika@gmail.com",
                    "38",
                    "Computer Science",
                    "6",
                ),
                (
                    "Vishakha Koundal",
                    "vishakha@gmail.com",
                    "39",
                    "Computer Science",
                    "6",
                ),
                (
                    "Ankit Koundal",
                    "ankit.koundal@gmail.com",
                    "40",
                    "Computer Science",
                    "6",
                ),
                (
                    "Ankit Gulerja",
                    "ankit.gulerja@gmail.com",
                    "41",
                    "Computer Science",
                    "6",
                ),
                ("Akshay Kumar", "akshay@gmail.com", "42", "Computer Science", "6"),
                ("Abhihay Thakur", "abhihay@gmail.com", "43", "Computer Science", "6"),
                (
                    "Parshant Sharma",
                    "parshant@gmail.com",
                    "44",
                    "Computer Science",
                    "6",
                ),
                ("Uday Thakur", "uday.thakur@gmail.com", "45", "Computer Science", "6"),
                ("Anshika", "anshika.6@gmail.com", "46", "Computer Science", "6"),
                ("Vansh Rana", "vansh@gmail.com", "47", "Computer Science", "6"),
                (
                    "Disha Choudhary",
                    "disha.choudhary@gmail.com",
                    "48",
                    "Computer Science",
                    "6",
                ),
                ("Mannat Walia", "mannat@gmail.com", "49", "Computer Science", "6"),
                (
                    "Krish Singh Athwal",
                    "krish.singh@gmail.com",
                    "50",
                    "Computer Science",
                    "6",
                ),
                # Electrical Engineering - 2nd Semester (45 students)
                (
                    "Abhishek Mittal",
                    "abhishek.mittal@gmail.com",
                    "1",
                    "Electrical",
                    "2",
                ),
                ("Aditya Nanda", "aditya.nanda@gmail.com", "2", "Electrical", "2"),
                ("Ankit Karnoot", "ankit.karnoot@gmail.com", "3", "Electrical", "2"),
                ("Ankit", "ankit@gmail.com", "4", "Electrical", "2"),
                ("Avinash Devi", "avinash.devi@gmail.com", "5", "Electrical", "2"),
                ("Adyoti Choudhary", "adyoti@gmail.com", "6", "Electrical", "2"),
                (
                    "Amit Kumar Maharaj Singh",
                    "amit.kumar@gmail.com",
                    "7",
                    "Electrical",
                    "2",
                ),
                ("Amata Harjps", "amata@gmail.com", "8", "Electrical", "2"),
                ("Amu Sharma", "amu@gmail.com", "9", "Electrical", "2"),
                ("Anurag Mahtra", "anurag@gmail.com", "10", "Electrical", "2"),
                ("Bhuvan Dev", "bhuvan@gmail.com", "11", "Electrical", "2"),
                ("Dighansh", "dighansh@gmail.com", "12", "Electrical", "2"),
                ("Harshul Thakpur", "harshul@gmail.com", "13", "Electrical", "2"),
                ("Harshir Choudhary", "harshir@gmail.com", "14", "Electrical", "2"),
                ("Ishant", "ishant@gmail.com", "15", "Electrical", "2"),
                ("Jaswant Kaur", "jaswant@gmail.com", "16", "Electrical", "2"),
                ("Kartik", "kartik@gmail.com", "17", "Electrical", "2"),
                (
                    "Kartik Choudhary",
                    "kartik.choudhary@gmail.com",
                    "18",
                    "Electrical",
                    "2",
                ),
                ("Kartik Kumar", "kartik.kumar@gmail.com", "19", "Electrical", "2"),
                ("Karvey", "karvey@gmail.com", "20", "Electrical", "2"),
                ("Kishor Sharma", "kishor@gmail.com", "21", "Electrical", "2"),
                ("Kiriti Kumar", "kiriti@gmail.com", "22", "Electrical", "2"),
                ("Nitesh Harpal", "nitesh@gmail.com", "23", "Electrical", "2"),
                ("Pallab Sharma", "pallab@gmail.com", "24", "Electrical", "2"),
                ("Rebindai", "rebindai@gmail.com", "25", "Electrical", "2"),
                ("Resnav Kumar", "resnav@gmail.com", "26", "Electrical", "2"),
                (
                    "Rishi Choudhary",
                    "rishi.choudhary@gmail.com",
                    "27",
                    "Electrical",
                    "2",
                ),
                ("Rishi", "rishi@gmail.com", "28", "Electrical", "2"),
                (
                    "Rohit Choudhary",
                    "rohit.choudhary@gmail.com",
                    "29",
                    "Electrical",
                    "2",
                ),
                ("Rohit Ola Rana", "rohit.rana@gmail.com", "30", "Electrical", "2"),
                ("Sahid Kumar", "sahid@gmail.com", "31", "Electrical", "2"),
                ("Sameet Sharma", "sameet@gmail.com", "32", "Electrical", "2"),
                ("Satvirram Daitnam", "satvirram@gmail.com", "33", "Electrical", "2"),
                ("Satyam Singh", "satyam@gmail.com", "34", "Electrical", "2"),
                ("Shardham Jintyal", "shardham@gmail.com", "35", "Electrical", "2"),
                ("Shridham", "shridham@gmail.com", "36", "Electrical", "2"),
                (
                    "Simran Choudhary",
                    "simran.choudhary@gmail.com",
                    "37",
                    "Electrical",
                    "2",
                ),
                ("Shalun Sharma", "shalun@gmail.com", "38", "Electrical", "2"),
                ("Sumit Kunbal", "sumit@gmail.com", "39", "Electrical", "2"),
                ("Taksh Batshai", "taksh@gmail.com", "40", "Electrical", "2"),
                ("Tanish Koushal", "tanish@gmail.com", "41", "Electrical", "2"),
                ("Vikram Chantyal", "vikram@gmail.com", "42", "Electrical", "2"),
                ("Abhinav", "abhinav@gmail.com", "43", "Electrical", "2"),
                ("Akarsht Choudhary", "akarsht@gmail.com", "44", "Electrical", "2"),
                ("Ileshan Kalihal", "ileshan@gmail.com", "45", "Electrical", "2"),
                # Electrical - 4th Semester (49 students)
                ("Abhishek Koli", "abhishek.koli@gmail.com", "1", "Electrical", "4"),
                ("Kanish Sharma", "kanish@gmail.com", "2", "Electrical", "4"),
                ("Abishek Jintyal", "abishek@gmail.com", "3", "Electrical", "4"),
                ("Aditya", "aditya.e4@gmail.com", "4", "Electrical", "4"),
                ("Aditya Katoch", "aditya.katoch.e@gmail.com", "5", "Electrical", "4"),
                ("Aditya Dhiman", "aditya.dhiman@gmail.com", "6", "Electrical", "4"),
                ("Akhil", "akhil.e@gmail.com", "7", "Electrical", "4"),
                ("Akhil Kumar", "akhil.kumar.e@gmail.com", "8", "Electrical", "4"),
                ("Akshata", "akshata@gmail.com", "9", "Electrical", "4"),
                ("Akshata Devi", "akshata.devi@gmail.com", "10", "Electrical", "4"),
                ("Anmol", "anmol.e@gmail.com", "11", "Electrical", "4"),
                ("Anuruddha", "anuruddha@gmail.com", "12", "Electrical", "4"),
                ("Apurva", "apurva@gmail.com", "13", "Electrical", "4"),
                ("Arjun", "arjun@gmail.com", "14", "Electrical", "4"),
                (
                    "Arjun Choudhary",
                    "arjun.choudhary@gmail.com",
                    "15",
                    "Electrical",
                    "4",
                ),
                ("Aryush Kumar", "aryush@gmail.com", "16", "Electrical", "4"),
                ("Ashfaq", "ashfaq@gmail.com", "17", "Electrical", "4"),
                ("Ashok", "ashok@gmail.com", "18", "Electrical", "4"),
                ("Ashok Dogra", "ashok.dogra@gmail.com", "19", "Electrical", "4"),
                ("Aswat", "aswat@gmail.com", "20", "Electrical", "4"),
                ("Aswini", "aswini@gmail.com", "21", "Electrical", "4"),
                (
                    "Aswini Choudhary",
                    "aswini.choudhary@gmail.com",
                    "22",
                    "Electrical",
                    "4",
                ),
                ("Atri Din", "atri@gmail.com", "23", "Electrical", "4"),
                ("Avnish", "avnish@gmail.com", "24", "Electrical", "4"),
                ("Avnish Kumar", "avnish.kumar@gmail.com", "25", "Electrical", "4"),
                ("Baljit", "baljit@gmail.com", "26", "Electrical", "4"),
                ("Baljit Nath", "baljit.nath@gmail.com", "27", "Electrical", "4"),
                ("Basant", "basant@gmail.com", "28", "Electrical", "4"),
                ("Bhagwan Prasad", "bhagwan@gmail.com", "29", "Electrical", "4"),
                ("Bhavesh Sangha", "bhavesh@gmail.com", "30", "Electrical", "4"),
                ("Bhola", "bhola@gmail.com", "31", "Electrical", "4"),
                ("Bhuma", "bhuma@gmail.com", "32", "Electrical", "4"),
                ("Bhupendra", "bhupendra@gmail.com", "33", "Electrical", "4"),
                (
                    "Bikram Choudhary",
                    "bikram.choudhary@gmail.com",
                    "34",
                    "Electrical",
                    "4",
                ),
                ("Bikram Sharma", "bikram.sharma@gmail.com", "35", "Electrical", "4"),
                ("Brajesh Singh Guleria", "brajesh@gmail.com", "36", "Electrical", "4"),
                ("Britannia Choudhary", "britannia@gmail.com", "37", "Electrical", "4"),
                ("Chirash Mahajan", "chirash@gmail.com", "38", "Electrical", "4"),
                ("Chaman", "chaman@gmail.com", "39", "Electrical", "4"),
                ("Chamkur Singh", "chamkur@gmail.com", "40", "Electrical", "4"),
                ("Chet Ram", "chet@gmail.com", "41", "Electrical", "4"),
                ("Chirag", "chirag@gmail.com", "42", "Electrical", "4"),
                ("Chiranji", "chiranji@gmail.com", "43", "Electrical", "4"),
                ("Devinder Singh", "devinder@gmail.com", "44", "Electrical", "4"),
                ("Deepak", "deepak@gmail.com", "45", "Electrical", "4"),
                ("Dewan", "dewan@gmail.com", "46", "Electrical", "4"),
                ("Dharamvir Singh", "dharamvir@gmail.com", "47", "Electrical", "4"),
                ("Dhiraj", "dhiraj@gmail.com", "48", "Electrical", "4"),
                ("Yogesh", "yogesh.e@gmail.com", "49", "Electrical", "4"),
                # Electrical - 6th Semester (52 students)
                ("Aadi Chauhan", "aadi@gmail.com", "1", "Electrical", "6"),
                ("Abhishek", "abhishek.e6@gmail.com", "2", "Electrical", "6"),
                ("Abhishek", "abhishek.e6b@gmail.com", "3", "Electrical", "6"),
                ("Akhil Kumar", "akhil.e6@gmail.com", "4", "Electrical", "6"),
                ("Akshay Sharma", "akshay.sharma@gmail.com", "5", "Electrical", "6"),
                ("Amit Kumar", "amit.e6@gmail.com", "6", "Electrical", "6"),
                ("Anchal Kumar", "anchal@gmail.com", "7", "Electrical", "6"),
                ("Aniket", "aniket@gmail.com", "8", "Electrical", "6"),
                ("Ankur Verma", "ankur@gmail.com", "9", "Electrical", "6"),
                ("Anshul", "anshul.e6@gmail.com", "10", "Electrical", "6"),
                ("Anshul", "anshul.e6b@gmail.com", "11", "Electrical", "6"),
                ("Anju Kumar", "anju.e6@gmail.com", "12", "Electrical", "6"),
                ("Aryan Sharma", "aryan.sharma@gmail.com", "13", "Electrical", "6"),
                ("Aastha Thakur", "aastha@gmail.com", "14", "Electrical", "6"),
                ("Avinit", "avinit@gmail.com", "15", "Electrical", "6"),
                ("Ayush Koundal", "ayush.koundal@gmail.com", "16", "Electrical", "6"),
                ("Bhuprendra Singh", "bhuprendra@gmail.com", "17", "Electrical", "6"),
                ("Disha Choudhary", "disha@gmail.com", "18", "Electrical", "6"),
                ("Gourav Koundal", "gourav@gmail.com", "19", "Electrical", "6"),
                ("Harsh Sharma", "harsh.sharma@gmail.com", "20", "Electrical", "6"),
                (
                    "Harshit Choudhary",
                    "harshit.choudhary@gmail.com",
                    "21",
                    "Electrical",
                    "6",
                ),
                ("Himanshu Choudhary", "himanshu@gmail.com", "22", "Electrical", "6"),
                ("Ishant", "ishant.e6@gmail.com", "23", "Electrical", "6"),
                ("Karishthik", "karishthik@gmail.com", "24", "Electrical", "6"),
                ("Kartik Choudhary", "kartik.e6@gmail.com", "25", "Electrical", "6"),
                ("Kartik Thakur", "kartik.thakur@gmail.com", "26", "Electrical", "6"),
                ("Kshitij Goswan", "kshitij@gmail.com", "27", "Electrical", "6"),
                ("Kushav Rana", "kushav@gmail.com", "28", "Electrical", "6"),
                ("Mansi", "mansi@gmail.com", "29", "Electrical", "6"),
                ("Hussain Choudhary", "hussain@gmail.com", "30", "Electrical", "6"),
                ("Pratham Chandel", "pratham@gmail.com", "31", "Electrical", "6"),
                ("Praveen", "praveen.e6@gmail.com", "32", "Electrical", "6"),
                (
                    "Sahil Choudhary",
                    "sahil.choudhary@gmail.com",
                    "33",
                    "Electrical",
                    "6",
                ),
                ("Sahil Kumar", "sahil.kumar@gmail.com", "34", "Electrical", "6"),
                ("Sandeep Kumar", "sandeep.e6@gmail.com", "35", "Electrical", "6"),
                ("Sanjeev Kumar", "sanjeev.e6@gmail.com", "36", "Electrical", "6"),
                ("Shunny", "shunny@gmail.com", "37", "Electrical", "6"),
                ("Dikshant Rana", "dikshant@gmail.com", "38", "Electrical", "6"),
                ("Swasthik", "swasthik.e6@gmail.com", "39", "Electrical", "6"),
                ("Varun Kumar", "varun.e6@gmail.com", "40", "Electrical", "6"),
                (
                    "Abhishek Kumar",
                    "abhishek.kumar.e@gmail.com",
                    "41",
                    "Electrical",
                    "6",
                ),
                ("Kritika", "kritika@gmail.com", "42", "Electrical", "6"),
                ("Palak", "palak.e6@gmail.com", "43", "Electrical", "6"),
                ("Sejal", "sejal.e6@gmail.com", "44", "Electrical", "6"),
                ("Sujal Choudhary", "sujal@gmail.com", "45", "Electrical", "6"),
                ("Akshay", "akshay.e6@gmail.com", "46", "Electrical", "6"),
                ("Akshit Kumar", "akshit.e6@gmail.com", "47", "Electrical", "6"),
                ("Rahul Dhiman", "rahul.dhiman@gmail.com", "48", "Electrical", "6"),
                ("Banshul Ratra", "banshul.e6@gmail.com", "49", "Electrical", "6"),
                ("Aashit Rana", "aashit@gmail.com", "50", "Electrical", "6"),
                ("Priyanshu", "priyanshu@gmail.com", "51", "Electrical", "6"),
                ("Gautam Choudhary", "gautam@gmail.com", "52", "Electrical", "6"),
                # Electronics - 4th Semester (41 students)
                ("Abhav Choudhary", "abhav@gmail.com", "1", "Electronics", "4"),
                ("Aditya Verma", "aditya.verma.ec@gmail.com", "2", "Electronics", "4"),
                ("Aditya Verma", "aditya.verma.ec2@gmail.com", "3", "Electronics", "4"),
                ("Akhil Rana", "akhil.rana.ec@gmail.com", "4", "Electronics", "4"),
                (
                    "Akshay Choudhary",
                    "akshay.choudhary.ec@gmail.com",
                    "5",
                    "Electronics",
                    "4",
                ),
                ("Akshita", "akshita.ec@gmail.com", "6", "Electronics", "4"),
                ("Akshita Kumari", "akshita.kumari@gmail.com", "7", "Electronics", "4"),
                ("Aletia", "aletia@gmail.com", "8", "Electronics", "4"),
                ("Amar", "amar.ec@gmail.com", "9", "Electronics", "4"),
                ("Anish Kumar", "anish.kumar.ec@gmail.com", "10", "Electronics", "4"),
                ("Anikit", "anikit@gmail.com", "11", "Electronics", "4"),
                ("Amanpreet", "amanpreet@gmail.com", "12", "Electronics", "4"),
                (
                    "Amar Singh Chauhan",
                    "amar.singh@gmail.com",
                    "13",
                    "Electronics",
                    "4",
                ),
                ("Ashish", "ashish.ec@gmail.com", "14", "Electronics", "4"),
                ("Ankush", "ankush.ec@gmail.com", "15", "Electronics", "4"),
                ("Anshul", "anshul.ec@gmail.com", "16", "Electronics", "4"),
                ("Koushal Kumar", "koushal@gmail.com", "17", "Electronics", "4"),
                ("Kuman Verma", "kuman@gmail.com", "18", "Electronics", "4"),
                (
                    "Nikhil Koundal",
                    "nikhil.koundal.ec@gmail.com",
                    "19",
                    "Electronics",
                    "4",
                ),
                ("Rituesh Bharti", "rituesh@gmail.com", "20", "Electronics", "4"),
                ("Rishab", "rishab@gmail.com", "21", "Electronics", "4"),
                ("Priyanshu", "priyanshu.ec@gmail.com", "22", "Electronics", "4"),
                ("Pulkit Desai", "pulkit@gmail.com", "23", "Electronics", "4"),
                ("Barshil Saklani", "barshil@gmail.com", "24", "Electronics", "4"),
                ("Riya Nanda", "riya.nanda@gmail.com", "25", "Electronics", "4"),
                ("Sanjeep", "sanjeep@gmail.com", "26", "Electronics", "4"),
                ("Saicsar Koundal", "saicsar@gmail.com", "27", "Electronics", "4"),
                ("Shabaev Sharma", "shabaev@gmail.com", "28", "Electronics", "4"),
                ("Shubham", "shubham.ec@gmail.com", "29", "Electronics", "4"),
                ("Sunan Choudhary", "sunan@gmail.com", "30", "Electronics", "4"),
                ("Tanishk Guptai", "tanishk@gmail.com", "31", "Electronics", "4"),
                ("Taraishi Sharma", "taraishi@gmail.com", "32", "Electronics", "4"),
                ("Tashvir Singh", "tashvir@gmail.com", "33", "Electronics", "4"),
                ("Vishal", "vishal.ec@gmail.com", "34", "Electronics", "4"),
                ("Vishnesh Sharma", "vishnesh@gmail.com", "35", "Electronics", "4"),
                ("Anshul", "anshul.ec2@gmail.com", "36", "Electronics", "4"),
                ("Anuj", "anuj.ec@gmail.com", "37", "Electronics", "4"),
                ("Arjun Sharma", "arjun.sharma.ec@gmail.com", "38", "Electronics", "4"),
                ("Krish", "krish.ec@gmail.com", "39", "Electronics", "4"),
                ("Kuk Kum", "kuk@gmail.com", "40", "Electronics", "4"),
                ("Sakshi", "sakshi@gmail.com", "41", "Electronics", "4"),
                ("Shivani", "shivani@gmail.com", "42", "Electronics", "4"),
                ("Aryan", "aryan.ec@gmail.com", "43", "Electronics", "4"),
                ("Sahil", "sahil.ec@gmail.com", "44", "Electronics", "4"),
                # Electronics - 6th Semester (38 students)
                ("Abhishek", "abhishek.ec6@gmail.com", "1", "Electronics", "6"),
                ("Abidheye Choudhary", "abidheye@gmail.com", "2", "Electronics", "6"),
                ("Akshet Dhiman", "akshet@gmail.com", "3", "Electronics", "6"),
                ("Ankit Dawahal", "ankit.dawahal@gmail.com", "4", "Electronics", "6"),
                ("Areshita Thakur", "areshita@gmail.com", "5", "Electronics", "6"),
                ("Ashvi", "ashvi@gmail.com", "6", "Electronics", "6"),
                ("Bhuwan Singh", "bhuwan.singh@gmail.com", "7", "Electronics", "6"),
                (
                    "Gaurav Choudhary",
                    "gaurav.choudhary@gmail.com",
                    "8",
                    "Electronics",
                    "6",
                ),
                (
                    "Himanshu Choudhary",
                    "himanshu.choudhary@gmail.com",
                    "9",
                    "Electronics",
                    "6",
                ),
                ("Luv Kumar", "luv@gmail.com", "10", "Electronics", "6"),
                (
                    "Mahak Choudhary",
                    "mahak.choudhary@gmail.com",
                    "11",
                    "Electronics",
                    "6",
                ),
                ("Mehak Dogra", "mehak@gmail.com", "12", "Electronics", "6"),
                ("Nidhi", "nidhi@gmail.com", "13", "Electronics", "6"),
                (
                    "Nitka Choudhary",
                    "nitka.choudhary@gmail.com",
                    "14",
                    "Electronics",
                    "6",
                ),
                ("Nitka Kumari", "nitka.kumari@gmail.com", "15", "Electronics", "6"),
                ("Nitin", "nitin@gmail.com", "16", "Electronics", "6"),
                ("Parihit Sharma", "parihit@gmail.com", "17", "Electronics", "6"),
                ("Raghita Thakur", "raghita@gmail.com", "18", "Electronics", "6"),
                ("Ritika", "ritika@gmail.com", "19", "Electronics", "6"),
                ("Rustam", "rustam@gmail.com", "20", "Electronics", "6"),
                ("Sakshi Devi", "sakshi.devi@gmail.com", "21", "Electronics", "6"),
                ("Sameck Sharma", "sameck@gmail.com", "22", "Electronics", "6"),
                ("Baluni", "baluni@gmail.com", "23", "Electronics", "6"),
                ("Shweta Kumari", "shweta@gmail.com", "24", "Electronics", "6"),
                ("Suneha", "suneha@gmail.com", "25", "Electronics", "6"),
                ("Tanisha", "tanisha.ec6@gmail.com", "26", "Electronics", "6"),
                ("Tanishka", "tanishka@gmail.com", "27", "Electronics", "6"),
                ("Varun Guleria", "varun.guleria@gmail.com", "28", "Electronics", "6"),
                (
                    "Ayush Choudhary",
                    "ayush.choudhary.ec6@gmail.com",
                    "29",
                    "Electronics",
                    "6",
                ),
                ("Baneshita", "baneshita@gmail.com", "30", "Electronics", "6"),
                ("Kartik Bhatt", "kartik.bhatt@gmail.com", "31", "Electronics", "6"),
                ("Kunti Sharma", "kunti@gmail.com", "32", "Electronics", "6"),
                ("Laxman Thakur", "laxman@gmail.com", "33", "Electronics", "6"),
                ("Riya Kumari", "riya.kumari.ec@gmail.com", "34", "Electronics", "6"),
                ("Ritik Sharma", "ritik.sharma@gmail.com", "35", "Electronics", "6"),
                (
                    "Aditya Sharma",
                    "aditya.sharma.ec6@gmail.com",
                    "36",
                    "Electronics",
                    "6",
                ),
                (
                    "Govind Singh",
                    "govind.singh.ec6@gmail.com",
                    "37",
                    "Electronics",
                    "6",
                ),
                ("Dikshant Rana", "dikshant.rana@gmail.com", "38", "Electronics", "6"),
                # Electronics - 2nd Semester (50 students)
                (
                    "Abhishek Mittal",
                    "abhishek.mittal.ec2@gmail.com",
                    "1",
                    "Electronics",
                    "2",
                ),
                (
                    "Aditya Verma",
                    "aditya.verma.ec2a@gmail.com",
                    "2",
                    "Electronics",
                    "2",
                ),
                (
                    "Aditya Verma",
                    "aditya.verma.ec2b@gmail.com",
                    "3",
                    "Electronics",
                    "2",
                ),
                (
                    "Aditya Thakur",
                    "aditya.thakur.ec@gmail.com",
                    "4",
                    "Electronics",
                    "2",
                ),
                (
                    "Aditya Katoch",
                    "aditya.katoch.ec@gmail.com",
                    "5",
                    "Electronics",
                    "2",
                ),
                (
                    "Aditya Sharma",
                    "aditya.sharma.ec2@gmail.com",
                    "6",
                    "Electronics",
                    "2",
                ),
                ("Akasshi Mehra", "akasshi.mehra@gmail.com", "7", "Electronics", "2"),
                ("Akshara Thakur", "akshara.thakur@gmail.com", "8", "Electronics", "2"),
                ("Arkshit Sharma", "arkshit.sharma@gmail.com", "9", "Electronics", "2"),
                ("Anita", "anita.ec@gmail.com", "10", "Electronics", "2"),
                ("Areen", "areen.ec@gmail.com", "11", "Electronics", "2"),
                ("Aryan Dhiman", "aryan.dhiman.ec@gmail.com", "12", "Electronics", "2"),
                ("Aryan Jamwal", "aryan.jamwal.ec@gmail.com", "13", "Electronics", "2"),
                ("Ayush", "ayush.ec@gmail.com", "14", "Electronics", "2"),
                (
                    "Banshul Kumar",
                    "banshul.kumar.ec@gmail.com",
                    "15",
                    "Electronics",
                    "2",
                ),
                (
                    "Diksha Chauhan",
                    "diksha.chauhan.ec@gmail.com",
                    "16",
                    "Electronics",
                    "2",
                ),
                ("Divyanshi", "divyanshi.ec@gmail.com", "17", "Electronics", "2"),
                ("Harsh", "harsh.ec@gmail.com", "18", "Electronics", "2"),
                ("Harshi", "harshi.ec@gmail.com", "19", "Electronics", "2"),
                (
                    "Harshit Kapoor",
                    "harshit.kapoor.ec@gmail.com",
                    "20",
                    "Electronics",
                    "2",
                ),
                ("Isha Kumari", "isha.kumari.ec@gmail.com", "21", "Electronics", "2"),
                ("Ishaan Kumar", "ishaan.kumar.ec@gmail.com", "22", "Electronics", "2"),
                (
                    "Muskan Choudhary",
                    "muskan.choudhary.ec@gmail.com",
                    "23",
                    "Electronics",
                    "2",
                ),
                ("Piyush", "piyush.ec@gmail.com", "24", "Electronics", "2"),
                ("Priya", "priya.ec@gmail.com", "25", "Electronics", "2"),
                (
                    "Pushkar Pathania",
                    "pushkar.pathania@gmail.com",
                    "26",
                    "Electronics",
                    "2",
                ),
                ("Rasik Jarwal", "rasik.jarwal@gmail.com", "27", "Electronics", "2"),
                ("Riya Dhiman", "riya.dhiman.ec@gmail.com", "28", "Electronics", "2"),
                (
                    "Sarshi Koundal",
                    "sarshi.koundal@gmail.com",
                    "29",
                    "Electronics",
                    "2",
                ),
                ("Saniya", "saniya.ec@gmail.com", "30", "Electronics", "2"),
                ("Sejal", "sejal.ec@gmail.com", "31", "Electronics", "2"),
                ("Shagun", "shagun.ec@gmail.com", "32", "Electronics", "2"),
                (
                    "Shiven Sharma",
                    "shiven.sharma.ec@gmail.com",
                    "33",
                    "Electronics",
                    "2",
                ),
                ("Shreya", "shreya.ec@gmail.com", "34", "Electronics", "2"),
                (
                    "Simran Bharti",
                    "simran.bharti.ec@gmail.com",
                    "35",
                    "Electronics",
                    "2",
                ),
                ("Sneha", "sneha.ec@gmail.com", "36", "Electronics", "2"),
                ("Tanisha", "tanisha.ec2@gmail.com", "37", "Electronics", "2"),
                (
                    "Vanshika Naryal",
                    "vanshika.naryal@gmail.com",
                    "38",
                    "Electronics",
                    "2",
                ),
                (
                    "Vishakha Koundal",
                    "vishakha.koundal.ec@gmail.com",
                    "39",
                    "Electronics",
                    "2",
                ),
                (
                    "Ankit Koundal",
                    "ankit.koundal.ec@gmail.com",
                    "40",
                    "Electronics",
                    "2",
                ),
                (
                    "Ankit Gulerja",
                    "ankit.gulerja.ec@gmail.com",
                    "41",
                    "Electronics",
                    "2",
                ),
                ("Akshay Kumar", "akshay.kumar.ec@gmail.com", "42", "Electronics", "2"),
                ("Abhay Thakur", "abhay.thakur.ec@gmail.com", "43", "Electronics", "2"),
                (
                    "Parshant Sharma",
                    "parshant.sharma.ec@gmail.com",
                    "44",
                    "Electronics",
                    "2",
                ),
                ("Uday Thakur", "uday.thakur.ec@gmail.com", "45", "Electronics", "2"),
                ("Anshika", "anshika.ec@gmail.com", "46", "Electronics", "2"),
                ("Vansh Rana", "vansh.rana.ec@gmail.com", "47", "Electronics", "2"),
                (
                    "Disha Choudhary",
                    "disha.choudhary.ec@gmail.com",
                    "48",
                    "Electronics",
                    "2",
                ),
                ("Mannat Walia", "mannat.walia.ec@gmail.com", "49", "Electronics", "2"),
                (
                    "Krish Singh Athwal",
                    "krish.singh.athwal.ec@gmail.com",
                    "50",
                    "Electronics",
                    "2",
                ),
                # Instrumentation - 2nd Semester (40 students)
                (
                    "Abhishek Sharma",
                    "abhishek.sharma.in@gmail.com",
                    "1",
                    "Instrumentation",
                    "2",
                ),
                ("Aditya", "aditya.in@gmail.com", "2", "Instrumentation", "2"),
                (
                    "Aditya Rana",
                    "aditya.rana.in@gmail.com",
                    "3",
                    "Instrumentation",
                    "2",
                ),
                ("Aashay Kumar", "aashay@gmail.com", "4", "Instrumentation", "2"),
                ("Anamika Lagwal", "anamika@gmail.com", "5", "Instrumentation", "2"),
                ("Ankit", "ankit.in@gmail.com", "6", "Instrumentation", "2"),
                ("Anjana Devi", "anjana@gmail.com", "7", "Instrumentation", "2"),
                ("Anusha", "anusha@gmail.com", "8", "Instrumentation", "2"),
                ("Arpit Koundal", "arpit@gmail.com", "9", "Instrumentation", "2"),
                (
                    "Aryan Kumar",
                    "aryan.kumar.in@gmail.com",
                    "10",
                    "Instrumentation",
                    "2",
                ),
                (
                    "Ashish Choudhary",
                    "ashish.choudhary.in@gmail.com",
                    "11",
                    "Instrumentation",
                    "2",
                ),
                ("Ashil", "ashil.in@gmail.com", "12", "Instrumentation", "2"),
                ("Ayush", "ayush.in@gmail.com", "13", "Instrumentation", "2"),
                ("Jayesh", "jayesh@gmail.com", "14", "Instrumentation", "2"),
                ("Kaashish", "kaashish@gmail.com", "15", "Instrumentation", "2"),
                (
                    "Krish Koundal",
                    "krish.koundal.in@gmail.com",
                    "16",
                    "Instrumentation",
                    "2",
                ),
                (
                    "Manoj Kumar",
                    "manoj.kumar.in@gmail.com",
                    "17",
                    "Instrumentation",
                    "2",
                ),
                ("Palak", "palak.in@gmail.com", "18", "Instrumentation", "2"),
                (
                    "Rahul Choudhary",
                    "rahul.choudhary.in@gmail.com",
                    "19",
                    "Instrumentation",
                    "2",
                ),
                (
                    "Rahul Maharaja",
                    "rahul.maharaja@gmail.com",
                    "20",
                    "Instrumentation",
                    "2",
                ),
                ("Reetul Choudhary", "reetul@gmail.com", "21", "Instrumentation", "2"),
                ("Ritam", "ritam@gmail.com", "22", "Instrumentation", "2"),
                ("Sahil", "sahil.in@gmail.com", "23", "Instrumentation", "2"),
                (
                    "Shardham Kumar",
                    "shardham.in2@gmail.com",
                    "24",
                    "Instrumentation",
                    "2",
                ),
                ("Sourav Dogra", "sourav@gmail.com", "25", "Instrumentation", "2"),
                ("Sujal", "sujal.in@gmail.com", "26", "Instrumentation", "2"),
                ("Sujan Kumar", "sujan@gmail.com", "27", "Instrumentation", "2"),
                ("Tulisha", "tulisha@gmail.com", "28", "Instrumentation", "2"),
                ("Tushar Kumar", "tushar@gmail.com", "29", "Instrumentation", "2"),
                ("Vinod Prasad", "vinod@gmail.com", "30", "Instrumentation", "2"),
                ("Aditya", "aditya.in2@gmail.com", "31", "Instrumentation", "2"),
                ("Anu Rana", "anu@gmail.com", "32", "Instrumentation", "2"),
                ("Bhata", "bhata@gmail.com", "33", "Instrumentation", "2"),
                (
                    "Piyush Kumar",
                    "piyush.kumar.in@gmail.com",
                    "34",
                    "Instrumentation",
                    "2",
                ),
                ("Prince Kumar", "prince@gmail.com", "35", "Instrumentation", "2"),
                ("Shavnam", "shavnam@gmail.com", "36", "Instrumentation", "2"),
                ("Shivam", "shivam.in@gmail.com", "37", "Instrumentation", "2"),
                (
                    "Sunil Kumar",
                    "sunil.kumar.in@gmail.com",
                    "38",
                    "Instrumentation",
                    "2",
                ),
                (
                    "Sujal Kumar",
                    "sujal.kumar.in@gmail.com",
                    "39",
                    "Instrumentation",
                    "2",
                ),
                (
                    "Sumit Kumar",
                    "sumit.kumar.in@gmail.com",
                    "40",
                    "Instrumentation",
                    "2",
                ),
                # Instrumentation - 4th Semester (44 students)
                ("Ajay", "ajay@gmail.com", "1", "Instrumentation", "4"),
                ("Akhil", "akhil.in4@gmail.com", "2", "Instrumentation", "4"),
                ("Akshay Rana", "akshay.rana@gmail.com", "3", "Instrumentation", "4"),
                ("Amandeep Singh", "amandeep@gmail.com", "4", "Instrumentation", "4"),
                ("Aman Joshi", "aman.joshi@gmail.com", "5", "Instrumentation", "4"),
                ("Amrit Kumar", "amrit@gmail.com", "6", "Instrumentation", "4"),
                (
                    "Ananya Choudhary",
                    "ananya.choudhary@gmail.com",
                    "7",
                    "Instrumentation",
                    "4",
                ),
                ("Ankit", "ankit.in4@gmail.com", "8", "Instrumentation", "4"),
                ("Anmol Verma", "anmol.verma@gmail.com", "9", "Instrumentation", "4"),
                ("Anshul", "anshul.in4@gmail.com", "10", "Instrumentation", "4"),
                (
                    "Arjun Kumar",
                    "arjun.kumar.in@gmail.com",
                    "11",
                    "Instrumentation",
                    "4",
                ),
                (
                    "Arjun Koundal",
                    "arjun.koundal@gmail.com",
                    "12",
                    "Instrumentation",
                    "4",
                ),
                ("Arun", "arun.in@gmail.com", "13", "Instrumentation", "4"),
                ("Arun Rana", "arun.rana@gmail.com", "14", "Instrumentation", "4"),
                ("Ashu Sharma", "ashu.sharma@gmail.com", "15", "Instrumentation", "4"),
                ("Ashish", "ashish.in4@gmail.com", "16", "Instrumentation", "4"),
                ("Ashok", "ashok.in@gmail.com", "17", "Instrumentation", "4"),
                ("Asmita", "asmita@gmail.com", "18", "Instrumentation", "4"),
                ("Aswani", "aswani@gmail.com", "19", "Instrumentation", "4"),
                (
                    "Aswani Kumar",
                    "aswani.kumar@gmail.com",
                    "20",
                    "Instrumentation",
                    "4",
                ),
                (
                    "Atish Sharma",
                    "atish.sharma@gmail.com",
                    "21",
                    "Instrumentation",
                    "4",
                ),
                ("Avnish", "avnish.in@gmail.com", "22", "Instrumentation", "4"),
                ("Ayush", "ayush.in4@gmail.com", "23", "Instrumentation", "4"),
                ("Ayush Raj", "ayush.raj@gmail.com", "24", "Instrumentation", "4"),
                ("Aditya", "aditya.in4@gmail.com", "25", "Instrumentation", "4"),
                (
                    "Aditya Sharma",
                    "aditya.sharma.in@gmail.com",
                    "26",
                    "Instrumentation",
                    "4",
                ),
                ("Aman", "aman.in@gmail.com", "27", "Instrumentation", "4"),
                (
                    "Aman Choudhary",
                    "aman.choudhary.in@gmail.com",
                    "28",
                    "Instrumentation",
                    "4",
                ),
                ("Apoorva", "apoorva.in@gmail.com", "29", "Instrumentation", "4"),
                ("Aakash Kumar", "aakash@gmail.com", "30", "Instrumentation", "4"),
                ("Aakul", "aakul@gmail.com", "31", "Instrumentation", "4"),
                (
                    "Aakul Vasarla",
                    "aakul.vasarla@gmail.com",
                    "32",
                    "Instrumentation",
                    "4",
                ),
                ("Abhashit", "abhashit@gmail.com", "33", "Instrumentation", "4"),
                ("Abhay", "abhay.in@gmail.com", "34", "Instrumentation", "4"),
                (
                    "Abhishek Kumar",
                    "abhishek.kumar.in@gmail.com",
                    "35",
                    "Instrumentation",
                    "4",
                ),
                ("Arjun", "arjun.in4@gmail.com", "36", "Instrumentation", "4"),
                ("Aryan", "aryan.in@gmail.com", "37", "Instrumentation", "4"),
                ("Arun Sharma", "arun.sharma@gmail.com", "38", "Instrumentation", "4"),
                ("Angad", "angad@gmail.com", "39", "Instrumentation", "4"),
                ("Ankita", "ankita.in@gmail.com", "40", "Instrumentation", "4"),
                (
                    "Anushka Sharma",
                    "anushka.sharma.in@gmail.com",
                    "41",
                    "Instrumentation",
                    "4",
                ),
                ("Rishant Agarwal", "rishant@gmail.com", "42", "Instrumentation", "4"),
                (
                    "Rajesh Kumar",
                    "rajesh.kumar.in@gmail.com",
                    "43",
                    "Instrumentation",
                    "4",
                ),
                ("Raj Kumar", "raj.kumar.in@gmail.com", "44", "Instrumentation", "4"),
                # Instrumentation - 6th Semester (as per notice)
                (
                    "Abhishek Kumar",
                    "abhishek.kumar.in6@gmail.com",
                    "1",
                    "Instrumentation",
                    "6",
                ),
                ("Akshay", "akshay.in6@gmail.com", "2", "Instrumentation", "6"),
                (
                    "Animesh Rana",
                    "animesh.rana.in6@gmail.com",
                    "3",
                    "Instrumentation",
                    "6",
                ),
                ("Anjali", "anjali.in6@gmail.com", "4", "Instrumentation", "6"),
                ("Anu Kumari", "anu.kumari.in6@gmail.com", "5", "Instrumentation", "6"),
                ("Ayush", "ayush1.in6@gmail.com", "6", "Instrumentation", "6"),
                ("Ayush", "ayush2.in6@gmail.com", "7", "Instrumentation", "6"),
                (
                    "Gaurav Shukla",
                    "gaurav.shukla.in6@gmail.com",
                    "8",
                    "Instrumentation",
                    "6",
                ),
                ("Harshit", "harshit.in6@gmail.com", "9", "Instrumentation", "6"),
                (
                    "Keshav (TFW)",
                    "keshav.tfw.in6@gmail.com",
                    "10",
                    "Instrumentation",
                    "6",
                ),
                ("Neha", "neha.in6@gmail.com", "11", "Instrumentation", "6"),
                (
                    "Nikhil Choudhary",
                    "nikhil.choudhary.in6@gmail.com",
                    "12",
                    "Instrumentation",
                    "6",
                ),
                (
                    "Pratham Choudhary",
                    "pratham.choudhary.in6@gmail.com",
                    "13",
                    "Instrumentation",
                    "6",
                ),
                ("Priya", "priya.in6@gmail.com", "14", "Instrumentation", "6"),
                ("Priyanshu", "priyanshu.in6@gmail.com", "15", "Instrumentation", "6"),
                (
                    "Priyanshu Choudhary",
                    "priyanshu.choudhary.in6@gmail.com",
                    "16",
                    "Instrumentation",
                    "6",
                ),
                ("Rithik", "rithik.in6@gmail.com", "17", "Instrumentation", "6"),
                (
                    "Sahib Singh Bedi",
                    "sahib.singh.bedi.in6@gmail.com",
                    "18",
                    "Instrumentation",
                    "6",
                ),
                ("Sahil", "sahil.in6@gmail.com", "19", "Instrumentation", "6"),
                ("Shahil", "shahil.in6@gmail.com", "20", "Instrumentation", "6"),
                ("Shubham", "shubham1.in6@gmail.com", "21", "Instrumentation", "6"),
                ("Sourabh", "sourabh.in6@gmail.com", "22", "Instrumentation", "6"),
                (
                    "Varun (TFW)",
                    "varun.tfw.in6@gmail.com",
                    "23",
                    "Instrumentation",
                    "6",
                ),
                ("Varun", "varun.in6@gmail.com", "24", "Instrumentation", "6"),
                (
                    "Vinay Kumar",
                    "vinay.kumar.in6@gmail.com",
                    "25",
                    "Instrumentation",
                    "6",
                ),
                ("Shubham", "shubham2.in6@gmail.com", "26", "Instrumentation", "6"),
                ("Akanksha", "akanksha.in6@gmail.com", "27", "Instrumentation", "6"),
                (
                    "Aman Kumar",
                    "aman.kumar.in6@gmail.com",
                    "28",
                    "Instrumentation",
                    "6",
                ),
                (
                    "Aryan Choudhary",
                    "aryan.choudhary.in6@gmail.com",
                    "29",
                    "Instrumentation",
                    "6",
                ),
                ("Dishant", "dishant.in6@gmail.com", "30", "Instrumentation", "6"),
                (
                    "Madhu Bala",
                    "madhu.bala.in6@gmail.com",
                    "31",
                    "Instrumentation",
                    "6",
                ),
                ("Shivam", "shivam.in6@gmail.com", "32", "Instrumentation", "6"),
                ("Prince", "prince.in6@gmail.com", "33", "Instrumentation", "6"),
                ("Abhishek", "abhishek.in6@gmail.com", "34", "Instrumentation", "6"),
                ("Akshay", "akshay2.in6@gmail.com", "35", "Instrumentation", "6"),
                (
                    "Rijul Kalia",
                    "rijul.kalia.in6@gmail.com",
                    "36",
                    "Instrumentation",
                    "6",
                ),
                # Mechanical - Semester 6
                (
                    "Akshit Pathania",
                    "akshit.pathania.me6@gmail.com",
                    "01",
                    "Mechanical",
                    "6",
                ),
                ("Aman Kumar", "aman.kumar.me6@gmail.com", "02", "Mechanical", "6"),
                ("Aman Sanjit", "aman.sanjit.me6@gmail.com", "03/2", "Mechanical", "6"),
                (
                    "Anirudh Kumar",
                    "anirudh.kumar.me6@gmail.com",
                    "04",
                    "Mechanical",
                    "6",
                ),
                ("Anmol", "anmol.me6@gmail.com", "05", "Mechanical", "6"),
                ("Anshul Kumar", "anshul.kumar.me6@gmail.com", "06", "Mechanical", "6"),
                ("Anshul Rana", "anshul.rana.me6@gmail.com", "07", "Mechanical", "6"),
                ("Anshul Rana", "anshul.rana2.me6@gmail.com", "08", "Mechanical", "6"),
                ("Archit Kumar", "archit.kumar.me6@gmail.com", "09", "Mechanical", "6"),
                ("Arpit", "arpit.me6@gmail.com", "10", "Mechanical", "6"),
                ("Aryan", "aryan.me6@gmail.com", "11", "Mechanical", "6"),
                (
                    "Chandan Kumar",
                    "chandan.kumar.me6@gmail.com",
                    "12",
                    "Mechanical",
                    "6",
                ),
                ("Deepak", "deepak.me6@gmail.com", "13", "Mechanical", "6"),
                (
                    "Divyansh Thakur",
                    "divyansh.thakur.me6@gmail.com",
                    "14",
                    "Mechanical",
                    "6",
                ),
                ("Freed Ali", "freed.ali.me6@gmail.com", "15", "Mechanical", "6"),
                ("Jasman", "jasman.me6@gmail.com", "16", "Mechanical", "6"),
                (
                    "Mandeep Singh",
                    "mandeep.singh.me6@gmail.com",
                    "17",
                    "Mechanical",
                    "6",
                ),
                ("Nikhil", "nikhil.me6@gmail.com", "18", "Mechanical", "6"),
                (
                    "Nikhil Choudhary",
                    "nikhil.choudhary.me6@gmail.com",
                    "19",
                    "Mechanical",
                    "6",
                ),
                ("Nishant", "nishant.me6@gmail.com", "20", "Mechanical", "6"),
                ("Nitish Kumar", "nitish.kumar.me6@gmail.com", "21", "Mechanical", "6"),
                (
                    "Pardeep Kumar",
                    "pardeep.kumar.me6@gmail.com",
                    "22",
                    "Mechanical",
                    "6",
                ),
                ("Piyush", "piyush.me6@gmail.com", "23", "Mechanical", "6"),
                (
                    "Rahul Koundal",
                    "rahul.koundal.me6@gmail.com",
                    "24",
                    "Mechanical",
                    "6",
                ),
                (
                    "Rajnish Choudhary",
                    "rajnish.choudhary.me6@gmail.com",
                    "25",
                    "Mechanical",
                    "6",
                ),
                ("Rajul Parmar", "rajul.parmar.me6@gmail.com", "26", "Mechanical", "6"),
                ("Raman Kumar", "raman.kumar.me6@gmail.com", "27", "Mechanical", "6"),
                ("Sahil Goma", "sahil.goma.me6@gmail.com", "28", "Mechanical", "6"),
                ("Sandeep Rana", "sandeep.rana.me6@gmail.com", "29", "Mechanical", "6"),
                (
                    "Shagun Singh Pathania",
                    "shagun.pathania.me6@gmail.com",
                    "30",
                    "Mechanical",
                    "6",
                ),
                (
                    "Subham Kondal",
                    "subham.kondal.me6@gmail.com",
                    "31",
                    "Mechanical",
                    "6",
                ),
                ("Suraj Kumar", "suraj.kumar.me6@gmail.com", "32", "Mechanical", "6"),
                ("Tarun Pal", "tarun.pal.me6@gmail.com", "33", "Mechanical", "6"),
                (
                    "Vanshul Sharma",
                    "vanshul.sharma.me6@gmail.com",
                    "34",
                    "Mechanical",
                    "6",
                ),
                ("Vishal Kumar", "vishal.kumar.me6@gmail.com", "35", "Mechanical", "6"),
                (
                    "Rupansh Koundal",
                    "rupansh.koundal.me6@gmail.com",
                    "36",
                    "Mechanical",
                    "6",
                ),
                (
                    "Abhishek Bhardwaj",
                    "abhishek.me6@gmail.com",
                    "37",
                    "Mechanical",
                    "6",
                ),
                ("Ansul Kumar", "ansu.kumar.me6@gmail.com", "38", "Mechanical", "6"),
                (
                    "Prince Bhatia",
                    "prince.bhatia.me6@gmail.com",
                    "39",
                    "Mechanical",
                    "6",
                ),
                (
                    "Sourav Tatyal",
                    "sourav.tatyal.me6@gmail.com",
                    "40",
                    "Mechanical",
                    "6",
                ),
                ("Vivek", "vivek.me6@gmail.com", "41", "Mechanical", "6"),
                (
                    "Thakur Nitish Singh Baryal",
                    "nitish.baryal.me6@gmail.com",
                    "42",
                    "Mechanical",
                    "6",
                ),
                ("Akshit", "akshit.me6@gmail.com", "43", "Mechanical", "6"),
                ("Anurag Soni", "anurag.soni.me6@gmail.com", "44", "Mechanical", "6"),
            ]

            students = []
            for name, email, roll_num, branch, semester in students_data:
                student = User(
                    name=name,
                    email=email,
                    password=generate_password_hash(roll_num),
                    role="student",
                    roll_number=roll_num,
                    branch=branch,
                    semester=semester,
                )
                students.append(student)

            teacher_users = []
            for name, email, department, subject in teachers_data:
                teacher_users.append(
                    User(
                        name=name,
                        email=email.lower(),
                        password=generate_password_hash("teacher123"),
                        role="teacher",
                        department=department,
                        subject=subject,
                    )
                )

            db.session.add_all([admin, default_teacher] + teacher_users + students)
            db.session.commit()

    app.run(debug=True)
