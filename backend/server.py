"""
Smart Locker Backend Server
Flask + SQLite

Install dependencies:
  pip install flask flask-cors requests qrcode pillow pyotp

Run:
  python server.py

The server handles:
  - Locker rental booking (web UI)
  - UPI payment QR generation
  - Payment verification polling
  - OTP generation for retrieval
  - Intrusion event logging
  - Telegram notifications (optional)
"""

import os
import uuid
import random
import string
import time
import sqlite3
import qrcode
import io
import base64
import hmac
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, send_file
from flask_cors import CORS

# ─── Optional: Telegram notifications ──────────────────────────
TELEGRAM_BOT_TOKEN  = ""   # Set your bot token here
TELEGRAM_CHAT_ID    = ""   # Set your chat ID here

# ─── UPI Configuration ─────────────────────────────────────────
UPI_VPA             = "7019007474@ptaxis"   # e.g. 9876543210@paytm or name@okicici
UPI_PAYEE_NAME      = "Akashgouda G Kopparad"
PRICE_PER_HOUR      = 20   # INR

app = Flask(__name__)
CORS(app)

DB_PATH = "locker.db"

# ─────────────────────────────────────────────────────────────
#  DATABASE SETUP
# ─────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS lockers (
            locker_id     TEXT PRIMARY KEY,
            status        TEXT DEFAULT 'available',
            current_order TEXT,
            intrusion_flag INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id       TEXT PRIMARY KEY,
            locker_id      TEXT,
            user_name      TEXT,
            user_phone     TEXT,
            amount         INTEGER,
            duration_hours INTEGER,
            payment_status TEXT DEFAULT 'pending',
            payment_ref    TEXT,
            otp            TEXT,
            verified       INTEGER DEFAULT 0,
            created_at     REAL,
            expires_at     REAL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            locker_id  TEXT,
            order_id   TEXT,
            event_type TEXT,
            timestamp  REAL,
            details    TEXT
        )
    """)

    # Insert a default locker if none exists
    c.execute("INSERT OR IGNORE INTO lockers (locker_id) VALUES ('LOCKER_001')")
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────────────────────
#  UPI DEEP LINK GENERATOR
# ─────────────────────────────────────────────────────────────
def generate_upi_url(order_id: str, amount: int, note: str) -> str:
    """
    Generates a UPI payment deep link.
    Works with: Google Pay, PhonePe, Paytm, BHIM, any UPI app.

    Format: upi://pay?pa=VPA&pn=NAME&am=AMOUNT&cu=INR&tn=NOTE&tr=TXN_REF
    """
    upi_url = (
        f"upi://pay?"
        f"pa={UPI_VPA}&"
        f"pn={UPI_PAYEE_NAME.replace(' ', '%20')}&"
        f"am={amount}.00&"
        f"cu=INR&"
        f"tn=Locker%20Rental%20{order_id[:8]}&"
        f"tr={order_id}"
    )
    return upi_url

def generate_qr_base64(url: str) -> str:
    """Generate QR code image as base64 string for web display."""
    qr = qrcode.QRCode(
        version=3,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def generate_otp(length=6) -> str:
    return ''.join(random.choices(string.digits, k=length))

def log_event(locker_id, order_id, event_type, details=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO events (locker_id, order_id, event_type, timestamp, details) VALUES (?,?,?,?,?)",
        (locker_id, order_id, event_type, time.time(), details)
    )
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────────────────────
#  TELEGRAM NOTIFICATIONS (optional)
# ─────────────────────────────────────────────────────────────
def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")

# ─────────────────────────────────────────────────────────────
#  API ROUTES — ESP32 polling endpoints
# ─────────────────────────────────────────────────────────────

@app.route("/api/locker/status/<locker_id>")
def locker_status(locker_id):
    """ESP32 polls this to check if a new rental is pending."""
    conn = get_db()
    locker = conn.execute(
        "SELECT * FROM lockers WHERE locker_id=?", (locker_id,)
    ).fetchone()
    conn.close()

    if not locker:
        return jsonify({"error": "Locker not found"}), 404

    if locker["status"] == "payment_pending" and locker["current_order"]:
        conn = get_db()
        order = conn.execute(
            "SELECT * FROM orders WHERE order_id=?", (locker["current_order"],)
        ).fetchone()
        conn.close()

        if order:
            upi_url = generate_upi_url(order["order_id"], order["amount"], "Locker rental")
            return jsonify({
                "status":          "payment_pending",
                "order_id":        order["order_id"],
                "upi_url":         upi_url,
                "amount":          order["amount"],
                "duration_hours":  order["duration_hours"]
            })

    return jsonify({"status": locker["status"]})

@app.route("/api/payment/status/<order_id>")
def payment_status(order_id):
    """ESP32 polls this after showing QR to check if payment was received."""
    conn = get_db()
    order = conn.execute(
        "SELECT * FROM orders WHERE order_id=?", (order_id,)
    ).fetchone()
    conn.close()

    if not order:
        return jsonify({"payment_status": "not_found"}), 404

    return jsonify({
        "payment_status": order["payment_status"],
        "otp":            order["otp"] if order["payment_status"] == "paid" else None
    })


@app.route("/api/retrieval/status/<order_id>")
def retrieval_status(order_id):
    """ESP32 polls this to check if user has verified OTP for retrieval."""
    conn = get_db()
    order = conn.execute(
        "SELECT * FROM orders WHERE order_id=?", (order_id,)
    ).fetchone()
    conn.close()

    if not order:
        return jsonify({"verified": False}), 404

    return jsonify({"verified": bool(order["verified"])})

# ==========================================================
# TEST QR MATRIX FOR ESP32 TFT
# ==========================================================
@app.route('/api/testqr')
def testqr():

    upi_url = (
        "upi://pay?"
        "pa=7019007474@ptaxis&"
        "pn=Smart%20Locker&"
        "am=20.00&"
        "cu=INR&"
        "tn=Locker%20Payment"
    )

    qr = qrcode.QRCode(
        version=3,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=0
    )

    qr.add_data(upi_url)
    qr.make(fit=True)

    matrix = qr.get_matrix()

    data = []
    for row in matrix:
        data.append(
            ''.join(['1' if cell else '0' for cell in row])
        )

    return jsonify({
        "size": len(matrix),
        "data": data
    })

@app.route("/api/intrusion", methods=["POST"])
def report_intrusion():
    """ESP32 reports an intrusion event."""
    data = request.json
    locker_id = data.get("locker_id", "")
    order_id  = data.get("order_id", "")

    log_event(locker_id, order_id, "INTRUSION")

    conn = get_db()
    conn.execute(
        "UPDATE lockers SET intrusion_flag=1 WHERE locker_id=?", (locker_id,)
    )
    conn.commit()
    conn.close()

    send_telegram(f"🚨 INTRUSION ALERT!\nLocker: {locker_id}\nOrder: {order_id}\nTime: {datetime.now().strftime('%H:%M:%S')}")

    return jsonify({"logged": True})

@app.route("/api/intrusion/clear/<locker_id>")
def intrusion_clear(locker_id):
    """ESP32 polls this to know if staff has cleared the intrusion."""
    conn = get_db()
    locker = conn.execute(
        "SELECT intrusion_flag FROM lockers WHERE locker_id=?", (locker_id,)
    ).fetchone()

    cleared = locker and locker["intrusion_flag"] == 0
    conn.close()
    return jsonify({"cleared": cleared})

# ─────────────────────────────────────────────────────────────
#  PAYMENT WEBHOOK (Razorpay / Cashfree / manual)
# ─────────────────────────────────────────────────────────────
@app.route("/api/payment/confirm", methods=["POST"])
def payment_confirm():
    """
    Called when payment is confirmed.

    For production UPI:
      Option A: Use Razorpay's payment links webhook
      Option B: Use Cashfree Payment Gateway callback
      Option C: For demo/testing, call this manually from web UI

    POST body: { "order_id": "...", "utr": "UPI_UTR_NUMBER" }
    """
    data = request.json
    order_id = data.get("order_id")
    utr      = data.get("utr", "MANUAL")

    conn = get_db()
    order = conn.execute(
        "SELECT * FROM orders WHERE order_id=?", (order_id,)
    ).fetchone()

    if not order:
        conn.close()
        return jsonify({"error": "Order not found"}), 404

    otp = generate_otp(6)

    conn.execute(
        "UPDATE orders SET payment_status='paid', payment_ref=?, otp=? WHERE order_id=?",
        (utr, otp, order_id)
    )
    conn.execute(
        "UPDATE lockers SET status='payment_confirmed' WHERE locker_id=?",
        (order["locker_id"],)
    )
    conn.commit()
    conn.close()

    log_event(order["locker_id"], order_id, "PAYMENT_CONFIRMED", utr)

    # Send OTP to user via Telegram (in production: SMS/WhatsApp)
    send_telegram(
        f"✅ Payment confirmed for {order['user_name']}\n"
        f"Locker: {order['locker_id']}\n"
        f"🔑 Retrieval OTP: {otp}\n"
        f"Keep this OTP safe!"
    )

    return jsonify({"success": True, "otp": otp})

@app.route("/api/retrieval/verify", methods=["POST"])
def verify_retrieval():
    """
    User submits their OTP to retrieve items.
    POST body: { "order_id": "...", "otp": "123456" }
    """
    data     = request.json
    order_id = data.get("order_id")
    otp      = data.get("otp")

    conn = get_db()
    order = conn.execute(
        "SELECT * FROM orders WHERE order_id=?", (order_id,)
    ).fetchone()

    if not order:
        conn.close()
        return jsonify({"success": False, "message": "Order not found"}), 404

    if order["otp"] == otp and order["payment_status"] == "paid":
        conn.execute(
            "UPDATE orders SET verified=1 WHERE order_id=?", (order_id,)
        )
        conn.execute(
            "UPDATE lockers SET status='retrieval_pending' WHERE locker_id=?",
            (order["locker_id"],)
        )
        conn.commit()
        conn.close()
        log_event(order["locker_id"], order_id, "RETRIEVAL_VERIFIED")
        return jsonify({"success": True, "message": "OTP verified. Locker unlocking..."})
    else:
        conn.close()
        return jsonify({"success": False, "message": "Incorrect OTP"}), 401

# ─────────────────────────────────────────────────────────────
#  WEB UI ROUTES
# ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Main web UI for renting a locker."""
    conn   = get_db()
    lockers = conn.execute("SELECT * FROM lockers").fetchall()
    conn.close()
    return render_template_string(RENT_PAGE_HTML, lockers=lockers, price=PRICE_PER_HOUR)

