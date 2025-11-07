import logging
import time
from datetime import datetime
import json
import os
import sqlite3

class TradeDetector:
    def __init__(self, config_manager, auth_manager):
        self.config = config_manager
        self.auth = auth_manager
        self.logger = logging.getLogger('trade_detector')
        # Persistent processed trades (SQLite)
        db_path = self.config.get_settings().get('processed_trades_db', 'processed_trades.db')
        db_dir = os.path.dirname(db_path) or '.'
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        self._db_path = db_path

        # Add error handling for DB connection
        try:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._ensure_table()
        except sqlite3.Error as e:
            self.logger.error(f"Database initialization failed: {e}")
            # Fallback to in-memory
            self.processed_trades = set()

        self.processed_trades = self._load_processed_trades()
        self.last_check_time = None
    
    def _ensure_table(self):
        cur = self._conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processed_trades (
                trade_key TEXT PRIMARY KEY,
                first_seen TIMESTAMP
            )
        """)
        self._conn.commit()

    def _load_processed_trades(self):
        cur = self._conn.cursor()
        cur.execute("SELECT trade_key FROM processed_trades")
        rows = cur.fetchall()
        return set(r[0] for r in rows)

    def _persist_trade_key(self, trade_key):
        try:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO processed_trades (trade_key, first_seen) VALUES (?, ?)",
                (trade_key, datetime.now().isoformat())
            )
            self._conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to persist trade_key {trade_key}: {e}")
            # don't raise - persistence failure shouldn't block detection
            return
    def get_source_connection(self):
        """Get authenticated connection for source account"""
        return self.auth.get_connection('source_account')
    
    def fetch_trade_book(self):
        """Fetch trade book from source account"""
        try:
            connection = self.get_source_connection()
            if not connection:
                self.logger.error("No connection to source account")
                return None
            
            trade_data = connection.tradeBook()
            
            # Handle case where trade_data might be None
            if trade_data is None:
                self.logger.error("Trade book API returned None")
                return None
                
            return trade_data
            
        except Exception as e:
            self.logger.error(f"Error fetching trade book: {e}")
            return None
    
    def parse_trade(self, trade):
        """Parse trade details into standardized format"""
        try:
            # Handle both old and new API response formats
            if 'orderTimestamp' in trade:
                # Old format
                return {
                    'trade_key': f"{trade['orderTimestamp']}_{trade['tradingSymbol']}_{trade['quantity']}",
                    'symbol': trade['tradingSymbol'],
                    'quantity': trade['quantity'],
                    'order_type': trade['orderType'],
                    'product_type': trade.get('productType', ''),
                    'order_price': float(trade['averagePrice']),
                    'trade_price': float(trade.get('tradePrice', trade['averagePrice'])),
                    'order_time': trade['orderTimestamp'],
                    'trade_time': trade.get('tradeTime', trade['orderTimestamp']),
                    'exchange': trade.get('exchange', ''),
                    'status': trade.get('status', '')
                }
            else:
                # New format (what you're getting)
                return {
                    'trade_key': f"{trade.get('filltime', '')}_{trade['tradingsymbol']}_{trade['fillsize']}",
                    'symbol': trade['tradingsymbol'],
                    'quantity': trade['fillsize'],
                    'order_type': trade['transactiontype'],  # BUY/SELL
                    'product_type': trade.get('producttype', ''),
                    'order_price': float(trade['fillprice']),
                    'trade_price': float(trade['fillprice']),
                    'order_time': trade.get('filltime', ''),
                    'trade_time': trade.get('filltime', ''),
                    'exchange': trade.get('exchange', ''),
                    'status': 'complete'
                }
        except Exception as e:
            self.logger.error(f"Error parsing trade: {e}, Trade: {trade}")
            return None
    
    def is_new_trade(self, trade_key):
        """Check if we've already processed this trade"""
        return trade_key not in self.processed_trades
    
    def is_nifty_option(self, symbol):
        """Improved NIFTY option validation"""
        if not symbol:
            return False
        try:
            # More robust NIFTY detection
            return ('NIFTY' in symbol.upper() and 
                   any(x in symbol.upper() for x in ['CE', 'PE', 'CALL', 'PUT']))
        except:
            return False
    
    def detect_new_trades(self):
        """
        Detect new trades from source account
        Returns: list of new trades
        """
        try:
            self.logger.info("Checking for new trades...")
            trade_data = self.fetch_trade_book()
            
            # Better error handling for None response
            if trade_data is None:
                self.logger.error("No trade data received from API")
                return []
                
            if not trade_data.get('status'):
                error_msg = trade_data.get('message', 'Unknown error')
                self.logger.error(f"Trade book API error: {error_msg}")
                return []
            
            trades = trade_data.get('data', [])
            
            # Handle case where trades might be None or empty
            if trades is None:
                self.logger.info("No trades in trade book (data is None)")
                return []
                
            if len(trades) == 0:
                self.logger.info("Trade book is empty (no trades yet)")
                return []
                
            new_trades = []
            
            for trade in trades:
                parsed_trade = self.parse_trade(trade)
                if not parsed_trade:
                    continue
                
                # Check if it's a NIFTY option and new trade
                if (self.is_nifty_option(parsed_trade['symbol']) and 
                    self.is_new_trade(parsed_trade['trade_key'])):
                    
                    # Mark as processed (in-memory + persistent)
                    self.processed_trades.add(parsed_trade['trade_key'])
                    self._persist_trade_key(parsed_trade['trade_key'])
                    new_trades.append(parsed_trade)
                    
                    self.logger.info(f"NEW TRADE DETECTED: {parsed_trade['symbol']} "
                                   f"Qty: {parsed_trade['quantity']} "
                                   f"Price: {parsed_trade['order_price']}")
            
            self.last_check_time = datetime.now()
            
            if new_trades:
                self.logger.info(f"Found {len(new_trades)} new trades")
            else:
                self.logger.info("No new trades found")
                
            return new_trades
            
        except Exception as e:
            self.logger.error(f"Error detecting trades: {e}")
            return []
    
    def get_detection_stats(self):
        """Get statistics about trade detection"""
        return {
            'total_processed_trades': len(self.processed_trades),
            'last_check_time': self.last_check_time,
            'source_account_connected': bool(self.get_source_connection())
        }
    
    def clear_processed_trades(self):
        """Clear processed trades history (for testing)"""
        try:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM processed_trades")
            self._conn.commit()
            self.processed_trades.clear()
            self.logger.info("Cleared processed trades history (persistent DB cleared)")
        except Exception as e:
            self.logger.error(f"Failed to clear processed trades DB: {e}")
            # fallback to in-memory clear
            self.processed_trades.clear()
            self.logger.info("Cleared processed trades history (in-memory)")

    def __del__(self):
        try:
            if hasattr(self, '_conn') and self._conn:
                self._conn.close()
        except Exception:
            pass

