#!/usr/bin/env python3
"""
🤖 BOT CORE - main trading logic extracted from main.py for modularity.
"""

import asyncio
import logging
import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class BotCore:
    """Primary bot logic extracted from main.py."""
    
    def __init__(self, bot_instance):
        """Initialise with a reference to the main bot instance."""
        self.bot = bot_instance
    
    def _get_strictness_params(self):
        """Return analysis parameters for current strictness (three modes)."""
        if self.bot.strictness_percent <= 25:  # Conservative
            return {
                'min_confidence': 95.0,
                'min_trades': 2,
                'max_price_diff': 0.001
            }
        elif self.bot.strictness_percent <= 75:  # Moderate
            return {
                'min_confidence': 50.0,
                'min_trades': 6,
                'max_price_diff': 0.002
            }
        else:  # Aggressive
            return {
                'min_confidence': 30.0,
                'min_trades': 12,
                'max_price_diff': 0.005
            }
    
    def _calculate_trades_required(self, signal, strictness_params):
        """Determine the number of trades required for the given mode."""
        # Lowered requirements - 3 trades minimum instead of 6+
        if signal.confidence >= 70:
            return 3
        elif signal.confidence >= 60:
            return 4
        else:
            return 5
    
    async def _update_positions(self):
        """Update open positions."""
        for symbol in list(self.bot.paper_trader.positions.keys()):
            try:
                current_price = self.bot.binance_client.get_current_price(symbol)
                if current_price > 0:
                    closed_trade = self.bot.paper_trader.update_positions(symbol, current_price)
                    if closed_trade:
                        self._handle_closed_trade(closed_trade)
            except Exception as e:
                logger.error(f"Failed to update position {symbol}: {e}")
    
    def _handle_closed_trade(self, closed_trade):
        """Handle closed trade bookkeeping."""
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
        
        # Refresh GUI
        self._update_gui_after_close(closed_trade)
        
        # Log outcome
        logger.info(
            f"{'✅' if closed_trade.pnl > 0 else '❌'} "
            f"Closed position {closed_trade.symbol}: "
            f"P&L ${closed_trade.pnl:.2f} ({closed_trade.pnl_percent:.2f}%)"
        )
    
    def _update_gui_after_close(self, closed_trade):
        """Refresh GUI after closing a position."""
        current_prices_dict = {}
        for pos_symbol in self.bot.paper_trader.positions.keys():
            pos_price = self.bot.binance_client.get_current_price(pos_symbol)
            if pos_price > 0:
                current_prices_dict[pos_symbol] = pos_price
        
        self.bot._safe_gui_call(self.bot.gui.update_positions_data, 
                               self.bot.paper_trader.positions, current_prices_dict)
        
        if hasattr(self.bot.gui, 'update_history'):
            self.bot._safe_gui_call(self.bot.gui.update_history, self.bot.paper_trader.closed_trades)
        
        pnl_sign = "+" if closed_trade.pnl >= 0 else ""
        event_text = (
            f"{'✅' if closed_trade.pnl > 0 else '❌'} "
            f"Closed {closed_trade.symbol} {closed_trade.side}: "
            f"P&L {pnl_sign}${closed_trade.pnl:.2f} ({pnl_sign}{closed_trade.pnl_percent:.2f}%)"
        )
        self.bot._safe_gui_call(self.bot.gui.add_event, event_text, 
                               'success' if closed_trade.pnl > 0 else 'error')
    
    async def _analyze_signals(self):
        """Analyse signals for every pair."""
        # Анализ сигналов всегда выполняется (убрана проверка paused)
        
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
                    logger.debug(f"⏸️ {symbol}: empty order book")
                    continue
                
                processed += 1
                
                # Analyse signal
                signal = self.bot.signal_analyzer.analyze(symbol, orderbook, recent_trades)
                self.bot.current_signals[symbol] = signal
                
                # Use default parameters (adaptive learning removed)
                adaptive_params = {
                    'min_confidence': self.bot.config['signals']['min_confidence'],
                    'position_size_multiplier': 1.0,
                    'leverage_multiplier': 1.0
                }
                strictness_params = self._get_strictness_params()
                
                # Determine minimum confidence threshold
                if self.bot.strictness_percent > 75:
                    min_conf = strictness_params['min_confidence']
                else:
                    min_conf = max(adaptive_params['min_confidence'], 
                                 strictness_params['min_confidence'])
                
                if signal.direction in ['LONG', 'SHORT']:
                    # Use small epsilon to handle float precision issues
                    if signal.confidence < min_conf - 0.01:
                        logger.info(
                            f"⏸️ {symbol}: {signal.direction} - "
                            f"confidence={signal.confidence:.1f}% < {min_conf:.1f}% "
                            f"(min, strictness={self.bot.strictness_percent:.0f}%)"
                        )
                        continue  # Skip this signal if confidence is too low
                
                if signal.direction in ['LONG', 'SHORT'] and signal.confidence >= min_conf:
                    trades_required = self._calculate_trades_required(signal, strictness_params)
                    
                    if len(recent_trades) < trades_required:
                        logger.info(
                            f"⏸️ {symbol}: not enough trades "
                            f"({len(recent_trades)} < {trades_required}, "
                            f"strictness={self.bot.strictness_percent:.0f}%)"
                        )
                        continue
                    
                    # Ensure there is no open position already
                    if symbol not in self.bot.paper_trader.positions:
                        # Adaptive learning removed - always allow trading
                        
                        # Calculate priority
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
                logger.error(f"Signal analysis failed for {symbol}: {e}")
                continue
        
        logger.info(
            f"📊 Анализ завершен: обработано {processed}/{len(self.bot.pairs)} пар, "
            f"найдено сигналов: {len(all_signals)}"
        )
        if all_signals:
            logger.info(
                f"📋 Найденные сигналы: " + 
                ", ".join([
                    f"{s['signal'].symbol} {s['signal'].direction} "
                    f"({s['signal'].confidence:.1f}%)"
                    for s in all_signals
                ])
            )
        return all_signals
    
    async def _open_best_positions(self, all_signals):
        """Open top-priority positions."""
        all_signals.sort(key=lambda x: x['priority'], reverse=True)
        strictness_params = self._get_strictness_params()
        
        # Если есть отложенный сигнал для режима 1 ордера - добавляем его в начало очереди
        pending_signal = getattr(self.bot, 'pending_single_order_signal', None)
        if pending_signal:
            try:
                symbol = pending_signal['signal'].symbol
                priority = pending_signal['priority']
            except Exception:
                symbol = getattr(pending_signal.get('signal'), 'symbol', 'UNKNOWN')
                priority = pending_signal.get('priority', 0.0)
            logger.info(
                f"📥 ECO очередь: пробуем отложенный сигнал {symbol} "
                f"(priority={priority:.1f})"
            )
            all_signals.insert(0, pending_signal)
            self.bot.pending_single_order_signal = None
        
        # Проверка режима 1 ордера
        single_order_mode = getattr(self.bot, 'single_order_mode', False)
        
        if single_order_mode:
            # РЕЖИМ 1 ОРДЕРА: открывается только одна незащищенная позиция
            # Считаем незащищенные позиции (без стопа в +10%)
            unprotected_positions = sum(
                1 for pos in self.bot.paper_trader.positions.values() 
                if not pos.is_protected
            )
            
            logger.info(
                f"📊 Режим 1 ордера: {len(all_signals)} сигналов найдено, "
                f"незащищенных позиций: {unprotected_positions}"
            )
            
            # Если есть незащищенные позиции - не открываем новые
            if unprotected_positions > 0:
                logger.info(
                    f"⏸️ Режим 1 ордера: есть {unprotected_positions} незащищенных позиций. "
                    f"Новые сделки не открываются, пока позиции не закроются или не будут защищены стопом в +10%"
                )
                if all_signals:
                    best_signal = all_signals[0]
                    self.bot.pending_single_order_signal = best_signal
                    logger.info(
                        f"💾 ECO очередь: сигнал {best_signal['signal'].symbol} "
                        f"(priority={best_signal['priority']:.1f}) сохранен до установки защиты"
                    )
                return  # Не открываем новые позиции
            
            # Лимит = 1 (открываем только одну позицию)
            max_positions = 1
            current_positions = 0
        else:
            # ОБЫЧНЫЙ РЕЖИМ: несколько позиций по лимиту из конфига
            max_positions = self.bot.config['account']['max_positions']
            
            # ✅ Count only UNPROTECTED positions (without +10% stop-loss)
            # Protected positions don't count towards the limit
            unprotected_positions = sum(
                1 for pos in self.bot.paper_trader.positions.values() 
                if not pos.is_protected
            )
            current_positions = unprotected_positions
            
            logger.info(
                f"📊 Обработка сигналов: {len(all_signals)} найдено, "
                f"позиций: {len(self.bot.paper_trader.positions)} всего, "
                f"{unprotected_positions} незащищенных, максимум={max_positions}"
            )
        
        for signal_data in all_signals:
            signal = signal_data['signal']
            
            logger.info(
                f"🔍 {signal.symbol}: Обработка {signal.direction} сигнала "
                f"(confidence={signal.confidence:.1f}%, priority={signal_data['priority']:.1f})"
            )
            
            if current_positions >= max_positions:
                mode_desc = "режим 1 ордера" if single_order_mode else f"максимум позиций ({max_positions})"
                logger.info(
                    f"⏸️ {signal.symbol}: Достигнут лимит - {mode_desc} "
                    f"({current_positions}/{max_positions}) - пропускаем"
                )
                break
            
            # Fetch current order book
            if signal.confidence >= 90:
                orderbook = signal_data.get('orderbook')
            else:
                orderbook = self.bot.binance_client.get_orderbook(signal.symbol)
            
            if not orderbook or not orderbook.get('bids') or not orderbook.get('asks'):
                logger.info(
                    f"⏸️ {signal.symbol}: Нет актуального стакана ордеров "
                    f"(bids={bool(orderbook and orderbook.get('bids'))}, "
                    f"asks={bool(orderbook and orderbook.get('asks'))})"
                )
                continue
            
            # Validate price change tolerance
            signals_config = self.bot.config.get('signals', {})
            price_override_pct = signals_config.get('max_price_change_pct')
            if price_override_pct is None:
                allowed_price_diff = strictness_params['max_price_diff']
            else:
                allowed_price_diff = price_override_pct / 100.0 if price_override_pct > 0 else None
            
            if (
                allowed_price_diff is not None
                and self.bot.strictness_percent <= 75
                and signal.confidence < 90
            ):
                current_price = self.bot.binance_client.get_current_price(signal.symbol)
                if current_price == 0:
                    logger.info(
                        f"⏸️ {signal.symbol}: Не удалось получить текущую цену "
                        f"(current_price=0)"
                    )
                    continue
                
                price_diff = abs(current_price - signal.entry_price) / signal.entry_price
                if price_diff > allowed_price_diff:
                    logger.info(
                        f"⏸️ {signal.symbol}: Цена изменилась на {price_diff*100:.2f}% "
                        f"> допустимого {allowed_price_diff*100:.2f}% "
                        f"(signal_price=${signal.entry_price:.4f}, current_price=${current_price:.4f})"
                    )
                    continue
            
            # ✅ Check if position already exists
            if signal.symbol in self.bot.paper_trader.positions:
                existing_pos = self.bot.paper_trader.positions[signal.symbol]
                logger.info(
                    f"⏸️ {signal.symbol}: Позиция уже существует "
                    f"({existing_pos.side} @ ${existing_pos.entry_price:.4f}, "
                    f"ROI={getattr(existing_pos, 'unrealized_pnl_percent', 0):.2f}%)"
                )
                continue
            
            # Open the position
            adaptive_params = signal_data.get('adaptive_params', {})
            logger.info(
                f"📤 {signal.symbol}: Попытка открыть позицию "
                f"(entry=${signal.entry_price:.4f}, stop=${signal.stop_loss:.4f}, "
                f"tp1=${signal.take_profit_1:.4f})"
            )
            
            position = self.bot.paper_trader.open_position(signal, orderbook, adaptive_params)
            
            if position:
                current_positions += 1
                logger.info(
                    f"{'🟢' if position.side == 'LONG' else '🔴'} "
                    f"✅ {signal.symbol}: Позиция открыта {position.side} @ "
                    f"${position.entry_price:.2f} (leverage: {position.leverage}x, "
                    f"confidence: {signal.confidence:.1f}%, "
                    f"priority: {signal_data['priority']:.1f})"
                )
            else:
                logger.info(
                    f"❌ {signal.symbol}: Позиция НЕ открыта "
                    f"(open_position вернул None - см. логи выше для деталей)"
                )
    
    def _log_statistics(self):
        """Log trading statistics and handle autosave."""
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
                    f"📊 Signals: LONG {long_count}, SHORT {short_count} "
                    f"across {len(self.bot.current_signals)} pairs"
                )
                
                total_pnl = self.bot.paper_trader.balance - self.bot.paper_trader.starting_balance
                logger.info(f"💰 Balance: ${self.bot.paper_trader.balance:.2f}, P&L: ${total_pnl:+.2f}")
                if hasattr(self.bot, 'connection_stats'):
                    last_error = self.bot.connection_stats.get('last_error') or 'none'
                    logger.info(
                        "🔁 Reconnects: %s (last error: %s)",
                        self.bot.connection_stats.get('reconnects', 0),
                        last_error
                    )
            # Adaptive learning removed
            if self.bot.config['logging']['save_session']:
                filename = f"results/autosave_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                Path("results").mkdir(exist_ok=True)
                self.bot.paper_trader.save_session(filename)
                # Autosave silent - only log errors
                
                self.bot._last_signal_log = datetime.now()
        else:
            self.bot._last_signal_log = datetime.now()

