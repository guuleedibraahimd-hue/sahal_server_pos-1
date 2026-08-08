from flask import (
    Flask,
    render_template,
    request,
    redirect,
    jsonify,
    session,
    url_for,
    flash,
    send_from_directory
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
import time

from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone

import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/sw.js')
def serve_sw():
    return send_from_directory('static', 'sw.js')

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
# polling keliya — Railway WebSocket proxy dhibaato buu leeyahay
# =========================

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    allow_upgrades=False,
    transports=["polling"]
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
            "register_password": "6993"
        }

    except Exception as e:
        print("Firebase password error:", e)
        return {
            "admin_password": "6993",
            "register_password": "6993"
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
            entered   = request.form.get("password", "").strip()

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
        restaurants  = get_restaurants_firestore()
        supermarkets = get_supermarkets_firestore()
        orders       = get_orders_firestore()
        total        = len(orders)

        info_docs = db.collection("system_info").stream()
        all_info  = []

        for doc in info_docs:
            data = doc.to_dict()
            all_info.append({
                "id":       doc.id,
                "title":    data.get("title", ""),
                "content":  data.get("content", ""),
                "image":    data.get("image", ""),
                "video":    data.get("video", ""),
                "date":     str(data.get("date", "")),
                "position": data.get("position", 0)
            })

        all_info.sort(key=lambda x: x.get("position", 0))

        review_docs      = db.collection("reviews").stream()
        review_count_map = {}

        for doc in review_docs:
            item = doc.to_dict()
            rid  = item.get("restaurant_id")
            if rid:
                review_count_map[rid] = review_count_map.get(rid, 0) + 1

        for r in restaurants:
            rid              = r.get("id")
            r["review_count"]= review_count_map.get(rid, 0)

        top_reviews = sorted(
            restaurants,
            key=lambda x: x.get("review_count", 0),
            reverse=True
        )[:3]

        return render_template(
            "admin.html",
            restaurants=restaurants,
            supermarkets=supermarkets,
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
    session.pop("admin_ok",      None)
    session.pop("register_ok",   None)
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

        data          = request.get_json()
        admin_pass    = data.get("admin_password")
        register_pass = data.get("register_password")

        if not admin_pass or not register_pass:
            return jsonify({"success": False, "message": "Fill all fields"})

        db.collection("system_passwords").document("main").set({
            "admin_password":    admin_pass,
            "register_password": register_pass
        })

        return jsonify({"success": True, "message": "Passwords updated successfully ✅"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/change_passwords", methods=["POST"])
def change_passwords():
    new_admin    = request.form.get("admin_pass")
    new_register = request.form.get("register_pass")

    conn = sqlite3.connect("database.db")
    c    = conn.cursor()

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
            "active":       True,
            "status":       "active",
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
            "active":      False,
            "status":      "disabled",
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
# 🛒 SUPERMARKET FUNCTIONS
# =========================

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


# ==========================================
# 🛒 SUPERMARKET — ROUTES
# ==========================================

import string

# ==========================================
# 🗄️ INIT SUPERMARKET SALES TABLE (SQLite)
# ==========================================
def init_supermarket_sales(conn, c):
    c.execute("""
        CREATE TABLE IF NOT EXISTS supermarket_sales (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_no TEXT,
            market_id  TEXT,
            total      REAL DEFAULT 0,
            profit     REAL DEFAULT 0,
            items_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


# ==========================================
# 🔐 SUPERMARKET LOGIN
# ==========================================
@app.route("/supermarket_login", methods=["GET", "POST"])
def supermarket_login():
    try:
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()

            for doc in db.collection("supermarkets").stream():
                data = doc.to_dict()

                if (data.get("username") == username and
                        data.get("password") == password):

                    # Hubi active — Firestore wuxuu isticmaalaa "active" ama "status"
                    is_active = data.get("active", data.get("status", True))
                    if is_active is False or is_active == "disabled":
                        return render_template(
                            "supermarket_login.html",
                            error="Account disabled ❌"
                        )

                    session["market_id"]    = doc.id
                    session["market_name"]  = data.get("name", "Supermarket")
                    session["market_login"] = True
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


# ==========================================
# 🏠 SUPERMARKET DASHBOARD
# ==========================================
@app.route("/supermarket_dashboard")
def supermarket_dashboard():
    try:
        mid = session.get("market_id")
        if not mid:
            return redirect("/supermarket_login")

        # PRODUCTS — KA SOO QAAD FIRESTORE
        products_raw = []
        try:
            docs = db.collection("supermarkets").document(mid)\
                     .collection("products").stream()
            for doc in docs:
                p          = doc.to_dict()
                p["id"]    = doc.id
                p["name"]  = p.get("name", "")
                p["barcode"]= p.get("barcode", "")
                p["price"] = p.get("price", 0)
                p["cost_price"] = p.get("cost_price", 0)
                p["stock"] = p.get("stock", 0)
                p["category"]   = p.get("category", "General")
                p["unit"]       = p.get("unit", "pcs")
                p["box_qty"]    = p.get("box_qty", 0)
                p["box_price"]  = p.get("box_price", 0)
                products_raw.append(p)
        except Exception as e:
            print("Products load error:", e)

        # ORDERS — KA SOO QAAD SQLITE
        orders = []
        try:
            conn = sqlite3.connect(DB_PATH)
            c    = conn.cursor()
            init_supermarket_sales(conn, c)
            c.execute("""
                SELECT id, receipt_no, total, created_at, items_json
                FROM supermarket_sales
                WHERE market_id=?
                ORDER BY created_at DESC LIMIT 50
            """, (mid,))
            orders = c.fetchall()
            conn.close()
        except Exception as e:
            print("Orders load error:", e)

        return render_template(
            "supermarket_dashboard.html",
            products          = products_raw,
            supermarket_orders= orders,
            market_name       = session.get("market_name", "Supermarket"),
            market_id         = mid,
            today             = datetime.now().strftime("%Y-%m-%d")
        )

    except Exception as e:
        return f"Dashboard Error ❌ {str(e)}"


# ==========================================
# 📦 GET PRODUCTS JSON (for JS barcode scan)
# ==========================================
@app.route("/supermarket/products_json")
def supermarket_products_json():
    try:
        mid = session.get("market_id")
        if not mid:
            return jsonify([])

        docs    = db.collection("supermarkets").document(mid)\
                    .collection("products").stream()
        results = []
        for doc in docs:
            p = doc.to_dict()
            results.append({
                "id":        doc.id,
                "barcode":   p.get("barcode", ""),
                "name":      p.get("name", ""),
                "price":     p.get("price", 0),
                "cost":      p.get("cost_price", 0),
                "stock":     p.get("stock", 0),
                "category":  p.get("category", "General"),
                "unit":      p.get("unit", "pcs"),
                "box_qty":   p.get("box_qty", 0),
                "box_price": p.get("box_price", 0)
            })
        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)})


# ==========================================
# ➕ ADD PRODUCT (JSON) → FIRESTORE
# ==========================================
@app.route("/supermarket/add_product_json", methods=["POST"])
def supermarket_add_product_json():
    try:
        mid = session.get("market_id")
        if not mid:
            return jsonify({"success": False, "error": "Not logged in"}), 401

        data = request.get_json()
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"success": False, "error": "Name required ❌"})

        db.collection("supermarkets").document(mid)\
          .collection("products").add({
            "barcode":    data.get("barcode", ""),
            "name":       name,
            "price":      float(data.get("price", 0)),
            "cost_price": float(data.get("cost_price", 0)),
            "stock":      int(data.get("stock", 0)),
            "category":   data.get("category", "General"),
            "unit":       data.get("unit", "pcs"),
            "box_qty":    int(data.get("box_qty", 0)),
            "box_price":  float(data.get("box_price", 0)),
            "created_at": datetime.now().isoformat()
        })

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# ✏️ EDIT PRODUCT → FIRESTORE
# ==========================================
@app.route("/supermarket/edit_product/<pid>", methods=["PUT"])
def supermarket_edit_product(pid):
    try:
        mid = session.get("market_id")
        if not mid:
            return jsonify({"success": False, "error": "Not logged in"}), 401

        data = request.get_json()
        db.collection("supermarkets").document(mid)\
          .collection("products").document(pid).update({
            "name":       data.get("name"),
            "barcode":    data.get("barcode", ""),
            "price":      float(data.get("price", 0)),
            "cost_price": float(data.get("cost_price", 0)),
            "stock":      int(data.get("stock", 0)),
            "category":   data.get("category", "General"),
            "unit":       data.get("unit", "pcs"),
            "box_qty":    int(data.get("box_qty", 0)),
            "box_price":  float(data.get("box_price", 0))
        })

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# 🗑 DELETE PRODUCT → FIRESTORE
# ==========================================
@app.route("/supermarket/delete_product/<pid>", methods=["DELETE"])
def supermarket_delete_product(pid):
    try:
        mid = session.get("market_id")
        if not mid:
            return jsonify({"success": False, "error": "Not logged in"}), 401

        db.collection("supermarkets").document(mid)\
          .collection("products").document(pid).delete()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# 🛒 COMPLETE SALE
# ==========================================
@app.route("/supermarket/complete_sale", methods=["POST"])
def supermarket_complete_sale():
    try:
        mid = session.get("market_id")
        if not mid:
            return jsonify({"success": False, "error": "Not logged in"}), 401

        data = request.get_json()
        cart = data.get("cart", [])
        if not cart:
            return jsonify({"success": False, "error": "Cart is empty ❌"})

        total_revenue = 0
        total_profit  = 0
        receipt_items = []

        for item in cart:
            pid   = item.get("id")
            qty   = int(item.get("qty", 1))
            price = float(item.get("price", 0))
            label = item.get("label", "pcs")

            # GET PRODUCT FROM FIRESTORE
            prod_doc = db.collection("supermarkets").document(mid)\
                         .collection("products").document(pid).get()

            if not prod_doc.exists:
                return jsonify({"success": False, "error": f"Product not found ❌"})

            p         = prod_doc.to_dict()
            name      = p.get("name", "")
            cost      = float(p.get("cost_price", 0))
            stock     = int(p.get("stock", 0))
            box_qty   = int(p.get("box_qty", 0))
            stock_dec = box_qty * qty if "Box" in label and box_qty else qty

            if stock_dec > stock:
                return jsonify({"success": False, "error": f"Not enough stock for {name} ❌"})

            revenue = price * qty
            profit  = (price - cost) * qty
            total_revenue += revenue
            total_profit  += profit

            # UPDATE STOCK IN FIRESTORE
            db.collection("supermarkets").document(mid)\
              .collection("products").document(pid).update({
                "stock": stock - stock_dec
            })

            receipt_items.append({
                "name":  name,
                "qty":   qty,
                "price": price,
                "label": label,
                "total": revenue
            })

        receipt_no = "RCP-" + "".join(random.choices(string.digits, k=6))

        # SAVE SALE TO SQLITE
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        init_supermarket_sales(conn, c)
        c.execute("""
            INSERT INTO supermarket_sales
            (receipt_no, market_id, total, profit, items_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (receipt_no, mid, round(total_revenue, 2),
              round(total_profit, 2), json.dumps(receipt_items),
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

        return jsonify({
            "success":    True,
            "receipt_no": receipt_no,
            "total":      round(total_revenue, 2),
            "profit":     round(total_profit, 2),
            "items":      receipt_items
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# 🖨️ REPRINT RECEIPT
# ==========================================
@app.route("/supermarket/receipt/<receipt_no>")
def supermarket_get_receipt(receipt_no):
    try:
        mid = session.get("market_id")
        if not mid:
            return jsonify({"success": False})

        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        init_supermarket_sales(conn, c)
        c.execute("""
            SELECT items_json, total FROM supermarket_sales
            WHERE receipt_no=? AND market_id=?
        """, (receipt_no, mid))
        row = c.fetchone()
        conn.close()

        if not row:
            return jsonify({"success": False})

        return jsonify({
            "success": True,
            "items":   json.loads(row[0]),
            "total":   row[1]
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# 📤 BULK CSV IMPORT → FIRESTORE
# ==========================================
@app.route("/supermarket/bulk_import", methods=["POST"])
def supermarket_bulk_import():
    try:
        mid = session.get("market_id")
        if not mid:
            return jsonify({"success": False, "error": "Not logged in"}), 401

        data     = request.get_json()
        products = data.get("products", [])
        if not products:
            return jsonify({"success": False, "error": "No products ❌"})

        imported   = 0
        prod_ref   = db.collection("supermarkets").document(mid).collection("products")

        for p in products:
            name = p.get("name", "").strip()
            if not name:
                continue
            try:
                prod_ref.add({
                    "barcode":    p.get("barcode", ""),
                    "name":       name,
                    "price":      float(p.get("price", 0)),
                    "cost_price": float(p.get("cost_price", 0)),
                    "stock":      int(p.get("stock", 0)),
                    "category":   p.get("category", "General"),
                    "unit":       p.get("unit", "pcs"),
                    "box_qty":    int(p.get("box_qty", 0)),
                    "box_price":  float(p.get("box_price", 0)),
                    "created_at": datetime.now().isoformat()
                })
                imported += 1
            except:
                pass

        return jsonify({"success": True, "imported": imported})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# 📊 STATS
# ==========================================
@app.route("/supermarket/stats")
def supermarket_stats():
    try:
        mid = session.get("market_id")
        if not mid:
            return jsonify({})

        # Products count from Firestore
        prod_docs      = db.collection("supermarkets").document(mid)\
                           .collection("products").stream()
        total_products = 0
        low_stock      = 0
        for doc in prod_docs:
            p = doc.to_dict()
            total_products += 1
            if int(p.get("stock", 0)) <= 10:
                low_stock += 1

        # Sales from SQLite
        today = datetime.now().strftime("%Y-%m-%d")
        conn  = sqlite3.connect(DB_PATH)
        c     = conn.cursor()
        init_supermarket_sales(conn, c)
        c.execute("""
            SELECT SUM(total), COUNT(*)
            FROM supermarket_sales
            WHERE market_id=? AND date(created_at)=?
        """, (mid, today))
        row           = c.fetchone()
        today_revenue = round(row[0] or 0, 2)
        today_orders  = row[1] or 0
        conn.close()

        return jsonify({
            "total_products": total_products,
            "today_revenue":  today_revenue,
            "today_orders":   today_orders,
            "low_stock":      low_stock
        })

    except Exception as e:
        return jsonify({"error": str(e)})


# ==========================================
# 📊 ANALYTICS
# ==========================================
@app.route("/supermarket/analytics")
def supermarket_analytics():
    try:
        mid       = session.get("market_id")
        if not mid:
            return jsonify({})

        date_from = request.args.get("from", datetime.now().strftime("%Y-%m-%d"))
        date_to   = request.args.get("to",   datetime.now().strftime("%Y-%m-%d"))

        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        init_supermarket_sales(conn, c)

        c.execute("""
            SELECT SUM(total), SUM(profit), COUNT(*)
            FROM supermarket_sales
            WHERE market_id=? AND date(created_at) BETWEEN ? AND ?
        """, (mid, date_from, date_to))
        row = c.fetchone()

        c.execute("""
            SELECT date(created_at), COUNT(*), SUM(total), SUM(profit)
            FROM supermarket_sales
            WHERE market_id=? AND date(created_at) BETWEEN ? AND ?
            GROUP BY date(created_at)
            ORDER BY date(created_at) DESC
        """, (mid, date_from, date_to))
        daily = [{"date":r[0],"orders":r[1],
                  "revenue":round(r[2],2),"profit":round(r[3],2)}
                 for r in c.fetchall()]

        # Top products from items_json
        all_sales   = c.execute("""
            SELECT items_json FROM supermarket_sales
            WHERE market_id=? AND date(created_at) BETWEEN ? AND ?
        """, (mid, date_from, date_to)).fetchall()

        conn.close()

        product_map = {}
        items_total = 0
        for sale in all_sales:
            try:
                items = json.loads(sale[0])
                for item in items:
                    k = item.get("name", "")
                    product_map[k] = product_map.get(k, 0) + item.get("qty", 0)
                    items_total   += item.get("qty", 0)
            except:
                pass

        top_products = sorted(
            [{"name": k, "qty": v} for k, v in product_map.items()],
            key=lambda x: x["qty"], reverse=True
        )[:10]

        return jsonify({
            "revenue":      round(row[0] or 0, 2),
            "profit":       round(row[1] or 0, 2),
            "orders":       row[2] or 0,
            "items_sold":   items_total,
            "daily":        daily,
            "top_products": top_products
        })

    except Exception as e:
        return jsonify({"error": str(e)})


# ==========================================
# 📋 REGISTER SUPERMARKET (ADMIN)
# ==========================================
@app.route("/supermarket_register", methods=["GET", "POST"])
def supermarket_register():
    try:
        if request.method == "POST":
            months = int(request.form.get("months", 1))
            expiry = (datetime.now() + timedelta(days=months*30)).strftime("%Y-%m-%d")
            db.collection("supermarkets").add({
                "name":       request.form.get("name", ""),
                "username":   request.form.get("username", ""),
                "password":   request.form.get("password", ""),
                "price":      request.form.get("price", ""),
                "payment":    request.form.get("payment", ""),
                "expiry_date":expiry,
                "active":     True,
                "created_at": datetime.now()
            })
            return redirect("/supermarket_login")
        return render_template("supermarket_register.html")
    except Exception as e:
        return f"Register Error ❌ {str(e)}"

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
from collections import defaultdict


def _parse_created_at(value):
    """Waxay isku dayaysaa in ay convert-garayso created_at (Firestore timestamp,
    datetime, ama string) una soo celiso datetime object oo timezone-aware.
    Haddii ay fashilanto waxay soo celisaa None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        # Firestore DatetimeWithNanoseconds ama string ISO
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _range_start(range_key, now):
    """Waxay soo celisaa taariikhda bilowga range-ka la doortay (day/week/month/year)."""
    if range_key == "day":
        return now - timedelta(days=1)
    if range_key == "week":
        return now - timedelta(days=7)
    if range_key == "month":
        return now - timedelta(days=30)
    if range_key == "year":
        return now - timedelta(days=365)
    return now - timedelta(days=7)  # default = week


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

        # ---------- Range filter (?range=day/week/month/year) ----------
        range_key = request.args.get("range", "week")
        now = datetime.now(timezone.utc)
        range_start = _range_start(range_key, now)

        # ---------- Menu ----------
        menu = []
        menu_by_id = {}
        menu_docs = restaurant_ref.collection("menu").stream()
        for doc in menu_docs:
            item = doc.to_dict()
            item["id"] = doc.id
            menu.append(item)
            menu_by_id[doc.id] = item

        # ---------- Orders ----------
        orders = []
        total = 0.0
        order_docs = restaurant_ref.collection("orders").stream()

        # Xogta chart-yada ee waxaan ka soo xisaabin doono orders-ka dhabta ah
        daily_revenue = defaultdict(float)   # {date_str: revenue}
        daily_orders = defaultdict(int)      # {date_str: order count}
        status_counts = defaultdict(int)     # {status: count}
        item_sales = defaultdict(lambda: {"qty": 0, "revenue": 0.0, "image": "", "name": ""})
        category_revenue = defaultdict(float)  # {category: revenue}

        for doc in order_docs:
            order = doc.to_dict()
            order["id"] = doc.id

            try:
                price = float(order.get("price", 0))
            except Exception:
                price = 0.0
            total += price
            orders.append(order)

            created_at = _parse_created_at(order.get("created_at"))
            status = str(order.get("status") or "pending").lower()
            status_counts[status] += 1

            # Only bucket into the range-filtered charts if we have a valid date
            if created_at and created_at >= range_start:
                if range_key == "day":
                    bucket = created_at.strftime("%H:00")
                elif range_key == "year":
                    bucket = created_at.strftime("%b")
                else:
                    bucket = created_at.strftime("%b %d")

                daily_revenue[bucket] += price
                daily_orders[bucket] += 1

            # Line items for top-selling & category breakdown, if the order stores them
            items = order.get("items")
            if isinstance(items, list):
                for it in items:
                    name = it.get("name") or "Unknown"
                    qty = int(it.get("qty", it.get("quantity", 1)) or 1)
                    line_price = float(it.get("price", 0) or 0)
                    item_sales[name]["qty"] += qty
                    item_sales[name]["revenue"] += line_price * qty
                    item_sales[name]["name"] = name

                    menu_match = next((m for m in menu if m.get("name") == name), None)
                    item_sales[name]["image"] = menu_match.get("image", "") if menu_match else it.get("image", "")

                    category = (menu_match.get("category") if menu_match else it.get("category")) or "Other"
                    category_revenue[category] += line_price * qty

        # ---------- Order status breakdown (for template list + donut chart) ----------
        status_breakdown = [
            {"label": s.title(), "count": c} for s, c in sorted(status_counts.items())
        ]
        status_labels = [s["label"] for s in status_breakdown] or ["No Data"]
        status_counts_list = [s["count"] for s in status_breakdown] or [1]

        # ---------- Overview chart (revenue + orders over time) ----------
        chart_labels = sorted(daily_revenue.keys(), key=lambda k: k)
        chart_revenue = [round(daily_revenue[k], 2) for k in chart_labels]
        chart_orders = [daily_orders[k] for k in chart_labels]

        # ---------- Top selling items ----------
        top_items = sorted(item_sales.values(), key=lambda x: x["qty"], reverse=True)[:5]
        for t in top_items:
            t["revenue"] = round(t["revenue"], 2)

        # ---------- Revenue by category ----------
        category_labels = list(category_revenue.keys()) or ["No Data"]
        category_values = [round(v, 2) for v in category_revenue.values()] or [0]

        return render_template(
            "restaurant_admin.html",
            r=restaurant,
            menu=menu,
            orders=orders,
            total=round(total, 2),
            profit=round(total, 2),
            loss=0,
            compare_text="System working",
            rid=rid,
            range=range_key,
            status_breakdown=status_breakdown,
            status_labels=status_labels,
            status_counts=status_counts_list,
            chart_labels=chart_labels,
            chart_revenue=chart_revenue,
            chart_orders=chart_orders,
            top_items=top_items,
            category_labels=category_labels,
            category_values=category_values,
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
# 📢 SYSTEM INFO — ADD
# ==========================================
@app.route("/add_info", methods=["POST"])
def add_info():
    try:
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        image_file = request.files.get("image")
        video_file = request.files.get("video")

        image_name = ""
        video_name = ""

        if image_file and image_file.filename:
            image_name = secure_filename(image_file.filename)
            image_file.save(os.path.join("static/uploads", image_name))

        if video_file and video_file.filename:
            video_name = secure_filename(video_file.filename)
            video_file.save(os.path.join("static/uploads", video_name))

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
    

# ── KITCHEN joins its room on page load ──
@socketio.on("kitchen_join")
def kitchen_join(data):
    rid  = data.get("rid", "")
    room = f"kitchen_{rid}"
    join_room(room)
    emit("kitchen_ready", {"room": room})

# ── CUSTOMER joins its room ──
@socketio.on("customer_join")
def customer_join(data):
    rid   = data.get("rid", "")
    table = data.get("table", "")
    room  = f"customer_{rid}_{table}"
    join_room(room)
    emit("customer_ready", {"room": room})

# ── Customer → Kitchen: offer ──
@socketio.on("webrtc_offer")
def webrtc_offer(data):
    rid   = data.get("rid", "")
    table = data.get("table", "")
    data["table"] = table
    emit("webrtc_offer", data, to=f"kitchen_{rid}")

# ── Customer → Kitchen: ICE ──
@socketio.on("webrtc_ice_customer")
def webrtc_ice_customer(data):
    rid = data.get("rid", "")
    emit("webrtc_ice_customer", data, to=f"kitchen_{rid}")

# ── Customer → Kitchen: end ──
@socketio.on("webrtc_end_customer")
def webrtc_end_customer(data):
    rid = data.get("rid", "")
    emit("webrtc_end", data, to=f"kitchen_{rid}")

# ── Kitchen → Customer: answer ──
@socketio.on("webrtc_answer")
def webrtc_answer(data):
    rid   = data.get("rid", "")
    table = data.get("table", "")
    emit("webrtc_answer", data, to=f"customer_{rid}_{table}")

# ── Kitchen → Customer: ICE ──
@socketio.on("webrtc_ice_kitchen")
def webrtc_ice_kitchen(data):
    rid   = data.get("rid", "")
    table = data.get("table", "")
    emit("webrtc_ice_kitchen", data, to=f"customer_{rid}_{table}")

# ── Kitchen → Customer: end ──
@socketio.on("webrtc_end_kitchen")
def webrtc_end_kitchen(data):
    rid   = data.get("rid", "")
    table = data.get("table", "")
    emit("webrtc_end", data, to=f"customer_{rid}_{table}")

# ==========================================
# 💊 PHARMACY ROUTES — UPDATED VERSION
# ==========================================
# Medicines  → Firestore: pharmacy_product/{username}/medicines
# Sales      → SQLite
# Debts      → SQLite
# Images     → static/uploads/ (filename stored in Firestore)
# ==========================================

PHARMACY_IMG_FOLDER = "static/uploads"
os.makedirs(PHARMACY_IMG_FOLDER, exist_ok=True)


# ==========================================
# GET PHARMACY FIRESTORE REF
# ==========================================
def get_pharmacy_ref():
    """
    Returns reference to: pharmacy_product/{username}/medicines
    The document ID (username) is always the pharmacy's own username.
    """
    username = session.get("pharmacy_user", "")
    if not username:
        username = session.get("pharmacy_id", "unknown")
    return (
        db.collection("pharmacy_product")
          .document(username)
          .collection("medicines")
    )


def get_username():
    """Returns the current pharmacy's username (used as document ID)."""
    return session.get("pharmacy_user", session.get("pharmacy_id", "unknown"))


# ==========================================
# INIT PHARMACY SALES/DEBTS (SQLite only)
# ==========================================
def init_pharmacy_sql(conn, c):
    c.execute("""
        CREATE TABLE IF NOT EXISTS pharmacy_users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role     TEXT DEFAULT 'pharmacist'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS pharmacy_sales (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            pharmacy_id    TEXT,
            medicine_id    TEXT,
            medicine_name  TEXT,
            barcode        TEXT,
            quantity_sold  INTEGER,
            cost_price     REAL,
            selling_price  REAL,
            profit         REAL,
            sale_date      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS pharmacy_debts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            pharmacy_id TEXT,
            name        TEXT NOT NULL,
            phone       TEXT,
            type        TEXT DEFAULT 'cash',
            amount      REAL DEFAULT 0,
            description TEXT,
            date        TEXT,
            status      TEXT DEFAULT 'unpaid',
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


# ==========================================
# PHARMACY LOGIN
# ==========================================
@app.route("/pharmacy_login", methods=["GET", "POST"])
def pharmacy_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            for doc in db.collection("pharmacies").where("username", "==", username).stream():
                ph = doc.to_dict()
                if ph.get("password") == password:
                    expiry = ph.get("expiry_date", "")
                    if expiry and expiry < today:
                        return render_template("pharmacy_login.html", error="Subscription expired - Please renew with admin.")
                    if not ph.get("active", True):
                        return render_template("pharmacy_login.html", error="Account disabled - Contact admin.")
                    session["pharmacy_ok"]     = True
                    session["pharmacy_user"]   = username
                    session["pharmacy_name"]   = ph.get("pharmacy_name", username)
                    session["pharmacy_id"]     = doc.id
                    session["pharmacy_expiry"] = expiry
                    return redirect("/pharmacy")
        except Exception as e:
            print("Pharmacy login pharmacies error:", e)
        try:
            pu_doc = db.collection("pharmacy_users").document(username).get()
            if pu_doc.exists:
                pu = pu_doc.to_dict()
                if pu.get("password") == password:
                    session["pharmacy_ok"]   = True
                    session["pharmacy_user"] = username
                    session["pharmacy_name"] = pu.get("pharmacy_name", username)
                    session["pharmacy_id"]   = pu.get("pharmacy_id", username)
                    return redirect("/pharmacy")
        except Exception as e:
            print("Pharmacy login pharmacy_users error:", e)
        try:
            conn = sqlite3.connect(DB_PATH)
            c    = conn.cursor()
            c.execute("""CREATE TABLE IF NOT EXISTS pharmacy_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'pharmacist')""")
            c.execute("SELECT * FROM pharmacy_users WHERE username=? AND password=?", (username, password))
            user = c.fetchone()
            conn.close()
            if user:
                session["pharmacy_ok"]   = True
                session["pharmacy_user"] = username
                session["pharmacy_name"] = username
                session["pharmacy_id"]   = username
                return redirect("/pharmacy")
        except Exception as e:
            print("Pharmacy login SQLite error:", e)
        return render_template("pharmacy_login.html", error="Wrong username or password")
    return render_template("pharmacy_login.html")


# ==========================================
# PHARMACY LOGOUT
# ==========================================
@app.route("/pharmacy/logout")
def pharmacy_logout():
    session.pop("pharmacy_ok",     None)
    session.pop("pharmacy_user",   None)
    session.pop("pharmacy_name",   None)
    session.pop("pharmacy_id",     None)
    session.pop("pharmacy_expiry", None)
    return redirect("/pharmacy_login")


# ==========================================
# PHARMACY DASHBOARD
# ==========================================
@app.route("/pharmacy")
def pharmacy():
    if not session.get("pharmacy_ok"):
        return redirect("/pharmacy_login")
    try:
        ref       = get_pharmacy_ref()
        medicines = []
        for doc in ref.stream():
            m = doc.to_dict()
            medicines.append((
                doc.id,
                m.get("name", ""),
                m.get("barcode", ""),
                m.get("cost_price", 0),
                m.get("selling_price", 0),
                m.get("stock_quantity", 0),
                m.get("expiry_date", ""),
                m.get("category", "General"),
                m.get("created_at", ""),
                m.get("image", ""),       # filename for static/uploads
                m.get("imageUrl", "")     # optional external URL
            ))
        today      = datetime.now().strftime("%Y-%m-%d")
        alert_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        pid        = get_username()
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        init_pharmacy_sql(conn, c)
        c.execute("""SELECT COUNT(*), SUM(quantity_sold), SUM(profit)
                     FROM pharmacy_sales WHERE pharmacy_id=? AND date(sale_date)=?""", (pid, today))
        row          = c.fetchone()
        today_sales  = row[0] or 0
        today_qty    = row[1] or 0
        today_profit = round(row[2] or 0, 2)
        c.execute("""SELECT medicine_name, SUM(quantity_sold) as total
                     FROM pharmacy_sales WHERE pharmacy_id=? AND date(sale_date)=?
                     GROUP BY medicine_name ORDER BY total DESC LIMIT 5""", (pid, today))
        top_selling = c.fetchall()
        conn.close()
        expired       = [m for m in medicines if m[6] and m[6] < today]
        expiry_alerts = [m for m in medicines if m[6] and today <= m[6] <= alert_date]
        low_stock     = [m for m in medicines if int(m[5]) <= 3]
        return render_template(
            "pharmacy.html",
            medicines=medicines, today_sales=today_sales, today_qty=today_qty,
            today_profit=today_profit, expiry_alerts=expiry_alerts, expired=expired,
            low_stock=low_stock, top_selling=top_selling, today=today,
            now_date=today, expiry_warn=alert_date
        )
    except Exception as e:
        return f"Pharmacy Error: {str(e)}"


# ==========================================
# ADD MEDICINE → pharmacy_product/{username}/medicines
# ==========================================
@app.route("/pharmacy/add_medicine", methods=["POST"])
def add_medicine():
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
            return jsonify({"success": False, "error": "Medicine name required"})

        image_filename = ""
        image_file     = request.files.get("image")
        if image_file and image_file.filename:
            ext       = os.path.splitext(image_file.filename)[1].lower()
            safe_name = secure_filename(f"{name.replace(' ','_')}_{int(datetime.now().timestamp())}{ext}")
            image_file.save(os.path.join(PHARMACY_IMG_FOLDER, safe_name))
            image_filename = safe_name

        ref = get_pharmacy_ref()
        ref.add({
            "name":           name,
            "barcode":        barcode or "",
            "cost_price":     cost_price,
            "selling_price":  selling_price,
            "stock_quantity": stock_qty,
            "expiry_date":    expiry_date,
            "category":       category,
            "image":          image_filename,
            "imageUrl":       "",
            "created_at":     datetime.now().isoformat()
        })
        return jsonify({"success": True, "message": "Medicine added"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# SEARCH MEDICINE → pharmacy_product/{username}/medicines
# ==========================================
@app.route("/pharmacy/search")
def search_medicine():
    if not session.get("pharmacy_ok"):
        return jsonify({"error": "Not logged in"}), 401
    query = request.args.get("q", "").strip()
    try:
        ref     = get_pharmacy_ref()
        results = []
        q_low   = query.lower()
        for doc in ref.stream():
            m    = doc.to_dict()
            name = m.get("name", "")
            bc   = m.get("barcode", "")
            if not query or bc == query or q_low in name.lower():
                results.append({
                    "medicine_id":    doc.id,
                    "name":           name,
                    "barcode":        bc,
                    "cost_price":     m.get("cost_price", 0),
                    "selling_price":  m.get("selling_price", 0),
                    "stock_quantity": m.get("stock_quantity", 0),
                    "expiry_date":    m.get("expiry_date", ""),
                    "category":       m.get("category", "General"),
                    "image":          m.get("image", ""),
                    "imageUrl":       m.get("imageUrl", "")
                })
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)})


# ==========================================
# SELL MEDICINE → SQLite sales, update Firestore stock
# ==========================================
@app.route("/pharmacy/sell", methods=["POST"])
def sell_medicine():
    if not session.get("pharmacy_ok"):
        return jsonify({"success": False, "error": "Not logged in"}), 401
    try:
        data = request.get_json()
        cart = data.get("cart", [])
        if not cart:
            return jsonify({"success": False, "error": "Cart is empty"})
        ref          = get_pharmacy_ref()
        pid          = get_username()
        total_profit = 0
        conn         = sqlite3.connect(DB_PATH)
        c            = conn.cursor()
        init_pharmacy_sql(conn, c)
        for item in cart:
            med_id     = item.get("medicine_id")
            qty        = int(item.get("quantity", 1))
            paid_price = float(item.get("price", 0))
            med_doc    = ref.document(str(med_id)).get()
            if not med_doc.exists:
                conn.close()
                return jsonify({"success": False, "error": f"Medicine not found: {med_id}"})
            m     = med_doc.to_dict()
            name  = m.get("name", "")
            bc    = m.get("barcode", "")
            cost  = float(m.get("cost_price", 0))
            stock = int(m.get("stock_quantity", 0))
            if qty > stock:
                conn.close()
                return jsonify({"success": False, "error": f"Not enough stock for {name}. Available: {stock}"})
            profit       = (paid_price - cost) * qty
            total_profit += profit
            ref.document(str(med_id)).update({"stock_quantity": stock - qty})
            c.execute("""INSERT INTO pharmacy_sales
                (pharmacy_id, medicine_id, medicine_name, barcode,
                 quantity_sold, cost_price, selling_price, profit, sale_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (pid, med_id, name, bc, qty, cost, paid_price,
                 profit, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Sale recorded",
                        "total_profit": round(total_profit, 2),
                        "items_sold": len(cart)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# EDIT MEDICINE → Firestore
# ==========================================
@app.route("/pharmacy/edit/<med_id>", methods=["PUT"])
def edit_medicine(med_id):
    if not session.get("pharmacy_ok"):
        return jsonify({"success": False, "error": "Not logged in"}), 401
    try:
        data = request.get_json()
        ref  = get_pharmacy_ref()
        ref.document(med_id).update({
            "name":           data.get("name"),
            "barcode":        data.get("barcode", ""),
            "cost_price":     float(data.get("cost_price", 0)),
            "selling_price":  float(data.get("selling_price", 0)),
            "stock_quantity": int(data.get("stock_quantity", 0)),
            "expiry_date":    data.get("expiry_date", ""),
            "category":       data.get("category", "General")
        })
        return jsonify({"success": True, "message": "Updated"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# DELETE MEDICINE → Firestore
# ==========================================
@app.route("/pharmacy/delete/<med_id>", methods=["DELETE"])
def delete_medicine(med_id):
    if not session.get("pharmacy_ok"):
        return jsonify({"success": False, "error": "Not logged in"}), 401
    try:
        ref = get_pharmacy_ref()
        ref.document(med_id).delete()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# ALERTS → Firestore
# ==========================================
@app.route("/pharmacy/alerts")
def pharmacy_alerts():
    if not session.get("pharmacy_ok"):
        return jsonify({"error": "Not logged in"}), 401
    try:
        today      = datetime.now().strftime("%Y-%m-%d")
        alert_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        ref        = get_pharmacy_ref()
        expiring = []; expired = []; low_st = []
        for doc in ref.stream():
            m     = doc.to_dict()
            exp   = m.get("expiry_date", "")
            stock = int(m.get("stock_quantity", 0))
            entry = {"medicine_id": doc.id, "name": m.get("name",""), "stock": stock, "expiry": exp}
            if exp:
                if exp < today: expired.append(entry)
                elif exp <= alert_date: expiring.append(entry)
            if stock <= 3: low_st.append(entry)
        return jsonify({"expiring_soon": expiring, "expired": expired, "low_stock": low_st,
                        "total_alerts": len(expiring) + len(expired) + len(low_st)})
    except Exception as e:
        return jsonify({"error": str(e)})


# ==========================================
# REPORT → SQLite
# ==========================================
@app.route("/pharmacy/report")
def pharmacy_report():
    if not session.get("pharmacy_ok"):
        return jsonify({"error": "Not logged in"}), 401
    try:
        pid       = get_username()
        date_from = request.args.get("from", datetime.now().strftime("%Y-%m-%d"))
        date_to   = request.args.get("to",   datetime.now().strftime("%Y-%m-%d"))
        conn      = sqlite3.connect(DB_PATH)
        c         = conn.cursor()
        init_pharmacy_sql(conn, c)
        c.execute("""SELECT COUNT(*), SUM(quantity_sold),
                     SUM(selling_price * quantity_sold),
                     SUM(cost_price    * quantity_sold),
                     SUM(profit)
                     FROM pharmacy_sales
                     WHERE pharmacy_id=? AND date(sale_date) BETWEEN ? AND ?""",
                  (pid, date_from, date_to))
        row = c.fetchone()
        c.execute("""SELECT medicine_name,
                     SUM(quantity_sold) as qty,
                     SUM(profit)        as profit
                     FROM pharmacy_sales
                     WHERE pharmacy_id=? AND date(sale_date) BETWEEN ? AND ?
                     GROUP BY medicine_name ORDER BY qty DESC LIMIT 5""",
                  (pid, date_from, date_to))
        top_medicines = [{"name": r[0], "qty": r[1], "profit": round(r[2], 2)}
                         for r in c.fetchall()]
        c.execute("""SELECT date(sale_date),
                     COUNT(*),
                     SUM(quantity_sold),
                     SUM(profit)
                     FROM pharmacy_sales
                     WHERE pharmacy_id=? AND date(sale_date) BETWEEN ? AND ?
                     GROUP BY date(sale_date) ORDER BY date(sale_date) DESC""",
                  (pid, date_from, date_to))
        daily = [{"date": r[0], "transactions": r[1], "qty": r[2], "profit": round(r[3], 2)}
                 for r in c.fetchall()]
        conn.close()
        return jsonify({
            "from": date_from, "to": date_to,
            "total_transactions": row[0] or 0,
            "total_qty":          row[1] or 0,
            "total_revenue":      round(row[2] or 0, 2),
            "total_cost":         round(row[3] or 0, 2),
            "net_profit":         round(row[4] or 0, 2),
            "top_medicines":      top_medicines,
            "daily":              daily
        })
    except Exception as e:
        return jsonify({"error": str(e)})


# ==========================================
# ADD DEBT → SQLite
# ==========================================
@app.route("/pharmacy/add_debt", methods=["POST"])
def add_debt():
    if not session.get("pharmacy_ok"):
        return jsonify({"success": False, "error": "Not logged in"}), 401
    try:
        pid  = get_username()
        data = request.get_json()
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"success": False, "error": "Name required"})
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        init_pharmacy_sql(conn, c)
        c.execute("""INSERT INTO pharmacy_debts
            (pharmacy_id, name, phone, type, amount, description, date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'unpaid')""",
            (pid, name, data.get("phone", ""), data.get("type", "cash"),
             float(data.get("amount", 0)), data.get("description", ""),
             data.get("date", datetime.now().strftime("%Y-%m-%d"))))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# GET DEBTS → SQLite
# ==========================================
@app.route("/pharmacy/debts")
def get_debts():
    if not session.get("pharmacy_ok"):
        return jsonify({"error": "Not logged in"}), 401
    try:
        pid  = get_username()
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        init_pharmacy_sql(conn, c)
        c.execute("SELECT * FROM pharmacy_debts WHERE pharmacy_id=? ORDER BY created_at DESC", (pid,))
        rows = c.fetchall()
        c.execute("SELECT COUNT(*) FROM pharmacy_debts WHERE pharmacy_id=?", (pid,))
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM pharmacy_debts WHERE pharmacy_id=? AND type='product' AND status!='paid'", (pid,))
        product_count = c.fetchone()[0]
        c.execute("SELECT SUM(amount) FROM pharmacy_debts WHERE pharmacy_id=? AND type='cash' AND status!='paid'", (pid,))
        cash_total = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM pharmacy_debts WHERE pharmacy_id=? AND status='paid'", (pid,))
        paid_count = c.fetchone()[0]
        conn.close()
        debts = [{"id": r[0], "name": r[2], "phone": r[3], "type": r[4],
                  "amount": r[5], "description": r[6], "date": r[7],
                  "status": r[8], "created_at": r[9]} for r in rows]
        return jsonify({"debts": debts, "total": total, "product_count": product_count,
                        "cash_total": round(cash_total, 2), "paid_count": paid_count})
    except Exception as e:
        return jsonify({"error": str(e)})


# ==========================================
# MARK DEBT PAID
# ==========================================
@app.route("/pharmacy/debt_paid/<int:debt_id>", methods=["POST"])
def mark_debt_paid(debt_id):
    if not session.get("pharmacy_ok"):
        return jsonify({"success": False, "error": "Not logged in"}), 401
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("UPDATE pharmacy_debts SET status='paid' WHERE id=?", (debt_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# DELETE DEBT
# ==========================================
@app.route("/pharmacy/delete_debt/<int:debt_id>", methods=["DELETE"])
def delete_debt(debt_id):
    if not session.get("pharmacy_ok"):
        return jsonify({"success": False, "error": "Not logged in"}), 401
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("DELETE FROM pharmacy_debts WHERE id=?", (debt_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# REGISTER PHARMACY (ADMIN)
# ==========================================
@app.route("/admin/register_pharmacy", methods=["POST"])
def admin_register_pharmacy():
    try:
        if not session.get("admin_ok"):
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        data          = request.get_json()
        pharmacy_name = data.get("pharmacy_name", "").strip()
        phone         = data.get("phone", "").strip()
        monthly_fee   = float(data.get("monthly_fee", 0))
        months        = int(data.get("months", 3))
        username      = data.get("username", "").strip()
        password      = data.get("password", "").strip()
        if not pharmacy_name or not phone or not username or not password:
            return jsonify({"success": False, "error": "Fill all required fields"})
        expiry_date = (datetime.now() + timedelta(days=months * 30)).strftime("%Y-%m-%d")
        total_fee   = round(monthly_fee * months, 2)
        doc_ref = db.collection("pharmacies").add({
            "pharmacy_name": pharmacy_name, "phone": phone,
            "username": username, "password": password,
            "monthly_fee": monthly_fee, "months": months, "total_fee": total_fee,
            "created_at": datetime.now().isoformat(), "expiry_date": expiry_date, "active": True
        })
        db.collection("pharmacy_users").document(username).set({
            "username": username, "password": password,
            "pharmacy_name": pharmacy_name, "phone": phone,
            "pharmacy_id": doc_ref[1].id, "created_at": datetime.now().isoformat()
        })
        # Create the pharmacy_product document for this user
        db.collection("pharmacy_product").document(username).set({
            "pharmacy_name": pharmacy_name,
            "username":      username,
            "created_at":    datetime.now().isoformat()
        })
        return jsonify({"success": True, "message": "Pharmacy registered",
                        "expiry_date": expiry_date, "total_fee": total_fee})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# RENEW PHARMACY (ADMIN)
# ==========================================
@app.route("/admin/renew_pharmacy/<string:pid>", methods=["POST"])
def admin_renew_pharmacy(pid):
    try:
        if not session.get("admin_ok"):
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        data   = request.get_json()
        months = int(data.get("months", 3))
        ph_ref = db.collection("pharmacies").document(pid)
        ph_doc = ph_ref.get()
        if not ph_doc.exists:
            return jsonify({"success": False, "error": "Pharmacy not found"})
        ph         = ph_doc.to_dict()
        old_expiry = ph.get("expiry_date", datetime.now().strftime("%Y-%m-%d"))
        try:
            base = max(datetime.strptime(old_expiry, "%Y-%m-%d"), datetime.now())
        except:
            base = datetime.now()
        new_expiry = (base + timedelta(days=months * 30)).strftime("%Y-%m-%d")
        ph_ref.update({"expiry_date": new_expiry, "active": True,
                       "last_renewed": datetime.now().isoformat(), "renewed_months": months})
        return jsonify({"success": True, "expiry_date": new_expiry})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# DELETE PHARMACY (ADMIN)
# ==========================================
@app.route("/admin/delete_pharmacy/<string:pid>", methods=["DELETE"])
def admin_delete_pharmacy(pid):
    try:
        if not session.get("admin_ok"):
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        ph_doc = db.collection("pharmacies").document(pid).get()
        if not ph_doc.exists:
            return jsonify({"success": False, "error": "Not found"})
        ph       = ph_doc.to_dict()
        username = ph.get("username", "")
        db.collection("pharmacies").document(pid).delete()
        if username:
            try:
                db.collection("pharmacy_users").document(username).delete()
            except:
                pass
            try:
                db.collection("pharmacy_product").document(username).delete()
            except:
                pass
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# CREATE PHARMACY USER (ADMIN)
# ==========================================
@app.route("/admin/create_pharmacy_user", methods=["POST"])
def admin_create_pharmacy_user():
    try:
        if not session.get("admin_ok"):
            return jsonify({"success": False, "error": "Unauthorized ❌"}), 401

        data     = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        if not username or not password:
            return jsonify({"success": False, "error": "Fill all fields ❌"})

        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS pharmacy_users (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                username  TEXT UNIQUE,
                password  TEXT,
                role      TEXT DEFAULT 'pharmacist'
            )
        """)
        conn.commit()
        c.execute("SELECT id FROM pharmacy_users WHERE username=?", (username,))
        if c.fetchone():
            conn.close()
            return jsonify({"success": False, "error": f"Username '{username}' already exists ❌"})
        c.execute(
            "INSERT INTO pharmacy_users (username, password) VALUES (?, ?)",
            (username, password)
        )
        conn.commit()
        conn.close()

        db.collection("pharmacy_users").document(username).set({
            "username":   username,
            "password":   password,
            "created_at": datetime.now().isoformat()
        })

        # Auto-create the pharmacy_product document so collection is ready
        db.collection("pharmacy_product").document(username).set({
            "username":   username,
            "created_at": datetime.now().isoformat()
        }, merge=True)

        return jsonify({"success": True, "message": f"User '{username}' created ✅"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =========================
# 💳 PAYMENT QR GENERATOR (A4)
# =========================
@app.route("/payment_qr", methods=["GET", "POST"])
def payment_qr():
    if not session.get("admin_ok"):
        return redirect("/admin")

    img_file = ""
    ussd_code = ""

    if request.method == "POST":
        ussd_code = request.form.get("ussd_code", "").strip()

        if not ussd_code:
            return render_template("qr_payment.html", img="", ussd="", error="Fadlan geli USSD code ❌")

        # tel: link — si scan-ku toos ugu wanqali karo dial-ka
        # # waxaa loo beddelaa %23 si telefoonku u aqbalo
        tel_link = "tel:" + ussd_code.replace("#", "%23")

        filename = f"payqr_{int(time.time())}.png"
        qr_folder = os.path.join("static", "qr")
        os.makedirs(qr_folder, exist_ok=True)
        file_path = os.path.join(qr_folder, filename)

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=12,
            border=2
        )
        qr.add_data(tel_link)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        img.save(file_path)

        img_file = filename

    return render_template("qr_payment.html", img=img_file, ussd=ussd_code)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))

    init_db()

    socketio.run(
        app,
        host="0.0.0.0",
        port=port
    )