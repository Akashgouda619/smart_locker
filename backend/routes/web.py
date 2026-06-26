import io
import base64
import time
import qrcode
from flask import Blueprint, render_template_string, request, jsonify, Response
from functools import wraps
from database.db import get_db_connection
from models.locker import LockerModel
from models.booking import BookingModel
from models.user import UserModel
from models.otp import OTPModel
from services.booking_service import BookingService
from services.payment_service import PaymentService
from utils.upi import generate_upi_link
from config import Config

# Basic Auth Decorator for Admin Dashboard Security
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not (auth.username == "admin" and auth.password == "admin123"):
            return Response(
                "Could not verify your access level for that URL.\n"
                "You have to login with proper credentials (admin / admin123)", 401,
                {"WWW-Authenticate": 'Basic realm="Login Required"'}
            )
        return f(*args, **kwargs)
    return decorated

web_bp = Blueprint("web", __name__)

# ─── PREMIUM CSS DESIGN SYSTEM & LAYOUTS ────────────────────────────────────

RENT_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Smart Locker Portal</title>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #000000;
      --card-bg: #0c0c0e;
      --border: #3f3f46;
      --text: #ffffff;
      --text-muted: #a3a3a3;
      --primary: #ffffff;
      --primary-hover: #e5e5e5;
      --primary-text: #000000;
      --success: #22c55e;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Outfit', sans-serif; }
    body {
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .container {
      background: var(--card-bg);
      border: 1px solid #ffffff;
      border-radius: 24px;
      padding: 40px;
      width: 100%;
      max-width: 480px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8);
    }
    h2 {
      font-size: 26px;
      font-weight: 700;
      text-align: center;
      margin-bottom: 6px;
      color: var(--text);
    }
    .subtitle {
      font-size: 13px;
      color: var(--text-muted);
      text-align: center;
      margin-bottom: 32px;
    }
    label {
      display: block;
      margin-bottom: 8px;
      font-weight: 600;
      font-size: 13px;
      color: var(--text);
    }
    input, select {
      width: 100%;
      padding: 14px;
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 12px;
      font-size: 15px;
      color: #000000;
      margin-bottom: 20px;
      transition: border-color 0.2s;
    }
    input:focus, select:focus {
      outline: none;
      border-color: #ffffff;
    }
    
    .locker-grid {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-bottom: 20px;
    }
    .locker-card {
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      background: #121212;
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
      transition: all 0.2s;
    }
    .locker-card.available:hover {
      border-color: #ffffff;
    }
    .locker-card.selected {
      background: #ffffff;
      border-color: #ffffff;
    }
    .locker-card.selected .locker-info h4 {
      color: #000000;
    }
    .locker-card.selected .locker-info p {
      color: #525252;
    }
    .locker-card.occupied {
      opacity: 0.3;
      cursor: not-allowed;
    }
    
    .locker-info h4 {
      font-size: 15px;
      font-weight: 600;
      color: var(--text);
    }
    .locker-info p {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 2px;
    }
    
    .status-tag {
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 6px;
      text-transform: uppercase;
      display: inline-block;
    }
    .status-tag.available {
      background: rgba(34, 197, 94, 0.15);
      color: #22c55e;
      border: 1px solid rgba(34, 197, 94, 0.3);
    }
    .status-tag.occupied {
      background: rgba(239, 68, 68, 0.15);
      color: #ef4444;
      border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .locker-card.selected .status-tag.available {
      background: #22c55e;
      color: #ffffff;
      border: none;
    }
    
    .price-display {
      font-size: 18px;
      font-weight: 700;
      margin-bottom: 24px;
      text-align: right;
      color: var(--text);
    }
    .price-display span {
      color: var(--success);
    }
    
    button {
      width: 100%;
      background: var(--primary);
      color: var(--primary-text);
      border: none;
      padding: 16px;
      border-radius: 12px;
      font-size: 16px;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.2s;
    }
    button:hover {
      background: var(--primary-hover);
    }
    
    .nav-links {
      margin-top: 24px;
      text-align: center;
    }
    .nav-links a {
      color: var(--text-muted);
      text-decoration: none;
      font-size: 14px;
      font-weight: 600;
    }
    .nav-links a:hover {
      color: #ffffff;
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <div class="container">
    <h2>Premium Locker Storage</h2>
    <p class="subtitle">Premium self-service rental storage — pay per hour</p>

    <form action="/rent" method="post">
      <label>Your Full Name</label>
      <input type="text" name="name" placeholder="Enter your name" required>

      <label>Phone Number (for retrieval OTP)</label>
      <input type="tel" name="phone" placeholder="10-digit mobile number" required pattern="[0-9]{10}">

      <label>Select Available Locker</label>
      <div class="locker-grid">
        {% for locker in lockers %}
        <div class="locker-card {% if locker.status == 'available' %}available selected{% else %}occupied{% endif %}"
             id="card-{{locker.locker_id}}" onclick="selectLocker('{{locker.locker_id}}', '{{locker.status}}')">
          <input type="radio" name="locker_id" value="{{locker.locker_id}}" id="radio-{{locker.locker_id}}"
                 {% if locker.status != 'available' %}disabled{% else %}checked{% endif %} style="display:none" required>
          <div class="locker-info">
            <h4>Locker {{locker.locker_number}}</h4>
            <p>{{locker.location}} • Size: {{locker.size}}</p>
          </div>
          <div>
            <span class="status-tag {{locker.status}}">{{locker.status}}</span>
          </div>
        </div>
        {% endfor %}
      </div>

      <label>Rental Duration</label>
      <select name="duration" onchange="updatePrice(this.value)">
        <option value="1">1 Hour — ₹{{price}}</option>
        <option value="2">2 Hours — ₹{{price * 2}}</option>
        <option value="3">3 Hours — ₹{{price * 3}}</option>
        <option value="6">6 Hours — ₹{{price * 6}}</option>
        <option value="12">12 Hours — ₹{{price * 12}}</option>
      </select>

      <div class="price-display">Total Amount: <span id="amount-display">₹{{price}}</span></div>

      <button type="submit">Proceed to Payment →</button>
    </form>

    <div class="nav-links">
      <a href="/retrieve">Retrieve Items 🔓</a>
    </div>
  </div>

  <script>
    function updatePrice(hours) {
      const price = {{ price }};
      document.getElementById('amount-display').textContent = '₹' + (price * hours);
    }

    function selectLocker(lockerId, status) {
      if (status !== 'available') return;
      document.querySelectorAll('.locker-card').forEach(c => c.classList.remove('selected'));
      document.getElementById('card-' + lockerId).classList.add('selected');
      const radio = document.getElementById('radio-' + lockerId);
      if (radio) radio.checked = true;
    }
  </script>
</body>
</html>
"""

PAYMENT_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Payment — Smart Locker</title>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #000000;
      --card-bg: #0c0c0e;
      --border: #3f3f46;
      --text: #ffffff;
      --text-muted: #a3a3a3;
      --primary: #ffffff;
      --primary-hover: #e5e5e5;
      --primary-text: #000000;
      --success: #22c55e;
      --error: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Outfit', sans-serif; }
    body {
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .container {
      background: var(--card-bg);
      border: 1px solid #ffffff;
      border-radius: 16px;
      padding: 32px;
      width: 100%;
      max-width: 480px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8);
      text-align: center;
    }
    h2 { font-size: 24px; font-weight: 700; margin-bottom: 20px; color: var(--text); }
    .amount { font-size: 40px; font-weight: 800; color: var(--success); margin-bottom: 20px; }
    .info-box {
      background: #121212;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      text-align: left;
      margin-bottom: 24px;
      font-size: 14px;
    }
    .info-row { display: flex; justify-content: space-between; margin-bottom: 8px; }
    .info-row:last-child { margin-bottom: 0; }
    .info-label { color: var(--text-muted); }
    .info-val { font-weight: 600; color: var(--text); }
    
    .instruction-box {
      background: #121212;
      border: 1px solid var(--border);
      color: var(--text-muted);
      border-radius: 12px;
      padding: 16px;
      text-align: left;
      font-size: 13px;
      line-height: 1.5;
      margin-bottom: 24px;
    }
    
    hr { border: none; border-top: 1px solid var(--border); margin: 24px 0; }
    
    input {
      width: 100%;
      padding: 14px;
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 8px;
      font-size: 15px;
      color: #000000;
      margin-bottom: 16px;
      transition: border-color 0.2s;
      text-align: center;
    }
    input:focus {
      outline: none;
      border-color: #ffffff;
    }
    
    button {
      width: 100%;
      background: var(--success);
      color: white;
      border: none;
      padding: 16px;
      border-radius: 8px;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      transition: background-color 0.2s;
    }
    button:hover { background: #15803d; }
    button.primary-btn { background: var(--primary); color: var(--primary-text); }
    button.primary-btn:hover { background: var(--primary-hover); }
    button.btn-cancel {
      background: rgba(239, 68, 68, 0.08);
      border: 1px solid rgba(239, 68, 68, 0.2);
      color: #ef4444;
      margin-top: 12px;
    }
    button.btn-cancel:hover {
      background: #ef4444;
      color: white;
    }
    
    #status-msg {
      padding: 14px;
      border-radius: 8px;
      font-weight: 600;
      font-size: 13px;
      margin-top: 16px;
      display: none;
      text-align: center;
    }
    #status-msg.success { background: rgba(34, 197, 94, 0.15); color: var(--success); border: 1px solid rgba(34, 197, 94, 0.3); display: block; }
    #status-msg.error { background: rgba(239, 68, 68, 0.15); color: var(--error); border: 1px solid rgba(239, 68, 68, 0.3); display: block; }
  </style>
</head>
<body>
  <div class="container">
    <h2>Complete Locker Payment</h2>
    <div class="amount">₹{{ amount }}</div>

    <div class="info-box">
      <div class="info-row"><span class="info-label">Name</span><span class="info-val">{{ user_name }}</span></div>
      <div class="info-row"><span class="info-label">Locker ID</span><span class="info-val">{{ locker_id }}</span></div>
      <div class="info-row"><span class="info-label">Duration</span><span class="info-val">{{ duration }} hour(s)</span></div>
      <div class="info-row"><span class="info-label">Booking ID</span><span class="info-val">#{{ booking_id }}</span></div>
    </div>

    <div class="instruction-box">
      <strong>How to Pay:</strong>
      <ol style="margin-left: 20px; margin-top: 8px;">
        <li>Scan the QR code displayed on the physical locker screen.</li>
        <li>Complete payment of ₹{{ amount }} using GPay, PhonePe, or Paytm.</li>
        <li>Enter the 12-digit transaction Reference No. / UTR below to unlock your locker.</li>
      </ol>
    </div>

    <hr>

    <div id="confirm-section">
      <div style="margin-bottom: 20px; text-align: left;">
        <label for="utr-input" style="font-size: 13px; font-weight: 600; color: var(--text-muted); display: block; margin-bottom: 8px;">
          Enter 12-Digit UPI Ref No. / UTR
        </label>
        <input type="text" id="utr-input" placeholder="e.g. 123456789012" maxlength="12">
        <button class="primary-btn" onclick="submitPaymentUTR()" id="confirm-btn">Confirm Payment ✓</button>
        <button class="btn-cancel" onclick="cancelOrder()" id="cancel-btn">Cancel Order ✕</button>
      </div>
      <div id="status-msg"></div>
    </div>
  </div>

  <script>
    const BOOKING_ID = "{{ booking_id }}";

    function showPaymentSuccessUI() {
      const confirmSec = document.getElementById('confirm-section');
      if (confirmSec) {
        confirmSec.innerHTML = 
          '<div class="success" style="padding: 16px; border-radius: 12px; background: rgba(34, 197, 94, 0.15); border: 1px solid rgba(34, 197, 94, 0.3); margin-bottom: 16px;">' +
          '  <p style="font-size:14px; font-weight:600; color:var(--success)">✅ Payment Detected! Locker Open.</p>' +
          '  <p style="font-size:12px; color:var(--text-muted); margin-top: 4px;">Store items now. Pressing CLOSE DOOR locks the locker and starts your timer.</p>' +
          '</div>' +
          '<button class="primary-btn" onclick="closeStorageDoor()">🔒 CLOSE DOOR</button>' +
          '<div id="status-msg"></div>';
      }
    }

    async function submitPaymentUTR() {
      const utr = document.getElementById('utr-input').value.trim();
      if (!/^\\d{12}$/.test(utr)) {
        alert("Please enter a valid 12-digit numeric UPI Ref No. / UTR.");
        return;
      }
      
      const confirmBtn = document.getElementById('confirm-btn');
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Verifying UTR...';
      
      try {
        const res = await fetch('/api/payment/confirm', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ order_id: BOOKING_ID, utr: utr })
        });
        const data = await res.json();
        const msg = document.getElementById('status-msg');
        if (data.success) {
          showPaymentSuccessUI();
        } else {
          msg.className = 'error';
          msg.textContent = '❌ Verification Failed: ' + data.message;
          msg.style.display = 'block';
          confirmBtn.disabled = false;
          confirmBtn.textContent = 'Confirm Payment ✓';
        }
      } catch (err) {
        console.error("Error confirming payment:", err);
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Confirm Payment ✓';
      }
    }

    async function cancelOrder() {
      if (!confirm("Are you sure you want to cancel this booking?")) return;
      const cancelBtn = document.getElementById('cancel-btn');
      cancelBtn.disabled = true;
      cancelBtn.textContent = 'Cancelling...';
      try {
        const res = await fetch('/api/web/cancel', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ booking_id: BOOKING_ID })
        });
        const data = await res.json();
        if (data.success) {
          alert('Booking cancelled successfully.');
          window.location.href = '/';
        } else {
          alert('Failed to cancel booking: ' + data.message);
          cancelBtn.disabled = false;
          cancelBtn.textContent = 'Cancel Order ✕';
        }
      } catch (err) {
        console.error("Error cancelling booking:", err);
        cancelBtn.disabled = false;
        cancelBtn.textContent = 'Cancel Order ✕';
      }
    }

    // Poll payment status every 2 seconds for automatic detection
    let pollInterval = setInterval(async () => {
      try {
        const res = await fetch('/api/payment/check-status/' + BOOKING_ID);
        const data = await res.json();
        if (data.success && data.paid) {
          clearInterval(pollInterval);
          showPaymentSuccessUI();
        }
      } catch (err) {
        console.error("Error polling payment status:", err);
      }
    }, 2000);

    async function closeStorageDoor() {
      const res = await fetch('/api/web/close-storage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ booking_id: BOOKING_ID })
      });
      const data = await res.json();
      if (data.success) {
        document.getElementById('confirm-section').innerHTML = 
          '<div class="success" style="padding: 16px; border-radius: 12px; background: rgba(34, 197, 94, 0.15); border: 1px solid rgba(34, 197, 94, 0.3);">' +
          '  <p style="font-size:15px; font-weight:700; color:var(--success)">🔒 Locker Locked Successfully!</p>' +
          '  <p style="font-size:13px; color:#a3a3a3; margin-top: 8px;">Your rental timer has started on the TFT screen.</p>' +
          '  <p style="font-size:13px; color:#a3a3a3; margin-top: 4px;">For retrieval later, click below:</p>' +
          '  <p style="margin-top: 16px;"><a href="/retrieve?booking_id=' + BOOKING_ID + '" style="color:#ffffff; font-weight:bold; text-decoration:underline;">Go to Retrieval Page →</a></p>' +
          '</div>';
      } else {
        alert("Failed to close door: " + data.message);
      }
    }
  </script>
</body>
</html>
"""

RETRIEVE_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Retrieve Storage — Smart Locker</title>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #000000;
      --card-bg: #0c0c0e;
      --border: #3f3f46;
      --text: #ffffff;
      --text-muted: #a3a3a3;
      --primary: #ffffff;
      --primary-hover: #e5e5e5;
      --primary-text: #000000;
      --success: #22c55e;
      --error: #ef4444;
      --warning: #f97316;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Outfit', sans-serif; }
    body {
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .container {
      background: var(--card-bg);
      border: 1px solid #ffffff;
      border-radius: 24px;
      padding: 40px;
      width: 100%;
      max-width: 480px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8);
      text-align: center;
    }
    h2 { font-size: 26px; font-weight: 700; margin-bottom: 8px; color: var(--text); }
    p.desc { font-size: 14px; color: var(--text-muted); margin-bottom: 32px; }
    label { display: block; margin-bottom: 8px; font-weight: 600; text-align: left; font-size: 13px; color: var(--text); }
    
    input {
      width: 100%;
      padding: 14px;
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 12px;
      font-size: 16px;
      color: #000000;
      text-align: center;
      margin-bottom: 20px;
    }
    
    button {
      width: 100%;
      background: var(--primary);
      color: var(--primary-text);
      border: none;
      padding: 16px;
      border-radius: 12px;
      font-size: 16px;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.2s;
      margin-bottom: 16px;
    }
    button:hover { background: var(--primary-hover); }
    button.btn-sec { background: #121212; border: 1px solid var(--border); color: var(--text-muted); }
    button.btn-sec:hover { background: #1a1a1a; color: var(--text); }
    button.btn-success { background: var(--success); color: #ffffff; }
    button.btn-success:hover { background: #15803d; }
    
    .otp-alert {
      background: rgba(249, 115, 22, 0.1);
      border: 1px solid rgba(249, 115, 22, 0.3);
      color: var(--warning);
      padding: 16px;
      border-radius: 12px;
      font-size: 14px;
      font-weight: 600;
      margin-bottom: 24px;
      text-align: center;
      display: none;
    }
    .otp-code { font-size: 24px; font-weight: 800; display: block; margin-top: 8px; letter-spacing: 4px; color: var(--text); }
    
    #msg {
      padding: 16px;
      border-radius: 12px;
      font-weight: 600;
      font-size: 14px;
      margin-top: 16px;
      display: none;
    }
    #msg.ok { background: rgba(34, 197, 94, 0.15); color: var(--success); border: 1px solid rgba(34, 197, 94, 0.3); display: block; }
    #msg.err { background: rgba(239, 68, 68, 0.15); color: var(--error); border: 1px solid rgba(239, 68, 68, 0.3); display: block; }
    
    .home-link { display: inline-block; margin-top: 20px; color: var(--text-muted); text-decoration: none; font-size: 14px; font-weight: 600; }
    .home-link:hover { color: #ffffff; text-decoration: underline; }
  </style>
</head>
<body>
  <div class="container" id="main-content">
    <h2>🔓 Retrieve Items</h2>
    <p class="desc">Request OTP and verify code to unlock your locker.</p>

    <!-- OTP code is displayed on TFT screen -->

    <div id="otp-request-section">
      <label>Enter Booking ID</label>
      <input type="number" id="booking-id" value="{{ booking_id }}" placeholder="e.g. 1">
      <button onclick="requestOTP()">Generate Retrieval OTP →</button>
    </div>

    <div id="otp-verify-section" style="display:none;">
      <label>Enter 6-Digit OTP</label>
      <input type="text" id="otp" placeholder="------" maxlength="6">
      <button class="btn-success" onclick="verifyOTP()">Verify OTP & Unlock Locker</button>
      <button class="btn-sec" onclick="backToRequest()">Cancel</button>
    </div>

    <div id="msg"></div>
    <a href="/" class="home-link">← Back to Rent Page</a>
  </div>

  <script>
    async function requestOTP() {
      const bookingId = document.getElementById('booking-id').value.trim();
      if (!bookingId) {
        alert('Please enter your Booking ID.');
        return;
      }
      
      const res = await fetch('/api/web/generate-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ booking_id: bookingId })
      });
      const data = await res.json();
      const msg = document.getElementById('msg');
      
      if (data.success) {
        msg.className = 'ok';
        msg.textContent = "🔑 OTP Code is displayed on the locker's TFT screen! Please read it and enter below.";
        msg.style.display = 'block';
        document.getElementById('otp-request-section').style.display = 'none';
        document.getElementById('otp-verify-section').style.display = 'block';
      } else {
        msg.className = 'err';
        msg.textContent = '❌ ' + (data.message || 'Failed to request OTP. Make sure your locker is actively rented.');
        msg.style.display = 'block';
      }
    }

    async function verifyOTP() {
      const bookingId = document.getElementById('booking-id').value.trim();
      const otp = document.getElementById('otp').value.trim();
      if (otp.length !== 6) {
        alert('Please enter a 6-digit OTP code.');
        return;
      }
      
      const res = await fetch('/api/web/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ booking_id: bookingId, otp })
      });
      const data = await res.json();
      const msg = document.getElementById('msg');
      
      if (data.success) {
        // Transition to retrieval close screen
        document.getElementById('main-content').innerHTML = 
          '<h2>🔓 Retrieval Approved</h2>' +
          '<p class="desc">Locker unlocked. Collect your items from the locker.</p>' +
          '<div class="success" style="padding: 16px; border-radius: 12px; background: rgba(34, 197, 94, 0.15); border: 1px solid rgba(34, 197, 94, 0.3); margin-bottom: 24px; text-align: left;">' +
          '  <p style="font-size:14px; font-weight:600; color:var(--success)">✅ OTP Verified. Locker Open.</p>' +
          '  <p style="font-size:12px; color:var(--text-muted); margin-top: 4px;">Collect your items now. Click CLOSE LOCKER below once completed.</p>' +
          '</div>' +
          '<button class="primary-btn btn-success" onclick="closeRetrievalLocker(' + bookingId + ')">🔒 CLOSE LOCKER</button>' +
          '<div id="msg"></div>';
      } else {
        msg.className = 'err';
        msg.textContent = '❌ ' + (data.message || 'Incorrect OTP or expired.');
        msg.style.display = 'block';
      }
    }

    async function closeRetrievalLocker(bookingId) {
      const res = await fetch('/api/web/close-retrieval', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ booking_id: bookingId })
      });
      const data = await res.json();
      if (data.success) {
        document.getElementById('main-content').innerHTML = 
          '<h2>✅ Locker Returned</h2>' +
          '<p class="desc">Thank you for using the Smart Locker system!</p>' +
          '<div class="success" style="padding: 16px; border-radius: 12px; background: rgba(34, 197, 94, 0.15); border: 1px solid rgba(34, 197, 94, 0.3); margin-bottom: 24px;">' +
          '  <p style="font-size:15px; font-weight:700; color:var(--success)">🔒 Locker Secured & Available</p>' +
          '  <p style="font-size:13px; color:#a3a3a3; margin-top: 8px;">The booking session has been completed, and rental durations have been recorded.</p>' +
          '</div>' +
          '<a href="/" class="home-link">← Back to Rent Page</a>';
      } else {
        alert("Failed to close locker: " + data.message);
      }
    }

    function backToRequest() {
      document.getElementById('otp-request-section').style.display = 'block';
      document.getElementById('otp-verify-section').style.display = 'none';
      document.getElementById('msg').style.display = 'none';
    }
  </script>
</body>
</html>
"""

ADMIN_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Locker Admin Dashboard — Smart Locker</title>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --primary: #ffffff;
      --primary-hover: #e5e5e5;
      --bg: #000000;
      --card-bg: #0c0c0e;
      --border: #3f3f46;
      --text: #ffffff;
      --text-muted: #a3a3a3;
      --success: #22c55e;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Outfit', sans-serif; }
    body {
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 40px 20px;
    }
    .container {
      max-width: 1000px;
      margin: 0 auto;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 40px;
    }
    h2 { font-size: 28px; font-weight: 700; color: var(--primary); }
    .back-btn { text-decoration: none; color: var(--primary); font-weight: 600; font-size: 14px; }
    .back-btn:hover { text-decoration: underline; }
    
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 20px;
      margin-bottom: 40px;
    }
    .stat-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
    }
    .stat-label { font-size: 13px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; letter-spacing: 1px; }
    .stat-val { font-size: 32px; font-weight: 700; color: var(--text); margin-top: 8px; }
    
    .table-container {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 20px;
      overflow: hidden;
      margin-bottom: 40px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8);
    }
    h3 { font-size: 18px; font-weight: 700; padding: 20px 24px; border-bottom: 1px solid var(--border); color: var(--text); }
    table { width: 100%; border-collapse: collapse; text-align: left; }
    th { background: #121212; color: var(--text-muted); font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; padding: 14px 24px; }
    td { padding: 16px 24px; font-size: 14px; border-bottom: 1px solid var(--border); color: var(--text); }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #161616; }
    
    .tag {
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 6px;
      text-transform: uppercase;
      display: inline-block;
    }
    .tag.completed { background: rgba(34, 197, 94, 0.15); color: var(--success); }
    .tag.active_rental { background: rgba(255, 255, 255, 0.1); color: var(--text); }
    .tag.pending_payment { background: rgba(249, 115, 22, 0.15); color: #f97316; }
    .tag.waiting_for_door_close { background: rgba(6, 182, 212, 0.15); color: #06b6d4; }
    .tag.otp_generated { background: rgba(236, 72, 153, 0.15); color: #ec4899; }
    .tag.retrieval_approved { background: rgba(168, 85, 247, 0.15); color: #a855f7; }
    
    .tag.available { background: rgba(34, 197, 94, 0.15); color: var(--success); }
    .tag.occupied { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
    .tag.reserved { background: rgba(249, 115, 22, 0.15); color: #f97316; }
    
    .btn-reset {
      background: rgba(239, 68, 68, 0.08);
      border: 1px solid rgba(239, 68, 68, 0.15);
      color: #ef4444;
      padding: 6px 12px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    .btn-reset:hover { background: #ef4444; color: white; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h2>🔒 Locker Admin Dashboard</h2>
      <a href="/" class="back-btn">← Rent Locker</a>
    </header>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Available Lockers</div>
        <div class="stat-val" style="color: var(--success)">{{ stats.available_lockers }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Active Rentals</div>
        <div class="stat-val" style="color: #818cf8">{{ stats.active_rentals }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">OTP Requests</div>
        <div class="stat-val" style="color: #ec4899">{{ stats.otp_requests }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Completed Rentals</div>
        <div class="stat-val">{{ stats.completed_rentals }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Revenue</div>
        <div class="stat-val" style="color: var(--success)">₹{{ stats.total_revenue }}</div>
      </div>
    </div>

    <div class="table-container">
      <h3>Lockers Status</h3>
      <table>
        <thead>
          <tr><th>Locker ID</th><th>Number</th><th>Location</th><th>Size</th><th>Status</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {% for l in lockers %}
          <tr>
            <td>{{ l.locker_id }}</td>
            <td>{{ l.locker_number }}</td>
            <td>{{ l.location }}</td>
            <td>{{ l.size }}</td>
            <td><span class="tag {{ l.status }}">{{ l.status }}</span></td>
            <td>
              <button class="btn-reset" onclick="resetLocker('{{ l.locker_id }}')">Force Reset</button>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    <div class="table-container">
      <h3>Recent Booking Orders</h3>
      <table>
        <thead>
          <tr><th>Booking ID</th><th>Locker</th><th>User</th><th>Amount</th><th>Status</th><th>Start Time</th><th>End Time</th></tr>
        </thead>
        <tbody>
          {% for o in orders %}
          <tr>
            <td>#{{ o.booking_id }}</td>
            <td>{{ o.locker_id }} ({{ o.locker_number }})</td>
            <td>{{ o.full_name }}<br><small style="color:var(--text-muted)">{{ o.phone }}</small></td>
            <td>₹{{ o.amount }}</td>
            <td><span class="tag {{ o.booking_status }}">{{ o.booking_status.replace('_', ' ') }}</span></td>
            <td>{{ o.start_time or '—' }}</td>
            <td>{{ o.end_time or '—' }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

  <script>
    async function resetLocker(lockerId) {
      if(!confirm("Force reset locker " + lockerId + " to available? This completes or cancels all associated bookings.")) return;
      const res = await fetch('/api/admin/reset/' + lockerId, { method: 'POST' });
      const data = await res.json();
      if(data.success) {
        location.reload();
      } else {
        alert("Failed to reset locker");
      }
    }
  </script>
</body>
</html>
"""

# ─── ROUTE HANDLERS ──────────────────────────────────────────────────────────

@web_bp.route("/")
def index():
    """Locker Rent index page."""
    lockers = LockerModel.get_all()
    price = Config.PRICE_PER_HOUR
    return render_template_string(RENT_PAGE_HTML, lockers=lockers, price=price)

@web_bp.route("/rent", methods=["POST"])
def rent_locker_web():
    """Handle booking submission from the Rent Web UI."""
    name = request.form.get("name")
    phone = request.form.get("phone")
    locker_id = request.form.get("locker_id")
    duration_hours = int(request.form.get("duration", 1))

    if not all([name, phone, locker_id]):
        return "<h2>Invalid Submission. Please fill all fields.</h2>", 400

    conn = get_db_connection()
    # Find or create user
    user = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    if not user:
        from werkzeug.security import generate_password_hash
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (full_name, phone, email, password_hash) VALUES (?, ?, ?, ?)",
            (name, phone, f"{phone}@mock-locker.com", generate_password_hash("test1234"))
        )
        conn.commit()
        user_id = cursor.lastrowid
    else:
        user_id = user["id"]
    conn.close()

    # Create the booking using the service
    duration_minutes = duration_hours * 60
    success, message, booking = BookingService.create_booking(user_id, locker_id, duration_minutes)
    
    if not success:
        return f"<h2>Error: {message}</h2>", 400

    upi_url = generate_upi_link(booking["booking_id"], booking["amount"])
    
    # Generate QR Base64
    qr = qrcode.QRCode(version=3, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_img = base64.b64encode(buffer.getvalue()).decode()

    return render_template_string(
        PAYMENT_PAGE_HTML,
        booking_id=booking["booking_id"],
        amount=booking["amount"],
        user_name=name,
        locker_id=locker_id,
        duration=duration_hours,
        upi_url=upi_url,
        qr_img=qr_img
    )

@web_bp.route("/retrieve")
def retrieve_page():
    """Retrieval page."""
    booking_id = request.args.get("booking_id", "")
    return render_template_string(RETRIEVE_PAGE_HTML, booking_id=booking_id)

@web_bp.route("/admin")
@requires_auth
def admin_page():
    """Admin dashboard page."""
    conn = get_db_connection()
    total_lockers = conn.execute("SELECT COUNT(*) FROM lockers").fetchone()[0] or 0
    available_lockers = conn.execute("SELECT COUNT(*) FROM lockers WHERE status = 'available'").fetchone()[0] or 0
    occupied_lockers = conn.execute("SELECT COUNT(*) FROM lockers WHERE status = 'occupied'").fetchone()[0] or 0
    active_rentals = conn.execute("SELECT COUNT(*) FROM bookings WHERE booking_status = 'active_rental'").fetchone()[0] or 0
    completed_rentals = conn.execute("SELECT COUNT(*) FROM bookings WHERE booking_status = 'completed'").fetchone()[0] or 0
    
    # Fetch active OTP requests
    otp_requests = OTPModel.get_active_otp_requests_count()
    
    # Calculate revenue
    total_revenue = conn.execute("SELECT SUM(amount) FROM payments WHERE payment_status = 'paid'").fetchone()[0] or 0.0
    conn.close()

    stats = {
        "total_lockers": total_lockers,
        "available_lockers": available_lockers,
        "occupied_lockers": occupied_lockers,
        "active_rentals": active_rentals,
        "completed_rentals": completed_rentals,
        "otp_requests": otp_requests,
        "total_revenue": round(total_revenue, 2)
    }

    lockers = LockerModel.get_all()
    orders = BookingModel.get_all()
    return render_template_string(ADMIN_PAGE_HTML, stats=stats, lockers=lockers, orders=orders)


# ─── WEB SIMULATION API MAPPINGS ──────────────────────────────────────────────

@web_bp.route("/api/payment/confirm", methods=["POST"])
def web_payment_confirm():
    """Confirms payment, updating state to waiting_for_door_close."""
    data = request.get_json() or {}
    booking_id = data.get("order_id") or data.get("booking_id")
    utr = data.get("utr") or data.get("utr_ref") or "MOCK_PAYMENT"

    if not booking_id:
        return jsonify({"success": False, "message": "Missing booking_id (order_id)"}), 400

    try:
        booking_id = int(booking_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid booking_id format"}), 400

    success, message, payment = PaymentService.process_mock_success(booking_id, utr)
    return jsonify({"success": success, "message": message})

@web_bp.route("/api/web/close-storage", methods=["POST"])
def web_close_storage():
    """Triggered by CLOSE DOOR button. Starts rental log and locks the servo."""
    data = request.get_json() or {}
    booking_id = data.get("booking_id")
    if not booking_id:
        return jsonify({"success": False, "message": "Missing booking_id"}), 400
        
    try:
        booking_id = int(booking_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid booking_id format"}), 400
        
    success, message = BookingService.activate_rental(booking_id)
    return jsonify({"success": success, "message": message})

@web_bp.route("/api/web/generate-otp", methods=["POST"])
def web_generate_otp():
    """Generates an OTP and displays it on the locker's TFT screen."""
    import random
    import string
    
    data = request.get_json() or {}
    booking_id = data.get("booking_id")
    if not booking_id:
        return jsonify({"success": False, "message": "Missing booking_id"}), 400
        
    try:
        booking_id = int(booking_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid booking_id format"}), 400
        
    booking = BookingModel.get_by_id(booking_id)
    if not booking:
        return jsonify({"success": False, "message": "Booking not found"}), 404
        
    otp_code = "".join(random.choices(string.digits, k=6))
    
    # Store OTP in DB
    otp_id = OTPModel.create(booking_id, booking["phone"], otp_code, validity_minutes=5)
    if not otp_id:
        return jsonify({"success": False, "message": "Failed to create OTP"}), 500
        
    print(f"[OTP SYSTEM] Generated OTP: {otp_code} for booking {booking_id}. Shown on TFT screen.")
    
    # Update booking status to otp_generated
    BookingModel.update_status(booking_id, "otp_generated")
    
    return jsonify({"success": True, "message": "OTP generated successfully. Look at the locker screen to see the code."})

@web_bp.route("/api/web/verify-otp", methods=["POST"])
def web_verify_otp():
    """Verifies retrieval OTP and transitions status to retrieval_approved (locker unlocks)."""
    data = request.get_json() or {}
    booking_id = data.get("booking_id")
    otp_code = data.get("otp")
    
    if not booking_id or not otp_code:
        return jsonify({"success": False, "message": "Missing booking_id or OTP"}), 400
        
    try:
        booking_id = int(booking_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid booking_id format"}), 400
        
    booking = BookingModel.get_by_id(booking_id)
    if not booking:
        return jsonify({"success": False, "message": "Booking not found"}), 404
    
    if booking["booking_status"] not in ("active_rental", "waiting_for_door_close", "otp_generated"):
        return jsonify({"success": False, "message": f"Booking is not in a valid state for OTP (current: {booking['booking_status']})"}), 400
        
    verified, message = OTPModel.verify(booking_id, otp_code)
    if not verified:
        return jsonify({"success": False, "message": message})
        
    # Update booking status to retrieval_approved
    BookingModel.update_status(booking_id, "retrieval_approved")
    return jsonify({"success": True, "message": "OTP verified successfully"})

@web_bp.route("/api/web/close-retrieval", methods=["POST"])
def web_close_retrieval():
    """Triggered by CLOSE LOCKER button. Ends rental and makes locker available again."""
    data = request.get_json() or {}
    booking_id = data.get("booking_id")
    if not booking_id:
        return jsonify({"success": False, "message": "Missing booking_id"}), 400
        
    try:
        booking_id = int(booking_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid booking_id format"}), 400
        
    success, message = BookingService.complete_rental(booking_id)
    return jsonify({"success": success, "message": message})

@web_bp.route("/api/payment/check-status/<int:booking_id>", methods=["GET"])
def check_payment_status(booking_id):
    """Checks booking payment status without auto-confirmation."""
    booking = BookingModel.get_by_id(booking_id)
    if not booking:
        return jsonify({"success": False, "message": "Booking not found"}), 404
        
    is_paid = booking["booking_status"] != "pending_payment"
    return jsonify({"success": True, "paid": is_paid})

@web_bp.route("/api/web/cancel", methods=["POST"])
def web_cancel_booking():
    """Cancels booking from Web UI, restoring locker to available."""
    data = request.get_json() or {}
    booking_id = data.get("booking_id")
    if not booking_id:
        return jsonify({"success": False, "message": "Missing booking_id"}), 400
        
    try:
        booking_id = int(booking_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid booking_id format"}), 400
        
    success, message = BookingService.cancel_booking(booking_id)
    return jsonify({"success": success, "message": message})

@web_bp.route("/api/web/my-bookings", methods=["GET"])
def web_my_bookings():
    """Fetches bookings for a user by their phone number."""
    phone = request.args.get("phone")
    if not phone:
        return jsonify({"success": False, "message": "Phone number required"}), 400
        
    conn = get_db_connection()
    bookings = conn.execute(
        """SELECT b.*, l.locker_number, l.location, l.size 
           FROM bookings b
           JOIN users u ON b.user_id = u.id
           JOIN lockers l ON b.locker_id = l.locker_id
           WHERE u.phone = ? 
           ORDER BY b.created_at DESC""",
        (phone,)
    ).fetchall()
    conn.close()
    return jsonify({"success": True, "bookings": [dict(b) for b in bookings]})

@web_bp.route("/api/admin/reset/<locker_id>", methods=["POST"])
@requires_auth
def web_admin_reset_locker(locker_id):
    """Resets locker for admin screen."""
    # Find any active bookings for this locker to complete them correctly (syncs to Firestore & MQTT)
    conn = get_db_connection()
    active_bookings = conn.execute(
        "SELECT booking_id FROM bookings WHERE locker_id = ? AND booking_status != 'completed'", 
        (locker_id,)
    ).fetchall()
    conn.close()

    # Complete each active booking through BookingModel (updates SQLite, Firestore, and publishes MQTT reset)
    for b in active_bookings:
        BookingModel.update_status(b["booking_id"], "completed")
    
    # Also ensure the locker is marked available in SQLite and Firestore
    LockerModel.update_status(locker_id, "available")
    
    return jsonify({"success": True})
