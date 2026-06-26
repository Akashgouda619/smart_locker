import math
from datetime import datetime
from config import Config
from database.db import get_db_connection
from models.locker import LockerModel
from models.booking import BookingModel
from models.payment import PaymentModel
from models.rental_log import RentalLogModel

class BookingService:
    @staticmethod
    def calculate_amount(duration_minutes):
        """Calculates the booking cost based on duration (in minutes) and hourly rate."""
        hours = duration_minutes / 60.0
        # Charge at least for 1 hour
        hours_to_charge = max(1.0, hours)
        # Round up to nearest integer hour for billing or charge fractional
        # Let's charge fractional with precision of 2 decimals
        return round(hours_to_charge * Config.PRICE_PER_HOUR, 2)

    @staticmethod
    def create_booking(user_id, locker_id, duration_minutes):
        """
        Creates a locker booking.
        Updates locker status to 'reserved' and inserts booking and payment records.
        Runs inside a database transaction block.
        """
        success = False
        message = ""
        booking_data = None
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # 1. Lock locker for update/check status
            locker = cursor.execute(
                "SELECT * FROM lockers WHERE locker_id = ?", (locker_id,)
            ).fetchone()
            
            if not locker:
                return False, "Locker not found", None
                
            if locker["status"] != "available":
                return False, "Locker is not available for booking", None

            # Calculate price
            amount = BookingService.calculate_amount(duration_minutes)
            
            # 2. Update locker status to 'reserved'
            cursor.execute(
                "UPDATE lockers SET status = 'reserved' WHERE locker_id = ?",
                (locker_id,)
            )
            
            # 3. Create booking
            cursor.execute(
                """INSERT INTO bookings (user_id, locker_id, rental_duration, amount, booking_status)
                   VALUES (?, ?, ?, ?, 'pending_payment')""",
                (user_id, locker_id, duration_minutes, amount)
            )
            booking_id = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO payments (booking_id, amount, payment_status) VALUES (?, ?, 'pending')",
                (booking_id, amount)
            )
            
            conn.commit()
            success = True
            message = "Booking created successfully"
            
            # Fetch completed booking info
            booking_data = BookingModel.get_by_id(booking_id)
            
        except Exception as e:
            conn.rollback()
            print(f"Transaction failed in create_booking: {e}")
            return False, f"Internal error during booking creation: {str(e)}", None
        finally:
            conn.close()

        if success and booking_data:
            try:
                BookingModel.update_status(booking_data["booking_id"], 'pending_payment')
            except Exception as fe:
                print(f"Failed to sync newly created booking to Firestore/MQTT: {fe}")
            return True, message, booking_data
        return False, "Failed to create booking", None

    @staticmethod
    def cancel_booking(booking_id):
        """
        Cancels a booking if it is in pending_payment status.
        Restores locker status to 'available'.
        """
        success = False
        message = ""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            booking = cursor.execute(
                "SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)
            ).fetchone()
            
            if not booking:
                return False, "Booking not found"
                
            if booking["booking_status"] != "pending_payment":
                return False, f"Cannot cancel booking in status: {booking['booking_status']}"
                
            # Update booking status
            cursor.execute(
                "UPDATE bookings SET booking_status = 'cancelled' WHERE booking_id = ?",
                (booking_id,)
            )
            
            # Restore locker to available
            cursor.execute(
                "UPDATE lockers SET status = 'available' WHERE locker_id = ?",
                (booking["locker_id"],)
            )
            
            # Mark payment as failed/cancelled
            cursor.execute(
                "UPDATE payments SET payment_status = 'failed' WHERE booking_id = ?",
                (booking_id,)
            )
            
            conn.commit()
            success = True
            message = "Booking cancelled successfully"
            
        except Exception as e:
            conn.rollback()
            print(f"Transaction failed in cancel_booking: {e}")
            return False, f"Internal error: {str(e)}"
        finally:
            conn.close()

        if success:
            try:
                BookingModel.update_status(booking_id, "cancelled")
            except Exception as fe:
                print(f"Failed to sync cancel to Firestore/MQTT: {fe}")
            return True, message
        return False, message

    @staticmethod
    def activate_rental(booking_id, start_time_str=None):
        """
        Activates a paid booking. Called when the user closes the storage door.
        Updates booking status to 'active_rental', locker to 'occupied', and creates a rental log.
        """
        if not start_time_str:
            start_time_str = datetime.now().isoformat()
            
        success = False
        message = ""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            booking = cursor.execute(
                "SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)
            ).fetchone()
            
            if not booking:
                return False, "Booking not found"
                
            if booking["booking_status"] != "waiting_for_door_close":
                return False, f"Booking status must be 'waiting_for_door_close' to activate. Current: {booking['booking_status']}"
                
            # Update booking status and start_time
            cursor.execute(
                "UPDATE bookings SET booking_status = 'active_rental', start_time = ? WHERE booking_id = ?",
                (start_time_str, booking_id)
            )
            
            # Update locker status to occupied
            cursor.execute(
                "UPDATE lockers SET status = 'occupied' WHERE locker_id = ?",
                (booking["locker_id"],)
            )
            
            # Create rental log
            cursor.execute(
                "INSERT INTO rental_logs (booking_id, start_time) VALUES (?, ?)",
                (booking_id, start_time_str)
            )
            
            conn.commit()
            success = True
            message = "Rental activated successfully"
            
        except Exception as e:
            conn.rollback()
            print(f"Transaction failed in activate_rental: {e}")
            return False, f"Internal error: {str(e)}"
        finally:
            conn.close()

        if success:
            try:
                BookingModel.update_status(booking_id, "active_rental")
            except Exception as fe:
                print(f"Failed to sync activate to Firestore/MQTT: {fe}")
            return True, message
        return False, message

    @staticmethod
    def complete_rental(booking_id, end_time_str=None):
        """
        Completes an active rental. Called when the user closes the retrieval door.
        Updates booking status to 'completed', locker to 'available', and logs actual duration.
        """
        if not end_time_str:
            end_time_str = datetime.now().isoformat()
            
        success = False
        message = ""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            booking = cursor.execute(
                "SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)
            ).fetchone()
            
            if not booking:
                return False, "Booking not found"
                
            if booking["booking_status"] != "retrieval_approved":
                return False, f"Cannot complete booking in status: {booking['booking_status']}"
                
            # Fetch rental log to calculate duration
            log = cursor.execute(
                "SELECT * FROM rental_logs WHERE booking_id = ? AND end_time IS NULL",
                (booking_id,)
            ).fetchone()
            
            duration_minutes = 0
            start_time_str = booking["start_time"] or booking["created_at"]
            
            if log:
                start_time_str = log["start_time"]
                
            try:
                start_dt = datetime.fromisoformat(start_time_str)
                end_dt = datetime.fromisoformat(end_time_str)
                delta = end_dt - start_dt
                duration_minutes = int(math.ceil(delta.total_seconds() / 60.0))
            except Exception as ex:
                print(f"Duration parsing error: {ex}")
                duration_minutes = booking["rental_duration"]

            # Update booking
            cursor.execute(
                "UPDATE bookings SET booking_status = 'completed', end_time = ? WHERE booking_id = ?",
                (end_time_str, booking_id)
            )
            
            # Restore locker to available
            cursor.execute(
                "UPDATE lockers SET status = 'available' WHERE locker_id = ?",
                (booking["locker_id"],)
            )
            
            # Close rental log
            if log:
                cursor.execute(
                    "UPDATE rental_logs SET end_time = ?, duration_minutes = ? WHERE booking_id = ? AND end_time IS NULL",
                    (end_time_str, duration_minutes, booking_id)
                )
            else:
                # If log didn't exist for some reason, create a complete one
                cursor.execute(
                    "INSERT INTO rental_logs (booking_id, start_time, end_time, duration_minutes) VALUES (?, ?, ?, ?)",
                    (booking_id, start_time_str, end_time_str, duration_minutes)
                )
                
            conn.commit()
            success = True
            message = "Rental completed successfully"
            
        except Exception as e:
            conn.rollback()
            print(f"Transaction failed in complete_rental: {e}")
            return False, f"Internal error: {str(e)}"
        finally:
            conn.close()

        if success:
            try:
                BookingModel.update_status(booking_id, "completed")
            except Exception as fe:
                print(f"Failed to sync complete to Firestore/MQTT: {fe}")
            return True, message
        return False, message
