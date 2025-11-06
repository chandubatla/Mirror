import sys
import os
import logging

# Add src to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config.config_manager import ConfigManager
from src.auth.auth_manager import AuthManager
from src.detection.trade_detector import TradeDetector

def test_trade_detector():
    print("Starting Trade Detector Test...")
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(levelname)s - %(name)s - %(message)s')
    
    try:
        # Load config and auth
        config = ConfigManager()
        auth = AuthManager(config)
        
        print("1. Authenticating source account...")
        auth_result = auth.authenticate_account('source_account')
        if not auth_result[0]:
            print(" Source account authentication failed, but continuing test...")
        
        print("2. Creating trade detector...")
        detector = TradeDetector(config, auth)
        
        print("3. Testing trade detection...")
        new_trades = detector.detect_new_trades()
        print(f" Detected {len(new_trades)} new trades")
        
        # Show trade details if any found
        for trade in new_trades:
            print(f"      - {trade['symbol']} | Qty: {trade['quantity']} | Price: {trade['order_price']}")
        
        print("4. Testing detection stats...")
        stats = detector.get_detection_stats()
        print(f"Stats: {stats}")
        
        print("5. Testing NIFTY option detection...")
        # Test with some example symbols
        test_cases = [
            ('NIFTY25OCT23400CE', True),
            ('RELIANCE', False),
            ('BANKNIFTY25OCT2345000PE', True),
            ('NIFTY25OCT23400', False)  # No CE/PE
        ]
        
        for symbol, expected in test_cases:
            result = detector.is_nifty_option(symbol)
            status = "" if result == expected else ""
            print(f"   {status} {symbol}: {result} (expected: {expected})")
        
        print(" TRADE DETECTOR TEST COMPLETED!")
        
        # Cleanup
        auth.logout_all()
        
    except Exception as e:
        print(f"Trade detector test failed: {e}")
        raise

if __name__ == "__main__":
    test_trade_detector()