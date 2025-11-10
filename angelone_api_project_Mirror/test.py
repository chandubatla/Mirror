#!/usr/bin/env python3
import os
import time
from dotenv import load_dotenv
from SmartApi import SmartConnect

# Load environment
load_dotenv("/root/config.env")

def test_source_account():
    print("🔧 TESTING SOURCE ACCOUNT - REFRESH TOKEN")
    print("=" * 50)
    
    # Source account credentials
    api_key = os.getenv("SOURCE_API_KEY")
    client_id = os.getenv("SOURCE_CLIENT_ID") 
    mpin = os.getenv("SOURCE_MPIN")
    
    print(f"API Key: {api_key[:10]}...")
    print(f"Client ID: {client_id}")
    
    try:
        # Create connection
        connection = SmartConnect(api_key=api_key)
        print("✅ SmartConnect created")
        
        # Login with refresh token (if available)
        print("🔄 Checking for existing session...")
        
        # Try to get profile without login first
        try:
            profile = connection.getProfile()
            if profile.get('status'):
                print("✅ Already logged in!")
            else:
                print("❌ Not logged in, need fresh login")
                return
        except:
            print("❌ No active session, need fresh login")
            return
        
        # Test 1: Search for symbols
        print("\n🔍 TEST 1: Searching for NIFTY symbols...")
        result = connection.searchscrip("NFO", "NIFTY")
        
        if result.get('status'):
            symbols = result.get('data', [])
            print(f"✅ Found {len(symbols)} NIFTY symbols")
            
            # Show first 10 symbols
            print("\n📋 First 10 symbols:")
            for i, symbol in enumerate(symbols[:10]):
                symbol_name = symbol.get('symbol', 'N/A')
                token = symbol.get('token', 'N/A')
                print(f"  {i+1}. {symbol_name} -> Token: {token}")
        else:
            print(f"❌ Search failed: {result.get('message')}")
        
        # Test 2: Get NIFTY spot price
        print("\n💰 TEST 2: Getting NIFTY spot price...")
        nifty_spot = connection.searchscrip("NSE", "NIFTY 50")
        if nifty_spot.get('status') and nifty_spot.get('data'):
            nifty_token = nifty_spot['data'][0].get('token')
            nifty_symbol = nifty_spot['data'][0].get('symbol')
            
            ltp_data = connection.ltpData("NSE", nifty_symbol, nifty_token)
            if ltp_data.get('status'):
                spot_price = ltp_data['data']['ltp']
                print(f"✅ NIFTY Spot: ₹{spot_price}")
            else:
                print(f"❌ LTP failed: {ltp_data.get('message')}")
        
        # Test 3: Check specific option symbol
        print("\n🎯 TEST 3: Checking specific option...")
        test_symbols = [
            "NIFTY11NOV26100CE",
            "NIFTY26100CE", 
            "NIFTY11NOV26100CE.NFO"
        ]
        
        for symbol in test_symbols:
            print(f"  Searching: {symbol}")
            search_result = connection.searchscrip("NFO", symbol)
            if search_result.get('status') and search_result.get('data'):
                for item in search_result['data']:
                    if symbol in item.get('symbol', ''):
                        print(f"  ✅ FOUND: {item.get('symbol')} -> Token: {item.get('token')}")
                        break
                else:
                    print(f"  ❌ Not found in results")
            else:
                print(f"  ❌ Search failed")
        
        # Test 4: Get order book
        print("\n📊 TEST 4: Checking order book...")
        order_book = connection.orderBook()
        if order_book.get('status'):
            orders = order_book.get('data', [])
            print(f"✅ Found {len(orders)} orders in book")
            for order in orders[:3]:  # Show first 3 orders
                print(f"  - {order.get('tradingsymbol')} | {order.get('transactiontype')} | Qty: {order.get('quantity')}")
        else:
            print(f"❌ Order book failed: {order_book.get('message')}")
            
        # Test 5: Get positions
        print("\n📈 TEST 5: Checking positions...")
        positions = connection.position()
        if positions.get('status'):
            pos_data = positions.get('data', [])
            print(f"✅ Found {len(pos_data)} positions")
            for pos in pos_data[:3]:  # Show first 3 positions
                print(f"  - {pos.get('tradingsymbol')} | Net: {pos.get('netqty')} | P&L: {pos.get('pnl')}")
        else:
            print(f"❌ Positions failed: {positions.get('message')}")
            
        print("\n🎯 SOURCE ACCOUNT TEST COMPLETED!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        print(f"Full error: {traceback.format_exc()}")

if __name__ == "__main__":
    test_source_account()