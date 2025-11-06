import logging

class PositionTracker:
    def __init__(self, config_manager, auth_manager):
        self.config = config_manager
        self.auth = auth_manager
        self.logger = logging.getLogger('position_tracker')
        self.previous_holdings = {}
        
    def get_current_holdings(self, account_id):
        """Get current holdings for an account"""
        try:
            connection = self.auth.get_connection(account_id)
            if connection:
                holdings_data = connection.holding()
                if holdings_data and holdings_data.get('status'):
                    return self.parse_holdings(holdings_data['data'])
            return {}
        except Exception as e:
            self.logger.error(f"Error getting holdings: {e}")
            return {}
    
    def parse_holdings(self, holdings_data):
        """Parse holdings data into standardized format"""
        positions = {}
        try:
            for holding in holdings_data:
                symbol = holding.get('tradingsymbol', '')
                quantity = int(holding.get('quantity', 0))
                
                # Only track positions with quantity > 0
                if quantity > 0 and self.is_nifty_option(symbol):
                    positions[symbol] = {
                        'symbol': symbol,
                        'quantity': quantity,
                        'product_type': holding.get('producttype', ''),
                        'exchange': holding.get('exchange', '')
                    }
                    
            return positions
        except Exception as e:
            self.logger.error(f"Error parsing holdings: {e}")
            return {}
    
    def is_nifty_option(self, symbol):
        """Check if symbol is a NIFTY option (your focus)"""
        return 'NIFTY' in symbol and ('CE' in symbol or 'PE' in symbol)
    
    def detect_exits(self, current_holdings):
        """Detect positions that were exited"""
        exits = []
        
        # Compare with previous holdings to find closed positions
        for symbol, previous_pos in self.previous_holdings.items():
            if symbol not in current_holdings:
                # Position was closed (exit detected)
                exits.append({
                    'symbol': symbol,
                    'quantity': previous_pos['quantity'],
                    'action': 'EXIT',
                    'product_type': previous_pos.get('product_type', ''),
                    'exchange': previous_pos.get('exchange', '')
                })
                self.logger.info(f"EXIT DETECTED: {symbol} Qty: {previous_pos['quantity']}")
        
        self.previous_holdings = current_holdings
        return exits
    
    def get_position_stats(self):
        """Get position tracking statistics"""
        return {
            'total_tracked_positions': len(self.previous_holdings),
            'tracked_symbols': list(self.previous_holdings.keys())
        }