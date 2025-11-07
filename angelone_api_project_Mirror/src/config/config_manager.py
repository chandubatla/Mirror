import json
import os
from dotenv import load_dotenv

class ConfigManager:
    def __init__(self):
        load_dotenv(dotenv_path="/root/config.env")
        load_dotenv(dotenv_path="../.env")
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
        """Load settings with defaults"""
        settings = {
            'dry_run': True,  # Safe default
            'max_trade_qty': 50,
            'price_tolerance': 0.01,
            'max_retries': 3,
            'retry_delay': 2,
            'check_interval': 10,
            'processed_trades_db': 'data/processed_trades.db',
            'mirror_enabled': False  # Add missing setting
        }
        
        # Override from env/config
        config_settings = self._load_from_env_or_file()
        settings.update(config_settings)
        
        return settings
    
    def _load_from_env_or_file(self):
        """Load settings from environment variables or config file"""
        config_settings = {}
        
        # Load from environment variables if present
        env_mappings = {
            'DRY_RUN': ('dry_run', lambda x: x.lower() == 'true'),
            'MAX_TRADE_QTY': ('max_trade_qty', int),
            'PRICE_TOLERANCE': ('price_tolerance', float),
            'MAX_RETRIES': ('max_retries', int),
            'RETRY_DELAY': ('retry_delay', int),
            'CHECK_INTERVAL': ('check_interval', int),
            'PROCESSED_TRADES_DB': ('processed_trades_db', str),
            'MIRROR_ENABLED': ('mirror_enabled', lambda x: x.lower() == 'true')  # Add env mapping
        }

        for env_key, (setting_key, converter) in env_mappings.items():
            if env_value := os.getenv(env_key):
                try:
                    config_settings[setting_key] = converter(env_value)
                except ValueError as e:
                    self.logger.warning(f"Failed to convert {env_key}: {e}")
                    
        return config_settings

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