@app.route("/rent", methods=["POST"])
def rent_locker():
    """Process a rental request — creates order and shows UPI QR."""
    locker_id      = request.form.get("locker_id")
    user_name      = request.form.get("name")
    user_phone     = request.form.get("phone")
    duration_hours = int(request.form.get("duration", 1))

    # Validate locker availability
    conn = get_db()
    locker = conn.execute(
        "SELECT * FROM lockers WHERE locker_id=? AND status='available'",
        (locker_id,)
    ).fetchone()

    if not locker:
        conn.close()
        return "<h2>Locker not available. Please try again.</h2>", 400

    order_id   = str(uuid.uuid4())
    amount     = PRICE_PER_HOUR * duration_hours
    created_at = time.time()
    expires_at = created_at + (duration_hours * 3600) + 300  # +5 min grace

    conn.execute(
        """INSERT INTO orders
           (order_id, locker_id, user_name, user_phone, amount, duration_hours, created_at, expires_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (order_id, locker_id, user_name, user_phone, amount, duration_hours, created_at, expires_at)
    )
    conn.execute(
        "UPDATE lockers SET status='payment_pending', current_order=? WHERE locker_id=?",
        (order_id, locker_id)
    )
    conn.commit()
    conn.close()

    log_event(locker_id, order_id, "ORDER_CREATED")

    upi_url = generate_upi_url(order_id, amount, "Locker rental")
    qr_img  = generate_qr_base64(upi_url)

    return render_template_string(
        PAYMENT_PAGE_HTML,
        order_id=order_id,
        amount=amount,
        user_name=user_name,
        locker_id=locker_id,
        duration=duration_hours,
        upi_url=upi_url,
        qr_img=qr_img
    )

@app.route("/retrieve")
def retrieve_page():
    """Page for user to enter OTP and retrieve items."""
    order_id = request.args.get("order_id", "")
    return render_template_string(RETRIEVE_PAGE_HTML, order_id=order_id)

@app.route("/admin")
def admin_page():
    """Simple admin dashboard."""
    conn = get_db()
    orders = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    events = conn.execute(
        "SELECT * FROM events ORDER BY timestamp DESC LIMIT 30"
    ).fetchall()
    lockers = conn.execute("SELECT * FROM lockers").fetchall()
    conn.close()
    return render_template_string(ADMIN_PAGE_HTML, orders=orders, events=events, lockers=lockers)

@app.route("/admin/clear_intrusion/<locker_id>")
def clear_intrusion(locker_id):
    """Admin clears intrusion flag."""
    conn = get_db()
    conn.execute(
        "UPDATE lockers SET intrusion_flag=0, status='available', current_order=NULL WHERE locker_id=?",
        (locker_id,)
    )
    conn.commit()
    conn.close()
    return jsonify({"cleared": True})

@app.route("/admin/reset_locker/<locker_id>")
def reset_locker(locker_id):
    """Admin manually resets locker to available."""
    conn = get_db()
    conn.execute(
        "UPDATE lockers SET status='available', current_order=NULL, intrusion_flag=0 WHERE locker_id=?",
        (locker_id,)
    )
    conn.commit()
    conn.close()
    return jsonify({"reset": True})


# ─────────────────────────────────────────────────────────────
#  HTML TEMPLATES
# ─────────────────────────────────────────────────────────────

RENT_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Smart Locker — Rent</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: sans-serif; background: #f0f4f8; color: #222; padding: 20px; }
    .card { background: white; border-radius: 12px; padding: 24px; max-width: 400px;
            margin: 20px auto; box-shadow: 0 2px 12px rgba(0,0,0,0.1); }
    h1 { color: #1a56db; margin-bottom: 6px; }
    .subtitle { color: #666; margin-bottom: 24px; font-size: 14px; }
    label { display: block; margin-bottom: 4px; font-weight: 600; font-size: 14px; }
    input, select { width: 100%; padding: 10px 12px; border: 1.5px solid #ddd;
                    border-radius: 8px; font-size: 15px; margin-bottom: 16px; }
    input:focus, select:focus { outline: none; border-color: #1a56db; }
    button { width: 100%; background: #1a56db; color: white; border: none;
             padding: 13px; border-radius: 8px; font-size: 16px; cursor: pointer; }
    button:hover { background: #1447b8; }
    .locker-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
    .locker-btn { border: 2px solid #ddd; border-radius: 8px; padding: 12px 8px;
                  text-align: center; cursor: pointer; background: white; }
    .locker-btn.available { border-color: #16a34a; color: #16a34a; }
    .locker-btn.selected  { background: #1a56db; color: white; border-color: #1a56db; }
    .locker-btn.occupied  { border-color: #dc2626; color: #999; cursor: not-allowed; }
    .price { color: #1a56db; font-weight: bold; }
    #amount-display { font-size: 18px; font-weight: bold; color: #1a56db; margin-bottom: 16px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>🔒 Smart Locker</h1>
    <p class="subtitle">Secure self-service storage — pay per hour</p>

    <form action="/rent" method="post">
      <label>Your Name</label>
      <input type="text" name="name" placeholder="Enter your name" required>

      <label>Phone Number</label>
      <input type="tel" name="phone" placeholder="10-digit mobile number" required pattern="[0-9]{10}">

      <label>Select Locker</label>
      <div class="locker-grid">
        {% for locker in lockers %}
        <label class="locker-btn {% if locker.status == 'available' %}available{% else %}occupied{% endif %}"
               id="btn-{{locker.locker_id}}">
          <input type="radio" name="locker_id" value="{{locker.locker_id}}"
                 {% if locker.status != 'available' %}disabled{% endif %}
                 onchange="selectLocker(this)" style="display:none">
          <div style="font-weight:700">{{locker.locker_id}}</div>
          <div style="font-size:12px;margin-top:4px">
            {% if locker.status == 'available' %}✅ Available{% else %}🔴 Occupied{% endif %}
          </div>
        </label>
        {% endfor %}
      </div>

      <label>Duration</label>
      <select name="duration" onchange="updatePrice(this.value)">
        <option value="1">1 Hour — ₹{{price}}</option>
        <option value="2">2 Hours — ₹{{price * 2}}</option>
        <option value="3">3 Hours — ₹{{price * 3}}</option>
        <option value="6">6 Hours — ₹{{price * 6}}</option>
        <option value="12">12 Hours — ₹{{price * 12}}</option>
      </select>

      <div id="amount-display">Total: ₹{{price}}</div>

      <button type="submit">Continue to Payment →</button>
    </form>
  </div>

  <script>
    const price = {{ price }};
    function updatePrice(h) {
      document.getElementById('amount-display').textContent = 'Total: ₹' + (price * h);
    }
    function selectLocker(radio) {
      document.querySelectorAll('.locker-btn').forEach(b => b.classList.remove('selected'));
      document.getElementById('btn-' + radio.value).classList.add('selected');
    }
  </script>
</body>
</html>
"""

PAYMENT_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Pay for Locker</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: sans-serif; background: #f0f4f8; padding: 20px; }
    .card { background: white; border-radius: 12px; padding: 24px; max-width: 420px;
            margin: 20px auto; box-shadow: 0 2px 12px rgba(0,0,0,0.1); text-align: center; }
    h2 { color: #1a56db; margin-bottom: 4px; }
    .amount { font-size: 32px; font-weight: 800; color: #16a34a; margin: 12px 0; }
    .info { background: #f8fafc; border-radius: 8px; padding: 12px; margin: 16px 0;
            font-size: 14px; text-align: left; }
    .info div { margin-bottom: 6px; }
    .qr-wrap { border: 2px solid #e2e8f0; border-radius: 12px; padding: 16px;
               display: inline-block; margin: 16px 0; }
    .qr-wrap img { width: 200px; height: 200px; }
    .upi-apps { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin: 16px 0; }
    .upi-btn { background: #1a56db; color: white; text-decoration: none; padding: 10px 16px;
               border-radius: 8px; font-size: 14px; font-weight: 600; }
    .upi-btn.gpay   { background: #4285f4; }
    .upi-btn.pp     { background: #5f0096; }
    .upi-btn.paytm  { background: #002970; }
    .note { font-size: 12px; color: #666; margin: 12px 0; }
    .separator { margin: 16px 0; border: none; border-top: 1px solid #e2e8f0; }
    #confirm-section { margin-top: 16px; }
    input { width: 100%; padding: 10px 12px; border: 1.5px solid #ddd;
            border-radius: 8px; font-size: 15px; margin-bottom: 12px; }
    button { width: 100%; background: #16a34a; color: white; border: none;
             padding: 12px; border-radius: 8px; font-size: 15px; cursor: pointer; font-weight: 600; }
    #status-msg { margin-top: 12px; padding: 10px; border-radius: 8px; display: none; font-weight: 600; }
    #status-msg.success { background: #dcfce7; color: #16a34a; display: block; }
    #status-msg.error   { background: #fee2e2; color: #dc2626; display: block; }
  </style>
</head>
<body>
  <div class="card">
    <h2>Complete Payment</h2>
    <div class="amount">₹{{ amount }}</div>

    <div class="info">
      <div><strong>Name:</strong> {{ user_name }}</div>
      <div><strong>Locker:</strong> {{ locker_id }}</div>
      <div><strong>Duration:</strong> {{ duration }} hour(s)</div>
      <div><strong>Order:</strong> {{ order_id[:16] }}...</div>
    </div>

    <p style="font-size:14px; margin-bottom:8px;"><strong>Scan QR with any UPI app:</strong></p>
    <div class="qr-wrap">
      <img src="data:image/png;base64,{{ qr_img }}" alt="UPI QR Code">
    </div>

    <div class="upi-apps">
      <a class="upi-btn gpay"  href="{{ upi_url }}">Google Pay</a>
      <a class="upi-btn pp"    href="{{ upi_url }}">PhonePe</a>
      <a class="upi-btn paytm" href="{{ upi_url }}">Paytm</a>
    </div>

    <p class="note">
      Tap a button to open your UPI app directly.<br>
      Or scan the QR code above.
    </p>

    <hr class="separator">

    <div id="confirm-section">
      <p style="font-size:14px; margin-bottom:10px;">
        <strong>After payment, enter UTR/Reference number:</strong>
      </p>
      <input type="text" id="utr" placeholder="e.g. 421234567890 (12-digit UTR)">
      <button onclick="confirmPayment()">Confirm Payment ✓</button>
      <div id="status-msg"></div>
    </div>

    <p class="note" style="margin-top:16px;">
      After confirming, you will receive a 6-digit OTP.<br>
      Keep it safe — you'll need it to retrieve your items.
    </p>
  </div>

  <script>
    const ORDER_ID = "{{ order_id }}";

    async function confirmPayment() {
      const utr = document.getElementById('utr').value.trim();
      if (!utr) {
        alert('Please enter the UTR / reference number from your UPI app.');
        return;
      }
      const res  = await fetch('/api/payment/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order_id: ORDER_ID, utr })
      });
      const data = await res.json();
      const msg  = document.getElementById('status-msg');
      if (data.success) {
        msg.className = 'success';
        msg.textContent = '✅ Payment confirmed! Your OTP: ' + data.otp + '  (Save this!)';
        document.getElementById('confirm-section').innerHTML +=
          '<p style="margin-top:16px;font-size:14px">→ <a href="/retrieve?order_id=' + ORDER_ID + '">Go to Retrieval page</a></p>';
      } else {
        msg.className = 'error';
        msg.textContent = '❌ ' + (data.error || 'Confirmation failed. Try again.');
      }
    }
  </script>
</body>
</html>
"""

RETRIEVE_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Retrieve Items</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: sans-serif; background: #f0f4f8; padding: 20px; }
    .card { background: white; border-radius: 12px; padding: 24px; max-width: 380px;
            margin: 20px auto; box-shadow: 0 2px 12px rgba(0,0,0,0.1); text-align: center; }
    h2 { color: #1a56db; margin-bottom: 8px; }
    p { color: #555; font-size: 14px; margin-bottom: 20px; }
    input { width: 100%; padding: 14px 12px; border: 1.5px solid #ddd; border-radius: 8px;
            font-size: 22px; letter-spacing: 8px; text-align: center; margin-bottom: 16px; }
    button { width: 100%; background: #1a56db; color: white; border: none;
             padding: 13px; border-radius: 8px; font-size: 16px; cursor: pointer; }
    #msg { margin-top: 14px; padding: 12px; border-radius: 8px; display: none; font-weight: 600; }
    #msg.ok  { background: #dcfce7; color: #16a34a; display: block; }
    #msg.err { background: #fee2e2; color: #dc2626; display: block; }
    .order-input { font-size: 14px; letter-spacing: 0; text-align: left; }
  </style>
</head>
<body>
  <div class="card">
    <h2>🔓 Retrieve Items</h2>
    <p>Enter your 6-digit OTP to unlock the locker and collect your belongings.</p>

    <label style="font-size:12px; font-weight:600; text-align:left; display:block; margin-bottom:4px;">
      Order ID (from confirmation page)
    </label>
    <input class="order-input" type="text" id="order-id" value="{{ order_id }}" placeholder="Order ID">

    <label style="font-size:12px; font-weight:600; text-align:left; display:block; margin-bottom:4px; margin-top:8px;">
      OTP (6 digits)
    </label>
    <input type="number" id="otp" placeholder="------" maxlength="6"
           oninput="if(this.value.length>6) this.value=this.value.slice(0,6)">

    <button onclick="verifyOTP()">Unlock Locker →</button>
    <div id="msg"></div>
  </div>

  <script>
    async function verifyOTP() {
      const order_id = document.getElementById('order-id').value.trim();
      const otp      = document.getElementById('otp').value.trim();
      if (!order_id || otp.length !== 6) {
        alert('Please enter both Order ID and 6-digit OTP.');
        return;
      }
      const res  = await fetch('/api/retrieval/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order_id, otp })
      });
      const data = await res.json();
      const msg  = document.getElementById('msg');
      if (data.success) {
        msg.className = 'ok';
        msg.textContent = '✅ Verified! Locker is unlocking — collect your items.';
      } else {
        msg.className = 'err';
        msg.textContent = '❌ ' + (data.message || 'Incorrect OTP. Try again.');
      }
    }
  </script>
</body>
</html>
"""

ADMIN_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Locker Admin</title>
  <style>
    body { font-family: sans-serif; padding: 20px; background: #f0f4f8; }
    h2 { margin-bottom: 16px; color: #1a56db; }
    table { width: 100%; border-collapse: collapse; background: white;
            border-radius: 8px; overflow: hidden; margin-bottom: 24px;
            box-shadow: 0 1px 6px rgba(0,0,0,0.08); }
    th { background: #1a56db; color: white; padding: 10px 12px; text-align: left; font-size: 13px; }
    td { padding: 9px 12px; font-size: 13px; border-bottom: 1px solid #f1f5f9; }
    tr:hover td { background: #f8fafc; }
    .tag { padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
    .paid { background: #dcfce7; color: #16a34a; }
    .pending { background: #fef9c3; color: #854d0e; }
    .available { background: #dcfce7; color: #16a34a; }
    .occupied { background: #fee2e2; color: #dc2626; }
    .btn { background: #1a56db; color: white; border: none; padding: 6px 12px;
           border-radius: 6px; cursor: pointer; font-size: 12px; text-decoration: none; }
    .btn.red { background: #dc2626; }
  </style>
</head>
<body>
  <h2>🔒 Locker Admin Dashboard</h2>

  <h3>Lockers</h3>
  <table>
    <tr><th>Locker ID</th><th>Status</th><th>Intrusion</th><th>Actions</th></tr>
    {% for l in lockers %}
    <tr>
      <td>{{ l.locker_id }}</td>
      <td><span class="tag {% if l.status == 'available' %}available{% else %}occupied{% endif %}">
        {{ l.status }}</span></td>
      <td>{% if l.intrusion_flag %}🚨 YES{% else %}—{% endif %}</td>
      <td>
        <a class="btn" href="/admin/reset_locker/{{ l.locker_id }}">Reset</a>
        {% if l.intrusion_flag %}
        <a class="btn red" href="/admin/clear_intrusion/{{ l.locker_id }}" style="margin-left:6px">Clear Alarm</a>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </table>

  <h3>Recent Orders</h3>
  <table>
    <tr><th>Order ID</th><th>Locker</th><th>User</th><th>Amount</th><th>Status</th><th>OTP</th></tr>
    {% for o in orders %}
    <tr>
      <td>{{ o.order_id[:12] }}...</td>
      <td>{{ o.locker_id }}</td>
      <td>{{ o.user_name }}<br><small>{{ o.user_phone }}</small></td>
      <td>₹{{ o.amount }}</td>
      <td><span class="tag {% if o.payment_status == 'paid' %}paid{% else %}pending{% endif %}">
        {{ o.payment_status }}</span></td>
      <td>{{ o.otp or '—' }}</td>
    </tr>
    {% endfor %}
  </table>

  <h3>Event Log</h3>
  <table>
    <tr><th>Time</th><th>Locker</th><th>Event</th><th>Details</th></tr>
    {% for e in events %}
    <tr>
      <td>{{ e.timestamp | int }}</td>
      <td>{{ e.locker_id }}</td>
      <td>{{ e.event_type }}</td>
      <td>{{ e.details or '—' }}</td>
    </tr>
    {% endfor %}
  </table>
</body>
</html>
"""

# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("=" * 50)
    print("  Smart Locker Backend Running")
    print("  Web UI:   http://localhost:5000")
    print("  Admin:    http://localhost:5000/admin")
    print("  Retrieve: http://localhost:5000/retrieve")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)
