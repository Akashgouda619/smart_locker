import requests
import json
from config import Config

class SMSService:
    @staticmethod
    def send_otp(phone_number, otp_code, expiry_minutes=5):
        """
        Sends a retrieval OTP SMS using the configured SMS provider.
        Configured via Config.SMS_PROVIDER: 'mock', 'twilio', 'fast2sms', 'msg91'
        """
        message = f"Smart Locker OTP\nYour retrieval code is: {otp_code}\nValid for {expiry_minutes} minutes."
        provider = Config.SMS_PROVIDER.lower()
        
        print(f"[SMS SERVICE] Routing message to {phone_number} using provider: {provider}")
        
        if provider == "twilio":
            return SMSService._send_twilio(phone_number, message)
        elif provider == "fast2sms":
            return SMSService._send_fast2sms(phone_number, otp_code, expiry_minutes)
        elif provider == "msg91":
            return SMSService._send_msg91(phone_number, otp_code, expiry_minutes)
        else:
            # Fallback to mock
            return SMSService._send_mock(phone_number, message)

    @staticmethod
    def _send_mock(phone_number, message):
        """Logs the SMS message to console instead of calling external APIs (Dev/Test mode)"""
        print("=" * 60)
        print("  [MOCK SMS SEND SUCCESS]")
        print(f"  To:      {phone_number}")
        print(f"  Message: {message.replace(chr(10), ' | ')}")
        print("=" * 60)
        return True, "SMS sent successfully (Mock Mode)"

    @staticmethod
    def _send_twilio(phone_number, message):
        """Sends SMS via Twilio REST API"""
        sid = Config.TWILIO_ACCOUNT_SID
        token = Config.TWILIO_AUTH_TOKEN
        from_num = Config.TWILIO_PHONE_NUMBER
        
        if not sid or not token or not from_num:
            return False, "Twilio configuration missing (SID, token, or sender number)"
            
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        
        # Ensure phone number has international format prefix (e.g. +91)
        to_num = phone_number
        if not to_num.startswith("+"):
            # Default to India (+91) if 10-digit number
            if len(to_num) == 10:
                to_num = f"+91{to_num}"
            else:
                to_num = f"+{to_num}"
                
        payload = {
            "To": to_num,
            "From": from_num,
            "Body": message
        }
        
        try:
            response = requests.post(url, data=payload, auth=(sid, token), timeout=10)
            if response.status_code in (200, 201):
                return True, "SMS sent successfully via Twilio"
            else:
                err_msg = response.json().get("message", "Unknown Twilio error")
                print(f"[Twilio Error] Status: {response.status_code} | Message: {err_msg}")
                return False, f"Twilio API failed: {err_msg}"
        except Exception as e:
            print(f"[Twilio Exception] {e}")
            return False, f"Twilio connection exception: {str(e)}"

    @staticmethod
    def _send_fast2sms(phone_number, otp_code, expiry_minutes):
        """Sends SMS via Fast2SMS API (Quick Transactional route)"""
        api_key = Config.FAST2SMS_API_KEY
        if not api_key:
            return False, "Fast2SMS API key missing"
            
        # Fast2SMS URL for quick SMS or OTP
        url = "https://www.fast2sms.com/dev/bulkV2"
        
        # We can use variables in transactional/otp templates or direct message
        # India phone number format: 10-digit number
        clean_phone = phone_number.replace("+91", "").strip()
        
        # Fast2SMS supports variables in template or direct message.
        # Direct message (using Fast2SMS Quick SMS):
        message_body = f"Smart Locker OTP. Your retrieval code is: {otp_code}. Valid for {expiry_minutes} minutes."
        
        payload = {
            "message": message_body,
            "language": "english",
            "route": "q", # Quick SMS route
            "numbers": clean_phone
        }
        
        headers = {
            "authorization": api_key,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=10)
            res_data = response.json()
            if response.status_code == 200 and res_data.get("return") is True:
                return True, "SMS sent successfully via Fast2SMS"
            else:
                err_msg = res_data.get("message", "Unknown error")
                print(f"[Fast2SMS Error] {err_msg}")
                return False, f"Fast2SMS API failed: {err_msg}"
        except Exception as e:
            print(f"[Fast2SMS Exception] {e}")
            return False, f"Fast2SMS connection exception: {str(e)}"

    @staticmethod
    def _send_msg91(phone_number, otp_code, expiry_minutes):
        """Sends SMS via MSG91 Flow API"""
        auth_key = Config.MSG91_AUTH_KEY
        template_id = Config.MSG91_TEMPLATE_ID
        sender_id = Config.MSG91_SENDER_ID
        
        if not auth_key or not template_id:
            return False, "MSG91 configuration missing (Auth key or template ID)"
            
        url = "https://api.msg91.com/api/v5/flow/"
        
        # Format phone number
        clean_phone = phone_number
        if clean_phone.startswith("+"):
            clean_phone = clean_phone.replace("+", "")
        elif len(clean_phone) == 10:
            clean_phone = f"91{clean_phone}" # default country code prefix
            
        payload = {
            "flow_id": template_id,
            "sender": sender_id,
            "recipients": [
                {
                    "mobiles": clean_phone,
                    "otp": otp_code,
                    "expiry": f"{expiry_minutes} minutes"
                }
            ]
        }
        
        headers = {
            "authkey": auth_key,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=10)
            res_data = response.json()
            if response.status_code == 200 and res_data.get("type") == "success":
                return True, "SMS sent successfully via MSG91"
            else:
                err_msg = res_data.get("message", "Unknown MSG91 error")
                print(f"[MSG91 Error] {err_msg}")
                return False, f"MSG91 API failed: {err_msg}"
        except Exception as e:
            print(f"[MSG91 Exception] {e}")
            return False, f"MSG91 connection exception: {str(e)}"
