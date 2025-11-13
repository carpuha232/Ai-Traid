#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick script to check current status on Binance"""
import json
import sys
from binance.client import Client

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load config
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

api_key = config['api']['key']
api_secret = config['api']['secret']

client = Client(api_key, api_secret)

print("=" * 60)
print("📊 CURRENT STATUS ON BINANCE")
print("=" * 60)

# 1. Account balance
account = client.futures_account(recvWindow=60000)
for asset in account.get('assets', []):
    if asset['asset'] == 'USDT':
        print(f"\n💰 Balance:")
        print(f"   Wallet: ${float(asset['walletBalance']):.2f}")
        print(f"   Available: ${float(asset['availableBalance']):.2f}")
        print(f"   Margin: ${float(asset['marginBalance']):.2f}")

# 2. Open positions
positions = client.futures_position_information(recvWindow=60000)
open_positions = [p for p in positions if float(p['positionAmt']) != 0]

print(f"\n📈 Open Positions: {len(open_positions)}")
for pos in open_positions:
    symbol = pos['symbol']
    amt = float(pos['positionAmt'])
    entry = float(pos['entryPrice'])
    mark = float(pos['markPrice'])
    pnl = float(pos['unRealizedProfit'])
    margin = float(pos.get('initialMargin', pos.get('positionInitialMargin', 0)))
    pnl_pct = (pnl / margin) * 100 if margin > 0 else 0
    liq = float(pos.get('liquidationPrice', 0))
    leverage = int(pos['leverage'])
    
    side = "LONG" if amt > 0 else "SHORT"
    emoji = "🟢" if side == "LONG" else "🔴"
    
    print(f"\n{emoji} {symbol} {side}")
    print(f"   Entry: ${entry:.4f}")
    print(f"   Mark: ${mark:.4f}")
    print(f"   Amount: {abs(amt)}")
    print(f"   Leverage: {leverage}x")
    print(f"   Margin: ${margin:.2f}")
    print(f"   PNL: ${pnl:.2f} ({pnl_pct:+.1f}%)")
    print(f"   Liquidation: ${liq:.4f}")

# 3. Open orders
orders = client.futures_get_open_orders(recvWindow=60000)
print(f"\n📋 Open Orders: {len(orders)}")
for order in orders:
    symbol = order['symbol']
    order_type = order['type']
    side = order['side']
    qty = float(order['origQty'])
    price = float(order.get('price', 0))
    stop_price = float(order.get('stopPrice', 0))
    order_id = order['orderId']
    
    if order_type == 'LIMIT':
        emoji = "🎯"
        desc = f"LIMIT {side} @ ${price:.4f}"
    elif order_type in ['STOP', 'STOP_MARKET']:
        emoji = "🛡️"
        desc = f"STOP {side} @ ${stop_price:.4f}"
    elif order_type in ['TAKE_PROFIT', 'TAKE_PROFIT_MARKET']:
        emoji = "💰"
        desc = f"TP {side} @ ${stop_price:.4f}"
    else:
        emoji = "❓"
        desc = f"{order_type} {side}"
    
    print(f"\n{emoji} {symbol}: {desc}")
    print(f"   Qty: {qty}")
    print(f"   Order ID: {order_id}")

print("\n" + "=" * 60)
print("✅ Status check complete")
print("=" * 60)

