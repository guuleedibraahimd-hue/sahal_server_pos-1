from flask import (
    Flask,
    render_template,
    request,
    redirect,
    jsonify,
    session,
    url_for,
    flash
)

from flask_socketio import (
    SocketIO,
    emit,
    join_room
)

from werkzeug.utils import secure_filename

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

import sqlite3
import os
import qrcode
import socket
import random
import json
import re

from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone

from flask_sock import Sock

import firebase_admin
from firebase_admin import credentials, firestore

# =========================
# 🚀 FLASK APP
# =========================

app = Flask(
    __name__,
    static_url_path="/static",
    static_folder="static",
    template_folder="templates"
)

# =========================
# 🔐 SECRET KEY
# =========================

app.secret_key = "supersecretkey123"

# =========================
# 🔌 SOCKET IO
# =========================

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)

# =========================
# 🔥 SAHAL SERVER FIREBASE
# =========================

firebase_key_str = os.environ.get("FIREBASE_KEY")
firebase_key = json.loads(firebase_key_str)
cred1 = credentials.Certificate(firebase_key)

sahal_app = firebase_admin.initialize_app(
    cred1,
    name="sahal_app"
)

db = firestore.client(sahal_app)  # ✅ hal mar oo kaliya

# =========================
# 💎 DHIBIC DAHAB FIREBASE
# =========================

dhibic_key_str = os.environ.get("DHIBIC_FIREBASE_KEY")
dhibic_key = json.loads(dhibic_key_str)
cred2 = credentials.Certificate(dhibic_key)

dhibic_app = firebase_admin.initialize_app(
    cred2,
    name="dhibic_app"
)

dhibic_db = firestore.client(dhibic_app)  # ✅ hal mar oo kaliya
# =========================
# 📁 FOLDERS
# =========================

UPLOAD_FOLDER = "static/uploads"
QR_FOLDER = "static/qr"

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

os.makedirs(
    QR_FOLDER,
    exist_ok=True
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# =========================
# DATABASE PATH
# =========================
DB_PATH = os.environ.get("DB_PATH", "database.db")

# =========================
# INIT DATABASE
# =========================
def init_db():
    print("INIT DB RUNNING...")

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

    c.execute("""
    CREATE TABLE IF NOT EXISTS settings(
        id INTEGER PRIMARY KEY,
        admin_password TEXT,
        register_password TEXT
    )
    """)

    c.execute("SELECT id FROM settings WHERE id=1")
    if not c.fetchone():
        c.execute("""
            INSERT INTO settings
            (id, admin_password, register_password)
            VALUES (1, '8880', '8880')
        """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS evote_passwords(
        id INTEGER PRIMARY KEY,
        student_password TEXT,
        candidate_password TEXT,
        evote_admin_password TEXT
    )
    """)

    c.execute("SELECT id FROM evote_passwords WHERE id=1")
    if not c.fetchone():
        c.execute("""
            INSERT INTO evote_passwords
            (id, student_password, candidate_password, evote_admin_password)
            VALUES (1, '12345', '12345', 'admin123')
        """)

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

    c.execute("""
    CREATE TABLE IF NOT EXISTS election_settings(
        id INTEGER PRIMARY KEY,
        current_round INTEGER DEFAULT 1,
        round_end_time TEXT
    )
    """)

    c.execute("SELECT id FROM election_settings WHERE id=1")
    if not c.fetchone():
        c.execute("""
            INSERT INTO election_settings
            (id, current_round, round_end_time)
            VALUES (1, 1, '')
        """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS election_timer(
        id INTEGER PRIMARY KEY,
        round_time_minutes INTEGER DEFAULT 60,
        end_time TEXT
    )
    """)

    c.execute("SELECT id FROM election_timer WHERE id=1")
    if not c.fetchone():
        c.execute("""
            INSERT INTO election_timer
            (id, round_time_minutes, end_time)
            VALUES (1, 60, '')
        """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS evote_timer(
        id INTEGER PRIMARY KEY,
        minutes INTEGER,
        end_time TEXT
    )
    """)

    c.execute("SELECT id FROM evote_timer WHERE id=1")
    if not c.fetchone():
        c.execute("""
            INSERT INTO evote_timer
            (id, minutes, end_time)
            VALUES (1, 60, '')
        """)

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

    c.execute("""
    CREATE TABLE IF NOT EXISTS supermarket_products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barcode TEXT UNIQUE,
        product_name TEXT,
        price REAL
    )
    """)

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

init_db()

# =========================
# 🔢 EVOTE CODE GENERATOR
# =========================
def generate_vote_code():
    return str(random.randint(100000, 999999))

# =========================
# 🇸🇴 SOMALIA TIME
# =========================
def somalia_time():
    return datetime.now(timezone(timedelta(hours=3)))

def get_somali_time():
    return datetime.now(timezone.utc) + timedelta(hours=3)

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

# =========================
# ⏰ AUTO CHECK EXPIRY
# =========================
def auto_check_expiry(rid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT expiry, active FROM restaurants WHERE id=?", (rid,))
        row = c.fetchone()
        if row and row[0]:
            expiry = datetime.strptime(row[0], "%Y-%m-%d")
            if datetime.now() >= expiry:
                c.execute("UPDATE restaurants SET active=0 WHERE id=?", (rid,))
                conn.commit()
    except Exception as e:
        print("Auto Expiry Error:", e)
    conn.close()

# =========================
# ⏰ AUTO ROUND PROGRESS
# =========================
def auto_round_progress():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT current_round FROM election_settings WHERE id=1")
        row = c.fetchone()
        current_round = row[0] if row else 1

        c.execute("SELECT end_time FROM election_timer WHERE id=1")
        timer_row = c.fetchone()

        if timer_row and timer_row[0]:
            end_time = datetime.strptime(timer_row[0], "%Y-%m-%d %H:%M:%S")
            now = somalia_time().replace(tzinfo=None)

            if now >= end_time + timedelta(minutes=20):
                next_round_no = current_round + 1
                if next_round_no <= 3:
                    c.execute(
                        "UPDATE election_settings SET current_round=? WHERE id=1",
                        (next_round_no,)
                    )
                    new_end = now + timedelta(minutes=60)
                    c.execute(
                        "UPDATE election_timer SET round_time_minutes=60, end_time=? WHERE id=1",
                        (new_end.strftime("%Y-%m-%d %H:%M:%S"),)
                    )
                    conn.commit()
                    print(f"Auto moved to Round {next_round_no} ✅")
    except Exception as e:
        print("Auto Round Error:", e)
    conn.close()

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
            item["name"] = item.get("name", "N/A")
            item["phone"] = item.get("phone", "N/A")
            item["username"] = item.get("username", "N/A")
            item["kitchen_password"] = item.get("kitchen_password", "N/A")
            item["password"] = item.get("password", "N/A")
            item["expiry"] = item.get("expiry", "N/A")
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
            item["name"] = item.get("name", "N/A")
            item["username"] = item.get("username", "N/A")
            item["expiry"] = item.get("expiry", "N/A")
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
            item["restaurant_name"] = item.get("restaurant_name", "N/A")
            item["food"] = item.get("food", "N/A")
            item["table"] = item.get("table", "N/A")
            item["time"] = item.get("time", "N/A")
            item["status"] = item.get("status", "Pending")
            orders.append(item)
    except Exception as e:
        print("Orders Load Error:", e)
    return orders


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

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/index")
def index():
    return render_template("index.html")


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
# 🔐 ADMIN ROUTE
# =========================
@app.route("/admin", methods=["GET", "POST"])
def admin():

    if request.method == "POST" and not session.get("admin_ok"):
        try:
            passwords = get_system_passwords()
            real_pass = passwords.get("admin_password")
            entered = request.form.get("password", "").strip()

            if entered != real_pass:
                return render_template(
                    "admin_login.html",
                    error="Wrong password ❌"
                )

            session["admin_ok"] = True
            return redirect("/admin")

        except Exception as e:
            print("ADMIN LOGIN ERROR:", e)
            return render_template(
                "admin_login.html",
                error=f"System Error ❌ {str(e)}"
            )

    if not session.get("admin_ok"):
        return render_template("admin_login.html")

    try:
        restaurants = get_restaurants_firestore()
        supermarkets = get_supermarkets_firestore()
        orders = get_orders_firestore()
        schools = get_schools_firestore()
        total = len(orders)

        info_docs = db.collection("system_info").stream()
        all_info = []

        for doc in info_docs:
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

        all_info.sort(key=lambda x: x.get("position", 0))

        for s in schools:
            expiry = s.get("expiry_date")
            try:
                if isinstance(expiry, str):
                    expiry = datetime.fromisoformat(expiry)
                elif hasattr(expiry, "timestamp"):
                    expiry = expiry
                else:
                    expiry = datetime.utcnow()
            except:
                expiry = datetime.utcnow()
            s["expiry_date_fixed"] = expiry

        review_docs = db.collection("reviews").stream()
        review_count_map = {}

        for doc in review_docs:
            item = doc.to_dict()
            rid = item.get("restaurant_id")
            if rid:
                review_count_map[rid] = review_count_map.get(rid, 0) + 1

        for r in restaurants:
            rid = r.get("id")
            r["review_count"] = review_count_map.get(rid, 0)

        top_reviews = sorted(
            restaurants,
            key=lambda x: x.get("review_count", 0),
            reverse=True
        )[:3]

        return render_template(
            "admin.html",
            restaurants=restaurants,
            supermarkets=supermarkets,
            schools=schools,
            orders=orders,
            total=total,
            top_reviews=top_reviews,
            all_info=all_info
        )

    except Exception as e:
        print("ADMIN LOAD ERROR:", e)
        return render_template(
            "admin_login.html",
            error=f"Admin Error ❌ {str(e)}"
        )


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

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
# =========================
# 🔐 CHANGE SYSTEM PASSWORDS
# =========================
@app.route("/change_system_passwords", methods=["POST"])
def change_system_passwords():
    try:
        if not session.get("admin_ok"):
            return jsonify({"success": False, "message": "Unauthorized"})

        data = request.get_json()
        admin_pass = data.get("admin_password")
        register_pass = data.get("register_password")

        if not admin_pass or not register_pass:
            return jsonify({"success": False, "message": "Fill all fields"})

        db.collection("system_passwords").document("main").set({
            "admin_password": admin_pass,
            "register_password": register_pass
        })

        return jsonify({"success": True, "message": "Passwords updated successfully ✅"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


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


# =========================
# ✅ ACTIVATE RESTAURANT
# =========================
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
        if not session.get("admin_ok"):
            return redirect("/admin")

        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return f"Restaurant not found ❌ ID: {rid}"

        restaurant_ref.update({
            "active": False,
            "status": "disabled",
            "disabled_at": datetime.now()
        })

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
# 🟢 ACTIVATE SCHOOL
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
# 🔴 DISABLE SCHOOL
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

        school_ref.update({
            "active": False,
            "status": "disabled",
            "expiry_date": datetime.now().isoformat(),
            "disabled_at": datetime.now().isoformat()
        })

        return redirect("/admin")

    except Exception as e:
        print("DISABLE SCHOOL ERROR:", e)
        return f"Disable school error ❌ {e}"


# =========================
# 🗑 DELETE SCHOOL
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
# 🛒 SUPERMARKET FUNCTIONS
# =========================
def get_supermarkets_firestore():
    supermarkets = []
    try:
        docs = db.collection("supermarkets").stream()
        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            item["active"] = item.get("active", False)
            item["name"] = item.get("name", "N/A")
            item["username"] = item.get("username", "N/A")
            item["expiry"] = item.get("expiry", "N/A")
            supermarkets.append(item)
    except Exception as e:
        print("Supermarket fetch error:", e)
    return supermarkets


def get_orders_firestore():
    orders = []
    try:
        docs = db.collection("orders").stream()
        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            item["restaurant_name"] = item.get("restaurant_name", "N/A")
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
        db.collection("supermarkets").document(mid).update({"active": True})
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
        db.collection("supermarkets").document(mid).update({"active": False})
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
    student_pass = request.form.get("student_password")
    screen_pass = request.form.get("screen_password")
    candidate_pass = request.form.get("candidate_password")
    admin_pass = request.form.get("evote_admin_password")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS evote_passwords(
            id INTEGER PRIMARY KEY,
            student_password TEXT,
            screen_password TEXT,
            candidate_password TEXT,
            evote_admin_password TEXT
        )
    """)

    try:
        c.execute("ALTER TABLE evote_passwords ADD COLUMN screen_password TEXT")
    except:
        pass

    c.execute("SELECT id FROM evote_passwords WHERE id=1")
    row = c.fetchone()

    if row:
        c.execute("""
            UPDATE evote_passwords
            SET student_password=?,
                screen_password=?,
                candidate_password=?,
                evote_admin_password=?
            WHERE id=1
        """, (student_pass, screen_pass, candidate_pass, admin_pass))
    else:
        c.execute("""
            INSERT INTO evote_passwords
            (id, student_password, screen_password, candidate_password, evote_admin_password)
            VALUES (1, ?, ?, ?, ?)
        """, (student_pass, screen_pass, candidate_pass, admin_pass))

    conn.commit()
    conn.close()

    return redirect("/admin")


