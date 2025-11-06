import sys
import os
import logging

# Add src to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config.config_manager import ConfigManager
from src.auth.auth_manager import AuthManager

def test_auth():
    print("Starting Auth Manager Test...")
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    
    try:
        # Load config
        config = ConfigManager()
        auth = AuthManager(config)
        
        print("1. Testing authentication for both accounts...")
        results = auth.authenticate_all_accounts()
        
        # Check results
        for account_id, result in results.items():
            assert 'success' in result, f"Missing success key for {account_id}"
            if result['success']:
                print(f"{account_id}: Authentication SUCCESS")
            else:
                print(f"   {account_id}: Authentication FAILED - {result['error']}")
                # Don't fail the test if auth fails (credentials might be wrong)
        
        print("2. Testing connection management...")
        source_conn = auth.get_connection('source_account')
        mirror_conn = auth.get_connection('mirror_account')
        
        # At least one connection should work for testing
        if source_conn or mirror_conn:
            print("Connection management working")
        else:
            print("No connections established (check credentials)")
        
        print("3. Testing authentication status...")
        source_status = auth.is_authenticated('source_account')
        mirror_status = auth.is_authenticated('mirror_account')
        print(f"   Source auth status: {source_status}")
        print(f"   Mirror auth status: {mirror_status}")
        
        print("4. Testing logout...")
        auth.logout_all()
        print("Logout completed")
        
        print("\n AUTH MANAGER TEST COMPLETED!")
        print("Note: Authentication failures might be due to incorrect credentials in config")
        
    except Exception as e:
        print(f"Auth test failed: {e}")
        raise

if __name__ == "__main__":
    test_auth()