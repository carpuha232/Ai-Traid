#!/usr/bin/env python3
"""Проверка активных позиций и ордеров"""

import json
from binance.client import Client

# Загружаем конфиг
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

api_key = config['api']['key']
api_secret = config['api']['secret']

client = Client(api_key, api_secret)

print("=" * 80)
print("АНАЛИЗ АКТИВНЫХ ПОЗИЦИЙ И ОРДЕРОВ")
print("=" * 80)

# Получаем все позиции
positions_data = client.futures_position_information()
print(f"\nВсего позиций в системе: {len(positions_data)}")

# Получаем все открытые ордера
open_orders = client.futures_get_open_orders(recvWindow=60000)
print(f"Всего открытых ордеров: {len(open_orders)}")

# Фильтруем только открытые позиции (не нулевые)
active_positions = []
for pos in positions_data:
    position_amt = float(pos.get('positionAmt', 0))
    if position_amt != 0:
        active_positions.append(pos)

print(f"Активных позиций (не нулевых): {len(active_positions)}\n")

# Группируем ордера по символам
orders_by_symbol = {}
for order in open_orders:
    symbol = order['symbol']
    if symbol not in orders_by_symbol:
        orders_by_symbol[symbol] = []
    orders_by_symbol[symbol].append(order)

# Анализируем каждую позицию
for pos in active_positions:
    symbol = pos['symbol']
    position_amt = float(pos.get('positionAmt', 0))
    entry_price = float(pos.get('entryPrice', 0))
    mark_price = float(pos.get('markPrice', 0))
    unrealized_pnl = float(pos.get('unRealizedProfit', 0))
    leverage = int(pos.get('leverage', 1))
    
    side = 'LONG' if position_amt > 0 else 'SHORT'
    quantity = abs(position_amt)
    
    # Рассчитываем ROI
    if entry_price > 0:
        price_diff = mark_price - entry_price if side == 'LONG' else entry_price - mark_price
        roi_pct = (price_diff / entry_price) * 100 * leverage
    else:
        roi_pct = 0
    
    print("=" * 80)
    print(f"ПОЗИЦИЯ: {symbol} {side}")
    print("=" * 80)
    print(f"  Entry Price: ${entry_price:.2f}")
    print(f"  Mark Price:  ${mark_price:.2f}")
    print(f"  Quantity:    {quantity:.6f}")
    print(f"  Leverage:    {leverage}x")
    print(f"  Unrealized PNL: ${unrealized_pnl:.2f}")
    print(f"  ROI:         {roi_pct:.2f}%")
    
    # Рассчитываем ликвидационную цену
    # Для LONG: liq = entry - (entry / leverage)
    # Для SHORT: liq = entry + (entry / leverage)
    if side == 'LONG':
        liq_price = entry_price * (1 - 1.0 / leverage)
    else:
        liq_price = entry_price * (1 + 1.0 / leverage)
    
    print(f"  Liquidation Price: ${liq_price:.2f}")
    
    # Рассчитываем цену где ROI = -85%
    # ROI = ((price - entry) / entry) * 100 * leverage = -85
    # (price - entry) / entry = -85 / (100 * leverage)
    # price = entry * (1 - 85 / (100 * leverage))
    if side == 'LONG':
        emergency_stop_price = entry_price * (1 - 85.0 / (100.0 * leverage))
    else:
        emergency_stop_price = entry_price * (1 + 85.0 / (100.0 * leverage))
    
    print(f"  Emergency Stop Price (ROI=-85%): ${emergency_stop_price:.2f}")
    
    # Проверяем ордера для этого символа
    symbol_orders = orders_by_symbol.get(symbol, [])
    print(f"\n  Ордеров для {symbol}: {len(symbol_orders)}")
    
    if symbol_orders:
        for order in symbol_orders:
            order_type = order.get('type', 'UNKNOWN')
            order_side = order.get('side', 'UNKNOWN')
            order_id = order.get('orderId', '')
            status = order.get('status', 'UNKNOWN')
            price = float(order.get('price', 0))
            stop_price = float(order.get('stopPrice', 0))
            quantity = float(order.get('origQty', 0))
            
            print(f"\n    Order ID: {order_id}")
            print(f"       Type: {order_type}")
            print(f"       Side: {order_side}")
            print(f"       Status: {status}")
            print(f"       Quantity: {quantity:.6f}")
            
            if stop_price > 0:
                print(f"       Stop Price: ${stop_price:.2f}")
                if side == 'LONG':
                    # Для LONG позиции
                    if order_side == 'SELL':
                        # Это стоп-ордер на закрытие LONG
                        stop_roi = ((stop_price - entry_price) / entry_price) * 100 * leverage
                        print(f"       Stop ROI: {stop_roi:.2f}%")
                        print(f"       Distance from Entry: {((stop_price - entry_price) / entry_price) * 100:.2f}%")
                        print(f"       Distance from Liq: {((stop_price - liq_price) / liq_price) * 100:.2f}%")
                        print(f"       Distance from Emergency Stop: {((stop_price - emergency_stop_price) / emergency_stop_price) * 100:.2f}%")
                        
                        # Определяем тип стопа
                        if abs(stop_roi - (-85.0)) < 1.0:
                            print(f"       [СТРАХОВОЧНЫЙ СТОП] Emergency Stop @ ROI = -85%")
                        elif stop_roi > 0:
                            print(f"       [СТОП-ЛОСС] Progressive Stop @ ROI = +{stop_roi:.2f}%")
                        else:
                            print(f"       [НЕИЗВЕСТНЫЙ ТИП СТОПА]")
            
            if price > 0:
                print(f"       Limit Price: ${price:.2f}")
            
            print()
    else:
        print(f"    [НЕТ ОРДЕРОВ] Нет открытых ордеров для {symbol}")
    
    print()

print("=" * 80)
print("АНАЛИЗ ЗАВЕРШЕН")
print("=" * 80)