# =========================
# 🗑 DELETE MENU
# =========================
@app.route("/delete_menu/<mid>/<rid>")
def delete_menu(mid, rid):
    try:
        restaurant_ref = db.collection("restaurants").document(rid)
        menu_ref = restaurant_ref.collection("menu").document(mid)
        menu_doc = menu_ref.get()

        if not menu_doc.exists:
            return "Menu item not found ❌"

        menu_data = menu_doc.to_dict()
        image_name = menu_data.get("image")

        if image_name:
            image_path = os.path.join("static", "uploads", image_name)
            if os.path.exists(image_path):
                os.remove(image_path)

        menu_ref.delete()
        return redirect(f"/restaurant_admin/{rid}")

    except Exception as e:
        return f"Delete menu error ❌ {str(e)}"


# =========================
# 🔄 RENEW SCHOOL
# =========================
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


# =========================
# ⛔ CHECK SCHOOL EXPIRY
# =========================
@app.before_request
def check_school_expiry():
    path = request.path

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

        if not data.get("active"):
            return redirect("/renew_page")

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


# =========================
# 📄 RENEW PAGE
# =========================
@app.route("/renew_page")
def renew_page():
    return render_template("renew.html")


# =========================
# 🔄 ADMIN RENEW SCHOOL
# =========================
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


# =========================
# 🔄 ADMIN RENEW RESTAURANT
# =========================
@app.route("/renew/restaurant/<string:rid>")
def renew_restaurant(rid):
    try:
        if not session.get("admin_ok"):
            return redirect("/admin")

        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return f"Restaurant not found ❌ ID: {rid}"

        new_expiry = datetime.now() + timedelta(days=90)

        restaurant_ref.update({
            "active": True,
            "status": "active",
            "expiry_date": new_expiry.isoformat(),
            "renewed_at": datetime.now().isoformat()
        })

        return redirect("/admin")

    except Exception as e:
        print("RENEW RESTAURANT ERROR:", e)
        return f"Renew error ❌ {e}"


