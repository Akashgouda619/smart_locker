from flask import Blueprint
from models.booking import BookingModel
from models.rental_log import RentalLogModel
from utils.helpers import json_response

rental_bp = Blueprint("rental", __name__)

@rental_bp.route("/api/rental/status/<int:booking_id>", methods=["GET"])
def get_rental_status(booking_id):
    """Retrieve the rental tracking log and status for a specific booking."""
    booking = BookingModel.get_by_id(booking_id)
    if not booking:
        return json_response(
            success=False,
            message="Booking not found",
            status_code=404
        )

    rental_log = RentalLogModel.get_by_booking(booking_id)
    
    # Format response payload
    rental_status = {
        "booking_id": booking["booking_id"],
        "locker_id": booking["locker_id"],
        "locker_number": booking["locker_number"],
        "booking_status": booking["booking_status"],
        "start_time": booking["start_time"],
        "end_time": booking["end_time"],
        "rental_duration_minutes": booking["rental_duration"],
        "actual_duration_minutes": rental_log["duration_minutes"] if rental_log else None,
        "log_start_time": rental_log["start_time"] if rental_log else None,
        "log_end_time": rental_log["end_time"] if rental_log else None
    }

    return json_response(
        success=True,
        message="Rental status retrieved successfully",
        data=rental_status
    )
