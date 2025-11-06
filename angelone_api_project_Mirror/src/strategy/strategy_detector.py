import time
import logging
import pandas as pd
from datetime import datetime

class EMAStrategy:
    def __init__(self, config, latency_tracker, pnl_tracker):
        self.logger = logging.getLogger("EMA_STRATEGY")
        self.config = config
        self.latency_tracker = latency_tracker
        self.pnl_tracker = pnl_tracker
        self.candles = []
        self.position = None  # 'BUY' / 'SELL' / None
        self.last_signal_time = None

    def on_new_candle(self, candle):
        """Receive new 1-minute candle from WebSocket manager"""
        start = time.time()
        self.candles.append(candle)
        if len(self.candles) < self.config["EMA_SLOW"]:
            return

        df = pd.DataFrame(self.candles)
        df["ema_fast"] = df["close"].ewm(span=self.config["EMA_FAST"], adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.config["EMA_SLOW"], adjust=False).mean()
        latest = df.iloc[-1]

        signal = None
        if latest["ema_fast"] > latest["ema_slow"] and self.position != "BUY":
            signal = "BUY"
        elif latest["ema_fast"] < latest["ema_slow"] and self.position == "BUY":
            signal = "SELL"

        if signal:
            latency = round((time.time() - start) * 1000, 2)
            self.latency_tracker.record("candle_to_signal", latency)
            self.execute_signal(signal, latest)

    def execute_signal(self, signal, candle):
        self.logger.info(f"SIGNAL: {signal} | EMA9: {candle['ema_fast']:.2f} | EMA21: {candle['ema_slow']:.2f}")
        if signal == "BUY":
            self.position = "BUY"
            self.pnl_tracker.record_entry(candle["close"])
        elif signal == "SELL" and self.position == "BUY":
            self.position = None
            self.pnl_tracker.record_exit(candle["close"])
