#!/usr/bin/env python3
"""
FINAL WORKING BOT - Real Angel One + Live NIFTY Candles
EMA Crossover Strategy | 100 Iteration Test
"""

import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from SmartApi import SmartConnect
import pyotp

# === YOUR CREDENTIALS (FILL THESE) ===
from dotenv import load_dotenv
import os
load_dotenv(dotenv_path="D:/tax/config.env")
load_dotenv(dotenv_path="../.env")   # go one directory up
API_KEY   = os.getenv("API_KEY")
CLIENT_ID = os.getenv("CLIENT_ID")
MPIN      = os.getenv("MPIN")
TOTP_TOKEN = os.getenv("TOTP_TOKEN")

# === NIFTY TOKEN ===
# NIFTY November 2025 Future (example)
NIFTY_FUT_TOKEN = "17855"   # Update from symbol file
EXCHANGE = "NFO"

# === Logging Setup ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8',
    handlers=[
        logging.FileHandler('final_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AngelAPI:
    """Handles Angel One authentication and data fetching"""
    
    def __init__(self):
        self.obj = None
        self.is_authenticated = False
        self.authenticate()
    
    def authenticate(self):
        """Your proven authentication"""
        try:
            logger.info("Authenticating with Angel One...")
            totp = pyotp.TOTP(TOTP_TOKEN).now()
            logger.info(f"TOTP: {totp}")
            
            self.obj = SmartConnect(api_key=API_KEY)
            data = self.obj.generateSession(CLIENT_ID, MPIN, totp)
            
            if data['status']:
                self.is_authenticated = True
                logger.info("Angel One Authentication SUCCESSFUL!")
            else:
                logger.error(f"Auth failed: {data.get('message')}")
                
        except Exception as e:
            logger.error(f"Auth error: {e}")
            self.is_authenticated = False
    
    def get_candle_data(self, symbol=NIFTY_FUT_TOKEN, duration=30):
        """Fetch historical 1-minute candles"""
        try:
            if not self.is_authenticated:
                return pd.DataFrame()
            
            from_date = (datetime.now() - timedelta(minutes=duration)).strftime("%Y-%m-%d %H:%M")
            to_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            params = {
                "exchange": EXCHANGE,
                "symboltoken": symbol,
                "interval": "ONE_MINUTE",
                "fromdate": from_date,
                "todate": to_date
            }
            
            response = self.obj.getCandleData(params)
            
            if response['data']:
                df = pd.DataFrame(response['data'],
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
                return df.sort_values('timestamp').reset_index(drop=True)
            else:
                logger.warning(f"No candle data: {response.get('message')}")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Candle fetch error: {e}")
            return pd.DataFrame()
    
    def logout(self):
        """Logout safely"""
        try:
            if self.is_authenticated and self.obj:
                self.obj.terminateSession(CLIENT_ID)
                logger.info("Logged out from Angel One")
        except Exception as e:
            logger.error(f"Logout error: {e}")


class FinalTradingBot:
    def __init__(self, iterations=100):
        self.df = pd.DataFrame()
        self.current_position = None
        self.trades = []
        self.iteration = 0
        self.total_iterations = iterations
        self.api = AngelAPI()
        
        # Stats
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0
        
        self.initialize_bot()
    
    def initialize_bot(self):
        if self.api.is_authenticated:
            logger.info("FINAL TRADING BOT INITIALIZED (LIVE MODE)")
        else:
            logger.info("BOT RUNNING IN SIMULATION MODE")
        self.create_initial_data()
    
    def _create_simulated_data(self):
        """Fallback: Generate realistic price series"""
        logger.info("Generating simulated initial data...")
        base_price = 45000
        num_points = 20
        prices = [base_price]
        
        for _ in range(1, num_points):
            change = np.random.normal(0, 0.0015)
            prices.append(prices[-1] * (1 + change))
        
        timestamps = [datetime.now() - timedelta(minutes=i) for i in range(num_points, 0, -1)]
        
        self.df = pd.DataFrame({
            'timestamp': timestamps,
            'open': prices,
            'high': [p * (1 + np.random.uniform(0, 0.001)) for p in prices],
            'low': [p * (1 - np.random.uniform(0, 0.001)) for p in prices],
            'close': prices,
            'volume': np.random.randint(500000, 1200000, num_points)
        })
    
    def create_initial_data(self):
        """Load live data or fallback to simulation"""
        logger.info("Fetching initial market data...")
        df_live = self.api.get_candle_data(duration=30)
        
        if not df_live.empty and len(df_live) >= 10:
            self.df = df_live.tail(50).copy()
            logger.info(f"Live data loaded: {len(self.df)} candles")
        else:
            logger.warning("Live data failed or insufficient → using simulation")
            self._create_simulated_data()
        
        # Calculate EMAs
        self.df['ema_fast'] = self.df['close'].ewm(span=9).mean()
        self.df['ema_slow'] = self.df['close'].ewm(span=21).mean()
        
        logger.info(f"EMAs: Fast={self.df['ema_fast'].iloc[-1]:.2f}, Slow={self.df['ema_slow'].iloc[-1]:.2f}")
    
    def add_new_data(self):
        """Fetch latest completed candle"""
        try:
            new_df = self.api.get_candle_data(duration=3)
            if new_df.empty:
                return
            
            latest = new_df.iloc[-1]
            last_ts = self.df['timestamp'].iloc[-1] if len(self.df) > 0 else None
            
            # Avoid duplicate timestamp
            if last_ts is None or latest['timestamp'] > last_ts:
                new_row = pd.DataFrame([latest])
                self.df = pd.concat([self.df, new_row], ignore_index=True)
                self.df = self.df.tail(150)
                
                # Update EMAs
                self.df['ema_fast'] = self.df['close'].ewm(span=9).mean()
                self.df['ema_slow'] = self.df['close'].ewm(span=21).mean()
                
                source = "LIVE" if self.api.is_authenticated else "SIM"
                logger.info(f"{source} Candle: {latest['timestamp'].strftime('%H:%M')} | Close: ₹{latest['close']:.2f}")
            else:
                logger.debug("No new candle yet")
                
        except Exception as e:
            logger.error(f"Update failed: {e}")
            # Optional: fallback LTP simulation
            self._add_simulated_tick()
    
    def _add_simulated_tick(self):
        """Fallback: simulate price movement"""
        last_close = self.df['close'].iloc[-1]
        volatility = np.random.normal(0, 0.002)
        new_price = last_close * (1 + volatility)
        new_price = max(44500, min(45500, new_price))
        
        new_candle = {
            'timestamp': datetime.now(),
            'open': last_close,
            'high': max(last_close, new_price) * (1 + np.random.uniform(0, 0.0005)),
            'low': min(last_close, new_price) * (1 - np.random.uniform(0, 0.0005)),
            'close': new_price,
            'volume': np.random.randint(500000, 1200000)
        }
        
        self.df = pd.concat([self.df, pd.DataFrame([new_candle])], ignore_index=True)
        self.df = self.df.tail(150)
        self.df['ema_fast'] = self.df['close'].ewm(span=9).mean()
        self.df['ema_slow'] = self.df['close'].ewm(span=21).mean()
        logger.info(f"SIM Tick: ₹{new_price:.2f}")
    
    def check_for_signal(self):
        if len(self.df) < 10:
            return "HOLD"
        
        curr = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        if pd.isna(curr['ema_fast']) or pd.isna(prev['ema_fast']):
            return "HOLD"
        
        fast_above_now = curr['ema_fast'] > curr['ema_slow']
        fast_above_prev = prev['ema_fast'] > prev['ema_slow']
        
        avg_vol = self.df['volume'].tail(20).mean()
        vol_ok = curr['volume'] > avg_vol
        
        if fast_above_now and not fast_above_prev and vol_ok:
            logger.info("BUY SIGNAL: EMA(9) crossed above EMA(21)")
            return "BUY"
        elif not fast_above_now and fast_above_prev and vol_ok:
            logger.info("SELL SIGNAL: EMA(9) crossed below EMA(21)")
            return "SELL"
        return "HOLD"
    
    def enter_trade(self, signal):
        price = self.df['close'].iloc[-1]
        qty = 15
        
        trade = {
            'trade_id': f"T{len(self.trades)+1}",
            'entry_time': datetime.now(),
            'signal': signal,
            'entry_price': price,
            'quantity': qty,
            'status': 'OPEN'
        }
        
        if signal == "BUY":
            trade['target'] = price * 1.0050   # +0.50%
            trade['stop_loss'] = price * 0.9975  # -0.25%
        else:
            trade['target'] = price * 0.9950
            trade['stop_loss'] = price * 1.0025
        
        self.current_position = trade
        self.trades.append(trade)
        
        logger.info(f"TRADE: {signal} @ ₹{price:.2f} | T:₹{trade['target']:.2f} | SL:₹{trade['stop_loss']:.2f}")
    
    def manage_position(self):
        if not self.current_position or self.current_position['status'] != 'OPEN':
            return
        
        price = self.df['close'].iloc[-1]
        trade = self.current_position
        
        hit_target = (trade['signal'] == "BUY" and price >= trade['target']) or \
                     (trade['signal'] == "SELL" and price <= trade['target'])
        hit_sl = (trade['signal'] == "BUY" and price <= trade['stop_loss']) or \
                 (trade['signal'] == "SELL" and price >= trade['stop_loss'])
        
        if hit_target:
            self.exit_trade("TARGET", price, True)
        elif hit_sl:
            self.exit_trade("STOPLOSS", price, False)
    
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
        if is_win: self.wins += 1
        else: self.losses += 1
        
        logger.info(f"{reason}: {'+' if is_win else '-'}{abs(pnl):.2f} | Wins: {self.wins} | PnL: ₹{self.total_pnl:.2f}")
        self.current_position = None
    
    def generate_report(self, duration):
        completed = [t for t in self.trades if t['status'] in ['TARGET', 'STOPLOSS']]
        
        logger.info("="*50)
        logger.info("FINAL TRADING REPORT")
        logger.info("="*50)
        logger.info(f"Duration: {duration:.1f}s | Iterations: {self.total_iterations}")
        logger.info(f"Trades: {len(self.trades)} | Completed: {len(completed)}")
        
        if completed:
            win_rate = (self.wins / len(completed)) * 100
            logger.info(f"Wins: {self.wins} | Losses: {self.losses} | Win Rate: {win_rate:.1f}%")
            logger.info(f"Total PnL: ₹{self.total_pnl:.2f} | Avg: ₹{self.total_pnl/len(completed):.2f}")
            
            # Save CSV
            df_out = pd.DataFrame([{
                'ID': t['trade_id'],
                'Signal': t['signal'],
                'Entry': t['entry_price'],
                'Exit': t['exit_price'],
                'PnL': t['pnl'],
                'Status': t['status'],
                'Hold(s)': int(t['hold_time']),
                'EntryTime': t['entry_time'].strftime('%H:%M:%S'),
                'ExitTime': t['exit_time'].strftime('%H:%M:%S')
            } for t in completed])
            df_out.to_csv('final_trading_results.csv', index=False)
            logger.info("Results saved: final_trading_results.csv")
            
            if win_rate >= 60:
                logger.info("STRATEGY: Excellent!")
            elif win_rate >= 50:
                logger.info("STRATEGY: Good")
            else:
                logger.info("STRATEGY: Needs tuning")
        else:
            logger.info("No completed trades.")
        
        logger.info("BOT COMPLETED SUCCESSFULLY!")
    
    def run_bot(self):
        logger.info("EMA Crossover Bot | 0.5% Target | 0.25% SL | Volume Filter")
        logger.info("="*50)
        
        start_time = time.time()
        try:
            for self.iteration in range(self.total_iterations):
                if self.iteration % 20 == 0:
                    prog = (self.iteration / self.total_iterations) * 100
                    logger.info(f"Progress: {self.iteration}/{self.total_iterations} ({prog:.1f}%) | PnL: ₹{self.total_pnl:.2f}")
                
                self.add_new_data()
                
                if not self.current_position:
                    signal = self.check_for_signal()
                    if signal in ["BUY", "SELL"]:
                        self.enter_trade(signal)
                
                self.manage_position()
                time.sleep(2)
                
        except KeyboardInterrupt:
            logger.info("Stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}")
        
        finally:
            duration = time.time() - start_time
            self.generate_report(duration)
            # self.api.logout()  # Uncomment in production


if __name__ == "__main__":
    print("FINAL TRADING BOT - LIVE NIFTY EMA CROSSOVER")
    print("Fill your credentials in the script")
    print("="*50)
    bot = FinalTradingBot(iterations=100)
    bot.run_bot()