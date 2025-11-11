#!/usr/bin/env python3
"""
🤖 AUTO SCALPING BOT - UNIFIED VERSION
Combined release with the best capabilities from V1, V2, and V3.
"""

import asyncio
import logging
import sys
import traceback
import threading
from pathlib import Path
from datetime import datetime

# Internal modules
from core.binance_client import BinanceRealtimeClient
from core.signal_analyzer import SignalAnalyzer
from core.config_manager import ConfigManager
from core.bot_core import BotCore
from simulation.paper_trader import PaperTrader
from core.live_trader import LiveTrader

# Qt GUI
from PySide6 import QtWidgets, QtCore
from gui.main_window import TradingPrototype

# Global exception handler (V3)
def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Global handler for uncaught exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    try:
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        try:
            logger.error(f"❌ Unhandled exception: {error_msg}", exc_info=False)
        except:
            print(f"❌ Unhandled exception (logger unavailable): {error_msg}")
        
        print(f"❌ Unhandled exception: {exc_type.__name__}: {exc_value}")
        print("See log file for details.")
    except Exception as e:
        print(f"❌ Critical failure while handling exception: {e}")
        print(f"Original error: {exc_type.__name__}: {exc_value}")

sys.excepthook = global_exception_handler

# Logging setup
logging.basicConfig(
    level=logging.INFO,  # Changed from DEBUG to INFO
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/bot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)
logging.getLogger('binance').setLevel(logging.WARNING)


