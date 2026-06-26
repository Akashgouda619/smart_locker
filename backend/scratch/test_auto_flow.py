import requests
import time
import sys

BASE_URL = "http://localhost:5000"

def test_flow():
    print("==================================================")
    print(" STARTING SMART LOCKER AUTO DETECT & TFT OTP FLOW ")
    print("==================================================")

    # 1. Rent a locker (simulate booking)
    print("\n[1] Submitting booking request to /rent...")
    payload = {
        "name": "Integration Test User",
        "phone": "9988776655",
        "locker_id": "LOCKER_001",
        "duration": "2"
    }
    
    # Send post request to /rent
    session = requests.Session()
    res = session.post(f"{BASE_URL}/rent", data=payload)
    if res.status_code != 200:
        print(f"[FAIL] Booking failed: {res.status_code}")
        print(res.text[:300])
        return False
    print("[OK] Booking created successfully!")
    
    # We need to extract the Booking ID from the response or check the DB.
    # Since our DB starts at ID 1 and increases, let's query the database to find the latest booking ID.
    import sqlite3
    import os
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locker.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    row = cursor.execute("SELECT booking_id, booking_status, created_at FROM bookings ORDER BY booking_id DESC LIMIT 1").fetchone()
    conn.close()
    
    if not row:
        print("[FAIL] Could not find booking in DB.")
        return False
    
    booking_id, status, created_at = row
    print(f"Found latest booking in database: Booking ID = #{booking_id}, status = '{status}', created_at = '{created_at}'")
    
    # 2. Verify initial payment check-status is false
    print(f"\n[2] Checking initial payment status for #{booking_id}...")
    res = requests.get(f"{BASE_URL}/api/payment/check-status/{booking_id}")
    data = res.json()
    print("Response:", data)
    if data.get("paid") is not False:
        print("[FAIL] Error: Payment status should be unpaid initially.")
        return False
    print("[OK] Initial status is unpaid.")
    
    # 3. Submit a mock 12-digit UTR to confirm payment
    import random
    random_utr = "".join([str(random.randint(0, 9)) for _ in range(12)])
    print(f"\n[3] Submitting mock 12-digit UTR '{random_utr}' to confirm payment...")
    confirm_payload = {
        "order_id": booking_id,
        "utr": random_utr
    }
    res = requests.post(f"{BASE_URL}/api/payment/confirm", json=confirm_payload)
    confirm_data = res.json()
    print("Confirm Response:", confirm_data)
    if not confirm_data.get("success"):
        print("[FAIL] Error: Failed to confirm payment with UTR.")
        return False
    
    # Re-check status - should be paid!
    res = requests.get(f"{BASE_URL}/api/payment/check-status/{booking_id}")
    data = res.json()
    print("Payment status after confirmation:", data)
    if data.get("paid") is not True:
        print("[FAIL] Error: Payment status should be paid.")
        return False
    print("[OK] Payment confirmed successfully!")

    # 4. Check ESP32 status polls
    print(f"\n[4] Polling status from ESP32 perspective...")
    res = requests.get(f"{BASE_URL}/api/esp32/locker/LOCKER_001/status")
    esp_data = res.json()
    print("Response:", esp_data)
    if esp_data["data"]["payment_status"] != "waiting_for_door_close":
        print("[FAIL] Error: State should be waiting_for_door_close.")
        return False
    print("[OK] State correctly transitioned to waiting_for_door_close!")

    # 5. Simulate closing storage door
    print(f"\n[5] Simulating CLOSE DOOR (Storage Door closed)...")
    res = requests.post(f"{BASE_URL}/api/web/close-storage", json={"booking_id": booking_id})
    print("Response:", res.json())
    if not res.json().get("success"):
        print("[FAIL] Error: Failed to close storage door.")
        return False
    print("[OK] Storage door closed. Active rental timer started.")

    # 6. Check ESP32 state is active_rental
    res = requests.get(f"{BASE_URL}/api/esp32/locker/LOCKER_001/status")
    esp_data = res.json()
    if esp_data["data"]["payment_status"] != "active_rental":
        print(f"[FAIL] Error: State should be active_rental (current: {esp_data['data']['payment_status']})")
        return False
    print("[OK] ESP32 state is active_rental.")

    # 7. Generate retrieval OTP
    print(f"\n[6] Generating retrieval OTP...")
    res = requests.post(f"{BASE_URL}/api/web/generate-otp", json={"booking_id": booking_id})
    otp_res = res.json()
    print("Response:", otp_res)
    if not otp_res.get("success"):
        print("[FAIL] Error: Failed to generate OTP.")
        return False
    if "otp_code" in otp_res:
        print("[FAIL] Error: Mock otp_code should NOT be returned to the client browser!")
        return False
    print("[OK] OTP generated successfully. Code is hidden from browser.")

    # 8. Verify ESP32 status poll returns the OTP code dynamically
    print(f"\n[7] Verifying ESP32 status returns the OTP code dynamically for TFT screen display...")
    res = requests.get(f"{BASE_URL}/api/esp32/locker/LOCKER_001/status")
    esp_data = res.json()
    print("Response:", esp_data)
    otp_code = esp_data["data"].get("otp_code")
    if not otp_code or len(otp_code) != 6:
        print(f"[FAIL] Error: Dynamic otp_code missing or invalid (current: {otp_code})")
        return False
    print(f"[OK] Successfully retrieved OTP code from ESP32 status: '{otp_code}'!")

    # 9. Verify OTP on retrieve page
    print(f"\n[8] Submitting OTP '{otp_code}' to verify retrieval...")
    res = requests.post(f"{BASE_URL}/api/web/verify-otp", json={"booking_id": booking_id, "otp": otp_code})
    print("Response:", res.json())
    if not res.json().get("success"):
        print("[FAIL] Error: Failed to verify OTP.")
        return False
    print("[OK] OTP verified successfully. Locker servo unlocked.")

    # 10. Verify state is retrieval_approved
    res = requests.get(f"{BASE_URL}/api/esp32/locker/LOCKER_001/status")
    esp_data = res.json()
    if esp_data["data"]["payment_status"] != "retrieval_approved":
         print(f"[FAIL] Error: Expected state retrieval_approved, got {esp_data['data']['payment_status']}")
         return False
    print("[OK] State is retrieval_approved.")

    # 11. Finalize retrieval and close locker
    print(f"\n[9] Simulating CLOSE LOCKER (Final door closed)...")
    res = requests.post(f"{BASE_URL}/api/web/close-retrieval", json={"booking_id": booking_id})
    print("Response:", res.json())
    if not res.json().get("success"):
        print("[FAIL] Error: Failed to close retrieval.")
        return False
    print("[OK] Rental session completed successfully!")

    # 12. Verify locker is idle/available
    res = requests.get(f"{BASE_URL}/api/esp32/locker/LOCKER_001/status")
    esp_data = res.json()
    if esp_data["data"]["locker_status"] != "available":
        print(f"[FAIL] Error: Expected locker available, got {esp_data['data']['locker_status']}")
        return False
    print("[OK] Locker returned to available state.")

    print("\n==================================================")
    print(" *** ALL AUTOMATED FLOW TESTS PASSED SUCCESSFULLY! *** ")
    print("==================================================")
    return True

if __name__ == "__main__":
    test_flow()
