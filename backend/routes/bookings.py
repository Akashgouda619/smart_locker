from flask import Blueprint, request, g
from middleware.auth import token_required
from models.booking import BookingModel
from services.booking_service import BookingService
from utils.helpers import json_response

bookings_bp = Blueprint("bookings", __name__)

@bookings_bp.route("/api/bookings/create", methods=["POST"])
@token_required
def create_booking():
    """Create a new booking and hold the locker."""
    data = request.get_json() or {}
    locker_id = data.get("locker_id")
    rental_duration = data.get("rental_duration") # in minutes

    if not locker_id or not rental_duration:
        return json_response(
            success=False,
            message="Please provide locker_id and rental_duration (in minutes)",
            status_code=400
        )

    try:
        rental_duration = int(rental_duration)
        if rental_duration <= 0:
            raise ValueError
    except ValueError:
        return json_response(
            success=False,
            message="rental_duration must be a positive integer representing minutes",
            status_code=400
        )

    user_id = g.current_user["id"]
    success, message, booking = BookingService.create_booking(user_id, locker_id, rental_duration)
    
    if not success:
        return json_response(
            success=False,
            message=message,
            status_code=400
        )

    return json_response(
        success=True,
        message=message,
        data=booking,
        status_code=201
    )

@bookings_bp.route("/api/bookings/<int:booking_id>", methods=["GET"])
@token_required
def get_booking(booking_id):
    """Retrieve details of a specific booking. Restricts lookup to the owner."""
    booking = BookingModel.get_by_id(booking_id)
    
    if not booking:
        return json_response(
            success=False,
            message=f"Booking with ID {booking_id} not found",
            status_code=404
        )

    # Enforce ownership: only the user who booked or an admin can access
    if booking["user_id"] != g.current_user["id"]:
        return json_response(
            success=False,
            message="Unauthorized. You do not own this booking.",
            status_code=403
        )

    return json_response(
        success=True,
        message="Booking retrieved successfully",
        data=booking
    )

@bookings_bp.route("/api/bookings/cancel", methods=["POST"])
@token_required
def cancel_booking():
    """Cancel a booking before it has been paid."""
    data = request.get_json() or {}
    booking_id = data.get("booking_id")

    if not booking_id:
        return json_response(
            success=False,
            message="Please provide booking_id",
            status_code=400
        )

    booking = BookingModel.get_by_id(booking_id)
    if not booking:
        # Ghost booking check: if the server database was reset but Firestore has a ghost booking, delete it to let the app recover
        try:
            from services.firebase_service import delete_booking_sync
            delete_booking_sync(booking_id)
        except Exception as e:
            print(f"Failed to delete ghost booking from Firestore: {e}")
        return json_response(
            success=True,
            message="Ghost booking cleared successfully"
        )

    if booking["user_id"] != g.current_user["id"]:
        return json_response(
            success=False,
            message="Unauthorized to cancel this booking",
            status_code=403
        )

    success, message = BookingService.cancel_booking(booking_id)
    if not success:
        return json_response(
            success=False,
            message=message,
            status_code=400
        )

    return json_response(
        success=True,
        message=message
    )

@bookings_bp.route("/api/bookings/<int:booking_id>/generate-otp", methods=["POST"])
@token_required
def generate_otp_route(booking_id):
    """Generates a retrieval OTP, saves it to DB, updates status to otp_generated, and sends SMS."""
    import random
    import string
    from models.otp import OTPModel
    from services.sms_service import SMSService
    
    booking = BookingModel.get_by_id(booking_id)
    if not booking:
        return json_response(success=False, message="Booking not found", status_code=404)
        
    if booking["user_id"] != g.current_user["id"]:
        return json_response(success=False, message="Unauthorized to request OTP for this booking", status_code=403)
        
    if booking["booking_status"] != "active_rental":
        return json_response(
            success=False, 
            message=f"Locker must be in active_rental status to generate OTP. Current: {booking['booking_status']}", 
            status_code=400
        )
        
    # Generate random 6 digit OTP
    otp_code = "".join(random.choices(string.digits, k=6))
    
    # Store OTP in database
    otp_id = OTPModel.create(booking_id, booking["phone"], otp_code, validity_minutes=5)
    if not otp_id:
        return json_response(success=False, message="Failed to store OTP in database", status_code=500)
        
    # Send OTP SMS via SMS Service
    sms_success, sms_msg = SMSService.send_otp(booking["phone"], otp_code, expiry_minutes=5)
    
    # Update booking status to otp_generated
    BookingModel.update_status(booking_id, "otp_generated")
    
    return json_response(
        success=True, 
        message=f"Retrieval OTP generated and sent. {sms_msg}", 
        data={"booking_id": booking_id, "otp_code": otp_code} # Return OTP code so web UI test can display it
    )

