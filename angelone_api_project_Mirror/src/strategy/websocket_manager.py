import time
import logging
from datetime import datetime
import random  # replace with actual tick feed later

class WebSocketManager:
    def __init__(self, symbol, strategy, latency_tracker):
        self.logger = logging.getLogger("FEED")
        self.symbol = symbol
        self.strategy = strategy
        self.latency_tracker = latency_tracker
        self.running = False

    def start(self):
        self.running = True
        self.logger.info(f"Feed started for {self.symbol}")
        while self.running:
            now = datetime.now()
            candle = {
                "timestamp": now.strftime("%H:%M:%S"),
                "open": random.uniform(48000, 48300),
                "high": random.uniform(48300, 48400),
                "low": random.uniform(48000, 48200),
                "close": random.uniform(48100, 48350),
            }
            latency = round((time.time() * 1000) % 100, 2)
            self.latency_tracker.record("tick_to_candle", latency)
            self.logger.info(f"Candle built ({latency} ms) O:{candle['open']:.2f} H:{candle['high']:.2f} L:{candle['low']:.2f} C:{candle['close']:.2f}")
            self.strategy.on_new_candle(candle)
            time.sleep(2)  # simulate 1-min feed (shortened for local test)

    def stop(self):
        self.running = False
        self.logger.info("Feed stopped.")
