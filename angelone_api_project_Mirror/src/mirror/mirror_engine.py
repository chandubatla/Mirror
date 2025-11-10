import logging
import time
import threading
import sqlite3
import os
from datetime import datetime
from datetime import datetime

class MirrorEngine:
    def __init__(self, config_manager, auth_manager, safety_manager):
        self.config = config_manager
        self.auth = auth_manager
        self.safety = safety_manager
        self.logger = logging.getLogger('mirror_engine')
        self.mirroring_enabled = False
        self.mirrored_trades = set()
        # simple in-memory lock to prevent double execution races
        self._lock = threading.Lock()
        
        # Add configuration for tolerances
        settings = config_manager.get_settings()
        self.price_tolerance = settings.get('price_tolerance', 0.01)  # 1% default
        self.max_retries = settings.get('max_retries', 3)
        self.retry_delay = settings.get('retry_delay', 2)
        # DB for persistence (use processed_trades DB by default)
        db_path = settings.get('processed_trades_db', 'data/processed_trades.db')
        db_dir = os.path.dirname(db_path) or '.'
        try:
            os.makedirs(db_dir, exist_ok=True)
        except Exception:
            pass
        self._db_path = db_path
        self._db_conn = None
        try:
            self._db_conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._ensure_table()
            # load existing mirrored trades into memory
            self.mirrored_trades.update(self._load_persisted_mirrors())
        except Exception as e:
            self.logger.warning(f"Could not open DB for mirrored trades persistence: {e}")

        # simple in-memory lock to prevent double execution races
        self._lock = threading.Lock()
        
    def start(self):
        """Start mirroring engine"""
        self.mirroring_enabled = True
        self.logger.info("MIRRORING ENGINE STARTED")
        
    def stop(self):
        """Stop mirroring engine"""
        self.mirroring_enabled = False
        self.logger.info("MIRRORING ENGINE STOPPED")
        
    def is_already_mirrored(self, trade_key):
        """Check if trade was already mirrored"""
        return trade_key in self.mirrored_trades
        
    def is_within_price_tolerance(self, source_price, current_price):
        """Improved price tolerance check"""
        if not source_price or source_price <= 0:
            return False
        try:
            diff_percent = abs(current_price - source_price) / source_price
            return diff_percent <= self.price_tolerance
        except:
            self.logger.error("Price tolerance check failed")
            return False

    def get_current_market_price(self, symbol, token=None):
        """
        Get current LTP for the symbol using Angel One API
        Args:
            symbol: Trading symbol (e.g. 'NIFTY25NOV23400CE')
            token: Optional symbol token (if already known)
        Returns:
            float: Current market price or None on failure
        """
        try:
            # Get mirror account connection (we need fresh prices)
            connection = self.auth.get_connection('mirror_account')
            if not connection:
                self.logger.error("No connection for LTP check")
                return None

            # Get token if not provided
            if not token:
                token = self.get_symbol_token(symbol)
                if not token:
                    self.logger.error(f"Could not get token for {symbol}")
                    return None

            # Call LTP API with retry
            for attempt in range(self.max_retries):
                try:
                    ltp_response = connection.ltpData(
                        exchange='NFO',  # Options are on NFO
                        tradingsymbol=symbol,
                        symboltoken=token
                    )
                    if ltp_response and ltp_response.get('status'):
                        return float(ltp_response['data']['ltp'])
                    else:
                        error = ltp_response.get('message', 'Unknown error')
                        self.logger.warning(f"LTP attempt {attempt + 1} failed: {error}")
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay)
                except Exception as e:
                    self.logger.warning(f"LTP API error (attempt {attempt + 1}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)

            self.logger.error(f"All LTP attempts failed for {symbol}")
            return None

        except Exception as e:
            self.logger.error(f"Error getting market price: {e}")
            return None
    
    def place_angel_one_order(self, connection, trade):
        """
        Place actual order using Angel One API
        Args:
            connection: Authenticated SmartConnect instance
            trade: Normalized trade dict with symbol, quantity, etc.
        Returns:
            dict: Angel One order response with status and orderid
        """
        try:
            # Get token once and reuse (if available)
            symbol_token = self.get_symbol_token(trade['symbol'])
            if not symbol_token:
                # proceed without token (some clients accept tradingsymbol only)
                self.logger.warning(f"Could not get token for {trade['symbol']}, proceeding without symboltoken")
            # Build order parameters
            order_params = {
                'variety': 'NORMAL',
                'tradingsymbol': trade['symbol'],
                # include symboltoken only when available
                **({'symboltoken': symbol_token} if symbol_token else {}),
                'transactiontype': trade['order_type'],  # BUY/SELL
                'exchange': trade.get('exchange', 'NFO'),  # Default NFO for options
                'ordertype': 'MARKET',  # Always MARKET for mirroring
                'producttype': trade.get('product_type', 'INTRADAY'),  # Default INTRADAY
                'duration': 'DAY',
                'quantity': str(trade['quantity']),  # API expects string
            }
            
            # Optional price validation
            current_price = self.get_current_market_price(trade['symbol'], token=symbol_token)
            if current_price and not self.is_within_price_tolerance(trade['order_price'], current_price):
                self.logger.warning(
                    f"Price deviation: Source={trade['order_price']:.2f}, "
                    f"Current={current_price:.2f}, Tolerance={self.price_tolerance:.1%}"
                )
                # Continue with order - logging is sufficient since using MARKET orders
            
            # Place order with connection
            self.logger.info(
                f"Placing order: {order_params['transactiontype']} {trade['symbol']} x"
                f"{order_params['quantity']} ({order_params['producttype']})"
            )
            order_response = connection.placeOrder(order_params)
            
            if order_response.get('status'):
                self.logger.info(
                    f"Order placed successfully: ID {order_response['data']['orderid']}"
                )
            return order_response
            
        except Exception as e:
            self.logger.error(f"Order placement error: {e}")
            return {'status': False, 'message': str(e)}
    
    def get_symbol_token(self, symbol):
        """
        Get symbol token using Angel One search_scrip API
        Works for both NIFTY and BANKNIFTY options
        """
        try:
            connection = self.auth.get_connection('mirror_account')
            if not connection:
                self.logger.error("No connection for symbol lookup")
                return None

            # ✅ IMPROVED: Extract base symbol for search
            if 'BANKNIFTY' in symbol:
                search_term = 'BANKNIFTY'
            elif 'NIFTY' in symbol:
                search_term = 'NIFTY'
            elif 'FINNIFTY' in symbol:
                search_term = 'FINNIFTY'
            else:
                search_term = symbol  # Fallback to full symbol
            
            self.logger.info(f"Searching for symbol: {symbol} using term: {search_term}")
            
            # Search with retry
            for attempt in range(self.max_retries):
                try:
                    # ✅ FIXED: search_scrip (with underscore)
                    search_response = connection.search_scrip(
                        exchange='NFO',
                        searchscrip=search_term
                    )
                    
                    if search_response and search_response.get('status'):
                        # Find exact symbol match in the results
                        for item in search_response.get('data', []):
                            if item.get('symbol') == symbol:
                                token = item['token']
                                self.logger.info(f"Found token {token} for {symbol}")
                                return token
                        
                        # If exact match not found, log available symbols for debugging
                        available_symbols = [item.get('symbol', '') for item in search_response.get('data', [])]
                        self.logger.warning(f"Symbol {symbol} not found in search results. Available: {available_symbols[:5]}...")  # Show first 5
                        return None
                    else:
                        error = search_response.get('message', 'Unknown error')
                        self.logger.warning(f"Search attempt {attempt + 1} failed: {error}")
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay)
                            
                except Exception as e:
                    self.logger.warning(f"Search API error (attempt {attempt + 1}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
            
            self.logger.error(f"All search attempts failed for {symbol}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting symbol token: {e}")
            return None
    
    def mirror_trade(self, trade):
        """
        Mirror a single trade to target account with price validation
        Returns: True if successful
        """
        if not self.mirroring_enabled:
            self.logger.warning("Mirroring disabled - trade not executed")
            return False
            
        trade_key = trade.get('trade_key')
        if not trade_key:
            self.logger.error("Trade missing trade_key")
            return False

        # Prevent double-execution using in-memory reservation with a lock
        with self._lock:
            if self.is_already_mirrored(trade_key):
                self.logger.info(f"Trade {trade_key} already mirrored - skipping")
                return True
            # reserve immediately to avoid race re-entry
            self.mirrored_trades.add(trade_key)

        try:
            self.logger.info(f"ATTEMPTING TO MIRROR: {trade['symbol']} "
                           f"Qty: {trade['quantity']} @ {trade['order_price']}")

            # Get mirror account connection
            mirror_conn = self.auth.get_connection('mirror_account')
            if not mirror_conn:
                self.logger.error("No connection to mirror account")
                # rollback reservation
                with self._lock:
                    self.mirrored_trades.discard(trade_key)
                return False

            # Check price tolerance (if we can get current price)
            current_price = self.get_current_market_price(trade['symbol'])
            if current_price and not self.is_within_price_tolerance(trade['order_price'], current_price):
                self.logger.warning(f"Price out of tolerance: Source={trade['order_price']}, Current={current_price}")
                # proceed but log warning

            # Place actual order with retry logic
            for attempt in range(self.max_retries):
                self.logger.info(f"Mirror attempt {attempt + 1}/{self.max_retries}")

                order_response = self.place_angel_one_order(mirror_conn, trade)

                if order_response.get('status'):
                    self.logger.info(f"SUCCESSFULLY MIRRORED: {trade['symbol']}")
                    return True
                else:
                    error_msg = order_response.get('message', 'Unknown error')
                    self.logger.warning(f"Mirror attempt {attempt + 1} failed: {error_msg}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)

            self.logger.error(f"FAILED TO MIRROR after {self.max_retries} attempts: {trade['symbol']}")
            # leave trade_key reserved to avoid reattempts by default
            return False

        except Exception as e:
            self.logger.error(f"Mirror execution error: {e}")
            # ensure reservation is cleared so future attempts can retry
            with self._lock:
                self.mirrored_trades.discard(trade_key)
            return False

    # Persistence helpers
    def _ensure_table(self):
        if not self._db_conn:
            return
        cur = self._db_conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mirrored_trades (
                trade_key TEXT PRIMARY KEY,
                mirrored_at TIMESTAMP,
                order_id TEXT
            )
        """)
        self._db_conn.commit()

    def _persist_mirrored_trade(self, trade_key, order_id=None):
        if not self._db_conn:
            return
        cur = self._db_conn.cursor()
        cur.execute("INSERT OR IGNORE INTO mirrored_trades (trade_key, mirrored_at, order_id) VALUES (?, ?, ?)",
                    (trade_key, datetime.now().isoformat(), order_id))
        self._db_conn.commit()

    def _load_persisted_mirrors(self):
        if not self._db_conn:
            return set()
        cur = self._db_conn.cursor()
        try:
            cur.execute('SELECT trade_key FROM mirrored_trades')
            rows = cur.fetchall()
            return set(r[0] for r in rows)
        except Exception:
            return set()
    
    def get_mirror_stats(self):
        """Get mirroring statistics"""
        return {
            'mirroring_enabled': self.mirroring_enabled,
            'total_mirrored': len(self.mirrored_trades),
            'last_mirror_attempt': getattr(self, 'last_attempt', None)
        }