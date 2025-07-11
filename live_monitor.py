"""
📊 Живой мониторинг обучения в реальном времени
"""

import json
import time
import os
from datetime import datetime

def live_monitor():
    """Живой мониторинг обучения"""
    
    print("📊 ЖИВОЙ МОНИТОРИНГ ОБУЧЕНИЯ")
    print("=" * 50)
    print("🔄 Нажмите Ctrl+C для остановки")
    print("=" * 50)
    
    last_file_size = 0
    last_check_time = time.time()
    cycle_count = 0
    
    try:
        while True:
            current_time = time.time()
            
            # Проверяем изменения в файле состояния
            if os.path.exists('progressive_learning_state.json'):
                current_file_size = os.path.getsize('progressive_learning_state.json')
                file_modified = os.path.getmtime('progressive_learning_state.json')
                
                if current_file_size != last_file_size:
                    cycle_count += 1
                    print(f"\n🔄 ЦИКЛ {cycle_count} - {datetime.fromtimestamp(file_modified).strftime('%H:%M:%S')}")
                    print("=" * 50)
                    
                    # Пытаемся прочитать последние данные
                    try:
                        with open('final_neural_network_state.json', 'r') as f:
                            nn_state = json.load(f)
                        
                        learning_stats = nn_state.get('learning_stats', {})
                        win_rate_history = learning_stats.get('win_rate_history', [])
                        capital_history = learning_stats.get('capital_history', [])
                        experience_memory = nn_state.get('experience_memory', [])
                        
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
                        print(f"🧠 Память опыта: {len(experience_memory)} записей")
                        
                        # Анализ прогресса
                        if current_win_rate >= 0.65:
                            print("🏆 ДОСТИГНУТ ЦЕЛЕВОЙ ВИНРЕЙТ 65%+!")
                        elif current_win_rate >= 0.60:
                            print("🎯 Близко к цели! Винрейт 60%+")
                        elif current_win_rate >= 0.55:
                            print("📈 Хороший прогресс! Винрейт 55%+")
                        else:
                            print("🔄 Продолжается обучение...")
                        
                        # Анализ последних сделок
                        if experience_memory:
                            recent_trades = experience_memory[-3:]  # Последние 3 сделки
                            print(f"\n📊 Последние сделки:")
                            for i, trade in enumerate(recent_trades, 1):
                                decision = trade['decision']
                                result = trade['result']
                                profit = result['profit']
                                action = decision['action'].upper()
                                timeframe = decision['timeframe']
                                leverage = decision['leverage']
                                
                                if profit > 0:
                                    print(f"   ✅ {action} {timeframe}: +${profit:.2f} ({leverage}x)")
                                else:
                                    print(f"   ❌ {action} {timeframe}: ${profit:.2f} ({leverage}x)")
                        
                        last_file_size = current_file_size
                        
                    except Exception as e:
                        print(f"⚠️ Ошибка чтения данных: {e}")
                
                # Показываем статус каждые 60 секунд
                if current_time - last_check_time >= 60:
                    print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - Обучение активно...")
                    last_check_time = current_time
            
            time.sleep(2)  # Проверяем каждые 2 секунды
            
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
            print(f"🔄 Всего циклов мониторинга: {cycle_count}")
            
        except Exception as e:
            print(f"❌ Ошибка при чтении финальной статистики: {e}")

if __name__ == "__main__":
    live_monitor() 