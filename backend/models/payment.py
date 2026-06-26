from database.db import get_db_connection

class PaymentModel:
    @staticmethod
    def create(booking_id, amount, status='pending'):
        """Creates a payment record."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO payments (booking_id, amount, payment_status) VALUES (?, ?, ?)",
                (booking_id, amount, status)
            )
            conn.commit()
            payment_id = cursor.lastrowid
            return PaymentModel.get_by_id(payment_id)
        except Exception as e:
            print(f"Error creating payment: {e}")
            return None
        finally:
            conn.close()

    @staticmethod
    def get_by_id(payment_id):
        """Fetches payment by ID."""
        conn = get_db_connection()
        payment = conn.execute("SELECT * FROM payments WHERE payment_id = ?", (payment_id,)).fetchone()
        conn.close()
        return dict(payment) if payment else None

    @staticmethod
    def get_by_booking_id(booking_id):
        """Fetches payments by booking ID."""
        conn = get_db_connection()
        payment = conn.execute("SELECT * FROM payments WHERE booking_id = ?", (booking_id,)).fetchone()
        conn.close()
        return dict(payment) if payment else None

    @staticmethod
    def get_all():
        """Fetches all payments in the system."""
        conn = get_db_connection()
        payments = conn.execute(
            """SELECT p.*, b.locker_id, u.full_name 
               FROM payments p
               JOIN bookings b ON p.booking_id = b.booking_id
               JOIN users u ON b.user_id = u.id
               ORDER BY p.created_at DESC"""
        ).fetchall()
        conn.close()
        return [dict(p) for p in payments]

    @staticmethod
    def update_status(payment_id, status, transaction_id=None):
        """Updates payment status and attaches a transaction/UTR ID."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if transaction_id:
                cursor.execute(
                    "UPDATE payments SET payment_status = ?, transaction_id = ? WHERE payment_id = ?",
                    (status, transaction_id, payment_id)
                )
            else:
                cursor.execute(
                    "UPDATE payments SET payment_status = ? WHERE payment_id = ?",
                    (status, payment_id)
                )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating payment status: {e}")
            return False
        finally:
            conn.close()
            
    @staticmethod
    def update_status_by_booking(booking_id, status, transaction_id=None):
        """Updates payment status for a given booking ID."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if transaction_id:
                cursor.execute(
                    "UPDATE payments SET payment_status = ?, transaction_id = ? WHERE booking_id = ?",
                    (status, transaction_id, booking_id)
                )
            else:
                cursor.execute(
                    "UPDATE payments SET payment_status = ? WHERE booking_id = ?",
                    (status, booking_id)
                )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating payment by booking ID: {e}")
            return False
        finally:
            conn.close()
