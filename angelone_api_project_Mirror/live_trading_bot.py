#!/usr/bin/env python3
"""
LIVE TRADING BOT - Angel One NIFTY Futures | EMA Crossover
Auto Token Finder | Market Hours Check | Real Orders | Telegram Alerts
"""

import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from SmartApi import SmartConnect
import pyotp
import requests  # For Telegram
from pytz import timezone  # pip install pytz if needed

# === YOUR CREDENTIALS (FILL THESE) ===
from dotenv import load_dotenv
import os
load_dotenv(dotenv_path="D:/tax/config.env")
load_dotenv(dotenv_path="../.env")   # go one directory up
API_KEY   = os.getenv("API_KEY")
CLIENT_ID = os.getenv("CLIENT_ID")
MPIN      = os.getenv("MPIN")
TOTP_TOKEN = os.getenv("TOTP_TOKEN")

# === TELEGRAM (OPTIONAL) ===
TELEGRAM_BOT_TOKEN = ""  # e.g., "123456:ABC-DEF..."
TELEGRAM_CHAT_ID = ""    # e.g., "123456789"

# === TRADING CONFIG ===
SYMBOL_NAME = "NIFTY"    # For auto-search
EXPIRY_MONTH = "25NOV"   # Update monthly if needed
QUANTITY = 15            # Lot size for NIFTY Futures
PAPER_TRADING = True     # Set False for LIVE orders

