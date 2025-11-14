#!/usr/bin/env python3
import json

with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

pairs = config['signals']['pairs']
max_positions = config['account']['max_positions']

print(f"Всего пар в списке: {len(pairs)}")
print(f"Максимум позиций одновременно: {max_positions}")
print(f"\nСписок торговых пар:")
for i, pair in enumerate(pairs, 1):
    print(f"  {i}. {pair}")

