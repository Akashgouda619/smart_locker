import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "locker.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Reset locker status
cursor.execute("UPDATE lockers SET status = 'available'")

# Cancel unfinished bookings
cursor.execute("UPDATE bookings SET booking_status = 'cancelled' WHERE booking_status != 'completed'")

conn.commit()
conn.close()
print("Database successfully reset!")
