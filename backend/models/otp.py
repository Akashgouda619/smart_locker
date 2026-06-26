from datetime import datetime, timedelta
import time
from database.db import get_db_connection

class OTPModel:
    @staticmethod
    def create(booking_id, phone_number, otp_code, validity_minutes=5):
        """Creates a new OTP code in the database with an expiration time."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Calculate expiration time
        # SQLite stores dates as strings, let's use standard ISO format
        now = datetime.now()
        expires_at = (now + timedelta(minutes=validity_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        created_at = now.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            # Mark previous active OTPs for this booking as used/invalidated
            cursor.execute(
                "UPDATE otps SET used = 1 WHERE booking_id = ? AND used = 0",
                (booking_id,)
            )
            
            cursor.execute(
                """INSERT INTO otps (booking_id, phone_number, otp_code, created_at, expires_at, used)
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (booking_id, phone_number, otp_code, created_at, expires_at)
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error creating OTP record: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    @staticmethod
    def verify(booking_id, otp_code):
        """
        Verifies if the submitted OTP code is correct, not expired, and not yet used.
        If valid, marks it as used and returns True.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            # Find an unused, non-expired OTP matching booking_id and otp_code
            otp = cursor.execute(
                """SELECT * FROM otps 
                   WHERE booking_id = ? AND otp_code = ? AND used = 0 AND datetime(expires_at) > datetime(?)""",
                (booking_id, str(otp_code), now_str)
            ).fetchone()
            
            if otp:
                # Mark as used
                cursor.execute(
                    "UPDATE otps SET used = 1 WHERE otp_id = ?",
                    (otp["otp_id"],)
                )
                conn.commit()
                return True, "OTP verified successfully"
            else:
                # Let's check if the OTP exists but is expired or already used
                any_otp = cursor.execute(
                    "SELECT * FROM otps WHERE booking_id = ? AND otp_code = ?",
                    (booking_id, str(otp_code))
                ).fetchone()
                
                if not any_otp:
                    return False, "Invalid OTP code"
                elif any_otp["used"] == 1:
                    return False, "OTP has already been used"
                else:
                    return False, "OTP has expired"
        except Exception as e:
            print(f"Error verifying OTP: {e}")
            return False, f"Database error: {str(e)}"
        finally:
            conn.close()

    @staticmethod
    def get_latest_active_by_booking(booking_id):
        """Retrieves the latest unused, non-expired OTP record for UI test display."""
        conn = get_db_connection()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        otp = conn.execute(
            """SELECT * FROM otps 
               WHERE booking_id = ? AND used = 0 AND datetime(expires_at) > datetime(?) 
               ORDER BY created_at DESC LIMIT 1""",
            (booking_id, now_str)
        ).fetchone()
        conn.close()
        return dict(otp) if otp else None
        
    @staticmethod
    def get_active_otp_requests_count():
        """Returns the number of current pending/unused, non-expired OTP requests in the system."""
        conn = get_db_connection()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        count = conn.execute(
            "SELECT COUNT(DISTINCT booking_id) FROM otps WHERE used = 0 AND datetime(expires_at) > datetime(?)",
            (now_str,)
        ).fetchone()[0] or 0
        conn.close()
        return count
