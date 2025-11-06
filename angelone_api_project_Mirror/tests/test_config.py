import sys
import os

# Add src to Python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config.config_manager import ConfigManager

def test_config():
    print("Starting Config Manager Test...")
    
    try:
        config = ConfigManager()
        
        # Test 1: Check if accounts are loaded
        accounts = config.get_all_accounts()
        assert 'source_account' in accounts, "Source account missing"
        assert 'mirror_account' in accounts, "Mirror account missing"
        print("Accounts loaded correctly")
        
        # Test 2: Check account structure
        source_acc = config.get_account('source_account')
        required_keys = ['API_KEY', 'CLIENT_ID', 'MPIN', 'TOTP_TOKEN', 'name']
        for key in required_keys:
            assert key in source_acc, f"Missing key: {key}"
        print("Account structure correct")
        
        # Test 3: Check settings
        settings = config.get_settings()
        assert 'check_interval' in settings, "Settings missing"
        print("Settings loaded correctly")
        
        # Test 4: Test setting update
        original_value = settings['mirror_enabled']
        config.update_setting('mirror_enabled', not original_value)
        updated_settings = config.get_settings()
        assert updated_settings['mirror_enabled'] != original_value, "Setting update failed"
        print("Setting update works")
        
        print("\nALL CONFIG TESTS PASSED!")
        
    except Exception as e:
        print(f"Test failed: {e}")
        raise

if __name__ == "__main__":
    test_config()