class AutoScalpingBot:
    """Main class for the automated scalping bot."""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialise bot dependencies and state."""
        try:
            self.config_manager = ConfigManager(config_path)
            self.config = self.config_manager.config
            
            logger.info("="*60)
            logger.info("🤖 AUTO SCALPING BOT - CONSOLIDATED RELEASE")
            logger.info("="*60)
            
            if self.config['api']['key'] == "INSERT_YOUR_API_KEY_HERE":
                logger.error("❌ API keys are not configured! Update config.json.")
                raise ValueError("API keys are not configured")
        except Exception as e:
            logger.error(f"❌ Bot initialisation failed: {e}", exc_info=True)
            raise
        
        # Component setup
        self.binance_client = BinanceRealtimeClient(
            self.config['api']['key'],
            self.config['api']['secret']
        )
        
        self.signal_analyzer = SignalAnalyzer(self.config)
        self.signal_analyzer.set_trading_mode("Moderate")

        self.mode = self.config.get('mode', 'paper_trading')
        if self.mode == 'live_trading':
            self.paper_trader = LiveTrader(
                self.config,
                self.config['api']['key'],
                self.config['api']['secret']
            )
            logger.info("🚀 Trading mode: LIVE")
        else:
            self.paper_trader = PaperTrader(
                self.config,
                self.config['account']['starting_balance']
            )
            logger.info("🎯 Trading mode: PAPER")
        
        # Qt GUI
        self.app = None
        self.gui = None
        
        # State
        self.running = False
        self.paused = False  # For "Pause" button
        self.pairs = self.config['pairs']
        self.current_signals = {}
        self._last_signal_log = None
        self.connection_stats = {
            'reconnects': 0,
            'last_error': None,
            'backoff': 0.5
        }
        
        # Strictness (fixed at 50% - Moderate mode)
        self.strictness_percent = 50.0
        
        # Core logic bootstrap
        self.core = BotCore(self)
        
        logger.info("✅ All components initialised")
    
    def close_position(self, symbol: str, order_type: str = 'Manual'):
        """Close a specific position via GUI."""
        if symbol in self.paper_trader.positions:
            current_price = self.binance_client.get_current_price(symbol)
            if current_price > 0:
                closed_trade = self.paper_trader.close_position_manually(
                    symbol, current_price, order_type
                )
                if closed_trade:
                    logger.info(f"🔹 Closed position {symbol} manually ({order_type})")
                    return True
        return False
    
    def close_all_positions(self):
        """Close all open positions (emergency)."""
        if not self.paper_trader.positions:
            logger.info("No positions to close")
            return
        
        logger.warning("🚨 Emergency: closing all positions")
        current_prices = {
            symbol: self.binance_client.get_current_price(symbol)
            for symbol in list(self.paper_trader.positions.keys())
        }
        self.paper_trader.close_all_positions(current_prices)
        logger.info(f"✅ Closed {len(current_prices)} positions")
    
    def toggle_pause(self):
        """Toggle pause state (stop opening new positions)."""
        self.paused = not self.paused
        status = "PAUSED" if self.paused else "RESUMED"
        logger.info(f"⏸️ Bot {status} - new positions: {'DISABLED' if self.paused else 'ENABLED'}")
    
    def _on_window_close(self):
        """Handle GUI window close."""
        logger.info("⏹️ GUI window closed by user")
        self.running = False
        if self.app:
            self.app.quit()
    
    def _on_connection_toggle(self, connected: bool):
        """Handle connection button toggle."""
        if connected:
            logger.info("🔄 Starting bot from GUI...")
            # Start bot if not running
            if not self.running:
                asyncio_thread = threading.Thread(target=self._asyncio_thread, daemon=True)
                asyncio_thread.start()
        else:
            logger.info("⏹️ Stopping bot from GUI...")
            self.running = False
    
    def _on_auto_trading_toggle(self, active: bool):
        """Handle auto trading toggle."""
        self.paused = not active
        status = "ENABLED" if active else "DISABLED"
        logger.info(f"🤖 Auto trading {status}")
    
    def _on_refresh_requested(self):
        """Handle refresh button click."""
        logger.info("🔄 Manual refresh requested")
        self._update_gui()
    
    def _on_close_all_clicked(self):
        """Handle close all positions button."""
        self.close_all_positions()
    
    def _on_pause_toggled(self, checked: bool):
        """Handle pause button toggle."""
        self.paused = checked
        status = "PAUSED" if checked else "RESUMED"
        logger.info(f"⏸️ Bot {status}")
    
    def _safe_gui_call(self, signal, *args):
        """Emit Qt signal for thread-safe GUI updates."""
        try:
            if self.gui:
                signal.emit(*args)
        except (RuntimeError, AttributeError) as e:
            logger.debug(f"GUI signal emit failed: {e}")
    
    async def start(self):
        """Start the bot (V3: quick warm-up, minimal delays)."""
        connection_errors = 0
        max_connection_errors = 5
        self._boot_time = datetime.now()
        backoff_delay = self.connection_stats.get('backoff', 0.5)
        
        try:
            self.running = True
            
            logger.info("⏳ Waiting for GUI readiness...")
            await asyncio.sleep(0.1)  # V3: minimal delay
            
            logger.info("📡 Connecting to Binance...")
            await self.binance_client.start_streams(self.pairs)
            logger.info("✅ Connected to Binance WebSocket")
            
            # V3: fast warm-up
            logger.info("⏳ Performing quick warm-up...")
            warmup_deadline = datetime.now().timestamp() + 10
            ready_min = max(1, len(self.pairs)//3)
            logger.info(f"Warm-up needs at least {ready_min} ready pairs out of {len(self.pairs)}")
            
            for _ in range(5):
                ready = []
                for symbol in self.pairs:
                    state = self.binance_client.book_state.get(symbol)
                    if state and state.get('synced'):
                        ready.append(symbol)
                
                if len(ready) >= ready_min:
                    logger.info(f"✅ Warm-up complete: {len(ready)}/{len(self.pairs)} pairs ready")
                    break
                
                if datetime.now().timestamp() > warmup_deadline:
                    logger.warning(
                        f"⚠️ Warm-up timeout: {len(ready)}/{len(self.pairs)} ready — starting anyway"
                    )
                    break
                
                await asyncio.sleep(0.2)
            
            logger.info("🚀 Bot is running and monitoring the market...")
            
            # Main loop
            while self.running:
                try:
                    await self._main_loop()
                    connection_errors = 0
                    backoff_delay = 0.5
                    self.connection_stats['backoff'] = backoff_delay
                    await asyncio.sleep(0.1)  # V3: minimal delay (100 ms)
                    
                except ConnectionError as e:
                    connection_errors += 1
                    logger.warning(f"⚠️ Connection error ({connection_errors}/{max_connection_errors}): {e}")
                    self.connection_stats['reconnects'] += 1
                    self.connection_stats['last_error'] = str(e)
                    
                    if connection_errors >= max_connection_errors:
                        logger.error("❌ Too many connection errors. Stopping bot.")
                        break
                    
                    await asyncio.sleep(backoff_delay)
                    backoff_delay = min(backoff_delay * 1.5, 10.0)
                    self.connection_stats['backoff'] = backoff_delay
                    
                except KeyboardInterrupt:
                    logger.info("⏹️ Stop signal received (Ctrl+C)")
                    break
                    
                except RuntimeError as e:
                    if "wrapped C/C++ object" in str(e) or "deleted" in str(e):
                        logger.info("⏹️ GUI window closed")
                        break
                    raise
                    
                except Exception as e:
                    logger.error(f"❌ Error in main loop: {e}", exc_info=True)
                    await asyncio.sleep(backoff_delay)
                    backoff_delay = min(backoff_delay * 1.2, 5.0)
                    self.connection_stats['backoff'] = backoff_delay
            
        except KeyboardInterrupt:
            logger.info("⏹️ Stop signal received (Ctrl+C)...")
        except Exception as e:
            logger.error(f"❌ Critical error: {e}", exc_info=True)
        finally:
            await self.stop()
    
    async def _main_loop(self):
        """Main analysis and trading loop."""
        # Refresh open positions
        await self.core._update_positions()
        
        # Analyse signals
        all_signals = await self.core._analyze_signals()
        
        # Open strongest candidates (only if not paused)
        if not self.paused:
            await self.core._open_best_positions(all_signals)
        
        # Log stats
        self.core._log_statistics()
        
        # Update GUI
        self._update_gui()
    
    def _update_gui(self):
        """Refresh all GUI data using Qt signals."""
        try:
            if not self.running or not self.gui:
                return
            
            # Update account metrics
            pnl = self.paper_trader.balance - self.paper_trader.starting_balance
            stats = self.paper_trader.get_statistics()
            
            self._safe_gui_call(
                self.gui.update_account_signal,
                self.paper_trader.balance,
                pnl,
                stats['win_rate'],
                self.paper_trader.max_drawdown,
                len(self.paper_trader.positions)
            )
            
            # Update signals table
            self._safe_gui_call(self.gui.update_signals_signal, self.current_signals)
            
            # Update positions table
            current_prices = {
                symbol: self.binance_client.get_current_price(symbol)
                for symbol in self.paper_trader.positions.keys()
            }
            self._safe_gui_call(
                self.gui.update_positions_signal,
                self.paper_trader.positions,
                current_prices
            )
            
            # Update history table
            self._safe_gui_call(
                self.gui.update_history_signal,
                self.paper_trader.closed_trades
            )
            
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                self.running = False
        except Exception as e:
            logger.error(f"GUI update error: {e}")
    
    async def stop(self):
        """Stop the bot."""
        logger.info("⏹️ Stopping bot...")
        self.running = False
        
        if self.paper_trader.positions:
            logger.info("Closing all open positions...")
            current_prices = {
                symbol: self.binance_client.get_current_price(symbol)
                for symbol in self.paper_trader.positions.keys()
            }
            self.paper_trader.close_all_positions(current_prices)
        
        await self.binance_client.stop()
        logger.info("✅ Disconnected from Binance")
        
        if self.config['logging']['save_session']:
            filename = f"results/session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            Path("results").mkdir(exist_ok=True)
            self.paper_trader.save_session(filename)
        
        self._show_final_stats()
        logger.info("✅ Bot stopped")
    
    def _show_final_stats(self):
        """Display final statistics."""
        stats = self.paper_trader.get_statistics()
        
        logger.info("")
        logger.info("="*60)
        logger.info("📊 FINAL STATISTICS")
        logger.info("="*60)
        logger.info(f"Starting Balance:  ${self.paper_trader.starting_balance:.2f}")
        logger.info(f"Final Balance:     ${self.paper_trader.balance:.2f}")
        logger.info(f"Total P&L:         ${self.paper_trader.total_pnl:+.2f} ({(self.paper_trader.total_pnl/self.paper_trader.starting_balance*100):+.2f}%)")
        logger.info(f"Max Drawdown:      {self.paper_trader.max_drawdown:.2f}%")
        logger.info("-"*60)
        logger.info(f"Total Trades:      {stats['total_trades']}")
        logger.info(f"Winners:           {stats['winners']} ({stats['win_rate']:.1f}%)")
        logger.info(f"Losers:            {stats['losers']}")
        logger.info(f"Avg Win:           ${stats['avg_win']:.2f}")
        logger.info(f"Avg Loss:          ${stats['avg_loss']:.2f}")
        logger.info(f"Profit Factor:     {stats['profit_factor']:.2f}")
        logger.info(f"Best Trade:        ${stats['best_trade']:.2f}")
        logger.info(f"Worst Trade:       ${stats['worst_trade']:.2f}")
        logger.info(f"Avg Duration:      {stats['avg_duration']:.0f}s")
        logger.info("="*60)
    
    def _asyncio_thread(self):
        """Run asyncio loop in a dedicated thread."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.start())
        except KeyboardInterrupt:
            logger.info("⏹️ Ctrl+C received in asyncio thread")
        except Exception as e:
            logger.error(f"❌ Error in asyncio thread: {e}", exc_info=True)
    
    def run(self):
        """Run the bot with Qt GUI."""
        try:
            # Create Qt application
            self.app = QtWidgets.QApplication.instance()
            if not self.app:
                self.app = QtWidgets.QApplication(sys.argv)
            
            # Create main window
            self.gui = TradingPrototype()
            self.gui.show()
            
            # Connect GUI signals to bot methods
            self.gui.control_panel.connectionToggled.connect(self._on_connection_toggle)
            self.gui.control_panel.autoTradingToggled.connect(self._on_auto_trading_toggle)
            self.gui.control_panel.refreshRequested.connect(self._on_refresh_requested)
            self.gui.close_all_button.clicked.connect(self._on_close_all_clicked)
            self.gui.pause_button.toggled.connect(self._on_pause_toggled)
            
            # Set close callback
            self.app.aboutToQuit.connect(self._on_window_close)
            
            # Auto-start bot
            logger.info("🚀 Auto-starting bot...")
            asyncio_thread = threading.Thread(target=self._asyncio_thread, daemon=True)
            asyncio_thread.start()
            logger.info("✅ Asyncio thread started")
            
            # Update GUI to show connected state
            self.gui.control_panel.set_connection_toggle_state(True, silent=True)
            self.gui.statusBar().showMessage("Подключение к Binance...", 3000)
            
            # Start Qt event loop
            sys.exit(self.app.exec())
            
        except KeyboardInterrupt:
            logger.info("⏹️ Ctrl+C received")
        except Exception as e:
            logger.error(f"❌ GUI launch error: {e}", exc_info=True)


