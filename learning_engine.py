"""
🧠 Движок прогрессивного обучения автономной нейросети
Учится на максимальных таймфреймах, достигает 70%+ винрейта, переходит к меньшим
"""

import pandas as pd
import numpy as np
import random
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import os

from neural_network import AutonomousNeuralNetwork
from data_loader import RawDataLoader

class ProgressiveLearningEngine:
    """Движок прогрессивного обучения по таймфреймам"""
    
    def __init__(self, initial_capital: float = 100.0):
        self.neural_network = AutonomousNeuralNetwork(initial_capital)
        self.data_loader = RawDataLoader()
        
        # Комиссии за торговлю фьючерсами Binance
        self.entry_fee = 0.0002  # 0.02% за вход в позицию (maker)
        self.exit_fee = 0.0004   # 0.04% за выход из позиции (taker)
        
        # Прогрессивное обучение по таймфреймам (от большего к меньшему)
        self.timeframe_progression = ['1M', '1w', '1d', '12h', '8h', '6h', '4h', '2h', '1h', '30m', '15m', '5m', '3m', '1m']
        self.current_timeframe_index = 0
        self.current_timeframe = self.timeframe_progression[0]
        
        # Параметры обучения - УЛУЧШЕННАЯ ВЕРСИЯ
        self.learning_config = {
            'target_win_rate': 0.55,  # Целевой винрейт 55%+ (более реалистично)
            'max_drawdown': 0.3,     # Максимальная просадка 30%
            'cycles_per_timeframe': 999,  # Практически бесконечные циклы
            'trades_per_cycle': 50,      # Сделок за цикл
            'max_restarts': 999,         # Практически бесконечные перезапуски
            'evaluation_cycles': 15,     # Оценка каждые 15 циклов (больше времени на стабилизацию)
            'max_cycles_without_improvement': 100  # Больше циклов без улучшений
        }
        
        # Статистика обучения
        self.learning_history = []
        self.timeframe_history = []
        self.current_cycle = 0
        self.current_restart = 0
        self.best_performance = {
            'win_rate': 0.0,
            'total_profit': 0.0,
            'timeframe': '',
            'cycle': 0
        }
        
        # Состояние обучения
        self.is_learning = False
        self.learning_start_time = None
    
    def start_progressive_learning(self):
        """Запуск БЕСКОНЕЧНОГО прогрессивного обучения по таймфреймам"""
        print("🚀 ЗАПУСК БЕСКОНЕЧНОГО ПРОГРЕССИВНОГО ОБУЧЕНИЯ")
        print("=" * 60)
        print("🎯 Цель: винрейт 55%+ на каждом таймфрейме (более реалистично)")
        print("📈 Прогрессия: 1M → 1w → 1d → 12h → 8h → 6h → 4h → 2h → 1h → 30m → 15m → 5m → 3m → 1m")
        print("🔄 БЕСКОНЕЧНОЕ ОБУЧЕНИЕ: бот будет учиться до достижения цели на всех ТФ")
        print("🔄 ЦИКЛИЧНОСТЬ: после прохождения всех ТФ обучение начнется заново")
        print("=" * 60)
        
        # Сканируем доступные данные
        available_data = self.data_loader.scan_available_data()
        if not available_data:
            print("❌ Нет доступных данных для обучения")
            return
        
        print(f"📊 Найдено данных: {len(available_data)} комбинаций")
        
        # Загружаем сохраненное состояние
        self._load_learning_state()
        
        self.is_learning = True
        self.learning_start_time = time.time()
        
        # БЕСКОНЕЧНЫЙ цикл прогрессивного обучения
        iteration = 0
        while True:  # Бесконечный цикл
            iteration += 1
            print(f"\n🔄 ИТЕРАЦИЯ {iteration} БЕСКОНЕЧНОГО ОБУЧЕНИЯ")
            print("=" * 60)
            
            # Проходим все таймфреймы
            while self.current_timeframe_index < len(self.timeframe_progression):
                self.current_timeframe = self.timeframe_progression[self.current_timeframe_index]
                
                print(f"\n🎯 ОБУЧЕНИЕ НА ТАЙМФРЕЙМЕ: {self.current_timeframe}")
                print(f"📊 Прогресс: {self.current_timeframe_index + 1}/{len(self.timeframe_progression)}")
                print(f"🔄 Итерация: {iteration}")
                
                # Обучаемся на текущем таймфрейме (бесконечно до достижения цели)
                success = self._learn_on_timeframe()
                
                if success:
                    print(f"✅ ДОСТИГНУТ ВИНРЕЙТ 55%+ НА {self.current_timeframe}")
                    print(f"🎉 Переход к следующему таймфрейму")
                    
                    # Сохраняем успешный результат
                    self._save_timeframe_success()
                    
                    # Переходим к следующему таймфрейму
                    self.current_timeframe_index += 1
                    self.current_restart = 0
                    
                    if self.current_timeframe_index < len(self.timeframe_progression):
                        print(f"⏭️ Следующий таймфрейм: {self.timeframe_progression[self.current_timeframe_index]}")
                    else:
                        print("🏆 ВСЕ ТАЙМФРЕЙМЫ ПРОЙДЕНЫ В ЭТОЙ ИТЕРАЦИИ!")
                        break
                else:
                    # В новой логике это не должно происходить, но на всякий случай
                    print(f"❌ НЕОЖИДАННО: обучение прервано на {self.current_timeframe}")
                    self.current_restart += 1
                    
                    if self.current_restart >= self.learning_config['max_restarts']:
                        print(f"⚠️ Достигнут лимит перезапусков для {self.current_timeframe}")
                        print(f"🔄 Перезапуск обучения с начала")
                        self._restart_learning()
                    else:
                        print(f"🔄 Перезапуск обучения на {self.current_timeframe}")
                        self._restart_current_timeframe()
                
                # Сохраняем состояние
                self._save_learning_state()
            
            # После прохождения всех таймфреймов - начинаем заново
            print(f"\n🎉 ИТЕРАЦИЯ {iteration} ЗАВЕРШЕНА!")
            print("🔄 НАЧИНАЕМ НОВУЮ ИТЕРАЦИЮ ОБУЧЕНИЯ...")
            
            # Сбрасываем индекс таймфрейма для новой итерации
            self.current_timeframe_index = 0
            self.current_restart = 0
            
            # Сохраняем финальное состояние итерации
            self._save_learning_state()
            
            # Небольшая пауза между итерациями
            print("⏳ Пауза 5 секунд перед новой итерацией...")
            time.sleep(5)
    
    def _learn_on_timeframe(self) -> bool:
        """Обучение на конкретном таймфрейме до достижения 65%+ винрейта и стабильности - БЕСКОНЕЧНОЕ ОБУЧЕНИЕ"""
        timeframe_results = []
        cycles_without_improvement = 0
        best_win_rate = 0.0
        cycle = 0
        
        print(f"🔄 БЕСКОНЕЧНОЕ ОБУЧЕНИЕ НА {self.current_timeframe} ДО ДОСТИЖЕНИЯ 55%+ ВИНРЕЙТА")
        
        while True:  # Бесконечный цикл обучения
            cycle += 1
            self.current_cycle += 1
            print(f"\n🔄 Цикл {cycle} (бесконечное обучение) на {self.current_timeframe}")
            cycle_result = self._execute_timeframe_cycle()
            timeframe_results.append(cycle_result)
            
            # Проверяем прогресс каждые 5 циклов
            if cycle % self.learning_config['evaluation_cycles'] == 0:
                avg_win_rate = self._calculate_average_win_rate(timeframe_results[-self.learning_config['evaluation_cycles']:])
                print(f"📊 Средний винрейт за последние {self.learning_config['evaluation_cycles']} циклов: {avg_win_rate:.1%}")
                print(f"📈 Лучший винрейт на {self.current_timeframe}: {best_win_rate:.1%}")
                
                # Проверяем достижение цели по винрейту
                if avg_win_rate >= self.learning_config['target_win_rate']:
                    # Дополнительная проверка: нет ли перекоса по распределению прибыли
                    last_cycles = timeframe_results[-self.learning_config['evaluation_cycles']:]
                    all_profits = [trade['profit'] for cycle in last_cycles for trade in cycle['trades'] if 'profit' in trade]
                    if len(all_profits) > 2:
                        sorted_profits = sorted(all_profits, reverse=True)
                        top_2_sum = sum(sorted_profits[:2])
                        total_profit = sum(all_profits)
                        if total_profit > 0 and top_2_sum / total_profit > 0.9:
                            print("⚠️ 90% прибыли дают 1-2 сделки — продолжаем обучение для стабильности!")
                            # Не возвращаем False, продолжаем обучение
                        else:
                            print(f"🎯 ДОСТИГНУТ ЦЕЛЕВОЙ ВИНРЕЙТ {avg_win_rate:.1%} >= 55%! Переход к следующему таймфрейму.")
                            return True
                    else:
                        print(f"🎯 ДОСТИГНУТ ЦЕЛЕВОЙ ВИНРЕЙТ {avg_win_rate:.1%} >= 55%! Переход к следующему таймфрейму.")
                        return True
                
                # Проверка на просадку: если баланс вырос, но винрейт низкий — продолжаем обучение
                last_cycle = timeframe_results[-1]
                if last_cycle['end_capital'] > last_cycle['start_capital'] and avg_win_rate < self.learning_config['target_win_rate']:
                    print("⚠️ Баланс вырос, но винрейт низкий — продолжаем обучение для улучшения винрейта!")
                    # Не возвращаем False, продолжаем обучение
                
                # Проверяем улучшение
                if avg_win_rate > best_win_rate:
                    best_win_rate = avg_win_rate
                    cycles_without_improvement = 0
                    print(f"🎉 НОВЫЙ РЕКОРД ВИНРЕЙТА: {best_win_rate:.1%}!")
                else:
                    cycles_without_improvement += 1
                
                # Если нет улучшений очень долго, показываем это, но продолжаем обучение
                if cycles_without_improvement >= self.learning_config['max_cycles_without_improvement']:
                    print(f"⚠️ Нет улучшений {cycles_without_improvement} циклов, но продолжаем обучение...")
                    cycles_without_improvement = 0  # Сбрасываем счетчик, но продолжаем
                
                # Сохраняем состояние каждые 50 циклов
                if cycle % 50 == 0:
                    self._save_learning_state()
                    print(f"💾 Состояние сохранено после {cycle} циклов обучения")
    
    def _execute_timeframe_cycle(self) -> Dict:
        """Выполнение одного цикла обучения на конкретном таймфрейме"""
        
        # 🧠 УЛУЧШЕННАЯ ВЕРСИЯ: НЕ СБРАСЫВАЕМ КАПИТАЛ КАЖДЫЙ ЦИКЛ
        # Сброс только при достижении цели или каждые 100 циклов
        if self.current_cycle % 100 == 0:
            self.neural_network.current_capital = 100.0
            print(f"   💰 Сброс капитала до $100 (каждые 100 циклов)")
        else:
            print(f"   💰 Текущий капитал: ${self.neural_network.current_capital:.2f}")
        
        cycle_results = {
            'cycle': self.current_cycle,
            'timeframe': self.current_timeframe,
            'trades': [],
            'total_profit': 0.0,
            'win_count': 0,
            'loss_count': 0,
            'start_capital': self.neural_network.current_capital
        }
        
        # Получаем список доступных символов
        symbols = self.data_loader.get_all_symbols()
        
        print(f"   📊 Капитал в начале цикла: ${self.neural_network.current_capital:.2f}")
        print(f"   🎯 Сделки на {self.current_timeframe}:")
        
        # Выполняем сделки только на текущем таймфрейме
        for trade_num in range(self.learning_config['trades_per_cycle']):
            symbol = random.choice(symbols)
            
            try:
                # Получаем данные только для текущего таймфрейма
                market_data = self.data_loader.get_market_data_sample(symbol, self.current_timeframe)
                
                if not market_data:
                    continue
                
                # Нейросеть принимает решение
                decision = self.neural_network.make_autonomous_decision(market_data)
                
                # Симулируем результат сделки
                trade_result = self._simulate_trade(market_data, decision)
                
                # Нейросеть учится на результате
                self.neural_network.learn_from_result(decision, trade_result)
                
                # Сохраняем результат
                trade_info = {
                    'symbol': symbol,
                    'timeframe': self.current_timeframe,
                    'decision': decision,
                    'result': trade_result
                }
                cycle_results['trades'].append(trade_info)
                cycle_results['total_profit'] += trade_result['profit']
                
                if trade_result['profit'] > 0:
                    cycle_results['win_count'] += 1
                else:
                    cycle_results['loss_count'] += 1
                
                # Новый вывод: показываем, был ли exploration
                if decision.get('exploration', False):
                    print(f"      ⚡️ [EXPLORATION] Решение принято случайно!")
                
            except Exception as e:
                print(f"   ❌ Ошибка в сделке {trade_num}: {e}")
                continue
        
        # Обновляем статистику
        cycle_results['end_capital'] = self.neural_network.current_capital
        cycle_results['win_rate'] = cycle_results['win_count'] / self.learning_config['trades_per_cycle'] if self.learning_config['trades_per_cycle'] > 0 else 0.0
        
        print(f"   📈 Капитал в конце цикла: ${self.neural_network.current_capital:.2f}")
        print(f"   💰 Общая прибыль цикла: ${cycle_results['total_profit']:.2f}")
        print(f"   🎯 Винрейт цикла: {cycle_results['win_rate']:.1%} ({cycle_results['win_count']}/{self.learning_config['trades_per_cycle']})")
        
        return cycle_results
    
    def _calculate_average_win_rate(self, results: List[Dict]) -> float:
        """Вычисляет средний винрейт за последние циклы"""
        if not results:
            return 0.0
        
        total_win_rate = sum(r['win_rate'] for r in results)
        return total_win_rate / len(results)
    
    def _simulate_trade(self, market_data: Dict, decision: Dict) -> Dict:
        """Симуляция результата сделки с плавающим размером позиции, плечом, комиссиями и риск-менеджментом 1:2 (R = риск на сделку)"""
        import math
        entry_price = float(market_data.get('close', 0))
        if entry_price <= 0:
            entry_price = 1.0
        action = decision.get('action', 'buy')
        if action not in ['buy', 'sell']:
            action = 'buy'
        # Размер позиции: % от капитала
        position_size = max(0.01, min(1.0, float(decision.get('position_size', 0.05))))
        leverage = max(1, min(20, int(decision.get('leverage', 1))))
        capital = max(1.0, float(self.neural_network.current_capital))
        # Риск на сделку (R): 1% от капитала
        risk_percent = 0.01
        risk_per_trade = capital * risk_percent
        # Стоимость позиции (маржа)
        margin = capital * position_size
        notional = margin * leverage
        # Проверка: не открывать сделку, если маржа > капитал (для безопасности)
        if margin > capital:
            print(f"   ⚠️ Сделка пропущена: margin (${margin:.2f}) > капитал (${capital:.2f})")
            return {'profit': 0.0, 'fees': 0.0, 'exit_reason': 'skipped', 'action': action, 'position_size': position_size, 'leverage': leverage}
        # Кол-во монет
        coins = notional / entry_price
        # Комиссии (Binance Futures): 0.02% вход, 0.04% выход от notional
        entry_fee = notional * self.entry_fee
        exit_fee = notional * self.exit_fee
        total_fees = entry_fee + exit_fee
        # Симулируем движение цены (волатильность)
        timeframe_multiplier = self._get_timeframe_volatility()
        max_move = 0.10 * timeframe_multiplier
        price_move = random.uniform(-max_move, max_move)
        if action == 'buy':
            exit_price = entry_price * (1 + price_move)
        else:
            exit_price = entry_price * (1 - price_move)
        exit_price = max(0.0001, exit_price)
        # Прибыль/убыток до комиссий
        if action == 'buy':
            pnl = (exit_price - entry_price) * coins
        else:
            pnl = (entry_price - exit_price) * coins
        # --- Риск-менеджмент 1:2 ---
        # Стоп-лосс: -R (убыток = -risk_per_trade)
        # Тейк-профит: +2R (прибыль = +2*risk_per_trade)
        exit_reason = 'market_exit'
        gross_pnl = pnl
        if pnl < -risk_per_trade:
            gross_pnl = -risk_per_trade
            exit_reason = 'stop_loss'
        elif pnl > 2 * risk_per_trade:
            gross_pnl = 2 * risk_per_trade
            exit_reason = 'take_profit'
        # Чистая прибыль с учетом комиссий
        net_profit = gross_pnl - total_fees
        # Логировать, если комиссия превышает потенциальную прибыль (только если gross_pnl > 0)
        if gross_pnl > 0 and abs(total_fees) > abs(gross_pnl):
            print(f"   ⚠️ Комиссия (${total_fees:.2f}) превышает потенциальную прибыль (${gross_pnl:.2f})!")
        # Защита от переполнения
        if not math.isfinite(net_profit):
            net_profit = 0.0
        if not math.isfinite(total_fees):
            total_fees = 0.0
        # Обновляем капитал
        self.neural_network.current_capital += net_profit
        print(f"   💰 {market_data.get('symbol', 'UNKNOWN')} {action.upper()}: Цена ${entry_price:.4f}→${exit_price:.4f}, Размер {position_size:.1%}, Плечо {leverage}x, Прибыль ${net_profit:.2f} (комиссии: ${total_fees:.2f}) ({exit_reason})")
        return {
            'entry_price': entry_price,
            'exit_price': exit_price,
            'profit': net_profit,
            'fees': total_fees,
            'exit_reason': exit_reason,
            'action': action,
            'position_size': position_size,
            'leverage': leverage,
            'market_data': market_data  # 🧠 Добавляем данные рынка для анализа паттернов
        }
    
    def _get_timeframe_volatility(self) -> float:
        """Возвращает множитель волатильности для таймфрейма"""
        volatility_map = {
            '1M': 2.0, '1w': 1.5, '1d': 1.2, '12h': 1.1, '8h': 1.0,
            '6h': 0.9, '4h': 0.8, '2h': 0.7, '1h': 0.6, '30m': 0.5,
            '15m': 0.4, '5m': 0.3, '3m': 0.25, '1m': 0.2
        }
        return volatility_map.get(self.current_timeframe, 1.0)
    
    def _restart_learning(self):
        """Полный перезапуск обучения"""
        print("🔄 ПОЛНЫЙ ПЕРЕЗАПУСК ОБУЧЕНИЯ")
        print("💰 Сброс капитала до $100")
        self.neural_network = AutonomousNeuralNetwork(100.0)  # Всегда начинаем с $100
        self.neural_network.current_capital = 100.0  # Гарантируем сброс
        self.current_timeframe_index = 0
        self.current_restart = 0
        self.current_cycle = 0
        self.learning_history = []
        self.timeframe_history = []
    
    def _restart_current_timeframe(self):
        """Перезапуск обучения на текущем таймфрейме"""
        print(f"🔄 ПЕРЕЗАПУСК НА ТАЙМФРЕЙМЕ {self.current_timeframe}")
        print("💰 Сброс капитала до $100")
        self.neural_network.current_capital = 100.0  # Гарантируем сброс
        self.current_cycle = 0
    
    def _save_timeframe_success(self):
        """Сохраняет успешное прохождение таймфрейма"""
        success_record = {
            'timeframe': self.current_timeframe,
            'cycle': self.current_cycle,
            'timestamp': datetime.now().isoformat(),
            'capital': self.neural_network.current_capital
        }
        self.timeframe_history.append(success_record)
    
    def _save_learning_state(self):
        """Сохраняет состояние обучения"""
        state = {
            'current_timeframe_index': self.current_timeframe_index,
            'current_timeframe': self.current_timeframe,
            'current_cycle': self.current_cycle,
            'current_restart': self.current_restart,
            'neural_network_state': self.neural_network.get_state(),
            'timeframe_history': self.timeframe_history,
            'learning_history': self.learning_history[-100:]  # Последние 100 записей
        }
        
        with open('progressive_learning_state.json', 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    def _load_learning_state(self):
        """Загружает состояние обучения"""
        try:
            if os.path.exists('progressive_learning_state.json'):
                with open('progressive_learning_state.json', 'r', encoding='utf-8') as f:
                    state = json.load(f)
                
                self.current_timeframe_index = state.get('current_timeframe_index', 0)
                self.current_timeframe = state.get('current_timeframe', self.timeframe_progression[0])
                self.current_cycle = state.get('current_cycle', 0)
                self.current_restart = state.get('current_restart', 0)
                self.timeframe_history = state.get('timeframe_history', [])
                self.learning_history = state.get('learning_history', [])
                
                # Восстанавливаем состояние нейросети
                neural_state = state.get('neural_network_state', {})
                if neural_state:
                    self.neural_network.load_state(neural_state)
                
                print(f"📂 Загружено состояние обучения с таймфрейма {self.current_timeframe}")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки состояния: {e}")
    
    def _final_evaluation(self):
        """Финальная оценка обучения"""
        print("\n🏆 ФИНАЛЬНАЯ ОЦЕНКА ПРОГРЕССИВНОГО ОБУЧЕНИЯ")
        print("=" * 60)
        
        if self.timeframe_history:
            print("✅ УСПЕШНО ПРОЙДЕННЫЕ ТАЙМФРЕЙМЫ:")
            for record in self.timeframe_history:
                print(f"   📊 {record['timeframe']}: цикл {record['cycle']}, капитал ${record['capital']:.2f}")
        
        final_capital = float(self.neural_network.current_capital or 100.0)
        print(f"💰 Финальный капитал: ${final_capital:.2f}")
        print(f"📈 Общая прибыль: ${final_capital - 100.0:.2f}")
        
        learning_time = 0.0
        if self.learning_start_time is not None:
            learning_time = (time.time() - self.learning_start_time) / 60
        print(f"⏱️ Время обучения: {learning_time:.1f} минут")
        
        # Сохраняем финальное состояние
        with open('final_progressive_learning_state.json', 'w', encoding='utf-8') as f:
            json.dump({
                'timeframe_history': self.timeframe_history,
                'final_capital': final_capital,
                'total_profit': final_capital - 100.0,
                'learning_time_minutes': learning_time
            }, f, indent=2, ensure_ascii=False)
        
        print("💾 Финальное состояние сохранено в final_progressive_learning_state.json")
    
    def get_learning_summary(self) -> Dict:
        """Возвращает сводку обучения"""
        current_capital = float(self.neural_network.current_capital or 100.0)
        return {
            'current_timeframe': self.current_timeframe,
            'current_timeframe_index': self.current_timeframe_index,
            'current_cycle': self.current_cycle,
            'current_restart': self.current_restart,
            'current_capital': current_capital,
            'current_profit': current_capital - 100.0,
            'timeframe_history': self.timeframe_history,
            'best_performance': self.best_performance
        } 