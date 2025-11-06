#!/usr/bin/env python3
"""
PAPER TRADING BOT - Angel One NIFTY Futures
Real-time market data via Angel One API
Simulated orders (NO REAL TRADES)
Improved strategy with filters
"""

import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from SmartApi import SmartConnect
import pyotp
import requests
from pytz import timezone

# ========================================
# FILL YOUR CREDENTIALS HERE
# ========================================
from dotenv import load_dotenv
import os
load_dotenv(dotenv_path="D:/tax/config.env")
load_dotenv(dotenv_path="../.env")   # go one directory up
API_KEY   = os.getenv("API_KEY")
CLIENT_ID = os.getenv("CLIENT_ID")
MPIN      = os.getenv("MPIN")
TOTP_TOKEN = os.getenv("TOTP_TOKEN")

# ========================================
# TELEGRAM ALERTS (OPTIONAL)
# ========================================
TELEGRAM_BOT_TOKEN = ""  # Leave empty to disable
TELEGRAM_CHAT_ID = ""

# ========================================
# TRADING CONFIGURATION
# ========================================
SYMBOL_NAME = "NIFTY"
EXPIRY_MONTH = "NOV"
EXPIRY_YEAR = "25"
QUANTITY = 15
TIMEFRAME = "FIVE_MINUTE"

# Manual Token (RECOMMENDED)
MANUAL_NIFTY_TOKEN = "5960"          # NIFTY061125FUT (6-Nov-2025 weekly)
MANUAL_TRADING_SYMBOL = "NIFTY27NOV25FUT"

# Strategy Parameters
EMA_FAST = 9
EMA_SLOW = 21
EMA_TREND = 200
ATR_PERIOD = 14
STOP_LOSS_ATR = 1.5
TARGET_ATR = 3.0

# Risk Management
MAX_TRADES_PER_DAY = 3
MAX_CONSECUTIVE_LOSSES = 3
DAILY_LOSS_LIMIT = 5000
TIME_EXIT_MINUTES = 60
TRANSACTION_COST = 216