def main():
    """Entry point."""
    Path("logs").mkdir(exist_ok=True)
    Path("results").mkdir(exist_ok=True)
    
    if not Path("config.json").exists():
        logger.error("❌ config.json not found!")
        return
    
    try:
        bot = AutoScalpingBot()
    except Exception as e:
        logger.error(f"❌ Failed to create bot: {e}", exc_info=True)
        print(f"❌ Failed to create bot: {e}")
        traceback.print_exc()
        return
    
    print()
    print("="*60)
    print("AUTO SCALPING BOT - CONSOLIDATED RELEASE")
    print("="*60)
    print()
    print("Configuration:")
    print(f"  Starting balance: ${bot.config['account']['starting_balance']}")
    print(f"  Leverage: {bot.config['account']['leverage']}x")
    print(f"  Pairs: {len(bot.config['pairs'])}")
    print(f"  Minimum confidence: {bot.config['signals']['min_confidence']}%")
    print()
    print("Starting bot...")
    print("To stop: press Ctrl+C or close the GUI window")
    print()
    
    try:
        bot.run()
    except Exception as e:
        logger.error(f"❌ Bot run failure: {e}", exc_info=True)
        print(f"❌ Bot run failure: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ Program stopped by user (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Critical error in main(): {e}", exc_info=True)
        print(f"❌ Critical error: {e}")
        traceback.print_exc()
        sys.exit(1)

