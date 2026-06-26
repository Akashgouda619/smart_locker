from flask import Blueprint, request, jsonify
import qrcode
from models.locker import LockerModel
from models.booking import BookingModel
from services.booking_service import BookingService
from config import Config
from utils.helpers import json_response
from utils.upi import generate_upi_link

esp32_bp = Blueprint("esp32", __name__)

def generate_qr_matrix(url: str):
    """Generates a QR code grid matrix (1=black, 0=white) for the ESP32 to render."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=0
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    matrix = qr.get_matrix()
    size = len(matrix)
    
    # Format rows as binary string arrays
    data = ["".join(["1" if cell else "0" for cell in row]) for row in matrix]
    return size, data

@esp32_bp.route("/api/testqr", methods=["GET"])
def test_qr():
    """Returns a test QR matrix representation for verification."""
    upi_url = (
        "upi://pay?"
        "pa=7019007474@ptaxis&"
        "pn=Smart%20Locker&"
        "am=20.00&"
        "cu=INR&"
        "tn=Locker%20Payment"
    )
    qr_size, qr_data = generate_qr_matrix(upi_url)
    return jsonify({
        "size": qr_size,
        "data": qr_data
    })

@esp32_bp.route("/api/esp32/payment/<locker_id>", methods=["GET"])
def esp32_get_payment(locker_id):
    """
    Called by ESP32 to check for pending payment for this locker.
    Returns the QR matrix in JSON format for the ESP32 to draw on the TFT screen.
    """
    # Fetch the latest booking in pending_payment state
    booking = BookingModel.get_pending_payment_by_locker(locker_id)
    if not booking:
        return json_response(
            success=False,
            message="No pending payment booking found for this locker",
            status_code=404
        )

    upi_url = generate_upi_link(booking["booking_id"], booking["amount"])
    qr_size, qr_matrix = generate_qr_matrix(upi_url)

    # Prepare response data with QR matrix
    response_data = {
        "booking_id": booking["booking_id"],
        "amount": booking["amount"],
        "payment_status": booking["booking_status"],
        "qr_size": qr_size,
        "qr_matrix": qr_matrix
    }

    return json_response(
        success=True,
        message="Pending payment QR matrix generated",
        data=response_data
    )

@esp32_bp.route("/api/esp32/locker/<locker_id>/status", methods=["GET"])
def esp32_get_status(locker_id):
    """
    ESP32 polls this continuously to get current instruction and status.
    Instructs the hardware when to trigger the servo unlock.
    """
    booking = BookingModel.get_paid_or_active_by_locker(locker_id)
    if not booking:
        booking = BookingModel.get_pending_payment_by_locker(locker_id)
    
    if booking:
        # Determine whether the servo lock should open
        # The servo unlocks for item storage (waiting_for_door_close) and item retrieval (retrieval_approved)
        unlock = booking["booking_status"] in ("waiting_for_door_close", "retrieval_approved")
        
        otp_code = None
        if booking["booking_status"] == "otp_generated":
            from models.otp import OTPModel
            otp_record = OTPModel.get_latest_active_by_booking(booking["booking_id"])
            if otp_record:
                otp_code = otp_record["otp_code"]
            
        return json_response(
            success=True,
            message="Active booking status found",
            data={
                "unlock": unlock,
                "booking_id": booking["booking_id"],
                "payment_status": booking["booking_status"],
                "rental_duration": booking["rental_duration"],
                "otp_code": otp_code
            }
        )
        
    # If no booking exists, return idle state
    locker = LockerModel.get_by_id(locker_id)
    locker_status = locker["status"] if locker else "unknown"
    
    qr_size = 0
    qr_matrix = []
    if locker_status == "available":
        website_url = f"http://{request.host}/"
        try:
            qr_size, qr_matrix = generate_qr_matrix(website_url)
        except Exception as e:
            print(f"Error generating website QR: {e}")
            
    return json_response(
        success=True,
        message="Locker is idle",
        data={
            "unlock": False,
            "booking_id": None,
            "payment_status": None,
            "locker_status": locker_status,
            "qr_size": qr_size,
            "qr_matrix": qr_matrix
        }
    )

@esp32_bp.route("/api/esp32/heartbeat", methods=["POST"])
def esp32_heartbeat():
    """
    Periodic heartbeat from ESP32 to monitor signal strength (RSSI), battery/power status,
    and update locker online status.
    """
    data = request.get_json() or {}
    locker_id = data.get("locker_id")
    status = data.get("status")
    rssi = data.get("rssi")
    uptime = data.get("uptime") # in seconds

    if not locker_id:
        return json_response(
            success=False,
            message="Please provide locker_id",
            status_code=400
        )

    # In production, we would log this to a locker_health table or Redis.
    print(f"[HEARTBEAT] Locker: {locker_id} | Status: {status} | RSSI: {rssi}dBm | Uptime: {uptime}s")

    return json_response(
        success=True,
        message="Heartbeat received"
    )
