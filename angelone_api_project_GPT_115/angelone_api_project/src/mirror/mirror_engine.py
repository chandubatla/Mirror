import logging
import time
from datetime import datetime

class MirrorEngine:
    def __init__(self, config_manager, auth_manager, safety_manager):
        self.config = config_manager
        self.auth = auth_manager
        self.safety = safety_manager
        self.logger = logging.getLogger('mirror_engine')
        self.mirroring_enabled = False
        self.mirrored_trades = set()
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
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
        """Check if current price is within 1% of source price"""
        if source_price <= 0:
            return False
            
        price_diff = abs(current_price - source_price)
        price_tolerance_percent = (price_diff / source_price) * 100
        
        return price_tolerance_percent <= 1.0  # Your 1% tolerance
    
    def get_current_market_price(self, symbol):
        """Get current LTP for the symbol"""
        try:
            # TODO: Implement actual LTP API call
            # For now, return source price as current price
            # In production, you'd call: connection.ltpData(exchange, symboltoken, symbol)
            return None  # Placeholder
        except Exception as e:
            self.logger.error(f"Error getting market price: {e}")
            return None
    
    def place_angel_one_order(self, connection, trade):
        """Place actual order using Angel One API"""
        try:
            # You need to implement this with actual Angel One order placement
            order_params = {
                'variety': 'NORMAL',
                'tradingsymbol': trade['symbol'],
                'symboltoken': self.get_symbol_token(trade['symbol']),
                'transactiontype': trade['order_type'],  # BUY/SELL
                'exchange': trade['exchange'],
                'ordertype': 'MARKET',  # or 'LIMIT' if you want exact price
                'producttype': trade['product_type'],
                'duration': 'DAY',
                'quantity': trade['quantity'],
                # 'price': trade['order_price']  # if LIMIT order
            }
            
            # UNCOMMENT THIS FOR REAL TRADING:
            # order_response = connection.placeOrder(order_params)
            # return order_response
            
            # TEMPORARY: Simulate success
            return {'status': True, 'data': {'orderid': 'SIMULATED'}}
            
        except Exception as e:
            self.logger.error(f"Order placement error: {e}")
            return {'status': False, 'message': str(e)}
    
    def get_symbol_token(self, symbol):
        """Get symbol token - you need to implement this"""
        # You'll need to map symbols to tokens
        # This can be done via Angel One's searchscrip API
        return "12345"  # Placeholder
        
    def mirror_trade(self, trade):
        """
        Mirror a single trade to target account with price validation
        Returns: True if successful
        """
        if not self.mirroring_enabled:
            self.logger.warning("Mirroring disabled - trade not executed")
            return False
            
        # Check if already mirrored
        if self.is_already_mirrored(trade['trade_key']):
            self.logger.info(f"Trade already mirrored: {trade['symbol']}")
            return True
            
        try:
            self.logger.info(f"ATTEMPTING TO MIRROR: {trade['symbol']} "
                           f"Qty: {trade['quantity']} @ {trade['order_price']}")
            
            # Get mirror account connection
            mirror_conn = self.auth.get_connection('mirror_account')
            if not mirror_conn:
                self.logger.error("No connection to mirror account")
                return False
            
            # Check price tolerance (if we can get current price)
            current_price = self.get_current_market_price(trade['symbol'])
            if current_price and not self.is_within_price_tolerance(trade['order_price'], current_price):
                self.logger.warning(f"Price out of tolerance: Source={trade['order_price']}, Current={current_price}")
                # You can choose to skip or proceed - for testing, proceed
                # return False
            
            # Place actual order with retry logic
            for attempt in range(self.max_retries):
                self.logger.info(f"Mirror attempt {attempt + 1}/{self.max_retries}")
                
                order_response = self.place_angel_one_order(mirror_conn, trade)
                
                if order_response.get('status'):
                    self.mirrored_trades.add(trade['trade_key'])
                    self.logger.info(f"SUCCESSFULLY MIRRORED: {trade['symbol']}")
                    return True
                else:
                    error_msg = order_response.get('message', 'Unknown error')
                    self.logger.warning(f"Mirror attempt {attempt + 1} failed: {error_msg}")
                    
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
            
            self.logger.error(f"FAILED TO MIRROR after {self.max_retries} attempts: {trade['symbol']}")
            return False
                
        except Exception as e:
            self.logger.error(f"Mirror execution error: {e}")
            return False
    
    def get_mirror_stats(self):
        """Get mirroring statistics"""
        return {
            'mirroring_enabled': self.mirroring_enabled,
            'total_mirrored': len(self.mirrored_trades),
            'last_mirror_attempt': getattr(self, 'last_attempt', None)
        }