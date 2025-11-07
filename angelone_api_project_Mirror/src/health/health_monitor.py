from datetime import datetime
import logging

class HealthMonitor:
    def __init__(self):
        self.logger = logging.getLogger('health_monitor')
        self.start_time = datetime.now()
        self.last_successful_trade = None
        self.error_count = 0
        self.trade_count = 0
        
    def record_trade(self, success: bool, error_msg: str = None):
        if success:
            self.last_successful_trade = datetime.now()
            self.trade_count += 1
        else:
            self.error_count += 1
            self.logger.error(f"Trade failed: {error_msg}")
    
    def get_status(self):
        return {
            'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
            'last_successful_trade': self.last_successful_trade,
            'error_count': self.error_count,
            'trade_count': self.trade_count,
            'healthy': self.error_count < 10
        }