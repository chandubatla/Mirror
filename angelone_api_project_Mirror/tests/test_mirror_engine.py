import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import Mock

from src.mirror.mirror_engine import MirrorEngine


class DummyConfig:
    def get_settings(self):
        return {'price_tolerance': 0.02, 'max_retries': 2, 'retry_delay': 0}


class DummyAuth:
    def __init__(self, conn=None):
        self._conn = conn

    def get_connection(self, account_id):
        return self._conn


def test_get_symbol_token_finds_exact_match():
    # Mock connection.searchscrip to return the desired symbol
    target_symbol = 'NIFTY25NOV23400CE'
    mock_conn = Mock()
    mock_conn.searchscrip.return_value = {
        'status': True,
        'data': [
            {'symbol': 'OTHER', 'token': '111'},
            {'symbol': target_symbol, 'token': '999'}
        ]
    }

    engine = MirrorEngine(DummyConfig(), DummyAuth(mock_conn), None)
    token = engine.get_symbol_token(target_symbol)
    assert token == '999'
    mock_conn.searchscrip.assert_called()


def test_place_angel_one_order_calls_placeOrder_and_returns_success():
    mock_conn = Mock()
    mock_conn.placeOrder.return_value = {'status': True, 'data': {'orderid': 'ORD123'}}

    engine = MirrorEngine(DummyConfig(), DummyAuth(mock_conn), None)
    # monkeypatch get_symbol_token to avoid calling API
    engine.get_symbol_token = Mock(return_value='TOK123')

    trade = {
        'symbol': 'NIFTY25NOV23400CE',
        'quantity': 75,
        'order_type': 'BUY',
        'product_type': 'INTRADAY',
        'order_price': 50.0,
        'exchange': 'NFO'
    }

    resp = engine.place_angel_one_order(mock_conn, trade)
    assert resp.get('status') is True
    mock_conn.placeOrder.assert_called()


def test_mirror_trade_reserves_and_skips_duplicates():
    # Setup engine with mocked auth and place function
    mock_conn = Mock()
    mock_conn.placeOrder.return_value = {'status': True, 'data': {'orderid': 'X'}}

    auth = DummyAuth(mock_conn)
    engine = MirrorEngine(DummyConfig(), auth, None)
    engine.mirroring_enabled = True

    # stub methods
    engine.get_symbol_token = Mock(return_value='TOK')
    engine.get_current_market_price = Mock(return_value=45.0)
    engine.is_within_price_tolerance = Mock(return_value=True)
    engine.place_angel_one_order = Mock(return_value={'status': True, 'data': {'orderid': 'X'}})

    trade = {
        'trade_key': 'TK1',
        'symbol': 'NIFTY25NOV23400CE',
        'quantity': 75,
        'order_type': 'BUY',
        'product_type': 'INTRADAY',
        'order_price': 45.0,
        'exchange': 'NFO'
    }

    # First mirror attempt should succeed
    ok = engine.mirror_trade(trade)
    assert ok is True
    assert 'TK1' in engine.mirrored_trades

    # Second attempt should be skipped (already mirrored)
    engine.place_angel_one_order.reset_mock()
    ok2 = engine.mirror_trade(trade)
    assert ok2 is True
    engine.place_angel_one_order.assert_not_called()
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config.config_manager import ConfigManager
from src.auth.auth_manager import AuthManager
from src.safety.safety_manager import SafetyManager
from src.mirror.mirror_engine import MirrorEngine
import logging
from unittest.mock import MagicMock, patch

class MockSmartConnect:
    def __init__(self, **responses):
        self.responses = responses or {}
    
    def searchscrip(self, exchange, searchscrip):
        return self.responses.get('searchscrip', {
            'status': True,
            'data': [{
                'token': '5960',
                'symbol': 'NIFTY25NOV23400CE'
            }]
        })
    
    def ltpData(self, exchange, tradingsymbol, symboltoken):
        return self.responses.get('ltpData', {
            'status': True,
            'data': {'ltp': 45.50}
        })
    
    def placeOrder(self, order_params):
        return self.responses.get('placeOrder', {
            'status': True,
            'data': {'orderid': 'TEST123'}
        })