# ========================================
# LOGGING SETUP
# ========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('paper_trading.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AngelAPI:
    """Angel One API connection handler"""

    def __init__(self):
        self.obj = None
        self.is_authenticated = False
        self.nifty_token = None
        self.trading_symbol = None
        self.authenticate()

    def authenticate(self):
        """Connect to Angel One API"""
        try:
            logger.info("Connecting to Angel One API...")
            totp = pyotp.TOTP(TOTP_TOKEN).now()
            self.obj = SmartConnect(api_key=API_KEY)
            data = self.obj.generateSession(CLIENT_ID, MPIN, totp)

            if data['status']:
                self.is_authenticated = True
                logger.info("Angel One API Connected Successfully!")

                if MANUAL_NIFTY_TOKEN and MANUAL_TRADING_SYMBOL:
                    self.nifty_token = MANUAL_NIFTY_TOKEN
                    self.trading_symbol = MANUAL_TRADING_SYMBOL
                    logger.info(f"Using Manual Token: {self.trading_symbol} | {self.nifty_token}")
                else:
                    self.find_nifty_token()
            else:
                logger.error(f"Authentication Failed: {data.get('message')}")
        except Exception as e:
            logger.error(f"Connection Error: {e}")

    def find_nifty_token(self):
        """Auto-find NIFTY Future token"""
        try:
            search_result = None
            if hasattr(self.obj, 'searchScrip'):
                search_result = self.obj.searchScrip(exchange="NFO", searchscrip=SYMBOL_NAME)
            elif hasattr(self.obj, 'searchscrip'):
                search_result = self.obj.searchscrip(exchange="NFO", searchscrip=SYMBOL_NAME)
            elif hasattr(self.obj, 'search'):
                search_result = self.obj.search(SYMBOL_NAME, "NFO")

            if search_result and search_result.get('status') and search_result.get('data'):
                for item in search_result['data']:
                    symbol = item.get('symbol', '')
                    if EXPIRY_MONTH in symbol and 'FUT' in symbol:
                        self.nifty_token = item['token']
                        self.trading_symbol = symbol
                        logger.info(f"Found: {self.trading_symbol} | Token: {self.nifty_token}")
                        return True
                logger.warning(f"No match for '{EXPIRY_MONTH}' + 'FUT'")
            return False
        except Exception as e:
            logger.error(f"Token search error: {e}")
            return False

    def is_market_open(self):
        """Check if market is open (9:15 AM - 3:30 PM IST)"""
        ist = timezone('Asia/Kolkata')
        now = datetime.now(ist)
        if now.weekday() >= 5:
            return False
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        return market_open <= now <= market_close

    def get_live_data(self, duration_minutes=300):
        """Fetch live candle data with correct IST timing"""
        try:
            if not self.is_authenticated or not self.nifty_token:
                logger.warning("Not authenticated - using simulated data")
                return pd.DataFrame()

            ist = timezone('Asia/Kolkata')
            now_ist = datetime.now(ist)
            from_dt = now_ist - timedelta(minutes=min(duration_minutes, 2880))
            from_str = from_dt.strftime("%Y-%m-%d %H:%M")
            to_str = now_ist.strftime("%Y-%m-%d %H:%M")

            params = {
                "exchange": "NFO",
                "symboltoken": self.nifty_token,
                "interval": TIMEFRAME,
                "fromdate": from_str,
                "todate": to_str
            }

            logger.info(f"Fetching candles: {from_str} to {to_str}")
            response = self.obj.getCandleData(params)

            if response.get('status') and response.get('data'):
                df = pd.DataFrame(
                    response['data'],
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
                logger.info(f"LIVE data fetched: {len(df)} candles | Latest: {df.iloc[-1]['close']:.2f}")
                return df.sort_values('timestamp').reset_index(drop=True)
            else:
                msg = response.get('message', 'Empty data')
                logger.warning(f"No data: {msg}")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Data fetch error: {e}")
            return pd.DataFrame()

    def logout(self):
        """Close API session"""
        try:
            if self.is_authenticated:
                self.obj.terminateSession(CLIENT_ID)
                logger.info("Logged out from Angel One")
        except Exception as e:
            logger.error(f"Logout error: {e}")


class PaperTradingBot:
    """Paper trading bot with live data but simulated orders"""

    def __init__(self, iterations=200):
        self.api = AngelAPI()
        self.df = pd.DataFrame()
        self.current_position = None
        self.trades = []
        self.iteration = 0
        self.total_iterations = iterations
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0
        self.consecutive_losses = 0
        self.trades_today = 0
        self.daily_start_pnl = 0
        self.last_trade_date = None
        self.initialize()

    def initialize(self):
        mode = "LIVE DATA" if self.api.is_authenticated else "SIMULATION"
        logger.info("=" * 70)
        logger.info(f"PAPER TRADING BOT INITIALIZED ({mode})")
        logger.info(f"Strategy: EMA({EMA_FAST}/{EMA_SLOW}/{EMA_TREND}) + VWAP + ATR")
        logger.info(f"Timeframe: 5-minute candles")
        logger.info(f"Risk: Max {MAX_TRADES_PER_DAY} trades/day, {MAX_CONSECUTIVE_LOSSES} losses")
        logger.info(f"Transaction costs: ₹{TRANSACTION_COST} per trade (simulated)")
        logger.info(f"Symbol: {self.api.trading_symbol if self.api.trading_symbol else 'NIFTY FUT'}")
        logger.info(f"Market Status: {'OPEN' if self.api.is_market_open() else 'CLOSED'}")
        logger.info("=" * 70)
        self.load_initial_data()

    def load_initial_data(self):
        df_live = self.api.get_live_data(duration_minutes=1500)
        if not df_live.empty and len(df_live) >= 200:
            self.df = df_live.copy()
            logger.info("Using LIVE market data")
        else:
            logger.warning("Using simulated data (market closed or connection issue)")
            self._create_simulated_data()
        self._calculate_indicators()
        self._log_current_state()

    def _create_simulated_data(self):
        base_price = 24350
        num_candles = 250
        prices = [base_price]
        for _ in range(1, num_candles):
            change = np.random.normal(0, 0.002)
            prices.append(prices[-1] * (1 + change))
        timestamps = [datetime.now() - timedelta(minutes=5*i) for i in range(num_candles, 0, -1)]
        self.df = pd.DataFrame({
            'timestamp': timestamps,
            'open': prices,
            'high': [p * (1 + np.random.uniform(0, 0.002)) for p in prices],
            'low': [p * (1 - np.random.uniform(0, 0.002)) for p in prices],
            'close': prices,
            'volume': np.random.randint(1000000, 3000000, num_candles)
        })

    def _calculate_indicators(self):
        self.df['ema_fast'] = self.df['close'].ewm(span=EMA_FAST).mean()
        self.df['ema_slow'] = self.df['close'].ewm(span=EMA_SLOW).mean()
        self.df['ema_trend'] = self.df['close'].ewm(span=EMA_TREND).mean()
        self.df['high_low'] = self.df['high'] - self.df['low']
        self.df['high_close'] = abs(self.df['high'] - self.df['close'].shift())
        self.df['low_close'] = abs(self.df['low'] - self.df['close'].shift())
        self.df['true_range'] = self.df[['high_low', 'high_close', 'low_close']].max(axis=1)
        self.df['atr'] = self.df['true_range'].rolling(ATR_PERIOD).mean()
        self.df['vwap'] = (self.df['close'] * self.df['volume']).cumsum() / self.df['volume'].cumsum()

    def _log_current_state(self):
        if len(self.df) > 0:
            curr = self.df.iloc[-1]
            logger.info(f"Close: ₹{curr['close']:.2f}")
            logger.info(f"EMAs: Fast={curr['ema_fast']:.2f} | Slow={curr['ema_slow']:.2f} | Trend={curr['ema_trend']:.2f}")
            logger.info(f"ATR: {curr['atr']:.2f} | VWAP: {curr['vwap']:.2f}")

    def update_data(self):
        try:
            new_df = self.api.get_live_data(duration_minutes=10)
            if new_df.empty or not self.api.is_market_open():
                self._add_simulated_candle()
                return
            latest = new_df.iloc[-1]
            if len(self.df) == 0 or latest['timestamp'] > self.df['timestamp'].iloc[-1]:
                new_row = pd.DataFrame([latest])
                self.df = pd.concat([self.df, new_row], ignore_index=True).tail(300)
                self._calculate_indicators()
                logger.info(f"LIVE: {latest['timestamp'].strftime('%H:%M')} | Close: ₹{latest['close']:.2f}")
        except Exception as e:
            logger.error(f"Update error: {e}")
            self._add_simulated_candle()

    def _add_simulated_candle(self):
        if len(self.df) == 0:
            return
        last_close = self.df['close'].iloc[-1]
        change = np.random.normal(0, 0.001)
        new_price = last_close * (1 + change)
        new_candle = {
            'timestamp': datetime.now(),
            'open': last_close,
            'high': max(last_close, new_price) * 1.001,
            'low': min(last_close, new_price) * 0.999,
            'close': new_price,
            'volume': np.random.randint(1000000, 3000000)
        }
        self.df = pd.concat([self.df, pd.DataFrame([new_candle])], ignore_index=True).tail(300)
        self._calculate_indicators()
        logger.info(f"SIM: Close: ₹{new_price:.2f}")

    def check_signal(self):
        if len(self.df) < EMA_TREND:
            return "HOLD"
        today = datetime.now().date()
        if self.last_trade_date != today:
            self.trades_today = 0
            self.daily_start_pnl = self.total_pnl
            self.last_trade_date = today
            self.consecutive_losses = 0
        if self.trades_today >= MAX_TRADES_PER_DAY:
            return "HOLD"
        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            logger.warning(f"Max consecutive losses ({MAX_CONSECUTIVE_LOSSES}) reached")
            return "HOLD"
        daily_pnl = self.total_pnl - self.daily_start_pnl
        if daily_pnl < -DAILY_LOSS_LIMIT:
            logger.warning(f"Daily loss limit hit: ₹{daily_pnl:.0f}")
            return "HOLD"
        curr = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        if pd.isna(curr['ema_fast']) or pd.isna(curr['atr']):
            return "HOLD"
        fast_above_now = curr['ema_fast'] > curr['ema_slow']
        fast_above_prev = prev['ema_fast'] > prev['ema_slow']
        avg_vol = self.df['volume'].tail(20).mean()
        vol_ok = curr['volume'] > avg_vol * 0.8
        above_trend = curr['close'] > curr['ema_trend']
        below_trend = curr['close'] < curr['ema_trend']
        above_vwap = curr['close'] > curr['vwap']
        below_vwap = curr['close'] < curr['vwap']
        atr_ok = curr['atr'] > self.df['atr'].tail(50).mean() * 0.5
        if (fast_above_now and not fast_above_prev and vol_ok and above_trend and above_vwap and atr_ok):
            logger.info("BUY SIGNAL: All filters passed")
            return "BUY"
        elif (not fast_above_now and fast_above_prev and vol_ok and below_trend and below_vwap and atr_ok):
            logger.info("SELL SIGNAL: All filters passed")
            return "SELL"
        return "HOLD"

    def enter_trade(self, signal):
        price = self.df['close'].iloc[-1]
        atr = self.df['atr'].iloc[-1]
        stop_loss = price - (STOP_LOSS_ATR * atr) if signal == "BUY" else price + (STOP_LOSS_ATR * atr)
        target = price + (TARGET_ATR * atr) if signal == "BUY" else price - (TARGET_ATR * atr)
        risk = abs(price - stop_loss) * QUANTITY
        reward = abs(target - price) * QUANTITY
        rr_ratio = reward / risk if risk > 0 else 0
        trade = {
            'trade_id': f"T{len(self.trades)+1}",
            'entry_time': datetime.now(),
            'signal': signal,
            'entry_price': price,
            'stop_loss': stop_loss,
            'target': target,
            'quantity': QUANTITY,
            'status': 'OPEN',
            'transaction_cost': TRANSACTION_COST
        }
        self.current_position = trade
        self.trades.append(trade)
        self.trades_today += 1
        msg = (f"PAPER TRADE ENTERED:\n"
               f"   {signal} @ ₹{price:.2f}\n"
               f"   Target: ₹{target:.2f} (+₹{reward:.0f})\n"
               f"   Stop: ₹{stop_loss:.2f} (-₹{risk:.0f})\n"
               f"   Risk:Reward = 1:{rr_ratio:.2f}")
        logger.info(msg)
        self.send_telegram(msg)

    def manage_position(self):
        if not self.current_position or self.current_position['status'] != 'OPEN':
            return
        price = self.df['close'].iloc[-1]
        trade = self.current_position
        hold_time_minutes = (datetime.now() - trade['entry_time']).total_seconds() / 60
        if hold_time_minutes >= TIME_EXIT_MINUTES:
            is_win = (price > trade['entry_price']) if trade['signal'] == "BUY" else (price < trade['entry_price'])
            logger.info(f"TIME EXIT after {hold_time_minutes:.0f} minutes")
            self.exit_trade("TIME_EXIT", price, is_win)
            return
        now = datetime.now()
        if now.hour == 15 and now.minute >= 15:
            is_win = (price > trade['entry_price']) if trade['signal'] == "BUY" else (price < trade['entry_price'])
            logger.info("EOD EXIT - Squaring off")
            self.exit_trade("EOD_EXIT", price, is_win)
            return
        hit_target = (trade['signal'] == "BUY" and price >= trade['target']) or (trade['signal'] == "SELL" and price <= trade['target'])
        hit_sl = (trade['signal'] == "BUY" and price <= trade['stop_loss']) or (trade['signal'] == "SELL" and price >= trade['stop_loss'])
        if hit_target:
            self.exit_trade("TARGET", price, True)
        elif hit_sl:
            self.exit_trade("STOPLOSS", price, False)

    def exit_trade(self, reason, price, is_win):
        trade = self.current_position
        gross_pnl = ((price - trade['entry_price']) * trade['quantity'] if trade['signal'] == "BUY"
                     else (trade['entry_price'] - price) * trade['quantity'])
        net_pnl = gross_pnl - TRANSACTION_COST
        trade.update({
            'exit_price': price,
            'exit_time': datetime.now(),
            'status': reason,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'hold_time_minutes': (datetime.now() - trade['entry_time']).total_seconds() / 60
        })
        self.total_pnl += net_pnl
        if is_win:
            self.wins += 1
            self.consecutive_losses = 0
        else:
            self.losses += 1
            self.consecutive_losses += 1
        pnl_emoji = "SUCCESS" if net_pnl > 0 else "LOSS"
        msg = (f"{pnl_emoji} TRADE CLOSED: {reason}\n"
               f"   {trade['signal']} | Entry: ₹{trade['entry_price']:.2f} to Exit: ₹{price:.2f}\n"
               f"   Gross P&L: ₹{gross_pnl:+.0f} | Costs: -₹{TRANSACTION_COST}\n"
               f"   NET P&L: ₹{net_pnl:+.0f}\n"
               f"   Total P&L: ₹{self.total_pnl:+.0f}")
        logger.info(msg)
        self.send_telegram(msg)
        self.current_position = None

    def send_telegram(self, message):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=5)
        except:
            pass

    def generate_report(self):
        completed = [t for t in self.trades if t['status'] in ['TARGET', 'STOPLOSS', 'TIME_EXIT', 'EOD_EXIT']]
        logger.info("=" * 70)
        logger.info("PAPER TRADING PERFORMANCE REPORT")
        logger.info("=" * 70)
        logger.info(f"Total Iterations: {self.iteration}")
        logger.info(f"Total Trades: {len(self.trades)} | Completed: {len(completed)}")
        if completed:
            win_rate = (self.wins / len(completed)) * 100
            avg_win = sum(t['net_pnl'] for t in completed if t['net_pnl'] > 0) / self.wins if self.wins > 0 else 0
            avg_loss = sum(t['net_pnl'] for t in completed if t['net_pnl'] < 0) / self.losses if self.losses > 0 else 0
            logger.info(f"Wins: {self.wins} | Losses: {self.losses}")
            logger.info(f"Win Rate: {win_rate:.1f}%")
            logger.info(f"Total P&L: ₹{self.total_pnl:+.0f}")
            logger.info(f"Avg Win: ₹{avg_win:.0f} | Avg Loss: ₹{avg_loss:.0f}")
            df_results = pd.DataFrame([{
                'ID': t['trade_id'],
                'Signal': t['signal'],
                'Entry': t['entry_price'],
                'Exit': t['exit_price'],
                'Net_PnL': t['net_pnl'],
                'Status': t['status'],
                'Hold_Minutes': int(t['hold_time_minutes']),
                'Time': t['entry_time'].strftime('%Y-%m-%d %H:%M')
            } for t in completed])
            df_results.to_csv('paper_trading_results.csv', index=False)
            logger.info("Results saved: paper_trading_results.csv")
            verdict = "Excellent!" if win_rate >= 60 else "Good!" if win_rate >= 50 else "Needs improvement"
            logger.info(f"VERDICT: {verdict}")
        else:
            logger.info("No completed trades yet")
        logger.info("=" * 70)

    def run(self):
        """Main trading loop"""
        logger.info("Starting paper trading bot...")
        logger.info(f"Running for {self.total_iterations} iterations (~{self.total_iterations * 5} minutes)")
        logger.info("Press Ctrl+C to stop\n")
        start_time = time.time()
        try:
            while self.iteration < self.total_iterations:
                if self.iteration % 12 == 0 and self.iteration > 0:
                    logger.info(f"Progress: {self.iteration}/{self.total_iterations} | P&L: ₹{self.total_pnl:+.0f} | Trades: {len(self.trades)}")
                self.update_data()
                if not self.current_position:
                    signal = self.check_signal()
                    if signal in ["BUY", "SELL"]:
                        self.enter_trade(signal)
                self.manage_position()
                self.iteration += 1
                time.sleep(300)
        except KeyboardInterrupt:
            logger.info("\nStopped by user")
        finally:
            duration = (time.time() - start_time) / 3600
            logger.info(f"\nSession duration: {duration:.1f} hours")
            self.generate_report()
            self.api.logout()


# ========================================
# RUN THE BOT
# ========================================
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("NIFTY FUTURES PAPER TRADING BOT")
    print("=" * 70)
    print("PAPER TRADING MODE - No real orders will be placed")
    print("Using LIVE market data from Angel One API")
    print("Best to run during market hours: 9:15 AM - 3:30 PM IST")
    print("=" * 70)
    print("\nIMPORTANT: Credentials are filled. Bot starting...")
    bot = PaperTradingBot(iterations=100)
    bot.run()