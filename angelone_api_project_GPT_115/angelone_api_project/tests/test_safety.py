import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config.config_manager import ConfigManager
from src.safety.safety_manager import SafetyManager
import logging

def test_safety():
    print("Starting Safety Manager Test...")
    
    logging.basicConfig(level=logging.INFO)
    
    try:
        config = ConfigManager()
        safety = SafetyManager(config)
        
        print("1. Testing mirroring controls...")
        # Test enable/disable
        safety.enable_mirroring()
        status = safety.get_safety_status()
        assert status['mirroring_enabled'] == True, "Enable mirroring failed"
        print("Mirroring enable works")
        
        safety.disable_mirroring()
        status = safety.get_safety_status()
        assert status['mirroring_enabled'] == False, "Disable mirroring failed"
        print("Mirroring disable works")
        
        print("2. Testing emergency stop...")
        safety.emergency_stop_mirroring()
        status = safety.get_safety_status()
        assert status['emergency_stop'] == True, "Emergency stop failed"
        print(" Emergency stop works")
        
        # Test that enable fails during emergency stop
        result = safety.enable_mirroring()
        assert result == False, "Should not enable during emergency stop"
        print("Enable blocked during emergency stop")
        
        safety.reset_emergency_stop()
        status = safety.get_safety_status()
        assert status['emergency_stop'] == False, "Emergency stop reset failed"
        print("Emergency stop reset works")
        
        print("3. Testing trade validation...")
        # Valid trade
        valid_trade = {
            'symbol': 'NIFTY25OCT23400CE',
            'order_price': 45.50,
            'quantity': 75
        }
        
        can_mirror, reason = safety.can_mirror_trade(valid_trade)
        print(f"   Valid trade: {can_mirror} ({reason})")
        
        # Invalid trade (wrong symbol)
        invalid_trade = {
            'symbol': 'RELIANCE',
            'order_price': 2500,
            'quantity': 10
        }
        
        can_mirror, reason = safety.can_mirror_trade(invalid_trade)
        print(f"   Invalid trade: {can_mirror} ({reason})")
        
        print("4. Testing safety status...")
        status = safety.get_safety_status()
        print(f"  Safety status: {status}")
        
        print("\n SAFETY MANAGER TEST COMPLETED!")
        
    except Exception as e:
        print(f"Safety test failed: {e}")
        raise

if __name__ == "__main__":
    test_safety()