import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config.config_manager import ConfigManager
from src.auth.auth_manager import AuthManager
import logging

def debug_trade_api():
    """Debug what the tradeBook API actually returns"""
    print("Debugging TradeBook API...")
    
    logging.basicConfig(level=logging.DEBUG)
    
    try:
        config = ConfigManager()
        auth = AuthManager(config)
        
        # Authenticate
        auth.authenticate_account('source_account')
        connection = auth.get_connection('source_account')
        
        if not connection:
            print("No connection")
            return
        
        print("1. Calling tradeBook() API...")
        trade_data = connection.tradeBook()
        
        print("2. API Response:")
        print(f"   Type: {type(trade_data)}")
        print(f"   Full response: {trade_data}")
        
        if trade_data:
            print(f"   Status: {trade_data.get('status')}")
            print(f"   Message: {trade_data.get('message')}")
            print(f"   Data type: {type(trade_data.get('data'))}")
            print(f"   Data: {trade_data.get('data')}")
        else:
            print("trade_data is None")
        
        # Cleanup
        auth.logout_all()
        
    except Exception as e:
        print(f"Debug error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_trade_api()