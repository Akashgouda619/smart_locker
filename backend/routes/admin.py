from flask import Blueprint
from database.db import get_db_connection
from models.booking import BookingModel
from models.payment import PaymentModel
from models.locker import LockerModel
from utils.helpers import json_response

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/api/admin/dashboard", methods=["GET"])
def get_dashboard_metrics():
    """Retrieve key operational metrics for the Admin Dashboard."""
    conn = get_db_connection()
    try:
        # Total Lockers
        total_lockers = conn.execute("SELECT COUNT(*) FROM lockers").fetchone()[0] or 0
        
        # Available Lockers
        available_lockers = conn.execute("SELECT COUNT(*) FROM lockers WHERE status = 'available'").fetchone()[0] or 0
        
        # Occupied Lockers
        occupied_lockers = conn.execute("SELECT COUNT(*) FROM lockers WHERE status = 'occupied'").fetchone()[0] or 0
        
        # Active Rentals
        active_rentals = conn.execute("SELECT COUNT(*) FROM bookings WHERE booking_status = 'active'").fetchone()[0] or 0
        
        # Total Revenue (sum of all paid payments)
        total_revenue = conn.execute("SELECT SUM(amount) FROM payments WHERE payment_status = 'paid'").fetchone()[0] or 0.0
        
        # Today's Revenue (sum of paid payments created today)
        # Note: SQLite 'date('now')' matches the YYYY-MM-DD formatting of standard timestamps
        today_revenue = conn.execute(
            "SELECT SUM(amount) FROM payments WHERE payment_status = 'paid' AND date(created_at) = date('now')"
        ).fetchone()[0] or 0.0
        
        # Pending Payments
        pending_payments = conn.execute("SELECT COUNT(*) FROM bookings WHERE booking_status = 'pending_payment'").fetchone()[0] or 0
        
        metrics = {
            "total_lockers": total_lockers,
            "available_lockers": available_lockers,
            "occupied_lockers": occupied_lockers,
            "active_rentals": active_rentals,
            "total_revenue": round(total_revenue, 2),
            "todays_revenue": round(today_revenue, 2),
            "pending_payments": pending_payments
        }
        
        return json_response(
            success=True,
            message="Admin dashboard metrics retrieved",
            data=metrics
        )
    except Exception as e:
        print(f"Error retrieving admin dashboard metrics: {e}")
        return json_response(
            success=False,
            message="Internal database error",
            status_code=500
        )
    finally:
        conn.close()

@admin_bp.route("/api/admin/bookings", methods=["GET"])
def admin_get_bookings():
    """Retrieve all bookings in the system."""
    bookings = BookingModel.get_all()
    return json_response(
        success=True,
        message="All bookings retrieved successfully",
        data=bookings
    )

@admin_bp.route("/api/admin/payments", methods=["GET"])
def admin_get_payments():
    """Retrieve all payment records in the system."""
    payments = PaymentModel.get_all()
    return json_response(
        success=True,
        message="All payments retrieved successfully",
        data=payments
    )

@admin_bp.route("/api/admin/lockers", methods=["GET"])
def admin_get_lockers():
    """Retrieve all lockers in the system."""
    lockers = LockerModel.get_all()
    return json_response(
        success=True,
        message="All lockers retrieved successfully",
        data=lockers
    )
