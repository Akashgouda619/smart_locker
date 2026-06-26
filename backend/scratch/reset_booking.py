import sqlite3

def reset():
    db_path = 'c:/smart_locker/backend/locker.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("UPDATE bookings SET booking_status = 'active_rental' WHERE booking_id = 1")
    c.execute("UPDATE lockers SET status = 'occupied' WHERE locker_id = 'LOCKER_001'")
    conn.commit()
    print("Database updated: Booking #1 set to active_rental, LOCKER_001 set to occupied.")
    conn.close()

if __name__ == "__main__":
    reset()
