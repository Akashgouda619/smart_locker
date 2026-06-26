from flask import Blueprint, request
from models.booking import BookingModel
from models.payment import PaymentModel
from services.payment_service import PaymentService
from utils.helpers import json_response

payment_bp = Blueprint("payment", __name__)

@payment_bp.route("/api/payment/create", methods=["POST"])
def create_payment_route():
    """Create or retrieve a payment session for a booking."""
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
        return json_response(
            success=False,
            message="Booking not found",
            status_code=404
        )

    if booking["booking_status"] != "pending_payment":
        return json_response(
            success=False,
            message=f"Locker booking is not pending payment. Current status: {booking['booking_status']}",
            status_code=400
        )

    # Retrieve existing payment or create one
    payment = PaymentModel.get_by_booking_id(booking_id)
    if not payment:
        payment = PaymentModel.create(booking_id, booking["amount"])
        
    return json_response(
        success=True,
        message="Payment session initialized",
        data=payment
    )

@payment_bp.route("/api/payment/status/<int:payment_id>", methods=["GET"])
def get_payment_status(payment_id):
    """Retrieve the status of a specific payment session."""
    payment = PaymentModel.get_by_id(payment_id)
    if not payment:
        return json_response(
            success=False,
            message=f"Payment session {payment_id} not found",
            status_code=404
        )
    return json_response(
        success=True,
        message="Payment status retrieved",
        data={
            "payment_id": payment["payment_id"],
            "booking_id": payment["booking_id"],
            "amount": payment["amount"],
            "payment_status": payment["payment_status"],
            "transaction_id": payment["transaction_id"]
        }
    )

@payment_bp.route("/api/payment/mock-success", methods=["POST"])
def mock_payment_success():
    """Endpoint to simulate payment webhook confirmation (Mock Payment mode)."""
    data = request.get_json() or {}
    booking_id = data.get("booking_id")
    transaction_id = data.get("transaction_id") # optional custom ID

    if not booking_id:
        return json_response(
            success=False,
            message="Please provide booking_id",
            status_code=400
        )

    success, message, payment_data = PaymentService.process_mock_success(booking_id, transaction_id)
    
    if not success:
        return json_response(
            success=False,
            message=message,
            status_code=400
        )

    return json_response(
        success=True,
        message=message,
        data=payment_data
    )