# =========================
# 📝 REGISTER RESTAURANT
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    try:
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

        if request.method == "POST":
            months = int(request.form["months"])
            expiry_date = (
                datetime.now() + timedelta(days=months * 30)
            ).strftime("%Y-%m-%d")

            data = {
                "name": request.form["name"].strip(),
                "phone": request.form.get("phone", "").strip(),
                "username": request.form["username"].strip(),
                "password": request.form["password"].strip(),
                "kitchen_password": request.form["kitchen_password"].strip(),
                "restaurant_admin_password": request.form["restaurant_admin_password"].strip(),
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

            doc_ref = db.collection("restaurants").add(data)
            rid = doc_ref[1].id

            restaurant_ref = db.collection("restaurants").document(rid)
            restaurant_ref.collection("menu").document("init").set({"created_at": datetime.now()})
            restaurant_ref.collection("orders").document("init").set({"created_at": datetime.now()})

            return redirect("/admin")

        return render_template("register.html")

    except Exception as e:
        print("Register Error:", e)
        return f"Register Error ❌ {str(e)}"


# =========================
# 🔐 LOGIN RESTAURANT
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    try:
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()

            docs = db.collection("restaurants").stream()

            for doc in docs:
                data = doc.to_dict()

                if (
                    data.get("username") == username and
                    data.get("password") == password
                ):
                    if not data.get("active", True):
                        return render_template(
                            "login.html",
                            error="Account disabled ❌"
                        )

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
        print("LOGIN ERROR:", e)
        return render_template(
            "login.html",
            error=f"System Error ❌ {str(e)}"
        )


# =========================
# 🛒 SUPERMARKET LOGIN
# =========================
@app.route("/supermarket_login", methods=["GET", "POST"])
def supermarket_login():
    try:
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()

            docs = db.collection("supermarkets").stream()

            for doc in docs:
                data = doc.to_dict()

                if (
                    data.get("username") == username and
                    data.get("password") == password
                ):
                    if not data.get("active", True):
                        return render_template(
                            "supermarket_login.html",
                            error="Account disabled ❌"
                        )

                    session["market_login"] = True
                    session["market_id"] = doc.id
                    session["market_name"] = data.get("name")

                    return redirect("/supermarket_dashboard")

            return render_template(
                "supermarket_login.html",
                error="Wrong username or password ❌"
            )

        return render_template("supermarket_login.html")

    except Exception as e:
        print("SUPERMARKET LOGIN ERROR:", e)
        return render_template(
            "supermarket_login.html",
            error=f"System Error ❌ {str(e)}"
        )


# =========================
# 🛒 REGISTER SUPERMARKET
# =========================
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


# =========================
# ➕ ADD PRODUCT
# =========================
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
    """, (barcode, product_name, price))

    conn.commit()
    conn.close()

    return redirect("/supermarket_dashboard")

# =====================================
# 📊 RESTAURANT DASHBOARD
# =====================================
@app.route("/dashboard/<rid>")
def dashboard(rid):
    try:
        if not session.get("restaurant_login"):
            return redirect("/login")

        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return "Restaurant not found ❌"

        restaurant = restaurant_doc.to_dict()

        if not restaurant.get("active", True):
            return render_template("renew.html", rid=rid)

        expiry = restaurant.get("expiry", "")
        if expiry:
            try:
                expiry_date = datetime.strptime(expiry, "%Y-%m-%d")
                if datetime.now() >= expiry_date:
                    restaurant_ref.update({"active": False})
                    return render_template("renew.html", rid=rid)
            except Exception as expiry_error:
                print("Expiry Error:", expiry_error)

        menu = []
        menu_docs = restaurant_ref.collection("menu").stream()
        for doc in menu_docs:
            item = doc.to_dict()
            item["id"] = doc.id
            item["name"] = item.get("name", "No Name")
            item["price"] = item.get("price", 0)
            item["image"] = item.get("image", "")
            menu.append(item)

        ads = []
        ad_docs = restaurant_ref.collection("ads").stream()
        for doc in ad_docs:
            ad = doc.to_dict()
            ad["id"] = doc.id
            ad["title"] = ad.get("title", "")
            ad["image"] = ad.get("image", "")
            ad["audio"] = ad.get("audio", "")
            ad["created_at"] = ad.get("created_at", None)
            ads.append(ad)

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
# 📱 CUSTOMER MOBILE MENU
# =====================================
@app.route("/menu/<rid>/<table_no>")
def mobile_menu(rid, table_no):
    try:
        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return "Restaurant not found ❌"

        restaurant = restaurant_doc.to_dict()

        payment = restaurant.get("payment", "")
        payment_name = restaurant.get("payment_name", "")
        payment_number = restaurant.get("payment_number", payment)

        menu = []
        menu_docs = restaurant_ref.collection("menu").stream()
        for doc in menu_docs:
            if doc.id == "init":
                continue
            item = doc.to_dict()
            item["id"] = doc.id
            item["image"] = item.get("image", "")
            item["name"] = item.get("name", "No Name")
            item["price"] = item.get("price", 0)
            menu.append(item)

        ads = []
        ads_docs = restaurant_ref.collection("ads").stream()
        for doc in ads_docs:
            if doc.id == "init":
                continue
            ad = doc.to_dict()
            ad["id"] = doc.id
            ad["image"] = ad.get("image", "")
            ad["audio"] = ad.get("audio", "")
            ad["title"] = ad.get("title", "")
            ads.append(ad)

        ads = list(reversed(ads))

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


# =====================================
# 🛒 CUSTOMER ORDER
# =====================================
@app.route("/customer_order/<rid>", methods=["POST"])
def customer_order(rid):
    try:
        items = request.form.get("items", "")
        price = request.form.get("price", "0")
        table = request.form.get("table", "")
        drink_option = request.form.get("drink_option", "")
        food_option = request.form.get("food_option", "")
        tea_option = request.form.get("tea_option", "")

        if not items:
            return "No items selected ❌"
        if not table:
            return "Table number missing ❌"

        db.collection("restaurants").document(rid).collection("orders").add({
            "items": items,
            "price": float(price),
            "table": str(table),
            "drink_option": drink_option,
            "food_option": food_option,
            "tea_option": tea_option,
            "status": "pending",
            "created_at": datetime.utcnow()
        })

        return redirect(f"/menu/{rid}/{table}")

    except Exception as e:
        print("Order Error:", e)
        return f"Order failed ❌ {str(e)}"


# =====================================
# 📊 SALES DATA
# =====================================
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
        return jsonify({"error": str(e)})


# =====================================
# 🍽 RESTAURANT ADMIN PANEL
# =====================================
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

        menu = []
        menu_docs = restaurant_ref.collection("menu").stream()
        for doc in menu_docs:
            item = doc.to_dict()
            item["id"] = doc.id
            menu.append(item)

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
# 🧹 CLEAR KITCHEN ORDERS
# =====================================
@app.route("/clear_kitchen_orders/<rid>")
def clear_kitchen_orders(rid):
    try:
        if not session.get("admin_" + str(rid)):
            return redirect(f"/restaurant_admin_login/{rid}")

        orders_ref = db.collection("restaurants").document(rid).collection("orders")
        docs = orders_ref.stream()

        for doc in docs:
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

        ads_ref = db.collection("restaurants").document(rid).collection("ads")
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
            entered_password = request.form.get("password", "").strip()

            real_password = str(
                restaurant.get("restaurant_admin_password")
                or restaurant.get("resturen_admin password")
                or ""
            ).strip()

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
              style="max-width:400px;margin:50px auto;font-family:Arial;
                     background:white;padding:25px;border-radius:12px;
                     box-shadow:0 0 10px rgba(0,0,0,0.1);">
            <h2 style="text-align:center;">Admin Login 🔐</h2>
            <input type="password" name="password"
                   placeholder="Enter admin password" required
                   style="width:100%;padding:12px;margin:15px 0;
                          border:1px solid #ddd;border-radius:8px;
                          box-sizing:border-box;">
            <button type="submit"
                    style="width:100%;padding:12px;background:#0a7cff;
                           color:white;border:none;border-radius:8px;
                           font-weight:bold;cursor:pointer;">
                Login
            </button>
        </form>
        '''

    except Exception as e:
        print("Login Error:", e)
        return f"Login error ❌ {str(e)}"


# =====================================
# 👥 ADD STAFF
# =====================================
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
        db.collection("restaurants").document(rid).collection("staff").add(staff_data)
        return redirect("/dashboard/" + rid)

    except Exception as e:
        return f"Add staff error ❌ {str(e)}"


# =====================================
# 👥 STAFF LIST
# =====================================
@app.route("/staff_list/<rid>")
def staff_list(rid):
    try:
        docs = db.collection("restaurants").document(rid).collection("staff").stream()
        staff = []
        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            staff.append(item)
        return render_template("staff_list.html", staff=staff)

    except Exception as e:
        return f"Staff list error ❌ {str(e)}"


# =====================================
# 📰 SEND NEWS
# =====================================
@app.route("/send_news/<rid>", methods=["POST"])
def send_news(rid):
    try:
        news_data = {
            "title": request.form["title"],
            "message": request.form["message"],
            "created_at": datetime.now()
        }
        db.collection("restaurants").document(rid).collection("staff_news").add(news_data)
        return redirect("/dashboard/" + rid)

    except Exception as e:
        return f"Send news error ❌ {str(e)}"


# =====================================
# 📰 STAFF NEWS
# =====================================
@app.route("/staff_news/<rid>")
def staff_news(rid):
    try:
        docs = db.collection("restaurants").document(rid).collection("staff_news").stream()
        news = []
        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            news.append(item)
        return render_template("staff_news.html", news=news)

    except Exception as e:
        return f"Staff news error ❌ {str(e)}"


# =====================================
# 📊 STATS
# =====================================
@app.route("/stats/<rid>")
def stats(rid):
    try:
        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM orders WHERE restaurant_id=?", (rid,))
        orders = c.fetchone()[0]

        c.execute("SELECT AVG(CAST(price AS FLOAT)) FROM menu WHERE restaurant_id=?", (rid,))
        row = c.fetchone()
        avg_price = row[0] if row and row[0] else 0

        conn.close()

        revenue = orders * avg_price
        profit = round(revenue * 0.7, 2)

        return jsonify({
            "orders": orders,
            "revenue": round(revenue, 2),
            "profit": profit
        })

    except Exception as e:
        return jsonify({"error": str(e)})


# =====================================
# 🔔 GET CALLS
# =====================================
@app.route("/get_calls/<rid>")
def get_calls(rid):
    try:
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM waiter_calls WHERE restaurant_id=?", (rid,))
        count = c.fetchone()[0]
        conn.close()
        return jsonify({"count": count})

    except Exception as e:
        return jsonify({"error": str(e)})


# =====================================
# ✅ ADD MENU
# =====================================
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

        db.collection("restaurants").document(rid).collection("menu").add(menu_data)
        return redirect(f"/dashboard/{rid}")

    except Exception as e:
        return f"Add Menu Error ❌ {str(e)}"


# =====================================
# 📢 ADD AD
# =====================================
@app.route("/add_ad/<rid>", methods=["POST"])
def add_ad(rid):
    try:
        restaurant_ref = db.collection("restaurants").document(rid)
        title = request.form.get("title", "").strip()

        image_file = request.files.get("image")
        audio_file = request.files.get("audio")

        image_name = ""
        audio_name = ""

        if image_file and image_file.filename:
            image_name = image_file.filename
            image_file.save(os.path.join("static/uploads", image_name))

        if audio_file and audio_file.filename:
            audio_name = audio_file.filename
            audio_file.save(os.path.join("static/uploads", audio_name))

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


# =====================================
# 📱 GENERATE QR
# =====================================
@app.route("/generate_qr/<rid>", methods=["POST"])
def generate_qr(rid):
    try:
        table = request.form.get("table", "").strip()

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

        url = f"https://sahalserver.com/menu/{rid}/{table}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
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


# =====================================
# 🍽 CLEAN MENU ROUTE
# =====================================
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

        menu = []
        menu_docs = restaurant_ref.collection("menu").stream()
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

# =====================================
# 📦 CREATE ORDER - FINAL FIX
# =====================================
@app.route("/order/<rid>", methods=["POST"])
def create_order(rid):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data"}), 400

        table = str(data.get("table", "")).strip()
        cart  = data.get("cart", [])

        if not table or not cart:
            return jsonify({"error": "Invalid order"}), 400

        items_text  = ", ".join([f"{i.get('qty')}x {i.get('name')}" for i in cart])
        total_price = sum(float(i.get("price", 0)) * int(i.get("qty", 1)) for i in cart)

        # ✅ HAL MEEl KALIYA - restaurants subcollection
        order_ref = db.collection("restaurants").document(rid)\
                      .collection("orders").document()
        order_id  = order_ref.id

        order_ref.set({
            "items":      items_text,
            "cart":       cart,
            "table":      table,
            "price":      total_price,
            "status":     "pending",
            "created_at": datetime.utcnow(),
            "kitchen_cleared": False
        })

        return jsonify({
            "success":     True,
            "message":     "Order sent ✅",
            "order_id":    order_id,
            "receipt_url": f"/receipt/{rid}/{order_id}"
        })

    except Exception as e:
        print("ORDER ERROR:", e)
        return jsonify({"error": str(e)})

# =====================================
# 🔄 UPDATE STATUS
# =====================================
@app.route("/update_status/<rid>/<order_id>/<status>")
def update_status(rid, order_id, status):
    try:
        order_ref = db.collection("restaurants") \
            .document(rid) \
            .collection("orders") \
            .document(order_id)

        order_doc = order_ref.get()

        if not order_doc.exists:
            return jsonify({"success": False, "message": "Order not found ❌"})

        order_ref.update({
            "status": status,
            "updated_at": datetime.utcnow()
        })

        updated_data = order_ref.get().to_dict()

        return jsonify({
            "success": True,
            "message": f"Status updated to {updated_data.get('status')} ✅",
            "status": updated_data.get("status"),
            "order_id": order_id,
            "table": updated_data.get("table"),
            "items": updated_data.get("items")
        })

    except Exception as e:
        print("Update Status Error:", e)
        return jsonify({"success": False, "message": f"Update failed ❌ {str(e)}"})


# =====================================
# 🔔 GET ORDERS COUNT
# =====================================
@app.route("/get_orders_count/<int:rid>")
def get_orders_count(rid):
    try:
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM orders WHERE restaurant_id=?", (rid,))
        count = c.fetchone()[0]
        conn.close()
        return jsonify({"count": count})

    except Exception as e:
        return jsonify({"error": str(e)})


# =====================================
# 🔔 CALL WAITER
# =====================================
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


# =====================================
# 📋 ORDER STATUS
# =====================================
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


# =====================================
# 🍳 KITCHEN
# =====================================
@app.route("/kitchen/<rid>", methods=["GET", "POST"])
def kitchen(rid):
    try:
        restaurant_ref = db.collection("restaurants").document(rid)
        restaurant_doc = restaurant_ref.get()

        if not restaurant_doc.exists:
            return "Restaurant not found ❌"

        restaurant = restaurant_doc.to_dict()
        real_pass = restaurant.get("kitchen_password", "7890")

        if request.method == "POST":
            user_pass = request.form.get("password", "").strip()
            if user_pass != str(real_pass).strip():
                return render_template("kitchen_login.html", rid=rid, error="Wrong password ❌")
            session["kitchen_" + str(rid)] = True

        if not session.get("kitchen_" + str(rid)):
            return render_template("kitchen_login.html", rid=rid)

        order_docs = restaurant_ref.collection("orders") \
            .order_by("created_at", direction=firestore.Query.DESCENDING) \
            .stream()

        orders = []
        for doc in order_docs:
            order = doc.to_dict()
            order["id"] = doc.id

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

        calls = []
        call_docs = restaurant_ref.collection("waiter_calls").stream()
        for doc in call_docs:
            call_item = doc.to_dict()
            call_item["id"] = doc.id
            calls.append(call_item)

        return render_template("kitchen.html", orders=orders, calls=calls, rid=rid)

    except Exception as e:
        print("Kitchen Error:", e)
        return f"Kitchen error ❌ {str(e)}"


# =====================================
# 🤖 AI CHAT
# =====================================
@app.route("/ai_chat/<int:rid>", methods=["POST"])
def ai_chat(rid):
    try:
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

    except Exception as e:
        return jsonify({"error": str(e)})


# =====================================
# 📊 TODAY STATS
# =====================================
@app.route("/today_stats/<rid>")
def today_stats(rid):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM orders WHERE restaurant_id=? AND time LIKE ?", (rid, today + "%"))
        today_orders = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM orders WHERE restaurant_id=? AND time LIKE ?", (rid, yesterday + "%"))
        yesterday_orders = c.fetchone()[0]

        c.execute("SELECT AVG(CAST(price AS FLOAT)) FROM menu WHERE restaurant_id=?", (rid,))
        row = c.fetchone()
        avg_price = row[0] if row and row[0] else 0

        conn.close()

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

    except Exception as e:
        return jsonify({"error": str(e)})


# =====================================
# 📊 ANALYTICS PAGE
# =====================================
@app.route("/analytics/<rid>")
def analytics(rid):
    try:
        return render_template("stats.html", rid=rid)
    except Exception as e:
        return f"Analytics error ❌ {e}"

# =====================================
# 📅 ORDERS BY DATE
# =====================================
@app.route("/orders_by_date/<rid>")
def orders_by_date(rid):
    try:
        date = request.args.get("date")

        docs = db.collection("orders") \
            .where("restaurant_id", "==", rid) \
            .stream()

        result = []

        for doc in docs:
            item = doc.to_dict()
            created = item.get("created_at")

            if created:
                try:
                    created_str = created.strftime("%Y-%m-%d")
                    if created_str == date:
                        result.append({
                            "table": item.get("table_no"),
                            "food": item.get("food"),
                            "time": created.strftime("%H:%M")
                        })
                except:
                    pass

        return jsonify({"orders": result, "total": len(result)})

    except Exception as e:
        return jsonify({"error": str(e)})


# =====================================
# 📈 COMPARE TODAY VS YESTERDAY
# =====================================
@app.route("/compare/<rid>")
def compare(rid):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("""
            SELECT COUNT(*) FROM orders
            WHERE restaurant_id=? AND date(time)=?
        """, (str(rid), today))
        today_orders = c.fetchone()[0] or 0

        c.execute("""
            SELECT COUNT(*) FROM orders
            WHERE restaurant_id=? AND date(time)=?
        """, (str(rid), yesterday))
        yesterday_orders = c.fetchone()[0] or 0

        c.execute("""
            SELECT AVG(CAST(price AS FLOAT))
            FROM menu WHERE restaurant_id=?
        """, (str(rid),))
        row = c.fetchone()
        avg_price = row[0] if row and row[0] else 0

        conn.close()

        today_total = round(today_orders * avg_price, 2)
        yesterday_total = round(yesterday_orders * avg_price, 2)
        diff = round(today_total - yesterday_total, 2)

        if diff > 0:
            status = "PROFIT 📈"
        elif diff < 0:
            status = "LOSS 📉"
        else:
            status = "EVEN ⚖️"

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


# =====================================
# 🧹 CLEAR ORDERS
# =====================================
@app.route("/clear_orders/<rid>")
def clear_orders(rid):
    try:
        orders_ref = db.collection("restaurants").document(rid).collection("orders")
        docs = orders_ref.stream()

        for doc in docs:
            orders_ref.document(doc.id).update({
                "cleared_from_kitchen": True
            })

        return "OK"

    except Exception as e:
        return f"Error ❌ {str(e)}"


# =====================================
# 🏫 SCHOOL REGISTER PAGE
# =====================================
@app.route("/school_register")
def school_register_page():
    return render_template("school_register.html")


# =====================================
# 🔐 REGISTER SCHOOL
# =====================================
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

@app.route("/school_login", methods=["GET", "POST"])
def school_login():
    try:
        if request.method == "GET":
            return render_template("school_login.html")

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        print(f"LOGIN ATTEMPT: username={username}, password={password}")  # DEBUG

        # ✅ Toos u hel document-ka ID-ga ah
        school_doc = db.collection("schools").document(username).get()

        print(f"DOC EXISTS: {school_doc.exists}")  # DEBUG

        if not school_doc.exists:
            return render_template("school_login.html", error="❌ School code ma jiro")

        data = school_doc.to_dict()
        print(f"DATA: {data}")  # DEBUG

        # ✅ Password check
        if data.get("password") != password:
            return render_template("school_login.html", error="❌ Password khalad ah")

        # ✅ Status check
        if data.get("status") == "disabled":
            return render_template("school_login.html", error="❌ Account disabled")

        session["school"] = school_doc.id
        session["school_login"] = True
        session["school_id"] = school_doc.id
        session["school_name"] = data.get("school_name")

        return redirect("/school_dashboard")

    except Exception as e:
        print("SCHOOL LOGIN ERROR:", e)
        return render_template("school_login.html", error=f"❌ Error: {str(e)}")


# =====================================
# 🏫 SCHOOL DASHBOARD
# =====================================
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

        if not school.get("active", True):
            return redirect("/renew_page")

        expiry = school.get("expiry_date")
        if expiry:
            try:
                if datetime.now() > datetime.fromisoformat(expiry):
                    return redirect("/renew_page")
            except:
                return redirect("/renew_page")

        return render_template("student_dashboard.html", school=school)

    except Exception as e:
        print("DASHBOARD ERROR:", e)
        return "Internal Server Error ❌", 500


# =====================================
# ➕ ADD STUDENT
# =====================================
@app.route("/add_student", methods=["POST"])
def add_student():
    try:
        sid = session.get("school")

        if not sid:
            return jsonify({"error": "Not logged in"}), 401

        student_id = request.form.get("student_id", "").strip()
        full_name = request.form.get("full_name", "").strip()
        class_name = request.form.get("class_name", "").strip()
        fee = request.form.get("fee", "0").strip()
        district = request.form.get("district", "").strip()
        mother_phone = request.form.get("mother_phone", "").strip()
        student_phone = request.form.get("student_phone", "").strip()
        orphan = request.form.get("orphan", "no").strip()
        previous_school = request.form.get("previous_school", "").strip()
        parent_password = request.form.get("parent_password") or "1234"
        school_name = session.get("school_name")

        if not student_id.isdigit():
            return jsonify({"error": "Student ID must be numbers only ❌"})

        if db.collection("student").document(student_id).get().exists:
            return jsonify({"error": "Student ID already exists ❌"})

        if not re.fullmatch(r"[A-Za-z ]+", full_name):
            return jsonify({"error": "Name must be letters only ❌"})

        if mother_phone and not mother_phone.isdigit():
            return jsonify({"error": "Parent phone must be numbers only ❌"})

        if student_phone and not student_phone.isdigit():
            return jsonify({"error": "Student phone must be numbers only ❌"})

        try:
            fee_value = float(fee)
        except:
            return jsonify({"error": "Fee must be number ❌"})

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
            "school_name": school_name,
            "parent_password": parent_password,
            "status": "unpaid"
        }

        file = request.files.get("photo")
        if file and file.filename != "":
            os.makedirs("static/uploads", exist_ok=True)
            filename = f"{student_id}.jpg"
            file.save(f"static/uploads/{filename}")
            data["photo"] = filename

        db.collection("student").document(student_id).set(data)

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)})


# =====================================
# 📋 GET STUDENTS
# =====================================
@app.route("/get_students")
def get_students():
    try:
        sid = session.get("school")
        docs = db.collection("student").where("school_id", "==", sid).stream()

        students = []
        for d in docs:
            s = d.to_dict()
            if "status" not in s:
                s["status"] = "unpaid"
            students.append(s)

        return jsonify(students)

    except Exception as e:
        return jsonify({"error": str(e)})


# =====================================
# ❌ DELETE STUDENT
# =====================================
@app.route("/delete_student_api", methods=["POST"])
def delete_student_api():
    try:
        db.collection("student").document(
            request.form.get("student_id")
        ).delete()
        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)})

# =====================================
# 👨‍🏫 ADD TEACHER
# =====================================
@app.route("/add_teacher", methods=["POST"])
def add_teacher():

    try:

        sid = session.get("school")

        if not sid:

            return jsonify({
                "error": "Fadlan login soo dheh! ❌"
            }), 401

        full_name = request.form.get(
            "full_name", ""
        ).strip()

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        ).strip()

        phone = request.form.get(
            "phone", ""
        ).strip()

        subject = request.form.get(
            "subject", ""
        ).strip()

        assigned_classes_raw = request.form.get(
            "assigned_classes", "[]"
        )

        classes = json.loads(
            assigned_classes_raw
        )

        # =========================
        # ❌ REQUIRED FIELDS
        # =========================
        if not username or not password or not subject:

            return jsonify({
                "error": "Username, Password iyo Subject waa khasab ❌"
            })

        # =========================
        # 🔍 CHECK EXISTING USER
        # =========================
        existing = db.collection(
            "teachers"
        ).where(
            "username", "==", username
        ).stream()

        for _ in existing:

            return jsonify({
                "error": "Username-kan waa la isticmaalay ❌"
            })

        # =========================
        # 🔐 HASH PASSWORD
        # =========================
        hashed_password = generate_password_hash(
            password
        )

        # =========================
        # 💾 SAVE TEACHER
        # =========================
        db.collection("teachers").add({

            "username": username,

            "password": hashed_password,

            "full_name": full_name,

            "phone": phone,

            "subject": subject,

            "classes": classes,

            "school_id": sid,

            "created_at": get_somali_time()

        })

        return jsonify({
            "success": True
        })

    except Exception as e:

        print("ADD TEACHER ERROR:", e)

        return jsonify({
            "error": str(e)
        })
# =====================================
# ⏱ SUBMIT ATTENDANCE
# =====================================
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

        now = get_somali_time()
        day_name = now.strftime("%A")
        date_full = now.strftime("%d/%B/%Y")
        time_full = now.strftime("%I:%M:%S %p")
        today_key = now.strftime("%Y-%m-%d")

        check = db.collection("attendance_logs") \
            .where("class_name", "==", selected_class) \
            .where("date_key", "==", today_key) \
            .where("school_id", "==", school_id).stream()

        for _ in check:
            return jsonify({"error": "Fasalkan waa la xaadiriyay maanta! ❌"})

        student_map = {}
        docs = db.collection("student") \
            .where("school_id", "==", school_id) \
            .where("class_name", "==", selected_class).stream()

        for d in docs:
            s = d.to_dict()
            student_map[d.id] = s.get("full_name")

        full_attendance = []
        for item in attendance_list:
            full_attendance.append({
                "student_id": item["student_id"],
                "name": student_map.get(item["student_id"], ""),
                "status": item["status"]
            })

        db.collection("attendance_logs").add({
            "school_id": school_id,
            "class_name": selected_class,
            "teacher_name": teacher_name,
            "subject": subject,
            "date": f"{day_name}/{date_full}",
            "time": time_full,
            "date_key": today_key,
            "attendance": full_attendance,
            "timestamp": now,
            "unlock_time": now + timedelta(hours=24)
        })

        return jsonify({"success": True, "message": "Attendance saved successfully ✅"})

    except Exception as e:
        return jsonify({"error": str(e)})


# =====================================
# 📊 ADMIN ATTENDANCE
# =====================================
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
            day = a.get("date")
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
                    "time": a.get("time")
                })

        return render_template("admin_attendance.html", grouped=grouped)

    except Exception as e:
        return f"Attendance Error: {str(e)}"


# =====================================
# 🏫 SCHOOL ADMIN DASHBOARD
# =====================================
@app.route("/admin_dashboard_school")
def admin_dashboard_school():
    try:
        school_id = session.get("school")

        if not school_id:
            return redirect("/school_login")

        school_doc = db.collection("schools").document(school_id).get()
        school_data = school_doc.to_dict() if school_doc.exists else {}

        docs = db.collection("student") \
            .where("school_id", "==", school_id).stream()

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


# =====================================
# 🔐 UPDATE SCHOOL PASSWORDS
# =====================================
@app.route("/update_school_passwords", methods=["POST"])
def update_school_passwords():
    try:
        sid = session.get("school")

        if not sid:
            return jsonify({"success": False, "message": "Session expired"}), 401

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data received"})

        admin_pass = data.get("admin", "").strip()
        teacher_pass = data.get("teacher", "").strip()
        cashier_pass = data.get("cashier", "").strip()

        if not admin_pass:
            return jsonify({"success": False, "message": "Admin password required"})
        if not teacher_pass:
            return jsonify({"success": False, "message": "Teacher password required"})
        if not cashier_pass:
            return jsonify({"success": False, "message": "Cashier password required"})

        school_ref = db.collection("schools").document(sid)
        school_doc = school_ref.get()

        if not school_doc.exists:
            return jsonify({"success": False, "message": "School not found"})

        school_data = school_doc.to_dict()

        school_ref.update({
            "admin_password": admin_pass,
            "teacher_password": teacher_pass,
            "cashier_password": cashier_pass,
            "password_updated_at": get_somali_time()
        })

        db.collection("school_updates").add({
            "school_id": sid,
            "school_name": school_data.get("school_name", ""),
            "old_admin_password": school_data.get("admin_password", ""),
            "old_teacher_password": school_data.get("teacher_password", ""),
            "old_cashier_password": school_data.get("cashier_password", ""),
            "new_admin_password": admin_pass,
            "new_teacher_password": teacher_pass,
            "new_cashier_password": cashier_pass,
            "type": "password_update",
            "updated_by": "school_admin",
            "time": get_somali_time(),
            "timestamp": firestore.SERVER_TIMESTAMP
        })

        return jsonify({"success": True, "message": "Passwords updated successfully ✅"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# =====================================
# 🔍 SEARCH STUDENT
# =====================================
@app.route("/search_student")
def search_student():
    try:
        sid = session.get("school")
        student_id = request.args.get("student_id")

        doc = db.collection("student").document(student_id).get()

        if not doc.exists:
            return jsonify({"error": "Not found"})

        data = doc.to_dict()

        if data.get("school_id") != sid:
            return jsonify({"error": "Unauthorized"})

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)})


# =====================================
# 💳 UPDATE FEE STATUS
# =====================================
@app.route("/update_fee_status", methods=["POST"])
def update_fee_status():
    try:
        student_id = request.form.get("student_id")
        status = request.form.get("status")

        db.collection("student").document(student_id).update({"status": status})
        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)})


# =====================================
# 💰 PAY FEE
# =====================================
@app.route("/pay_fee", methods=["POST"])
def pay_fee():
    try:
        data_incoming = request.get_json()

        student_id = data_incoming.get("student_id")
        amount = data_incoming.get("amount")

        if not student_id or amount is None:
            return jsonify({"success": False, "error": "Missing data ❌"})

        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid amount ❌"})

        ref = db.collection("student").document(student_id)
        doc = ref.get()

        if not doc.exists:
            return jsonify({"success": False, "error": "Student not found ❌"})

        data = doc.to_dict()
        fee = float(data.get("fee", 0))
        old_paid = float(data.get("paid", 0))
        new_paid = old_paid + amount
        remaining = fee - new_paid
        status = "paid" if remaining <= 0 else "unpaid"
        display_remaining = max(0, remaining)
        now = datetime.now().strftime("%d/%m/%Y %H:%M")

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
        print(f"Error: {e}")
        return jsonify({"success": False, "error": str(e)})


# =====================================
# 👨‍👩‍👦 PARENT DATA
# =====================================
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
            "school_name": "Your School",
            "name": s.get("full_name", ""),
            "fee": fee,
            "paid": paid,
            "remaining": remaining,
            "attendance": s.get("attendance", {"present": 0, "absent": 0}),
            "reports": s.get("reports", [])
        })

    except Exception as e:
        print("PARENT ERROR:", e)
        return jsonify({"error": str(e)})


# =====================================
# 🏫 SCHOOL STUDENT REGISTER PAGE
# =====================================
@app.route("/school/student_register")
def school_student_register():
    try:
        if not session.get("school"):
            return redirect("/school_login")
        return render_template("add_student.html")

    except Exception as e:
        return f"Student Register Error: {str(e)}"


# =====================================
# 📊 TEACHER DASHBOARD
# =====================================
@app.route("/teacher_dashboard")
def teacher_dashboard():
    try:
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

        selected_class = request.args.get("class")
        if not selected_class or selected_class not in classes:
            selected_class = classes[0]

        session["selected_class"] = selected_class

        today = get_somali_time().strftime("%Y-%m-%d")

        lock_docs = db.collection("attendance_logs") \
            .where("class_name", "==", selected_class) \
            .where("date", "==", today) \
            .where("school_id", "==", school_id).stream()

        is_locked = False
        lock_data = None

        for d in lock_docs:
            is_locked = True
            lock_data = d.to_dict()

        docs = db.collection("student") \
            .where("school_id", "==", school_id) \
            .where("class_name", "==", selected_class).stream()

        students = []
        for d in docs:
            s = d.to_dict()
            s["student_id"] = d.id
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

@app.route("/receipt/<rid>/<order_id>")
def receipt(rid, order_id):
    try:
        order_ref = db.collection("restaurants").document(rid)\
                      .collection("orders").document(order_id)
        order_doc = order_ref.get()

        if not order_doc.exists:
            return "<h2 style='text-align:center;margin-top:100px;font-family:Arial'>❌ Receipt not found</h2>", 404

        order = order_doc.to_dict()
        rest_doc = db.collection("restaurants").document(rid).get()
        rest = rest_doc.to_dict() if rest_doc.exists else {}

        cart = order.get("cart", [])
        subtotal = float(order.get("price", 0))
        vat = round(subtotal * 0.05, 2)
        total = round(subtotal + vat, 2)

        items = []
        for i in cart:
            qty   = int(i.get("qty", 1))
            price = float(i.get("price", 0))
            items.append({
                "food":  i.get("name", "Item"),
                "qty":   qty,
                "price": price,
                "total": round(qty * price, 2)
            })

        # ✅ Somalia time (UTC+3)
        created_raw = order.get("created_at")
        try:
            created_at = created_raw.astimezone(ZoneInfo("Africa/Mogadishu"))
        except:
            created_at = created_raw

        return render_template(
            "receipt.html",
            rid             = rid,
            order_id        = order_id,
            restaurant_name = rest.get("name", "Restaurant"),
            phone           = rest.get("phone", ""),
            payment         = rest.get("payment", ""),
            table           = order.get("table", ""),
            ref             = order_id[:8].upper(),
            items           = items,
            subtotal        = subtotal,
            vat             = vat,
            total           = total,
            created_at      = created_at
        )

    except Exception as e:
        print("Receipt Error:", e)
        return f"Receipt Error ❌ {str(e)}"

@app.route("/dashboard_receipts/<rid>")
def dashboard_receipts(rid):
    try:
        if not session.get("restaurant_login"):
            return redirect("/login")

        order_docs = db.collection("restaurants").document(rid)\
                       .collection("orders")\
                       .order_by("created_at", direction=firestore.Query.DESCENDING)\
                       .stream()

        orders = []
        count = 1
        for doc in order_docs:
            o = doc.to_dict()
            if o.get("kitchen_cleared"):
                continue

            # ✅ FIX: items text u beddel
            items_raw = o.get("items", "")
            if isinstance(items_raw, list):
                items_text = ", ".join(items_raw)
            elif isinstance(items_raw, str):
                items_text = items_raw
            else:
                items_text = ""

            orders.append({
                "order_num":  count,
                "order_id":   doc.id,
                "table":      o.get("table", "?"),
                "items_text": items_text,   # ✅ string
                "price":      o.get("price", 0),
                "status":     o.get("status", "pending"),
                "created_at": o.get("created_at")
            })
            count += 1

        rest_doc = db.collection("restaurants").document(rid).get()
        rest = rest_doc.to_dict() if rest_doc.exists else {}

        return render_template(
            "dashboard_receipts.html",
            orders=orders,
            rid=rid,
            restaurant=rest.get("name", "Restaurant")
        )

    except Exception as e:
        return f"Receipt List Error ❌ {str(e)}"

@app.route("/receipt_view/<rid>/<table>")
def receipt_view(rid, table):
    try:
        order_docs = db.collection("restaurants").document(rid)\
                       .collection("orders")\
                       .order_by("created_at", direction=firestore.Query.DESCENDING)\
                       .stream()

        for doc in order_docs:
            o = doc.to_dict()
            if not o.get("kitchen_cleared"):
                order_id = doc.id
                cart = o.get("cart", [])
                subtotal = float(o.get("price", 0))
                vat = round(subtotal * 0.05, 2)
                total = round(subtotal + vat, 2)

                items = []
                for i in cart:
                    qty = int(i.get("qty", 1))
                    price = float(i.get("price", 0))
                    items.append({
                        "food": i.get("name", "Item"),
                        "qty": qty,
                        "price": price,
                        "total": round(qty * price, 2)
                    })

                rest_doc = db.collection("restaurants").document(rid).get()
                rest = rest_doc.to_dict() if rest_doc.exists else {}

                return render_template(
                    "receipt.html",
                    rid=rid,
                    order_id=order_id,
                    restaurant_name=rest.get("name", "Restaurant"),
                    phone=rest.get("phone", ""),
                    payment=rest.get("payment", ""),
                    table=o.get("table", table),
                    ref=order_id[:8].upper(),
                    items=items,
                    subtotal=subtotal,
                    vat=vat,
                    total=total,
                    created_at=o.get("created_at")
                )

        return "<h2 style='font-family:monospace;text-align:center;margin-top:100px'>📭 No orders found</h2>"

    except Exception as e:
        return f"Error ❌ {str(e)}"

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
# 📢 PUBLIC INFO PAGE (READ ONLY)
# ==========================================
@app.route("/info")
def show_info():

    try:

        return render_template("info_public.html")

    except Exception as e:

        print("INFO PAGE ERROR:", e)

        return f"Info Page Error ❌ {str(e)}"


# ==========================================
# 📢 ADMIN INFO PAGE
# ==========================================
@app.route("/admin_info")
def admin_info():

    try:

        return render_template("info.html")

    except Exception as e:

        print("ADMIN INFO ERROR:", e)

        return f"Admin Info Error ❌ {str(e)}"


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

        # ✅ SORT BY POSITION
        all_info.sort(
            key=lambda x: x.get("position", 0)
        )

        # ✅ RETURN JSON
        return jsonify({
            "success": True,
            "data": all_info
        })

    except Exception as e:

        print("GET INFO ERROR:", e)

        return jsonify({
            "success": False,
            "error": str(e)
        })


# ==========================================
# 🗑 DELETE INFO (ADMIN ONLY)
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
# 🔥 UPDATE POSITIONS (ADMIN ONLY)
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

        return redirect("/admin_info")

    except Exception as e:

        return str(e)

@app.route("/dashboard_login", methods=["POST"])
def dashboard_login():
    try:
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        docs = dhibic_db.collection("dashboard_users") \
                        .where("email", "==", email).limit(1).get()

        if len(docs) == 0:
            return jsonify({"success": False, "error": "Email not found"})

        user_data   = docs[0].to_dict()
        db_password = str(user_data.get("password", "")).strip()

        if db_password != password:
            return jsonify({"success": False, "error": "Wrong password"})

        session["dashboard_user"] = email
        return jsonify({"success": True, "redirect": "/view-orders"})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ==============================
# VIEW ORDERS PAGE
# ==============================
@app.route("/view-orders")
def view_orders():
    if "dashboard_user" not in session:
        return redirect("/")

    def fmt_ts(ts):
        try:
            return ts.strftime("%Y-%m-%d %H:%M") if ts else ""
        except:
            return str(ts) if ts else ""

    try:
        # ── data_orders ──
        do_docs = dhibic_db.collection("data_orders") \
            .order_by("createdAt", direction=firestore.Query.DESCENDING) \
            .limit(200).get()

        data_orders = []
        for doc in do_docs:
            d = doc.to_dict()
            data_orders.append({
                "docId":         doc.id,
                "referenceId":   d.get("referenceId", ""),
                "senderPhone":   d.get("senderPhone", ""),
                "receiverPhone": d.get("receiverPhone", ""),
                "packageName":   d.get("packageName", ""),
                "packageData":   d.get("packageData", ""),
                "description":   d.get("description", ""),
                "amount":        d.get("amount", "0"),
                "status":        d.get("status", "PENDING"),
                "createdAt":     fmt_ts(d.get("createdAt")),
            })

        # ── orders ──
        or_docs = dhibic_db.collection("orders") \
            .order_by("createdAt", direction=firestore.Query.DESCENDING) \
            .limit(200).get()

        orders = []
        for doc in or_docs:
            d = doc.to_dict()
            orders.append({
                "docId":        doc.id,
                "orderId":      d.get("orderId", ""),
                "customerId":   d.get("customerId", ""),
                "address":      d.get("address", ""),
                "merchantId":   d.get("merchantId", ""),
                "merchantName": d.get("merchantName", ""),
                "merchantPhone":d.get("merchantPhone", ""),
                "deliveryType": d.get("deliveryType", ""),
                "price":        d.get("price", d.get("amount", "0")),
                "status":       d.get("status", "PENDING"),
                "createdAt":    fmt_ts(d.get("createdAt")),
            })

        # ── exchange_orders ──
        ex_docs = dhibic_db.collection("exchange_orders") \
            .order_by("createdAt", direction=firestore.Query.DESCENDING) \
            .limit(200).get()

        exchange_orders = []
        for doc in ex_docs:
            d = doc.to_dict()
            exchange_orders.append({
                "docId":         doc.id,
                "senderNumber":  d.get("senderNumber", ""),
                "receiverNumber":d.get("receiverNumber", ""),
                "fromCompany":   d.get("fromCompany", ""),
                "toCompany":     d.get("toCompany", ""),
                "amount":        d.get("amount", "0"),
                "finalAmount":   d.get("finalAmount", "0"),
                "customerEmail": d.get("customerEmail", ""),
                "status":        d.get("status", "PENDING"),
                "createdAt":     fmt_ts(d.get("createdAt")),
                "approvedAt":    fmt_ts(d.get("approvedAt")),
            })

        return render_template(
            "view_orders.html",
            data_orders=data_orders,
            orders=orders,
            exchange_orders=exchange_orders,
        )

    except Exception as e:
        import traceback; traceback.print_exc()
        return f"Error: {str(e)}", 500


# ==============================
# APPROVE ORDER  (3 collection)
# ==============================
@app.route("/approve-order/<collection>/<doc_id>", methods=["POST"])
def approve_order(collection, doc_id):
    if "dashboard_user" not in session:
        return jsonify({"success": False, "error": "Not logged in"})

    allowed = {"data_orders", "orders", "exchange_orders"}
    if collection not in allowed:
        return jsonify({"success": False, "error": "Invalid collection"})

    try:
        status_val = "approved" if collection == "exchange_orders" else "APPROVED"
        dhibic_db.collection(collection).document(doc_id).update({
            "status": status_val
        })
        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ═══════════════════════════════════════════════════════════════
#  WebSocket Signalling Routes — WebRTC Call (Customer ↔ Kitchen)
#  
#  INSTALL: pip install flask-sock
#  
#  APP INIT (add near top of app.py, after app = Flask(__name__)):
#      from flask_sock import Sock
#      sock = Sock(app)
#
#  Then paste the code below into app.py
# ═══════════════════════════════════════════════════════════════

from flask_sock import Sock
import json
import threading

sock = Sock(app)   # <-- haddaad horey u sameysay sock = Sock(app) meel kale, line-kan tuur

# ── In-memory registry: active WebSocket connections ──────────
# { rid: { table: ws_customer_conn } }
_customer_sockets = {}

# { rid: set of kitchen ws connections }
_kitchen_sockets  = {}

_lock = threading.Lock()


# ══════════════════════════════════════════════════════════════
#  Customer WebSocket  →  /ws/call/<rid>/<table>
#  Customer side ku xidaa halkan; offer/ICE diraa, answer helaa
# ══════════════════════════════════════════════════════════════
@sock.route('/ws/call/<rid>/<table>')
def ws_call_customer(ws, rid, table):
    """Customer browser ku xidaa — WebRTC offer diraa kitchen-ka."""

    with _lock:
        if rid not in _customer_sockets:
            _customer_sockets[rid] = {}
        _customer_sockets[rid][table] = ws

    try:
        while True:
            raw = ws.receive()          # block until message
            if raw is None:
                break

            data = json.loads(raw)
            msg_type = data.get("type")

            # ── Forward offer → all kitchen connections for this rid
            if msg_type == "offer":
                data["table"] = table   # kitchen-ka yaqaan table number
                payload = json.dumps(data)
                with _lock:
                    dead = set()
                    for kws in _kitchen_sockets.get(rid, set()):
                        try:
                            kws.send(payload)
                        except Exception:
                            dead.add(kws)
                    for d in dead:
                        _kitchen_sockets.get(rid, set()).discard(d)

            # ── Forward ICE candidate → kitchen
            elif msg_type == "ice":
                data["table"] = table
                payload = json.dumps(data)
                with _lock:
                    dead = set()
                    for kws in _kitchen_sockets.get(rid, set()):
                        try:
                            kws.send(payload)
                        except Exception:
                            dead.add(kws)
                    for d in dead:
                        _kitchen_sockets.get(rid, set()).discard(d)

            # ── End call → notify kitchen
            elif msg_type == "end":
                data["table"] = table
                payload = json.dumps(data)
                with _lock:
                    dead = set()
                    for kws in _kitchen_sockets.get(rid, set()):
                        try:
                            kws.send(payload)
                        except Exception:
                            dead.add(kws)
                    for d in dead:
                        _kitchen_sockets.get(rid, set()).discard(d)

    except Exception:
        pass

    finally:
        with _lock:
            if rid in _customer_sockets:
                _customer_sockets[rid].pop(table, None)

# ==========================================
# 💊 PHARMACY ROUTES
# ==========================================
# SIDA LOO ISTICMAALO:
# Ku copy-garee routes-yadan app.py gudahiisa
# ama ku dar fasalka hoose:
#   from pharmacy_routes import *
# ==========================================

import sqlite3
import os
from datetime import datetime, timedelta
from flask import render_template, request, redirect, jsonify, session
from firebase_admin import firestore

DB_PATH = os.environ.get("DB_PATH", "database.db")

# ==========================================
# 🗄️ INIT PHARMACY DATABASE
# ==========================================

def init_pharmacy_db():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    # PHARMACY USERS
    c.execute("""
    CREATE TABLE IF NOT EXISTS pharmacy_users (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        username  TEXT UNIQUE,
        password  TEXT,
        role      TEXT DEFAULT 'pharmacist'
    )
    """)

    # MEDICINES TABLE
    c.execute("""
    CREATE TABLE IF NOT EXISTS medicines (
        medicine_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT NOT NULL,
        barcode        TEXT UNIQUE,
        cost_price     REAL    DEFAULT 0,
        selling_price  REAL    DEFAULT 0,
        stock_quantity INTEGER DEFAULT 0,
        expiry_date    TEXT,
        category       TEXT    DEFAULT 'General',
        created_at     TEXT    DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # SALES TABLE
    c.execute("""
    CREATE TABLE IF NOT EXISTS pharmacy_sales (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        medicine_id    INTEGER,
        medicine_name  TEXT,
        barcode        TEXT,
        quantity_sold  INTEGER,
        cost_price     REAL,
        selling_price  REAL,
        profit         REAL,
        sale_date      TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()
    print("PHARMACY DB READY ✅")


# ==========================================
# WAXAAD KU DARSATID app.py FASALKA:
# init_pharmacy_db()   ← ku dar init_db() xigta
# ==========================================


# ==========================================
# 🔐 PHARMACY LOGIN
# ==========================================

def pharmacy_login_route():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("SELECT * FROM pharmacy_users WHERE username=? AND password=?",
                  (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session["pharmacy_ok"] = True
            session["pharmacy_user"] = username
            return redirect("/pharmacy")

        return render_template("pharmacy_login.html", error="Wrong username or password ❌")

    return render_template("pharmacy_login.html")


# ==========================================
# 🏠 PHARMACY DASHBOARD
# ==========================================

def pharmacy_dashboard_route():
    if not session.get("pharmacy_ok"):
        return redirect("/pharmacy_login")

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    # ALL MEDICINES
    c.execute("SELECT * FROM medicines ORDER BY name ASC")
    medicines = c.fetchall()

    # TODAY STATS
    today = datetime.now().strftime("%Y-%m-%d")

    c.execute("""
        SELECT
            COUNT(*),
            SUM(quantity_sold),
            SUM(profit)
        FROM pharmacy_sales
        WHERE date(sale_date) = ?
    """, (today,))
    today_row    = c.fetchone()
    today_sales  = today_row[0] or 0
    today_qty    = today_row[1] or 0
    today_profit = round(today_row[2] or 0, 2)

    # EXPIRY ALERT — daawooyinka 90 maalmood gudahood dhacaya
    alert_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
    today_str   = datetime.now().strftime("%Y-%m-%d")

    c.execute("""
        SELECT * FROM medicines
        WHERE expiry_date <= ? AND expiry_date >= ?
        ORDER BY expiry_date ASC
    """, (alert_date, today_str))
    expiry_alerts = c.fetchall()

    # EXPIRED ALREADY
    c.execute("""
        SELECT * FROM medicines
        WHERE expiry_date < ?
        ORDER BY expiry_date ASC
    """, (today_str,))
    expired = c.fetchall()

    # LOW STOCK — 10 iyo ka hooseeya
    c.execute("""
        SELECT * FROM medicines
        WHERE stock_quantity <= 10
        ORDER BY stock_quantity ASC
    """)
    low_stock = c.fetchall()

    # TOP SELLING TODAY
    c.execute("""
        SELECT medicine_name, SUM(quantity_sold) as total
        FROM pharmacy_sales
        WHERE date(sale_date) = ?
        GROUP BY medicine_name
        ORDER BY total DESC
        LIMIT 5
    """, (today,))
    top_selling = c.fetchall()

    conn.close()

    return render_template(
        "pharmacy.html",
        medicines     = medicines,
        today_sales   = today_sales,
        today_qty     = today_qty,
        today_profit  = today_profit,
        expiry_alerts = expiry_alerts,
        expired       = expired,
        low_stock     = low_stock,
        top_selling   = top_selling
    )


# ==========================================
# ➕ ADD MEDICINE
# ==========================================

def add_medicine_route():
    if not session.get("pharmacy_ok"):
        return jsonify({"success": False, "error": "Not logged in"}), 401

    try:
        name          = request.form.get("name", "").strip()
        barcode       = request.form.get("barcode", "").strip()
        cost_price    = float(request.form.get("cost_price", 0))
        selling_price = float(request.form.get("selling_price", 0))
        stock_qty     = int(request.form.get("stock_quantity", 0))
        expiry_date   = request.form.get("expiry_date", "").strip()
        category      = request.form.get("category", "General").strip()

        if not name:
            return jsonify({"success": False, "error": "Medicine name required ❌"})

        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()

        c.execute("""
            INSERT INTO medicines
            (name, barcode, cost_price, selling_price, stock_quantity, expiry_date, category)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, barcode, cost_price, selling_price, stock_qty, expiry_date, category))

        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "Medicine added ✅"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# 🔍 SEARCH MEDICINE (AJAX / BARCODE)
# ==========================================

def search_medicine_route():
    if not session.get("pharmacy_ok"):
        return jsonify({"error": "Not logged in"}), 401

    query = request.args.get("q", "").strip()

    if not query:
        return jsonify([])

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    c.execute("""
        SELECT medicine_id, name, barcode, selling_price,
               stock_quantity, expiry_date, category
        FROM medicines
        WHERE name LIKE ? OR barcode = ?
        LIMIT 20
    """, (f"%{query}%", query))

    rows    = c.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "medicine_id":    r[0],
            "name":           r[1],
            "barcode":        r[2],
            "selling_price":  r[3],
            "stock_quantity": r[4],
            "expiry_date":    r[5],
            "category":       r[6]
        })

    return jsonify(results)


