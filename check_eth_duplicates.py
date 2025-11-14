#!/usr/bin/env python3
"""Проверка дублей ордеров для ETHUSDT"""

import json
from binance.client import Client

# Загружаем конфиг
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

api_key = config['api']['key']
api_secret = config['api']['secret']

client = Client(api_key, api_secret)

print("=" * 80)
print("ПРОВЕРКА ДУБЛЕЙ ОРДЕРОВ ДЛЯ ETHUSDT")
print("=" * 80)

# Получаем все открытые ордера для ETHUSDT
orders = client.futures_get_open_orders(symbol='ETHUSDT', recvWindow=60000)
print(f"\nВсего открытых ордеров для ETHUSDT: {len(orders)}\n")

if len(orders) > 1:
    print("⚠️ ОБНАРУЖЕНЫ ДУБЛИ!")
    print("=" * 80)
    
    # Группируем по типу и цене
    orders_by_type_price = {}
    for order in orders:
        order_type = order.get('type', 'UNKNOWN')
        order_side = order.get('side', 'UNKNOWN')
        price = float(order.get('price', 0))
        key = f"{order_type}_{order_side}_{price:.2f}"
        
        if key not in orders_by_type_price:
            orders_by_type_price[key] = []
        orders_by_type_price[key].append(order)
    
    # Показываем дубли
    for key, order_list in orders_by_type_price.items():
        if len(order_list) > 1:
            print(f"\n🔴 ДУБЛИ: {len(order_list)} ордеров с одинаковыми параметрами:")
            print(f"   Тип: {order_list[0].get('type')}, Сторона: {order_list[0].get('side')}, Цена: ${float(order_list[0].get('price', 0)):.2f}")
            for order in order_list:
                print(f"   - Order ID: {order.get('orderId')}, Status: {order.get('status')}, Qty: {float(order.get('origQty', 0)):.6f}")
    
    print("\n" + "=" * 80)
    print("ВСЕ ОРДЕРА:")
    print("=" * 80)
    
for i, order in enumerate(orders, 1):
    print(f"\n{i}. Order ID: {order.get('orderId')}")
    print(f"   Type: {order.get('type')}")
    print(f"   Side: {order.get('side')}")
    print(f"   Status: {order.get('status')}")
    print(f"   Price: ${float(order.get('price', 0)):.2f}")
    print(f"   Quantity: {float(order.get('origQty', 0)):.6f}")
    print(f"   Time: {order.get('time', 'N/A')}")

print("\n" + "=" * 80)

