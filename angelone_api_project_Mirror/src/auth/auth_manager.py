import pyotp
from SmartApi import SmartConnect
import logging
import time
from datetime import datetime, timedelta

class AuthManager:
    def __init__(self, config_manager):
        self.config = config_manager
        self.connections = {}  # Store SmartConnect objects for each account
        self.tokens = {}       # Store tokens for each account
        self.logger = logging.getLogger('auth_manager')
        
    def authenticate_account(self, account_id):
        """
        Authenticate a single account
        Returns: (success, connection_object, error_message)
        """
        try:
            account_config = self.config.get_account(account_id)
            if not account_config:
                return False, None, f"Account {account_id} not found"
            
            # Generate TOTP
            totp = pyotp.TOTP(account_config['TOTP_TOKEN']).now()
            
            # Create connection
            obj = SmartConnect(api_key=account_config['API_KEY'])
            
            # Authenticate
            data = obj.generateSession(
                account_config['CLIENT_ID'], 
                account_config['MPIN'], 
                totp
            )
            
            if data['status']:
                # Store connection and tokens
                self.connections[account_id] = obj
                self.tokens[account_id] = {
                    'jwt_token': data['data']['jwtToken'],
                    'refresh_token': data['data']['refreshToken'],
                    'login_time': datetime.now()
                }
                
                self.logger.info(f"Authenticated {account_id} successfully")
                return True, obj, None
            else:
                error_msg = data.get('message', 'Unknown error')
                self.logger.error(f"Authentication failed for {account_id}: {error_msg}")
                return False, None, error_msg
                
        except Exception as e:
            error_msg = f"Exception during authentication: {str(e)}"
            self.logger.error(f"Auth exception for {account_id}: {error_msg}")
            return False, None, error_msg
    
    def authenticate_all_accounts(self):
        """Authenticate both source and mirror accounts"""
        results = {}
        
        for account_id in ['source_account', 'mirror_account']:
            success, connection, error = self.authenticate_account(account_id)
            results[account_id] = {
                'success': success,
                'error': error,
                'connection': connection
            }
            
        return results
    
    def get_connection(self, account_id):
        """Get authenticated connection for an account"""
        return self.connections.get(account_id)
    
    def get_all_connections(self):
        """Get all authenticated connections"""
        return self.connections
    
    def is_authenticated(self, account_id):
        """Check if account is authenticated"""
        return account_id in self.connections
    
    def logout_account(self, account_id):
        """Logout from an account"""
        try:
            if account_id in self.connections:
                connection = self.connections[account_id]
                connection.terminateSession(self.config.get_account(account_id)['CLIENT_ID'])
                del self.connections[account_id]
                del self.tokens[account_id]
                self.logger.info(f"Logged out {account_id}")
                return True
        except Exception as e:
            self.logger.error(f"Logout failed for {account_id}: {e}")
        return False
    
    def logout_all(self):
        """Logout from all accounts"""
        for account_id in list(self.connections.keys()):
            self.logout_account(account_id)

# Test function for this module
def test_auth_manager():
    print("🧪 Testing Auth Manager...")
    
    # Import config manager
    from src.config.config_manager import ConfigManager
    
    # Setup basic logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        config = ConfigManager()
        auth = AuthManager(config)
        
        print("1. Testing authentication...")
        results = auth.authenticate_all_accounts()
        
        for account_id, result in results.items():
            if result['success']:
                print(f"{account_id}: Authentication SUCCESS")
            else:
                print(f" {account_id}: Authentication FAILED - {result['error']}")
        
        print("2. Testing connection retrieval...")
        source_conn = auth.get_connection('source_account')
        mirror_conn = auth.get_connection('mirror_account')
        
        if source_conn:
            print("Source connection retrieved")
        if mirror_conn:
            print("Mirror connection retrieved")
            
        print("3. Testing authentication status...")
        source_authed = auth.is_authenticated('source_account')
        mirror_authed = auth.is_authenticated('mirror_account')
        print(f"   Source authenticated: {source_authed}")
        print(f"   Mirror authenticated: {mirror_authed}")
        
        print("Auth Manager test completed!")
        
        # Cleanup
        auth.logout_all()
        
    except Exception as e:
        print(f"Auth Manager test failed: {e}")
        raise

if __name__ == "__main__":
    test_auth_manager()