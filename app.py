from flask import (
    Flask,
    render_template,
    request,
    redirect,
    jsonify,
    session
)

from flask_socketio import SocketIO, emit, join_room
from werkzeug.utils import secure_filename

import sqlite3
import os
import qrcode
import socket
import random
import json

from zoneinfo import ZoneInfo

# Tan waa muhiim si login-ka iyo expiry-ga ay u shaqeeyaan
from datetime import datetime, timedelta, timezone

# 🔥 FIREBASE
import firebase_admin
from firebase_admin import credentials, firestore

DB_PATH = os.environ.get("DB_PATH", "database.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id TEXT,
        table_no TEXT,
        food TEXT,
        price REAL,
        qty INTEGER DEFAULT 1,
        total REAL,
        time TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'pending'
    )
    """)

    c.execute("""
    CREATE INDEX IF NOT EXISTS idx_orders 
    ON orders(restaurant_id, table_no)
    """)

    conn.commit()
    conn.close()

init_db()

DB_PATH = os.environ.get("DB_PATH", "database.db")

# =========================
# 🔥 FIREBASE CONFIG (FIXED)
# =========================
if not firebase_admin._apps:
    firebase_key_str = os.environ.get("FIREBASE_KEY")

    if not firebase_key_str:
        raise Exception("FIREBASE_KEY not set!")

    firebase_key = json.loads(firebase_key_str)
    cred = credentials.Certificate(firebase_key)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# =========================
# 🔥 FIRESTORE FUNCTIONS
# =========================
def get_restaurants_firestore():
    restaurants = []

    try:
        docs = db.collection("restaurants").stream()

        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            item["active"] = item.get("active", False)
            restaurants.append(item)

    except Exception as e:
        print("Restaurant Load Error:", e)

    return restaurants


def get_schools_firestore():
    schools = []

    try:
        docs = db.collection("schools").stream()

        for d in docs:
            item = d.to_dict()

            item["id"] = d.id
            item["name"] = item.get("name", "N/A")
            item["phone"] = item.get("phone", "N/A")
            item["password"] = item.get("password", "N/A")
            item["school_code"] = item.get("school_code", d.id)

            item["active"] = item.get("active", True)
            item["status"] = item.get("status", "active")

            expiry = item.get("expiry_date")
            if expiry:
                try:
                    item["expiry_date"] = expiry
                    item["is_expired"] = datetime.now() > datetime.fromisoformat(expiry)
                except:
                    item["is_expired"] = False
            else:
                item["expiry_date"] = "N/A"
                item["is_expired"] = False

            schools.append(item)

        schools = sorted(
            schools,
            key=lambda x: x.get("expiry_date", ""),
            reverse=True
        )

    except Exception as e:
        print("School Load Error:", e)

    return schools


def get_supermarkets_firestore():
    supermarkets = []

    try:
        docs = db.collection("supermarkets").stream()

        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            item["active"] = item.get("active", False)
            supermarkets.append(item)

    except Exception as e:
        print("Supermarket Load Error:", e)

    return supermarkets


def get_orders_firestore():
    orders = []

    try:
        docs = db.collection("orders").stream()

        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            orders.append(item)

    except Exception as e:
        print("Orders Load Error:", e)

    return orders

# =========================
# 🔥 FIREBASE HELPERS
# =========================
def save_student_firestore(data):
    db.collection("students").add(data)


def get_students_firestore():
    docs = db.collection("students").stream()
    return [doc.to_dict() for doc in docs]


def save_restaurant_firestore(data):
    db.collection("restaurants").add(data)


def save_supermarket_firestore(data):
    db.collection("supermarkets").add(data)


def save_order_firestore(data):
    db.collection("orders").add(data)

# =========================
# 🔐 SYSTEM PASSWORDS FROM FIREBASE
# =========================
def get_system_passwords():
    try:
        doc_ref = db.collection("evote").document("system")
        doc = doc_ref.get()

        if doc.exists:
            return doc.to_dict()

        return {
            "admin_password": "6993",
            "register_password": "6993",
            "student_password": "9751",
            "screen_password": "7890",
            "candidate_password": "0482",
            "evote_admin_password": "1851"
        }

    except Exception as e:
        print("Firebase password error:", e)

        return {
            "admin_password": "6993",
            "register_password": "6993",
            "student_password": "9751",
            "screen_password": "7890",
            "candidate_password": "0482",
            "evote_admin_password": "1851"
        }


def check_school_active(school_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT expiry_date FROM schools WHERE id=?", (school_id,))
    result = c.fetchone()

    conn.close()

    if not result:
        return False

    try:
        expiry = datetime.fromisoformat(result[0])
    except:
        return False

    return datetime.now() <= expiry

# =========================
# 🇸🇴 SOMALIA TIME
# =========================
def somalia_time():
    return datetime.now(timezone(timedelta(hours=3)))

# =========================
# ⏰ AUTO ROUND PROGRESS
# =========================
def auto_round_progress():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        c.execute("""
            SELECT current_round
            FROM election_settings
            WHERE id=1
        """)
        row = c.fetchone()
        current_round = row[0] if row else 1

        c.execute("""
CREATE TABLE IF NOT EXISTS schools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_name TEXT,
    phone TEXT,
    school_code TEXT,
    password TEXT,
    subscription_fee REAL,
    start_date TEXT,
    expiry_date TEXT
)
""")

        c.execute("""
            SELECT end_time
            FROM election_timer
            WHERE id=1
        """)
        timer_row = c.fetchone()

        if timer_row and timer_row[0]:
            end_time = datetime.strptime(
                timer_row[0],
                "%Y-%m-%d %H:%M:%S"
            )

            now = somalia_time().replace(tzinfo=None)

            if now >= end_time + timedelta(minutes=20):
                next_round_no = current_round + 1

                if next_round_no <= 3:
                    c.execute("""
                        UPDATE election_settings
                        SET current_round=?
                        WHERE id=1
                    """, (next_round_no,))

                    new_end = now + timedelta(minutes=60)

                    c.execute("""
                        UPDATE election_timer
                        SET round_time_minutes=60,
                            end_time=?
                        WHERE id=1
                    """, (
                        new_end.strftime("%Y-%m-%d %H:%M:%S"),
                    ))

                    conn.commit()

                    print(f"Auto moved to Round {next_round_no} ✅")

    except Exception as e:
        print("Auto Round Error:", e)

    conn.close()

# =========================
# ⏰ AUTO CHECK EXPIRY
# =========================
def auto_check_expiry(rid):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    try:
        c.execute("SELECT expiry, active FROM restaurants WHERE id=?", (rid,))
        row = c.fetchone()

        if row and row[0]:
            expiry_date = row[0]

            expiry = datetime.strptime(expiry_date, "%Y-%m-%d")

            if datetime.now() >= expiry:
                c.execute("""
                    UPDATE restaurants
                    SET active=0
                    WHERE id=?
                """, (rid,))
                conn.commit()

    except Exception as e:
        print("Auto Expiry Error:", e)

    conn.close()


from flask import Flask
from flask_socketio import SocketIO
import os
import random

# =========================
# 🔢 EVOTE CODE GENERATOR
# =========================
def generate_vote_code():
    return str(random.randint(100000, 999999))


app = Flask(__name__, static_url_path='/static')
app.secret_key = "super-secret-key-123"

# ✅ SAX (HAL MAR OO KALIYA)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

UPLOAD_FOLDER = "static/uploads"
QR_FOLDER = "static/qr"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)


# =========================
# 🎤 WEBRTC SIGNALING EVENTS
# =========================
@socketio.on("voice_call")
def voice_call(data):
    emit("incoming_call", data, broadcast=True)


@socketio.on("offer")
def handle_offer(data):
    emit("offer", data, broadcast=True)


@socketio.on("answer")
def handle_answer(data):
    emit("answer", data, broadcast=True)


@socketio.on("ice_candidate")
def handle_ice(data):
    emit("ice_candidate", data, broadcast=True)


# =========================
# 🏠 SOCKET ROOM JOIN
# =========================
@socketio.on("join_customer_room")
def join_customer(data):
    room = f"{data['rid']}_{data['table']}"
    join_room(room)
    emit("joined_room", {"room": room})


@socketio.on("join_kitchen_room")
def join_kitchen(data):
    room = f"kitchen_{data['rid']}"
    join_room(room)
    emit("joined_kitchen", {"room": room})


# =========================
# 🌐 GET SERVER IP
# =========================
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()

    return ip


SERVER_IP = get_ip()


# =========================
# DATABASE
# =========================
def init_db():
    print("INIT DB RUNNING...")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # =========================
    # 🍽️ RESTAURANTS
    # =========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS restaurants(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        username TEXT,
        password TEXT,
        price INTEGER,
        expiry TEXT,
        active INTEGER,
        payment_number TEXT,
        kitchen_password TEXT
    )
    """)

    # =========================
    # ⚙️ SYSTEM SETTINGS
    # =========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings(
        id INTEGER PRIMARY KEY,
        admin_password TEXT,
        register_password TEXT
    )
    """)

    c.execute("SELECT id FROM settings WHERE id=1")
    existing_settings = c.fetchone()

    if not existing_settings:
        c.execute("""
            INSERT INTO settings
            (id, admin_password, register_password)
            VALUES (1, '8880', '8880')
        """)

    # =========================
    # 🔐 EVOTE PASSWORD SETTINGS
    # =========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS evote_passwords(
        id INTEGER PRIMARY KEY,
        student_password TEXT,
        candidate_password TEXT,
        evote_admin_password TEXT
    )
    """)

    c.execute("SELECT id FROM evote_passwords WHERE id=1")
    existing_passwords = c.fetchone()

    if not existing_passwords:
        c.execute("""
            INSERT INTO evote_passwords
            (id, student_password, candidate_password, evote_admin_password)
            VALUES (1, '12345', '12345', 'admin123')
        """)

    # =========================
    # 🎓 STUDENTS
    # =========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS students(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE,
        full_name TEXT,
        class_name TEXT,
        semester TEXT,
        vote_code TEXT UNIQUE,
        has_voted_round1 INTEGER DEFAULT 0,
        has_voted_round2 INTEGER DEFAULT 0,
        has_voted_round3 INTEGER DEFAULT 0
    )
    """)

    # =========================
    # 🧑‍💼 CANDIDATES
    # =========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS candidates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        department TEXT,
        round INTEGER DEFAULT 1,
        votes INTEGER DEFAULT 0,
        percentage REAL DEFAULT 0,
        image TEXT
    )
    """)

    # =========================
    # 🗳️ ROUND SETTINGS
    # =========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS election_settings(
        id INTEGER PRIMARY KEY,
        current_round INTEGER DEFAULT 1,
        round_end_time TEXT
    )
    """)

    c.execute("SELECT id FROM election_settings WHERE id=1")
    existing_round = c.fetchone()

    if not existing_round:
        c.execute("""
            INSERT INTO election_settings
            (id, current_round, round_end_time)
            VALUES (1, 1, '')
        """)

    # =========================
    # ⏰ ELECTION TIMER
    # =========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS election_timer(
        id INTEGER PRIMARY KEY,
        round_time_minutes INTEGER DEFAULT 60,
        end_time TEXT
    )
    """)

    c.execute("SELECT id FROM election_timer WHERE id=1")
    existing_timer = c.fetchone()

    if not existing_timer:
        c.execute("""
            INSERT INTO election_timer
            (id, round_time_minutes, end_time)
            VALUES (1, 60, '')
        """)

    # =========================
    # ⏰ EVOTE TIMER
    # =========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS evote_timer(
        id INTEGER PRIMARY KEY,
        minutes INTEGER,
        end_time TEXT
    )
    """)

    c.execute("SELECT id FROM evote_timer WHERE id=1")
    existing_evote_timer = c.fetchone()

    if not existing_evote_timer:
        c.execute("""
            INSERT INTO evote_timer
            (id, minutes, end_time)
            VALUES (1, 60, '')
        """)

    # =========================
    # 🛒 SUPERMARKETS
    # =========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS supermarkets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        username TEXT,
        password TEXT,
        price INTEGER,
        expiry TEXT,
        active INTEGER DEFAULT 1
    )
    """)

    # =========================
    # 🛒 SUPERMARKET PRODUCTS
    # =========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS supermarket_products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barcode TEXT UNIQUE,
        product_name TEXT,
        price REAL
    )
    """)

    # =========================
    # 🧾 SUPERMARKET ORDERS
    # =========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS supermarket_orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_no TEXT,
        total REAL,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()

    print("DATABASE READY ✅")


@app.route("/")
def home():
    return render_template("home.html")

# =========================
# 🗳 CANDIDATE LOGIN
# =========================
@app.route("/candidate_login", methods=["GET", "POST"])
def candidate_login():
    if request.method == "POST":
        password = request.form["password"]

        # 🔥 get password from Firebase
        passwords = get_system_passwords()
        real_pass = passwords.get("candidate_password")

        if password == real_pass:
            session["candidate_ok"] = True
            return redirect("/register_candidate")

        return "Wrong password ❌"

    return render_template(
        "password_login.html",
        title="Candidate Register"
    )

@app.route("/evote_admin_login", methods=["GET", "POST"])
def evote_admin_login():
    try:
        if request.method == "POST":
            password = request.form["password"]

            passwords = get_system_passwords()
            real_password = passwords.get("evote_admin_password")

            if password == real_password:
                session["evote_admin_ok"] = True
                return redirect("/evote_admin")

            return "Wrong password ❌"

        return render_template(
            "password_login.html",
            title="eVote Admin"
        )

    except Exception as e:
        return f"Login Error ❌ {str(e)}"

@app.route("/evote_admin")
def evote_admin():
    try:
        if not session.get("evote_admin_ok"):
            return redirect("/evote_admin_login")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS evote_timer (
                id INTEGER PRIMARY KEY,
                minutes INTEGER,
                end_time TEXT
            )
        """)

        c.execute("""
            SELECT minutes, end_time
            FROM evote_timer
            WHERE id=1
        """)
        timer = c.fetchone()

        conn.close()

        current_timer = timer[0] if timer else 0
        end_time = timer[1] if timer else "Not Set"

        return render_template(
            "evote_admin.html",
            current_timer=current_timer,
            end_time=end_time
        )

    except Exception as e:
        return f"eVote Admin Error ❌ {str(e)}"


