import json
import unittest
import os
import sys

# Add backend directory to path so we can import modules correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.db import get_db_connection

class TestSmartLockerBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use a separate test database to avoid messing with locker.db
        cls.db_name = "test_locker.db"
        cls.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), cls.db_name)
        
        # Override DATABASE_PATH and SMS_PROVIDER in Config
        from config import Config
        Config.DATABASE_PATH = cls.db_path
        Config.SMS_PROVIDER = "mock"
        
        # Create app and client
        cls.app = create_app()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        # Remove test database file
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except OSError:
                pass

    def test_full_locker_workflow(self):
        # 1. Register User
        register_payload = {
            "full_name": "Test User",
            "phone": "9876543210",
            "email": "user@example.com",
            "password": "securepassword123"
        }
        res = self.client.post("/api/auth/register", json=register_payload)
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data.decode("utf-8"))
        self.assertTrue(data["success"])
        
        # 2. Login User to get JWT
        login_payload = {
            "email": "user@example.com",
            "password": "securepassword123"
        }
        res = self.client.post("/api/auth/login", json=login_payload)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode("utf-8"))
        self.assertTrue(data["success"])
        token = data["data"]["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. View Lockers (LOCKER_001 should be seeded)
        res = self.client.get("/api/lockers")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode("utf-8"))
        self.assertTrue(data["success"])
        lockers = data["data"]
        self.assertEqual(len(lockers), 1)
        self.assertEqual(lockers[0]["locker_id"], "LOCKER_001")
        self.assertEqual(lockers[0]["status"], "available")

        # 4. Create Booking (LOCKER_001 for 60 minutes)
        booking_payload = {
            "locker_id": "LOCKER_001",
            "rental_duration": 60
        }
        res = self.client.post("/api/bookings/create", json=booking_payload, headers=headers)
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data.decode("utf-8"))
        self.assertTrue(data["success"])
        booking_id = data["data"]["booking_id"]
        self.assertEqual(data["data"]["booking_status"], "pending_payment")
        
        # Locker should now be reserved
        res = self.client.get("/api/lockers/LOCKER_001")
        data = json.loads(res.data.decode("utf-8"))
        self.assertEqual(data["data"]["status"], "reserved")

        # 5. ESP32 checks for pending payment for LOCKER_001
        res = self.client.get("/api/esp32/payment/LOCKER_001")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["booking_id"], booking_id)
        self.assertTrue("qr_matrix" in data["data"])
        self.assertTrue(data["data"]["qr_size"] > 0)
        self.assertEqual(data["data"]["payment_status"], "pending_payment")

        # 6. ESP32 checks locker status (should not unlock yet as payment is pending)
        res = self.client.get("/api/esp32/locker/LOCKER_001/status")
        data = json.loads(res.data.decode("utf-8"))
        self.assertFalse(data["data"]["unlock"])
        self.assertEqual(data["data"]["payment_status"], "pending_payment")

        # 7. Simulate Payment Success (Webhook / Web UI confirmation)
        payment_payload = {
            "booking_id": booking_id,
            "transaction_id": "TXN-MOCK-123456789"
        }
        res = self.client.post("/api/payment/mock-success", json=payment_payload)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["payment_status"], "paid")

        # 8. ESP32 checks locker status (should transition to waiting_for_door_close, unlock: true)
        res = self.client.get("/api/esp32/locker/LOCKER_001/status")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode("utf-8"))
        self.assertTrue(data["data"]["unlock"])
        self.assertEqual(data["data"]["payment_status"], "waiting_for_door_close")

        # 9. User closes storage door (simulates CLOSE DOOR UI click)
        res = self.client.post(f"/api/bookings/{booking_id}/close-storage", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode("utf-8"))
        self.assertTrue(data["success"])

        # Locker should now be occupied
        res = self.client.get("/api/lockers/LOCKER_001")
        data = json.loads(res.data.decode("utf-8"))
        self.assertEqual(data["data"]["status"], "occupied")

        # 10. ESP32 checks locker status (should be active_rental, unlock: false)
        res = self.client.get("/api/esp32/locker/LOCKER_001/status")
        data = json.loads(res.data.decode("utf-8"))
        self.assertFalse(data["data"]["unlock"])
        self.assertEqual(data["data"]["payment_status"], "active_rental")

        # 11. User requests retrieval - Generates OTP
        res = self.client.post(f"/api/bookings/{booking_id}/generate-otp", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode("utf-8"))
        self.assertTrue(data["success"])
        otp_code = data["data"]["otp_code"]

        # 12. ESP32 checks locker status (should show otp_generated, unlock: false)
        res = self.client.get("/api/esp32/locker/LOCKER_001/status")
        data = json.loads(res.data.decode("utf-8"))
        self.assertFalse(data["data"]["unlock"])
        self.assertEqual(data["data"]["payment_status"], "otp_generated")

        # 13. User submits verification OTP
        verify_payload = {
            "otp": otp_code
        }
        res = self.client.post(f"/api/bookings/{booking_id}/verify-otp", json=verify_payload, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode("utf-8"))
        self.assertTrue(data["success"])

        # 14. ESP32 checks locker status (should be retrieval_approved, unlock: true)
        res = self.client.get("/api/esp32/locker/LOCKER_001/status")
        data = json.loads(res.data.decode("utf-8"))
        self.assertTrue(data["data"]["unlock"])
        self.assertEqual(data["data"]["payment_status"], "retrieval_approved")

        # 15. User closes retrieval door (simulates CLOSE LOCKER UI click)
        res = self.client.post(f"/api/bookings/{booking_id}/close-retrieval", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode("utf-8"))
        self.assertTrue(data["success"])

        # Locker should be available again
        res = self.client.get("/api/lockers/LOCKER_001")
        data = json.loads(res.data.decode("utf-8"))
        self.assertEqual(data["data"]["status"], "available")

        # ESP32 checks status again (should be back to idle/available status)
        res = self.client.get("/api/esp32/locker/LOCKER_001/status")
        data = json.loads(res.data.decode("utf-8"))
        self.assertFalse(data["data"]["unlock"])
        self.assertIn(data["data"]["payment_status"], (None, "completed", "null", ""))

if __name__ == "__main__":
    unittest.main()