@bookings_bp.route("/api/bookings/<int:booking_id>/verify-otp", methods=["POST"])
@token_required
def verify_otp_route(booking_id):
    """Verifies the retrieval OTP, and updates booking status to retrieval_approved if correct."""
    from models.otp import OTPModel
    booking = BookingModel.get_by_id(booking_id)
    if not booking:
        return json_response(success=False, message="Booking not found", status_code=404)
        
    if booking["user_id"] != g.current_user["id"]:
        return json_response(success=False, message="Unauthorized to verify OTP for this booking", status_code=403)
        
    if booking["booking_status"] != "otp_generated":
        return json_response(
            success=False, 
            message=f"Booking is not waiting for OTP verification. Current: {booking['booking_status']}", 
            status_code=400
        )
        
    data = request.get_json() or {}
    otp_code = data.get("otp")
    if not otp_code:
        return json_response(success=False, message="Please provide the 6-digit OTP code", status_code=400)
        
    verified, message = OTPModel.verify(booking_id, otp_code)
    if not verified:
        return json_response(success=False, message=message, status_code=400)
        
    # Update booking status to retrieval_approved
    BookingModel.update_status(booking_id, "retrieval_approved")
    
    return json_response(
        success=True, 
        message="OTP verified successfully. Locker retrieval is approved."
    )

@bookings_bp.route("/api/bookings/<int:booking_id>/close-storage", methods=["POST"])
@token_required
def close_storage_route(booking_id):
    """Simulates closing the door after placing items. Transitions status to active_rental."""
    booking = BookingModel.get_by_id(booking_id)
    if not booking:
        return json_response(success=False, message="Booking not found", status_code=404)
        
    if booking["user_id"] != g.current_user["id"]:
        return json_response(success=False, message="Unauthorized", status_code=403)
        
    if booking["booking_status"] != "waiting_for_door_close":
        return json_response(
            success=False, 
            message=f"Locker must be waiting for storage close to trigger this action. Current: {booking['booking_status']}", 
            status_code=400
        )
        
    success, message = BookingService.activate_rental(booking_id)
    if not success:
        return json_response(success=False, message=message, status_code=500)
        
    return json_response(success=True, message="Locker closed. Rental timer started.")

@bookings_bp.route("/api/bookings/<int:booking_id>/close-retrieval", methods=["POST"])
@token_required
def close_retrieval_route(booking_id):
    """Simulates closing the door after collecting items. Transitions status to completed."""
    booking = BookingModel.get_by_id(booking_id)
    if not booking:
        return json_response(success=False, message="Booking not found", status_code=404)
        
    if booking["user_id"] != g.current_user["id"]:
        return json_response(success=False, message="Unauthorized", status_code=403)
        
    if booking["booking_status"] != "retrieval_approved":
        return json_response(
            success=False, 
            message=f"Locker must be waiting for retrieval close to trigger this action. Current: {booking['booking_status']}", 
            status_code=400
        )
        
    success, message = BookingService.complete_rental(booking_id)
    if not success:
        return json_response(success=False, message=message, status_code=500)
        
    return json_response(success=True, message="Locker retrieval completed. Locker is now available.")