@app.route("/upload_ad", methods=["POST"])
def upload_ad():
    try:
        if not session.get("evote_admin_ok"):
            return redirect("/evote_admin_login")

        ad_file = request.files.get("ad_video")

        if not ad_file or ad_file.filename == "":
            return redirect("/evote_admin")

        folder = os.path.join("static", "ads")
        os.makedirs(folder, exist_ok=True)

        filepath = os.path.join(folder, "ad1.mp4")
        ad_file.save(filepath)

        return redirect("/evote_admin")

    except Exception as e:
        return f"Upload Error ❌ {str(e)}"


@app.route("/set_timer", methods=["POST"])
def set_timer():
    try:
        if not session.get("evote_admin_ok"):
            return redirect("/evote_admin_login")

        minutes = int(request.form["minutes"])
        end_time = datetime.now() + timedelta(minutes=minutes)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS evote_timer (
                id INTEGER PRIMARY KEY,
                minutes INTEGER,
                end_time TEXT
            )
        """)

        c.execute("""
            INSERT OR REPLACE INTO evote_timer
            (id, minutes, end_time)
            VALUES (1, ?, ?)
        """, (
            minutes,
            end_time.strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        conn.close()

        return redirect("/evote_admin")

    except Exception as e:
        return f"Timer Error ❌ {str(e)}"


@app.route("/get_evote_timer")
def get_evote_timer():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS evote_timer (
                id INTEGER PRIMARY KEY,
                minutes INTEGER,
                end_time TEXT
            )
        """)

        c.execute("""
            SELECT minutes, end_time
            FROM evote_timer
            WHERE id=1
        """)
        timer = c.fetchone()

        conn.close()

        if timer:
            return {
                "minutes": timer[0],
                "end_time": timer[1]
            }

        return {
            "minutes": 0,
            "end_time": None
        }

    except Exception as e:
        return {
            "error": str(e)
        }

# =========================
# 🎓 STUDENT LOGIN (OPEN ACCESS)
# =========================
@app.route("/student_login")
def student_login():
    return redirect("/register_student")


@app.route("/screen_login", methods=["GET", "POST"])
def screen_login():
    if request.method == "POST":
        password = request.form["password"]

        passwords = get_system_passwords()
        real_pass = passwords.get("screen_password")

        if password == real_pass:
            session["screen_access"] = True
            return redirect("/student_screen")

        return "Wrong password ❌"

    return render_template(
        "password_login.html",
        title="Student Screen"
    )


# =========================
# 🎓 FUTURE LEADER ACADEMY REGISTRATION
# =========================
import re
from datetime import datetime

@app.route("/register_student", methods=["GET", "POST"])
def register_student():

    if request.method == "POST":
        try:
            student_id = request.form["student_id"].strip()
            full_name = request.form["full_name"].strip()
            phone_number = request.form["phone_number"].strip()
            department = request.form["department"].strip()
            student_class = request.form["student_class"].strip().upper()

            # ID = exactly 4 digits
            if not re.fullmatch(r"\d{4}", student_id):
                return "Student ID must be exactly 4 digits ❌"

            # Full name = exactly 3 names
            if not re.fullmatch(r"[A-Za-z ]+", full_name):
                return "Full name must contain letters only ❌"

            words = full_name.split()

            if len(words) != 3:
                return "Full name must be exactly 3 names ❌"

            # Phone = exactly 9 digits
            if not re.fullmatch(r"\d{9}", phone_number):
                return "Phone number must be exactly 9 digits ❌"

            # Class validation
            allowed_classes = ["F1", "F2", "F3", "F4"]

            if student_class not in allowed_classes:
                return "Invalid class selected ❌"

            # Existing ID check
            existing_student = db.collection("students") \
                .document(student_id).get()

            if existing_student.exists:
                return """
                <h2 style='text-align:center;color:red;'>
                    Student ID already exists ❌
                </h2>
                <div style='text-align:center; margin-top:20px;'>
                    <a href='/register_student'
                       style='padding:12px 20px;
                              background:#0a7cff;
                              color:white;
                              text-decoration:none;
                              border-radius:8px;'>
                       Try Another ID
                    </a>
                </div>
                """

            student_data = {
                "student_id": student_id,
                "full_name": full_name.title(),
                "phone_number": phone_number,
                "department": department,
                "student_class": student_class,
                "payment_status": "paid",
                "created_at": datetime.now()
            }

            db.collection("students") \
                .document(student_id) \
                .set(student_data)

            return render_template(
                "register_student.html",
                student=student_data
            )

        except Exception as e:
            return f"Firebase Error ❌ {e}"

    return render_template("register_student.html")


# =========================
# 📋 STUDENT SCREEN
# =========================
@app.route("/student_screen", methods=["GET"])
def student_screen():
    if not session.get("screen_access"):
        return redirect("/screen_login")

    try:
        search_id = request.args.get("student_id", "").strip()
        students = []
        searched_student = None

        # 🔥 SEARCH SINGLE STUDENT
        if search_id:
            doc = db.collection("students").document(search_id).get()

            if doc.exists:
                searched_student = doc.to_dict()
                students.append(searched_student)

        else:
            # 🔥 GET ALL STUDENTS
            docs = db.collection("students").stream()

            for doc in docs:
                students.append(doc.to_dict())

        return render_template(
            "student_screen.html",
            students=students,
            searched_student=searched_student
        )

    except Exception as e:
        return f"Student Screen Error ❌ {e}"
    
    # =========================
# 🗑 DELETE STUDENT
# =========================
@app.route("/delete_student/<student_id>")
def delete_student(student_id):
    try:
        db.collection("students").document(student_id).delete()
        return redirect("/student_screen")
    except Exception as e:
        return f"Delete Error ❌ {e}"

@app.route("/register_candidate", methods=["GET", "POST"])
def register_candidate():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        full_name = request.form["full_name"]
        department = request.form["department"]
        image = request.files["image"]

        filename = image.filename

        import os
        upload_path = os.path.join("static", "uploads")

        if not os.path.exists(upload_path):
            os.makedirs(upload_path)

        image.save(os.path.join(upload_path, filename))

        c.execute("""
            INSERT INTO candidates(full_name, department, image)
            VALUES (?, ?, ?)
        """, (full_name, department, filename))

        conn.commit()

    c.execute("SELECT * FROM candidates ORDER BY id DESC")
    candidates = c.fetchall()

    conn.close()

    return render_template(
        "register_candidate.html",
        candidates=candidates
    )

@app.route("/vote", methods=["GET", "POST"])
def vote():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        # current round
        c.execute("""
            SELECT current_round
            FROM election_settings
            WHERE id=1
        """)
        row = c.fetchone()
        current_round = row[0] if row else 1

        # submit vote
        if request.method == "POST":
            vote_code = request.form.get("student_id")
            candidate_id = request.form.get("candidate_id")

            if not vote_code or not candidate_id:
                conn.close()
                return "Missing vote code or candidate ❌"

            vote_column = f"has_voted_round{current_round}"

            # check student
            c.execute(f"""
                SELECT {vote_column}
                FROM students
                WHERE vote_code=?
            """, (vote_code,))
            student = c.fetchone()

            if not student:
                conn.close()
                return "Invalid vote code ❌"

            if student[0] == 1:
                conn.close()
                return "Already voted in this round ❌"

            # add vote
            c.execute("""
                UPDATE candidates
                SET votes = votes + 1
                WHERE id=?
            """, (candidate_id,))

            # mark student voted
            c.execute(f"""
                UPDATE students
                SET {vote_column}=1
                WHERE vote_code=?
            """, (vote_code,))

            conn.commit()

            return "Vote submitted successfully ✅"

        # get candidates
        c.execute("""
            SELECT id, full_name, department, image
            FROM candidates
            WHERE round=?
            ORDER BY votes DESC
        """, (current_round,))

        candidates = c.fetchall()
        conn.close()

        return render_template(
            "vote.html",
            candidates=candidates,
            current_round=current_round
        )

    except Exception as e:
        conn.close()
        return f"Vote Error ❌ {str(e)}"


@app.route("/admin_dashboard", methods=["GET", "POST"])
def admin_dashboard():

    # =========================
    # ⏰ AUTO ROUND CHECK
    # =========================
    auto_round_progress()

    # =========================
    # 🔐 EVOTE ADMIN PROTECTION
    # =========================
    if not session.get("evote_admin_ok"):
        return redirect("/evote_admin_login")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        # =========================
        # FIX: CREATE TIMER TABLE
        # =========================
        c.execute("""
            CREATE TABLE IF NOT EXISTS election_timer(
                id INTEGER PRIMARY KEY,
                round_time_minutes INTEGER DEFAULT 60,
                end_time TEXT
            )
        """)

        # =========================
        # DEFAULT TIMER ROW
        # =========================
        c.execute("SELECT * FROM election_timer WHERE id=1")
        if not c.fetchone():
            c.execute("""
                INSERT INTO election_timer
                (id, round_time_minutes, end_time)
                VALUES (1, 60, '')
            """)
            conn.commit()

        # =========================
        # DEFAULT ROUND SETTINGS
        # =========================
        c.execute("SELECT * FROM election_settings WHERE id=1")
        if not c.fetchone():
            c.execute("""
                INSERT INTO election_settings
                (id, current_round, round_end_time)
                VALUES (1, 1, '')
            """)
            conn.commit()

        # =========================
        # HANDLE FORM ACTIONS
        # =========================
        if request.method == "POST":
            action = request.form.get("action")

            # =========================
            # MOVE NEXT ROUND
            # =========================
            if action == "next_round":
                c.execute("""
                    UPDATE election_settings
                    SET current_round = current_round + 1
                    WHERE id=1
                """)

            # =========================
            # SET TIMER
            # =========================
            elif action == "set_timer":
                minutes = int(request.form.get("minutes", 60))

                end_time = somalia_time() + timedelta(minutes=minutes)

                c.execute("""
                    UPDATE election_timer
                    SET round_time_minutes=?,
                        end_time=?
                    WHERE id=1
                """, (
                    minutes,
                    end_time.strftime("%Y-%m-%d %H:%M:%S")
                ))

            conn.commit()

        # =========================
        # GET CURRENT ROUND
        # =========================
        c.execute("""
            SELECT current_round
            FROM election_settings
            WHERE id=1
        """)
        row = c.fetchone()
        current_round = row[0] if row else 1

        # =========================
        # GET RESULTS
        # =========================
        c.execute("""
            SELECT *
            FROM candidates
            WHERE round=?
            ORDER BY votes DESC
        """, (current_round,))
        results = c.fetchall()

        # =========================
        # GET TIMER
        # =========================
        c.execute("""
            SELECT round_time_minutes, end_time
            FROM election_timer
            WHERE id=1
        """)
        timer = c.fetchone()

        if not timer:
            timer = (60, "Not Set")

        conn.close()

        return render_template(
            "admin_dashboard.html",
            current_round=current_round,
            results=results,
            timer=timer
        )

    except Exception as e:
        conn.close()
        return f"Admin Dashboard Error ❌ {str(e)}"

@app.route("/submit_review/<rid>", methods=["POST"])
def submit_review(rid):
    try:
        rating = int(request.form.get("rating", 0))
        comment = request.form.get("comment", "").strip()

        if rating < 1 or rating > 5:
            return "Invalid rating ❌"

        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return "Restaurant not found ❌"

        restaurant_name = restaurant_doc.to_dict().get("name", "Unknown")

        review_data = {
            "restaurant_id": rid,
            "restaurant_name": restaurant_name,
            "rating": rating,
            "comment": comment,
            "created_at": datetime.now()
        }

        # 🔥 reviews collection auto create
        db.collection("reviews").add(review_data)

        return redirect(f"/table/{rid}/1")

    except Exception as e:
        return f"Review Error ❌ {str(e)}"

@app.route("/submit_order", methods=["POST"])
def submit_order():
    try:
        rid = request.form.get("rid")
        table = request.form.get("table")
        item_name = request.form.get("item_name")
        price = request.form.get("price")

        db.collection("orders").add({
            "restaurant_id": rid,
            "table_no": table,
            "item_name": item_name,
            "price": price,
            "status": "pending"
        })

        return redirect(f"/menu/{rid}/{table}")

    except Exception as e:
        return f"Order Error ❌ {str(e)}"

