"""
📊 Скрипт для проверки текущего прогресса обучения бота
"""

import json
import os
from datetime import datetime

def check_learning_progress():
    """Проверяет текущий прогресс обучения"""
    
    print("📊 ПРОВЕРКА ПРОГРЕССА ОБУЧЕНИЯ БОТА")
    print("=" * 50)
    
    # Проверяем файлы состояния
    state_files = [
        'progressive_learning_state.json',
        'learning_engine_state.json', 
        'final_neural_network_state.json'
    ]
    
    for file_name in state_files:
        if os.path.exists(file_name):
            file_size = os.path.getsize(file_name)
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_name))
            print(f"✅ {file_name}: {file_size:,} байт, изменен: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"❌ {file_name}: файл не найден")
    
    print("\n" + "=" * 50)
    
    # Пытаемся загрузить состояние нейросети
    try:
        with open('final_neural_network_state.json', 'r') as f:
            nn_state = json.load(f)
        
        learning_stats = nn_state.get('learning_stats', {})
        
        print("🧠 СОСТОЯНИЕ НЕЙРОСЕТИ:")
        print(f"📈 Завершено циклов: {learning_stats.get('cycles_completed', 0)}")
        print(f"💰 Общая прибыль: ${learning_stats.get('total_profit', 0):.2f}")
        print(f"📉 Максимальная просадка: {learning_stats.get('max_drawdown', 0):.1%}")
        
        # История винрейта
        win_rate_history = learning_stats.get('win_rate_history', [])
        if win_rate_history:
            current_win_rate = win_rate_history[-1]
            avg_win_rate = sum(win_rate_history) / len(win_rate_history)
            print(f"🎯 Текущий винрейт: {current_win_rate:.1%}")
            print(f"📊 Средний винрейт: {avg_win_rate:.1%}")
            print(f"📈 Всего измерений винрейта: {len(win_rate_history)}")
        
        # История капитала
        capital_history = learning_stats.get('capital_history', [])
        if capital_history:
            current_capital = capital_history[-1]
            initial_capital = capital_history[0]
            print(f"💰 Текущий капитал: ${current_capital:.2f}")
            print(f"📈 Изменение капитала: ${current_capital - initial_capital:.2f}")
            print(f"📊 Всего измерений капитала: {len(capital_history)}")
        
        # Память опыта
        experience_memory = nn_state.get('experience_memory', [])
        print(f"🧠 Размер памяти опыта: {len(experience_memory)} записей")
        
    except Exception as e:
        print(f"❌ Ошибка при чтении состояния нейросети: {e}")
    
    print("\n" + "=" * 50)
    
    # Пытаемся загрузить состояние движка обучения
    try:
        with open('learning_engine_state.json', 'r') as f:
            engine_state = json.load(f)
        
        print("⚙️ СОСТОЯНИЕ ДВИЖКА ОБУЧЕНИЯ:")
        print(f"🔄 Текущий цикл: {engine_state.get('current_cycle', 0)}")
        print(f"📊 Текущий таймфрейм: {engine_state.get('current_timeframe', 'N/A')}")
        print(f"📈 Индекс таймфрейма: {engine_state.get('current_timeframe_index', 0)}")
        print(f"🔄 Текущий перезапуск: {engine_state.get('current_restart', 0)}")
        
        # История таймфреймов
        timeframe_history = engine_state.get('timeframe_history', [])
        if timeframe_history:
            print(f"✅ Успешно пройденные таймфреймы: {len(timeframe_history)}")
            for record in timeframe_history[-3:]:  # Последние 3
                print(f"   📊 {record.get('timeframe', 'N/A')}: цикл {record.get('cycle', 0)}, капитал ${record.get('capital', 0):.2f}")
        
    except Exception as e:
        print(f"❌ Ошибка при чтении состояния движка: {e}")
    
    print("\n" + "=" * 50)
    
    # Проверяем данные
    data_dir = '.venv/data/historical'
    if os.path.exists(data_dir):
        data_files = [f for f in os.listdir(data_dir) if f.endswith('.zip')]
        print(f"📁 Найдено файлов данных: {len(data_files)}")
        if data_files:
            print("📊 Примеры файлов:")
            for file in data_files[:5]:
                print(f"   📄 {file}")
    else:
        print("❌ Папка с данными не найдена")

if __name__ == "__main__":
    check_learning_progress() 