# Test function for this module
def test_trade_detector():
    print("🧪 Testing Trade Detector...")
    
    # Import dependencies
    from src.config.config_manager import ConfigManager
    from src.auth.auth_manager import AuthManager
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(levelname)s - %(name)s - %(message)s')
    
    try:
        # Setup
        config = ConfigManager()
        auth = AuthManager(config)
        
        # Authenticate source account
        auth.authenticate_account('source_account')
        
        # Create detector
        detector = TradeDetector(config, auth)
        
        print("1. Testing trade detection...")
        new_trades = detector.detect_new_trades()
        print(f"   Found {len(new_trades)} new trades")
        
        print("2. Testing detection stats...")
        stats = detector.get_detection_stats()
        print(f"   Stats: {stats}")
        
        print("3. Testing NIFTY option filter...")
        test_symbols = ['NIFTY25OCT23400CE', 'RELIANCE', 'BANKNIFTY25OCT2345000PE']
        for symbol in test_symbols:
            is_nifty = detector.is_nifty_option(symbol)
            print(f"   {symbol}: {'NIFTY Option' if is_nifty else 'Other'}")
        
        print("🎯 Trade Detector test completed!")
        
        # Cleanup
        auth.logout_all()
        
    except Exception as e:
        print(f"❌ Trade Detector test failed: {e}")
        raise

if __name__ == "__main__":
    test_trade_detector()