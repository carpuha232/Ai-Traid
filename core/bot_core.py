#!/usr/bin/env python3
"""
🤖 BOT CORE - main trading logic extracted from main.py for modularity.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class BotCore:
    """Primary bot logic extracted from main.py."""
    
    def __init__(self, bot_instance):
        """Initialise with a reference to the main bot instance."""
        self.bot = bot_instance
    
    async def _update_positions(self):
        """Update open positions (stage 1: mark-to-market only)."""
        base_symbols = {s.split('|')[0] for s in list(self.bot.paper_trader.positions.keys())}
        for symbol in base_symbols:
            try:
                current_price = self.bot.binance_client.get_current_price(symbol)
                if current_price <= 0:
                    continue

                closed_trade = self.bot.paper_trader.update_positions(symbol, current_price)
                if closed_trade:
                    self._handle_closed_trade(closed_trade)
            except Exception as e:
                logger.error(f"Failed to update position {symbol}: {e}")
    
    def _handle_closed_trade(self, closed_trade):
        """Handle closed trade bookkeeping."""
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
            raw_symbol = pos_symbol.split('|')[0]
            pos_price = self.bot.binance_client.get_current_price(raw_symbol)
            if pos_price > 0:
                current_prices_dict[pos_symbol] = pos_price
        
        self.bot._safe_gui_call(self.bot.gui.update_positions_signal, 
                               self.bot.paper_trader.positions, current_prices_dict)
        
        if hasattr(self.bot.gui, 'update_history_signal'):
            self.bot._safe_gui_call(self.bot.gui.update_history_signal, self.bot.paper_trader.closed_trades)

    def _handle_position_open(self, signal, position):
        """Bookkeeping when a new position is opened."""
        logger.info(
            "✅ Position opened: %s %s @ %.4f (qty %.2f, margin $%.2f)",
            position.side,
            position.symbol,
            position.entry_price,
            position.size,
            position.margin_usdt,
        )

        if self.bot.gui and hasattr(self.bot.gui, "activity_log"):
            payload = {
                "side": position.side,
                "entry_price": position.entry_price,
                "stop_loss": position.stop_loss,
                "take_profit": position.take_profit_1,
                "risk_percent": self.bot.config["risk"].get("base_risk_percent", 0.0),
                "leverage": position.leverage,
            }
            self.bot._safe_gui_call(self.bot.gui.activity_log.add_position_opened, signal.symbol, payload)

        self.bot._update_gui()
    
    async def _analyze_signals(self):
        """Analyse signals for every pair (stage 1 rebuild)."""
        all_signals: List = []
        self.bot.current_signals = {}

        for symbol in self.bot.pairs:
            try:
                orderbook = self.bot.binance_client.get_orderbook(symbol)
                recent_trades: List[Dict] = self.bot.binance_client.get_recent_trades(symbol)

                signal = self.bot.signal_analyzer.analyze(symbol, orderbook, recent_trades)
                self.bot.current_signals[symbol] = signal
                all_signals.append(signal)
            except Exception as exc:
                logger.error("Signal analysis failed for %s: %s", symbol, exc)

        return all_signals
    
    async def _open_best_positions(self, all_signals):
        """Stage 1 entry logic – open every non-WAIT signal."""
        if not all_signals:
            return

        for signal in all_signals:
            if getattr(signal, "direction", "WAIT") == "WAIT":
                continue

            orderbook = self.bot.binance_client.get_orderbook(signal.symbol)
            position = self.bot.paper_trader.open_position(signal, orderbook)
            if position:
                self._handle_position_open(signal, position)
    
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
            if self.bot.config['logging']['save_session']:
                filename = f"results/autosave_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                Path("results").mkdir(exist_ok=True)
                self.bot.paper_trader.save_session(filename)
                self._prune_autosaves(keep=3)
                # Autosave silent - only log errors
                
                self.bot._last_signal_log = datetime.now()
        else:
            self.bot._last_signal_log = datetime.now()

    def _prune_autosaves(self, keep: int = 3):
        """Keep only the most recent `keep` autosave files."""
        if keep <= 0:
            return

        autosave_dir = Path("results")
        if not autosave_dir.exists():
            return

        autosave_files = sorted(
            autosave_dir.glob("autosave_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for old_file in autosave_files[keep:]:
            try:
                old_file.unlink(missing_ok=True)
            except Exception as exc:
                logger.warning("Failed to delete old autosave %s: %s", old_file, exc)