# =========================
# 🎥 UPLOAD ADS ROUTE
# =========================
@app.route('/upload_break_ad_evote', methods=['POST'])
def upload_break_ad_evote():
    if 'ad_video' not in request.files:
        return redirect('/evote_admin')

    file = request.files['ad_video']

    if file.filename == '':
        return redirect('/evote_admin')

    filename = secure_filename(file.filename)
    filepath = os.path.join('static/break_ads', filename)

    os.makedirs('static/break_ads', exist_ok=True)

    file.save(filepath)

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS break_ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT
        )
    """)

    c.execute("DELETE FROM break_ads")
    c.execute("INSERT INTO break_ads (filename) VALUES (?)", (filename,))

    conn.commit()
    conn.close()

    return redirect('/evote_admin')

@app.route("/next_round", methods=["POST"])
def next_round():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT current_round FROM election_settings WHERE id=1")
    row = c.fetchone()

    current_round = row[0] if row else 1
    next_round_no = current_round + 1

    if current_round == 1:
        limit_num = 6
    elif current_round == 2:
        limit_num = 3
    else:
        conn.close()
        return "Final round reached ✅"

    c.execute("""
        SELECT id
        FROM candidates
        WHERE round=?
        ORDER BY votes DESC
        LIMIT ?
    """, (current_round, limit_num))

    winners = c.fetchall()

    for w in winners:
        c.execute("""
            UPDATE candidates
            SET round=?, votes=0
            WHERE id=?
        """, (next_round_no, w[0]))

    c.execute("""
        INSERT OR REPLACE INTO election_settings
        (id, current_round)
        VALUES (1, ?)
    """, (next_round_no,))

    conn.commit()
    conn.close()

    return redirect("/admin_dashboard")


@app.route("/live_results")
def live_results():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        # =========================
        # CURRENT ROUND
        # =========================
        c.execute("""
            SELECT current_round
            FROM election_settings
            WHERE id=1
        """)
        row = c.fetchone()
        current_round = row[0] if row else 1

        # =========================
        # TIMER INFO
        # =========================
        c.execute("""
            SELECT round_time_minutes, end_time
            FROM election_timer
            WHERE id=1
        """)
        timer = c.fetchone()

        remaining_seconds = 0
        break_mode = False

        if timer and timer[1]:
            end_time_obj = datetime.strptime(
                timer[1],
                "%Y-%m-%d %H:%M:%S"
            )

            now = datetime.now()
            diff = (end_time_obj - now).total_seconds()

            # =========================
            # TIMER RUNNING
            # =========================
            if diff > 0:
                remaining_seconds = int(diff)

            else:
                # =========================
                # 1 MIN BREAK ADS
                # =========================
                break_end = end_time_obj + timedelta(minutes=1)
                break_diff = (break_end - now).total_seconds()

                if break_diff > 0:
                    break_mode = True
                    remaining_seconds = int(break_diff)

                else:
                    # =========================
                    # AUTO MOVE NEXT ROUND
                    # =========================
                    c.execute("""
                        UPDATE election_settings
                        SET current_round = current_round + 1
                        WHERE id=1
                    """)

                    # reset next round timer to 60 mins
                    next_end = now + timedelta(minutes=60)

                    c.execute("""
                        UPDATE election_timer
                        SET round_time_minutes=?,
                            end_time=?
                        WHERE id=1
                    """, (
                        60,
                        next_end.strftime("%Y-%m-%d %H:%M:%S")
                    ))

                    conn.commit()

                    current_round += 1
                    remaining_seconds = 3600
                    break_mode = False

        # =========================
        # GET CANDIDATES
        # =========================
        c.execute("""
            SELECT id, full_name, department, round,
                   votes, percentage, image
            FROM candidates
            WHERE round=?
            ORDER BY votes DESC
        """, (current_round,))

        candidates = c.fetchall()

        # =========================
        # CUSTOM PERCENTAGE
        # 1 VOTE = 0.5%
        # =========================
        updated_candidates = []

        for candidate in candidates:
            votes = candidate[4]
            percent = round(votes * 0.5, 1)

            updated_candidates.append((
                candidate[0],
                candidate[1],
                candidate[2],
                candidate[3],
                votes,
                percent,
                candidate[6]
            ))

        conn.close()

        return render_template(
            "live_results.html",
            candidates=updated_candidates,
            current_round=current_round,
            remaining_seconds=remaining_seconds,
            break_mode=break_mode
        )

    except Exception as e:
        conn.close()
        return f"Live Results Error ❌ {str(e)}"
   

@app.route("/index")
def index():
    return render_template("index.html")

# =========================
# 🔐 SYSTEM PASSWORDS
# =========================
ADMIN_PASSWORD = "8880"
REGISTER_PASSWORD = "8880"

# =========================
# 🔐 ADMIN ROUTE (FINAL CLEAN)
# =========================
@app.route("/admin", methods=["GET", "POST"])
def admin():

    # =========================
    # 🔒 LOGIN CHECK
    # =========================
    if session.get("admin_ok"):

        try:

            # =========================
            # 📦 LOAD DATA
            # =========================
            restaurants = get_restaurants_firestore()

            supermarkets = get_supermarkets_firestore()

            orders = get_orders_firestore()

            schools = get_schools_firestore()

            total = len(orders)

            # =========================
            # 🔥 FIX SCHOOL DATES
            # =========================
            from datetime import datetime

            for s in schools:

                expiry = s.get("expiry_date")

                try:

                    # haddii string yahay
                    if isinstance(expiry, str):

                        expiry = datetime.fromisoformat(expiry)

                    # haddii firestore datetime yahay
                    elif hasattr(expiry, "timestamp"):

                        expiry = expiry

                    else:

                        expiry = datetime.utcnow()

                except:

                    expiry = datetime.utcnow()

                s["expiry_date_fixed"] = expiry

            # =========================
            # ⭐ TOP REVIEWS
            # =========================
            top_reviews = []

            review_docs = db.collection("reviews").stream()

            review_count_map = {}

            for doc in review_docs:

                item = doc.to_dict()

                rid = item.get("restaurant_id")

                if rid:

                    review_count_map[rid] = review_count_map.get(rid, 0) + 1

            # =========================
            # 🔥 ADD REVIEW COUNTS
            # =========================
            for r in restaurants:

                rid = r.get("id")

                r["review_count"] = review_count_map.get(rid, 0)

            # =========================
            # 🔥 SORT TOP 3
            # =========================
            top_reviews = sorted(

                restaurants,

                key=lambda x: x.get("review_count", 0),

                reverse=True

            )[:3]

        except Exception as e:

            print("Admin Load Error:", e)

            restaurants = []

            supermarkets = []

            schools = []

            orders = []

            total = 0

            top_reviews = []

        # =========================
        # 📤 SEND TO TEMPLATE
        # =========================
        return render_template(

            "admin.html",

            restaurants=restaurants,

            supermarkets=supermarkets,

            schools=schools,

            orders=orders,

            total=total,

            top_reviews=top_reviews

        )

    # =========================
    # 🔑 LOGIN PROCESS
    # =========================
    if request.method == "POST":

        try:

            passwords = get_system_passwords()

            real_pass = passwords.get("admin_password")

            entered = request.form.get("password")

            if entered != real_pass:

                return render_template(

                    "admin_login.html",

                    error="Wrong password ❌"

                )

            session["admin_ok"] = True

            return redirect("/admin")

        except Exception as e:

            print("Login Error:", e)

            return render_template(

                "admin_login.html",

                error="System error ❌"

            )

    # =========================
    # 📄 LOGIN PAGE
    # =========================
    return render_template("admin_login.html")


# =========================
# 🔓 LOGOUT ADMIN
# =========================
@app.route("/logout_admin")
def logout_admin():

    session.pop("admin_ok", None)

    session.pop("register_ok", None)

    return redirect("/admin")


# =========================
# 🔓 LOGOUT REGISTER
# =========================
@app.route("/logout_register")
def logout_register():

    session.pop("register_ok", None)

    return redirect("/register")

# =========================
# 🔐 CHANGE SYSTEM PASSWORDS
# =========================
@app.route("/change_system_passwords", methods=["POST"])
def change_system_passwords():

    try:

        if not session.get("admin_ok"):

            return jsonify({
                "success": False,
                "message": "Unauthorized"
            })

        data = request.get_json()

        admin_pass = data.get("admin_password")

        register_pass = data.get("register_password")

        if not admin_pass or not register_pass:

            return jsonify({
                "success": False,
                "message": "Fill all fields"
            })

        db.collection("system_passwords") \
            .document("main") \
            .set({

                "admin_password": admin_pass,

                "register_password": register_pass

            })

        return jsonify({

            "success": True,

            "message": "Passwords updated successfully ✅"

        })

    except Exception as e:

        return jsonify({

            "success": False,

            "message": str(e)

        })
    
@app.route("/change_passwords", methods=["POST"])
def change_passwords():
    new_admin = request.form.get("admin_pass")
    new_register = request.form.get("register_pass")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        UPDATE settings
        SET admin_password=?,
            register_password=?
        WHERE id=1
    """, (new_admin, new_register))

    conn.commit()
    conn.close()

    return redirect("/admin")

@app.route("/activate/<string:rid>")
def activate_restaurant(rid):
    try:
        if not session.get("admin_ok"):
            return redirect("/admin")

        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return f"Restaurant not found ❌ ID: {rid}"

        restaurant_ref.update({
            "active": True,
            "status": "active",
            "activated_at": datetime.now()
        })

        return redirect("/admin")

    except Exception as e:
        return f"Activate restaurant error ❌ {e}"


# =========================
# ❌ DISABLE RESTAURANT
# =========================
@app.route("/disable/<string:rid>")
def disable_restaurant(rid):
    try:
        # 🔐 admin only
        if not session.get("admin_ok"):
            return redirect("/admin")

        # 🔍 check if restaurant exists
        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return f"Restaurant not found ❌ ID: {rid}"

        # ✅ disable only (history remains)
        restaurant_ref.update({
            "active": False,
            "status": "disabled",
            "disabled_at": datetime.now()
        })

        # ⚠️ IMPORTANT:
        # orders / menu / analytics lama taabanayo
        # si sales history waligeed u sii jirto

        return redirect("/admin")

    except Exception as e:
        return f"Disable restaurant error ❌ {e}"


# =========================
# 🗑 DELETE RESTAURANT
# =========================
@app.route("/delete_restaurant/<string:rid>")
def delete_restaurant(rid):
    try:
        if not session.get("admin_ok"):
            return redirect("/admin")

        db.collection("restaurants").document(rid).delete()

        return redirect("/admin")

    except Exception as e:
        return f"Delete restaurant error ❌ {e}"

# =========================
# 🏪 GET RESTAURANTS FIRESTORE
# =========================
def get_restaurants_firestore():
    restaurants = []

    try:
        docs = db.collection("restaurants").stream()

        for doc in docs:
            item = doc.to_dict()

            # muhiim: document id
            item["id"] = doc.id

            # haddii active maqan yahay
            item["active"] = item.get("active", False)

            # haddii fields qaar maqan yihiin
            item["name"] = item.get("name", "N/A")
            item["phone"] = item.get("phone", "N/A")
            item["username"] = item.get("username", "N/A")
            item["kitchen_password"] = item.get(
                "kitchen_password",
                "N/A"
            )
            item["password"] = item.get("password", "N/A")
            item["expiry"] = item.get("expiry", "N/A")

            restaurants.append(item)

    except Exception as e:
        print("Restaurant fetch error:", e)

    return restaurants

# =========================
# 🟢 ACTIVATE SCHOOL (FINAL WORKING)
# =========================
@app.route("/activate_school/<string:sid>")
def activate_school(sid):
    try:
        if not session.get("admin_ok"):
            return redirect("/admin")

        school_ref = db.collection("schools").document(sid)
        school_doc = school_ref.get()

        if not school_doc.exists:
            return f"School not found ❌ ID: {sid}"

        # 🔥 3 months renew
        new_expiry = datetime.now() + timedelta(days=90)

        school_ref.update({
            "active": True,
            "status": "active",
            "expiry_date": new_expiry.isoformat(),
            "activated_at": datetime.now().isoformat()
        })

        return redirect("/admin")

    except Exception as e:
        print("ACTIVATE SCHOOL ERROR:", e)
        return f"Activate school error ❌ {e}"


# =========================
# 🔴 DISABLE SCHOOL (FORCE RENEW)
# =========================
@app.route("/disable_school/<string:sid>")
def disable_school(sid):
    try:
        if not session.get("admin_ok"):
            return redirect("/admin")

        school_ref = db.collection("schools").document(sid)
        school_doc = school_ref.get()

        if not school_doc.exists:
            return f"School not found ❌ ID: {sid}"

        # 🔥 Disable + expire immediately
        school_ref.update({
            "active": False,
            "status": "disabled",
            "expiry_date": datetime.now().isoformat(),  # 🔥 muhiim
            "disabled_at": datetime.now().isoformat()
        })

        return redirect("/admin")

    except Exception as e:
        print("DISABLE SCHOOL ERROR:", e)
        return f"Disable school error ❌ {e}"


# =========================
# 🗑 DELETE SCHOOL (FINAL)
# =========================
@app.route("/delete_school/<string:sid>")
def delete_school(sid):
    try:
        if not session.get("admin_ok"):
            return redirect("/admin")

        db.collection("schools").document(sid).delete()

        return redirect("/admin")

    except Exception as e:
        print("DELETE SCHOOL ERROR:", e)
        return f"Delete school error ❌ {e}"

# =========================
# 🛒 GET SUPERMARKETS FIRESTORE
# =========================
def get_supermarkets_firestore():
    supermarkets = []

    try:
        docs = db.collection("supermarkets").stream()

        for doc in docs:
            item = doc.to_dict()

            # muhiim: document id
            item["id"] = doc.id

            item["active"] = item.get("active", False)

            item["name"] = item.get("name", "N/A")
            item["username"] = item.get("username", "N/A")
            item["expiry"] = item.get("expiry", "N/A")

            supermarkets.append(item)

    except Exception as e:
        print("Supermarket fetch error:", e)

    return supermarkets

# =========================
# 📦 GET ORDERS FIRESTORE
# =========================
def get_orders_firestore():
    orders = []

    try:
        docs = db.collection("orders").stream()

        for doc in docs:
            item = doc.to_dict()

            item["id"] = doc.id
            item["restaurant_name"] = item.get(
                "restaurant_name",
                "N/A"
            )
            item["food"] = item.get("food", "N/A")
            item["table"] = item.get("table", "N/A")
            item["time"] = item.get("time", "N/A")
            item["status"] = item.get("status", "Pending")

            orders.append(item)

    except Exception as e:
        print("Orders fetch error:", e)

    return orders

# =========================
# ✅ ACTIVATE SUPERMARKET
# =========================
@app.route("/activate_market/<string:mid>")
def activate_market(mid):
    try:
        if not session.get("admin_ok"):
            return redirect("/admin")

        db.collection("supermarkets").document(mid).update({
            "active": True
        })

        return redirect("/admin")

    except Exception as e:
        return f"Activate market error ❌ {e}"


# =========================
# ❌ DISABLE SUPERMARKET
# =========================
@app.route("/disable_market/<string:mid>")
def disable_market(mid):
    try:
        if not session.get("admin_ok"):
            return redirect("/admin")

        db.collection("supermarkets").document(mid).update({
            "active": False
        })

        return redirect("/admin")

    except Exception as e:
        return f"Disable market error ❌ {e}"


# =========================
# 🗑 DELETE SUPERMARKET
# =========================
@app.route("/delete_market/<string:mid>")
def delete_market(mid):
    try:
        if not session.get("admin_ok"):
            return redirect("/admin")

        db.collection("supermarkets").document(mid).delete()

        return redirect("/admin")

    except Exception as e:
        return f"Delete market error ❌ {e}"

