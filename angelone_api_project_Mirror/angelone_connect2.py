from SmartApi import SmartConnect
import pyotp
import json
from datetime import datetime

from dotenv import load_dotenv
import os
load_dotenv(dotenv_path="D:/tax/config.env")
load_dotenv(dotenv_path="../.env")   # go one directory up
API_KEY   = os.getenv("MIRROR_API_KEY")
CLIENT_ID = os.getenv("MIRROR_CLIENT_ID")
MPIN      = os.getenv("MIRROR_MPIN")
TOTP_TOKEN = os.getenv("MIRROR_TOTP_TOKEN")
    
# Generate current TOTP
totp = pyotp.TOTP(TOTP_TOKEN).now()

# Authenticate
obj = SmartConnect(api_key=API_KEY)
data = obj.generateSession(CLIENT_ID, MPIN, totp)

if data['status']:
    print("✅ Authentication successful!")
    jwt_token = data['data']['jwtToken']
    refresh_token = data['data']['refreshToken']
    
    print("JWT Token:", jwt_token)
    print("Refresh Token:", refresh_token)
    
    # Now you can make API calls
    try:
        holdings = obj.holding()
        print("\n📊 Holdings:")
        print(json.dumps(holdings, indent=2))
    except Exception as e:
        print("Error fetching holdings:", e)
        
else:
    print("❌ Authentication failed:", data.get('message'))
