import logging
import time
import threading
from datetime import datetime
from src.config.config_manager import ConfigManager
from src.auth.auth_manager import AuthManager
from src.detection.trade_detector import TradeDetector
from src.safety.safety_manager import SafetyManager
from src.mirror.mirror_engine import MirrorEngine  # ADD THIS IMPORT

class MirroringController:
    def __init__(self):
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            handlers=[
                logging.FileHandler(f'mirroring_{datetime.now().strftime("%Y%m%d")}.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('controller')
        
        # Initialize modules
        self.config = ConfigManager()
        self.auth = AuthManager(self.config)
        self.detector = TradeDetector(self.config, self.auth)
        self.safety = SafetyManager(self.config)
        self.mirror_engine = MirrorEngine(self.config, self.auth, self.safety)  # ADD THIS LINE
        
        self.running = False
        self.monitoring_thread = None
        
    def start_monitoring(self):
        """Start the monitoring loop"""
        if self.running:
            self.logger.warning("Monitoring already running")
            return False
        
        # Authenticate accounts
        self.logger.info("Authenticating accounts...")
        auth_results = self.auth.authenticate_all_accounts()
        
        for account_id, result in auth_results.items():
            if result['success']:
                self.logger.info(f"{account_id}: Authenticated")
            else:
                self.logger.error(f"{account_id}: Authentication failed - {result['error']}")
        
        # Start monitoring thread
        self.running = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        self.logger.info("Monitoring started (mirroring disabled by default)")
        return True
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        if not self.running:
            self.logger.warning("Monitoring not running")
            return False
        
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        # Stop mirroring engine and logout
        self.mirror_engine.stop()  # ADD THIS LINE
        self.auth.logout_all()
        self.logger.info("Monitoring stopped")
        return True
    
    def enable_mirroring(self):
        """Enable trade mirroring"""
        success = self.safety.enable_mirroring()
        if success:
            self.mirror_engine.start()  # ADD THIS LINE
        return success
    
    def disable_mirroring(self):
        """Disable trade mirroring"""
        self.mirror_engine.stop()  # ADD THIS LINE
        return self.safety.disable_mirroring()
    
    def emergency_stop(self):
        """Emergency stop all mirroring"""
        self.mirror_engine.stop()  # ADD THIS LINE
        return self.safety.emergency_stop_mirroring()
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting monitoring loop...")
        
        while self.running:
            try:
                # Check for new trades
                new_trades = self.detector.detect_new_trades()
                
                # Process new trades if mirroring is enabled
                if new_trades and self.safety.mirroring_enabled:
                    for trade in new_trades:
                        self._process_trade_for_mirroring(trade)
                
                # Wait before next check
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                time.sleep(10)  # Wait before retrying
    
    def _process_trade_for_mirroring(self, trade):
        """Process a trade for mirroring (safety checks + actual mirroring)"""
        can_mirror, reason = self.safety.can_mirror_trade(trade)
        
        if can_mirror:
            self.logger.info(f"READY TO MIRROR: {trade['symbol']} | "
                           f"Qty: {trade['quantity']} | Price: {trade['order_price']}")
            
            # ACTUAL MIRRORING LOGIC - ADD THIS BLOCK
            success = self.mirror_engine.mirror_trade(trade)
            if success:
                self.logger.info(f"✅ SUCCESSFULLY MIRRORED: {trade['symbol']}")
            else:
                self.logger.error(f"❌ FAILED TO MIRROR: {trade['symbol']}")
                
        else:
            self.logger.warning(f"SKIP MIRRORING: {trade['symbol']} | Reason: {reason}")
    
    def get_status(self):
        """Get current system status"""
        detector_stats = self.detector.get_detection_stats()
        safety_status = self.safety.get_safety_status()
        mirror_stats = self.mirror_engine.get_mirror_stats()  # ADD THIS LINE
        
        return {
            'system_running': self.running,
            'detection_stats': detector_stats,
            'safety_status': safety_status,
            'mirror_stats': mirror_stats,  # ADD THIS LINE
            'accounts_authenticated': list(self.auth.get_all_connections().keys())
        }
    
    def print_status(self):  # ADD THIS METHOD
        """Print formatted status"""
        status = self.get_status()
        print("\n" + "="*50)
        print("MIRRORING SYSTEM STATUS")
        print("="*50)
        print(f"System Running: {'✅' if status['system_running'] else '❌'}")
        print(f"Accounts Authenticated: {status['accounts_authenticated']}")
        print(f"Mirroring Enabled: {'✅' if status['safety_status']['mirroring_enabled'] else '❌'}")
        print(f"Emergency Stop: {'🔴 ACTIVE' if status['safety_status']['emergency_stop'] else '🟢 INACTIVE'}")
        print(f"Total Trades Detected: {status['detection_stats']['total_processed_trades']}")
        print(f"Total Trades Mirrored: {status['mirror_stats']['total_mirrored']}")
        print("="*50)

def main():
    """Main function with interactive controls"""
    controller = MirroringController()
    
    print("Angel One Mirroring System")
    print("="*40)
    print("Commands: start, stop, enable, disable, emergency, status, exit")
    print("="*40)
    
    while True:
        try:
            command = input("\n>>> ").strip().lower()
            
            if command == 'start':
                if controller.start_monitoring():
                    print("Monitoring STARTED - Checking for trades every 10 seconds")
                else:
                    print("Failed to start monitoring")
                    
            elif command == 'stop':
                if controller.stop_monitoring():
                    print("Monitoring STOPPED")
                else:
                    print("Failed to stop monitoring")
                    
            elif command == 'enable':
                if controller.enable_mirroring():
                    print("Mirroring ENABLED - Ready to mirror trades")
                else:
                    print("Cannot enable mirroring (check emergency stop)")
                    
            elif command == 'disable':
                controller.disable_mirroring()
                print("Mirroring DISABLED")
                
            elif command == 'emergency':
                controller.emergency_stop()
                print("EMERGENCY STOP ACTIVATED - All mirroring stopped")
                
            elif command == 'status':
                controller.print_status()  # UPDATED THIS LINE
                
            elif command in ['exit', 'quit']:
                controller.stop_monitoring()
                print("Exiting system...")
                break
                
            else:
                print("Unknown command. Available: start, stop, enable, disable, emergency, status, exit")
                
        except KeyboardInterrupt:
            print("Interrupted by user")
            controller.stop_monitoring()
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()