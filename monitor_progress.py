"""
📊 Мониторинг прогресса обучения в реальном времени
"""

import json
import time
import os
from datetime import datetime

def monitor_learning_progress():
    """Мониторит прогресс обучения в реальном времени"""
    
    print("📊 МОНИТОРИНГ ПРОГРЕССА ОБУЧЕНИЯ")
    print("=" * 50)
    print("🔄 Нажмите Ctrl+C для остановки мониторинга")
    print("=" * 50)
    
    last_file_size = 0
    last_check_time = time.time()
    
    try:
        while True:
            current_time = time.time()
            
            # Проверяем изменения в файле состояния
            if os.path.exists('progressive_learning_state.json'):
                current_file_size = os.path.getsize('progressive_learning_state.json')
                file_modified = os.path.getmtime('progressive_learning_state.json')
                
                if current_file_size != last_file_size:
                    print(f"\n🔄 ОБНОВЛЕНИЕ ОБУЧЕНИЯ - {datetime.fromtimestamp(file_modified).strftime('%H:%M:%S')}")
                    print("=" * 50)
                    
                    # Пытаемся прочитать последние данные
                    try:
                        with open('final_neural_network_state.json', 'r') as f:
                            nn_state = json.load(f)
                        
                        learning_stats = nn_state.get('learning_stats', {})
                        win_rate_history = learning_stats.get('win_rate_history', [])
                        capital_history = learning_stats.get('capital_history', [])
                        
                        if win_rate_history:
                            current_win_rate = win_rate_history[-1]
                            avg_win_rate = sum(win_rate_history) / len(win_rate_history)
                            print(f"🎯 Текущий винрейт: {current_win_rate:.1%}")
                            print(f"📊 Средний винрейт: {avg_win_rate:.1%}")
                            print(f"📈 Всего измерений: {len(win_rate_history)}")
                        
                        if capital_history:
                            current_capital = capital_history[-1]
                            initial_capital = capital_history[0]
                            total_change = current_capital - initial_capital
                            print(f"💰 Текущий капитал: ${current_capital:.2f}")
                            print(f"📈 Изменение: ${total_change:.2f}")
                        
                        total_profit = learning_stats.get('total_profit', 0)
                        print(f"💹 Общая прибыль: ${total_profit:.2f}")
                        
                        # Анализ прогресса
                        if current_win_rate >= 0.65:
                            print("🏆 ДОСТИГНУТ ЦЕЛЕВОЙ ВИНРЕЙТ 65%+!")
                        elif current_win_rate >= 0.60:
                            print("🎯 Близко к цели! Винрейт 60%+")
                        elif current_win_rate >= 0.55:
                            print("📈 Хороший прогресс! Винрейт 55%+")
                        else:
                            print("🔄 Продолжается обучение...")
                        
                        last_file_size = current_file_size
                        
                    except Exception as e:
                        print(f"⚠️ Ошибка чтения данных: {e}")
                
                # Показываем статус каждые 30 секунд
                if current_time - last_check_time >= 30:
                    print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - Обучение активно...")
                    last_check_time = current_time
            
            time.sleep(5)  # Проверяем каждые 5 секунд
            
    except KeyboardInterrupt:
        print(f"\n⏸️ Мониторинг остановлен пользователем")
        print("📊 Финальная статистика:")
        
        try:
            with open('final_neural_network_state.json', 'r') as f:
                nn_state = json.load(f)
            
            learning_stats = nn_state.get('learning_stats', {})
            win_rate_history = learning_stats.get('win_rate_history', [])
            capital_history = learning_stats.get('capital_history', [])
            
            if win_rate_history:
                current_win_rate = win_rate_history[-1]
                print(f"🎯 Финальный винрейт: {current_win_rate:.1%}")
            
            if capital_history:
                current_capital = capital_history[-1]
                print(f"💰 Финальный капитал: ${current_capital:.2f}")
            
            total_profit = learning_stats.get('total_profit', 0)
            print(f"💹 Финальная прибыль: ${total_profit:.2f}")
            
        except Exception as e:
            print(f"❌ Ошибка при чтении финальной статистики: {e}")

if __name__ == "__main__":
    monitor_learning_progress() 