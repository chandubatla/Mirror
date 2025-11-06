import csv, os, time
from datetime import datetime

class LatencyTracker:
    def __init__(self, log_dir="logs"):
        self.file_path = os.path.join(log_dir, f"latency_{datetime.now().date()}.csv")
        os.makedirs(log_dir, exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", newline="") as f:
                csv.writer(f).writerow(["timestamp", "event", "latency_ms"])

    def record(self, event, latency_ms):
        with open(self.file_path, "a", newline="") as f:
            csv.writer(f).writerow([datetime.now().strftime("%H:%M:%S"), event, latency_ms])