# =========================
# 🗳️ CHANGE EVOTE PASSWORDS
# =========================
@app.route("/change_evote_passwords", methods=["POST"])
def change_evote_passwords():
    # =========================
    # 🔐 GET FORM VALUES
    # =========================
    student_pass = request.form.get("student_password")
    screen_pass = request.form.get("screen_password")
    candidate_pass = request.form.get("candidate_password")
    admin_pass = request.form.get("evote_admin_password")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # =========================
    # 🔧 ENSURE TABLE EXISTS
    # =========================
    c.execute("""
        CREATE TABLE IF NOT EXISTS evote_passwords(
            id INTEGER PRIMARY KEY,
            student_password TEXT,
            screen_password TEXT,
            candidate_password TEXT,
            evote_admin_password TEXT
        )
    """)

    # =========================
    # ➕ ADD MISSING COLUMN SAFELY
    # =========================
    try:
        c.execute("ALTER TABLE evote_passwords ADD COLUMN screen_password TEXT")
    except:
        pass

    # =========================
    # 🔍 CHECK EXISTING ROW
    # =========================
    c.execute("SELECT id FROM evote_passwords WHERE id=1")
    row = c.fetchone()

    # =========================
    # 🔄 UPDATE OR INSERT
    # =========================
    if row:
        c.execute("""
            UPDATE evote_passwords
            SET student_password=?,
                screen_password=?,
                candidate_password=?,
                evote_admin_password=?
            WHERE id=1
        """, (
            student_pass,
            screen_pass,
            candidate_pass,
            admin_pass
        ))
    else:
        c.execute("""
            INSERT INTO evote_passwords
            (id, student_password, screen_password, candidate_password, evote_admin_password)
            VALUES (1, ?, ?, ?, ?)
        """, (
            student_pass,
            screen_pass,
            candidate_pass,
            admin_pass
        ))

    conn.commit()
    conn.close()

    return redirect("/admin")

@app.route("/delete_menu/<mid>/<rid>")
def delete_menu(mid, rid):
    try:
        restaurant_ref = db.collection("restaurants").document(rid)

        # menu item document
        menu_ref = restaurant_ref.collection("menu").document(mid)
        menu_doc = menu_ref.get()

        if not menu_doc.exists:
            return "Menu item not found ❌"

        menu_data = menu_doc.to_dict()

        # haddii image jiro
        image_name = menu_data.get("image")

        if image_name:
            image_path = os.path.join("static", "uploads", image_name)

            if os.path.exists(image_path):
                os.remove(image_path)

        # firestore delete
        menu_ref.delete()

        return redirect(f"/restaurant_admin/{rid}")

    except Exception as e:
        return f"Delete menu error ❌ {str(e)}"

# ==========================================
# 🔄 RENEW SCHOOL (3 MONTHS - FINAL FIRESTORE)
# ==========================================
from datetime import datetime, timedelta

@app.route("/renew_school", methods=["POST"])
def renew_school():
    try:
        school_id = session.get("school")

        if not school_id:
            return jsonify({"error": "Not logged in"}), 401

        school_ref = db.collection("schools").document(school_id)
        school_doc = school_ref.get()

        if not school_doc.exists:
            return jsonify({"error": "School not found"}), 404

        new_expiry = datetime.now() + timedelta(days=90)

        school_ref.update({
            "active": True,
            "status": "active",
            "expiry_date": new_expiry.isoformat(),
            "renewed_at": datetime.now().isoformat()
        })

        return jsonify({
            "success": True,
            "message": "✅ System renewed for 3 months",
            "expiry": new_expiry.isoformat()
        })

    except Exception as e:
        print("RENEW ERROR:", e)
        return jsonify({"error": str(e)})


# ==========================================
# ⛔ CHECK SCHOOL EXPIRY (AUTO REDIRECT - FIRESTORE)
# ==========================================
@app.before_request
def check_school_expiry():
    path = request.path

    # Skip allowed routes
    if path.startswith("/static") or path in [
        "/renew_page",
        "/renew_school",
        "/school_login"
    ]:
        return

    school_id = session.get("school")

    if not school_id:
        return

    try:
        school_doc = db.collection("schools").document(school_id).get()

        if not school_doc.exists:
            return

        data = school_doc.to_dict()

        # 🔴 haddii disabled
        if not data.get("active"):
            return redirect("/renew_page")

        # 🔴 haddii expired
        expiry = data.get("expiry_date")
        if expiry:
            try:
                expiry_date = datetime.fromisoformat(expiry)
                if datetime.now() > expiry_date:
                    return redirect("/renew_page")
            except:
                return redirect("/renew_page")

    except Exception as e:
        print("CHECK EXPIRY ERROR:", e)


# ==========================================
# 📄 RENEW PAGE
# ==========================================
@app.route("/renew_page")
def renew_page():
    return render_template("renew.html")


# ==========================================
# 🔄 ADMIN RENEW SCHOOL (FIRESTORE)
# ==========================================
@app.route("/renew_school_admin/<string:sid>")
def renew_school_admin(sid):
    try:
        if not session.get("admin_ok"):
            return redirect("/admin")

        school_ref = db.collection("schools").document(sid)
        school_doc = school_ref.get()

        if not school_doc.exists:
            return f"School not found ❌ ID: {sid}"

        new_expiry = datetime.now() + timedelta(days=90)

        school_ref.update({
            "active": True,
            "status": "active",
            "expiry_date": new_expiry.isoformat(),
            "renewed_at": datetime.now().isoformat()
        })

        return redirect("/admin")

    except Exception as e:
        print("ADMIN RENEW ERROR:", e)
        return f"Renew error ❌ {e}"

@app.route("/register", methods=["GET", "POST"])
def register():
    try:
        # 🔐 access page password
        if not session.get("register_ok"):

            if request.method == "POST":
                passwords = get_system_passwords()
                real_pass = passwords.get("register_password", "6993")

                if request.form.get("access_password") == real_pass:
                    session["register_ok"] = True
                    return redirect("/register")

                return render_template(
                    "access_register.html",
                    error="Wrong password ❌"
                )

            return render_template("access_register.html")

        # 🔥 REAL REGISTER PAGE
        if request.method == "POST":
            months = int(request.form["months"])

            expiry_date = (
                datetime.now() + timedelta(days=months * 30)
            ).strftime("%Y-%m-%d")

            data = {
                "name": request.form["name"].strip(),
                "phone": request.form.get("phone", "").strip(),
                "username": request.form["username"].strip(),

                # restaurant login
                "password": request.form["password"].strip(),

                # kitchen login
                "kitchen_password": request.form["kitchen_password"].strip(),

                # 🔥 IMPORTANT
                "restaurant_admin_password":
                    request.form["restaurant_admin_password"].strip(),

                # admin info
                "admin_name": request.form.get("admin_name", "").strip(),
                "admin_email": request.form.get("admin_email", "").strip(),

                "price": request.form["price"].strip(),
                "payment": request.form["payment"].strip(),

                "expiry": expiry_date,
                "active": True,

                "review_count": 0,
                "average_rating": 0,

                "created_at": datetime.now()
            }

            # 🔥 SAVE TO FIREBASE
            doc_ref = db.collection("restaurants").add(data)
            rid = doc_ref[1].id

            restaurant_ref = db.collection("restaurants").document(rid)

            # create menu collection
            restaurant_ref.collection("menu").document("init").set({
                "created_at": datetime.now()
            })

            # create orders collection
            restaurant_ref.collection("orders").document("init").set({
                "created_at": datetime.now()
            })

            return redirect("/admin")

        return render_template("register.html")

    except Exception as e:
        print("Register Error:", e)
        return f"Register Error ❌ {str(e)}"


@app.route("/login", methods=["GET", "POST"])
def login():
    try:
        if request.method == "POST":
            username = request.form["username"].strip()
            password = request.form["password"].strip()

            docs = db.collection("restaurants").stream()

            for doc in docs:
                data = doc.to_dict()

                if (
                    data.get("username") == username and
                    data.get("password") == password
                ):
                    if not data.get("active", True):
                        return "Account disabled ❌"

                    session["restaurant_login"] = True
                    session["restaurant_id"] = doc.id
                    session["restaurant_name"] = data.get("name")

                    return redirect(f"/dashboard/{doc.id}")

            return render_template(
                "login.html",
                error="Wrong username or password ❌"
            )

        return render_template("login.html")

    except Exception as e:
        print("Login Error:", e)
        return f"Login Error ❌ {str(e)}"

@app.route("/supermarket_register", methods=["GET", "POST"])
def supermarket_register():
    try:
        if request.method == "POST":
            data = {
                "name": request.form["name"],
                "username": request.form["username"],
                "password": request.form["password"],
                "created_at": datetime.now(),
                "active": True
            }

            db.collection("supermarkets").add(data)

            return redirect("/supermarket_login")

        return render_template("supermarket_register.html")

    except Exception as e:
        return f"Supermarket Register Error ❌ {str(e)}"

@app.route("/supermarket_login", methods=["GET", "POST"])
def supermarket_login():
    try:
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]

            docs = db.collection("supermarkets").stream()

            for doc in docs:
                data = doc.to_dict()

                if (
                    data.get("username") == username and
                    data.get("password") == password
                ):
                    session["market_id"] = doc.id
                    return redirect("/supermarket_dashboard")

            return "Wrong login ❌"

        return render_template("supermarket_login.html")

    except Exception as e:
        return f"Login Error ❌ {str(e)}"


@app.route("/register_supermarket", methods=["GET", "POST"])
def register_supermarket():
    try:
        if request.method == "POST":
            months = int(request.form["months"])

            expiry = (
                datetime.now() + timedelta(days=months * 30)
            ).strftime("%Y-%m-%d")

            data = {
                "name": request.form["name"],
                "username": request.form["username"],
                "password": request.form["password"],
                "price": request.form["price"],
                "expiry": expiry,
                "active": True,
                "created_at": datetime.now()
            }

            db.collection("supermarkets").add(data)

            return redirect("/supermarket_login")

        return render_template("supermarket_register.html")

    except Exception as e:
        return f"Register Error ❌ {str(e)}"

# =========================
# 🛒 PLACE ORDER
# =========================
@app.route("/place_order", methods=["POST"])
def place_order():
    try:
        data = request.json

        rid = data["rid"]
        table = data["table"]
        food = data["food"]
        price = float(data["price"])
        qty = int(data.get("qty", 1))

        total = price * qty

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("""
        INSERT INTO orders (restaurant_id, table_no, food, price, qty, total, time)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (rid, table, food, price, qty, total))

        conn.commit()
        conn.close()

        return jsonify({"status": "success"})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/add_product", methods=["POST"])
def add_product():
    barcode = request.form["barcode"]
    product_name = request.form["product_name"]
    price = request.form["price"]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        INSERT INTO supermarket_products
        (barcode, product_name, price)
        VALUES (?, ?, ?)
    """, (
        barcode,
        product_name,
        price
    ))

    conn.commit()
    conn.close()

    return redirect("/supermarket_dashboard")

# =====================================
# 📊 RESTAURANT DASHBOARD (CLEAN VERSION)
# =====================================
@app.route("/dashboard/<rid>")
def dashboard(rid):
    try:
        # 🔐 login protection
        if not session.get("restaurant_login"):
            return redirect("/login")

        # 🔥 get restaurant
        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return "Restaurant not found ❌"

        restaurant = restaurant_doc.to_dict()

        # 🔥 active check
        if not restaurant.get("active", True):
            return render_template("renew.html", rid=rid)

        # 🔥 expiry check
        expiry = restaurant.get("expiry", "")
        if expiry:
            try:
                expiry_date = datetime.strptime(expiry, "%Y-%m-%d")
                if datetime.now() >= expiry_date:
                    restaurant_ref.update({"active": False})
                    return render_template("renew.html", rid=rid)
            except Exception as expiry_error:
                print("Expiry Error:", expiry_error)

        # =====================================
        # 🍽 MENU
        # =====================================
        menu = []
        menu_docs = restaurant_ref.collection("menu").stream()

        for doc in menu_docs:
            item = doc.to_dict()
            item["id"] = doc.id
            item["name"] = item.get("name", "No Name")
            item["price"] = item.get("price", 0)
            item["image"] = item.get("image", "")
            menu.append(item)

        # =====================================
        # 📢 ADS
        # =====================================
        ads = []
        ad_docs = restaurant_ref.collection("ads").stream()

        for doc in ad_docs:
            ad = doc.to_dict()
            ad["id"] = doc.id
            ad["title"] = ad.get("title", "")
            ad["image"] = ad.get("image", "")
            ad["audio"] = ad.get("audio", "")
            ad["created_at"] = ad.get("created_at", None)

            print("DASHBOARD AD:", ad)   # debug
            ads.append(ad)

        # 🔥 newest first
        ads = list(reversed(ads))

        return render_template(
            "dashboard.html",
            rid=rid,
            restaurant=restaurant.get("name", "Restaurant"),
            menu=menu,
            ads=ads
        )

    except Exception as e:
        print("Dashboard Error:", e)
        return f"Dashboard Error ❌ {str(e)}"

# =====================================
# 📱 CUSTOMER MOBILE MENU ROUTE (LAST COMPLETE VERSION)
# =====================================
@app.route("/menu/<rid>/<table_no>")
def mobile_menu(rid, table_no):
    try:
        # 🔥 get restaurant document
        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return "Restaurant not found ❌"

        restaurant = restaurant_doc.to_dict()

        # =====================================
        # 💳 PAYMENT
        # =====================================
        payment = restaurant.get("payment", "")
        payment_name = restaurant.get("payment_name", "")
        payment_number = restaurant.get("payment_number", payment)

        # =====================================
        # 🍽 MENU ITEMS
        # =====================================
        menu = []
        menu_docs = restaurant_ref.collection("menu").stream()

        for doc in menu_docs:
            item = doc.to_dict()

            # skip empty init docs
            if doc.id == "init":
                continue

            item["id"] = doc.id
            item["image"] = item.get("image", "")
            item["name"] = item.get("name", "No Name")
            item["price"] = item.get("price", 0)

            menu.append(item)

        # =====================================
        # 📢 ADS
        # =====================================
        ads = []
        ads_docs = restaurant_ref.collection("ads").stream()

        for doc in ads_docs:
            ad = doc.to_dict()

            # skip init docs
            if doc.id == "init":
                continue

            ad["id"] = doc.id
            ad["image"] = ad.get("image", "")
            ad["audio"] = ad.get("audio", "")
            ad["title"] = ad.get("title", "")

            print("CUSTOMER AD:", ad)   # debug log

            ads.append(ad)

        # newest ads first
        ads = list(reversed(ads))

        print("TOTAL ADS:", len(ads))
        print("TOTAL MENU:", len(menu))

        # =====================================
        # 📄 RENDER TEMPLATE
        # =====================================
        return render_template(
            "customer_menu.html",
            menu=menu,
            table=table_no,
            rid=rid,
            ads=ads,
            restaurant=restaurant.get("name", "Restaurant"),
            payment=payment,
            payment_name=payment_name,
            payment_number=payment_number,
            order_status=None
        )

    except Exception as e:
        print("Menu Error:", e)
        return f"Menu Error ❌ {str(e)}"


