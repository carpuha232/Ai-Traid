#!/usr/bin/env python3
"""
Тестовый скрипт для проверки скачанных исторических данных
"""

import pandas as pd
from trading_bot.data_loader import HistoricalDataLoader
import matplotlib.pyplot as plt
from datetime import datetime

def test_data_loader():
    """Тестирует загрузчик данных"""
    print("🔍 Тестирование загрузчика данных...")
    
    loader = HistoricalDataLoader()
    
    # Получаем список доступных монет и таймфреймов
    coins = loader.get_available_coins()
    timeframes = loader.get_available_timeframes()
    
    print(f"📊 Доступные монеты: {len(coins)}")
    print(f"📈 Доступные таймфреймы: {timeframes}")
    
    # Тестируем загрузку данных BTCUSDT
    print("\n🔍 Тестирование загрузки BTCUSDT...")
    
    # Загружаем данные за последний месяц
    btc_1h = loader.get_coin_data('BTCUSDT', '1h', start_date='2025-05-01')
    print(f"BTCUSDT 1h (май 2025): {len(btc_1h)} строк")
    
    if len(btc_1h) > 0:
        print(f"Период: {btc_1h['open_time'].min()} - {btc_1h['open_time'].max()}")
        print(f"Цена: {btc_1h['close'].min():.2f} - {btc_1h['close'].max():.2f}")
        print(f"Объем: {btc_1h['volume'].sum():,.0f}")
    
    # Загружаем данные за весь период
    btc_all = loader.get_coin_data('BTCUSDT', '1h')
    print(f"BTCUSDT 1h (весь период): {len(btc_all)} строк")
    
    if len(btc_all) > 0:
        print(f"Период: {btc_all['open_time'].min()} - {btc_all['open_time'].max()}")
        print(f"Цена: {btc_all['close'].min():.2f} - {btc_all['close'].max():.2f}")
    
    # Тестируем разные таймфреймы
    print("\n🔍 Тестирование разных таймфреймов...")
    
    for tf in ['5m', '15m', '30m', '1h', '2h', '4h']:
        data = loader.get_coin_data('BTCUSDT', tf, start_date='2025-05-01')
        print(f"BTCUSDT {tf}: {len(data)} строк")
    
    # Тестируем разные монеты
    print("\n🔍 Тестирование разных монет...")
    
    test_coins = ['ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
    for coin in test_coins:
        data = loader.get_coin_data(coin, '1h', start_date='2025-05-01')
        print(f"{coin} 1h: {len(data)} строк")
    
    return btc_all

def analyze_data_quality(df):
    """Анализирует качество данных"""
    print("\n🔍 Анализ качества данных...")
    
    if len(df) == 0:
        print("❌ Нет данных для анализа")
        return
    
    # Проверяем на пропущенные значения
    missing = df.isnull().sum()
    print(f"Пропущенные значения:\n{missing}")
    
    # Проверяем на дубликаты
    duplicates = df.duplicated().sum()
    print(f"Дубликаты: {duplicates}")
    
    # Проверяем временные промежутки
    df_sorted = df.sort_values('open_time')
    time_diff = df_sorted['open_time'].diff()
    print(f"Средний временной промежуток: {time_diff.mean()}")
    print(f"Мин. временной промежуток: {time_diff.min()}")
    print(f"Макс. временной промежуток: {time_diff.max()}")
    
    # Проверяем аномалии в ценах
    price_stats = df[['open', 'high', 'low', 'close']].describe()
    print(f"\nСтатистика цен:\n{price_stats}")

def create_sample_chart(df):
    """Создает примерный график"""
    if len(df) == 0:
        print("❌ Нет данных для графика")
        return
    
    print("\n📈 Создание графика...")
    
    # Берем последние 100 точек для графика
    df_chart = df.tail(100).copy()
    
    plt.figure(figsize=(12, 6))
    plt.plot(df_chart['open_time'], df_chart['close'], label='Close Price')
    plt.title('BTCUSDT Price Chart (Last 100 points)')
    plt.xlabel('Time')
    plt.ylabel('Price (USDT)')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Сохраняем график
    plt.savefig('btc_sample_chart.png', dpi=300, bbox_inches='tight')
    print("✅ График сохранен как 'btc_sample_chart.png'")
    plt.close()

def main():
    """Основная функция тестирования"""
    print("🚀 Начинаем тестирование скачанных данных")
    print("=" * 50)
    
    try:
        # Тестируем загрузчик
        btc_data = test_data_loader()
        
        # Анализируем качество данных
        analyze_data_quality(btc_data)
        
        # Создаем график
        create_sample_chart(btc_data)
        
        print("\n✅ Тестирование завершено успешно!")
        print("📁 Данные готовы для использования в торговом боте")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 