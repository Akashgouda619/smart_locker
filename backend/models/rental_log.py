from database.db import get_db_connection

class RentalLogModel:
    @staticmethod
    def create(booking_id, start_time):
        """Creates a rental log when the locker is unlocked by the ESP32."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO rental_logs (booking_id, start_time) VALUES (?, ?)",
                (booking_id, start_time)
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error creating rental log: {e}")
            return None
        finally:
            conn.close()

    @staticmethod
    def close_log(booking_id, end_time, duration_minutes):
        """Closes a rental log when the locker is locked/completed."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE rental_logs SET end_time = ?, duration_minutes = ? WHERE booking_id = ? AND end_time IS NULL",
                (end_time, duration_minutes, booking_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error closing rental log: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def get_by_booking(booking_id):
        """Fetches the rental log for a given booking ID."""
        conn = get_db_connection()
        log = conn.execute("SELECT * FROM rental_logs WHERE booking_id = ?", (booking_id,)).fetchone()
        conn.close()
        return dict(log) if log else None

    @staticmethod
    def get_all():
        """Fetches all rental logs in the system."""
        conn = get_db_connection()
        logs = conn.execute(
            """SELECT r.*, b.locker_id, u.full_name 
               FROM rental_logs r
               JOIN bookings b ON r.booking_id = b.booking_id
               JOIN users u ON b.user_id = u.id
               ORDER BY r.start_time DESC"""
        ).fetchall()
        conn.close()
        return [dict(l) for l in logs]
