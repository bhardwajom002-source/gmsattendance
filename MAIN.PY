# gms.py
"""
GMS SCHOOL DHAMALA — single-file Flask app (ONLY FLASK)
Features:
 - Teacher login (username=Rekha, password=Rekha) with password hashing
 - Teacher password reset via OTP sent to ADMIN_RESET_EMAIL (only teacher)
 - Student signup & login (student sees only their own data)
 - Teacher dashboard: Add / Edit / DELETE student, Attendance (year -> present/absent)
 - Aadhaar and Phone validations
 - Export CSV (all or selected), wa.me link generator
 - Single file + SQLite (auto-create DB)
 - UI: Bootstrap + FontAwesome

How to run (Windows CMD):
 1) Put gms.py into folder, e.g., C:\java
 2) Open CMD and run:
    cd C:\java
    pip install flask werkzeug pandas
    python gms.py
 3) Open browser: http://127.0.0.1:5000

Important for OTP emails:
 - Configure SMTP env vars (or edit SMTP_USER / SMTP_PASS below)
 - For Gmail use an App Password (do not use your normal Gmail password).
"""

import os, re, io, csv, random, sqlite3, smtplib
from datetime import datetime
from email.message import EmailMessage
from flask import (
    Flask, render_template_string, request, redirect, url_for,
    session, flash, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------- CONFIG ----------------
APP_SECRET = os.getenv("APP_SECRET", "change_this_secret_for_prod")
DB_FILE = os.path.join(os.path.dirname(__file__), "gms_dhamala.db")

# SMTP settings (edit or set environment variables)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")   # sender email (must be set for OTP)
SMTP_PASS = os.getenv("SMTP_PASS", "")   # app password for sender
ADMIN_RESET_EMAIL = "rani1987rekha@gmail.com"   # OTP will be sent here (teacher reset)
# ----------------------------------------

app = Flask(__name__)
app.secret_key = APP_SECRET

# ---------- DB helpers ----------
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      role TEXT,
      username TEXT UNIQUE,
      password TEXT,
      email TEXT,
      name TEXT,
      class TEXT,
      father_name TEXT,
      mother_name TEXT,
      aadhaar TEXT,
      place TEXT,
      dob TEXT,
      phone TEXT,
      whatsapp TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      student_id INTEGER,
      year INTEGER,
      present INTEGER,
      absent INTEGER,
      FOREIGN KEY(student_id) REFERENCES users(id)
    );
    """)
    # default teacher (if not exists) with hashed password
    cur.execute("SELECT id FROM users WHERE role='teacher' AND username='Rekha'")
    if cur.fetchone() is None:
        cur.execute("INSERT INTO users (role, username, password, email, name) VALUES (?,?,?,?,?)",
                    ("teacher", "Rekha", generate_password_hash("Rekha"), ADMIN_RESET_EMAIL, "Rekha Rani"))
    conn.commit(); conn.close()

init_db()

# ---------- Utilities ----------
def send_otp_email(dest_email, otp_code):
    """Send OTP email via configured SMTP. Returns (ok, message)."""
    try:
        msg = EmailMessage()
        msg["Subject"] = "GMS Dhamala - Password Reset OTP"
        msg["From"] = SMTP_USER or "no-reply@example.com"
        msg["To"] = dest_email
        msg.set_content(f"Your OTP for teacher password reset is: {otp_code}\n\nIf you did not request this, ignore.")
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return True, "OTP sent"
    except Exception as e:
        return False, str(e)

def valid_aadhaar(a): return bool(re.fullmatch(r"\d{12}", a)) if a else True
def valid_phone(p): return bool(re.fullmatch(r"\d{10}", p)) if p else True
def random_username(name):
    base = re.sub(r"\s+","_", (name or "user").strip().lower())
    return f"{base}_{random.randint(100,999)}"

def get_user_by_username(u):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=?", (u,))
    r = cur.fetchone(); conn.close(); return r

def get_user_by_id(uid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (uid,))
    r = cur.fetchone(); conn.close(); return r

def create_student(data):
    conn = get_db(); cur = conn.cursor()
    cur.execute("""INSERT INTO users (role, username, password, email, name, class, father_name, mother_name, aadhaar, place, dob, phone, whatsapp)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("student", data["username"], generate_password_hash(data["password"]), data.get("email",""),
                 data["name"], data.get("class",""), data.get("father_name",""), data.get("mother_name",""),
                 data.get("aadhaar",""), data.get("place",""), data.get("dob",""), data.get("phone",""), data.get("whatsapp","")))
    conn.commit(); nid = cur.lastrowid; conn.close(); return nid

