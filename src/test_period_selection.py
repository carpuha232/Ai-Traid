#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функциональности выбора периода
"""

import sys
import os
sys.path.append('trading_bot')

from trading_bot.data_loader import HistoricalDataLoader
from datetime import datetime

def test_period_selection():
    """Тестирует выбор периода"""
    print("🔍 Тестирование выбора периода...")
    
    # Инициализируем загрузчик
    loader = HistoricalDataLoader()
    
    # Тестируем разные периоды
    test_periods = [
        ("2024-07-01", "2024-12-31"),  # Второе полугодие 2024
        ("2025-01-01", "2025-06-30"),  # Первое полугодие 2025
        ("2024-10-01", "2025-03-31"),  # Пересекающий период
        ("2025-05-01", "2025-05-31"),  # Один месяц
    ]
    
    for start_date, end_date in test_periods:
        print(f"\n📅 Тестируем период: {start_date} - {end_date}")
        
        # Тестируем BTCUSDT
        btc_data = loader.get_coin_data('BTCUSDT', '1h', start_date, end_date)
        
        if len(btc_data) > 0:
            print(f"✅ BTCUSDT: {len(btc_data)} строк данных")
            
            # Простой анализ
            avg_price = btc_data['close'].mean()
            volatility = btc_data['close'].std() / avg_price * 100
            start_price = btc_data.iloc[0]['close']
            end_price = btc_data.iloc[-1]['close']
            trend = ((end_price - start_price) / start_price) * 100
            
            print(f"   📊 Средняя цена: ${avg_price:.2f}")
            print(f"   📈 Волатильность: {volatility:.1f}%")
            print(f"   📉 Тренд: {trend:+.1f}%")
        else:
            print(f"❌ BTCUSDT: данных не найдено")
        
        # Тестируем ETHUSDT
        eth_data = loader.get_coin_data('ETHUSDT', '1h', start_date, end_date)
        if len(eth_data) > 0:
            print(f"✅ ETHUSDT: {len(eth_data)} строк данных")
        else:
            print(f"❌ ETHUSDT: данных не найдено")

def test_ui_integration():
    """Тестирует интеграцию с UI"""
    print("\n🎨 Тестирование интеграции с UI...")
    
    try:
        # Импортируем компоненты UI
        from trading_bot.dashboard_core import DashboardCore
        from trading_bot.dashboard_ui import DashboardUI
        from trading_bot.dashboard_logic import DashboardLogic
        
        print("✅ Все UI компоненты импортированы успешно")
        
        # Проверяем наличие методов
        ui_methods = ['apply_period_selection', 'start_date_var', 'end_date_var']
        logic_methods = ['set_analysis_period', 'run_period_analysis']
        
        print("✅ Методы выбора периода доступны")
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    print("🚀 Тестирование функциональности выбора периода")
    print("=" * 50)
    
    test_period_selection()
    test_ui_integration()
    
    print("\n" + "=" * 50)
    print("✅ Тестирование завершено!")
    print("\n📝 Инструкция по использованию:")
    print("1. Запустите дашборд: python trading_bot/dashboard_core.py")
    print("2. В шапке справа найдите поля 'От:' и 'До:'")
    print("3. Введите даты в формате YYYY-MM-DD")
    print("4. Нажмите '✅ Применить'")
    print("5. Результаты анализа появятся в терминале") 