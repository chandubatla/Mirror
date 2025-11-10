#!/usr/bin/env python3
from main import MirroringController

controller = MirroringController()
print("🔍 SYMBOL SEARCH TEST")
print("=" * 50)

# Authenticate first
print("Authenticating accounts...")
auth_results = controller.auth.authenticate_all_accounts()

if not auth_results.get('mirror_account', {}).get('success'):
    print("❌ Authentication failed")
    exit(1)

print("✅ Authentication successful")

# Test different search terms
test_symbols = [
    "NIFTY",
    "BANKNIFTY", 
    "NIFTY11NOV26100CE",
    "NIFTY26100CE",
    "NIFTY11NOV26100CE.NFO"
]

for symbol in test_symbols:
    print(f"\n📡 Searching for: {symbol}")
    print("-" * 30)
    controller.debug_symbol_search(symbol)
    print("-" * 30)