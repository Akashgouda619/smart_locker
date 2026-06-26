from database.db import get_db_connection

class LockerModel:
    @staticmethod
    def get_all():
        """Fetches all lockers in the system."""
        conn = get_db_connection()
        lockers = conn.execute("SELECT * FROM lockers").fetchall()
        conn.close()
        return [dict(l) for l in lockers]

    @staticmethod
    def get_available():
        """Fetches all lockers currently available for booking."""
        conn = get_db_connection()
        lockers = conn.execute("SELECT * FROM lockers WHERE status = 'available'").fetchall()
        conn.close()
        return [dict(l) for l in lockers]

    @staticmethod
    def get_by_id(locker_id):
        """Fetches a single locker by its unique locker_id (e.g. LOCKER_001)."""
        conn = get_db_connection()
        locker = conn.execute("SELECT * FROM lockers WHERE locker_id = ?", (locker_id,)).fetchone()
        conn.close()
        return dict(locker) if locker else None

    @staticmethod
    def update_status(locker_id, status):
        """Updates the status of a locker."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE lockers SET status = ? WHERE locker_id = ?",
                (status, locker_id)
            )
            conn.commit()
            
            # Sync to Firestore
            try:
                from services.firebase_service import sync_locker_status
                sync_locker_status(locker_id, status)
            except Exception as fe:
                print(f"Failed to sync locker status to Firestore: {fe}")
                
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating locker status: {e}")
            return False
        finally:
            conn.close()