@app.route("/customer_order/<rid>", methods=["POST"])
def customer_order(rid):
    try:
        # 🔥 Get form data
        items = request.form.get("items", "")
        price = request.form.get("price", "0")
        table = request.form.get("table", "")

        drink_option = request.form.get("drink_option", "")
        food_option = request.form.get("food_option", "")
        tea_option = request.form.get("tea_option", "")

        # 🔥 Validation
        if not items:
            return "No items selected ❌"

        if not table:
            return "Table number missing ❌"

        # 🔥 Save order to Firestore
        db.collection("restaurants").document(rid)\
            .collection("orders").add({
                "items": items,
                "price": float(price),
                "table": str(table),
                "drink_option": drink_option,
                "food_option": food_option,
                "tea_option": tea_option,
                "status": "pending",
                "created_at": datetime.utcnow()
            })

        # 🔥 Return to menu page
        return redirect(f"/menu/{rid}/{table}")

    except Exception as e:
        print("Order Error:", e)
        return f"Order failed ❌ {str(e)}"

@app.route("/sales_data/<rid>")
def sales_data(rid):
    try:
        from_date = request.args.get("from")
        to_date = request.args.get("to")

        order_docs = db.collection("orders") \
            .where("restaurant_id", "==", rid) \
            .stream()

        data = []
        total_sales = 0

        for doc in order_docs:
            item = doc.to_dict()

            created_at = str(item.get("created_at", ""))

            if from_date and to_date:
                if created_at[:10] < from_date or created_at[:10] > to_date:
                    continue

            total_sales += float(item.get("total", 0))

            data.append({
                "table": item.get("table_no"),
                "food": item.get("food"),
                "total": item.get("total"),
                "date": created_at
            })

        return jsonify({
            "orders": data,
            "total_orders": len(data),
            "total_sales": total_sales
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        })
# =====================================
# 🍽 RESTAURANT ADMIN PANEL
# =====================================
from datetime import datetime, timedelta
from google.cloud import firestore

@app.route("/restaurant_admin/<rid>", methods=["GET", "POST"])
def restaurant_admin(rid):
    try:
        if not session.get("admin_" + str(rid)):
            return redirect(f"/restaurant_admin_login/{rid}")

        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return "Restaurant not found ❌"

        restaurant = restaurant_doc.to_dict()
        restaurant["id"] = rid

        # 🔥 UPDATE SETTINGS TO FIREBASE
        if request.method == "POST":
            update_data = {
                "name": request.form.get("name", "").strip(),
                "username": request.form.get("username", "").strip(),
                "password": request.form.get("password", "").strip(),
                "kitchen_password": request.form.get("kitchen_password", "").strip(),
                "restaurant_admin_password": request.form.get("restaurant_admin_password", "").strip(),
                "updated_at": datetime.now(timezone.utc)
            }

            restaurant_ref.update(update_data)

            return redirect(f"/restaurant_admin/{rid}")

        # MENU
        menu = []
        menu_docs = restaurant_ref.collection("menu").stream()

        for doc in menu_docs:
            item = doc.to_dict()
            item["id"] = doc.id
            menu.append(item)

        # ORDERS
        orders = []
        total = 0

        order_docs = restaurant_ref.collection("orders").stream()

        for doc in order_docs:
            order = doc.to_dict()
            order["id"] = doc.id

            try:
                total += float(order.get("price", 0))
            except:
                pass

            orders.append(order)

        return render_template(
            "restaurant_admin.html",
            r=restaurant,
            menu=menu,
            orders=orders,
            total=round(total, 2),
            profit=round(total, 2),
            loss=0,
            compare_text="System working",
            rid=rid
        )

    except Exception as e:
        return f"Error ❌ {str(e)}"

# =====================================
# 🧹 CLEAR KITCHEN VIEW ONLY
# =====================================
@app.route("/clear_kitchen_orders/<rid>")
def clear_kitchen_orders(rid):
    try:
        if not session.get("admin_" + str(rid)):
            return redirect(f"/restaurant_admin_login/{rid}")

        orders_ref = db.collection("restaurants") \
            .document(rid) \
            .collection("orders")

        docs = orders_ref.stream()

        for doc in docs:
            data = doc.to_dict()

            # 🔥 keep history + sales
            # only hide from kitchen screen
            doc.reference.update({
                "kitchen_cleared": True,
                "cleared_at": datetime.now(timezone.utc)
            })

        return redirect(f"/restaurant_admin/{rid}")

    except Exception as e:
        return f"Kitchen clear error ❌ {str(e)}"


# =====================================
# 🗑 CLEAR ALL ADS
# =====================================
@app.route("/clear_ads/<rid>")
def clear_ads(rid):
    try:
        if not session.get("admin_" + str(rid)):
            return redirect(f"/restaurant_admin_login/{rid}")

        ads_ref = db.collection("restaurants") \
            .document(rid) \
            .collection("ads")

        docs = ads_ref.stream()

        for doc in docs:
            doc.reference.delete()

        return redirect(f"/restaurant_admin/{rid}")

    except Exception as e:
        return f"Ads clear error ❌ {str(e)}"

# =====================================
# 🔐 RESTAURANT ADMIN LOGIN
# =====================================
@app.route("/restaurant_admin_login/<rid>", methods=["GET", "POST"])
def restaurant_admin_login(rid):
    try:
        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return "Restaurant not found ❌"

        restaurant = restaurant_doc.to_dict()

        if request.method == "POST":
            entered_password = request.form.get(
                "password",
                ""
            ).strip()

            # 🔥 SUPPORT OLD + NEW FIREBASE FIELD
            real_password = str(
                restaurant.get("restaurant_admin_password")
                or restaurant.get("resturen_admin password")
                or ""
            ).strip()

            print("ENTERED PASSWORD:", entered_password)
            print("REAL PASSWORD:", real_password)

            if entered_password == real_password:
                session["admin_" + str(rid)] = True
                return redirect(f"/restaurant_admin/{rid}")

            return f'''
            <div style="max-width:400px;margin:50px auto;font-family:Arial;">
                <h3 style="color:red;">Wrong password ❌</h3>
                <a href="/restaurant_admin_login/{rid}">Try again</a>
            </div>
            '''

        return f'''
        <form method="post"
              style="max-width:400px;
                     margin:50px auto;
                     font-family:Arial;
                     background:white;
                     padding:25px;
                     border-radius:12px;
                     box-shadow:0 0 10px rgba(0,0,0,0.1);">

            <h2 style="text-align:center;">Admin Login 🔐</h2>

            <input type="password"
                   name="password"
                   placeholder="Enter admin password"
                   required
                   style="width:100%;
                          padding:12px;
                          margin:15px 0;
                          border:1px solid #ddd;
                          border-radius:8px;
                          box-sizing:border-box;">

            <button type="submit"
                    style="width:100%;
                           padding:12px;
                           background:#0a7cff;
                           color:white;
                           border:none;
                           border-radius:8px;
                           font-weight:bold;
                           cursor:pointer;">
                Login
            </button>
        </form>
        '''

    except Exception as e:
        print("Login Error:", e)
        return f"Login error ❌ {str(e)}"

# 🔥 ADD STAFF
@app.route("/add_staff/<rid>", methods=["POST"])
def add_staff(rid):
    try:
        staff_data = {
            "restaurant_id": rid,
            "name": request.form["name"],
            "email": request.form["email"],
            "password": request.form["password"],
            "role": "staff",
            "created_at": datetime.now()
        }

        db.collection("restaurants") \
            .document(rid) \
            .collection("staff") \
            .add(staff_data)

        return redirect("/dashboard/" + rid)

    except Exception as e:
        return f"Add staff error ❌ {str(e)}"


# 🔥 STAFF LIST
@app.route("/staff_list/<rid>")
def staff_list(rid):
    try:
        docs = db.collection("restaurants") \
            .document(rid) \
            .collection("staff") \
            .stream()

        staff = []
        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            staff.append(item)

        return render_template("staff_list.html", staff=staff)

    except Exception as e:
        return f"Staff list error ❌ {str(e)}"


# 🔥 SEND NEWS
@app.route("/send_news/<rid>", methods=["POST"])
def send_news(rid):
    try:
        news_data = {
            "title": request.form["title"],
            "message": request.form["message"],
            "created_at": datetime.now()
        }

        db.collection("restaurants") \
            .document(rid) \
            .collection("staff_news") \
            .add(news_data)

        return redirect("/dashboard/" + rid)

    except Exception as e:
        return f"Send news error ❌ {str(e)}"


# 🔥 STAFF NEWS
@app.route("/staff_news/<rid>")
def staff_news(rid):
    try:
        docs = db.collection("restaurants") \
            .document(rid) \
            .collection("staff_news") \
            .stream()

        news = []
        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            news.append(item)

        return render_template("staff_news.html", news=news)

    except Exception as e:
        return f"Staff news error ❌ {str(e)}"


@app.route("/stats/<rid>")
def stats(rid):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM orders WHERE restaurant_id=?", (rid,))
    orders = c.fetchone()[0]

    c.execute("SELECT AVG(CAST(price AS FLOAT)) FROM menu WHERE restaurant_id=?", (rid,))
    avg_price = c.fetchone() or 0

    revenue = orders * avg_price
    profit = round(revenue * 0.7, 2)

    conn.close()
    return jsonify({
        "orders": orders,
        "revenue": round(revenue, 2),
        "profit": profit
    })


@app.route("/get_calls/<rid>")
def get_calls(rid):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM waiter_calls WHERE restaurant_id=?", (rid,))
    count = c.fetchone()
    conn.close()
    return jsonify({"count": count})

# ✅ ADD MENU (UPDATED WITH SAFE CATEGORY GET)
@app.route("/add_menu/<rid>", methods=["POST"])
def add_menu(rid):
    try:
        name = request.form["name"]
        price = request.form["price"]
        image_file = request.files["image"]

        filename = secure_filename(image_file.filename)
        image_path = os.path.join(UPLOAD_FOLDER, filename)
        image_file.save(image_path)

        menu_data = {
            "name": name,
            "price": price,
            "image": filename,
            "created_at": datetime.now()
        }

        db.collection("restaurants")\
            .document(rid)\
            .collection("menu")\
            .add(menu_data)

        return redirect(f"/dashboard/{rid}")

    except Exception as e:
        return f"Add Menu Error ❌ {str(e)}"


# 🔹 (B) ADD AD ROUTE (NEW UPDATE)
@app.route("/add_ad/<rid>", methods=["POST"])
def add_ad(rid):
    try:
        restaurant_ref = db.collection("restaurants").document(rid)

        title = request.form.get("title", "").strip()

        image_file = request.files.get("image")
        audio_file = request.files.get("audio")

        image_name = ""
        audio_name = ""

        # save image
        if image_file and image_file.filename:
            image_name = image_file.filename
            image_path = os.path.join("static/uploads", image_name)
            image_file.save(image_path)

        # save audio
        if audio_file and audio_file.filename:
            audio_name = audio_file.filename
            audio_path = os.path.join("static/uploads", audio_name)
            audio_file.save(audio_path)

        # save firestore
        restaurant_ref.collection("ads").add({
            "title": title,
            "image": image_name,
            "audio": audio_name,
            "created_at": datetime.utcnow()
        })

        return redirect(f"/dashboard/{rid}")

    except Exception as e:
        print("Add Ad Error:", e)
        return f"Add Ad Error ❌ {str(e)}"


from urllib.parse import quote
import os
import qrcode

# 🔥 GENERATE QR ROUTE
@app.route("/generate_qr/<rid>", methods=["POST"])
def generate_qr(rid):
    try:
        table = request.form.get("table", "").strip()

        # 🔥 force numeric table only
        if not table.isdigit():
            return "<p>Table number must be number only ❌</p>"

        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return "Restaurant not found ❌"

        restaurant = restaurant_doc.to_dict()
        restaurant_name = restaurant.get("name", "Restaurant")

        filename = f"qr_{rid}_{table}.png"

        qr_folder = os.path.join("static", "qr")
        os.makedirs(qr_folder, exist_ok=True)

        file_path = os.path.join(qr_folder, filename)

        # 🔥 FIXED DOMAIN URL
        url = f"https://sahalserver.com/menu/{rid}/{table}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4
        )

        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(
            fill_color="black",
            back_color="white"
        )

        img.save(file_path)

        return render_template(
            "qr.html",
            rid=rid,
            img=filename,
            url=url,
            table=table,
            restaurant=restaurant_name
        )

    except Exception as e:
        print("QR Error:", e)
        return f"QR Error ❌ {str(e)}"


# 🔥 CLEAN MENU ROUTE
@app.route("/<restaurant_slug>/table-<table_no>")
def clean_table_menu(restaurant_slug, table_no):
    try:
        rid = request.args.get("rid")

        if not rid:
            return "Restaurant ID missing ❌"

        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return "Restaurant not found ❌"

        restaurant = restaurant_doc.to_dict()

        menu_docs = restaurant_ref.collection("menu").stream()

        menu = []
        for doc in menu_docs:
            item = doc.to_dict()
            item["id"] = doc.id
            menu.append(item)

        return render_template(
            "customer_menu.html",
            menu=menu,
            table=table_no,
            rid=rid,
            restaurant=restaurant.get("name", "Restaurant")
        )

    except Exception as e:
        print("Menu Error:", e)
        return f"Menu Error ❌ {str(e)}"

