"""
🧠 Логика торгового дашборда
Обновление цен, анализ, торговые операции
"""

import threading
import time
from datetime import datetime
import random
import tkinter as tk
from typing import Dict

# Добавляем импорт агрессивной системы
from .aggressive_trade_system import AggressiveTradeSystem
import trading_bot.online_data_manager as online_data_manager

# Добавляем импорт эволюционного агента
from evolutionary_rmm_agent import EvolutionaryRMMAgent
# Добавляем импорт анализатора знаний
from .knowledge_analyzer import KnowledgeAnalyzer
# Добавляем импорт синхронизации с GitHub
from .github_sync import KnowledgeSyncManager

class DashboardLogic:
    """Логика торгового дашборда"""
    
    def __init__(self, dashboard_core, dashboard_ui):
        self.core = dashboard_core
        self.ui = dashboard_ui
        self.colors = dashboard_core.colors
        
        # Состояние системы
        self.message_count = 0
        self.update_counter = 0
        
        # Инициализируем агрессивную торговую систему
        self.aggressive_system = AggressiveTradeSystem(initial_balance=100.0)
        self.rmm_agent = EvolutionaryRMMAgent(population_size=20, mutation_rate=0.2, elite_frac=0.2)
        self.rmm_logs = []  # Для хранения выводов и ошибок агента
        self.knowledge_analyzer = KnowledgeAnalyzer()  # Анализатор базы знаний
        self.sync_manager = KnowledgeSyncManager(self)  # Менеджер синхронизации с GitHub
        self.trading_active = False
        self.last_trading_check = None
        
        # Настройки торговли
        self.trading_settings = {
            'auto_trading': False,
            'risk_per_trade': 0.01,  # 1%
            'max_positions': 3,
            'min_confidence': 0.35,
            'aggression_mode': True
        }
        
        # Настройки периода анализа
        self.analysis_period = {
            'start_date': '2024-07-01',
            'end_date': '2025-05-31'  # Исправлено: данные есть только до мая 2025
        }
        
        # Настройки периода торговли (по умолчанию последние 3 месяца)
        self.trading_period = {
            'start_date': '2024-10-01',  # Начинаем с октября 2024
            'end_date': '2024-12-31'     # Заканчиваем декабрем 2024
        }
        
        # Инициализируем загрузчик данных
        try:
            from .data_loader import HistoricalDataLoader
            self.data_loader = HistoricalDataLoader()
            # Проверяем доступные данные
            self._check_available_data()
        except ImportError:
            try:
                from data_loader import HistoricalDataLoader
                self.data_loader = HistoricalDataLoader()
                # Проверяем доступные данные
                self._check_available_data()
            except ImportError:
                self.data_loader = None
                print("⚠️ Загрузчик исторических данных недоступен")
    
    def _check_available_data(self):
        """Проверяет доступные данные и устанавливает правильный период анализа"""
        try:
            if not self.data_loader:
                return
            
            # Получаем доступные монеты и таймфреймы
            available_coins = self.data_loader.get_available_coins()
            available_timeframes = self.data_loader.get_available_timeframes()
            
            # Проверяем данные для BTCUSDT на 1h таймфрейме
            btc_data = self.data_loader.get_coin_data('BTCUSDT', '1h')
            
            if len(btc_data) > 0:
                # Определяем реальный диапазон данных
                min_date = btc_data['open_time'].min()
                max_date = btc_data['open_time'].max()
                
                # Обновляем период анализа
                self.analysis_period['start_date'] = min_date.strftime('%Y-%m-%d')
                self.analysis_period['end_date'] = max_date.strftime('%Y-%m-%d')
                
                self.add_terminal_message(f"📊 Доступные данные:", "INFO")
                self.add_terminal_message(f"   • Монет: {len(available_coins)}", "INFO")
                self.add_terminal_message(f"   • Таймфреймов: {len(available_timeframes)}", "INFO")
                self.add_terminal_message(f"   • Период: {self.analysis_period['start_date']} - {self.analysis_period['end_date']}", "INFO")
                self.add_terminal_message(f"   • Строк данных BTC: {len(btc_data)}", "INFO")
            else:
                self.add_terminal_message("⚠️ Данные BTCUSDT не найдены", "WARNING")
                
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка проверки данных: {str(e)}", "ERROR")
    
    def start_price_updates(self):
        """Запуск обновления цен каждые 3 секунды"""
        def update_loop():
            # Запуск цикла обновления цен
            while True:
                try:
                    # Обновляем цены через price_manager и получаем статус
                    api_ok = False
                    if hasattr(self.core, 'price_manager') and self.core.price_manager:
                        api_ok = self.core.price_manager.simulate_price_change()
                        # Обновляем цены в core из price_manager
                        for symbol in self.core.symbols:
                            if symbol in self.core.price_manager.prices:
                                price_data = self.core.price_manager.prices[symbol]
                                if symbol not in self.core.prices:
                                    self.core.prices[symbol] = {}
                                self.core.prices[symbol].update(price_data)
                                if symbol in self.core.price_manager.price_history:
                                    self.core.price_history[symbol] = self.core.price_history[symbol].copy()
                    
                    # Получаем баланс фьючерсов
                    balance_info = online_data_manager.get_futures_balance()
                    usdt_balance = None
                    if isinstance(balance_info, list):
                        for acc in balance_info:
                            if acc.get('asset') == 'USDT':
                                usdt_balance = float(acc.get('balance', 0))
                                break
                    elif isinstance(balance_info, dict) and 'error' in balance_info:
                        usdt_balance = None
                    if usdt_balance is not None:
                        self.core.futures_balance_var.set(f"Futures USDT: {usdt_balance:.2f}")
                    else:
                        self.core.futures_balance_var.set("Futures USDT: --")
                    # Обновляем все карточки
                    for symbol in self.core.symbols:
                        self.update_coin_card(symbol)
                    
                    # Обновляем статистику
                    self.update_statistics()
                    
                    # Обновляем статистику торговли
                    self.update_trading_stats()
                    
                    # Обновляем статус
                    current_time = datetime.now().strftime("%H:%M:%S")
                    if api_ok:
                        api_status = "🟢 API: OK"
                    else:
                        api_status = "🔴 API: Ошибка"
                    self.core.api_status_var.set(api_status)
                    status_text = f"🔄 Обновлено: {current_time} | Монет: 30 | 📡 Реальные цены Binance"
                    self.ui.status_var.set(status_text)
                    
                    # Обновляем счетчик
                    self.update_counter += 1
                    
                    # Ждем 3 секунды
                    time.sleep(3)
                    
                except Exception as e:
                    # Тихо обрабатываем ошибки без вывода в терминал
                    time.sleep(5)
        
        # Запускаем обновление в отдельном потоке
        update_thread = threading.Thread(target=update_loop, daemon=True)
        update_thread.start()
    
    def simulate_price_change(self):
        """Получение реальных цен с Binance API через онлайн менеджер"""
        # Используем price_manager для получения данных
        if hasattr(self.core, 'price_manager') and self.core.price_manager:
            # Обновляем цены через price_manager
            self.core.price_manager.simulate_price_change()
            
            # Обновляем цены в core из price_manager
            for symbol in self.core.symbols:
                if symbol in self.core.price_manager.prices:
                    price_data = self.core.price_manager.prices[symbol]
                    if symbol not in self.core.prices:
                        self.core.prices[symbol] = {}
                    
                    # Копируем данные
                    self.core.prices[symbol].update(price_data)
                    
                    # Обновляем историю
                    if symbol in self.core.price_manager.price_history:
                        self.core.price_history[symbol] = self.core.price_history[symbol].copy()
            
            # Обновление цен завершено
    
    def update_coin_card(self, symbol):
        """Обновление карточки монеты"""
        if symbol not in self.ui.coin_cards or symbol not in self.core.prices:
            return
        
        card = self.ui.coin_cards[symbol]
        price_data = self.core.prices[symbol]
        
        # Форматирование цены
        current_price = price_data['current']
        if current_price >= 1:
            price_text = f"${current_price:.2f}"
        elif current_price >= 0.01:
            price_text = f"${current_price:.4f}"
        else:
            price_text = f"${current_price:.8f}"
        
        card.labels['price'].config(text=price_text)
        
        # Изменение цены с цветовой индикацией
        change_24h = price_data['change_24h']
        if change_24h > 0:
            change_text = f"+{change_24h:.1f}%"
            change_color = self.colors.colors['green']
        elif change_24h < 0:
            change_text = f"{change_24h:.1f}%"
            change_color = self.colors.colors['red']
        else:
            change_text = f"{change_24h:.1f}%"
            change_color = self.colors.colors['text_gray']
        
        card.labels['change'].config(text=change_text, fg=change_color)
        
        # Объем (компактно)
        volume = price_data['volume_24h']
        if volume >= 1_000_000_000:
            volume_text = f"Vol: ${volume/1_000_000_000:.1f}B"
        elif volume >= 1_000_000:
            volume_text = f"Vol: ${volume/1_000_000:.1f}M"
        else:
            volume_text = f"Vol: ${volume/1_000:.1f}K"
        
        card.labels['volume'].config(text=volume_text)
        
        # Анимация изменения цены
        if price_data['current'] > price_data['previous']:
            card.configure(bg=self.colors.colors['green'])
            card.after(200, lambda: card.configure(bg=self.colors.colors['bg_dark']))
        elif price_data['current'] < price_data['previous']:
            card.configure(bg=self.colors.colors['red'])
            card.after(200, lambda: card.configure(bg=self.colors.colors['bg_dark']))
    
    def update_statistics(self):
        """Обновление статистики"""
        positive_count = 0
        negative_count = 0
        total_volume = 0
        
        for symbol, price_data in self.core.prices.items():
            if price_data['change_24h'] > 0:
                positive_count += 1
            elif price_data['change_24h'] < 0:
                negative_count += 1
            
            total_volume += price_data['volume_24h']
        
        # Обновляем метки статистики
        self.ui.stats_labels["📈 0"].config(text=f"📈 {positive_count}")
        self.ui.stats_labels["📉 0"].config(text=f"📉 {negative_count}")
        
        if total_volume >= 1_000_000_000:
            volume_text = f"💰 ${total_volume/1_000_000_000:.1f}B"
        elif total_volume >= 1_000_000:
            volume_text = f"💰 ${total_volume/1_000_000:.1f}M"
        else:
            volume_text = f"💰 ${total_volume/1_000:.1f}K"
        
        self.ui.stats_labels["💰 $0"].config(text=volume_text)
    
    def update_trading_stats(self):
        """Обновляет статистику торговли (отключено)"""
        return
        
        # Получаем статистику из симуляции
        stats = self.core.simulation.stats
        balance = self.core.simulation.balance
        
        # Рассчитываем винрейт
        winrate = 0.0
        if stats['total_trades'] > 0:
            winrate = (stats['winning_trades'] / stats['total_trades']) * 100
        
        # Рассчитываем просадку
        max_drawdown = 0.0
        if self.core.simulation.initial_balance > 0:
            current_drawdown = ((self.core.simulation.initial_balance - balance) / self.core.simulation.initial_balance) * 100
            max_drawdown = max(max_drawdown, current_drawdown)
        
        # Обновляем метки
        self.ui.trading_stats_labels["💰 Баланс: $100.00"].config(
            text=f"💰 Баланс: ${balance:.2f}")
        
        self.ui.trading_stats_labels["📈 Винрейт: 0.0%"].config(
            text=f"📈 Винрейт: {winrate:.1f}%")
        
        self.ui.trading_stats_labels["📊 Сделок: 0"].config(
            text=f"📊 Сделок: {stats['total_trades']}")
        
        self.ui.trading_stats_labels["💵 PnL: $0.00"].config(
            text=f"💵 PnL: ${stats['total_pnl']:+.2f}")
        
        self.ui.trading_stats_labels["🎯 Прибыльных: 0"].config(
            text=f"🎯 Прибыльных: {stats['winning_trades']}")
        
        self.ui.trading_stats_labels["❌ Убыточных: 0"].config(
            text=f"❌ Убыточных: {stats['losing_trades']}")
        
        self.ui.trading_stats_labels["📉 Макс. просадка: 0.0%"].config(
            text=f"📉 Макс. просадка: {max_drawdown:.1f}%")
        
        self.ui.trading_stats_labels["⚡ Открытых позиций: 0"].config(
            text=f"⚡ Открытых позиций: {len(self.core.simulation.open_positions)}")
    
    def start_aggressive_trading(self):
        """Запускает эволюционного RM/MM агента для торговли"""
        try:
            print("[DEBUG] start_aggressive_trading вызван")
            self.trading_active = True
            self.trading_settings['auto_trading'] = True
            self.add_terminal_message("🚀 ЭВОЛЮЦИОННЫЙ RM/MM АГЕНТ ЗАПУЩЕН", "SUCCESS")
            self.add_terminal_message("🤖 Агент будет учиться на ошибках и логировать все действия", "INFO")
            self.add_terminal_message("")
            trading_thread = threading.Thread(target=self._evolutionary_trading_loop, daemon=True)
            trading_thread.start()
            print("[DEBUG] Поток эволюционного агента создан и запущен")
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка запуска эволюционного агента: {e}", "ERROR")

    def stop_aggressive_trading(self):
        """Останавливает торговлю"""
        try:
            self.trading_active = False
            self.trading_settings['auto_trading'] = False
            self.add_terminal_message("⏹️ ЭВОЛЮЦИОННЫЙ RM/MM АГЕНТ ОСТАНОВЛЕН", "WARNING")
            self.add_terminal_message("")
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка остановки торговли: {e}", "ERROR")

    def _evolutionary_trading_loop(self):
        """Основной цикл эволюционного агента с отладкой и проверкой остановки"""
        try:
            print("[DEBUG] _evolutionary_trading_loop стартует")
            self.trading_active = True  # Явно выставляем активность
            self.add_terminal_message("▶️ Старт цикла эволюционного агента", "DEBUG")
            symbols = self.core.symbols if hasattr(self.core, 'symbols') else []
            timeframe = self.ui.get_selected_timeframes() if hasattr(self.ui, 'get_selected_timeframes') else ['1h']
            speed = self.ui.sim_speed_var.get() if hasattr(self.ui, 'sim_speed_var') else '1:1'
            self.add_terminal_message(f"DEBUG: symbols={symbols}", "DEBUG")
            self.add_terminal_message(f"DEBUG: timeframes={timeframe}", "DEBUG")
            print(f"[DEBUG] symbols={symbols}")
            print(f"[DEBUG] timeframes={timeframe}")
            if not symbols:
                self.add_terminal_message("❌ Нет доступных монет для торговли!", "ERROR")
                print("[DEBUG] Нет доступных монет для торговли!")
                return
            max_generations = 20
            trades_per_individual = 30
            generation = 0
            while self.trading_active and generation < max_generations:
                self.add_terminal_message(f"\n🧬 Поколение {self.rmm_agent.generation+1}", "INFO")
                for i, ind in enumerate(self.rmm_agent.population):
                    if not self.trading_active:
                        break
                    log = f"\n🤖 Индивид {i+1}: {ind.describe()}"
                    self.add_terminal_message(log, "INFO")
                    self.rmm_logs.append({'generation': self.rmm_agent.generation+1, 'individual': i+1, 'params': ind.describe(), 'actions': []})
                    fitness, errors, actions = self._simulate_trading(ind, symbols, timeframe, trades_per_individual)
                    ind.fitness = fitness
                    for err in errors:
                        self.add_terminal_message(f"❌ Ошибка: {err}", "ERROR")
                        self.rmm_logs[-1]['actions'].append({'error': err})
                    for act in actions:
                        self.add_terminal_message(f"📝 {act}", "INFO")
                        self.rmm_logs[-1]['actions'].append({'action': act})
                    self._update_trading_stats(fitness)
                if not self.trading_active:
                    break
                self.rmm_agent.log_population()
                self.rmm_agent.evolve()
                generation += 1
                # Показываем статистику после каждого поколения
                self.show_learning_statistics()
            self.add_terminal_message("🏁 Эволюционное обучение завершено", "SUCCESS")
            # Сохраняем базу знаний
            try:
                kb_file = self.rmm_agent.save_knowledge_base()
                self.add_terminal_message(f"💾 База знаний сохранена: {kb_file}", "SUCCESS")
                # Показываем статистику обучения
                stats = self.rmm_agent.get_learning_statistics()
                self.add_terminal_message(f"📊 Статистика обучения:", "INFO")
                self.add_terminal_message(f"   • Поколений: {stats['generation']}", "INFO")
                self.add_terminal_message(f"   • Всего сделок: {stats['total_trades']}", "INFO")
                self.add_terminal_message(f"   • Всего ошибок: {stats['total_errors']}", "INFO")
                self.add_terminal_message(f"   • Средний winrate: {stats['avg_winrate']:.1f}%", "INFO")
                self.add_terminal_message(f"   • Лучший winrate: {stats['best_winrate']:.1f}%", "INFO")
                self.add_terminal_message(f"   • Размер базы знаний: {stats['knowledge_base_size']} записей", "INFO")
            except Exception as e:
                self.add_terminal_message(f"❌ Ошибка сохранения базы знаний: {e}", "ERROR")
            self.add_terminal_message("⏹️ Торговый цикл остановлен по запросу пользователя", "WARNING")
            print("[DEBUG] Эволюционное обучение завершено")
        except Exception as e:
            import traceback
            self.add_terminal_message(f"❌ Критическая ошибка эволюционного цикла: {e}", "ERROR")
            self.add_terminal_message(traceback.format_exc(), "ERROR")
            print(f"[DEBUG] Критическая ошибка: {e}")

    def _simulate_trading(self, ind, symbols, timeframes, trades_per_individual):
        """Симуляция торговли для одного индивида с использованием реальных исторических данных"""
        # Используем текущий баланс агрессивной системы вместо сброса к 100
        balance = self.aggressive_system.current_balance
        win_trades = 0
        total_trades = 0
        errors = []
        actions = []
        open_positions = []
        margin_call_count = 0
        
        # Загружаем и фильтруем данные по периоду торговли
        historical_data = {}
        for symbol in symbols:
            for tf in timeframes:
                try:
                    # Проверяем доступность загрузчика данных
                    if self.data_loader is None:
                        self.add_terminal_message("❌ Загрузчик исторических данных недоступен", "ERROR")
                        return 0.0, ["Нет загрузчика данных"], []
                    
                    # Загружаем данные для символа и таймфрейма
                    data = self.data_loader.get_coin_data(symbol, tf)
                    if data is not None and len(data) > 0:
                        # Фильтруем по периоду торговли
                        filtered_data = self._filter_data_by_period(
                            data, 
                            self.trading_period['start_date'], 
                            self.trading_period['end_date']
                        )
                        if len(filtered_data) > 0:
                            historical_data[f"{symbol}_{tf}"] = filtered_data
                            self.add_terminal_message(f"📊 Загружено {len(filtered_data)} свечей для {symbol} {tf} в периоде {self.trading_period['start_date']} - {self.trading_period['end_date']}", "DEBUG")
                        else:
                            self.add_terminal_message(f"⚠️ Нет данных для {symbol} {tf} в указанном периоде", "WARNING")
                except Exception as e:
                    self.add_terminal_message(f"❌ Ошибка загрузки данных {symbol} {tf}: {e}", "ERROR")
        
        if not historical_data:
            self.add_terminal_message("❌ Нет доступных исторических данных для торговли", "ERROR")
            return 0.0, ["Нет данных"], []
        
        self.add_terminal_message(f"📅 Торговля на исторических данных: {self.trading_period['start_date']} - {self.trading_period['end_date']}", "INFO")
        
        t = 0
        while t < trades_per_individual:
            try:
                # Выбираем случайный символ и таймфрейм
                symbol = random.choice(symbols)
                tf = random.choice(timeframes)
                data_key = f"{symbol}_{tf}"
                
                if data_key not in historical_data or len(historical_data[data_key]) == 0:
                    continue
                
                # Выбираем случайную свечу из исторических данных
                candle = historical_data[data_key].iloc[random.randint(0, len(historical_data[data_key]) - 1)]
                
                # Используем реальные цены из свечи
                open_price = float(candle['open'])
                high_price = float(candle['high'])
                low_price = float(candle['low'])
                close_price = float(candle['close'])
                volume = float(candle['volume'])
                candle_time = candle['open_time']
                
                direction = random.choice(['LONG', 'SHORT'])
                entry_price = open_price  # Входим по цене открытия свечи
                
                # ПРАВИЛЬНЫЙ РАСЧЕТ С УЧЕТОМ ПЛЕЧА
                risk_amount = balance * ind.position_size
                leverage = ind.leverage
                position_size = (risk_amount * leverage) / entry_price
                margin_used = risk_amount / leverage
                open_time = candle_time.strftime('%Y-%m-%d %H:%M:%S')
                
                pos = {
                    'symbol': symbol,
                    'size': position_size,
                    'entry_price': entry_price,
                    'leverage': leverage,
                    'side': direction,
                    'budget': risk_amount,
                    'margin_used': margin_used,
                    'pnl_dollars': 0,
                    'pnl_pct': 0,
                    'open': True,
                    'open_time': open_time,
                    'close_time': None
                }
                open_positions.append(pos)
                actions.append(f"Открыта позиция: {symbol} {direction} размер {position_size:.4f} по цене {entry_price:.2f} (риск ${risk_amount:.2f}, плечо {leverage}x, маржа ${margin_used:.2f}) в {open_time}")
                
                # Симулируем результат сделки на основе реальных данных
                # Используем волатильность свечи для определения вероятности выигрыша
                candle_volatility = (high_price - low_price) / open_price
                
                # БАЗОВЫЙ ВИНРЕЙТ - более реалистичный подход
                base_winrate = 0.45  # Базовый винрейт 45% (ближе к реальности)
                
                # Корректируем winrate на основе РЕАЛЬНЫХ рыночных условий
                # Вместо искусственных бонусов используем анализ свечи
                
                # Анализируем тренд свечи
                candle_trend = 'bullish' if close_price > open_price else 'bearish'
                
                # Корректируем на основе направления сделки и тренда свечи
                if (direction == 'LONG' and candle_trend == 'bullish') or (direction == 'SHORT' and candle_trend == 'bearish'):
                    base_winrate += 0.05  # +5% если направление совпадает с трендом
                
                # Корректируем на основе волатильности
                if candle_volatility > 0.05:  # Высокая волатильность
                    base_winrate -= 0.1  # -10% при высокой волатильности
                elif candle_volatility < 0.01:  # Низкая волатильность
                    base_winrate += 0.05  # +5% при низкой волатильности
                
                # Добавляем небольшой элемент случайности
                winrate = min(0.65, max(0.25, base_winrate + random.uniform(-0.05, 0.05)))
                
                is_win = random.random() < winrate
                
                # Рассчитываем PnL на основе реальных цен
                if is_win:
                    if direction == 'LONG':
                        exit_price = close_price  # Выходим по цене закрытия
                    else:  # SHORT
                        exit_price = low_price  # Для шорта используем минимум свечи
                    pnl_pct = (exit_price - entry_price) / entry_price if direction == 'LONG' else (entry_price - exit_price) / entry_price
                else:
                    if direction == 'LONG':
                        exit_price = low_price  # Для проигрышного лонга используем минимум
                    else:  # SHORT
                        exit_price = high_price  # Для проигрышного шорта используем максимум
                    pnl_pct = (exit_price - entry_price) / entry_price if direction == 'LONG' else (entry_price - exit_price) / entry_price
                
                pnl = risk_amount * pnl_pct * leverage
                commission_rate = 0.0004
                position_volume = position_size * entry_price
                commission = position_volume * commission_rate * 2
                final_pnl = pnl - commission
                old_balance = balance
                balance += final_pnl
                
                self.add_terminal_message(f"[РЕАЛЬНЫЕ ДАННЫЕ] Свеча: {open_time} | O:{open_price:.2f} H:{high_price:.2f} L:{low_price:.2f} C:{close_price:.2f}", "DEBUG")
                self.add_terminal_message(f"[РЕАЛЬНЫЕ ДАННЫЕ] Волатильность: {candle_volatility:.3f} | Тренд: {candle_trend}", "DEBUG")
                self.add_terminal_message(f"[РЕАЛЬНЫЕ ДАННЫЕ] Винрейт: {winrate:.1%} | Результат: {'ПОБЕДА' if is_win else 'ПОРАЖЕНИЕ'}", "DEBUG")
                self.add_terminal_message(f"[РЕАЛЬНЫЕ ДАННЫЕ] PnL: ${final_pnl:+.2f} ({pnl_pct*100:+.1f}% * {leverage}x)", "DEBUG")
                
                pos['pnl_dollars'] = final_pnl
                pos['pnl_pct'] = final_pnl / risk_amount if risk_amount > 0 else 0
                pos['open'] = False
                close_time = candle_time.strftime('%Y-%m-%d %H:%M:%S')
                pos['close_time'] = close_time
                
                trade_data = {
                    'win': is_win,
                    'symbol': symbol,
                    'timeframe': tf,
                    'direction': direction,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': final_pnl,
                    'pnl_pct': final_pnl / risk_amount if risk_amount > 0 else 0,
                    'size': position_size,
                    'leverage': leverage,
                    'budget': risk_amount,
                    'margin_used': margin_used,
                    'commission': commission,
                    'duration': 'instant',
                    'open_time': open_time,
                    'close_time': close_time,
                    'market_conditions': {
                        'volatility': candle_volatility,
                        'trend': candle_trend,
                        'volume': volume,
                        'candle_range': high_price - low_price
                    }
                }
                ind.update_history(trade_data)
                if is_win:
                    win_trades += 1
                total_trades += 1
                actions.append(f"Закрыта позиция: {symbol} {direction} PnL {final_pnl:+.2f} (комиссия: {commission:.2f}) Баланс: {balance:.2f} в {close_time}")
                current_winrate = (win_trades / total_trades) * 100
                actions.append(f"Winrate по текущим параметрам за {len(ind.trade_history)} сделок: {current_winrate:.1f}%")
                if current_winrate < 40:
                    actions.append("❗ Агент замечает, что winrate низкий — будет мутировать параметры")
                elif current_winrate > 60:
                    actions.append("✅ Агент доволен winrate и будет стараться закрепить успех")
                self._update_positions_table(open_positions)
                open_positions = [p for p in open_positions if p['open']]
                analysis = self.knowledge_analyzer.analyze_trade_result(trade_data) if hasattr(self.knowledge_analyzer, 'analyze_trade_result') else None
                if analysis:
                    self.add_terminal_message(f"[Анализ сделки] {analysis}", "INFO")
                # Margin-call: если баланс <= 0, закрываем все позиции, логируем и перезапускаем симуляцию
                if balance <= 0:
                    margin_call_count += 1
                    self.add_terminal_message(f"❌ MARGIN CALL! Баланс ушел в минус (${balance:.2f}). Все позиции закрыты. Перезапуск симуляции с $100.", "ERROR")
                    # Закрываем все открытые позиции
                    for p in open_positions:
                        p['open'] = False
                        p['close_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    open_positions.clear()
                    # Сброс баланса
                    balance = 100.0
                    # Можно добавить паузу или анализ, если нужно
                else:
                    t += 1
                # Динамическое управление риском (как в агрессивной системе)
                if total_trades >= 5:
                    recent_trades = total_trades - 5
                    recent_wins = win_trades - (total_trades - 5) if total_trades > 5 else win_trades
                    recent_winrate = (recent_wins / 5) * 100 if total_trades >= 5 else 0
                    old_risk = ind.position_size
                    if recent_winrate > 60 and ind.position_size < 0.03:
                        ind.position_size = min(ind.position_size + 0.002, 0.03)
                        self.add_terminal_message(f"[РИСК] ⬆️ Увеличен до {ind.position_size*100:.1f}% (winrate: {recent_winrate:.1f}%)", "INFO")
                    elif recent_winrate < 40 and ind.position_size > 0.005:
                        ind.position_size = max(ind.position_size - 0.002, 0.005)
                        self.add_terminal_message(f"[РИСК] ⬇️ Уменьшен до {ind.position_size*100:.1f}% (winrate: {recent_winrate:.1f}%)", "INFO")
                    if ind.position_size != old_risk:
                        self.add_terminal_message(f"[РИСК] Новый риск: {ind.position_size*100:.1f}% от баланса", "INFO")
            except Exception as e:
                error_msg = f"Ошибка в сделке {t+1}: {e}"
                errors.append(error_msg)
                self.add_terminal_message(error_msg, "ERROR")
                ind.record_error({
                    'error_type': 'simulation_error',
                    'error_message': error_msg,
                    'trade_number': t+1
                })
        # Рассчитываем фитнес (приоритет: winrate > общий PnL > количество сделок)
        if total_trades == 0:
            fitness = 0.0
        else:
            winrate = (win_trades / total_trades) * 100
            total_pnl = balance - 100.0
            pnl_ratio = total_pnl / 100.0
            fitness = (winrate * 0.6) + (pnl_ratio * 100 * 0.3) + (min(total_trades / 10, 1.0) * 100 * 0.1)
        old_aggressive_balance = self.aggressive_system.current_balance
        self.aggressive_system.current_balance = balance
        self.add_terminal_message(f"[СИНХРОНИЗАЦИЯ] Баланс эволюционного агента: ${balance:.2f}", "DEBUG")
        self.add_terminal_message(f"[СИНХРОНИЗАЦИЯ] Баланс агрессивной системы: ${old_aggressive_balance:.2f} → ${self.aggressive_system.current_balance:.2f}", "DEBUG")
        self.add_terminal_message(f"[СИНХРОНИЗАЦИЯ] Без масштабирования - одинаковый баланс", "DEBUG")
        for trade_data in ind.trade_history[-total_trades:]:
            if 'pnl' in trade_data:
                closed_position = {
                    'symbol': trade_data.get('symbol', 'UNKNOWN'),
                    'direction': trade_data.get('direction', 'LONG'),
                    'entry_price': trade_data.get('entry_price', 0),
                    'close_price': trade_data.get('exit_price', 0),
                    'size': trade_data.get('size', 0),
                    'pnl': trade_data.get('pnl', 0),
                    'pnl_pct': trade_data.get('pnl_pct', 0),
                    'commission': trade_data.get('commission', 0),
                    'close_time': datetime.now(),
                    'reason': 'Evolutionary Trade'
                }
                self.aggressive_system.closed_positions.append(closed_position)
        self.add_terminal_message(f"[MARGIN CALL] Количество margin-call за симуляцию: {margin_call_count}", "WARNING")
        # Явно возвращаем результат для предотвращения ошибки распаковки
        return fitness, errors, actions
    
    def _update_positions_table(self, positions):
        """Обновляет таблицу открытых позиций в UI (добавлены даты открытия/закрытия)"""
        try:
            if hasattr(self.ui, 'positions_table'):
                open_pos = [p for p in positions if p.get('open', False)]
                for row in self.ui.positions_table.get_children():
                    self.ui.positions_table.delete(row)
                for pos in open_pos:
                    symbol = pos.get('symbol', '')
                    size = f"{pos.get('size', 0):.4f} {symbol.replace('USDT','')}"
                    entry = f"{pos.get('entry_price', 0):.2f}"
                    breakeven = f"{pos.get('entry_price', 0):.2f}"
                    mark = f"{pos.get('entry_price', 0):.2f}"
                    leverage = pos.get('leverage', 1)
                    side = pos.get('side', 'LONG')
                    if side == 'LONG':
                        liq = f"{pos.get('entry_price', 0) * (1 - 1/max(leverage,1)):.2f}"
                    else:
                        liq = f"{pos.get('entry_price', 0) * (1 + 1/max(leverage,1)):.2f}"
                    margin_rate = f"{100/max(leverage,1):.2f}%"
                    margin = f"{(pos.get('size',0)*pos.get('entry_price',0)/max(leverage,1)):.2f} USDT"
                    pnl = f"{pos.get('pnl_dollars',0):+.2f} USDT ({pos.get('pnl_pct',0)*100:+.2f}%)"
                    stop = "-"
                    take = "-"
                    open_time = pos.get('open_time', '-')
                    close_time = pos.get('close_time', '-')
                    iid = self.ui.positions_table.insert("", "end", values=(symbol, size, entry, breakeven, mark, liq, margin_rate, margin, pnl, stop, take, open_time))
                    self.ui.positions_table.set(iid, column="Действия", value="Закрыть")
        except Exception as e:
            pass

    def _update_trading_stats(self, fitness):
        """Обновляет торговую статистику в UI"""
        try:
            # Получаем правильный статус торговли вместо использования fitness
            status = self.get_trading_status()
            balance = status['balance']
            winrate = status['winrate']
            
            if hasattr(self.ui, 'trading_stats_labels'):
                self.ui.trading_stats_labels["💰 Баланс: $100.00"].config(text=f"💰 Баланс: ${balance:,.2f}")
                self.ui.trading_stats_labels["📈 Винрейт: 0.0%"].config(text=f"📈 Винрейт: {winrate:.1f}%")
        except Exception as e:
            pass

    def get_trading_status(self) -> Dict:
        """Возвращает статус торговли"""
        try:
            return {
                'active': self.trading_active,
                'balance': self.aggressive_system.current_balance,
                'open_positions': len(self.aggressive_system.open_positions),
                'total_trades': len(self.aggressive_system.closed_positions),
                'winrate': self._calculate_winrate(),
                'total_pnl': self._calculate_total_pnl()
            }
        except Exception as e:
            return {
                'active': False,
                'balance': 100.0,
                'open_positions': 0,
                'total_trades': 0,
                'winrate': 0.0,
                'total_pnl': 0.0
            }

    def _calculate_winrate(self) -> float:
        """Рассчитывает винрейт"""
        try:
            if len(self.aggressive_system.closed_positions) == 0:
                return 0.0
            
            winning_trades = sum(1 for p in self.aggressive_system.closed_positions if p['pnl'] > 0)
            return (winning_trades / len(self.aggressive_system.closed_positions)) * 100
        except:
            return 0.0

    def _calculate_total_pnl(self) -> float:
        """Рассчитывает общий P&L"""
        try:
            return sum(p['pnl'] for p in self.aggressive_system.closed_positions)
        except:
            return 0.0
    
    def set_analysis_period(self, start_date: str, end_date: str):
        """Установка периода для анализа исторических данных"""
        try:
            # Обновляем период
            self.analysis_period['start_date'] = start_date
            self.analysis_period['end_date'] = end_date
            
            # Проверяем доступность загрузчика
            if not self.data_loader:
                self.ui.add_terminal_message("❌ Загрузчик исторических данных недоступен", "ERROR")
                return
            
            # Тестируем загрузку данных для BTCUSDT
            test_data = self.data_loader.get_coin_data(
                'BTCUSDT', '1h', 
                start_date=start_date, 
                end_date=end_date
            )
            
            if len(test_data) > 0:
                self.ui.add_terminal_message(
                    f"✅ Период установлен: {start_date} - {end_date} | "
                    f"Данных: {len(test_data)} строк", 
                    "SUCCESS"
                )
                
                # Запускаем анализ на основе нового периода
                self.run_period_analysis()
            else:
                self.ui.add_terminal_message(
                    f"⚠️ Для периода {start_date} - {end_date} данных не найдено", 
                    "ERROR"
                )
                
        except Exception as e:
            self.ui.add_terminal_message(f"❌ Ошибка установки периода: {str(e)}", "ERROR")
    
    def run_period_analysis(self):
        """Запуск анализа на основе выбранного периода"""
        try:
            if not self.data_loader:
                return
            
            start_date = self.analysis_period['start_date']
            end_date = self.analysis_period['end_date']
            
            # Анализируем топ-5 монет
            top_coins = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
            
            analysis_results = []
            for coin in top_coins:
                # Загружаем данные для 1h таймфрейма
                data = self.data_loader.get_coin_data(coin, '1h', start_date, end_date)
                
                if len(data) > 0:
                    # Простой анализ: средняя цена, волатильность, тренд
                    avg_price = data['close'].mean()
                    volatility = data['close'].std() / avg_price * 100
                    
                    # Определяем тренд (сравниваем начало и конец периода)
                    start_price = data.iloc[0]['close']
                    end_price = data.iloc[-1]['close']
                    trend = ((end_price - start_price) / start_price) * 100
                    
                    analysis_results.append({
                        'coin': coin,
                        'avg_price': avg_price,
                        'volatility': volatility,
                        'trend': trend,
                        'data_points': len(data)
                    })
            
            # Выводим результаты в терминал
            if analysis_results:
                self.ui.add_terminal_message("📊 Анализ исторических данных:", "INFO")
                for result in analysis_results:
                    trend_icon = "📈" if result['trend'] > 0 else "📉"
                    self.ui.add_terminal_message(
                        f"{trend_icon} {result['coin']}: "
                        f"Средняя цена: ${result['avg_price']:.2f}, "
                        f"Волатильность: {result['volatility']:.1f}%, "
                        f"Тренд: {result['trend']:+.1f}%, "
                        f"Данных: {result['data_points']}",
                        "INFO"
                    )
            
        except Exception as e:
            self.ui.add_terminal_message(f"❌ Ошибка анализа периода: {str(e)}", "ERROR")
    
    def check_data_availability(self, start_date: str, end_date: str) -> bool:
        """Проверяет доступность данных для указанного периода"""
        try:
            if not self.data_loader:
                return False
            
            # Проверяем данные для BTCUSDT на 1h таймфрейме
            test_data = self.data_loader.get_coin_data(
                'BTCUSDT', '1h', 
                start_date=start_date, 
                end_date=end_date
            )
            
            return len(test_data) > 0
            
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка проверки доступности данных: {str(e)}", "ERROR")
            return False
    
    def add_terminal_message(self, message: str, level: str = "INFO"):
        self.ui.add_terminal_message(message, level)

    def clear_terminal(self):
        self.ui.clear_terminal()

    def update_positions_table(self):
        if hasattr(self.core, 'simulation') and self.core.simulation:
            positions = self.core.simulation.get_open_positions_info()
            self.ui.update_positions_table(positions)
    
    def show_recent_ai_insights(self):
        """Показывает последние уроки ИИ"""
        if not self.core.intelligent_system:
            return
            
        insights = self.core.intelligent_system.get_recent_insights(3)
        if insights:
            self.add_terminal_message("📚 Последние уроки ИИ:", "INFO")
            for insight in insights:
                self.add_terminal_message(f"   • {insight}", "INFO")
    
    def add_ai_analysis_message(self):
        """Добавляет периодическое сообщение от ИИ с анализом рынка (отключено)"""
        # Функция отключена для предотвращения запросов исторических данных
        pass
    
    def add_multi_timeframe_analysis(self):
        """Добавляет мультитаймфреймовый анализ (отключено)"""
        # Функция отключена для предотвращения запросов исторических данных
        pass
    
    def add_simple_market_analysis(self):
        """Добавляет простой анализ рынка (fallback)"""
        try:
            # Анализируем текущее состояние рынка
            positive_count = sum(1 for data in self.core.prices.values() if data['change_24h'] > 0)
            negative_count = sum(1 for data in self.core.prices.values() if data['change_24h'] < 0)
            total_coins = len(self.core.prices)
            
            # Анализ рынка
            
            # Определяем настроение рынка
            if positive_count > total_coins * 0.6:
                sentiment = "📈 Бычий рынок"
                analysis = "Большинство монет растут, ищу возможности для LONG позиций"
            elif negative_count > total_coins * 0.6:
                sentiment = "📉 Медвежий рынок"
                analysis = "Большинство монет падают, ищу возможности для SHORT позиций"
            else:
                sentiment = "➡️ Боковой рынок"
                analysis = "Рынок в боковике, жду четких сигналов для входа"
            
            # Находим топ-монеты
            sorted_coins = sorted(self.core.prices.items(), key=lambda x: abs(x[1]['change_24h']), reverse=True)
            top_volatile = [f"{symbol}: {data['change_24h']:+.1f}%" for symbol, data in sorted_coins[:3]]
            
            # Формируем сообщение
            message = f"🧠 Анализ рынка: {sentiment} | {analysis} | Топ волатильность: {' | '.join(top_volatile)}"
            self.add_terminal_message(message, "SIGNAL")
            
            # Добавляем поиск торговых возможностей
            self.search_trading_opportunities()
            
        except Exception as e:
            # Тихо обрабатываем ошибки анализа
            pass
    
    def search_trading_opportunities(self):
        """Ищет торговые возможности на основе анализа"""
        try:
            # Анализируем каждую монету на предмет торговых сигналов
            opportunities = []
            
            for symbol, price_data in self.core.prices.items():
                # Простые критерии для торговых сигналов
                change_24h = price_data['change_24h']
                volume = price_data['volume_24h']
                
                # Сигнал на покупку: сильный рост + высокий объем
                if change_24h > 5 and volume > 50000000:  # 5% рост + 50M объем
                    opportunities.append(f"🚀 {symbol}: Сильный рост +{change_24h:.1f}% (объем: ${volume/1e6:.1f}M)")
                
                # Сигнал на продажу: сильное падение + высокий объем
                elif change_24h < -5 and volume > 50000000:  # 5% падение + 50M объем
                    opportunities.append(f"📉 {symbol}: Сильное падение {change_24h:.1f}% (объем: ${volume/1e6:.1f}M)")
                
                # Сигнал на разворот: экстремальные значения
                elif change_24h > 15:  # Более 15% роста - возможен разворот
                    opportunities.append(f"⚠️ {symbol}: Экстремальный рост +{change_24h:.1f}% - возможен разворот")
                elif change_24h < -15:  # Более 15% падения - возможен разворот
                    opportunities.append(f"⚠️ {symbol}: Экстремальное падение {change_24h:.1f}% - возможен разворот")
            
            # Показываем найденные возможности
            if opportunities:
                self.add_terminal_message("🎯 Найденные торговые возможности:", "SIGNAL")
                for opp in opportunities[:5]:  # Показываем максимум 5 возможностей
                    self.add_terminal_message(f"   • {opp}", "INFO")
            else:
                self.add_terminal_message("🔍 Торговых возможностей не найдено - жду лучших условий", "INFO")
                
        except Exception as e:
            # Тихо обрабатываем ошибки поиска возможностей
            pass
    
    def start_ai_analysis_timer(self):
        """Запускает периодический анализ ИИ каждые 15 секунд (отключено)"""
        # Функция отключена для предотвращения запросов исторических данных
        pass
    
    def delayed_ai_start(self):
        """Запускает ИИ анализ после полной инициализации GUI (отключено)"""
        # Функция отключена для предотвращения запросов исторических данных
        pass
    
    def update_market_data(self):
        """Обновление данных о состоянии рынка"""
        # Расчет данных рынка на основе реальных цен
        total_market_cap = sum(price_data['current'] * random.randint(1000000, 10000000) 
                              for price_data in self.core.prices.values())
        
        total_volume = sum(price_data['volume_24h'] for price_data in self.core.prices.values())
        
        # Определяем топ-монеты
        sorted_coins = sorted(self.core.prices.items(), 
                            key=lambda x: x[1]['change_24h'], reverse=True)
        
        top_gainers = [f"{symbol}: +{data['change_24h']:.1f}%" 
                      for symbol, data in sorted_coins[:3]]
        top_losers = [f"{symbol}: {data['change_24h']:.1f}%" 
                     for symbol, data in sorted_coins[-3:]]
        
        # Определяем настроение рынка
        positive_count = sum(1 for data in self.core.prices.values() if data['change_24h'] > 0)
        if positive_count > len(self.core.prices) * 0.7:
            sentiment = "bullish"
        elif positive_count < len(self.core.prices) * 0.3:
            sentiment = "bearish"
        else:
            sentiment = "neutral"
        
        self.ui.market_data = {
            'total_market_cap': total_market_cap,
            'total_volume_24h': total_volume,
            'bitcoin_dominance': random.uniform(40, 55),
            'market_sentiment': sentiment,
            'top_gainers': top_gainers,
            'top_losers': top_losers
        }
        
        # Обновляем каждые 5 секунд
        self.core.root.after(5000, self.update_market_data)
    
    def animate_market_ticker(self):
        """Анимация бегущей строки рынка"""
        # Очищаем canvas
        self.ui.ticker_canvas.delete("all")
        
        # Получаем размеры canvas
        canvas_width = self.ui.ticker_canvas.winfo_width()
        canvas_height = self.ui.ticker_canvas.winfo_height()
        
        if canvas_width > 0:
            # Формируем текст бегущей строки
            sentiment_emoji = {
                'bullish': '📈',
                'bearish': '📉',
                'neutral': '➡️'
            }
            
            ticker_text = (
                f"🌐 РЫНОК КРИПТОВАЛЮТ • "
                f"Капитализация: ${self.ui.market_data['total_market_cap']/1e12:.1f}T • "
                f"Объем 24ч: ${self.ui.market_data['total_volume_24h']/1e9:.1f}B • "
                f"BTC доминирование: {self.ui.market_data['bitcoin_dominance']:.1f}% • "
                f"Настроение: {sentiment_emoji[self.ui.market_data['market_sentiment']]} "
                f"{self.ui.market_data['market_sentiment'].upper()} • "
                f"Топ рост: {' | '.join(self.ui.market_data['top_gainers'])} • "
                f"Топ падение: {' | '.join(self.ui.market_data['top_losers'])} • "
            )
            
            # Создаем текст бегущей строки
            text_id = self.ui.ticker_canvas.create_text(
                canvas_width - self.ui.ticker_position, 
                canvas_height // 2,
                text=ticker_text,
                font=("Arial", 12, "bold"),
                fill=self.colors.colors['text_white'],
                anchor=tk.W
            )
            
            # Дублируем текст для бесконечной прокрутки
            text_width = self.ui.ticker_canvas.bbox(text_id)[2] - self.ui.ticker_canvas.bbox(text_id)[0]
            if self.ui.ticker_position > text_width:
                self.ui.ticker_canvas.create_text(
                    canvas_width - self.ui.ticker_position + text_width, 
                    canvas_height // 2,
                    text=ticker_text,
                    font=("Arial", 12, "bold"),
                    fill=self.colors.colors['text_white'],
                    anchor=tk.W
                )
            
            # Обновляем позицию
            self.ui.ticker_position += 1.5
            if self.ui.ticker_position > text_width:
                self.ui.ticker_position = 0
        
        # Планируем следующее обновление
        self.core.root.after(50, self.animate_market_ticker) 

    def start_aggressive_trading(self):
        """Запускает эволюционного RM/MM агента для торговли"""
        try:
            print("[DEBUG] start_aggressive_trading вызван")
            self.trading_active = True
            self.trading_settings['auto_trading'] = True
            self.add_terminal_message("🚀 ЭВОЛЮЦИОННЫЙ RM/MM АГЕНТ ЗАПУЩЕН", "SUCCESS")
            self.add_terminal_message("🤖 Агент будет учиться на ошибках и логировать все действия", "INFO")
            self.add_terminal_message("")
            trading_thread = threading.Thread(target=self._evolutionary_trading_loop, daemon=True)
            trading_thread.start()
            print("[DEBUG] Поток эволюционного агента создан и запущен")
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка запуска эволюционного агента: {e}", "ERROR")

    def stop_aggressive_trading(self):
        """Останавливает торговлю"""
        try:
            self.trading_active = False
            self.trading_settings['auto_trading'] = False
            self.add_terminal_message("⏹️ ЭВОЛЮЦИОННЫЙ RM/MM АГЕНТ ОСТАНОВЛЕН", "WARNING")
            self.add_terminal_message("")
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка остановки торговли: {e}", "ERROR")

    def _evolutionary_trading_loop(self):
        """Основной цикл эволюционного агента с отладкой и проверкой остановки"""
        try:
            print("[DEBUG] _evolutionary_trading_loop стартует")
            self.trading_active = True  # Явно выставляем активность
            self.add_terminal_message("▶️ Старт цикла эволюционного агента", "DEBUG")
            symbols = self.core.symbols if hasattr(self.core, 'symbols') else []
            timeframe = self.ui.get_selected_timeframes() if hasattr(self.ui, 'get_selected_timeframes') else ['1h']
            speed = self.ui.sim_speed_var.get() if hasattr(self.ui, 'sim_speed_var') else '1:1'
            self.add_terminal_message(f"DEBUG: symbols={symbols}", "DEBUG")
            self.add_terminal_message(f"DEBUG: timeframes={timeframe}", "DEBUG")
            print(f"[DEBUG] symbols={symbols}")
            print(f"[DEBUG] timeframes={timeframe}")
            if not symbols:
                self.add_terminal_message("❌ Нет доступных монет для торговли!", "ERROR")
                print("[DEBUG] Нет доступных монет для торговли!")
                return
            max_generations = 20
            trades_per_individual = 30
            generation = 0
            while self.trading_active and generation < max_generations:
                self.add_terminal_message(f"\n🧬 Поколение {self.rmm_agent.generation+1}", "INFO")
                for i, ind in enumerate(self.rmm_agent.population):
                    if not self.trading_active:
                        break
                    log = f"\n🤖 Индивид {i+1}: {ind.describe()}"
                    self.add_terminal_message(log, "INFO")
                    self.rmm_logs.append({'generation': self.rmm_agent.generation+1, 'individual': i+1, 'params': ind.describe(), 'actions': []})
                    fitness, errors, actions = self._simulate_trading(ind, symbols, timeframe, trades_per_individual)
                    ind.fitness = fitness
                    for err in errors:
                        self.add_terminal_message(f"❌ Ошибка: {err}", "ERROR")
                        self.rmm_logs[-1]['actions'].append({'error': err})
                    for act in actions:
                        self.add_terminal_message(f"📝 {act}", "INFO")
                        self.rmm_logs[-1]['actions'].append({'action': act})
                    self._update_trading_stats(fitness)
                if not self.trading_active:
                    break
                self.rmm_agent.log_population()
                self.rmm_agent.evolve()
                generation += 1
                # Показываем статистику после каждого поколения
                self.show_learning_statistics()
            self.add_terminal_message("🏁 Эволюционное обучение завершено", "SUCCESS")
            # Сохраняем базу знаний
            try:
                kb_file = self.rmm_agent.save_knowledge_base()
                self.add_terminal_message(f"💾 База знаний сохранена: {kb_file}", "SUCCESS")
                # Показываем статистику обучения
                stats = self.rmm_agent.get_learning_statistics()
                self.add_terminal_message(f"📊 Статистика обучения:", "INFO")
                self.add_terminal_message(f"   • Поколений: {stats['generation']}", "INFO")
                self.add_terminal_message(f"   • Всего сделок: {stats['total_trades']}", "INFO")
                self.add_terminal_message(f"   • Всего ошибок: {stats['total_errors']}", "INFO")
                self.add_terminal_message(f"   • Средний winrate: {stats['avg_winrate']:.1f}%", "INFO")
                self.add_terminal_message(f"   • Лучший winrate: {stats['best_winrate']:.1f}%", "INFO")
                self.add_terminal_message(f"   • Размер базы знаний: {stats['knowledge_base_size']} записей", "INFO")
            except Exception as e:
                self.add_terminal_message(f"❌ Ошибка сохранения базы знаний: {e}", "ERROR")
            self.add_terminal_message("⏹️ Торговый цикл остановлен по запросу пользователя", "WARNING")
            print("[DEBUG] Эволюционное обучение завершено")
        except Exception as e:
            import traceback
            self.add_terminal_message(f"❌ Критическая ошибка эволюционного цикла: {e}", "ERROR")
            self.add_terminal_message(traceback.format_exc(), "ERROR")
            print(f"[DEBUG] Критическая ошибка: {e}")

    def _simulate_trading(self, ind, symbols, timeframes, trades_per_individual):
        """Симуляция торговли для одного индивида с использованием реальных исторических данных"""
        # Используем текущий баланс агрессивной системы вместо сброса к 100
        balance = self.aggressive_system.current_balance
        win_trades = 0
        total_trades = 0
        errors = []
        actions = []
        open_positions = []
        margin_call_count = 0
        
        # Загружаем и фильтруем данные по периоду торговли
        historical_data = {}
        for symbol in symbols:
            for tf in timeframes:
                try:
                    # Проверяем доступность загрузчика данных
                    if self.data_loader is None:
                        self.add_terminal_message("❌ Загрузчик исторических данных недоступен", "ERROR")
                        return 0.0, ["Нет загрузчика данных"], []
                    
                    # Загружаем данные для символа и таймфрейма
                    data = self.data_loader.get_coin_data(symbol, tf)
                    if data is not None and len(data) > 0:
                        # Фильтруем по периоду торговли
                        filtered_data = self._filter_data_by_period(
                            data, 
                            self.trading_period['start_date'], 
                            self.trading_period['end_date']
                        )
                        if len(filtered_data) > 0:
                            historical_data[f"{symbol}_{tf}"] = filtered_data
                            self.add_terminal_message(f"📊 Загружено {len(filtered_data)} свечей для {symbol} {tf} в периоде {self.trading_period['start_date']} - {self.trading_period['end_date']}", "DEBUG")
                        else:
                            self.add_terminal_message(f"⚠️ Нет данных для {symbol} {tf} в указанном периоде", "WARNING")
                except Exception as e:
                    self.add_terminal_message(f"❌ Ошибка загрузки данных {symbol} {tf}: {e}", "ERROR")
        
        if not historical_data:
            self.add_terminal_message("❌ Нет доступных исторических данных для торговли", "ERROR")
            return 0.0, ["Нет данных"], []
        
        self.add_terminal_message(f"📅 Торговля на исторических данных: {self.trading_period['start_date']} - {self.trading_period['end_date']}", "INFO")
        
        t = 0
        while t < trades_per_individual:
            try:
                # Выбираем случайный символ и таймфрейм
                symbol = random.choice(symbols)
                tf = random.choice(timeframes)
                data_key = f"{symbol}_{tf}"
                
                if data_key not in historical_data or len(historical_data[data_key]) == 0:
                    continue
                
                # Выбираем случайную свечу из исторических данных
                candle = historical_data[data_key].iloc[random.randint(0, len(historical_data[data_key]) - 1)]
                
                # Используем реальные цены из свечи
                open_price = float(candle['open'])
                high_price = float(candle['high'])
                low_price = float(candle['low'])
                close_price = float(candle['close'])
                volume = float(candle['volume'])
                candle_time = candle['open_time']
                
                direction = random.choice(['LONG', 'SHORT'])
                entry_price = open_price  # Входим по цене открытия свечи
                
                # ПРАВИЛЬНЫЙ РАСЧЕТ С УЧЕТОМ ПЛЕЧА
                risk_amount = balance * ind.position_size
                leverage = ind.leverage
                position_size = (risk_amount * leverage) / entry_price
                margin_used = risk_amount / leverage
                open_time = candle_time.strftime('%Y-%m-%d %H:%M:%S')
                
                pos = {
                    'symbol': symbol,
                    'size': position_size,
                    'entry_price': entry_price,
                    'leverage': leverage,
                    'side': direction,
                    'budget': risk_amount,
                    'margin_used': margin_used,
                    'pnl_dollars': 0,
                    'pnl_pct': 0,
                    'open': True,
                    'open_time': open_time,
                    'close_time': None
                }
                open_positions.append(pos)
                actions.append(f"Открыта позиция: {symbol} {direction} размер {position_size:.4f} по цене {entry_price:.2f} (риск ${risk_amount:.2f}, плечо {leverage}x, маржа ${margin_used:.2f}) в {open_time}")
                
                # Симулируем результат сделки на основе реальных данных
                # Используем волатильность свечи для определения вероятности выигрыша
                candle_volatility = (high_price - low_price) / open_price
                
                # БАЗОВЫЙ ВИНРЕЙТ - более реалистичный подход
                base_winrate = 0.45  # Базовый винрейт 45% (ближе к реальности)
                
                # Корректируем winrate на основе РЕАЛЬНЫХ рыночных условий
                # Вместо искусственных бонусов используем анализ свечи
                
                # Анализируем тренд свечи
                candle_trend = 'bullish' if close_price > open_price else 'bearish'
                
                # Корректируем на основе направления сделки и тренда свечи
                if (direction == 'LONG' and candle_trend == 'bullish') or (direction == 'SHORT' and candle_trend == 'bearish'):
                    base_winrate += 0.05  # +5% если направление совпадает с трендом
                
                # Корректируем на основе волатильности
                if candle_volatility > 0.05:  # Высокая волатильность
                    base_winrate -= 0.1  # -10% при высокой волатильности
                elif candle_volatility < 0.01:  # Низкая волатильность
                    base_winrate += 0.05  # +5% при низкой волатильности
                
                # Добавляем небольшой элемент случайности
                winrate = min(0.65, max(0.25, base_winrate + random.uniform(-0.05, 0.05)))
                
                is_win = random.random() < winrate
                
                # Рассчитываем PnL на основе реальных цен
                if is_win:
                    if direction == 'LONG':
                        exit_price = close_price  # Выходим по цене закрытия
                    else:  # SHORT
                        exit_price = low_price  # Для шорта используем минимум свечи
                    pnl_pct = (exit_price - entry_price) / entry_price if direction == 'LONG' else (entry_price - exit_price) / entry_price
                else:
                    if direction == 'LONG':
                        exit_price = low_price  # Для проигрышного лонга используем минимум
                    else:  # SHORT
                        exit_price = high_price  # Для проигрышного шорта используем максимум
                    pnl_pct = (exit_price - entry_price) / entry_price if direction == 'LONG' else (entry_price - exit_price) / entry_price
                
                pnl = risk_amount * pnl_pct * leverage
                commission_rate = 0.0004
                position_volume = position_size * entry_price
                commission = position_volume * commission_rate * 2
                final_pnl = pnl - commission
                old_balance = balance
                balance += final_pnl
                
                self.add_terminal_message(f"[РЕАЛЬНЫЕ ДАННЫЕ] Свеча: {open_time} | O:{open_price:.2f} H:{high_price:.2f} L:{low_price:.2f} C:{close_price:.2f}", "DEBUG")
                self.add_terminal_message(f"[РЕАЛЬНЫЕ ДАННЫЕ] Волатильность: {candle_volatility:.3f} | Тренд: {candle_trend}", "DEBUG")
                self.add_terminal_message(f"[РЕАЛЬНЫЕ ДАННЫЕ] Винрейт: {winrate:.1%} | Результат: {'ПОБЕДА' if is_win else 'ПОРАЖЕНИЕ'}", "DEBUG")
                self.add_terminal_message(f"[РЕАЛЬНЫЕ ДАННЫЕ] PnL: ${final_pnl:+.2f} ({pnl_pct*100:+.1f}% * {leverage}x)", "DEBUG")
                
                pos['pnl_dollars'] = final_pnl
                pos['pnl_pct'] = final_pnl / risk_amount if risk_amount > 0 else 0
                pos['open'] = False
                close_time = candle_time.strftime('%Y-%m-%d %H:%M:%S')
                pos['close_time'] = close_time
                
                trade_data = {
                    'win': is_win,
                    'symbol': symbol,
                    'timeframe': tf,
                    'direction': direction,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': final_pnl,
                    'pnl_pct': final_pnl / risk_amount if risk_amount > 0 else 0,
                    'size': position_size,
                    'leverage': leverage,
                    'budget': risk_amount,
                    'margin_used': margin_used,
                    'commission': commission,
                    'duration': 'instant',
                    'open_time': open_time,
                    'close_time': close_time,
                    'market_conditions': {
                        'volatility': candle_volatility,
                        'trend': candle_trend,
                        'volume': volume,
                        'candle_range': high_price - low_price
                    }
                }
                ind.update_history(trade_data)
                if is_win:
                    win_trades += 1
                total_trades += 1
                actions.append(f"Закрыта позиция: {symbol} {direction} PnL {final_pnl:+.2f} (комиссия: {commission:.2f}) Баланс: {balance:.2f} в {close_time}")
                current_winrate = (win_trades / total_trades) * 100
                actions.append(f"Winrate по текущим параметрам за {len(ind.trade_history)} сделок: {current_winrate:.1f}%")
                if current_winrate < 40:
                    actions.append("❗ Агент замечает, что winrate низкий — будет мутировать параметры")
                elif current_winrate > 60:
                    actions.append("✅ Агент доволен winrate и будет стараться закрепить успех")
                self._update_positions_table(open_positions)
                open_positions = [p for p in open_positions if p['open']]
                analysis = self.knowledge_analyzer.analyze_trade_result(trade_data) if hasattr(self.knowledge_analyzer, 'analyze_trade_result') else None
                if analysis:
                    self.add_terminal_message(f"[Анализ сделки] {analysis}", "INFO")
                # Margin-call: если баланс <= 0, закрываем все позиции, логируем и перезапускаем симуляцию
                if balance <= 0:
                    margin_call_count += 1
                    self.add_terminal_message(f"❌ MARGIN CALL! Баланс ушел в минус (${balance:.2f}). Все позиции закрыты. Перезапуск симуляции с $100.", "ERROR")
                    # Закрываем все открытые позиции
                    for p in open_positions:
                        p['open'] = False
                        p['close_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    open_positions.clear()
                    # Сброс баланса
                    balance = 100.0
                    # Можно добавить паузу или анализ, если нужно
                else:
                    t += 1
                # Динамическое управление риском (как в агрессивной системе)
                if total_trades >= 5:
                    recent_trades = total_trades - 5
                    recent_wins = win_trades - (total_trades - 5) if total_trades > 5 else win_trades
                    recent_winrate = (recent_wins / 5) * 100 if total_trades >= 5 else 0
                    old_risk = ind.position_size
                    if recent_winrate > 60 and ind.position_size < 0.03:
                        ind.position_size = min(ind.position_size + 0.002, 0.03)
                        self.add_terminal_message(f"[РИСК] ⬆️ Увеличен до {ind.position_size*100:.1f}% (winrate: {recent_winrate:.1f}%)", "INFO")
                    elif recent_winrate < 40 and ind.position_size > 0.005:
                        ind.position_size = max(ind.position_size - 0.002, 0.005)
                        self.add_terminal_message(f"[РИСК] ⬇️ Уменьшен до {ind.position_size*100:.1f}% (winrate: {recent_winrate:.1f}%)", "INFO")
                    if ind.position_size != old_risk:
                        self.add_terminal_message(f"[РИСК] Новый риск: {ind.position_size*100:.1f}% от баланса", "INFO")
            except Exception as e:
                error_msg = f"Ошибка в сделке {t+1}: {e}"
                errors.append(error_msg)
                self.add_terminal_message(error_msg, "ERROR")
                ind.record_error({
                    'error_type': 'simulation_error',
                    'error_message': error_msg,
                    'trade_number': t+1
                })
        # Рассчитываем фитнес (приоритет: winrate > общий PnL > количество сделок)
        if total_trades == 0:
            fitness = 0.0
        else:
            winrate = (win_trades / total_trades) * 100
            total_pnl = balance - 100.0
            pnl_ratio = total_pnl / 100.0
            fitness = (winrate * 0.6) + (pnl_ratio * 100 * 0.3) + (min(total_trades / 10, 1.0) * 100 * 0.1)
        old_aggressive_balance = self.aggressive_system.current_balance
        self.aggressive_system.current_balance = balance
        self.add_terminal_message(f"[СИНХРОНИЗАЦИЯ] Баланс эволюционного агента: ${balance:.2f}", "DEBUG")
        self.add_terminal_message(f"[СИНХРОНИЗАЦИЯ] Баланс агрессивной системы: ${old_aggressive_balance:.2f} → ${self.aggressive_system.current_balance:.2f}", "DEBUG")
        self.add_terminal_message(f"[СИНХРОНИЗАЦИЯ] Без масштабирования - одинаковый баланс", "DEBUG")
        for trade_data in ind.trade_history[-total_trades:]:
            if 'pnl' in trade_data:
                closed_position = {
                    'symbol': trade_data.get('symbol', 'UNKNOWN'),
                    'direction': trade_data.get('direction', 'LONG'),
                    'entry_price': trade_data.get('entry_price', 0),
                    'close_price': trade_data.get('exit_price', 0),
                    'size': trade_data.get('size', 0),
                    'pnl': trade_data.get('pnl', 0),
                    'pnl_pct': trade_data.get('pnl_pct', 0),
                    'commission': trade_data.get('commission', 0),
                    'close_time': datetime.now(),
                    'reason': 'Evolutionary Trade'
                }
                self.aggressive_system.closed_positions.append(closed_position)
        self.add_terminal_message(f"[MARGIN CALL] Количество margin-call за симуляцию: {margin_call_count}", "WARNING")
        # Явно возвращаем результат для предотвращения ошибки распаковки
        return fitness, errors, actions
    
    def _update_positions_table(self, positions):
        """Обновляет таблицу открытых позиций в UI (добавлены даты открытия/закрытия)"""
        try:
            if hasattr(self.ui, 'positions_table'):
                open_pos = [p for p in positions if p.get('open', False)]
                for row in self.ui.positions_table.get_children():
                    self.ui.positions_table.delete(row)
                for pos in open_pos:
                    symbol = pos.get('symbol', '')
                    size = f"{pos.get('size', 0):.4f} {symbol.replace('USDT','')}"
                    entry = f"{pos.get('entry_price', 0):.2f}"
                    breakeven = f"{pos.get('entry_price', 0):.2f}"
                    mark = f"{pos.get('entry_price', 0):.2f}"
                    leverage = pos.get('leverage', 1)
                    side = pos.get('side', 'LONG')
                    if side == 'LONG':
                        liq = f"{pos.get('entry_price', 0) * (1 - 1/max(leverage,1)):.2f}"
                    else:
                        liq = f"{pos.get('entry_price', 0) * (1 + 1/max(leverage,1)):.2f}"
                    margin_rate = f"{100/max(leverage,1):.2f}%"
                    margin = f"{(pos.get('size',0)*pos.get('entry_price',0)/max(leverage,1)):.2f} USDT"
                    pnl = f"{pos.get('pnl_dollars',0):+.2f} USDT ({pos.get('pnl_pct',0)*100:+.2f}%)"
                    stop = "-"
                    take = "-"
                    open_time = pos.get('open_time', '-')
                    close_time = pos.get('close_time', '-')
                    iid = self.ui.positions_table.insert("", "end", values=(symbol, size, entry, breakeven, mark, liq, margin_rate, margin, pnl, stop, take, open_time))
                    self.ui.positions_table.set(iid, column="Действия", value="Закрыть")
        except Exception as e:
            pass

    def _update_trading_stats(self, fitness):
        """Обновляет торговую статистику в UI"""
        try:
            # Получаем правильный статус торговли вместо использования fitness
            status = self.get_trading_status()
            balance = status['balance']
            winrate = status['winrate']
            
            if hasattr(self.ui, 'trading_stats_labels'):
                self.ui.trading_stats_labels["💰 Баланс: $100.00"].config(text=f"💰 Баланс: ${balance:,.2f}")
                self.ui.trading_stats_labels["📈 Винрейт: 0.0%"].config(text=f"📈 Винрейт: {winrate:.1f}%")
        except Exception as e:
            pass

    def get_trading_status(self) -> Dict:
        """Возвращает статус торговли"""
        try:
            return {
                'active': self.trading_active,
                'balance': self.aggressive_system.current_balance,
                'open_positions': len(self.aggressive_system.open_positions),
                'total_trades': len(self.aggressive_system.closed_positions),
                'winrate': self._calculate_winrate(),
                'total_pnl': self._calculate_total_pnl()
            }
        except Exception as e:
            return {
                'active': False,
                'balance': 100.0,
                'open_positions': 0,
                'total_trades': 0,
                'winrate': 0.0,
                'total_pnl': 0.0
            }

    def _calculate_winrate(self) -> float:
        """Рассчитывает винрейт"""
        try:
            if len(self.aggressive_system.closed_positions) == 0:
                return 0.0
            
            winning_trades = sum(1 for p in self.aggressive_system.closed_positions if p['pnl'] > 0)
            return (winning_trades / len(self.aggressive_system.closed_positions)) * 100
        except:
            return 0.0

    def _calculate_total_pnl(self) -> float:
        """Рассчитывает общий P&L"""
        try:
            return sum(p['pnl'] for p in self.aggressive_system.closed_positions)
        except:
            return 0.0
    
    def set_analysis_period(self, start_date: str, end_date: str):
        """Установка периода для анализа исторических данных"""
        try:
            # Обновляем период
            self.analysis_period['start_date'] = start_date
            self.analysis_period['end_date'] = end_date
            
            # Проверяем доступность загрузчика
            if not self.data_loader:
                self.ui.add_terminal_message("❌ Загрузчик исторических данных недоступен", "ERROR")
                return
            
            # Тестируем загрузку данных для BTCUSDT
            test_data = self.data_loader.get_coin_data(
                'BTCUSDT', '1h', 
                start_date=start_date, 
                end_date=end_date
            )
            
            if len(test_data) > 0:
                self.ui.add_terminal_message(
                    f"✅ Период установлен: {start_date} - {end_date} | "
                    f"Данных: {len(test_data)} строк", 
                    "SUCCESS"
                )
                
                # Запускаем анализ на основе нового периода
                self.run_period_analysis()
            else:
                self.ui.add_terminal_message(
                    f"⚠️ Для периода {start_date} - {end_date} данных не найдено", 
                    "ERROR"
                )
                
        except Exception as e:
            self.ui.add_terminal_message(f"❌ Ошибка установки периода: {str(e)}", "ERROR")
    
    def run_period_analysis(self):
        """Запуск анализа на основе выбранного периода"""
        try:
            if not self.data_loader:
                return
            
            start_date = self.analysis_period['start_date']
            end_date = self.analysis_period['end_date']
            
            # Анализируем топ-5 монет
            top_coins = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
            
            analysis_results = []
            for coin in top_coins:
                # Загружаем данные для 1h таймфрейма
                data = self.data_loader.get_coin_data(coin, '1h', start_date, end_date)
                
                if len(data) > 0:
                    # Простой анализ: средняя цена, волатильность, тренд
                    avg_price = data['close'].mean()
                    volatility = data['close'].std() / avg_price * 100
                    
                    # Определяем тренд (сравниваем начало и конец периода)
                    start_price = data.iloc[0]['close']
                    end_price = data.iloc[-1]['close']
                    trend = ((end_price - start_price) / start_price) * 100
                    
                    analysis_results.append({
                        'coin': coin,
                        'avg_price': avg_price,
                        'volatility': volatility,
                        'trend': trend,
                        'data_points': len(data)
                    })
            
            # Выводим результаты в терминал
            if analysis_results:
                self.ui.add_terminal_message("📊 Анализ исторических данных:", "INFO")
                for result in analysis_results:
                    trend_icon = "📈" if result['trend'] > 0 else "📉"
                    self.ui.add_terminal_message(
                        f"{trend_icon} {result['coin']}: "
                        f"Средняя цена: ${result['avg_price']:.2f}, "
                        f"Волатильность: {result['volatility']:.1f}%, "
                        f"Тренд: {result['trend']:+.1f}%, "
                        f"Данных: {result['data_points']}",
                        "INFO"
                    )
            
        except Exception as e:
            self.ui.add_terminal_message(f"❌ Ошибка анализа периода: {str(e)}", "ERROR")
    
    def analyze_knowledge_base(self):
        """Анализирует базу знаний и генерирует отчет"""
        try:
            self.add_terminal_message("🧠 АНАЛИЗ БАЗЫ ЗНАНИЙ ЗАПУЩЕН", "INFO")
            self.add_terminal_message("📊 Загружаю данные для анализа...", "INFO")
            
            # Загружаем данные
            self.knowledge_analyzer.load_knowledge_base()
            self.knowledge_analyzer.load_individuals_data()
            
            # Создаем DataFrame
            self.knowledge_analyzer.create_trades_dataframe()
            self.knowledge_analyzer.create_errors_dataframe()
            
            # Анализируем паттерны
            self.add_terminal_message("🔍 Анализирую успешные паттерны...", "INFO")
            success_patterns = self.knowledge_analyzer.analyze_successful_patterns()
            
            if success_patterns:
                self.add_terminal_message(f"✅ Успешные паттерны найдены:", "SUCCESS")
                self.add_terminal_message(f"   • Общий winrate: {success_patterns['winrate']}%", "INFO")
                self.add_terminal_message(f"   • Всего сделок: {success_patterns['total_trades']}", "INFO")
                self.add_terminal_message(f"   • Средний PnL: {success_patterns['avg_pnl']:.4f}", "INFO")
            
            # Анализируем ошибки
            self.add_terminal_message("🔍 Анализирую паттерны ошибок...", "INFO")
            error_patterns = self.knowledge_analyzer.analyze_error_patterns()
            
            if error_patterns:
                self.add_terminal_message(f"❌ Паттерны ошибок найдены:", "WARNING")
                self.add_terminal_message(f"   • Всего ошибок: {error_patterns['total_errors']}", "INFO")
                if 'error_types' in error_patterns and not error_patterns['error_types'].empty:
                    top_error = error_patterns['error_types'].iloc[0]
                    # Исправление: корректно выводим тип ошибки и количество
                    if hasattr(top_error, 'name'):
                        self.add_terminal_message(f"   • Частая ошибка: {top_error.name} ({top_error} раз)", "INFO")
                    elif isinstance(top_error, tuple) and len(top_error) == 2:
                        self.add_terminal_message(f"   • Частая ошибка: {top_error[0]} ({top_error[1]} раз)", "INFO")
                    else:
                        self.add_terminal_message(f"   • Частая ошибка: {top_error} раз", "INFO")
            
            # Находим оптимальные параметры
            self.add_terminal_message("🎯 Ищу оптимальные параметры...", "INFO")
            optimal_params = self.knowledge_analyzer.find_optimal_parameters()
            
            if optimal_params and 'recommendations' in optimal_params:
                self.add_terminal_message("🎯 РЕКОМЕНДАЦИИ НАЙДЕНЫ:", "SUCCESS")
                for rec in optimal_params['recommendations']:
                    self.add_terminal_message(f"   • {rec}", "INFO")
            
            # Сохраняем отчет
            report_file = self.knowledge_analyzer.save_analysis_report()
            self.add_terminal_message(f"📄 Полный отчет сохранен: {report_file}", "SUCCESS")
            
            # Показываем краткую сводку
            self.add_terminal_message("📊 КРАТКАЯ СВОДКА АНАЛИЗА:", "INFO")
            stats = self.knowledge_analyzer.get_learning_statistics() if hasattr(self.knowledge_analyzer, 'get_learning_statistics') else {}
            if stats:
                self.add_terminal_message(f"   • Индивидов проанализировано: {len(self.knowledge_analyzer.individuals_data)}", "INFO")
                if self.knowledge_analyzer.trades_df is not None:
                    self.add_terminal_message(f"   • Сделок в базе: {len(self.knowledge_analyzer.trades_df)}", "INFO")
                if self.knowledge_analyzer.errors_df is not None:
                    self.add_terminal_message(f"   • Ошибок в базе: {len(self.knowledge_analyzer.errors_df)}", "INFO")
            
            self.add_terminal_message("🏁 АНАЛИЗ БАЗЫ ЗНАНИЙ ЗАВЕРШЕН", "SUCCESS")
            
        except Exception as e:
            import traceback
            self.add_terminal_message(f"❌ Ошибка анализа базы знаний: {e}", "ERROR")
            self.add_terminal_message(traceback.format_exc(), "ERROR")
    
    def sync_knowledge_to_github(self):
        """Синхронизация базы знаний с GitHub"""
        try:
            self.add_terminal_message("🔄 Запуск синхронизации с GitHub...", "INFO")
            
            # Синхронизируем с GitHub
            self.sync_manager.sync_after_learning("🤖 Обновление базы знаний после обучения")
            
            # Показываем статус синхронизации
            status_msg = self.sync_manager.get_sync_status_message()
            self.add_terminal_message(status_msg, "INFO")
            
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка синхронизации: {e}", "ERROR")
    
    def sync_knowledge_from_github(self):
        """Загрузка базы знаний с GitHub"""
        try:
            self.add_terminal_message("📥 Загрузка базы знаний с GitHub...", "INFO")
            
            # Загружаем с GitHub
            self.sync_manager.sync_before_learning()
            
            # Показываем статус синхронизации
            status_msg = self.sync_manager.get_sync_status_message()
            self.add_terminal_message(status_msg, "INFO")
            
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка загрузки: {e}", "ERROR")
    
    def get_sync_status(self) -> str:
        """Возвращает статус синхронизации с GitHub"""
        try:
            if hasattr(self, 'sync_manager') and self.sync_manager:
                return self.sync_manager.get_status()
            return "Не настроена"
        except Exception as e:
            return f"Ошибка: {str(e)}"

    def get_learning_statistics(self) -> dict:
        """Получает статистику обучения для отображения"""
        try:
            # Собираем статистику из всех источников
            stats = {
                'total_trades': 0,
                'winrate': 0.0,
                'total_pnl': 0.0,
                'balance': 100.0,
                'generation': 0,
                'best_fitness': 0.0,
                'learning_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Статистика из агрессивной системы
            if hasattr(self, 'aggressive_system'):
                closed_positions = self.aggressive_system.closed_positions
                stats['total_trades'] = len(closed_positions)
                stats['balance'] = self.aggressive_system.current_balance
                
                if stats['total_trades'] > 0:
                    winning_trades = len([p for p in closed_positions if p.get('pnl', 0) > 0])
                    stats['winrate'] = (winning_trades / stats['total_trades']) * 100
                    stats['total_pnl'] = sum([p.get('pnl', 0) for p in closed_positions])
            
            # Статистика из эволюционного агента
            if hasattr(self, 'rmm_agent'):
                stats['generation'] = getattr(self.rmm_agent, 'generation', 0)
                # Получаем лучший fitness из истории поколений
                if hasattr(self.rmm_agent, 'knowledge_base') and self.rmm_agent.knowledge_base.get('generation_history'):
                    best_fitness = max([gen.get('best_fitness', 0) for gen in self.rmm_agent.knowledge_base['generation_history']])
                    stats['best_fitness'] = best_fitness
            
            return stats
            
        except Exception as e:
            return {'error': str(e)}

    def show_learning_statistics(self):
        """
        Отображает лаконичную статистику обучения в терминале
        Формат: как в версии 1 на гите
        """
        stats = self.get_learning_statistics()
        # Целевые значения
        target_winrate = 70.0
        target_pnl = 100.0
        target_trades = 1000
        # % выполнения целей
        winrate_progress = min(stats['winrate'] / target_winrate * 100, 100) if target_winrate else 0
        pnl_progress = min(stats['total_pnl'] / target_pnl * 100, 100) if target_pnl else 0
        trades_progress = min(stats['total_trades'] / target_trades * 100, 100) if target_trades else 0
        # Формируем строку
        summary = (
            f"\n=== 📊 СТАТИСТИКА ОБУЧЕНИЯ ===\n"
            f"Winrate: {stats['winrate']:.1f}% (цель: {target_winrate}%) | Выполнение: {winrate_progress:.0f}%\n"
            f"PnL: ${stats['total_pnl']:+.2f} (цель: ${target_pnl:+.2f}) | Выполнение: {pnl_progress:.0f}%\n"
            f"Сделок: {stats['total_trades']} (цель: {target_trades}) | Выполнение: {trades_progress:.0f}%\n"
            f"Баланс: ${stats['balance']:.2f}\n"
            f"Поколение: {stats['generation']} | Лучший fitness: {stats['best_fitness']:.2f}\n"
            f"Время: {stats['learning_time']}\n"
            f"============================\n"
        )
        self.add_terminal_message(summary, "INFO")

    def start_turbo_learning(self):
        """Запускает максимально быстрое обучение бота"""
        try:
            self.add_terminal_message("🚀 ЗАПУСК МАКСИМАЛЬНО БЫСТРОГО ОБУЧЕНИЯ", "SUCCESS")
            self.add_terminal_message("⚡ Турбо-режим: без задержек, без вывода в терминал", "INFO")
            self.add_terminal_message("🎯 Цель: максимум ошибок и опыта за минимальное время", "INFO")
            self.add_terminal_message("")
            
            # Включаем турбо-режим
            self.trading_settings['turbo_mode'] = True
            self.trading_settings['silent_mode'] = True
            self.trading_settings['auto_trading'] = True
            self.trading_active = True
            
            # Увеличиваем параметры для быстрого обучения
            if hasattr(self, 'rmm_agent'):
                self.rmm_agent.population_size = 50  # Больше индивидов
                self.rmm_agent.mutation_rate = 0.3   # Больше мутаций
                self.rmm_agent.elite_frac = 0.1      # Меньше элиты для большего разнообразия
            
            # Запускаем эволюционный цикл
            self._evolutionary_trading_loop()
            
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка запуска турбо-обучения: {str(e)}", "ERROR")

    def stop_turbo_learning(self):
        """Останавливает турбо-обучение"""
        try:
            self.add_terminal_message("⏹️ ОСТАНОВКА ТУРБО-ОБУЧЕНИЯ", "WARNING")
            
            # Отключаем турбо-режим
            self.trading_settings['turbo_mode'] = False
            self.trading_settings['silent_mode'] = False
            self.trading_active = False
            
            # Показываем финальную статистику
            self.show_learning_statistics()
            
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка остановки турбо-обучения: {str(e)}", "ERROR")

    def set_trading_period(self, start_date: str, end_date: str):
        """Установка периода для торговли"""
        try:
            from datetime import datetime
            # Проверяем корректность дат
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
            
            self.trading_period['start_date'] = start_date
            self.trading_period['end_date'] = end_date
            
            self.add_terminal_message(f"📅 Период торговли установлен: {start_date} - {end_date}", "INFO")
            
            # Выводим информацию о доступных данных для этого периода
            self._show_trading_period_info()
            
        except ValueError as e:
            self.add_terminal_message(f"❌ Ошибка формата даты: {e}. Используйте формат YYYY-MM-DD", "ERROR")
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка установки периода торговли: {e}", "ERROR")

    def _show_trading_period_info(self):
        """Показывает информацию о доступных данных для текущего периода торговли"""
        try:
            if self.data_loader is None:
                return
                
            # Проверяем данные для BTCUSDT на 1h таймфрейме
            btc_data = self.data_loader.get_coin_data('BTCUSDT', '1h')
            if len(btc_data) > 0:
                filtered_data = self._filter_data_by_period(
                    btc_data, 
                    self.trading_period['start_date'], 
                    self.trading_period['end_date']
                )
                
                self.add_terminal_message(f"📊 Данные для торговли:", "INFO")
                self.add_terminal_message(f"   • Период: {self.trading_period['start_date']} - {self.trading_period['end_date']}", "INFO")
                self.add_terminal_message(f"   • Доступно свечей BTC: {len(filtered_data)}", "INFO")
                
                if len(filtered_data) > 0:
                    min_date = filtered_data['open_time'].min().strftime('%Y-%m-%d')
                    max_date = filtered_data['open_time'].max().strftime('%Y-%m-%d')
                    self.add_terminal_message(f"   • Реальный диапазон: {min_date} - {max_date}", "INFO")
                else:
                    self.add_terminal_message(f"   • ⚠️ Нет данных в указанном периоде", "WARNING")
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка получения информации о периоде: {e}", "ERROR")

    def _filter_data_by_period(self, data, start_date, end_date):
        """Фильтрует данные по указанному периоду"""
        try:
            import pandas as pd
            # Конвертируем строки дат в pandas Timestamp
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            
            # Фильтруем данные по дате (open_time уже является pandas Timestamp)
            filtered_data = data[
                (data['open_time'] >= start_dt) & 
                (data['open_time'] <= end_dt)
            ]
            
            return filtered_data
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка фильтрации данных: {e}", "ERROR")
            return data  # Возвращаем исходные данные при ошибке