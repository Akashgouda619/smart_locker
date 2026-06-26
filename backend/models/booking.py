from database.db import get_db_connection

class BookingModel:
    @staticmethod
    def create(user_id, locker_id, rental_duration, amount):
        """Creates a new booking record."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO bookings (user_id, locker_id, rental_duration, amount, booking_status) 
                   VALUES (?, ?, ?, ?, 'pending_payment')""",
                (user_id, locker_id, rental_duration, amount)
            )
            conn.commit()
            booking_id = cursor.lastrowid
            return BookingModel.get_by_id(booking_id)
        except Exception as e:
            print(f"Error creating booking: {e}")
            return None
        finally:
            conn.close()

    @staticmethod
    def get_by_id(booking_id):
        """Fetches a single booking by booking_id."""
        conn = get_db_connection()
        booking = conn.execute(
            """SELECT b.*, u.full_name, u.phone, u.email, l.locker_number, l.location, l.size 
               FROM bookings b
               JOIN users u ON b.user_id = u.id
               JOIN lockers l ON b.locker_id = l.locker_id
               WHERE b.booking_id = ?""",
            (booking_id,)
        ).fetchone()
        conn.close()
        return dict(booking) if booking else None

    @staticmethod
    def get_by_user(user_id):
        """Fetches all bookings for a specific user, ordered by creation date."""
        conn = get_db_connection()
        bookings = conn.execute(
            """SELECT b.*, l.locker_number, l.location, l.size 
               FROM bookings b
               JOIN lockers l ON b.locker_id = l.locker_id
               WHERE b.user_id = ? 
               ORDER BY b.created_at DESC""",
            (user_id,)
        ).fetchall()
        conn.close()
        return [dict(b) for b in bookings]

    @staticmethod
    def get_pending_payment_by_locker(locker_id):
        """Fetches the latest booking for a locker in pending_payment state."""
        conn = get_db_connection()
        booking = conn.execute(
            "SELECT * FROM bookings WHERE locker_id = ? AND booking_status = 'pending_payment' ORDER BY created_at DESC LIMIT 1",
            (locker_id,)
        ).fetchone()
        conn.close()
        return dict(booking) if booking else None

    @staticmethod
    def get_paid_or_active_by_locker(locker_id):
        """Fetches the latest active booking for a locker."""
        conn = get_db_connection()
        booking = conn.execute(
            """SELECT * FROM bookings 
               WHERE locker_id = ? AND booking_status IN ('waiting_for_door_close', 'active_rental', 'otp_generated', 'retrieval_approved') 
               ORDER BY created_at DESC LIMIT 1""",
            (locker_id,)
        ).fetchone()
        conn.close()
        return dict(booking) if booking else None

    @staticmethod
    def get_all():
        """Fetches all bookings in the system."""
        conn = get_db_connection()
        bookings = conn.execute(
            """SELECT b.*, u.full_name, l.locker_number 
               FROM bookings b
               JOIN users u ON b.user_id = u.id
               JOIN lockers l ON b.locker_id = l.locker_id
               ORDER BY b.created_at DESC"""
        ).fetchall()
        conn.close()
        return [dict(b) for b in bookings]

    @staticmethod
    def update_status(booking_id, status):
        """Updates the booking status, syncs to Firestore, and publishes MQTT commands."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE bookings SET booking_status = ? WHERE booking_id = ?",
                (status, booking_id)
            )
            conn.commit()
            
            # Sync to Firestore and publish MQTT commands
            try:
                from services.firebase_service import sync_booking, sync_locker_status
                from services.mqtt_service import publish_command
                
                booking = BookingModel.get_by_id(booking_id)
                if booking:
                    # Sync to Firestore
                    otp_code = None
                    if status == 'otp_generated':
                        otp = cursor.execute(
                            "SELECT otp_code FROM otps WHERE booking_id = ? ORDER BY created_at DESC LIMIT 1", 
                            (booking_id,)
                        ).fetchone()
                        if otp:
                            otp_code = otp["otp_code"]
                            
                    sync_booking(
                        booking_id=booking_id,
                        user_id=booking["user_id"],
                        email=booking["email"],
                        locker_id=booking["locker_id"],
                        booking_status=status,
                        rental_duration=booking["rental_duration"],
                        amount=booking["amount"],
                        start_time=booking["start_time"],
                        otp_code=otp_code
                    )
                    
                    # Sync locker status based on booking status
                    locker_id = booking["locker_id"]
                    if status in ['waiting_for_door_close', 'retrieval_approved']:
                        sync_locker_status(locker_id, "unlocked")
                    elif status in ['active_rental', 'otp_generated']:
                        sync_locker_status(locker_id, "occupied")
                    elif status in ['completed', 'cancelled']:
                        sync_locker_status(locker_id, "available")
                    elif status == 'pending_payment':
                        sync_locker_status(locker_id, "reserved")
                        
                    # Publish MQTT command to ESP32
                    if status == 'waiting_for_door_close':
                        publish_command(locker_id, "unlock", {"state": "waiting_for_door_close"})
                    elif status == 'active_rental':
                        duration_ms = booking["rental_duration"] * 60 * 1000
                        publish_command(locker_id, "lock", {"state": "active_rental", "duration_ms": duration_ms})
                    elif status == 'otp_generated':
                        if otp_code:
                            publish_command(locker_id, "show_otp", {"otp_code": otp_code})
                    elif status == 'retrieval_approved':
                        publish_command(locker_id, "unlock", {"state": "retrieval_approved"})
                    elif status in ['completed', 'cancelled']:
                        publish_command(locker_id, "reset", {"state": "available"})
                    elif status == 'pending_payment':
                        publish_command(locker_id, "pending_payment")
            except Exception as fe:
                print(f"Failed to sync Firestore or publish MQTT: {fe}")
                
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating booking status: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def update_times(booking_id, start_time=None, end_time=None):
        """Updates the rental start or end times."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if start_time and end_time:
                cursor.execute(
                    "UPDATE bookings SET start_time = ?, end_time = ? WHERE booking_id = ?",
                    (start_time, end_time, booking_id)
                )
            elif start_time:
                cursor.execute(
                    "UPDATE bookings SET start_time = ? WHERE booking_id = ?",
                    (start_time, booking_id)
                )
            elif end_time:
                cursor.execute(
                    "UPDATE bookings SET end_time = ? WHERE booking_id = ?",
                    (end_time, booking_id)
                )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating booking times: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def request_unlock(booking_id):
        """Flags that the user requested an unlock for this booking."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE bookings SET unlock_requested = 1 WHERE booking_id = ?",
                (booking_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error requesting unlock: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def reset_unlock_request(booking_id):
        """Resets the unlock request flag."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE bookings SET unlock_requested = 0 WHERE booking_id = ?",
                (booking_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error resetting unlock request: {e}")
            return False
        finally:
            conn.close()