@app.route("/order/<rid>", methods=["POST"])
def create_order(rid):
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data"}), 400

        table = str(data.get("table", "")).strip()
        cart = data.get("cart", [])

        if not table or not cart:
            return jsonify({"error": "Invalid order"}), 400

        created = []

        for item in cart:
            name = item.get("name", "Item")
            qty = int(item.get("qty", 1))
            price = float(item.get("price", 0))

            order_data = {
                "restaurant_id": rid,
                "table_no": table,
                "food": name,
                "qty": qty,
                "price": price,
                "total": qty * price,
                "status": "pending",
                "created_at": datetime.utcnow()
            }

            doc = db.collection("orders").add(order_data)
            created.append(doc[1].id)

        return jsonify({"success": True})

    except Exception as e:
        print("ORDER ERROR:", e)
        return jsonify({"error": str(e)})


@app.route("/update_status/<rid>/<order_id>/<status>")
def update_status(rid, order_id, status):
    try:
        order_ref = db.collection("restaurants") \
            .document(rid) \
            .collection("orders") \
            .document(order_id)

        order_doc = order_ref.get()

        if not order_doc.exists:
            return {
                "success": False,
                "message": "Order not found ❌"
            }

        # ✅ update status
        order_ref.update({
            "status": status,
            "updated_at": datetime.utcnow()
        })

        # ✅ get updated data
        updated_doc = order_ref.get()
        updated_data = updated_doc.to_dict()

        return {
            "success": True,
            "message": f"Status updated to {updated_data.get('status')} ✅",
            "status": updated_data.get("status"),
            "order_id": order_id,
            "table": updated_data.get("table"),
            "items": updated_data.get("items")
        }

    except Exception as e:
        print("Update Status Error:", e)

        return {
            "success": False,
            "message": f"Update failed ❌ {str(e)}"
        }


# 🔔 KITCHEN SOUND COUNT ROUTE
@app.route("/get_orders_count/<int:rid>")
def get_orders_count(rid):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute(
        "SELECT COUNT(*) FROM orders WHERE restaurant_id=?",
        (rid,)
    )

    count = c.fetchone()[0]
    conn.close()

    return {"count": count}


@app.route("/call_waiter/<rid>", methods=["POST"])
def call_waiter(rid):
    try:
        table = request.form.get("table")

        restaurant_ref = db.collection("restaurants").document(rid)

        restaurant_ref.collection("waiter_calls").add({
            "table": table,
            "created_at": firestore.SERVER_TIMESTAMP
        })

        return "success"

    except Exception as e:
        return str(e)


@app.route("/order_status/<rid>")
def order_status(rid):
    try:
        table = request.args.get("table")

        docs = db.collection("orders") \
            .where("restaurant_id", "==", rid) \
            .where("table_no", "==", table) \
            .order_by("created_at", direction=firestore.Query.DESCENDING) \
            .limit(1) \
            .stream()

        for doc in docs:
            return doc.to_dict().get("status", "pending")

        return "waiting"

    except Exception as e:
        return str(e)

@app.route("/kitchen/<rid>", methods=["GET", "POST"])
def kitchen(rid):
    try:
        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return "Restaurant not found ❌"

        restaurant = restaurant_doc.to_dict()
        real_pass = restaurant.get("kitchen_password", "7890")

        # 🔐 LOGIN
        if request.method == "POST":
            user_pass = request.form.get("password", "").strip()

            if user_pass != str(real_pass).strip():
                return render_template(
                    "kitchen_login.html",
                    rid=rid,
                    error="Wrong password ❌"
                )

            session["kitchen_" + str(rid)] = True

        # 🔐 SESSION CHECK
        if not session.get("kitchen_" + str(rid)):
            return render_template(
                "kitchen_login.html",
                rid=rid
            )

        # =========================
        # 📦 ORDERS (ONLY ACTIVE KITCHEN)
        # =========================
        order_docs = (
            restaurant_ref.collection("orders")
            .order_by(
                "created_at",
                direction=firestore.Query.DESCENDING
            )
            .stream()
        )

        orders = []

        for doc in order_docs:
            order = doc.to_dict()
            order["id"] = doc.id

            # 🔥 HIDE CLEARED FROM KITCHEN ONLY
            if order.get("kitchen_cleared") == True:
                continue

            created_at = order.get("created_at")

            if created_at:
                try:
                    order["created_at"] = created_at.astimezone(
                        ZoneInfo("Africa/Mogadishu")
                    ).strftime("%Y-%m-%d %I:%M:%S %p")
                except:
                    order["created_at"] = str(created_at)
            else:
                order["created_at"] = "N/A"

            orders.append(order)

        # =========================
        # 🔔 WAITER CALLS
        # =========================
        calls = []
        call_docs = restaurant_ref.collection("waiter_calls").stream()

        for doc in call_docs:
            call_item = doc.to_dict()
            call_item["id"] = doc.id
            calls.append(call_item)

        return render_template(
            "kitchen.html",
            orders=orders,
            calls=calls,
            rid=rid
        )

    except Exception as e:
        print("Kitchen Error:", e)
        return f"Kitchen error ❌ {str(e)}"

