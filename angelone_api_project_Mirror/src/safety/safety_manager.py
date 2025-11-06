import logging
from datetime import datetime, timedelta

class SafetyManager:
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = logging.getLogger('safety_manager')
        self.mirroring_enabled = False
        self.emergency_stop = False
        self.last_safety_check = None
        
    def enable_mirroring(self):
        """Enable mirroring (manual control)"""
        if self.emergency_stop:
            self.logger.error("Cannot enable mirroring - Emergency stop is active")
            return False
            
        self.mirroring_enabled = True
        self.logger.info("Mirroring ENABLED")
        return True
    
    def disable_mirroring(self):
        """Disable mirroring (manual control)"""
        self.mirroring_enabled = False
        self.logger.info("Mirroring DISABLED")
        return True
    
    def emergency_stop_mirroring(self):
        """Immediately stop all mirroring (safety)"""
        self.mirroring_enabled = False
        self.emergency_stop = True
        self.logger.error("EMERGENCY STOP ACTIVATED - All mirroring stopped")
        return True
    
    def reset_emergency_stop(self):
        """Reset emergency stop (manual intervention required)"""
        self.emergency_stop = False
        self.logger.warning("Emergency stop RESET - Mirroring can be enabled")
        return True
    
    def can_mirror_trade(self, trade):
        """
        Check if a trade can be mirrored
        Returns: (can_mirror, reason)
        """
        # Check 1: Mirroring enabled
        if not self.mirroring_enabled:
            return False, "Mirroring is disabled"
        
        # Check 2: Emergency stop
        if self.emergency_stop:
            return False, "Emergency stop is active"
        
        # Check 3: Market hours (basic check)
        if not self.is_market_hours():
            return False, "Outside market hours"
        
        # Check 4: Valid trade type (NIFTY options only)
        if not self.is_valid_trade_type(trade):
            return False, "Not a NIFTY option trade"
        
        # Check 5: Price validation
        if not self.is_valid_price(trade):
            return False, "Invalid price"
        
        self.last_safety_check = datetime.now()
        return True, "OK"
    
    def is_market_hours(self):
        """Check if current time is within market hours"""
        now = datetime.now()
        current_time = now.time()
        
        # Market hours: 9:15 AM to 3:30 PM
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0).time()
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0).time()
        
        is_market_hours = market_open <= current_time <= market_close
        if not is_market_hours:
            self.logger.warning(f"Outside market hours: {current_time}")
        
        return is_market_hours
    
    def is_valid_trade_type(self, trade):
        """Validate trade type (NIFTY options only)"""
        symbol = trade.get('symbol', '')
        is_valid = 'NIFTY' in symbol and ('CE' in symbol or 'PE' in symbol)
        
        if not is_valid:
            self.logger.warning(f"Invalid trade type: {symbol}")
        
        return is_valid
    
    def is_valid_price(self, trade):
        """Validate trade price (basic checks)"""
        price = trade.get('order_price', 0)
        
        # Check if price is reasonable
        if price <= 0:
            self.logger.error(f"Invalid price: {price}")
            return False
        
        if price > 10000:  # Unlikely option price
            self.logger.warning(f"Suspicious price: {price}")
            return False
        
        return True
    
    def get_safety_status(self):
        """Get current safety status"""
        return {
            'mirroring_enabled': self.mirroring_enabled,
            'emergency_stop': self.emergency_stop,
            'market_hours': self.is_market_hours(),
            'last_safety_check': self.last_safety_check,
            'can_mirror': self.mirroring_enabled and not self.emergency_stop and self.is_market_hours()
        }

# Test function
def test_safety_manager():
    print("Testing Safety Manager...")
    
    from src.config.config_manager import ConfigManager
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    try:
        config = ConfigManager()
        safety = SafetyManager(config)
        
        print("1. Testing mirroring controls...")
        safety.enable_mirroring()
        status = safety.get_safety_status()
        print(f"   Mirroring enabled: {status['mirroring_enabled']}")
        
        safety.disable_mirroring()
        status = safety.get_safety_status()
        print(f"   Mirroring enabled: {status['mirroring_enabled']}")
        
        print("2. Testing emergency stop...")
        safety.emergency_stop_mirroring()
        status = safety.get_safety_status()
        print(f"   Emergency stop: {status['emergency_stop']}")
        
        print("3. Testing trade validation...")
        test_trade = {
            'symbol': 'NIFTY25OCT23400CE',
            'order_price': 45.50,
            'quantity': 75
        }
        
        can_mirror, reason = safety.can_mirror_trade(test_trade)
        print(f"   Can mirror trade: {can_mirror} (Reason: {reason})")
        
        print("4. Testing safety status...")
        status = safety.get_safety_status()
        print(f"   Safety status: {status}")
        
        print("Safety Manager test completed!")
        
    except Exception as e:
        print(f"Safety Manager test failed: {e}")
        raise

if __name__ == "__main__":
    test_safety_manager()