# ==========================================
# 🛒 SELL MEDICINE (CART CHECKOUT)
# ==========================================

def sell_medicine_route():
    if not session.get("pharmacy_ok"):
        return jsonify({"success": False, "error": "Not logged in"}), 401

    try:
        data = request.get_json()
        cart = data.get("cart", [])

        if not cart:
            return jsonify({"success": False, "error": "Cart is empty ❌"})

        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()

        total_profit = 0

        for item in cart:
            med_id   = item.get("medicine_id")
            qty      = int(item.get("quantity", 1))

            # Get medicine info
            c.execute("SELECT name, barcode, cost_price, selling_price, stock_quantity FROM medicines WHERE medicine_id=?",
                      (med_id,))
            med = c.fetchone()

            if not med:
                conn.close()
                return jsonify({"success": False, "error": f"Medicine ID {med_id} not found ❌"})

            name          = med[0]
            barcode       = med[1]
            cost_price    = med[2]
            selling_price = med[3]
            stock         = med[4]

            # CHECK STOCK
            if qty > stock:
                conn.close()
                return jsonify({
                    "success": False,
                    "error":   f"Not enough stock for {name}. Available: {stock} ❌"
                })

            profit = (selling_price - cost_price) * qty
            total_profit += profit

            # RECORD SALE
            c.execute("""
                INSERT INTO pharmacy_sales
                (medicine_id, medicine_name, barcode, quantity_sold,
                 cost_price, selling_price, profit, sale_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (med_id, name, barcode, qty, cost_price, selling_price,
                  profit, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

            # REDUCE STOCK
            c.execute("""
                UPDATE medicines
                SET stock_quantity = stock_quantity - ?
                WHERE medicine_id = ?
            """, (qty, med_id))

        conn.commit()
        conn.close()

        return jsonify({
            "success":      True,
            "message":      "Sale recorded ✅",
            "total_profit": round(total_profit, 2)
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# 📊 PROFIT & LOSS REPORT
# ==========================================

def pharmacy_report_route():
    if not session.get("pharmacy_ok"):
        return jsonify({"error": "Not logged in"}), 401

    try:
        date_from = request.args.get("from", datetime.now().strftime("%Y-%m-%d"))
        date_to   = request.args.get("to",   datetime.now().strftime("%Y-%m-%d"))

        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()

        # TOTAL SALES + PROFIT
        c.execute("""
            SELECT
                COUNT(*),
                SUM(quantity_sold),
                SUM(selling_price * quantity_sold),
                SUM(cost_price    * quantity_sold),
                SUM(profit)
            FROM pharmacy_sales
            WHERE date(sale_date) BETWEEN ? AND ?
        """, (date_from, date_to))
        row = c.fetchone()

        total_transactions = row[0] or 0
        total_qty          = row[1] or 0
        total_revenue      = round(row[2] or 0, 2)
        total_cost         = round(row[3] or 0, 2)
        net_profit         = round(row[4] or 0, 2)

        # TOP 5 SELLING
        c.execute("""
            SELECT medicine_name, SUM(quantity_sold) as qty, SUM(profit) as profit
            FROM pharmacy_sales
            WHERE date(sale_date) BETWEEN ? AND ?
            GROUP BY medicine_name
            ORDER BY qty DESC
            LIMIT 5
        """, (date_from, date_to))
        top_medicines = [{"name": r[0], "qty": r[1], "profit": round(r[2], 2)}
                         for r in c.fetchall()]

        # DAILY BREAKDOWN
        c.execute("""
            SELECT
                date(sale_date),
                COUNT(*),
                SUM(quantity_sold),
                SUM(profit)
            FROM pharmacy_sales
            WHERE date(sale_date) BETWEEN ? AND ?
            GROUP BY date(sale_date)
            ORDER BY date(sale_date) DESC
        """, (date_from, date_to))
        daily = [{"date": r[0], "transactions": r[1], "qty": r[2], "profit": round(r[3], 2)}
                 for r in c.fetchall()]

        conn.close()

        return jsonify({
            "from":               date_from,
            "to":                 date_to,
            "total_transactions": total_transactions,
            "total_qty":          total_qty,
            "total_revenue":      total_revenue,
            "total_cost":         total_cost,
            "net_profit":         net_profit,
            "top_medicines":      top_medicines,
            "daily":              daily
        })

    except Exception as e:
        return jsonify({"error": str(e)})


# ==========================================
# 🗑 DELETE MEDICINE
# ==========================================

def delete_medicine_route(med_id):
    if not session.get("pharmacy_ok"):
        return jsonify({"success": False, "error": "Not logged in"}), 401
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("DELETE FROM medicines WHERE medicine_id=?", (med_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# ✏️ EDIT MEDICINE
# ==========================================

def edit_medicine_route(med_id):
    if not session.get("pharmacy_ok"):
        return jsonify({"success": False, "error": "Not logged in"}), 401
    try:
        data          = request.get_json()
        name          = data.get("name", "")
        barcode       = data.get("barcode", "")
        cost_price    = float(data.get("cost_price", 0))
        selling_price = float(data.get("selling_price", 0))
        stock_qty     = int(data.get("stock_quantity", 0))
        expiry_date   = data.get("expiry_date", "")
        category      = data.get("category", "General")

        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("""
            UPDATE medicines
            SET name=?, barcode=?, cost_price=?, selling_price=?,
                stock_quantity=?, expiry_date=?, category=?
            WHERE medicine_id=?
        """, (name, barcode, cost_price, selling_price, stock_qty, expiry_date, category, med_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Updated ✅"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# 📋 GET ALL MEDICINES (JSON)
# ==========================================

def get_medicines_route():
    if not session.get("pharmacy_ok"):
        return jsonify({"error": "Not logged in"}), 401
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("SELECT * FROM medicines ORDER BY name ASC")
        rows = c.fetchall()
        conn.close()
        medicines = []
        for r in rows:
            medicines.append({
                "medicine_id":    r[0],
                "name":           r[1],
                "barcode":        r[2],
                "cost_price":     r[3],
                "selling_price":  r[4],
                "stock_quantity": r[5],
                "expiry_date":    r[6],
                "category":       r[7],
                "created_at":     r[8]
            })
        return jsonify(medicines)
    except Exception as e:
        return jsonify({"error": str(e)})


# ==========================================
# 🚨 EXPIRY + LOW STOCK ALERTS (JSON)
# ==========================================

def pharmacy_alerts_route():
    if not session.get("pharmacy_ok"):
        return jsonify({"error": "Not logged in"}), 401
    try:
        today      = datetime.now().strftime("%Y-%m-%d")
        alert_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()

        # EXPIRING SOON
        c.execute("""
            SELECT medicine_id, name, stock_quantity, expiry_date
            FROM medicines
            WHERE expiry_date <= ? AND expiry_date >= ?
            ORDER BY expiry_date ASC
        """, (alert_date, today))
        expiring = [{"medicine_id": r[0], "name": r[1], "stock": r[2], "expiry": r[3]}
                    for r in c.fetchall()]

        # ALREADY EXPIRED
        c.execute("""
            SELECT medicine_id, name, stock_quantity, expiry_date
            FROM medicines
            WHERE expiry_date < ?
            ORDER BY expiry_date ASC
        """, (today,))
        expired = [{"medicine_id": r[0], "name": r[1], "stock": r[2], "expiry": r[3]}
                   for r in c.fetchall()]

        # LOW STOCK
        c.execute("""
            SELECT medicine_id, name, stock_quantity, expiry_date
            FROM medicines
            WHERE stock_quantity <= 10
            ORDER BY stock_quantity ASC
        """)
        low_stock = [{"medicine_id": r[0], "name": r[1], "stock": r[2], "expiry": r[3]}
                     for r in c.fetchall()]

        conn.close()

        return jsonify({
            "expiring_soon": expiring,
            "expired":       expired,
            "low_stock":     low_stock,
            "total_alerts":  len(expiring) + len(expired) + len(low_stock)
        })
    except Exception as e:
        return jsonify({"error": str(e)})


# ==========================================
# 👤 CREATE PHARMACY USER (ADMIN ONLY)
# ==========================================

def create_pharmacy_user_route():
    if not session.get("admin_ok"):
        return jsonify({"success": False, "error": "Admin only"}), 401
    try:
        data     = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        if not username or not password:
            return jsonify({"success": False, "error": "Fill all fields"})
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("INSERT INTO pharmacy_users (username, password) VALUES (?, ?)",
                  (username, password))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Pharmacy user created ✅"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# 🚪 LOGOUT PHARMACY
# ==========================================

def pharmacy_logout_route():
    session.pop("pharmacy_ok", None)
    session.pop("pharmacy_user", None)
    return redirect("/pharmacy_login")


# ==========================================
# 📌 ROUTES LIST — KU DAR app.py FASALKA:
# ==========================================
#
# app.route("/pharmacy_login", methods=["GET","POST"])(pharmacy_login_route)
# app.route("/pharmacy")(pharmacy_dashboard_route)
# app.route("/pharmacy/add_medicine", methods=["POST"])(add_medicine_route)
# app.route("/pharmacy/search")(search_medicine_route)
# app.route("/pharmacy/sell", methods=["POST"])(sell_medicine_route)
# app.route("/pharmacy/report")(pharmacy_report_route)
# app.route("/pharmacy/delete/<int:med_id>", methods=["DELETE"])(delete_medicine_route)
# app.route("/pharmacy/edit/<int:med_id>", methods=["PUT"])(edit_medicine_route)
# app.route("/pharmacy/medicines")(get_medicines_route)
# app.route("/pharmacy/alerts")(pharmacy_alerts_route)
# app.route("/pharmacy/create_user", methods=["POST"])(create_pharmacy_user_route)
# app.route("/pharmacy/logout")(pharmacy_logout_route)
#
# ==========================================

# ==========================================
# 💊 PHARMACY — KU DAR APP.PY FASALKA
# ==========================================
# 1. Ku copy-garee functions-yada pharmacy_routes.py
#    ama ku dar fasalka hoose app.py:
#
#    from pharmacy_routes import (
#        init_pharmacy_db,
#        pharmacy_login_route,
#        pharmacy_dashboard_route,
#        add_medicine_route,
#        search_medicine_route,
#        sell_medicine_route,
#        pharmacy_report_route,
#        delete_medicine_route,
#        edit_medicine_route,
#        get_medicines_route,
#        pharmacy_alerts_route,
#        create_pharmacy_user_route,
#        pharmacy_logout_route
#    )
#
# 2. Ku dar init_db() xigta:
#    init_pharmacy_db()
#
# 3. Ku dar routes-yada hoose app.py gudahiisa
# ==========================================

# ============================================================
# COPY ROUTES-YADAN AH DIRECTLY APP.PY GUDAHIISA
# ============================================================

from datetime import datetime, timedelta

# ---- INIT (ku dar init_db() xigta) ----
# init_pharmacy_db()


@app.route("/pharmacy_login", methods=["GET", "POST"])
def pharmacy_login():
    return pharmacy_login_route()


@app.route("/pharmacy")
def pharmacy():
    return pharmacy_dashboard_route()


@app.route("/pharmacy/add_medicine", methods=["POST"])
def add_medicine():
    return add_medicine_route()


@app.route("/pharmacy/search")
def search_medicine():
    return search_medicine_route()


@app.route("/pharmacy/sell", methods=["POST"])
def sell_medicine():
    return sell_medicine_route()


@app.route("/pharmacy/report")
def pharmacy_report():
    return pharmacy_report_route()


@app.route("/pharmacy/delete/<int:med_id>", methods=["DELETE"])
def delete_medicine(med_id):
    return delete_medicine_route(med_id)


@app.route("/pharmacy/edit/<int:med_id>", methods=["PUT"])
def edit_medicine(med_id):
    return edit_medicine_route(med_id)


@app.route("/pharmacy/medicines")
def get_medicines():
    return get_medicines_route()


@app.route("/pharmacy/alerts")
def pharmacy_alerts():
    return pharmacy_alerts_route()


@app.route("/pharmacy/create_user", methods=["POST"])
def create_pharmacy_user():
    return create_pharmacy_user_route()


@app.route("/pharmacy/logout")
def pharmacy_logout():
    return pharmacy_logout_route()


# ============================================================
# PHARMACY — TEMPLATE VARIABLES FIX
# ============================================================
# Pharmacy dashboard-ka wuxuu u baahan yahay laba variable oo
# Jinja2 template-ka ku jira (now_date iyo expiry_warn).
# Ku beddel pharmacy_dashboard_route() function-ka fasalka:
#
#    from datetime import datetime, timedelta
#
#    return render_template(
#        "pharmacy.html",
#        medicines     = medicines,
#        today_sales   = today_sales,
#        today_qty     = today_qty,
#        today_profit  = today_profit,
#        expiry_alerts = expiry_alerts,
#        expired       = expired,
#        low_stock     = low_stock,
#        top_selling   = top_selling,
#        today         = datetime.now().strftime("%Y-%m-%d"),
#        now_date      = datetime.now().strftime("%Y-%m-%d"),
#        expiry_warn   = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
#    )
# ============================================================


# ============================================================
# FIRESTORE — CREATE PHARMACY USER FROM ADMIN PANEL
# ============================================================
# Admin-ka wuxuu username iyo password ku abuuri karaa Firestore:
#
# @app.route("/admin/create_pharmacy_user", methods=["POST"])
# def admin_create_pharmacy_user():
#     if not session.get("admin_ok"):
#         return jsonify({"success": False, "error": "Unauthorized"}), 401
#     try:
#         data     = request.get_json()
#         username = data.get("username", "").strip()
#         password = data.get("password", "").strip()
#         if not username or not password:
#             return jsonify({"success": False, "error": "Fill all fields"})
#         # SQLite ku kaydi
#         conn = sqlite3.connect(DB_PATH)
#         c    = conn.cursor()
#         c.execute("INSERT INTO pharmacy_users (username, password) VALUES (?, ?)",
#                   (username, password))
#         conn.commit()
#         conn.close()
#         # Firestore-na ku kaydi
#         db.collection("pharmacy_users").document(username).set({
#             "username":    username,
#             "password":    password,
#             "created_at":  datetime.now().isoformat()
#         })
#         return jsonify({"success": True, "message": "User created ✅"})
#     except Exception as e:
#         return jsonify({"success": False, "error": str(e)})
# ============================================================

# ══════════════════════════════════════════════════════════════
#  Kitchen WebSocket  →  /ws/kitchen/<rid>
#  Kitchen browser ku xidaa; incoming offer helaa, answer diraa
# ══════════════════════════════════════════════════════════════
@sock.route('/ws/kitchen/<rid>')
def ws_call_kitchen(ws, rid):
    """Kitchen browser ku xidaa — incoming calls helaa, answer diraysa."""

    with _lock:
        if rid not in _kitchen_sockets:
            _kitchen_sockets[rid] = set()
        _kitchen_sockets[rid].add(ws)

    try:
        while True:
            raw = ws.receive()          # block until message
            if raw is None:
                break

            data = json.loads(raw)
            msg_type = data.get("type")
            table    = data.get("table", "")

            # ── Forward answer → specific customer
            if msg_type == "answer":
                with _lock:
                    cws = _customer_sockets.get(rid, {}).get(table)
                if cws:
                    try:
                        cws.send(json.dumps(data))
                    except Exception:
                        pass

            # ── Forward ICE → specific customer
            elif msg_type == "ice":
                with _lock:
                    cws = _customer_sockets.get(rid, {}).get(table)
                if cws:
                    try:
                        cws.send(json.dumps(data))
                    except Exception:
                        pass

            # ── End call → notify customer
            elif msg_type == "end":
                with _lock:
                    cws = _customer_sockets.get(rid, {}).get(table)
                if cws:
                    try:
                        cws.send(json.dumps(data))
                    except Exception:
                        pass

    except Exception:
        pass

    finally:
        with _lock:
            if rid in _kitchen_sockets:
                _kitchen_sockets[rid].discard(ws)    
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))

    init_db()

    socketio.run(
        app,
        host="0.0.0.0",
        port=port
    )
