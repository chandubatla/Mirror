import json
import os
from dotenv import load_dotenv
import os
load_dotenv(dotenv_path="D:/tax/config.env")
load_dotenv(dotenv_path="../.env")   # go one directory up
class ConfigManager:
    def __init__(self):
        self.accounts = self.load_accounts()
        self.settings = self.load_settings()
    
    def load_accounts(self):
        """
        Load your 2 Angel One accounts
        Replace the values with your actual credentials
        """
        
        return {
            'source_account': {
                'API_KEY': os.getenv("SOURCE_API_KEY"),
                'CLIENT_ID': os.getenv("SOURCE_CLIENT_ID"),
                'MPIN': os.getenv("SOURCE_MPIN"),
                'TOTP_TOKEN': os.getenv("SOURCE_TOTP_TOKEN"),
                'name': os.getenv("SOURCE_NAME", "source_account")
            },
            'mirror_account': {
                'API_KEY': os.getenv("MIRROR_API_KEY"),
                'CLIENT_ID': os.getenv("MIRROR_CLIENT_ID"),
                'MPIN': os.getenv("MIRROR_MPIN"),
                'TOTP_TOKEN': os.getenv("MIRROR_TOTP_TOKEN"),
                'name': os.getenv("MIRROR_NAME", "mirror_account")
            }
        }
    
    def load_settings(self):
        """Load mirroring settings"""
        return {
            'check_interval': 10,  # Check for new trades every 10 seconds
            'slippage_tolerance': 1.0,  # 1% price tolerance
            'max_retries': 3,
            'mirror_enabled': False,  # Start with mirroring disabled
            'log_level': 'INFO'
        }
    
    def get_account(self, account_id):
        """Get specific account configuration"""
        return self.accounts.get(account_id)
    
    def get_all_accounts(self):
        """Get all accounts"""
        return self.accounts
    
    def get_settings(self):
        """Get all settings"""
        return self.settings
    
    def update_setting(self, key, value):
        """Update a setting (for manual control)"""
        if key in self.settings:
            self.settings[key] = value
            return True
        return False

# Test function for this module
def test_config_manager():
    print("Testing Config Manager...")
    config = ConfigManager()
    
    # Test accounts
    accounts = config.get_all_accounts()
    print(f"Loaded {len(accounts)} accounts: {list(accounts.keys())}")
    
    # Test settings
    settings = config.get_settings()
    print(f"Settings: {settings}")
    
    # Test individual account
    source_acc = config.get_account('source_account')
    print(f"Source account keys: {list(source_acc.keys())}")
    
    print("Config Manager test completed!")

if __name__ == "__main__":
    test_config_manager()