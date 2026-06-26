import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from services.sms_service import SMSService

Config.FAST2SMS_API_KEY = "jKMfBadulIE3csx4F2zAgJNHZ1nwkO7pLCv5VhRtTQXeq9ybYoPxCgzp2brlL4vGyafmKMJqeiF3VHRB"
Config.SMS_PROVIDER = "fast2sms"

phone = "7019007474"
if len(sys.argv) > 1:
    phone = sys.argv[1]

print(f"Testing SMS sending to {phone}...")
success, msg = SMSService.send_otp(phone, "123456", 5)
print(f"Result: success={success}, message={msg}")
