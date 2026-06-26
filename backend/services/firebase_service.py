import firebase_admin
from firebase_admin import credentials, firestore
import os

db = None
initialized = False

def init_firebase():
    """Initializes the Firebase Admin SDK using a service account key JSON file."""
    global db, initialized
    
    # Path: backend/config/firebase-key.json
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_dir = os.path.join(backend_dir, "config")
    
    # Ensure config folder exists
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
        
    key_path = os.path.join(config_dir, "firebase-key.json")
    
    if os.path.exists(key_path):
        try:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            initialized = True
            print(">>> Firebase Admin successfully initialized.")
        except Exception as e:
            print(f">>> Failed to initialize Firebase Admin SDK: {e}")
    else:
        print(f">>> Firebase Admin key NOT found at: {key_path}")
        print(">>> Firestore real-time sync is currently in MOCK MODE.")
        print(">>> To enable, download a Service Account Key JSON from Firebase Console and save it as backend/config/firebase-key.json")

def sync_locker_status(locker_id, status):
    """Pushes locker status changes (available / occupied / reserved) to Firestore."""
    if not initialized:
        return
    try:
        doc_ref = db.collection("lockers").document(locker_id)
        doc_ref.set({
            "locker_id": locker_id,
            "status": status,
            "last_updated": firestore.SERVER_TIMESTAMP
        }, merge=True)
        print(f"[Firebase Sync] Locker {locker_id} set to {status}")
    except Exception as e:
        print(f"[Firebase Sync Error] Locker {locker_id}: {e}")

def sync_booking(booking_id, user_id, email, locker_id, booking_status, rental_duration, amount, start_time=None, otp_code=None):
    """Pushes booking details and state transitions to Firestore in real-time."""
    if not initialized:
        return
    try:
        doc_ref = db.collection("bookings").document(str(booking_id))
        booking_data = {
            "booking_id": booking_id,
            "user_id": user_id,
            "email": email,
            "locker_id": locker_id,
            "booking_status": booking_status,
            "rental_duration": rental_duration,
            "amount": amount,
            "last_updated": firestore.SERVER_TIMESTAMP
        }
        
        if start_time:
            booking_data["start_time"] = start_time
        if otp_code:
            booking_data["otp_code"] = otp_code
            
        doc_ref.set(booking_data, merge=True)
        print(f"[Firebase Sync] Booking #{booking_id} set to {booking_status}")
    except Exception as e:
        print(f"[Firebase Sync Error] Booking #{booking_id}: {e}")

def delete_booking_sync(booking_id):
    """Deletes booking records from Firestore (used for cancellations/resets)."""
    if not initialized:
        return
    try:
        db.collection("bookings").document(str(booking_id)).delete()
        print(f"[Firebase Sync] Booking #{booking_id} removed from Firestore.")
    except Exception as e:
        print(f"[Firebase Sync Error] Delete Booking #{booking_id}: {e}")
