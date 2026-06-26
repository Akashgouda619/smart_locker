import uuid
from datetime import datetime
from database.db import get_db_connection
from models.booking import BookingModel
from models.payment import PaymentModel

class PaymentService:
    @staticmethod
    def process_mock_success(booking_id, transaction_id=None):
        """
        Simulates a successful payment webhook/callback.
        Updates payment to 'paid', associates the transaction_id, and sets booking status to 'paid'.
        Runs inside a database transaction.
        """
        if not transaction_id or transaction_id == "MOCK_PAYMENT":
            transaction_id = f"TXN-MOCK-{uuid.uuid4().hex[:12].upper()}"
            
        success = False
        message = ""
        updated_payment = None
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # 1. Fetch booking
            booking = cursor.execute(
                "SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)
            ).fetchone()
            
            if not booking:
                return False, "Booking not found", None
                
            if booking["booking_status"] != "pending_payment":
                return False, f"Booking is not in pending_payment status (current: {booking['booking_status']})", None

            # Check if transaction_id already exists to prevent UNIQUE constraint violation in dev/test
            existing_txn = cursor.execute(
                "SELECT * FROM payments WHERE transaction_id = ?", (transaction_id,)
            ).fetchone()
            if existing_txn:
                transaction_id = f"{transaction_id}-{uuid.uuid4().hex[:4].upper()}"

            # 2. Fetch payment record
            payment = cursor.execute(
                "SELECT * FROM payments WHERE booking_id = ?", (booking_id,)
            ).fetchone()
            
            if not payment:
                return False, "Payment session not found for this booking", None

            # 3. Update payment table to paid
            cursor.execute(
                "UPDATE payments SET payment_status = 'paid', transaction_id = ? WHERE booking_id = ?",
                (transaction_id, booking_id)
            )
            
            # 4. Update booking table to waiting_for_door_close
            cursor.execute(
                "UPDATE bookings SET booking_status = 'waiting_for_door_close' WHERE booking_id = ?",
                (booking_id,)
            )
            
            conn.commit()
            success = True
            message = "Payment successfully confirmed"
            
            # Retrieve updated payment object
            updated_payment = PaymentModel.get_by_booking_id(booking_id)
            
        except Exception as e:
            conn.rollback()
            print(f"Transaction failed in process_mock_success: {e}")
            return False, f"Internal error during payment confirmation: {str(e)}", None
        finally:
            conn.close()

        if success:
            try:
                BookingModel.update_status(booking_id, "waiting_for_door_close")
            except Exception as fe:
                print(f"Failed to sync payment confirmation to Firestore/MQTT: {fe}")
            return True, message, updated_payment
        return False, message, None
