import csv, os
from datetime import datetime

class PnLTracker:
    def __init__(self, log_dir="logs"):
        self.file_path = os.path.join(log_dir, f"pnl_{datetime.now().date()}.csv")
        os.makedirs(log_dir, exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", newline="") as f:
                csv.writer(f).writerow(["timestamp", "signal", "entry", "exit", "pnl", "hold_sec", "latency_ms"])
        self.entry_price = None
        self.entry_time = None

    def record_entry(self, price):
        self.entry_price = price
        self.entry_time = datetime.now()
        print(f"[ENTRY] {price}")

    def record_exit(self, price):
        if not self.entry_price:
            return
        pnl = round(price - self.entry_price, 2)
        hold = (datetime.now() - self.entry_time).seconds
        with open(self.file_path, "a", newline="") as f:
            csv.writer(f).writerow([datetime.now().strftime("%H:%M:%S"), "BUY→SELL", self.entry_price, price, pnl, hold, ""])
        print(f"[EXIT] {price} | PnL: {pnl}")
        self.entry_price, self.entry_time = None, None