def update_student(uid, data):
    conn = get_db(); cur = conn.cursor()
    cur.execute("""UPDATE users SET name=?, class=?, father_name=?, mother_name=?, aadhaar=?, place=?, dob=?, phone=?, whatsapp=?, email=?
                   WHERE id=?""",
                (data["name"], data["class"], data["father_name"], data["mother_name"], data["aadhaar"],
                 data["place"], data["dob"], data["phone"], data["whatsapp"], data["email"], uid))
    conn.commit(); conn.close()

def delete_student(uid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM attendance WHERE student_id=?", (uid,))
    cur.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit(); conn.close()

def list_students():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE role='student' ORDER BY class, name")
    rows = cur.fetchall(); conn.close(); return rows

def add_or_update_attendance(sid, year, present, absent):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id FROM attendance WHERE student_id=? AND year=?", (sid, year))
    f = cur.fetchone()
    if f:
        cur.execute("UPDATE attendance SET present=?, absent=? WHERE id=?", (present, absent, f["id"]))
    else:
        cur.execute("INSERT INTO attendance (student_id, year, present, absent) VALUES (?,?,?,?)", (sid, year, present, absent))
    conn.commit(); conn.close()

def get_attendance(student_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT year, present, absent FROM attendance WHERE student_id=?", (student_id,))
    r = cur.fetchall(); conn.close(); return r

# ---------- Templates (Bootstrap + FontAwesome) ----------
BASE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>GMS School Dhamala</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>.card{box-shadow:0 6px 20px rgba(0,0,0,0.06);border-radius:12px}.small-muted{color:#6c757d}</style></head><body class="bg-light">
<nav class="navbar navbar-expand-lg bg-white border-bottom"><div class="container">
<a class="navbar-brand fw-bold" href="{{ url_for('home') }}">GMS School Dhamala</a>
<div>{% if session.get('user') %}<span class="me-3 small-muted">Hello, {{ session.get('user_name') }} ({{ session.get('user_role') }})</span><a class="btn btn-outline-secondary btn-sm" href="{{ url_for('logout') }}">Logout</a>{% endif %}</div></div></nav>
<div class="container my-4">{% with messages = get_flashed_messages(with_categories=true) %}
{% if messages %}{% for cat,msg in messages %}<div class="alert alert-{{cat}} alert-dismissible fade show" role="alert">{{msg}}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>{% endfor %}{% endif %}{% endwith %}{{ body|safe }}</div>
<footer class="text-center small text-muted mb-4">Built for GMS School Dhamala — Incharge: Rekha Rani</footer>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script></body></html>"""

HOME_BODY = """
<div class="row g-4">
  <div class="col-md-4"><div class="card p-4">
    <h5>Teacher</h5><p class="small-muted">Incharge portal (username: <b>Rekha</b>)</p>
    <a class="btn btn-primary w-100" href="{{ url_for('teacher_login') }}">Teacher Login</a><hr>
    <form method="post" action="{{ url_for('send_otp') }}"><button class="btn btn-outline-warning w-100">Send OTP to Admin Email (Reset)</button></form>
  </div></div>

  <div class="col-md-4"><div class="card p-4">
    <h5>Student</h5><p class="small-muted">Signup or Login to view your personal record</p>
    <div class="d-grid gap-2"><a class="btn btn-success" href="{{ url_for('student_signup') }}">Student Signup</a><a class="btn btn-secondary" href="{{ url_for('student_login') }}">Student Login</a></div>
  </div></div>

  <div class="col-md-4"><div class="card p-4">
    <h5>AI Assistant</h5><p class="small-muted">Quick helper</p>
    <button class="btn btn-info" onclick="alert('Namaste Rekha ji! Aap records manage kar sakti hain — example: Show class 8, Add student, Generate whatsapp group')">M Rekha Rani — aap mujhse kya help chahiye?</button>
  </div></div>
</div>
"""

TEACHER_LOGIN = """
<div class="row justify-content-center"><div class="col-md-6"><div class="card p-4">
  <h4>Teacher Login</h4>
  <form method="post" action="{{ url_for('teacher_login') }}">
    <input name="username" class="form-control mb-2" placeholder="Username" value="Rekha">
    <div class="input-group mb-2"><input id="pw" name="password" class="form-control" placeholder="Password" type="password"><button type="button" class="btn btn-outline-secondary" onclick="togglePw()">Show</button></div>
    <div class="d-flex gap-2"><button class="btn btn-primary">Login</button><a class="btn btn-link" href="{{ url_for('home') }}">Back</a></div>
  </form>
  <hr>
  <h6>Reset Password (OTP)</h6>
  <form method="post" action="{{ url_for('send_otp') }}"><button class="btn btn-warning btn-sm">Send OTP to Admin Email</button></form>
  <form method="post" action="{{ url_for('reset_password') }}" class="mt-2">
    <input name="otp" class="form-control mb-2" placeholder="Enter OTP">
    <input name="new_password" class="form-control mb-2" placeholder="New password" type="password">
    <input name="new_password2" class="form-control mb-2" placeholder="Confirm password" type="password">
    <button class="btn btn-success btn-sm">Reset</button>
  </form>
</div></div></div>
<script>function togglePw(){var e=document.getElementById('pw'); e.type = e.type==='password'?'text':'password';}</script>
"""

TEACHER_DASH = """
<div class="row">
  <div class="col-md-4"><div class="card p-3">
    <h5>Add Student</h5>
    <form method="post" action="{{ url_for('add_student') }}">
      <input class="form-control mb-2" name="name" placeholder="Student Name" required>
      <select class="form-select mb-2" name="class"><option>6th</option><option>7th</option><option selected>8th</option><option>9th</option><option>10th</option></select>
      <input class="form-control mb-2" name="father_name" placeholder="Father Name">
      <input class="form-control mb-2" name="mother_name" placeholder="Mother Name">
      <input class="form-control mb-2" name="aadhaar" placeholder="Aadhaar (12 digits)">
      <input class="form-control mb-2" name="place" placeholder="Place">
      <label class="small-muted">DOB</label><input class="form-control mb-2" name="dob" type="date">
      <input class="form-control mb-2" name="phone" placeholder="Phone (10 digits)">
      <input class="form-control mb-2" name="whatsapp" placeholder="WhatsApp (10 digits) - leave blank => same as phone">
      <input class="form-control mb-2" name="email" placeholder="Email (optional)">
      <input class="form-control mb-2" name="password" placeholder="Initial password" value="student123">
      <button class="btn btn-success w-100">Add Student</button>
    </form>
    <hr>
    <h6>Attendance</h6>
    <form method="post" action="{{ url_for('attendance') }}">
      <select class="form-select mb-2" name="student_id">{% for s in students %}<option value="{{ s['id'] }}">{{ s['name'] }} — {{ s['class'] }}</option>{% endfor %}</select>
      <input class="form-control mb-2" name="year" type="number" value="{{ year }}">
      <input class="form-control mb-2" name="present" type="number" value="0" placeholder="Present">
      <input class="form-control mb-2" name="absent" type="number" value="0" placeholder="Absent">
      <button class="btn btn-primary w-100">Save Attendance</button>
    </form>
  </div></div>

  <div class="col-md-8"><div class="card p-3">
    <h5>Students (editable)</h5>
    <form method="post" action="{{ url_for('save_edits') }}">
      <table class="table table-sm"><thead><tr><th></th><th>Name</th><th>Class</th><th>Aadhaar</th><th>Phone</th><th>WhatsApp</th><th>Email</th><th>Actions</th></tr></thead>
      <tbody>{% for s in students %}
        <tr>
          <td><input type="checkbox" name="selected" value="{{ s['id'] }}"></td>
          <td><input class="form-control" name="name_{{ s['id'] }}" value="{{ s['name'] }}"></td>
          <td><select class="form-select" name="class_{{ s['id'] }}"><option {% if s['class']=='6th' %}selected{% endif %}>6th</option><option {% if s['class']=='7th' %}selected{% endif %}>7th</option><option {% if s['class']=='8th' %}selected{% endif %}>8th</option><option {% if s['class']=='9th' %}selected{% endif %}>9th</option><option {% if s['class']=='10th' %}selected{% endif %}>10th</option></select></td>
          <td><input class="form-control" name="aadhaar_{{ s['id'] }}" value="{{ s['aadhaar'] }}"></td>
          <td><input class="form-control" name="phone_{{ s['id'] }}" value="{{ s['phone'] }}"></td>
          <td><input class="form-control" name="whatsapp_{{ s['id'] }}" value="{{ s['whatsapp'] }}"></td>
          <td><input class="form-control" name="email_{{ s['id'] }}" value="{{ s['email'] }}"></td>
          <td>
            <form method="post" action="{{ url_for('delete_student') }}" style="display:inline">
              <input type="hidden" name="id" value="{{ s['id'] }}">
              <button class="btn btn-danger btn-sm" onclick="return confirm('Delete student {{ s['name'] }} ? This cannot be undone.')"><i class="fa fa-trash"></i></button>
            </form>
          </td>
        </tr>{% endfor %}</tbody></table>
      <div class="d-flex gap-2">
        <button class="btn btn-primary">Save Changes</button>
        <a class="btn btn-outline-success" href="{{ url_for('export_csv') }}">Export CSV (all)</a>
      </div>
    </form>
    <hr>
    <h6>WhatsApp group</h6>
    <form method="post" action="{{ url_for('wa_links') }}">
      <select class="form-select mb-2" name="wa_student" multiple>{% for s in students %}<option value="{{ s['id'] }}">{{ s['name'] }} — {{ s['phone'] or s['whatsapp'] }}</option>{% endfor %}</select>
      <button class="btn btn-info">Generate wa.me Links</button>
    </form>
    {% if wa_links %}<div class="mt-3"><h6>Links</h6><ul>{% for l in wa_links %}<li><a href="{{ l['url'] }}" target="_blank">{{ l['name'] }} — {{ l['num'] }}</a></li>{% endfor %}</ul>
      <form method="post" action="{{ url_for('download_selected_csv') }}">{% for id in selected_ids %}<input type="hidden" name="id" value="{{ id }}">{% endfor %}<button class="btn btn-outline-primary">Download Selected CSV</button></form></div>{% endif %}
  </div></div>
</div>
"""

STUDENT_SIGNUP = """
<div class="row justify-content-center"><div class="col-md-6"><div class="card p-4">
  <h4>Student Signup</h4>
  <form method="post" action="{{ url_for('student_signup') }}">
    <input class="form-control mb-2" name="name" placeholder="Full name" required>
    <select class="form-select mb-2" name="class"><option>6th</option><option>7th</option><option>8th</option><option>9th</option><option>10th</option></select>
    <input class="form-control mb-2" name="phone" placeholder="Phone (10 digits)" required>
    <input class="form-control mb-2" name="email" placeholder="Email (optional)">
    <input class="form-control mb-2" name="password" placeholder="Password" required>
    <input class="form-control mb-2" name="username" placeholder="Username (optional)">
    <button class="btn btn-success w-100">Signup</button>
  </form>
</div></div></div>
"""

STUDENT_LOGIN = """
<div class="row justify-content-center"><div class="col-md-6"><div class="card p-4">
  <h4>Student Login</h4>
  <form method="post" action="{{ url_for('student_login') }}">
    <input class="form-control mb-2" name="username" placeholder="Username" required>
    <div class="input-group mb-2"><input id="spw" class="form-control" name="password" placeholder="Password" type="password" required><button type="button" class="btn btn-outline-secondary" onclick="toggleSpw()">Show</button></div>
    <button class="btn btn-primary w-100">Login</button>
  </form>
</div></div></div>
<script>function toggleSpw(){var e=document.getElementById('spw'); e.type=e.type==='password'?'text':'password';}</script>
"""

STUDENT_DASH = """
<div class="row"><div class="col-md-8"><div class="card p-3">
  <h4>Your Profile</h4>
  <p><strong>Name:</strong> {{ user['name'] }}</p>
  <p><strong>Class:</strong> {{ user['class'] }}</p>
  <p><strong>Father:</strong> {{ user['father_name'] }} | <strong>Mother:</strong> {{ user['mother_name'] }}</p>
  <p><strong>Place:</strong> {{ user['place'] }}</p>
  <p><strong>DOB:</strong> {{ user['dob'] }}</p>
  <p><strong>Phone:</strong> {{ user['phone'] }} &nbsp; <a href="https://wa.me/91{{ user['whatsapp'] }}" target="_blank"><i class="fa-brands fa-whatsapp"></i></a></p>
  <hr>
  <h6>Attendance</h6>
  {% if attendance %}<table class="table table-sm"><thead><tr><th>Year</th><th>Present</th><th>Absent</th></tr></thead><tbody>{% for a in attendance %}<tr><td>{{ a['year'] }}</td><td>{{ a['present'] }}</td><td>{{ a['absent'] }}</td></tr>{% endfor %}</tbody></table>{% else %}<p class="small-muted">No attendance yet.</p>{% endif %}
  <a class="btn btn-outline-primary btn-sm" href="{{ url_for('download_my_record') }}">Download My Record (CSV)</a>
</div></div></div>
"""

# ---------- Routes ----------
@app.route("/")
def home():
    body = render_template_string(HOME_BODY)
    return render_template_string(BASE, body=body)

# Teacher login/reset
@app.route("/teacher/login", methods=["GET","POST"])
def teacher_login():
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","")
        user = get_user_by_username(u)
        if user and user["role"] == "teacher" and check_password_hash(user["password"], p):
            session["user"] = user["id"]; session["user_role"] = "teacher"; session["user_name"] = user["name"] or user["username"]
            return redirect(url_for("teacher_dashboard"))
        else:
            flash("❌ Incorrect Username or Password", "danger")
    body = render_template_string(TEACHER_LOGIN)
    return render_template_string(BASE, body=body)

@app.route("/send_otp", methods=["POST"])
def send_otp():
    otp = f"{random.randint(0,999999):06d}"
    session["teacher_otp"] = otp
    session["teacher_otp_time"] = datetime.utcnow().timestamp()
    ok, msg = send_otp_email(ADMIN_RESET_EMAIL, otp)
    if ok:
        flash("OTP sent to admin email. Check inbox.", "success")
    else:
        flash(f"Failed to send OTP: {msg} — configure SMTP_USER/SMTP_PASS env vars.", "danger")
    return redirect(url_for("teacher_login"))

@app.route("/reset_password", methods=["POST"])
def reset_password():
    otp = request.form.get("otp","").strip()
    new_pw = request.form.get("new_password","")
    new_pw2 = request.form.get("new_password2","")
    stored = session.get("teacher_otp")
    ttime = session.get("teacher_otp_time", 0)
    if not stored or otp != stored or (datetime.utcnow().timestamp() - ttime) > 600:
        flash("Invalid or expired OTP.", "danger"); return redirect(url_for("teacher_login"))
    if not new_pw or new_pw != new_pw2:
        flash("Passwords do not match.", "danger"); return redirect(url_for("teacher_login"))
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE users SET password=? WHERE role='teacher' AND username='Rekha'", (generate_password_hash(new_pw),))
    conn.commit(); conn.close()
    session.pop("teacher_otp", None)
    flash("Teacher password updated. Use new password to login.", "success")
    return redirect(url_for("teacher_login"))

@app.route("/teacher/dashboard")
def teacher_dashboard():
    if session.get("user_role") != "teacher": return redirect(url_for("teacher_login"))
    students = list_students()
    return render_template_string(BASE, body=render_template_string(TEACHER_DASH, students=students, year=datetime.now().year, wa_links=None, selected_ids=[]))

@app.route("/add_student", methods=["POST"])
def add_student():
    if session.get("user_role") != "teacher": return redirect(url_for("teacher_login"))
    f = request.form
    name = f.get("name","").strip(); sclass = f.get("class","").strip(); father = f.get("father_name","").strip(); mother = f.get("mother_name","").strip()
    aad = f.get("aadhaar","").strip(); place = f.get("place","").strip(); dob = f.get("dob",""); phone = f.get("phone","").strip()
    whatsapp = f.get("whatsapp","").strip() or phone; email = f.get("email","").strip(); password = f.get("password","student123")
    if aad and not valid_aadhaar(aad): flash("Aadhaar must be exactly 12 digits.", "danger"); return redirect(url_for("teacher_dashboard"))
    if phone and not valid_phone(phone): flash("Phone must be exactly 10 digits.", "danger"); return redirect(url_for("teacher_dashboard"))
    if whatsapp and not valid_phone(whatsapp): flash("WhatsApp must be exactly 10 digits.", "danger"); return redirect(url_for("teacher_dashboard"))
    username = random_username(name)
    while get_user_by_username(username): username = random_username(name)
    create_student({"username": username, "password": password, "email": email, "name": name, "class": sclass, "father_name": father, "mother_name": mother, "aadhaar": aad, "place": place, "dob": dob, "phone": phone, "whatsapp": whatsapp})
    flash(f"Student {name} added (username: {username})", "success"); return redirect(url_for("teacher_dashboard"))

@app.route("/attendance", methods=["POST"])
def attendance():
    if session.get("user_role") != "teacher": return redirect(url_for("teacher_login"))
    sid = int(request.form.get("student_id")); year = int(request.form.get("year")); present = int(request.form.get("present")); absent = int(request.form.get("absent"))
    add_or_update_attendance(sid, year, present, absent); flash("Attendance saved.", "success"); return redirect(url_for("teacher_dashboard"))

@app.route("/save_edits", methods=["POST"])
def save_edits():
    if session.get("user_role") != "teacher": return redirect(url_for("teacher_login"))
    students = list_students()
    for s in students:
        sid = s["id"]; name = request.form.get(f"name_{sid}", "").strip(); cls = request.form.get(f"class_{sid}", "").strip()
        aad = request.form.get(f"aadhaar_{sid}", "").strip(); phone = request.form.get(f"phone_{sid}", "").strip(); whatsapp = request.form.get(f"whatsapp_{sid}", "").strip()
        email = request.form.get(f"email_{sid}", "").strip()
        if aad and not valid_aadhaar(aad): flash(f"Aadhaar for {name} must be 12 digits.", "danger"); return redirect(url_for("teacher_dashboard"))
        if phone and not valid_phone(phone): flash(f"Phone for {name} must be 10 digits.", "danger"); return redirect(url_for("teacher_dashboard"))
        if whatsapp and not valid_phone(whatsapp): flash(f"WhatsApp for {name} must be 10 digits.", "danger"); return redirect(url_for("teacher_dashboard"))
        update_student(sid, {"name": name, "class": cls, "father_name": s["father_name"], "mother_name": s["mother_name"], "aadhaar": aad, "place": s["place"], "dob": s["dob"], "phone": phone, "whatsapp": whatsapp, "email": email})
    flash("All changes saved.", "success"); return redirect(url_for("teacher_dashboard"))

@app.route("/delete_student", methods=["POST"])
def delete_student_route():
    if session.get("user_role") != "teacher": return redirect(url_for("teacher_login"))
    sid = int(request.form.get("id")); s = get_user_by_id(sid)
    if s:
        delete_student(sid); flash(f"Student {s['name']} deleted.", "info")
    else:
        flash("Student not found.", "danger")
    return redirect(url_for("teacher_dashboard"))

@app.route("/wa_links", methods=["POST"])
def wa_links():
    if session.get("user_role") != "teacher": return redirect(url_for("teacher_login"))
    ids = request.form.getlist("wa_student"); links=[]; selected=[]
    conn = get_db(); cur = conn.cursor()
    for sid in ids:
        cur.execute("SELECT name, whatsapp, phone FROM users WHERE id=?", (sid,))
        r = cur.fetchone()
        if r:
            num = r["whatsapp"] or r["phone"]
            if num and re.fullmatch(r"\d{10}", num):
                links.append({"name": r["name"], "num": num, "url": f"https://wa.me/91{num}"}); selected.append(sid)
    conn.close()
    students = list_students()
    return render_template_string(BASE, body=render_template_string(TEACHER_DASH, students=students, year=datetime.now().year, wa_links=links, selected_ids=selected))

@app.route("/download_selected_csv", methods=["POST"])
def download_selected_csv():
    if session.get("user_role") != "teacher": return redirect(url_for("teacher_login"))
    ids = request.form.getlist("id"); si = io.StringIO(); cw = csv.writer(si)
    cw.writerow(["id","name","class","father_name","mother_name","aadhaar","place","dob","phone","whatsapp","email"])
    conn = get_db(); cur = conn.cursor()
    for sid in ids:
        cur.execute("SELECT * FROM users WHERE id=?", (sid,)); r = cur.fetchone()
        if r: cw.writerow([r["id"], r["name"], r["class"], r["father_name"], r["mother_name"], r["aadhaar"], r["place"], r["dob"], r["phone"], r["whatsapp"], r["email"]])
    conn.close(); mem = io.BytesIO(); mem.write(si.getvalue().encode()); mem.seek(0)
    return send_file(mem, download_name="selected_students.csv", as_attachment=True, mimetype="text/csv")

@app.route("/export_csv")
def export_csv():
    if session.get("user_role") != "teacher": return redirect(url_for("teacher_login"))
    students = list_students(); si = io.StringIO(); cw = csv.writer(si)
    cw.writerow(["id","name","class","father_name","mother_name","aadhaar","place","dob","phone","whatsapp","email"])
    for s in students: cw.writerow([s["id"], s["name"], s["class"], s["father_name"], s["mother_name"], s["aadhaar"], s["place"], s["dob"], s["phone"], s["whatsapp"], s["email"]])
    mem = io.BytesIO(); mem.write(si.getvalue().encode()); mem.seek(0)
    return send_file(mem, download_name="students_all.csv", as_attachment=True, mimetype="text/csv")

# Student signup/login/dashboard
@app.route("/student/signup", methods=["GET","POST"])
def student_signup():
    if request.method == "POST":
        name = request.form.get("name","").strip(); sclass = request.form.get("class","").strip(); phone = request.form.get("phone","").strip()
        email = request.form.get("email","").strip(); password = request.form.get("password","").strip(); username = request.form.get("username","").strip() or random_username(name)
        if not name or not valid_phone(phone): flash("Name and 10-digit phone required.", "danger"); return redirect(url_for("student_signup"))
        if get_user_by_username(username): flash("Username already exists, choose another.", "danger"); return redirect(url_for("student_signup"))
        create_student({"username": username, "password": password, "email": email, "name": name, "class": sclass, "phone": phone, "whatsapp": phone})
        flash(f"Signed up. Your username: {username}. Please login.", "success"); return redirect(url_for("student_login"))
    return render_template_string(BASE, body=render_template_string(STUDENT_SIGNUP))

@app.route("/student/login", methods=["GET","POST"])
def student_login():
    if request.method == "POST":
        username = request.form.get("username","").strip(); pw = request.form.get("password","")
        user = get_user_by_username(username)
        if user and user["role"] == "student" and check_password_hash(user["password"], pw):
            session["user"] = user["id"]; session["user_role"] = "student"; session["user_name"] = user["name"]; return redirect(url_for("student_dashboard"))
        else:
            flash("❌ Incorrect Username or Password", "danger")
    return render_template_string(BASE, body=render_template_string(STUDENT_LOGIN))

@app.route("/student/dashboard")
def student_dashboard():
    if session.get("user_role") != "student": return redirect(url_for("student_login"))
    uid = session.get("user"); u = get_user_by_id(uid); attendance = get_attendance(uid)
    return render_template_string(BASE, body=render_template_string(STUDENT_DASH, user=u, attendance=attendance))

@app.route("/download_my_record")
def download_my_record():
    if session.get("user_role") != "student": return redirect(url_for("student_login"))
    uid = session.get("user"); u = get_user_by_id(uid)
    si = io.StringIO(); cw = csv.writer(si)
    cw.writerow(["name","class","father_name","mother_name","aadhaar","place","dob","phone","whatsapp","email"])
    cw.writerow([u["name"], u["class"], u["father_name"], u["mother_name"], u["aadhaar"], u["place"], u["dob"], u["phone"], u["whatsapp"], u["email"]])
    mem = io.BytesIO(); mem.write(si.getvalue().encode()); mem.seek(0)
    return send_file(mem, download_name=f"{u['name']}_record.csv", as_attachment=True, mimetype="text/csv")

@app.route("/logout")
def logout():
    session.clear(); flash("Logged out.", "info"); return redirect(url_for("home"))

# ---------- Run ----------
if __name__ == "__main__":
    app.run(debug=True)
