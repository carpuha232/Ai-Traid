"""
📊 Детальный анализ прогресса обучения
"""

import json
import os
from datetime import datetime

def detailed_progress_analysis():
    """Детальный анализ прогресса обучения"""
    
    print("📊 ДЕТАЛЬНЫЙ АНАЛИЗ ПРОГРЕССА ОБУЧЕНИЯ")
    print("=" * 60)
    
    # Проверяем файлы состояния
    state_files = {
        'progressive_learning_state.json': 'Основное состояние обучения',
        'learning_engine_state.json': 'Состояние движка обучения',
        'final_neural_network_state.json': 'Состояние нейросети'
    }
    
    print("📁 АНАЛИЗ ФАЙЛОВ СОСТОЯНИЯ:")
    for file_name, description in state_files.items():
        if os.path.exists(file_name):
            file_size = os.path.getsize(file_name)
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_name))
            print(f"✅ {file_name}: {file_size:,} байт")
            print(f"   📝 {description}")
            print(f"   🕒 Изменен: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"❌ {file_name}: файл не найден")
        print()
    
    print("=" * 60)
    print("📊 АНАЛИЗ ДАННЫХ:")
    
    # Проверяем данные
    data_dir = '.venv/data/historical'
    if os.path.exists(data_dir):
        timeframes = [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))]
        print(f"📈 Найдено таймфреймов: {len(timeframes)}")
        
        total_files = 0
        for tf in timeframes:
            tf_path = os.path.join(data_dir, tf)
            files = [f for f in os.listdir(tf_path) if f.endswith('.csv')]
            total_files += len(files)
            print(f"   📊 {tf}: {len(files)} файлов")
        
        print(f"📁 Всего файлов данных: {total_files}")
    else:
        print("❌ Папка с данными не найдена")
    
    print("\n" + "=" * 60)
    print("🧠 АНАЛИЗ НЕЙРОСЕТИ:")
    
    try:
        with open('final_neural_network_state.json', 'r') as f:
            nn_state = json.load(f)
        
        learning_stats = nn_state.get('learning_stats', {})
        experience_memory = nn_state.get('experience_memory', [])
        
        print(f"📈 Завершено циклов: {learning_stats.get('cycles_completed', 0)}")
        print(f"💰 Общая прибыль: ${learning_stats.get('total_profit', 0):.2f}")
        print(f"📉 Максимальная просадка: {learning_stats.get('max_drawdown', 0):.1%}")
        
        win_rate_history = learning_stats.get('win_rate_history', [])
        if win_rate_history:
            current_win_rate = win_rate_history[-1]
            avg_win_rate = sum(win_rate_history) / len(win_rate_history)
            print(f"🎯 Текущий винрейт: {current_win_rate:.1%}")
            print(f"📊 Средний винрейт: {avg_win_rate:.1%}")
            print(f"📈 Всего измерений винрейта: {len(win_rate_history)}")
        
        capital_history = learning_stats.get('capital_history', [])
        if capital_history:
            current_capital = capital_history[-1]
            initial_capital = capital_history[0]
            print(f"💰 Текущий капитал: ${current_capital:.2f}")
            print(f"📈 Изменение капитала: ${current_capital - initial_capital:.2f}")
        
        print(f"🧠 Размер памяти опыта: {len(experience_memory)} записей")
        
        # Анализ последних сделок
        if experience_memory:
            print(f"\n📊 АНАЛИЗ ПОСЛЕДНИХ СДЕЛОК:")
            recent_trades = experience_memory[-5:]  # Последние 5 сделок
            for i, trade in enumerate(recent_trades, 1):
                decision = trade['decision']
                result = trade['result']
                print(f"   {i}. {decision['action'].upper()} {decision['timeframe']}: "
                      f"${result['profit']:.2f} (плечо {decision['leverage']}x)")
        
    except Exception as e:
        print(f"❌ Ошибка при анализе нейросети: {e}")
    
    print("\n" + "=" * 60)
    print("⚙️ АНАЛИЗ ДВИЖКА ОБУЧЕНИЯ:")
    
    try:
        with open('learning_engine_state.json', 'r') as f:
            engine_state = json.load(f)
        
        print(f"🔄 Текущий цикл: {engine_state.get('current_cycle', 0)}")
        print(f"📊 Текущий таймфрейм: {engine_state.get('current_timeframe', 'N/A')}")
        print(f"📈 Индекс таймфрейма: {engine_state.get('current_timeframe_index', 0)}")
        print(f"🔄 Текущий перезапуск: {engine_state.get('current_restart', 0)}")
        
        timeframe_history = engine_state.get('timeframe_history', [])
        if timeframe_history:
            print(f"✅ Успешно пройденные таймфреймы: {len(timeframe_history)}")
            for record in timeframe_history[-3:]:
                print(f"   📊 {record.get('timeframe', 'N/A')}: цикл {record.get('cycle', 0)}, "
                      f"капитал ${record.get('capital', 0):.2f}")
        
    except Exception as e:
        print(f"❌ Ошибка при анализе движка: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 ВЫВОДЫ:")
    
    # Анализируем прогресс
    if os.path.exists('progressive_learning_state.json'):
        file_size = os.path.getsize('progressive_learning_state.json')
        if file_size > 1000000:  # Больше 1MB
            print("✅ Обучение активно продолжается (большой файл состояния)")
        else:
            print("⚠️ Файл состояния небольшой - возможно, обучение недавно началось")
    
    try:
        with open('final_neural_network_state.json', 'r') as f:
            nn_state = json.load(f)
        
        learning_stats = nn_state.get('learning_stats', {})
        win_rate_history = learning_stats.get('win_rate_history', [])
        
        if win_rate_history:
            current_win_rate = win_rate_history[-1]
            if current_win_rate >= 0.65:
                print("🏆 ДОСТИГНУТ ЦЕЛЕВОЙ ВИНРЕЙТ 65%+!")
            elif current_win_rate >= 0.60:
                print("🎯 Близко к цели! Винрейт 60%+")
            elif current_win_rate >= 0.55:
                print("📈 Хороший прогресс! Винрейт 55%+")
            else:
                print("🔄 Продолжается обучение для достижения цели")
        
        total_profit = learning_stats.get('total_profit', 0)
        if total_profit > 0:
            print("✅ Бот показывает положительную прибыль!")
        elif total_profit > -50:
            print("📈 Значительное улучшение результатов!")
        else:
            print("⚠️ Бот пока в убытке, но есть прогресс")
            
    except Exception as e:
        print(f"❌ Ошибка при анализе: {e}")

if __name__ == "__main__":
    detailed_progress_analysis() 