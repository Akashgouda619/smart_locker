import sqlite3

def clean():
    db_path = 'c:/smart_locker/backend/locker.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("UPDATE lockers SET status = 'available' WHERE locker_id = 'LOCKER_001'")
    c.execute("DELETE FROM bookings")
    c.execute("DELETE FROM payments")
    c.execute("DELETE FROM otps")
    c.execute("DELETE FROM rental_logs")
    conn.commit()
    print("Database cleaned: LOCKER_001 set to available, all bookings cleared.")
    conn.close()

if __name__ == "__main__":
    clean()
