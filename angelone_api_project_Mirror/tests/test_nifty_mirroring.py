import os
import sys

# Ensure repository root is on sys.path when tests run
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from main import MirroringController

class StubDetector:
    def __init__(self, sample_trade):
        self._sample = sample_trade

    def detect_new_trades(self):
        # Simulate the search script returning a NIFTY trade
        return [self._sample]

    def get_detection_stats(self):
        return {'total_processed_trades': 1}


class StubSafety:
    def __init__(self):
        self.mirroring_enabled = True
        self.emergency_stop = False

    def can_mirror_trade(self, trade):
        # Allow mirroring for the test trade
        return True, ""

    def enable_mirroring(self):
        self.mirroring_enabled = True
        return True

    def disable_mirroring(self):
        self.mirroring_enabled = False
        return True

    def emergency_stop_mirroring(self):
        self.emergency_stop = True
        self.mirroring_enabled = False
        return True

    def get_safety_status(self):
        return {'mirroring_enabled': self.mirroring_enabled, 'emergency_stop': self.emergency_stop}


class StubMirrorEngine:
    def __init__(self):
        self.mirrored_trades = []

    def mirror_trade(self, trade):
        self.mirrored_trades.append(trade)
        return True

    def get_mirror_stats(self):
        return {'total_mirrored': len(self.mirrored_trades)}

    def start(self):
        pass

    def stop(self):
        pass


class StubAuth:
    def __init__(self):
        pass

    def get_all_connections(self):
        return {}


def test_nifty_search_and_mirror_flow():
    """
    Simulate the search script returning a NIFTY trade and ensure the controller
    processes it and the mirror engine records the mirroring.
    """
    controller = MirroringController()

    # Prepare a sample NIFTY trade
    nifty_trade = {
        'symbol': 'NIFTY',
        'quantity': 25,
        'order_price': 19100
    }

    # Inject stubs to avoid any external API calls
    controller.detector = StubDetector(nifty_trade)
    controller.safety = StubSafety()
    stub_engine = StubMirrorEngine()
    controller.mirror_engine = stub_engine
    controller.auth = StubAuth()

    # Simulate detection and processing loop once
    new_trades = controller.detector.detect_new_trades()
    assert new_trades, "Detector should return at least one trade"
    assert new_trades[0]['symbol'] == 'NIFTY', "Returned trade should be for NIFTY"

    # Process the trade for mirroring
    controller._process_trade_for_mirroring(new_trades[0])

    # Validate the mirror engine recorded the trade
    assert len(stub_engine.mirrored_trades) == 1
    assert stub_engine.mirrored_trades[0]['symbol'] == 'NIFTY'

    # Validate get_status exposes mirror stats correctly
    status = controller.get_status()
    assert status['mirror_stats']['total_mirrored'] == 1
    assert status['detection_stats']['total_processed_trades'] == 1
    assert status['safety_status']['mirroring_enabled'] is True

    # Ensure print_status runs without raising
    controller.print_status()