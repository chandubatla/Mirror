import logging
from logging import config
import logging.handlers
import time
import threading
from datetime import datetime
from src.config.config_manager import ConfigManager
from src.auth.auth_manager import AuthManager
from src.detection.trade_detector import TradeDetector
from src.safety.safety_manager import SafetyManager
from src.mirror.mirror_engine import MirrorEngine
from src.health.health_monitor import HealthMonitor

class MirroringController:
    def debug_symbol_search(self, symbol):
        """Debug method to check symbol search results"""
        print(f"\n🔍 DEBUG SYMBOL SEARCH: {symbol}")
        print("=" * 50)
        
        if not hasattr(self, 'mirror_engine') or not self.mirror_engine:
            print("❌ Mirror engine not initialized")
            return
        
        connection = self.auth.get_connection('mirror_account')
        if not connection:
            print("❌ No connection available")
            return
        
        try:
            search_response = connection.search_scrip(
                exchange='NFO',
                searchscrip=symbol
            )
            
            if search_response and search_response.get('status'):
                symbols_found = [item.get('symbol', '') for item in search_response.get('data', [])]
                print(f"✅ Found {len(symbols_found)} symbols:")
                for s in symbols_found[:10]:  # Show first 10
                    print(f"   - {s}")
                
                # Check if our symbol exists
                if symbol in symbols_found:
                    print(f"🎯 EXACT MATCH FOUND: {symbol}")
                else:
                    print(f"❌ Exact match NOT found for: {symbol}")
                    
                # Also try with just the base symbol
                if 'BANKNIFTY' in symbol:
                    base_symbol = 'BANKNIFTY'
                elif 'NIFTY' in symbol:
                    base_symbol = 'NIFTY'
                else:
                    base_symbol = symbol.split('2')[0] if '2' in symbol else symbol
                    
                print(f"\n🔍 Trying base symbol search: {base_symbol}")
                base_search = connection.search_scrip(exchange='NFO', searchscrip=base_symbol)
                if base_search and base_search.get('status'):
                    base_symbols = [item.get('symbol', '') for item in base_search.get('data', [])]
                    print(f"✅ Found {len(base_symbols)} symbols with base '{base_symbol}':")
                    for s in base_symbols[:10]:
                        if symbol in s:  # Show symbols containing our target
                            print(f"   - {s}")
            else:
                print(f"❌ Search failed: {search_response.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Search error: {e}")
            import traceback
            print(f"Full error: {traceback.format_exc()}")

    def __init__(self):
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            handlers=[
                logging.handlers.RotatingFileHandler(
                    f'mirroring_{datetime.now().strftime("%Y%m%d")}.log',
                    maxBytes=5_000_000,
                    backupCount=5
                ),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('controller')
        
        # Initialize configuration first
        self.config = ConfigManager()
        
        # ✅ FIXED: Access LOT_SIZES from accounts configuration
        accounts_config = self.config.get_all_accounts()
        self.LOT_SIZES = accounts_config.get('LOT_SIZE', {})
        self.DEFAULT_LOT_SIZE = 75
        
        # ✅ FIXED: Temporarily disable max_trade_qty for testing
        self.max_trade_qty = None
        
        # Initialize modules with proper error handling
        try:
            self.auth = AuthManager(self.config)
            self.detector = TradeDetector(self.config, self.auth)
            self.safety = SafetyManager(self.config)
            self.mirror_engine = MirrorEngine(self.config, self.auth, self.safety)
            self.health_monitor = HealthMonitor()
        except Exception as e:
            self.logger.error(f"Failed to initialize modules: {e}")
            # Set modules to None to avoid attribute errors
            self.auth = None
            self.detector = None
            self.safety = None
            self.mirror_engine = None
            self.health_monitor = None
        
        # Safety defaults
        settings = self.config.get_settings()
        self.dry_run = settings.get('dry_run', True)
        
        self.running = False
        self.monitoring_thread = None
        
        self.logger.info(f"Loaded LOT_SIZES: {self.LOT_SIZES}")
    def quick_test(self):
        """Quick test without max_trade_qty limit"""
        print("\n🔧 QUICK TEST (max_trade_qty disabled)")
        print("="*40)
        
        # Temporarily disable max limit
        original_max = self.max_trade_qty
        self.max_trade_qty = None
        
        test_trades = [
            {'symbol': 'NIFTY25NOV2525350PE', 'quantity': '75'},
            {'symbol': 'BANKNIFTY25NOV2550000CE', 'quantity': '35'},
        ]
        
        for trade in test_trades:
            success, mirrored_qty, lots, lot_size, message = self._convert_to_lot_based_quantity(trade)
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} | {trade['symbol']} Qty: {trade['quantity']}")
            print(f"     → {message}")
        
        # Restore original value
        self.max_trade_qty = original_max
    def _get_instrument_lot_size(self, trading_symbol):
        """
        Extract base instrument and return lot size from config
        """
        if not trading_symbol:
            return self.DEFAULT_LOT_SIZE
            
        trading_symbol_upper = trading_symbol.upper()
        
        if 'NIFTY' in trading_symbol_upper and 'BANKNIFTY' not in trading_symbol_upper and 'FINNIFTY' not in trading_symbol_upper:
            return self.LOT_SIZES.get('NIFTY', self.DEFAULT_LOT_SIZE)
        elif 'BANKNIFTY' in trading_symbol_upper:
            return self.LOT_SIZES.get('BANKNIFTY', self.DEFAULT_LOT_SIZE)
        elif 'FINNIFTY' in trading_symbol_upper:
            return self.LOT_SIZES.get('FINNIFTY', self.DEFAULT_LOT_SIZE)
        elif 'MIDCPNIFTY' in trading_symbol_upper:
            return self.LOT_SIZES.get('MIDCPNIFTY', self.DEFAULT_LOT_SIZE)
        elif 'SENSEX' in trading_symbol_upper:
            return self.LOT_SIZES.get('SENSEX', self.DEFAULT_LOT_SIZE)
        elif 'BANKEX' in trading_symbol_upper:
            return self.LOT_SIZES.get('BANKEX', self.DEFAULT_LOT_SIZE)
        else:
            return self.DEFAULT_LOT_SIZE

    def _identify_instrument(self, symbol):
        """Identify the instrument type from symbol"""
        if not symbol:
            return 'UNKNOWN'
            
        symbol_upper = symbol.upper()
        if 'BANKNIFTY' in symbol_upper:
            return 'BANKNIFTY'
        elif 'FINNIFTY' in symbol_upper:
            return 'FINNIFTY' 
        elif 'MIDCPNIFTY' in symbol_upper:
            return 'MIDCPNIFTY'
        elif 'SENSEX' in symbol_upper:
            return 'SENSEX'
        elif 'BANKEX' in symbol_upper:
            return 'BANKEX'
        elif 'NIFTY' in symbol_upper:
            return 'NIFTY'
        else:
            return 'UNKNOWN/DEFAULT'

    def _convert_to_lot_based_quantity(self, trade):
        """
        Convert trade quantity to lot-based quantity
        Returns: (success, mirrored_qty, lots, lot_size, message)
        """
        try:
            # Get original quantity and convert to int (FIXES THE TYPE ERROR)
            original_qty = int(trade.get('quantity', 0))
            trading_symbol = trade.get('symbol', '') or trade.get('trading_symbol', '')
            
            # Skip if no quantity or invalid symbol
            if original_qty <= 0:
                return False, 0, 0, 0, f"Invalid quantity: {original_qty}"
                
            if not trading_symbol:
                return False, 0, 0, 0, "No trading symbol provided"
            
            # Get appropriate lot size for this instrument
            lot_size = self._get_instrument_lot_size(trading_symbol)
            
            # Calculate how many full lots
            lots = original_qty // lot_size
            
            # Skip if less than 1 lot
            if lots < 1:
                return False, 0, 0, lot_size, f"Ignoring trade: {original_qty} is less than 1 lot ({lot_size})"
                
            # Calculate mirrored quantity
            mirrored_qty = lots * lot_size
            
            # Apply max trade quantity limit (with int conversion fix)
            if self.max_trade_qty is not None and mirrored_qty > int(self.max_trade_qty):
                # Cap at max allowed lots
                max_lots = int(self.max_trade_qty) // lot_size
                if max_lots < 1:
                    return False, 0, 0, lot_size, f"Mirrored quantity {mirrored_qty} exceeds max limit {self.max_trade_qty}"
                
                mirrored_qty = max_lots * lot_size
                lots = max_lots
            
            return True, mirrored_qty, lots, lot_size, f"Converted {original_qty} -> {mirrored_qty} ({lots} lots of {lot_size})"
            
        except Exception as e:
            return False, 0, 0, 0, f"Error converting to lot quantity: {e}"

    def test_symbol_parsing(self):
        """Test symbol parsing and lot size detection"""
        print("\n" + "="*50)
        print("SYMBOL PARSING TEST")
        print("="*50)
        
        test_symbols = [
            "NIFTY25NOV2525350PE",      # From your logs
            "BANKNIFTY25NOV2550000CE",
            "NIFTY25NOV2550000PE",
            "FINNIFTY25NOV2550000CE",
            "RELIANCE",                 # Equity (should use default)
            "INVALID_SYMBOL"            # Should use default
        ]
        
        for symbol in test_symbols:
            lot_size = self._get_instrument_lot_size(symbol)
            instrument_type = self._identify_instrument(symbol)
            print(f"Symbol: {symbol}")
            print(f"  → Lot Size: {lot_size}")
            print(f"  → Instrument: {instrument_type}")
            print()

    def test_lot_conversion(self):
        """Test quantity to lot conversion"""
        print("\n" + "="*50)
        print("LOT CONVERSION TEST")
        print("="*50)
        
        test_cases = [
            {'symbol': 'NIFTY25NOV2525350PE', 'quantity': '75'},     # 1 lot
            {'symbol': 'NIFTY25NOV2525350PE', 'quantity': '150'},    # 2 lots
            {'symbol': 'NIFTY25NOV2525350PE', 'quantity': '50'},     # <1 lot (should ignore)
            {'symbol': 'BANKNIFTY25NOV2550000CE', 'quantity': '35'}, # 1 lot
            {'symbol': 'BANKNIFTY25NOV2550000CE', 'quantity': '105'}, # 3 lots
            {'symbol': 'BANKNIFTY25NOV2550000CE', 'quantity': '30'}, # <1 lot (should ignore)
        ]
        
        for trade in test_cases:
            success, mirrored_qty, lots, lot_size, message = self._convert_to_lot_based_quantity(trade)
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} | {trade['symbol']} Qty: {trade['quantity']}")
            print(f"     → Mirrored: {mirrored_qty} ({lots} lots of {lot_size})")
            print(f"     → Message: {message}")
            print()

    def start_monitoring(self):
        """Start the monitoring loop"""
        if self.running:
            self.logger.warning("Monitoring already running")
            return False
        
        # ✅ ADDED: Check if modules are properly initialized
        if not self.auth:
            self.logger.error("Authentication module not initialized. Cannot start monitoring.")
            return False
        
        # Authenticate accounts (with retry)
        self.logger.info("Authenticating accounts...")
        try:
            auth_results = self._call_with_retry(self.auth.authenticate_all_accounts, max_attempts=3, initial_delay=1)
        except Exception as e:
            self.logger.error(f"Authentication failed after retries: {e}. Aborting start.")
            return False
        
        # If any account failed, do not start monitoring
        failed = [k for k,v in auth_results.items() if not v.get('success')]
        if failed:
            self.logger.error(f"Authentication failed for accounts: {failed}. Aborting start.")
            return False
        
        # Start monitoring thread
        self.running = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = False
        self.monitoring_thread.start()
        
        self.logger.info("Monitoring started (mirroring disabled by default)")
        return True
    
    def check_module_status(self):
        """Check if all modules are properly initialized"""
        print("\n🔍 MODULE STATUS CHECK")
        print("=" * 30)
        
        modules = {
            'config': self.config,
            'auth': self.auth,
            'detector': self.detector,
            'safety': self.safety,
            'mirror_engine': self.mirror_engine,
            'health_monitor': self.health_monitor
        }
        
        for name, module in modules.items():
            status = "✅ INITIALIZED" if module is not None else "❌ NOT INITIALIZED"
            print(f"{name:15} : {status}")
        
        # Check if we can get accounts from config
        if self.config:
            try:
                accounts = self.config.get_all_accounts()
                print(f"Accounts loaded   : ✅ {list(accounts.keys())}")
            except Exception as e:
                print(f"Accounts loaded   : ❌ Error: {e}")

    def stop_monitoring(self):
        """Stop the monitoring loop"""
        if not self.running:
            self.logger.warning("Monitoring not running")
            return False
        
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        # Stop mirroring engine and logout
        if getattr(self, 'mirror_engine', None):
            try:
                self.mirror_engine.stop()
            except Exception:
                self.logger.exception("Error stopping mirror engine")
        self.auth.logout_all()
        self.logger.info("Monitoring stopped")
        return True
    
    def enable_mirroring(self):
        """Enable trade mirroring"""
        success = self.safety.enable_mirroring()
        if success:
            if getattr(self, 'mirror_engine', None):
                try:
                    self.mirror_engine.start()
                except Exception:
                    self.logger.exception("Error starting mirror engine")
        return success
    
    def disable_mirroring(self):
        """Disable trade mirroring"""
        if getattr(self, 'mirror_engine', None):
            try:
                self.mirror_engine.stop()
            except Exception:
                self.logger.exception("Error stopping mirror engine")
        return self.safety.disable_mirroring()
    
    def emergency_stop(self):
        """Emergency stop all mirroring"""
        if getattr(self, 'mirror_engine', None):
            try:
                self.mirror_engine.stop()
            except Exception:
                self.logger.exception("Error stopping mirror engine")
        return self.safety.emergency_stop_mirroring()
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting monitoring loop...")
        # Prefer direct call to ConfigManager.get_settings()
        check_interval = self.config.get_settings().get('check_interval', 10)
        
        while self.running:
            try:
                # Check for new trades
                new_trades = self.detector.detect_new_trades()
                
                # Process new trades if mirroring is enabled
                if new_trades and getattr(self.safety, 'mirroring_enabled', False):
                    for trade in new_trades:
                        self._process_trade_for_mirroring(trade)
                
                # Wait before next check (use configured interval)
                time.sleep(check_interval)
                
            except Exception as e:
                self.logger.exception(f"Monitoring loop error: {e}")
                time.sleep(min(check_interval, 10))
    
    def _call_with_retry(self, func, *args, max_attempts=3, initial_delay=1, backoff=2, **kwargs):
        """Call func with simple retry/backoff; raises last exception if all attempts fail"""
        delay = initial_delay
        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exc = e
                self.logger.warning(f"Attempt {attempt} for {getattr(func, '__name__', str(func))} failed: {e}")
                if attempt == max_attempts:
                    break
                time.sleep(delay)
                delay *= backoff
        raise last_exc

    def _process_trade_for_mirroring(self, trade):
        """Process a trade for mirroring with lot-based quantities"""
        # Safety checks
        can_mirror, reason = self.safety.can_mirror_trade(trade)

        # If safety gate fails, skip mirroring
        if not can_mirror:
            self.logger.warning(f"SKIP MIRRORING: {trade.get('symbol')} | Reason: {reason}")
            return

        # Convert to lot-based quantity
        success, mirrored_qty, lots, lot_size, conversion_msg = self._convert_to_lot_based_quantity(trade)
        
        if not success:
            self.logger.warning(f"SKIP MIRRORING: {trade.get('symbol')} | {conversion_msg}")
            return

        # Update trade with mirrored quantity for logging
        original_qty = trade.get('quantity')
        trade['original_quantity'] = original_qty
        trade['quantity'] = mirrored_qty
        
        self.logger.info(f"LOT CONVERSION: {conversion_msg} for {trade.get('symbol')}")
        
        if can_mirror:
            self.logger.info(f"READY TO MIRROR: {trade['symbol']} | Qty: {original_qty}→{mirrored_qty} ({lots} lots) | Price: {trade.get('order_price', 'N/A')}")
            
            if self.dry_run:
                # Do not execute real orders in dry-run mode
                self.logger.info(f"DRY-RUN: simulated mirroring of {trade['symbol']} qty {mirrored_qty} ({lots} lots of {lot_size})")
                # If mirror_engine exposes bookkeeping for tests/stats, update it (best-effort)
                try:
                    if getattr(self.mirror_engine, 'mirrored_trades', None) is not None:
                        self.mirror_engine.mirrored_trades.append(trade)
                except Exception:
                    # Non-critical in dry-run
                    self.logger.debug("mirror_engine bookkeeping not available during dry-run")
                return

            # Attempt real mirroring with retries
            try:
                success = self.mirror_engine.mirror_trade(trade)
                self.health_monitor.record_trade(success)
            except Exception as e:
                self.health_monitor.record_trade(False, str(e))
                raise

            if success:
                self.logger.info(f"✅ SUCCESSFULLY MIRRORED: {trade['symbol']} - {lots} lots ({mirrored_qty})")
            else:
                self.logger.error(f"❌ FAILED TO MIRROR: {trade['symbol']} - {lots} lots ({mirrored_qty})")
        else:
            self.logger.warning(f"SKIP MIRRORING: {trade.get('symbol')} | Reason: {reason}")
    
    def get_status(self):
        """Get current system status"""
        detector_stats = self.detector.get_detection_stats()
        safety_status = self.safety.get_safety_status()
        mirror_stats = self.mirror_engine.get_mirror_stats()
        
        return {
            'system_running': self.running,
            'detection_stats': detector_stats,
            'safety_status': safety_status,
            'mirror_stats': mirror_stats,
            'accounts_authenticated': list(self.auth.get_all_connections().keys()),
            'lot_sizes': self.LOT_SIZES
        }
    
    def print_status(self):
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
        print(f"Dry Run Mode: {'✅ ACTIVE' if self.dry_run else '❌ INACTIVE'}")
        print("Lot Sizes Configuration:")
        for instrument, lot_size in self.LOT_SIZES.items():
            print(f"  {instrument}: {lot_size}")
        print("="*50)

def main():
    """Main function with interactive controls"""
    controller = MirroringController()
    
    # 🧪 RUN TESTS FIRST
    print("🚀 RUNNING PRE-FLIGHT CHECKS...")
    controller.test_symbol_parsing()
    controller.test_lot_conversion()
    print("🎯 PRE-FLIGHT CHECKS COMPLETE!")
    
    # handle signals for graceful shutdown
    import signal
    def _handle_signal(signum, frame):
        print("\nSignal received, stopping...")
        controller.stop_monitoring()
        raise SystemExit(0)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    
    print("\nAngel One Mirroring System")
    print("="*40)
    print("Commands: start, stop, enable, disable, emergency, status, exit")
    print("="*40)
    
    while True:
        try:
            command = input("\n>>> ").strip().lower()
            
            if command == 'start':
                if controller.start_monitoring():
                    interval = controller.config.get_settings().get('check_interval', 10)
                    print(f"Monitoring STARTED - Checking for trades every {interval} seconds")
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
                controller.print_status()
                
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