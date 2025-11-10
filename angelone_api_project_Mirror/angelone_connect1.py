from SmartApi import SmartConnect
import pyotp
import json
from datetime import datetime
from dotenv import load_dotenv
import os
load_dotenv(dotenv_path="/root/config.env")
load_dotenv(dotenv_path="../.env")   # go one directory up
API_KEY   = os.getenv("SOURCE_API_KEY")
CLIENT_ID = os.getenv("SOURCE_CLIENT_ID")
MPIN      = os.getenv("SOURCE_MPIN")
TOTP_TOKEN = os.getenv("SOURCE_TOTP_TOKEN")
    
    
import os
from dotenv import load_dotenv

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Go one level up (or more) to where your .env is stored
ENV_PATH = os.path.join(BASE_DIR, "..", ".env")

# Load it
load_dotenv(dotenv_path=ENV_PATH)

# Example usage
print("Loaded SMARTAPI_API_KEY:", os.getenv("SMARTAPI_API_KEY"))



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