def test_mirror_engine():
    print("Starting Mirror Engine Test...")
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Initialize components
        config = ConfigManager()
        auth = AuthManager(config)
        safety = SafetyManager(config)
        engine = MirrorEngine(config, auth, safety)
        
        # Mock authentication for mirror account
        mock_connection = MockSmartConnect()
        auth.get_connection = MagicMock(return_value=mock_connection)
        
        print("1. Testing symbol token lookup...")
        token = engine.get_symbol_token('NIFTY25NOV23400CE')
        assert token == '5960', f"Expected token 5960, got {token}"
        print("Symbol token lookup works")
        
        # Test failed search
        mock_connection.responses['searchscrip'] = {'status': False, 'message': 'API Error'}
        token = engine.get_symbol_token('NIFTY25NOV23400CE')
        assert token is None, "Should handle failed search"
        print("Symbol token error handling works")
        
        print("2. Testing market price fetch...")
        mock_connection.responses['ltpData'] = {'status': True, 'data': {'ltp': 45.50}}
        price = engine.get_current_market_price('NIFTY25NOV23400CE', token='5960')
        assert price == 45.50, f"Expected price 45.50, got {price}"
        print("Market price fetch works")
        
        # Test failed LTP
        mock_connection.responses['ltpData'] = {'status': False, 'message': 'API Error'}
        price = engine.get_current_market_price('NIFTY25NOV23400CE', token='5960')
        assert price is None, "Should handle failed LTP"
        print("Market price error handling works")
        
        print("3. Testing order placement...")
        mock_connection.responses['placeOrder'] = {'status': True, 'data': {'orderid': 'TEST123'}}
        trade = {
            'symbol': 'NIFTY25NOV23400CE',
            'quantity': 75,
            'order_type': 'BUY',
            'product_type': 'INTRADAY',
            'order_price': 45.50,
            'exchange': 'NFO'
        }
        
        result = engine.place_angel_one_order(mock_connection, trade)
        assert result['status'] == True, "Order placement failed"
        assert result['data']['orderid'] == 'TEST123', "Invalid order ID"
        print("Order placement works")
        
        # Test failed order
        mock_connection.responses['placeOrder'] = {'status': False, 'message': 'Insufficient funds'}
        result = engine.place_angel_one_order(mock_connection, trade)
        assert result['status'] == False, "Should handle failed order"
        print("Order error handling works")
        
        print("4. Testing full mirror flow...")
        # Reset mock responses to success
        mock_connection.responses.update({
            'searchscrip': {'status': True, 'data': [{'token': '5960', 'symbol': 'NIFTY25NOV23400CE'}]},
            'ltpData': {'status': True, 'data': {'ltp': 45.50}},
            'placeOrder': {'status': True, 'data': {'orderid': 'TEST123'}}
        })
        
        # Enable mirroring
        engine.start()
        safety.enable_mirroring()
        
        trade['trade_key'] = '202511071226_NIFTY25NOV23400CE_75'
        success = engine.mirror_trade(trade)
        assert success == True, "Mirror trade failed"
        assert trade['trade_key'] in engine.mirrored_trades, "Trade not marked as mirrored"
        print("Full mirror flow works")
        
        # Test duplicate prevention
        success = engine.mirror_trade(trade)
        assert success == True, "Duplicate trade not handled"
        print("Duplicate prevention works")
        
        print("5. Testing mirror stats...")
        stats = engine.get_mirror_stats()
        assert stats['mirroring_enabled'] == True, "Mirror stats: enabled wrong"
        assert stats['total_mirrored'] > 0, "Mirror stats: total wrong"
        print("Mirror stats work")
        
        print("\nMIRROR ENGINE TEST COMPLETED!")
        
    except Exception as e:
        print(f"Mirror engine test failed: {e}")
        raise

if __name__ == "__main__":
    test_mirror_engine()