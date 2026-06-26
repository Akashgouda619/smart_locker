import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "smart_locker_super_secret_key_123456")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt_secret_key_for_smart_locker_api_98765")
    JWT_ACCESS_TOKEN_EXPIRES = 24  # Token validity in hours
    
    # SQLite Database Configuration
    DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "locker.db"))
    
    # UPI Configuration
    UPI_VPA = os.environ.get("UPI_VPA", "7019007474@ptaxis")
    UPI_PAYEE_NAME = os.environ.get("UPI_PAYEE_NAME", "Akashgouda G Kopparad")
    PRICE_PER_HOUR = 20  # Price in INR
    
    # SMS Configuration
    SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "fast2sms") # mock, twilio, fast2sms, msg91
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")
    FAST2SMS_API_KEY = os.environ.get("FAST2SMS_API_KEY", "jKMfBadulIE3csx4F2zAgJNHZ1nwkO7pLCv5VhRtTQXeq9ybYoPxCgzp2brlL4vGyafmKMJqeiF3VHRB")
    MSG91_AUTH_KEY = os.environ.get("MSG91_AUTH_KEY", "")
    MSG91_SENDER_ID = os.environ.get("MSG91_SENDER_ID", "LKRsys")
    MSG91_TEMPLATE_ID = os.environ.get("MSG91_TEMPLATE_ID", "")