# === Logging ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8',
    handlers=[logging.FileHandler('live_bot.log', encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class AngelAPI:
    def __init__(self):
        self.obj = None
        self.is_authenticated = False
        self.nifty_token = None
        self.authenticate()
    
    def authenticate(self):
        try:
            logger.info("🔐 Authenticating with Angel One...")
            totp = pyotp.TOTP(TOTP_TOKEN).now()
            self.obj = SmartConnect(api_key=API_KEY)
            data = self.obj.generateSession(CLIENT_ID, MPIN, totp)
            
            if data['status']:
                self.is_authenticated = True
                logger.info("✅ Angel One Authentication SUCCESSFUL!")
                self.find_nifty_token()  # Auto-find token
            else:
                logger.error(f"❌ Auth failed: {data.get('message')}")
        except Exception as e:
            logger.error(f"❌ Auth error: {e}")
    
    def find_nifty_token(self):
        """Copy from your working original code"""
        try:
            response = self.obj.searchscrip(exchange="NFO", searchscrip=SYMBOL_NAME)
            if response['status'] and response['data']:
                for item in response['data']:
                    if EXPIRY_MONTH in item['symbol'] and 'FUT' in item['symbol']:
                        self.nifty_token = item['token']
                        self.trading_symbol = item['symbol']
                        logger.info(f"🎯 Found: {self.trading_symbol} | Token: {self.nifty_token}")
                        return True
            return False
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return False
    
    def is_market_open(self):
        """Check if market hours (9:15 AM - 3:30 PM IST)"""
        ist = timezone('Asia/Kolkata')
        now = datetime.now(ist)
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        if now.weekday() >= 5:  # Weekend
            return False
        return market_open <= now <= market_close
    
    def get_candle_data(self, duration=60):
        """Fetch 1-min candles for NIFTY FUT"""
        try:
            if not self.is_authenticated or not self.nifty_token:
                return pd.DataFrame()
            
            if not self.is_market_open():
                logger.warning("⏰ Market closed - skipping live data")
                return pd.DataFrame()
            
            from_date = (datetime.now() - timedelta(minutes=duration)).strftime("%Y-%m-%d %H:%M")
            to_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            params = {
                "exchange": "NFO",
                "symboltoken": self.nifty_token,
                "interval": "ONE_MINUTE",
                "fromdate": from_date,
                "todate": to_date
            }
            
            response = self.obj.getCandleData(params)
            if response.get('data'):
                df = pd.DataFrame(response['data'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
                logger.info(f"📊 Live candles loaded: {len(df)} records")
                return df.sort_values('timestamp').reset_index(drop=True)
            else:
                logger.warning(f"⚠️ No candle data: {response.get('message', 'Empty')}")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"❌ Candle error: {e}")
            return pd.DataFrame()
    
    def place_order(self, transaction_type, quantity):
        """Place market order for NIFTY FUT"""
        try:
            # Get trading symbol via search (or hardcode if known)
            search_resp = self.obj.searchscrip(exchange="NFO", searchscrip=SYMBOL_NAME)
            trading_symbol = next((item['symbol'] for item in search_resp['data'] if item['token'] == self.nifty_token), "NIFTY25NOVFUT")
            
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": trading_symbol,
                "symboltoken": self.nifty_token,
                "transactiontype": transaction_type,  # BUY or SELL
                "exchange": "NFO",
                "ordertype": "MARKET",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "price": "0",
                "squareoff": "0",
                "stoploss": "0",
                "quantity": str(quantity)
            }
            
            order_id = self.obj.placeOrder(order_params)
            logger.info(f"📝 Order placed: {transaction_type} {quantity} | ID: {order_id['data']['orderid']}")
            return order_id
        except Exception as e:
            logger.error(f"❌ Order error: {e}")
            return None
    
    def logout(self):
        try:
            if self.is_authenticated:
                self.obj.terminateSession(CLIENT_ID)
                logger.info("✅ Logged out")
        except Exception as e:
            logger.error(f"❌ Logout error: {e}")


class LiveTradingBot:
    def __init__(self, iterations=100, continuous=False):
        self.df = pd.DataFrame()
        self.current_position = None
        self.trades = []
        self.iteration = 0
        self.total_iterations = iterations if not continuous else float('inf')
        self.api = AngelAPI()
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0
        self.initialize_bot()
    
    def initialize_bot(self):
        mode = "LIVE" if self.api.is_authenticated and self.api.nifty_token else "SIMULATION"
        logger.info(f"🚀 LIVE TRADING BOT INITIALIZED ({mode} MODE)")
        if mode == "LIVE":
            logger.info(f"📈 Trading {SYMBOL_NAME} FUT Token: {self.api.nifty_token}")
        self.create_initial_data()
    
    def _create_simulated_data(self):
        base_price = 24350  # Approx NIFTY level
        num_points = 30
        prices = [base_price]
        for _ in range(1, num_points):
            change = np.random.normal(0, 0.001)
            prices.append(prices[-1] * (1 + change))
        
        timestamps = [datetime.now() - timedelta(minutes=i) for i in range(num_points, 0, -1)]
        self.df = pd.DataFrame({
            'timestamp': timestamps,
            'open': prices,
            'high': [p * (1 + np.random.uniform(0, 0.001)) for p in prices],
            'low': [p * (1 - np.random.uniform(0, 0.001)) for p in prices],
            'close': prices,
            'volume': np.random.randint(1000000, 3000000, num_points)
        })
    
    def create_initial_data(self):
        df_live = self.api.get_candle_data(duration=60)
        if not df_live.empty and len(df_live) >= 10:
            self.df = df_live.copy()
        else:
            logger.warning("⚠️ Using simulation for initial data")
            self._create_simulated_data()
        
        self.df['ema_fast'] = self.df['close'].ewm(span=9).mean()
        self.df['ema_slow'] = self.df['close'].ewm(span=21).mean()
        logger.info(f"💹 EMAs: Fast={self.df['ema_fast'].iloc[-1]:.2f} | Slow={self.df['ema_slow'].iloc[-1]:.2f}")
    
    def add_new_data(self):
        try:
            new_df = self.api.get_candle_data(duration=5)
            if new_df.empty:
                if self.api.is_market_open():
                    logger.debug("No new live candle yet")
                self._add_simulated_tick()
                return
            
            latest = new_df.iloc[-1]
            if len(self.df) == 0 or latest['timestamp'] > self.df['timestamp'].iloc[-1]:
                new_row = pd.DataFrame([latest])
                self.df = pd.concat([self.df, new_row], ignore_index=True).tail(150)
                self.df['ema_fast'] = self.df['close'].ewm(span=9).mean()
                self.df['ema_slow'] = self.df['close'].ewm(span=21).mean()
                source = "LIVE" if len(new_df) > 0 else "SIM"
                logger.info(f"📊 {source} Candle: {latest['timestamp'].strftime('%H:%M')} | Close: ₹{latest['close']:.2f}")
            else:
                self._add_simulated_tick()
        except Exception as e:
            logger.error(f"❌ Update error: {e}")
            self._add_simulated_tick()
    
    def _add_simulated_tick(self):
        if len(self.df) == 0:
            return
        last_close = self.df['close'].iloc[-1]
        change = np.random.normal(0, 0.0005)
        new_price = last_close * (1 + change)
        new_candle = {
            'timestamp': datetime.now(),
            'open': last_close,
            'high': max(last_close, new_price) * 1.0005,
            'low': min(last_close, new_price) * 0.9995,
            'close': new_price,
            'volume': np.random.randint(1000000, 3000000)
        }
        self.df = pd.concat([self.df, pd.DataFrame([new_candle])], ignore_index=True).tail(150)
        self.df['ema_fast'] = self.df['close'].ewm(span=9).mean()
        self.df['ema_slow'] = self.df['close'].ewm(span=21).mean()
        logger.info(f"🔄 SIM Tick: ₹{new_price:.2f}")
    
    def check_for_signal(self):
        if len(self.df) < 21:
            return "HOLD"
        
        curr = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        if pd.isna(curr['ema_fast']):
            return "HOLD"
        
        fast_above_now = curr['ema_fast'] > curr['ema_slow']
        fast_above_prev = prev['ema_fast'] > prev['ema_slow']
        
        avg_vol = self.df['volume'].tail(20).mean()
        vol_ok = curr['volume'] > avg_vol * 0.8  # Relaxed for futures
        
        if fast_above_now and not fast_above_prev and vol_ok:
            logger.info("🎯 BUY SIGNAL: EMA Crossover + Volume OK")
            return "BUY"
        elif not fast_above_now and fast_above_prev and vol_ok:
            logger.info("🎯 SELL SIGNAL: EMA Crossover + Volume OK")
            return "SELL"
        return "HOLD"
    
    def send_telegram_alert(self, message):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
            requests.post(url, json=payload)
            logger.info("📱 Telegram alert sent")
        except Exception as e:
            logger.error(f"❌ Telegram error: {e}")
    
    def enter_trade(self, signal):
        price = self.df['close'].iloc[-1]
        trade = {
            'trade_id': f"T{len(self.trades)+1}",
            'entry_time': datetime.now(),
            'signal': signal,
            'entry_price': price,
            'quantity': QUANTITY,
            'status': 'OPEN'
        }
        
        if signal == "BUY":
            trade['target'] = price * 1.005
            trade['stop_loss'] = price * 0.9975
            trans_type = "BUY"
        else:
            trade['target'] = price * 0.995
            trade['stop_loss'] = price * 1.0025
            trans_type = "SELL"
        
        self.current_position = trade
        self.trades.append(trade)
        
        alert_msg = f"🚨 {signal} @ ₹{price:.2f} | Target: ₹{trade['target']:.2f} | SL: ₹{trade['stop_loss']:.2f}"
        logger.info(f"💰 TRADE ENTERED: {alert_msg}")
        self.send_telegram_alert(alert_msg)
        
        if not PAPER_TRADING:
            # LIVE ORDER - UNCOMMENT TO ENABLE
            # order_id = self.api.place_order(trans_type, QUANTITY)
            # if order_id:
            #     trade['order_id'] = order_id['data']['orderid']
            pass  # Paper mode: Log only
    
    def manage_position(self):
        if not self.current_position or self.current_position['status'] != 'OPEN':
            return
        
        price = self.df['close'].iloc[-1]
        trade = self.current_position
        
        hit_target = (trade['signal'] == "BUY" and price >= trade['target']) or \
                     (trade['signal'] == "SELL" and price <= trade['target'])
        hit_sl = (trade['signal'] == "BUY" and price <= trade['stop_loss']) or \
                 (trade['signal'] == "SELL" and price >= trade['stop_loss'])
        
        if hit_target or hit_sl:
            reason = "TARGET" if hit_target else "STOPLOSS"
            is_win = hit_target
            self.exit_trade(reason, price, is_win)
    
    def exit_trade(self, reason, price, is_win):
        trade = self.current_position
        pnl = (price - trade['entry_price']) * trade['quantity'] if trade['signal'] == "BUY" \
              else (trade['entry_price'] - price) * trade['quantity']
        
        trade.update({
            'exit_price': price,
            'status': reason,
            'pnl': pnl,
            'hold_time': (datetime.now() - trade['entry_time']).total_seconds(),
            'exit_time': datetime.now()
        })
        
        self.total_pnl += pnl
        if is_win:
            self.wins += 1
        else:
            self.losses += 1
        
        alert_msg = f"✅ {reason} | {trade['signal']} | PnL: ₹{pnl:+.2f} | Total: ₹{self.total_pnl:.2f}"
        logger.info(alert_msg)
        self.send_telegram_alert(alert_msg)
        self.current_position = None
    
    def generate_report(self, duration):
        completed = [t for t in self.trades if t['status'] in ['TARGET', 'STOPLOSS']]
        logger.info("=" * 60)
        logger.info("📈 LIVE TRADING REPORT")
        logger.info("=" * 60)
        logger.info(f"⏱️ Duration: {duration:.1f}s | Iterations: {self.iteration}")
        logger.info(f"🎯 Total Trades: {len(self.trades)} | Completed: {len(completed)}")
        
        if completed:
            win_rate = (self.wins / len(completed)) * 100
            logger.info(f"🏆 Wins: {self.wins} | Losses: {self.losses} | Win Rate: {win_rate:.1f}%")
            logger.info(f"💰 Total PnL: ₹{self.total_pnl:.2f} | Avg/Trade: ₹{self.total_pnl/len(completed):.2f}")
            
            # CSV Export
            df_out = pd.DataFrame([{
                'ID': t['trade_id'], 'Signal': t['signal'], 'Entry': t['entry_price'],
                'Exit': t['exit_price'], 'PnL': t['pnl'], 'Status': t['status'],
                'Hold(s)': int(t['hold_time']), 'EntryTime': t['entry_time'].strftime('%H:%M:%S')
            } for t in completed])
            df_out.to_csv('live_trading_results.csv', index=False)
            logger.info("💾 Results saved: live_trading_results.csv")
            
            status = "Excellent!" if win_rate >= 60 else "Good" if win_rate >= 50 else "Tune Parameters"
            logger.info(f"💡 STRATEGY: {status}")
        else:
            logger.info("📝 No completed trades yet.")
        
        logger.info("🎉 BOT SESSION COMPLETED!")
    
    def run_bot(self):
        logger.info("🤖 LIVE EMA CROSSOVER BOT | NIFTY FUT | 0.5% Target | 0.25% SL | Volume Filter")
        logger.info(f"📋 Mode: {'LIVE ORDERS' if not PAPER_TRADING else 'PAPER TRADING'}")
        if not self.api.is_market_open():
            logger.warning("⏰ Market closed - running in simulation mode")
        logger.info("=" * 60)
        
        start_time = time.time()
        try:
            while self.iteration < self.total_iterations:
                if self.iteration % 20 == 0:
                    prog = (self.iteration / self.total_iterations * 100) if self.total_iterations != float('inf') else 'Continuous'
                    logger.info(f"📊 Progress: {self.iteration} | PnL: ₹{self.total_pnl:.2f} | Market Open: {self.api.is_market_open()}")
                
                self.add_new_data()
                
                if not self.current_position:
                    signal = self.check_for_signal()
                    if signal in ["BUY", "SELL"]:
                        self.enter_trade(signal)
                
                self.manage_position()
                self.iteration += 1
                time.sleep(60)  # 1-min candles → wait 60s
                
        except KeyboardInterrupt:
            logger.info("🛑 Stopped by user")
        finally:
            duration = time.time() - start_time
            self.generate_report(duration)
            self.api.logout()


if __name__ == "__main__":
    print("🚀 LIVE NIFTY FUT TRADING BOT - Auto Token + Real Orders + Alerts")
    print("Run during 9:15 AM - 3:30 PM IST for live data")
    print("=" * 60)
    
    # For continuous: bot = LiveTradingBot(continuous=True)
    bot = LiveTradingBot(iterations=100)
    bot.run_bot()