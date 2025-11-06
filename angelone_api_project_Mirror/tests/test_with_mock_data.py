import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config.config_manager import ConfigManager
from src.auth.auth_manager import AuthManager
from src.detection.trade_detector import TradeDetector
import logging

def test_with_mock_trades():
    """Test trade detector with mock trade data"""
    print("🧪 Testing with Mock Trades...")
    
    logging.basicConfig(level=logging.INFO)
    
    try:
        config = ConfigManager()
        auth = AuthManager(config)
        
        # Create detector
        detector = TradeDetector(config, auth)
        
        print("1. Testing with mock NIFTY option trades...")
        
        # Create mock trades (simulating API response)
        mock_trades = [
            {
                'orderTimestamp': '2024-10-31 10:00:00',
                'tradingSymbol': 'NIFTY25OCT23400CE',
                'quantity': '75',
                'orderType': 'BUY',
                'productType': 'NRML',
                'averagePrice': '45.50',
                'tradePrice': '45.50',
                'tradeTime': '2024-10-31 10:00:05',
                'exchange': 'NFO',
                'status': 'complete'
            },
            {
                'orderTimestamp': '2024-10-31 10:01:00', 
                'tradingSymbol': 'NIFTY25OCT23400PE',
                'quantity': '75',
                'orderType': 'SELL',
                'productType': 'NRML',
                'averagePrice': '22.30',
                'tradePrice': '22.30',
                'tradeTime': '2024-10-31 10:01:03',
                'exchange': 'NFO',
                'status': 'complete'
            }
        ]
        
        # Manually add mock trades to detector
        for trade in mock_trades:
            parsed = detector.parse_trade(trade)
            if parsed and detector.is_nifty_option(parsed['symbol']):
                detector.processed_trades.add(parsed['trade_key'])
                print(f"    Added mock trade: {parsed['symbol']} | Qty: {parsed['quantity']}")
        
        print("2. Testing duplicate detection...")
        # Try to add the same trade again
        duplicate_trade = mock_trades[0].copy()
        parsed_dup = detector.parse_trade(duplicate_trade)
        is_new = detector.is_new_trade(parsed_dup['trade_key'])
        print(f"   Duplicate trade detected as new: {is_new} (should be False)")
        
        print("3. Testing stats...")
        stats = detector.get_detection_stats()
        print(f"   Stats: {stats}")
        
        print("Mock data test completed!")
        
    except Exception as e:
        print(f" Mock test failed: {e}")
        raise

if __name__ == "__main__":
    test_with_mock_trades()