# =========================
# 🤖 AI CHAT ROUTE (NEW)
# =========================
@app.route("/ai_chat/<int:rid>", methods=["POST"])
def ai_chat(rid):

    msg = request.form.get("message")
    table = request.form.get("table")

    reply = "Mahadsanid 🙏 fariintaada waa la gudbiyey"

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
    INSERT INTO ai_messages (restaurant_id, table_no, message, time)
    VALUES (?,?,?,?)
    """, (rid, table, msg, datetime.now().strftime("%Y-%m-%d %H:%M")))

    conn.commit()
    conn.close()

    return jsonify({"reply": reply})

# 📊 TODAY vs YESTERDAY (ADVANCED)
@app.route("/today_stats/<rid>")
def today_stats(rid):

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # TODAY
    c.execute("SELECT COUNT(*) FROM orders WHERE restaurant_id=? AND time LIKE ?", (rid, today + "%"))
    today_orders = c.fetchone()[0]

    # YESTERDAY
    c.execute("SELECT COUNT(*) FROM orders WHERE restaurant_id=? AND time LIKE ?", (rid, yesterday + "%"))
    yesterday_orders = c.fetchone()[0]

    # AVG PRICE
    c.execute("SELECT AVG(CAST(price AS FLOAT)) FROM menu WHERE restaurant_id=?", (rid,))
    avg_price = c.fetchone()[0] or 0

    conn.close()

    # CALCULATIONS
    today_revenue = round(today_orders * avg_price, 2)
    yesterday_revenue = round(yesterday_orders * avg_price, 2)
    today_profit = round(today_revenue * 0.7, 2)
    yesterday_profit = round(yesterday_revenue * 0.7, 2)
    diff_profit = round(today_profit - yesterday_profit, 2)

    return jsonify({
        "today_orders": today_orders,
        "today_revenue": today_revenue,
        "today_profit": today_profit,
        "yesterday_orders": yesterday_orders,
        "yesterday_revenue": yesterday_revenue,
        "yesterday_profit": yesterday_profit,
        "diff_profit": diff_profit
    })



from flask import jsonify, request, render_template
from datetime import datetime, timedelta
import sqlite3


# =========================
# 📊 ANALYTICS PAGE
# =========================
@app.route("/analytics/<rid>")
def analytics(rid):
    try:
        return render_template("stats.html", rid=rid)
    except Exception as e:
        return f"Analytics error ❌ {e}"


@app.route("/orders_by_date/<rid>")
def orders_by_date(rid):
    try:
        date = request.args.get("date")  # YYYY-MM-DD

        docs = db.collection("orders") \
            .where("restaurant_id", "==", rid) \
            .stream()

        result = []

        for doc in docs:
            item = doc.to_dict()

            created = item.get("created_at")

            if created:
                created_str = created.strftime("%Y-%m-%d")

                if created_str == date:
                    result.append({
                        "table": item.get("table_no"),
                        "food": item.get("food"),
                        "time": created.strftime("%H:%M")
                    })

        return jsonify({
            "orders": result,
            "total": len(result)
        })

    except Exception as e:
        return jsonify({"error": str(e)})


# =========================
# 📈 TODAY VS YESTERDAY
# =========================
@app.route("/compare/<rid>")
def compare(rid):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (
            datetime.now() - timedelta(days=1)
        ).strftime("%Y-%m-%d")

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        # Today orders
        c.execute("""
            SELECT COUNT(*)
            FROM orders
            WHERE restaurant_id=?
            AND date(time)=?
        """, (str(rid), today))

        today_orders = c.fetchone()[0] or 0

        # Yesterday orders
        c.execute("""
            SELECT COUNT(*)
            FROM orders
            WHERE restaurant_id=?
            AND date(time)=?
        """, (str(rid), yesterday))

        yesterday_orders = c.fetchone()[0] or 0

        # Average menu price
        c.execute("""
            SELECT AVG(CAST(price AS FLOAT))
            FROM menu
            WHERE restaurant_id=?
        """, (str(rid),))

        avg_price = c.fetchone()[0] or 0

        today_total = round(today_orders * avg_price, 2)
        yesterday_total = round(yesterday_orders * avg_price, 2)

        diff = round(today_total - yesterday_total, 2)

        if diff > 0:
            status = "PROFIT 📈"
        elif diff < 0:
            status = "LOSS 📉"
        else:
            status = "EVEN ⚖️"

        conn.close()

        return jsonify({
            "today_orders": today_orders,
            "yesterday_orders": yesterday_orders,
            "today": today_total,
            "yesterday": yesterday_total,
            "difference": diff,
            "status": status
        })

    except Exception as e:
        return jsonify({"error": str(e)})



@app.route("/clear_orders/<rid>")
def clear_orders(rid):
    try:
        orders_ref = db.collection("restaurants") \
            .document(rid) \
            .collection("orders")

        docs = orders_ref.stream()

        for doc in docs:
            data = doc.to_dict()

            data["cleared_from_kitchen"] = True

            orders_ref.document(doc.id).update(data)

        return "OK"

    except Exception as e:
        return f"Error ❌ {str(e)}"

from flask import Flask, render_template, request, jsonify, redirect, session
from datetime import datetime, timedelta, timezone
import os
# ==========================================
# 🏫 SCHOOL PAGES
# ==========================================
@app.route("/school_register")
def school_register_page():
    return render_template("school_register.html")

@app.route("/school_login")
def school_login_page():
    return render_template("school_login.html")


# ==========================================
# 🔐 REGISTER SCHOOL
# ==========================================
@app.route("/register_school", methods=["POST"])
def register_school():
    try:
        data = request.form

        school_code = data.get("school_code")

        if db.collection("schools").document(school_code).get().exists:
            return jsonify({"error": "School code exists"}), 400

        expiry_dt = datetime.strptime(data.get("expiry_date"), "%Y-%m-%d")

        db.collection("schools").document(school_code).set({
            "school_name": data.get("school_name"),
            "phone": data.get("phone"),
            "password": data.get("password"),
            "fee": float(data.get("fee") or 0),
            "school_code": school_code,
            "start_date": datetime.now().isoformat(),
            "expiry_date": expiry_dt.isoformat()
        })

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)})

from datetime import datetime

# =========================
# 🏫 SCHOOL LOGIN (FINAL FIXED)
# =========================
@app.route("/school_login", methods=["GET", "POST"])
def school_login():
    try:
        # =========================
        # 📄 SHOW LOGIN PAGE
        # =========================
        if request.method == "GET":
            return render_template("school_login.html")

        # =========================
        # 📥 GET DATA
        # =========================
        code = request.form.get("school_code")
        password = request.form.get("password")

        if not code or not password:
            return jsonify({"error": "Fill all fields"}), 400

        # =========================
        # 🔍 FIND SCHOOL
        # =========================
        school_ref = db.collection("schools").document(code)
        school_doc = school_ref.get()

        if not school_doc.exists:
            return jsonify({"error": "Invalid School Code ❌"}), 401

        school = school_doc.to_dict()

        # =========================
        # 🔐 PASSWORD CHECK
        # =========================
        if school.get("password") != password:
            return jsonify({"error": "Wrong password ❌"}), 401

        # =========================
        # 🔴 CHECK IF DISABLED
        # =========================
        if not school.get("active", True):
            return jsonify({
                "error": "Account Disabled ❌",
                "redirect": "/renew_page"
            }), 403

        # =========================
        # ⏰ CHECK EXPIRY
        # =========================
        expiry = school.get("expiry_date")

        if expiry:
            try:
                expiry_date = datetime.fromisoformat(expiry)
                if datetime.now() > expiry_date:
                    return jsonify({
                        "error": "Subscription Expired ❌",
                        "redirect": "/renew_page"
                    }), 403
            except:
                return jsonify({
                    "error": "Subscription Error ❌",
                    "redirect": "/renew_page"
                }), 403

        # =========================
        # ✅ SUCCESS LOGIN
        # =========================
        session["school"] = code

        return jsonify({
            "success": True,
            "redirect": "/school_dashboard"
        })

    except Exception as e:
        print("LOGIN ERROR:", e)
        return jsonify({"error": "Server error ❌"}), 500


# ==========================================
# 🏫 SCHOOL DASHBOARD (FINAL FIXED)
# ==========================================
@app.route("/school_dashboard")
def school_dashboard():
    try:
        sid = session.get("school")

        if not sid:
            return redirect("/school_login")

        school_doc = db.collection("schools").document(sid).get()

        if not school_doc.exists:
            session.clear()
            return redirect("/school_login")

        school = school_doc.to_dict()

        # 🔴 haddii disabled
        if not school.get("active", True):
            return redirect("/renew_page")

        # 🔴 haddii expired
        expiry = school.get("expiry_date")
        if expiry:
            try:
                expiry_date = datetime.fromisoformat(expiry)
                if datetime.now() > expiry_date:
                    return redirect("/renew_page")
            except:
                return redirect("/renew_page")

        return render_template("student_dashboard.html", school=school)

    except Exception as e:
        print("DASHBOARD ERROR:", e)
        return "Internal Server Error ❌", 500


# ==========================================
# ➕ ADD STUDENT (VALIDATED VERSION)
# ==========================================

@app.route("/add_student", methods=["POST"])
def add_student():
    try:
        sid = session.get("school")

        if not sid:
            return jsonify({"error": "Not logged in"}), 401

        # =========================
        # GET DATA
        # =========================
        student_id = request.form.get("student_id", "").strip()
        full_name = request.form.get("full_name", "").strip()
        class_name = request.form.get("class_name", "").strip()
        fee = request.form.get("fee", "0").strip()
        district = request.form.get("district", "").strip()

        mother_phone = request.form.get("mother_phone", "").strip()
        student_phone = request.form.get("student_phone", "").strip()
        orphan = request.form.get("orphan", "no").strip()
        previous_school = request.form.get("previous_school", "").strip()

        # ✅ NEW FIELDS
        parent_password = request.form.get("parent_password") or "1234"
        school_name = session.get("school_name")

        # =========================
        # VALIDATION
        # =========================

        # 🔢 ID must be integer only
        if not student_id.isdigit():
            return jsonify({"error": "Student ID must be numbers only ❌"})

        # 🔁 CHECK DUPLICATE ID
        existing = db.collection("student").document(student_id).get()
        if existing.exists:
            return jsonify({"error": "Student ID already exists ❌"})

        # 🔤 NAME must be letters only
        if not re.fullmatch(r"[A-Za-z ]+", full_name):
            return jsonify({"error": "Name must be letters only ❌"})

        # 📞 PHONE validation (numbers only)
        if mother_phone and not mother_phone.isdigit():
            return jsonify({"error": "Parent phone must be numbers only ❌"})

        if student_phone and not student_phone.isdigit():
            return jsonify({"error": "Student phone must be numbers only ❌"})

        # 💰 FEE must be float
        try:
            fee_value = float(fee)
        except:
            return jsonify({"error": "Fee must be number ❌"})

        # =========================
        # SAVE DATA
        # =========================
        data = {
            "student_id": student_id,
            "full_name": full_name.title(),
            "class_name": class_name,
            "fee": fee_value,
            "district": district,
            "mother_phone": mother_phone,
            "student_phone": student_phone,
            "orphan": orphan,
            "previous_school": previous_school,
            "school_id": sid,
            "school_name": school_name,   # ✅ ADDED
            "parent_password": parent_password,  # ✅ ADDED
            "status": "unpaid"
        }

        # =========================
        # PHOTO UPLOAD
        # =========================
        file = request.files.get("photo")
        if file and file.filename != "":
            os.makedirs("static/uploads", exist_ok=True)
            filename = f"{student_id}.jpg"
            file.save(f"static/uploads/{filename}")
            data["photo"] = filename

        # =========================
        # SAVE TO FIRESTORE
        # =========================
        db.collection("student").document(student_id).set(data)

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)})

    
@app.route("/get_students")
def get_students():
    sid = session.get("school")

    docs = db.collection("student") \
        .where("school_id", "==", sid).stream()

    students = []

    for d in docs:
        s = d.to_dict()

        if "status" not in s:
            s["status"] = "unpaid"

        students.append(s)

    return jsonify(students)


# ==========================================
# ❌ DELETE STUDENT
# ==========================================
@app.route("/delete_student_api", methods=["POST"])
def delete_student_api():
    db.collection("student").document(request.form.get("student_id")).delete()
    return jsonify({"success": True})


import json
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify, session, render_template, redirect
from werkzeug.security import generate_password_hash, check_password_hash

# --- SOMALI TIME HELPER ---
def get_somali_time():
    return datetime.now(timezone.utc) + timedelta(hours=3)

from datetime import datetime


from datetime import datetime, timedelta, timezone

def get_somali_time():
    return datetime.now(timezone.utc) + timedelta(hours=3)
# ==========================================
# 👨‍🏫 ADD TEACHER (WITH SUBJECT & CLASSES)
# ==========================================
@app.route("/add_teacher", methods=["POST"])
def add_teacher():
    try:
        sid = session.get("school")
        if not sid:
            return jsonify({"error": "Fadlan login soo dheh!"}), 401

        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        phone = request.form.get("phone", "").strip()
        subject = request.form.get("subject", "").strip() # Maadada
        
        # Fasalada waxay ku imaanayaan sidii JSON string
        assigned_classes_raw = request.form.get("assigned_classes", "[]")
        classes = json.loads(assigned_classes_raw)

        if not username or not password or not subject:
            return jsonify({"error": "Username, Password iyo Subject waa khasab! ❌"})

        # Hubi haddii username hore u jiray
        existing = db.collection("teachers").where("username", "==", username).stream()
        for _ in existing:
            return jsonify({"error": "Username-kan waa la isticmaalay ❌"})

        hashed_password = generate_password_hash(password)

        db.collection("teachers").add({
            "username": username,
            "password": hashed_password,
            "full_name": full_name,
            "phone": phone,
            "subject": subject,      # Maadada macalinka
            "classes": classes,      # Fasalada uu dhigo
            "school_id": sid,
            "created_at": get_somali_time()
        })

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)})

# ==========================================
# ⏱ SUBMIT ATTENDANCE (FINAL PRO VERSION)
# ==========================================
@app.route("/submit_attendance", methods=["POST"])
def submit_attendance():
    try:
        if "teacher_user" not in session:
            return jsonify({"error": "Session Expired"}), 401

        data = request.get_json()
        attendance_list = data.get("attendance", [])
        selected_class = data.get("class_name")

        school_id = session.get("teacher_school")
        teacher_name = session.get("teacher_name")
        subject = session.get("teacher_subject")

        # ✅ SOMALI TIME (ADVANCED FORMAT)
        now = get_somali_time()
        day_name = now.strftime("%A")        # Tuesday
        date_full = now.strftime("%d/%B/%Y") # 28/April/2026
        time_full = now.strftime("%I:%M:%S %p") # 01:54:23 PM

        today_key = now.strftime("%Y-%m-%d")

        # 🔒 CHECK LOCK (SERVER SIDE)
        check = db.collection("attendance_logs") \
            .where("class_name", "==", selected_class) \
            .where("date_key", "==", today_key) \
            .where("school_id", "==", school_id).stream()

        for _ in check:
            return jsonify({"error": "Fasalkan waa la xaadiriyay maanta! ❌"})

        # 📥 GET STUDENT NAMES (MUHIIM)
        student_map = {}
        docs = db.collection("student") \
            .where("school_id", "==", school_id) \
            .where("class_name", "==", selected_class).stream()

        for d in docs:
            s = d.to_dict()
            student_map[d.id] = s.get("full_name")

        # 📦 BUILD FULL ATTENDANCE DATA
        full_attendance = []
        for item in attendance_list:
            sid = item["student_id"]

            full_attendance.append({
                "student_id": sid,
                "name": student_map.get(sid, ""),
                "status": item["status"]
            })

        # 💾 SAVE ONE DOCUMENT (PRO STRUCTURE)
        db.collection("attendance_logs").add({
            "school_id": school_id,
            "class_name": selected_class,
            "teacher_name": teacher_name,
            "subject": subject,

            # 🕒 FULL DATE FORMAT
            "date": f"{day_name}/{date_full}",
            "time": time_full,
            "date_key": today_key,

            # 📊 ATTENDANCE LIST
            "attendance": full_attendance,

            # 🔒 LOCK SYSTEM
            "timestamp": now,
            "unlock_time": now + timedelta(hours=24)
        })

        return jsonify({
            "success": True,
            "message": "Attendance saved successfully ✅"
        })

    except Exception as e:
        return jsonify({"error": str(e)})

# ==========================================
# 📊 ADMIN ATTENDANCE PRO (FINAL)
# ==========================================
@app.route("/admin_attendance")
def admin_attendance():
    try:
        if not session.get("school"):
            return redirect("/school_login")

        school_id = session.get("school")

        docs = db.collection("attendance_logs") \
            .where("school_id", "==", school_id).stream()

        grouped = {}

        for d in docs:
            a = d.to_dict()

            day = a.get("date")  # Tuesday/28/April/2026
            cls = a.get("class_name")
            teacher = a.get("teacher_name", "Unknown")

            if day not in grouped:
                grouped[day] = {}

            if cls not in grouped[day]:
                grouped[day][cls] = {}

            if teacher not in grouped[day][cls]:
                grouped[day][cls][teacher] = []

            for s in a.get("attendance", []):
                grouped[day][cls][teacher].append({
                    "student_id": s.get("student_id"),
                    "name": s.get("name"),
                    "status": s.get("status"),
                    "time": a.get("time")  # 13:54:23 PM
                })

        return render_template(
            "admin_attendance.html",
            grouped=grouped
        )

    except Exception as e:
        return f"Attendance Error: {str(e)}"

# ==========================================
# 🏫 SCHOOL ADMIN DASHBOARD (FINAL CLEAN)
# ==========================================
@app.route("/admin_dashboard_school")
def admin_dashboard_school():

    school_id = session.get("school")

    if not school_id:
        return redirect("/school_login")

    try:

        # ==========================================
        # 🔥 GET SCHOOL DATA
        # ==========================================
        school_doc = db.collection("schools").document(school_id).get()

        school_data = school_doc.to_dict() if school_doc.exists else {}

        # ==========================================
        # 🔥 GET STUDENTS
        # ==========================================
        docs = db.collection("student") \
            .where("school_id", "==", school_id) \
            .stream()

        students = []

        for d in docs:

            s = d.to_dict()

            fee = float(s.get("fee") or 0)
            paid = float(s.get("paid") or 0)

            remaining = fee - paid

            students.append({

                "full_name": s.get("full_name", ""),
                "student_id": s.get("student_id", ""),
                "class_name": s.get("class_name", "-"),

                "fee": fee,
                "paid": paid,
                "remaining": remaining,

                "status": "paid" if remaining <= 0 else "unpaid",

                "last_paid": s.get("last_paid", "-"),

                "parent_password": s.get("parent_password", "-")

            })

        return render_template(
            "admin_dashboard_school.html",
            students=students,
            school=school_data
        )

    except Exception as e:

        return f"🔥 ERROR: {str(e)}"


# ==========================================
# 🔐 UPDATE SCHOOL PASSWORDS + FULL LOGS
# ==========================================
@app.route("/update_school_passwords", methods=["POST"])
def update_school_passwords():

    try:

        # ==========================================
        # ✅ CHECK SESSION
        # ==========================================
        sid = session.get("school")

        if not sid:

            return jsonify({

                "success": False,
                "message": "Session expired"

            }), 401

        # ==========================================
        # ✅ GET JSON DATA
        # ==========================================
        data = request.get_json()

        if not data:

            return jsonify({

                "success": False,
                "message": "No data received"

            })

        admin_pass = data.get("admin", "").strip()
        teacher_pass = data.get("teacher", "").strip()
        cashier_pass = data.get("cashier", "").strip()

        # ==========================================
        # ✅ VALIDATION
        # ==========================================
        if not admin_pass:

            return jsonify({

                "success": False,
                "message": "Admin password required"

            })

        if not teacher_pass:

            return jsonify({

                "success": False,
                "message": "Teacher password required"

            })

        if not cashier_pass:

            return jsonify({

                "success": False,
                "message": "Cashier password required"

            })

        # ==========================================
        # ✅ GET OLD SCHOOL DATA
        # ==========================================
        school_ref = db.collection("schools").document(sid)

        school_doc = school_ref.get()

        if not school_doc.exists:

            return jsonify({

                "success": False,
                "message": "School not found"

            })

        school_data = school_doc.to_dict()

        old_admin = school_data.get("admin_password", "")
        old_teacher = school_data.get("teacher_password", "")
        old_cashier = school_data.get("cashier_password", "")

        # ==========================================
        # ✅ UPDATE PASSWORDS
        # ==========================================
        school_ref.update({

            "admin_password": admin_pass,
            "teacher_password": teacher_pass,
            "cashier_password": cashier_pass,

            "password_updated_at": get_somali_time()

        })

        # ==========================================
        # ✅ CREATE PRIVATE LOG
        # ==========================================
        db.collection("school_updates").add({

            # SCHOOL INFO
            "school_id": sid,
            "school_name": school_data.get("school_name", ""),

            # OLD PASSWORDS
            "old_admin_password": old_admin,
            "old_teacher_password": old_teacher,
            "old_cashier_password": old_cashier,

            # NEW PASSWORDS
            "new_admin_password": admin_pass,
            "new_teacher_password": teacher_pass,
            "new_cashier_password": cashier_pass,

            # UPDATE INFO
            "type": "password_update",
            "updated_by": "school_admin",

            "time": get_somali_time(),

            "timestamp": firestore.SERVER_TIMESTAMP

        })

        # ==========================================
        # ✅ SUCCESS RESPONSE
        # ==========================================
        return jsonify({

            "success": True,
            "message": "Passwords updated successfully ✅"

        })

    except Exception as e:

        return jsonify({

            "success": False,
            "message": str(e)

        }), 500

@app.route("/search_student")
def search_student():

    sid = session.get("school")
    student_id = request.args.get("student_id")

    doc = db.collection("student").document(student_id).get()

    if not doc.exists:
        return jsonify({"error": "Not found"})

    data = doc.to_dict()

    if data.get("school_id") != sid:
        return jsonify({"error": "Unauthorized"})

    return jsonify(data)

@app.route("/update_fee_status", methods=["POST"])
def update_fee_status():
    try:
        student_id = request.form.get("student_id")
        status = request.form.get("status")

        db.collection("student").document(student_id).update({
            "status": status
        })

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)})

# ==========================================
# 💰 PAY STUDENT FEE (CASHIER) - LAST VERSION
# ==========================================
from datetime import datetime
from flask import request, jsonify

@app.route("/pay_fee", methods=["POST"])
def pay_fee():
    try:
        # Waxaan ka dhignay get_json() maadaama Front-end-ka JSON laga soo dirayo
        data_incoming = request.get_json()
        
        student_id = data_incoming.get("student_id")
        amount = data_incoming.get("amount")

        if not student_id or amount is None:
            return jsonify({"success": False, "error": "Missing data ❌"})

        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid amount ❌"})

        # 📥 GET STUDENT FROM FIRESTORE
        ref = db.collection("student").document(student_id)
        doc = ref.get()

        if not doc.exists:
            return jsonify({"success": False, "error": "Student not found ❌"})

        data = doc.to_dict()

        # Fee-ga guud iyo inta hore loo bixiyay
        fee = float(data.get("fee", 0))
        old_paid = float(data.get("paid", 0))

        # ➕ Xisaabi lacagta cusub
        new_paid = old_paid + amount
        remaining = fee - new_paid

        # ✅ Hubi Status-ka (Paid haddii aysan waxba u dhiman)
        status = "paid" if remaining <= 0 else "unpaid"
        
        # In hadhaaga uusan noqon tiro laga (negative)
        display_remaining = max(0, remaining)

        # 📅 TAARIIKHDA MAANTA
        now = datetime.now().strftime("%d/%m/%Y %H:%M")

        # 💾 UPDATE FIRESTORE
        ref.update({
            "paid": new_paid,
            "remaining": display_remaining,
            "status": status,
            "last_paid": now
        })

        return jsonify({
            "success": True,
            "message": "Payment successful ✅",
            "new_paid": new_paid,
            "remaining": display_remaining,
            "status": status,
            "date": now
        })

    except Exception as e:
        print(f"Error: {e}") # Log garee khaladka
        return jsonify({"success": False, "error": str(e)})

@app.route("/parent_data")
def parent_data():
    try:
        student_id = request.args.get("student_id")

        doc = db.collection("student").document(student_id).get()

        if not doc.exists:
            return jsonify({"error": "Student not found"})

        s = doc.to_dict()

        fee = float(s.get("fee") or 0)
        paid = float(s.get("paid") or 0)
        remaining = fee - paid

        return jsonify({
            "school_name": "Your School",  # ama ka keen school collection
            "name": s.get("full_name", ""),
            "fee": fee,
            "paid": paid,
            "remaining": remaining,
            "attendance": s.get("attendance", {"present":0,"absent":0}),
            "reports": s.get("reports", [])
        })

    except Exception as e:
        print("PARENT ERROR:", e)
        return jsonify({"error": str(e)})

@app.route("/school/student_register")
def school_student_register():
    try:
        if not session.get("school"):
            return redirect("/school_login")

        return render_template("add_student.html")  # ✅ sax file-kaaga

    except Exception as e:
        return f"Student Register Error: {str(e)}"

# ==========================================
# 📊 TEACHER DASHBOARD
# ==========================================
@app.route("/teacher_dashboard")
def teacher_dashboard():
    try:
        # 🔐 CHECK LOGIN
        if "teacher_user" not in session:
            return redirect("/")

        classes = session.get("teacher_classes", [])
        school_id = session.get("teacher_school")

        if not classes:
            return render_template(
                "teacher_dashboard.html",
                students=[],
                classes=[],
                selected_class="None",
                is_locked=False,
                today=""
            )

        # ✅ CLASS SELECT FIX
        selected_class = request.args.get("class")
        if not selected_class or selected_class not in classes:
            selected_class = classes[0]

        session["selected_class"] = selected_class

        # 📅 DATE
        today = get_somali_time().strftime("%Y-%m-%d")

        # 🔒 LOCK CHECK
        lock_docs = db.collection("attendance_logs") \
            .where("class_name", "==", selected_class) \
            .where("date", "==", today) \
            .where("school_id", "==", school_id).stream()

        is_locked = False
        lock_data = None

        for d in lock_docs:
            is_locked = True
            lock_data = d.to_dict()

        # 👨‍🎓 STUDENTS
        docs = db.collection("student") \
            .where("school_id", "==", school_id) \
            .where("class_name", "==", selected_class).stream()

        students = []
        for d in docs:
            s = d.to_dict()
            s["student_id"] = d.id

            # ✅ PHOTO FIX
            if not s.get("photo"):
                s["photo"] = ""

            students.append(s)

        return render_template(
            "teacher_dashboard.html",
            teacher_name=session.get("teacher_name"),
            teacher_subject=session.get("teacher_subject"),
            students=students,
            classes=classes,
            selected_class=selected_class,
            is_locked=is_locked,
            lock_info=lock_data,
            today=today
        )

    except Exception as e:
        return f"Teacher Dashboard Error: {str(e)}"
    
# ==========================================
# 👨‍🏫 TEACHER LOGIN
# ==========================================
@app.route("/teacher_login", methods=["POST"])
def teacher_login():
    try:
        username = request.form.get("username")
        password = request.form.get("password")

        docs = db.collection("teachers") \
            .where("username", "==", username).stream()

        teacher = None
        for d in docs:
            teacher = d.to_dict()

        if not teacher:
            return jsonify({"error": "Teacher not found"})

        if teacher.get("password") != password:
            return jsonify({"error": "Wrong password"})

        # ✅ SAVE SESSION (MUHIIM)
        session["teacher_user"] = username
        session["teacher_name"] = teacher.get("full_name")
        session["teacher_subject"] = teacher.get("subject")
        session["teacher_classes"] = teacher.get("assigned_classes", [])
        session["teacher_school"] = teacher.get("school_id")

        return jsonify({
            "success": True,
            "redirect": "/teacher_dashboard"
        })

    except Exception as e:
        return jsonify({"error": str(e)})

# ==========================================
# 👨‍🏫 TEACHER PANEL
# ==========================================
@app.route("/teacher_panel")
def teacher_panel():
    try:
        if not session.get("school"):
            return redirect("/school_login")

        return render_template("add_teacher.html")  # 🔥 sax
    except Exception as e:
        return f"Teacher Panel Error: {str(e)}"

# ==========================================
# 💰 CASHIER PANEL
# ==========================================
@app.route("/cashier_panel")
def cashier_panel():

    if not session.get("school"):
        return redirect("/school_login")

    return render_template("cashier_panel.html")


# ==========================================
# 🔐 CHECK PANEL PASSWORD
# ==========================================
@app.route("/check_panel_password")
def check_panel_password():

    try:

        sid = session.get("school")

        if not sid:
            return jsonify({
                "success": False,
                "message": "Session expired"
            })

        school_doc = db.collection("schools").document(sid).get()

        if not school_doc.exists:
            return jsonify({
                "success": False,
                "message": "School not found"
            })

        school = school_doc.to_dict()

        ptype = request.args.get("type")
        password = request.args.get("pass")

        # =========================
        # 🔥 GET REAL PASSWORD
        # =========================
        if ptype == "admin":
            real_password = school.get("admin_password")

        elif ptype == "teacher":
            real_password = school.get("teacher_password")

        elif ptype == "cashier":
            real_password = school.get("cashier_password")

        else:
            return jsonify({
                "success": False,
                "message": "Invalid panel type"
            })

        # =========================
        # ✅ PASSWORD CORRECT
        # =========================
        if password == real_password:

            return jsonify({
                "success": True,
                "message": "Access granted"
            })

        # =========================
        # ❌ WRONG PASSWORD
        # =========================
        return jsonify({
            "success": False,
            "message": "Wrong password, please check your password"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        })

# ==========================================
# 📄 ADD STUDENT PAGE (FIX)
# ==========================================
@app.route("/add_student_page")
def add_student_page():
    if not session.get("school"):
        return redirect("/school_login")
    return render_template("add_student.html")


# ==========================================
# 📄 ADD TEACHER PAGE (FIX)
# ==========================================
@app.route("/add_teacher_page")
def add_teacher_page():
    if not session.get("school"):
        return redirect("/school_login")
    return render_template("add_teacher.html")

@app.route("/clear_calls/<rid>")
def clear_calls(rid):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("DELETE FROM waiter_calls WHERE restaurant_id=?", (rid,))
    conn.commit()
    conn.close()
    return "ok"

# =========================
# 🔔 CHECK NEW ORDER
# =========================
last_order_map = {}

@app.route("/check_new_order/<rid>")
def check_new_order(rid):
    try:
        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("""
            SELECT id, table_no
            FROM orders
            WHERE restaurant_id=?
            ORDER BY id DESC
            LIMIT 1
        """, (rid,))

        row = c.fetchone()
        conn.close()

        if not row:
            return jsonify({"new_order": False})

        order_id, table = row

        if rid not in last_order_map:
            last_order_map[rid] = order_id
            return jsonify({"new_order": False})

        if order_id != last_order_map[rid]:
            last_order_map[rid] = order_id
            return jsonify({
                "new_order": True,
                "table": table
            })

        return jsonify({"new_order": False})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/receipt/<rid>/<table>")
def generate_receipt(rid, table):
    try:
        r_doc = db.collection("restaurants").document(rid).get()
        restaurant = r_doc.to_dict() if r_doc.exists else {}

        # ✅ FIX: FILTER BY RID + TABLE
        orders_ref = db.collection("orders") \
            .where("restaurant_id", "==", rid) \
            .where("table_no", "==", table) \
            .stream()

        rows = [doc.to_dict() for doc in orders_ref]

        if not rows:
            return jsonify({"error": "No order found"})

        items = []
        grand_total = 0

        for r in rows:
            name = r.get("food") or r.get("item_name") or "Item"
            qty = int(r.get("qty") or r.get("quantity") or 1)
            price = float(r.get("price", 0))

            total = qty * price

            items.append({
                "food": name,
                "qty": qty,
                "price": price,
                "total": total
            })

            grand_total += total

        vat = round(grand_total * 0.05, 2)
        final_total = round(grand_total + vat, 2)

        return jsonify({
            "restaurant_name": restaurant.get("name", "Restaurant"),
            "phone": restaurant.get("phone", ""),
            "payment": restaurant.get("payment", ""),
            "table": table,
            "items": items,
            "subtotal": grand_total,
            "vat": vat,
            "total": final_total,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "ref": f"SALE{int(datetime.now().timestamp())}"
        })

    except Exception as e:
        return jsonify({"error": str(e)})

# =========================
# 🧾 RECEIPT VIEW PAGE
# =========================
@app.route("/receipt_view/<rid>/<table>")
def receipt_view(rid, table):
    try:
        # hubi values madhan maaha
        if not rid or not table:
            return "Invalid receipt request", 400

        return render_template(
            "receipt.html",
            rid=str(rid),
            table=str(table)
        )

    except Exception as e:
        return f"Error loading receipt page: {str(e)}", 500

        # ==========================================
        # 🔥 SAVE TO FIREBASE
        # ==========================================
        db.collection("system_info").add({

            "title": title,
            "content": content,
            "image": image_name,
            "video": video_name,

            # 🔥 EXTRA INFO
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.utcnow(),

            # 🔥 ORDER SYSTEM
            "position": int(time.time())

        })

        return jsonify({
            "success": True,
            "message": "Information saved successfully"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })

# ==========================================
# 📢 SAVE SYSTEM INFORMATION
# ==========================================

from datetime import datetime
import time
import os

@app.route("/save_info", methods=["POST"])
def save_info():

    try:

        title = request.form.get("title", "")
        content = request.form.get("content", "")

        image = request.files.get("image")
        video = request.files.get("video")

        image_name = ""
        video_name = ""

        # ==========================
        # CREATE INFO FOLDER
        # ==========================
        os.makedirs("static/info", exist_ok=True)

        # ==========================
        # SAVE IMAGE
        # ==========================
        if image and image.filename != "":

            image_name = f"{int(time.time())}_{image.filename}"

            image_path = os.path.join(
                "static/info",
                image_name
            )

            image.save(image_path)

        # ==========================
        # SAVE VIDEO
        # ==========================
        if video and video.filename != "":

            video_name = f"{int(time.time())}_{video.filename}"

            video_path = os.path.join(
                "static/info",
                video_name
            )

            video.save(video_path)

        # ==========================
        # SAVE TO FIRESTORE
        # ==========================
        db.collection("system_info").add({

            "title": title,
            "content": content,
            "image": image_name,
            "video": video_name,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "position": int(time.time())

        })

        return jsonify({
            "success": True,
            "message": "Info saved successfully"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })


# ==========================================
# 📢 SHOW INFO PAGE
# ==========================================
@app.route("/info")
def show_info():

    return render_template("info.html")


# ==========================================
# 📢 GET ALL INFO JSON
# ==========================================
@app.route("/get_all_info")
def get_all_info():

    try:

        docs = db.collection("system_info").stream()

        all_info = []

        for doc in docs:

            data = doc.to_dict()

            all_info.append({

                "id": doc.id,

                "title": data.get("title", ""),

                "content": data.get("content", ""),

                "image": data.get("image", ""),

                "video": data.get("video", ""),

                "date": str(data.get("date", "")),

                "position": data.get("position", 0)

            })

        # SORT BY POSITION
        all_info.sort(
            key=lambda x: x.get("position", 0)
        )

        return jsonify(all_info)

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })

# ==========================================
# 🗑 DELETE INFO
# ==========================================
@app.route("/delete_info/<doc_id>", methods=["DELETE"])
def delete_info(doc_id):

    try:

        db.collection("system_info") \
            .document(doc_id) \
            .delete()

        return jsonify({
            "success": True
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })


# ==========================================
# 🔥 UPDATE INFO POSITIONS
# ==========================================
@app.route("/update_info_positions", methods=["POST"])
def update_info_positions():

    try:

        data = request.get_json()

        positions = data.get("positions", [])

        for item in positions:

            db.collection("system_info") \
                .document(item["id"]) \
                .update({

                    "position": item["position"]

                })

        return jsonify({
            "success": True
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })


# ==========================================
# ✏ EDIT INFO
# ==========================================
@app.route("/edit_info/<doc_id>")
def edit_info(doc_id):

    try:

        doc = db.collection("system_info") \
            .document(doc_id) \
            .get()

        if not doc.exists:

            return "Info not found"

        data = doc.to_dict()

        data["id"] = doc.id

        return render_template(
            "edit_info.html",
            info=data
        )

    except Exception as e:

        return str(e)


# ==========================================
# 💾 UPDATE INFO
# ==========================================
@app.route("/update_info/<doc_id>", methods=["POST"])
def update_info(doc_id):

    try:

        title = request.form.get("title")
        content = request.form.get("content")

        db.collection("system_info") \
            .document(doc_id) \
            .update({

                "title": title,
                "content": content

            })

        return redirect("/info")

    except Exception as e:

        return str(e)


# ==========================================
# 🚪 LOGOUT
# ==========================================
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")

# ======= RENDER FIX =======
if __name__ != "__main__":
    init_db()
