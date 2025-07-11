"""
🚀 Главный файл для запуска прогрессивного обучения автономной нейросети
Запускает обучение по таймфреймам с целью винрейта 70%+ на каждом
"""

import sys
import os
import time
from datetime import datetime

# Добавляем текущую папку в путь для импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from learning_engine import ProgressiveLearningEngine
from data_loader import RawDataLoader

def main():
    """Главная функция запуска прогрессивного обучения"""
    
    print("🧠 ПРОГРЕССИВНОЕ ОБУЧЕНИЕ АВТОНОМНОЙ НЕЙРОСЕТИ")
    print("=" * 60)
    print("🎯 Цель: винрейт 70%+ на каждом таймфрейме")
    print("📈 Прогрессия: 1M → 1w → 1d → 12h → 8h → 6h → 4h → 2h → 1h → 30m → 15m → 5m → 3m → 1m")
    print("🔄 Перезапуск: если не удается достичь 70%+ винрейта")
    print("📊 Обучение только на сырых данных (цена, объем, время)")
    print("🚫 Без технических индикаторов (RSI, MA, MACD и т.д.)")
    print("=" * 60)
    
    # Проверяем наличие данных
    data_loader = RawDataLoader()
    available_data = data_loader.scan_available_data()
    
    if not available_data:
        print("❌ Нет доступных данных для обучения!")
        print("📁 Убедитесь, что в папке .venv/data/historical есть ZIP файлы с данными")
        return
    
    print(f"✅ Найдено данных: {len(available_data)} комбинаций")
    
    # Создаем прогрессивный движок обучения
    learning_engine = ProgressiveLearningEngine(initial_capital=100.0)
    
    # Запускаем прогрессивное обучение
    try:
        start_time = time.time()
        learning_engine.start_progressive_learning()
        end_time = time.time()
        
        # Финальная статистика
        summary = learning_engine.get_learning_summary()
        
        print(f"\n🏁 ПРОГРЕССИВНОЕ ОБУЧЕНИЕ ЗАВЕРШЕНО")
        print("=" * 60)
        print(f"⏱️ Время обучения: {(end_time - start_time) / 60:.1f} минут")
        print(f"📊 Текущий таймфрейм: {summary['current_timeframe']}")
        print(f"🔄 Завершено циклов: {summary['current_cycle']}")
        print(f"💰 Финальный капитал: ${summary['current_capital']:.2f}")
        print(f"📈 Общая прибыль: ${summary['current_profit']:.2f}")
        
        if summary['timeframe_history']:
            print(f"\n✅ УСПЕШНО ПРОЙДЕННЫЕ ТАЙМФРЕЙМЫ:")
            for record in summary['timeframe_history']:
                print(f"   📊 {record['timeframe']}: цикл {record['cycle']}, капитал ${record['capital']:.2f}")
        
        # Проверяем завершение всех таймфреймов
        if summary['current_timeframe_index'] >= len(learning_engine.timeframe_progression):
            print(f"\n🏆 ВСЕ ТАЙМФРЕЙМЫ ПРОЙДЕНЫ! ОБУЧЕНИЕ ПОЛНОСТЬЮ ЗАВЕРШЕНО!")
        else:
            print(f"\n⏸️ Обучение остановлено на таймфрейме {summary['current_timeframe']}")
            print(f"📊 Прогресс: {summary['current_timeframe_index'] + 1}/{len(learning_engine.timeframe_progression)}")
        
    except KeyboardInterrupt:
        print(f"\n⏸️ Прогрессивное обучение прервано пользователем")
        summary = learning_engine.get_learning_summary()
        print(f"📊 Текущий таймфрейм: {summary['current_timeframe']}")
        print(f"💰 Текущий капитал: ${summary['current_capital']:.2f}")
        print(f"📈 Текущая прибыль: ${summary['current_profit']:.2f}")
        
    except Exception as e:
        print(f"\n❌ Ошибка во время прогрессивного обучения: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 