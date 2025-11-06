#!/usr/bin/env python3
"""
🤖 BOT CORE - Основная логика бота
Вынесено из main.py для реструктуризации
"""

import asyncio
import logging
import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class BotCore:
    """Основная логика бота - вынесена из main.py"""
    
    def __init__(self, bot_instance):
        """Инициализация с ссылкой на основной класс бота"""
        self.bot = bot_instance
    
    def _get_strictness_params(self):
        """Получить параметры анализа на основе текущей жесткости (три режима)"""
        if self.bot.strictness_percent <= 25:  # КОНСЕРВАТИВНАЯ
            return {
                'min_confidence': 95.0,
                'min_trades': 2,
                'max_price_diff': 0.001
            }
        elif self.bot.strictness_percent <= 75:  # УМЕРЕННАЯ
            return {
                'min_confidence': 50.0,
                'min_trades': 6,
                'max_price_diff': 0.002
            }
        else:  # АГРЕССИВНАЯ
            return {
                'min_confidence': 30.0,
                'min_trades': 12,
                'max_price_diff': 0.005
            }
    
    def _calculate_trades_required(self, signal, strictness_params):
        """Рассчитать требуемое количество сделок в зависимости от режима"""
        min_trades_required = strictness_params['min_trades']
        
        if self.bot.strictness_percent > 75:  # Агрессивная
            if signal.confidence >= 90:
                return max(10, min_trades_required - 2)
            elif signal.confidence >= 80:
                return max(10, min_trades_required - 1)
            return min_trades_required
        elif self.bot.strictness_percent > 25:  # Умеренная
            if signal.confidence >= 90:
                return 5
            elif signal.confidence >= 80:
                return max(5, min_trades_required - 1)
            return min_trades_required
        
        return min_trades_required  # Консервативная
    
    async def _update_positions(self):
        """Обновление открытых позиций"""
        for symbol in list(self.bot.paper_trader.positions.keys()):
            try:
                current_price = self.bot.binance_client.get_current_price(symbol)
                if current_price > 0:
                    closed_trade = self.bot.paper_trader.update_positions(symbol, current_price)
                    if closed_trade:
                        self._handle_closed_trade(closed_trade)
            except Exception as e:
                logger.error(f"Ошибка обновления позиции {symbol}: {e}")
    
    def _handle_closed_trade(self, closed_trade):
        """Обработка закрытой сделки"""
        self.bot.learning.learn_from_trade(closed_trade)
        
        # Обновляем производительность факторов
        signal = self.bot.current_signals.get(closed_trade.symbol)
        if signal and hasattr(signal, 'direction') and signal.direction != 'WAIT':
            factors = {
                'wall': getattr(signal, 'wall_score', 50),
                'spread': getattr(signal, 'spread_score', 50),
                'imbalance': getattr(signal, 'imbalance_score', 50),
                'aggression': getattr(signal, 'aggression_score', 50),
                'momentum': getattr(signal, 'momentum_score', 50),
                'fib': getattr(signal, 'fib_score', 50)
            }
            self.bot.signal_analyzer.update_factor_performance(factors, closed_trade.pnl > 0)
        
        # Обновляем GUI
        self._update_gui_after_close(closed_trade)
        
        # Логируем
        logger.info(
            f"{'✅' if closed_trade.pnl > 0 else '❌'} "
            f"Закрыта позиция {closed_trade.symbol}: "
            f"P&L ${closed_trade.pnl:.2f} ({closed_trade.pnl_percent:.2f}%)"
        )
    
    def _update_gui_after_close(self, closed_trade):
        """Обновление GUI после закрытия позиции"""
        current_prices_dict = {}
        for pos_symbol in self.bot.paper_trader.positions.keys():
            pos_price = self.bot.binance_client.get_current_price(pos_symbol)
            if pos_price > 0:
                current_prices_dict[pos_symbol] = pos_price
        
        self.bot._safe_gui_call(self.bot.gui.update_positions, 
                               self.bot.paper_trader.positions, current_prices_dict)
        
        if hasattr(self.bot.gui, 'update_history'):
            self.bot._safe_gui_call(self.bot.gui.update_history, self.bot.paper_trader.closed_trades)
        
        pnl_sign = "+" if closed_trade.pnl >= 0 else ""
        event_text = (
            f"{'✅' if closed_trade.pnl > 0 else '❌'} "
            f"Закрыта {closed_trade.symbol} {closed_trade.side}: "
            f"P&L {pnl_sign}${closed_trade.pnl:.2f} ({pnl_sign}{closed_trade.pnl_percent:.2f}%)"
        )
        self.bot._safe_gui_call(self.bot.gui.add_event, event_text, 
                               'success' if closed_trade.pnl > 0 else 'error')
    
    async def _analyze_signals(self):
        """Анализ сигналов для всех пар"""
        all_signals = []
        processed = 0
        
        for symbol in self.bot.pairs:
            try:
                orderbook = self.bot.binance_client.get_orderbook(symbol)
                window_seconds = self.bot.config['signals'].get('tape_window_seconds', 20)
                recent_trades = self.bot.binance_client.get_recent_trades(
                    symbol, 500, max(60, window_seconds)
                )
                
                if not orderbook.get('bids') or not orderbook.get('asks') or \
                   not orderbook['bids'] or not orderbook['asks']:
                    logger.debug(f"⏸️ {symbol}: Пустой стакан")
                    continue
                
                processed += 1
                
                # Анализируем сигнал
                signal = self.bot.signal_analyzer.analyze(symbol, orderbook, recent_trades)
                self.bot.current_signals[symbol] = signal
                
                # Получаем адаптивные параметры
                adaptive_params = self.bot.learning.get_adaptive_params(symbol, signal.direction)
                strictness_params = self._get_strictness_params()
                
                # Определяем минимальную уверенность
                if self.bot.strictness_percent > 75:
                    min_conf = strictness_params['min_confidence']
                else:
                    min_conf = max(adaptive_params['min_confidence'], 
                                 strictness_params['min_confidence'])
                
                # Логируем причины отказа
                if signal.direction in ['LONG', 'SHORT']:
                    if signal.confidence < min_conf:
                        logger.info(
                            f"⏸️ {symbol}: {signal.direction} - "
                            f"confidence={signal.confidence:.1f}% < {min_conf:.1f}% "
                            f"(min, режим={self.bot.strictness_percent:.0f}%)"
                        )
                
                # Если сигнал торговый - добавляем в список
                if signal.direction in ['LONG', 'SHORT'] and signal.confidence >= min_conf:
                    trades_required = self._calculate_trades_required(signal, strictness_params)
                    
                    if len(recent_trades) < trades_required:
                        logger.info(
                            f"⏸️ {symbol}: Недостаточно сделок "
                            f"({len(recent_trades)} < {trades_required}, "
                            f"режим={self.bot.strictness_percent:.0f}%)"
                        )
                        continue
                    
                    # Проверяем что нет позиции
                    if symbol not in self.bot.paper_trader.positions:
                        # Проверяем обучение
                        if self.bot.strictness_percent <= 75 and signal.confidence < 90:
                            if not self.bot.learning.should_trade_direction(symbol, signal.direction):
                                logger.info(
                                    f"⏸️ {symbol}: Направление {signal.direction} "
                                    f"заблокировано адаптивным обучением"
                                )
                                continue
                        
                        # Рассчитываем приоритет
                        expected_profit_percent = abs(
                            signal.take_profit_1 - signal.entry_price
                        ) / signal.entry_price
                        priority_score = signal.confidence * expected_profit_percent * 100
                        
                        all_signals.append({
                            'signal': signal,
                            'orderbook': orderbook,
                            'priority': priority_score,
                            'recent_trades': len(recent_trades),
                            'adaptive_params': adaptive_params
                        })
            
            except Exception as e:
                logger.error(f"Ошибка анализа {symbol}: {e}")
                continue
        
        logger.debug(f"📊 Обработано {processed}/{len(self.bot.pairs)} пар, сигналов: {len(all_signals)}")
        return all_signals
    
    async def _open_best_positions(self, all_signals):
        """Открытие лучших позиций"""
        all_signals.sort(key=lambda x: x['priority'], reverse=True)
        
        max_positions = self.bot.config['account']['max_positions']
        current_positions = len(self.bot.paper_trader.positions)
        
        for signal_data in all_signals:
            if current_positions >= max_positions:
                break
            
            signal = signal_data['signal']
            
            # Получаем актуальный стакан
            if signal.confidence >= 90:
                orderbook = signal_data.get('orderbook')
            else:
                orderbook = self.bot.binance_client.get_orderbook(signal.symbol)
            
            if not orderbook or not orderbook.get('bids') or not orderbook.get('asks'):
                logger.debug(f"⏸️ {signal.symbol}: Нет актуального стакана")
                continue
            
            # Проверяем изменение цены
            if self.bot.strictness_percent <= 75 and signal.confidence < 90:
                current_price = self.bot.binance_client.get_current_price(signal.symbol)
                if current_price == 0:
                    continue
                
                strictness_params = self._get_strictness_params()
                price_diff = abs(current_price - signal.entry_price) / signal.entry_price
                if price_diff > strictness_params['max_price_diff']:
                    logger.debug(
                        f"⏸️ {signal.symbol}: Цена изменилась {price_diff*100:.2f}% > "
                        f"{strictness_params['max_price_diff']*100:.2f}%, пропускаем"
                    )
                    continue
            
            # Открываем позицию
            adaptive_params = signal_data.get('adaptive_params', {})
            position = self.bot.paper_trader.open_position(signal, orderbook, adaptive_params)
            
            if position:
                current_positions += 1
                logger.info(
                    f"{'🟢' if position.side == 'LONG' else '🔴'} "
                    f"Открыта позиция {position.symbol} {position.side}: "
                    f"${position.entry_price:.2f} (плечо: {position.leverage}x, "
                    f"уверенность: {signal.confidence:.1f}%, "
                    f"приоритет: {signal_data['priority']:.1f})"
                )
    
    def _log_statistics(self):
        """Логирование статистики и автосохранение"""
        if self.bot._last_signal_log is not None:
            elapsed = (datetime.now() - self.bot._last_signal_log).total_seconds()
            if elapsed >= 60:
                long_count = sum(
                    1 for sig in self.bot.current_signals.values() 
                    if sig.direction == 'LONG'
                )
                short_count = sum(
                    1 for sig in self.bot.current_signals.values() 
                    if sig.direction == 'SHORT'
                )
                
                logger.info(
                    f"📊 Сигналы: LONG {long_count}, SHORT {short_count} "
                    f"из {len(self.bot.current_signals)} пар"
                )
                
                total_pnl = self.bot.paper_trader.balance - self.bot.paper_trader.starting_balance
                logger.info(f"💰 Баланс: ${self.bot.paper_trader.balance:.2f}, P&L: ${total_pnl:+.2f}")
                logger.info(self.bot.learning.get_learning_summary())
                
                # Автосохранение
                if self.bot.config['logging']['save_session']:
                    filename = f"results/autosave_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    Path("results").mkdir(exist_ok=True)
                    self.bot.paper_trader.save_session(filename)
                    logger.info(f"💾 Автосохранение: {filename}")
                
                self.bot._last_signal_log = datetime.now()
        else:
            self.bot._last_signal_log = datetime.now()

