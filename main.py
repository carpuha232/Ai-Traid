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
import os
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
            # If logger is unavailable, try to write to file directly
            try:
                with open('logs/error.log', 'a', encoding='utf-8') as f:
                    f.write(f"{datetime.now()} - ERROR - Unhandled exception: {error_msg}\n")
            except:
                pass  # If even file write fails, silently ignore
        
        # All output goes to logger/file, no print() to prevent console windows
        try:
            logger.error(f"❌ Unhandled exception: {exc_type.__name__}: {exc_value}")
            logger.error("See log file for details.")
        except:
            pass
    except Exception as e:
        try:
            logger.error(f"❌ Critical failure while handling exception: {e}")
            logger.error(f"Original error: {exc_type.__name__}: {exc_value}")
        except:
            # Last resort: write to error log file
            try:
                with open('logs/error.log', 'a', encoding='utf-8') as f:
                    f.write(f"{datetime.now()} - ERROR - Critical failure: {e}\n")
                    f.write(f"{datetime.now()} - ERROR - Original: {exc_type.__name__}: {exc_value}\n")
            except:
                pass

sys.excepthook = global_exception_handler

# Logging setup
# IMPORTANT: Use config.json for log level, disable StreamHandler to prevent console windows
# Load config first to get log level
try:
    import json
    with open('config.json', 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    log_level_str = config_data.get('logging', {}).get('level', 'INFO')
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
except:
    log_level = logging.INFO

logging.basicConfig(
    level=log_level,  # Use level from config.json
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/bot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
        # StreamHandler removed to prevent console windows
    ]
)
logger = logging.getLogger(__name__)
# Reduce noise from third-party libraries
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
            
            # Check API keys only for live trading mode
            self.mode = self.config.get('mode', 'paper_trading')
            if self.mode == 'live_trading' and self.config['api']['key'] == "INSERT_YOUR_API_KEY_HERE":
                logger.error("❌ API keys are not configured! Update config.json.")
                raise ValueError("API keys are not configured")
            elif self.mode == 'paper_trading':
                logger.info("📊 Running in PAPER TRADING mode (demo)")
            elif self.mode == 'live_trading':
                logger.info("🚀 Running in LIVE TRADING mode")
            
            # Log Testnet status
            if self.config.get('api', {}).get('testnet', False):
                logger.info("🧪 Using Binance TESTNET (demo funds)")
        except Exception as e:
            logger.error(f"❌ Bot initialisation failed: {e}", exc_info=True)
            raise
        
        # Component setup
        api_key = self.config['api']['key']
        api_secret = self.config['api']['secret']
        testnet = self.config.get('api', {}).get('testnet', False)
        
        self.binance_client = BinanceRealtimeClient(api_key, api_secret, testnet=testnet)
        
        self.signal_analyzer = SignalAnalyzer(self.config)
        self.signal_analyzer.set_trading_mode("Moderate")

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
        self.single_order_mode = False  # По умолчанию обычный режим (не режим 1 ордера)
        self.pairs = self.config.get('pairs', self.config.get('signals', {}).get('pairs', []))
        self.current_signals = {}
        self._last_signal_log = None
        self.pending_single_order_signal = None  # ECO очередь для отложенного сигнала
        self.connection_stats = {
            'reconnects': 0,
            'last_error': None,
            'backoff': 0.5
        }
        self._averaging_recreate_lock = threading.Lock()
        
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
    
    def _monitor_position_protection(self):
        """Monitor positions - simplified: Averaging in loss, Stepped Stop in profit."""
        if self.mode != 'live_trading':
            return
        
        # Periodically cleanup orphaned/duplicate orders (every 15 seconds to reduce API calls)
        if not hasattr(self, '_last_cleanup_time'):
            self._last_cleanup_time = datetime.now()
        
        cleanup_interval = self.config.get('risk', {}).get('protective_refresh_interval', 15.0)  # Use config interval
        if (datetime.now() - self._last_cleanup_time).total_seconds() >= cleanup_interval:
            try:
                # paper_trader is LiveTrader in live_trading mode
                if hasattr(self.paper_trader, 'client') and hasattr(self.paper_trader, '_cleanup_orphaned_orders'):
                    open_orders = self.paper_trader.client.futures_get_open_orders(recvWindow=60000)
                    logger.info(f"🧹 Periodic cleanup: Found {len(open_orders)} open orders")
                    orders_by_symbol = {}
                    for order in open_orders:
                        symbol = order['symbol']
                        if symbol not in orders_by_symbol:
                            orders_by_symbol[symbol] = []
                        orders_by_symbol[symbol].append(order)
                    self.paper_trader._cleanup_orphaned_orders(open_orders, orders_by_symbol)
                    self._last_cleanup_time = datetime.now()
            except Exception as e:
                logger.warning(f"⚠️ Cleanup error: {e}")
        
        if not hasattr(self.paper_trader, 'risk_manager'):
            return
        
        risk_manager = self.paper_trader.risk_manager
        
        # IMPORTANT: Get positions dict reference directly (not a copy)
        # This ensures we're working with the same objects that were updated by refresh_all_positions()
        positions_dict = self.paper_trader.positions
        
        logger.debug(f"📊 Monitoring {len(positions_dict)} positions: {list(positions_dict.keys())}")
        
        for symbol, position in positions_dict.items():
            # Skip if no PNL data
            if not hasattr(position, 'unrealized_pnl_percent'):
                logger.warning(f"⏭️ {symbol}: Skipping - no unrealized_pnl_percent attribute (position may not be refreshed)")
                continue
            
            pnl_pct = position.unrealized_pnl_percent
            logger.info(f"🔍 {symbol}: Checking protection - ROI={pnl_pct:.2f}%")
            
            # ═══════════════════════════════════════════════════════
            # MODE 1: LOSS (ROI < 0) - Martingale Averaging
            # ═══════════════════════════════════════════════════════
            if pnl_pct < 0:
                logger.debug(f"📊 {symbol}: ROI={pnl_pct:.2f}% < 0% → Entering MODE 1 (Martingale Averaging)")
                # Cancel trailing stop if going back to loss
                if position.stepped_stop_active and position.stepped_stop_order_id:
                    if risk_manager.cancel_order(symbol, position.stepped_stop_order_id):
                        logger.info(f"🔄 {symbol}: Trailing stop canceled (ROI < 0%)")
                        position.stepped_stop_active = False
                        position.stepped_stop_order_id = None
                        position.stepped_stop_replacing = False
                        position.stepped_stop_last_update = None
                        position.is_protected = False
                
                # Cancel any old Emergency Stop orders (legacy - we don't use them anymore)
                # Check for STOP orders with ROI around -85% (old emergency stop logic)
                try:
                    open_orders = risk_manager.client.futures_get_open_orders(symbol=symbol, recvWindow=60000)
                    order_side = 'SELL' if position.side == 'LONG' else 'BUY'
                    for order in open_orders:
                        order_type = order.get('type')
                        if order_type in ['STOP', 'STOP_MARKET'] and order.get('side') == order_side:
                            order_id = str(order.get('orderId', ''))
                            stop_price = float(order.get('stopPrice', 0))
                            if stop_price > 0:
                                # Calculate ROI for this stop price
                                if position.side == 'LONG':
                                    stop_roi = ((stop_price - position.entry_price) / position.entry_price) * 100 * position.leverage
                                else:
                                    stop_roi = ((position.entry_price - stop_price) / position.entry_price) * 100 * position.leverage
                                
                                # If ROI is around -85%, it's an old emergency stop - cancel it
                                if abs(stop_roi - (-85.0)) < 5.0:  # Within 5% of -85%
                                    try:
                                        risk_manager.client.futures_cancel_order(symbol=symbol, orderId=order_id)
                                        logger.info(f"🗑️ {symbol}: Canceled old Emergency Stop order {order_id} (legacy, ROI={stop_roi:.1f}%)")
                                    except Exception as e:
                                        logger.debug(f"Failed to cancel old emergency stop {order_id}: {e}")
                except Exception as e:
                    logger.debug(f"Error checking for old emergency stops: {e}")
                
                # Ensure averaging order is active (Martingale)
                # Always try to place averaging order - place_averaging_order will cancel old ones
                # Check if position size is valid for averaging
                initial_size = getattr(position, 'initial_size', position.size)
                if initial_size <= 0:
                    logger.debug(f"⏸️ {symbol}: Skipping averaging order - position size too small ({initial_size:.6f})")
                else:
                    current_liq = risk_manager.calculate_liquidation_price(
                        entry_price=position.entry_price,
                        side=position.side,
                        leverage=position.leverage
                    )
                    
                    # Calculate target averaging price (no tolerance - must be exact)
                    target_price = risk_manager.calculate_averaging_order_price(
                        entry_price=position.entry_price,
                        liquidation_price=current_liq,
                        side=position.side
                    )
                    
                    # Get tick_size for price comparison (to account for exchange rounding)
                    limits = risk_manager._get_symbol_limits(symbol) if hasattr(risk_manager, '_get_symbol_limits') else None
                    tick_size = limits.tick_size if limits and limits.tick_size > 0 else 0.0001
                    
                    # Get available balance for margin check
                    available_balance = None
                    if hasattr(self.paper_trader, 'get_available_balance'):
                        try:
                            available_balance = self.paper_trader.get_available_balance()
                        except:
                            pass
                    
                    # Check if current averaging order still exists and is valid
                    averaging_order_valid = False
                    cancel_existing = False
                    # IMPORTANT: Check hasattr first, then check if value is not None/empty
                    has_averaging_id = hasattr(position, 'averaging_order_id') and position.averaging_order_id
                    logger.debug(f"🔍 {symbol}: Averaging order check - has_averaging_id={has_averaging_id}, value={getattr(position, 'averaging_order_id', None)}")
                    
                    if has_averaging_id:
                        logger.debug(f"🔍 {symbol}: Checking averaging order {position.averaging_order_id}")
                        try:
                            order_info = risk_manager.client.futures_get_order(
                                symbol=symbol,
                                orderId=position.averaging_order_id
                            )
                            if order_info:
                                status = order_info.get('status')
                                if status in ['NEW', 'PARTIALLY_FILLED']:
                                    existing_price = float(order_info.get('price') or 0.0)
                                    if existing_price > 0 and target_price > 0:
                                        # Round target price to tick_size for comparison
                                        rounded_target = risk_manager._round_to_tick(target_price, tick_size)
                                        price_diff = abs(existing_price - rounded_target)
                                        
                                        # CRITICAL: Check if order is above liquidation (for LONG) or below (for SHORT)
                                        # Order below liquidation must ALWAYS be recreated
                                        order_below_liq = False
                                        if position.side == 'LONG':
                                            if existing_price <= current_liq:
                                                order_below_liq = True
                                                logger.warning(
                                                    f"🚨 {symbol}: Averaging order {position.averaging_order_id} @ ${existing_price:.4f} "
                                                    f"is AT or BELOW liquidation ${current_liq:.4f} - MUST recreate!"
                                                )
                                        else:  # SHORT
                                            if existing_price >= current_liq:
                                                order_below_liq = True
                                                logger.warning(
                                                    f"🚨 {symbol}: Averaging order {position.averaging_order_id} @ ${existing_price:.4f} "
                                                    f"is AT or ABOVE liquidation ${current_liq:.4f} - MUST recreate!"
                                                )
                                        
                                        # Order is valid only if:
                                        # 1. Price matches exactly (within tick_size rounding)
                                        # 2. Order is above liquidation (for LONG) or below (for SHORT)
                                        if price_diff <= tick_size and not order_below_liq:
                                            averaging_order_valid = True
                                            logger.info(
                                                f"✅ {symbol}: Averaging order {position.averaging_order_id} active "
                                                f"@ ${existing_price:.4f} (target ${rounded_target:.4f}, diff=${price_diff:.6f}, "
                                                f"liq=${current_liq:.4f})"
                                            )
                                        elif order_below_liq:
                                            cancel_existing = True
                                            logger.error(
                                                f"🚨 {symbol}: Averaging order {position.averaging_order_id} @ ${existing_price:.4f} "
                                                f"is below liquidation ${current_liq:.4f} - recreating immediately!"
                                            )
                                        else:
                                            cancel_existing = True
                                            logger.info(
                                                f"♻️ {symbol}: Averaging order {position.averaging_order_id} price "
                                                f"${existing_price:.4f} differs from target ${rounded_target:.4f} "
                                                f"(diff=${price_diff:.6f}, tick_size=${tick_size}) → recreating"
                                            )
                                    else:
                                        cancel_existing = True
                                        logger.info(
                                            f"♻️ {symbol}: Averaging order {position.averaging_order_id} has invalid price, recreating"
                                        )
                                else:
                                    cancel_existing = True
                                    logger.info(
                                        f"ℹ️ {symbol}: Averaging order {position.averaging_order_id} status={status}, recreating"
                                    )
                            else:
                                cancel_existing = True
                                logger.info(f"⚠️ {symbol}: Averaging order {position.averaging_order_id} not found on exchange, recreating")
                        except Exception as e:
                            # Order doesn't exist or was filled
                            logger.info(f"⚠️ {symbol}: Averaging order {position.averaging_order_id} check failed: {e}, will recreate")
                            cancel_existing = True
                    
                    if averaging_order_valid:
                        # Current averaging order already matches target - skip re-placement
                        continue
                    
                    # Before creating new order, check if there's already a valid order on exchange
                    # This prevents duplicates if our stored order_id is stale
                    found_valid_order = False
                    try:
                        open_orders = risk_manager.client.futures_get_open_orders(symbol=symbol, recvWindow=60000)
                        order_side = 'BUY' if position.side == 'LONG' else 'SELL'
                        rounded_target = risk_manager._round_to_tick(target_price, tick_size)
                        
                        for order in open_orders:
                            if order.get('type') == 'LIMIT' and order.get('side') == order_side:
                                order_price = float(order.get('price', 0))
                                if order_price > 0 and target_price > 0:
                                    price_diff = abs(order_price - rounded_target)
                                    
                                    # CRITICAL: Check if order is above liquidation (for LONG) or below (for SHORT)
                                    # Do NOT use orders that are below liquidation, even if price matches
                                    order_below_liq = False
                                    if position.side == 'LONG':
                                        if order_price <= current_liq:
                                            order_below_liq = True
                                    else:  # SHORT
                                        if order_price >= current_liq:
                                            order_below_liq = True
                                    
                                    # Order is valid only if price matches exactly (within tick_size) and is above liquidation
                                    if price_diff <= tick_size and not order_below_liq:
                                        # Found valid order on exchange - use it instead of creating new
                                        order_id_str = str(order.get('orderId', ''))
                                        stored_id = str(position.averaging_order_id) if hasattr(position, 'averaging_order_id') and position.averaging_order_id else None
                                        if order_id_str != stored_id:
                                            logger.info(
                                                f"✅ {symbol}: Found valid averaging order {order_id_str} on exchange "
                                                f"@ ${order_price:.4f} (target ${rounded_target:.4f}, diff=${price_diff:.6f}, "
                                                f"liq=${current_liq:.4f}) - using it"
                                            )
                                            position.averaging_order_id = order_id_str
                                            found_valid_order = True
                                            break
                                    elif order_below_liq:
                                        logger.warning(
                                            f"⚠️ {symbol}: Found averaging order {order.get('orderId')} on exchange "
                                            f"@ ${order_price:.4f} but it's below liquidation ${current_liq:.4f} - ignoring"
                                        )
                    except Exception as e:
                        logger.debug(f"⚠️ {symbol}: Error checking open orders: {e}")
                    
                    if found_valid_order:
                        # Found valid order on exchange - skip creating new one
                        continue
                    
                    if cancel_existing and has_averaging_id and position.averaging_order_id:
                        try:
                            if risk_manager.cancel_order(symbol, position.averaging_order_id):
                                logger.info(f"🗑️ {symbol}: Averaging order {position.averaging_order_id} canceled before replacement")
                        except Exception as e:
                            logger.debug(f"⚠️ {symbol}: Failed to cancel averaging order {position.averaging_order_id}: {e}")
                        position.averaging_order_id = None
                    
                    # Only place new order if current one doesn't exist or is invalid
                    if not averaging_order_valid:
                        balance_str = f"${available_balance:.2f}" if available_balance is not None else "$0.00"
                        logger.info(
                            f"📊 {symbol}: Attempting to place averaging order - "
                            f"entry=${position.entry_price:.4f}, liq=${current_liq:.4f}, "
                            f"target_price=${target_price:.4f}, available_balance={balance_str}"
                        )
                        order_id = risk_manager.place_averaging_order(
                            position=position,
                            liquidation_price=current_liq,
                            available_balance=available_balance
                        )
                        if order_id:
                            position.averaging_order_id = order_id
                            limits = risk_manager._get_symbol_limits(symbol) if hasattr(risk_manager, '_get_symbol_limits') else None
                            display_price = target_price
                            if limits:
                                display_price = risk_manager._round_to_tick(target_price, limits.tick_size)
                            distance_from_liq_pct = (
                                abs(display_price - current_liq) / current_liq * 100.0
                                if current_liq else 0.0
                            )
                            logger.info(
                                f"🎯 {symbol}: Averaging order #{position.averaging_count + 1} placed "
                                f"@ {distance_from_liq_pct:.2f}% from liquidation (Martingale) - Order ID: {order_id}"
                            )
                            logger.debug(f"💾 {symbol}: Saved averaging_order_id={order_id} to position")
                        else:
                            logger.warning(
                                f"⚠️ {symbol}: Failed to place averaging order - "
                                f"check logs above for reason (balance, limits, averaging_down_enabled, etc.)"
                            )
                    else:
                        logger.debug(f"✅ {symbol}: Averaging order remains unchanged")
            
            # ═══════════════════════════════════════════════════════
            # MODE 2: SMALL PROFIT (0% ≤ ROI < activation_pnl%) - Cancel Averaging
            # ═══════════════════════════════════════════════════════
            else:
                # Get activation PNL from config (default 20%)
                activation_pnl = risk_manager.config.get('risk', {}).get('stepped_stop_activation_pnl', 20.0)
                
                # Cancel any old Emergency Stop orders (legacy - we don't use them anymore)
                # Check for STOP orders with ROI around -85% (old emergency stop logic)
                try:
                    open_orders = risk_manager.client.futures_get_open_orders(symbol=symbol, recvWindow=60000)
                    order_side = 'SELL' if position.side == 'LONG' else 'BUY'
                    for order in open_orders:
                        order_type = order.get('type')
                        if order_type in ['STOP', 'STOP_MARKET'] and order.get('side') == order_side:
                            order_id = str(order.get('orderId', ''))
                            stop_price = float(order.get('stopPrice', 0))
                            if stop_price > 0:
                                # Calculate ROI for this stop price
                                if position.side == 'LONG':
                                    stop_roi = ((stop_price - position.entry_price) / position.entry_price) * 100 * position.leverage
                                else:
                                    stop_roi = ((position.entry_price - stop_price) / position.entry_price) * 100 * position.leverage
                                
                                # If ROI is around -85%, it's an old emergency stop - cancel it
                                if abs(stop_roi - (-85.0)) < 5.0:  # Within 5% of -85%
                                    try:
                                        risk_manager.client.futures_cancel_order(symbol=symbol, orderId=order_id)
                                        logger.info(f"🗑️ {symbol}: Canceled old Emergency Stop order {order_id} (legacy, ROI={stop_roi:.1f}%)")
                                    except Exception as e:
                                        logger.debug(f"Failed to cancel old emergency stop {order_id}: {e}")
                except Exception as e:
                    logger.debug(f"Error checking for old emergency stops: {e}")
                
                if 0 <= pnl_pct < activation_pnl:
                    # ROI is positive but below activation threshold
                    logger.debug(f"📊 {symbol}: ROI={pnl_pct:.2f}% is in range [0%, {activation_pnl}%) - no trailing stop yet")
                    # Cancel averaging when in profit
                    if position.averaging_order_id:
                        if risk_manager.cancel_order(symbol, position.averaging_order_id):
                            logger.info(f"🔄 {symbol}: Averaging order canceled (in profit)")
                        position.averaging_order_id = None
                    
                    self._maybe_reset_margin_after_averaging(symbol, position, pnl_pct, risk_manager)
                    
                    # IMPORTANT: Do NOT cancel trailing stop if ROI drops below activation_pnl!
                    # Trailing stop should remain active until it triggers or is replaced by a higher level.
                    # This is the correct trailing stop behavior - it only moves up, never down.
                    if position.stepped_stop_active:
                        logger.debug(
                            f"🛡️ {symbol}: ROI={pnl_pct:.2f}% < {activation_pnl}%, but trailing stop @ +{position.stepped_stop_level_pnl:.1f}% "
                            f"remains active (trailing stop only moves up, never down)"
                        )
                    
                    # No new trailing stop until activation_pnl% PNL
                    # Existing trailing stop (if any) remains active
                    continue
                
                # ═══════════════════════════════════════════════════════
                # MODE 3: TRAILING STOP (ROI ≥ activation_pnl%) - Maximum Profit
                # ═══════════════════════════════════════════════════════
                # pnl_pct >= activation_pnl
                logger.info(f"🎯 {symbol}: Entering MODE 3 - ROI={pnl_pct:.2f}% >= activation_pnl={activation_pnl}%")
                
                # Cancel averaging permanently when entering protected mode
                if position.averaging_order_id:
                    if risk_manager.cancel_order(symbol, position.averaging_order_id):
                        logger.info(f"🗑️ {symbol}: Averaging order canceled (trailing stop activated)")
                    position.averaging_order_id = None
                
                self._maybe_reset_margin_after_averaging(symbol, position, pnl_pct, risk_manager)
                
                # Calculate trailing stop level
                target_stop_pnl = risk_manager.calculate_progressive_stop_level(pnl_pct)
                
                if target_stop_pnl is None:
                    logger.warning(f"⚠️ {symbol}: calculate_progressive_stop_level returned None for PNL={pnl_pct:.2f}% (activation_pnl={activation_pnl}%)")
                    continue
                
                # Safety check: trailing stop must be at least 10%
                if target_stop_pnl < 10.0:
                    logger.error(
                        f"🚨 {symbol}: Calculated trailing stop level {target_stop_pnl:.2f}% < 10% for PNL={pnl_pct:.2f}%. "
                        f"Using minimum 10% instead."
                    )
                    target_stop_pnl = 10.0
                
                logger.info(f"🛡️ {symbol}: Calculated trailing stop level: {target_stop_pnl:.1f}% (current PNL={pnl_pct:.2f}%)")
                
                # Mark as protected on first activation
                if not position.is_protected:
                    position.is_protected = True
                    position.protection_activated_at = pnl_pct
                    logger.info(f"✅ {symbol}: TRAILING STOP ACTIVATED at PNL={pnl_pct:.1f}% (stop @ +{target_stop_pnl:.1f}%)")
                
                # Check if stop level needs updating
                # IMPORTANT: Trailing stop can only move UP, never DOWN
                current_stop_pnl = position.stepped_stop_level_pnl if position.stepped_stop_active else 0.0
                
                # Only update if: no stop exists OR new stop is HIGHER than current
                # NEVER update if new stop is LOWER - keep current stop active!
                if not position.stepped_stop_active:
                    # No stop exists, place first one
                    logger.info(
                        f"🛡️ {symbol}: PNL={pnl_pct:.1f}% → Placing trailing stop @ +{target_stop_pnl:.1f}%"
                    )
                    
                    position.stepped_stop_replacing = True
                    new_order_id = risk_manager.place_progressive_stop_order(
                        position=position,
                        stop_pnl_pct=target_stop_pnl
                    )
                    
                    if new_order_id:
                        position.stepped_stop_active = True
                        position.stepped_stop_level_pnl = target_stop_pnl
                        position.stepped_stop_order_id = new_order_id
                        position.stepped_stop_replacing = False
                        position.stepped_stop_last_update = datetime.now()
                    else:
                        position.stepped_stop_replacing = False
                        logger.warning(
                            f"⚠️ {symbol}: Failed to place initial trailing stop @ +{target_stop_pnl:.1f}%. "
                            f"Current stop will remain inactive until next attempt."
                        )
                        
                elif target_stop_pnl > current_stop_pnl:
                    # New stop is HIGHER - update (trailing stop moves up)
                    logger.info(
                        f"🛡️ {symbol}: PNL={pnl_pct:.1f}% → Raising trailing stop from +{current_stop_pnl:.1f}% to +{target_stop_pnl:.1f}%"
                    )
                    
                    # ВАЖНО: place_progressive_stop_order уже ставит новый ордер первым, потом удаляет старый
                    position.stepped_stop_replacing = True
                    new_order_id = risk_manager.place_progressive_stop_order(
                        position=position,
                        stop_pnl_pct=target_stop_pnl
                    )
                    
                    if new_order_id:
                        # Update position state
                        position.stepped_stop_level_pnl = target_stop_pnl
                        position.stepped_stop_order_id = new_order_id
                        position.stepped_stop_replacing = False
                        position.stepped_stop_last_update = datetime.now()
                    else:
                        position.stepped_stop_replacing = False
                        logger.warning(
                            f"⚠️ {symbol}: Failed to raise trailing stop to +{target_stop_pnl:.1f}%. "
                            f"Keeping previous level @ +{current_stop_pnl:.1f}%."
                        )
                        
                else:
                    # target_stop_pnl <= current_stop_pnl
                    # PNL dropped or same - KEEP current stop active (DO NOT UPDATE!)
                    # This is trailing stop behavior - stop only moves up, never down
                    logger.debug(
                        f"🛡️ {symbol}: PNL={pnl_pct:.1f}% → Keeping stop @ +{current_stop_pnl:.1f}% "
                        f"(calculated would be +{target_stop_pnl:.1f}%, but trailing stop only moves up)"
                    )
                    # DO NOTHING - current stop remains active and will trigger if price reaches it

    def _maybe_reset_margin_after_averaging(self, symbol: str, position, pnl_pct: float, risk_manager):
        """In ECO mode, after averaging and ROI recovery, reduce position back to initial size."""
        settings = self.config.get('risk', {}).get('reset_margin_after_averaging', {})
        if not settings.get('enabled'):
            return
        if not getattr(self, 'single_order_mode', False):
            return
        if getattr(position, 'averaging_count', 0) <= 0:
            return
        
        trigger_roi = settings.get('trigger_roi_pct', 1.5)
        if pnl_pct < trigger_roi:
            return
        
        initial_size = getattr(position, 'initial_size', position.size)
        current_size = getattr(position, 'size', initial_size)
        if current_size <= initial_size:
            return
        
        limits = risk_manager._get_symbol_limits(symbol) if hasattr(risk_manager, '_get_symbol_limits') else None
        step = limits.step_size if limits else 0.0
        tolerance = step if step else 1e-6
        if current_size <= initial_size + tolerance:
            return
        
        reduce_method = getattr(self.paper_trader, 'reduce_position_to_initial_size', None)
        if not callable(reduce_method):
            logger.debug(f"ℹ️ {symbol}: reduce_position_to_initial_size недоступен")
            return
        
        logger.info(
            f"🔁 {symbol}: ROI={pnl_pct:.2f}% после averaging → сбрасываем маржу "
            f"до стартового размера {initial_size:.6f}"
        )
        success = reduce_method(symbol, initial_size, limits)
        if success:
            position.size = initial_size
            position.margin_usdt = position.initial_margin
            position.position_value_usdt = position.initial_margin * position.leverage
            position.total_margin = position.initial_margin
            position.averaging_count = 0
            position.averaging_order_id = None
    
    def _on_window_close(self):
        """Handle GUI window close."""
        logger.info("GUI window closed by user")
        self.running = False
        
        # ALWAYS remove lock file on close (with retries)
        lock_file = Path("bot.lock")
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                if lock_file.exists():
                    lock_file.unlink()
                    logger.info("Lock file removed successfully")
                    break
            except Exception as e:
                if attempt < max_attempts - 1:
                    import time
                    time.sleep(0.2)  # Wait 200ms before retry
                else:
                    logger.warning(f"Could not remove lock file after {max_attempts} attempts: {e}")
                    # Try one more time with force
                    try:
                        if lock_file.exists():
                            import os
                            os.remove(lock_file)
                            logger.info("Lock file force-removed")
                    except:
                        pass
        
        # Stop asyncio operations gracefully
        try:
            if hasattr(self, 'binance_client') and self.binance_client:
                # Stop WebSocket connections
                loop = None
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                if loop and not loop.is_closed():
                    # Schedule stop in asyncio loop
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(self.binance_client.stop(), loop)
                    else:
                        loop.run_until_complete(self.binance_client.stop())
        except Exception as e:
            logger.warning(f"⚠️ Error stopping connections: {e}")
        
        # Quit Qt application
        if self.app:
            self.app.quit()
    
    def _on_connection_toggle(self, connected: bool):
        """Handle connection button toggle."""
        if connected:
            logger.info("🔄 Starting bot from GUI...")
            # Start bot if not running and asyncio thread doesn't exist
            if not self.running:
                # Check if asyncio thread already exists
                existing_threads = [t for t in threading.enumerate() if hasattr(t, 'name') and t.name == 'asyncio_thread']
                if not existing_threads:
                    asyncio_thread = threading.Thread(target=self._asyncio_thread, daemon=True, name='asyncio_thread')
                    asyncio_thread.start()
                else:
                    logger.warning("⚠️ Asyncio thread already exists, not creating duplicate")
        else:
            logger.info("⏹️ Stopping bot from GUI...")
            self.running = False
    
    def _on_single_order_mode_toggle(self, active: bool):
        """Обработка переключения режима 1 ордера.
        
        Args:
            active: True = режим 1 ордера ВКЛ, False = обычный режим
        """
        self.single_order_mode = active
        status = "ВКЛ" if active else "ВЫКЛ"
        mode_desc = "режим 1 ордера (одна сделка за раз)" if active else "обычный режим (несколько позиций)"
        logger.info(f"🔄 Режим 1 ордера {status} - {mode_desc}")
        
        # Если включили режим 1 ордера и есть открытые позиции - предупреждение
        if active and len(self.paper_trader.positions) > 0:
            unprotected = sum(1 for pos in self.paper_trader.positions.values() if not pos.is_protected)
            if unprotected > 0:
                logger.warning(
                    f"⚠️ Режим 1 ордера включен, но есть {unprotected} незащищенных позиций. "
                    f"Новые сделки не будут открываться, пока все позиции не закроются или не будут защищены."
                )
    
    def _on_refresh_requested(self):
        """Handle refresh button click."""
        logger.info("🔄 Manual refresh requested")
        self._update_gui()
    
    def _on_averaging_distance_changed(self, distance_pct: float):
        """Update averaging distance from GUI slider and recreate orders."""
        try:
            distance_pct = max(0.0, round(float(distance_pct), 4))
        except (TypeError, ValueError):
            logger.warning(f"⚠️ Invalid averaging distance received from GUI: {distance_pct}")
            return
        
        logger.info(f"🎚️ Averaging distance updated via GUI → {distance_pct:.2f}% от ликвидации")
        
        # Update in-memory config and persist to disk
        self.config.setdefault('risk', {})['averaging_distance_from_liq_pct'] = distance_pct
        self.config_manager.set('risk.averaging_distance_from_liq_pct', distance_pct)
        self.config_manager.save()
        
        # Update risk manager config and recreate active averaging orders
        if self.mode == 'live_trading' and hasattr(self.paper_trader, 'risk_manager'):
            risk_manager = self.paper_trader.risk_manager
            risk_manager.config.setdefault('risk', {})['averaging_distance_from_liq_pct'] = distance_pct
            
            threading.Thread(
                target=self._recreate_averaging_orders,
                args=(distance_pct,),
                daemon=True,
                name='averaging_recreate'
            ).start()
    
    def _recreate_averaging_orders(self, distance_pct: float):
        """Recreate all active averaging orders with the new distance setting."""
        if not self._averaging_recreate_lock.acquire(blocking=False):
            logger.info("♻️ Averaging order recreation already in progress, skipping duplicate request")
            return
        
        try:
            if not hasattr(self.paper_trader, 'risk_manager'):
                logger.debug("ℹ️ Risk manager not available, skipping averaging recreation")
                return
            
            risk_manager = self.paper_trader.risk_manager
            positions = getattr(self.paper_trader, 'positions', {})
            if not positions:
                logger.info("ℹ️ No positions to update for averaging distance change")
                return
            
            logger.info(f"♻️ Recreating averaging orders for {len(positions)} positions (distance {distance_pct:.2f}%)")
            
            for symbol, position in list(positions.items()):
                order_id = getattr(position, 'averaging_order_id', None)
                pnl_pct = getattr(position, 'unrealized_pnl_percent', None)
                
                if not order_id:
                    continue  # No active averaging order
                
                if pnl_pct is None or pnl_pct >= 0:
                    logger.debug(f"⏭️ {symbol}: ROI={pnl_pct if pnl_pct is not None else 0:.2f}% ≥ 0 → averaging order not recreated")
                    continue
                
                try:
                    if risk_manager.cancel_order(symbol, order_id):
                        logger.info(f"🗑️ {symbol}: Averaging order {order_id} canceled due to distance update")
                except Exception as e:
                    logger.warning(f"⚠️ {symbol}: Failed to cancel averaging order {order_id}: {e}")
                finally:
                    position.averaging_order_id = None
                
                try:
                    liquidation_price = risk_manager.calculate_liquidation_price(
                        entry_price=position.entry_price,
                        side=position.side,
                        leverage=position.leverage
                    )
                    
                    available_balance = None
                    if hasattr(self.paper_trader, 'get_available_balance'):
                        try:
                            available_balance = self.paper_trader.get_available_balance()
                        except Exception as e:
                            logger.debug(f"⚠️ Failed to fetch available balance before recreating order for {symbol}: {e}")
                    
                    new_order_id = risk_manager.place_averaging_order(
                        position=position,
                        liquidation_price=liquidation_price,
                        available_balance=available_balance
                    )
                    
                    if new_order_id:
                        position.averaging_order_id = new_order_id
                        logger.info(
                            f"🎯 {symbol}: Averaging order recreated with new distance {distance_pct:.2f}% → #{new_order_id}"
                        )
                    else:
                        logger.warning(
                            f"⚠️ {symbol}: Could not place averaging order after distance update (distance {distance_pct:.2f}%)"
                        )
                except Exception as e:
                    logger.error(f"❌ {symbol}: Error recreating averaging order after distance change: {e}", exc_info=True)
        finally:
            self._averaging_recreate_lock.release()
    
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
            
            # Timer for periodic position refresh
            # Use config.json intervals if available, otherwise use defaults
            last_position_refresh = datetime.now().timestamp()
            last_protection_check = datetime.now()
            position_refresh_interval = self.config.get('risk', {}).get('protective_refresh_interval', 10.0)  # seconds - from config.json
            protection_check_interval = 10.0  # seconds - check protection every 10 seconds (less frequent to reduce API calls)
            
            # Main loop
            while self.running:
                try:
                    # Periodic position refresh for live trading
                    now = datetime.now().timestamp()
                    if self.mode == 'live_trading' and now - last_position_refresh >= position_refresh_interval:
                        # IMPORTANT: Refresh positions FIRST, then monitor protection
                        # This ensures order IDs are preserved during refresh
                        if hasattr(self.paper_trader, 'refresh_all_positions'):
                            self.paper_trader.refresh_all_positions()
                            last_position_refresh = now
                            logger.debug("🔄 Positions refreshed from Binance API")
                        
                        # ✅ Monitor positions for protection system (every 10 seconds to avoid API spam)
                        # IMPORTANT: Call AFTER refresh to ensure order IDs are checked correctly
                        if (datetime.now() - last_protection_check).total_seconds() >= protection_check_interval:
                            self._monitor_position_protection()
                            last_protection_check = datetime.now()
                    
                    await self._main_loop()
                    connection_errors = 0
                    backoff_delay = 0.5
                    self.connection_stats['backoff'] = backoff_delay
                    await asyncio.sleep(0.5)  # Balanced mode: 500ms delay
                    
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
        
        # Open strongest candidates (логика режима 1 ордера внутри _open_best_positions)
        await self.core._open_best_positions(all_signals)
        
        # Log stats
        self.core._log_statistics()
        
        # Update GUI
        self._update_gui()
    
    def _update_gui(self):
        """Refresh all GUI data using Qt signals."""
        try:
            if not self.gui:
                return
            
            # Note: Position refresh is handled in main loop every 5 seconds
            # No need to refresh here to avoid duplicate API calls
            
            # Update account metrics (always, even when bot is stopped)
            pnl = self.paper_trader.balance - self.paper_trader.starting_balance
            stats = self.paper_trader.get_statistics()
            
            # Calculate net profit (PNL - commissions from closed trades)
            total_commission = sum(trade.total_commission for trade in self.paper_trader.closed_trades)
            net_profit = pnl - total_commission
            
            self._safe_gui_call(
                self.gui.update_account_signal,
                self.paper_trader.balance,
                pnl,
                stats['win_rate'],
                self.paper_trader.max_drawdown,
                len(self.paper_trader.positions)
            )
            
            # Update net profit widget
            self._safe_gui_call(self.gui.control_panel.update_net_profit, net_profit)
            
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
        
        # Check if we should close positions on stop (configurable)
        close_on_stop = self.config.get('bot_behavior', {}).get('close_positions_on_stop', False)
        
        if self.paper_trader.positions:
            if close_on_stop:
                logger.info("Closing all open positions...")
                current_prices = {
                    symbol: self.binance_client.get_current_price(symbol)
                    for symbol in self.paper_trader.positions.keys()
                }
                self.paper_trader.close_all_positions(current_prices)
            else:
                logger.info(f"ℹ️ Leaving {len(self.paper_trader.positions)} open positions on exchange")
                logger.info("💡 Use GUI 'Закрыть' button to close positions manually if needed")
        
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
            # STRICT check: Another QApplication instance means duplicate
            # This should never happen if main() check worked, but double-check anyway
            existing_app = QtWidgets.QApplication.instance()
            if existing_app:
                logger.error("❌ Another QApplication instance detected! This should not happen.")
                logger.error("="*60)
                logger.error("❌ ERROR: Another bot window is already open!")
                logger.error("="*60)
                logger.error("Please close the existing window first before starting a new one.")
                # Remove lock file since we're not starting
                lock_file = Path("bot.lock")
                if lock_file.exists():
                    try:
                        lock_file.unlink()
                    except:
                        pass
                sys.exit(1)
            
            # Create Qt application
            self.app = QtWidgets.QApplication(sys.argv)
            
            # Create main window
            self.gui = TradingPrototype()
            current_distance = self.config.get('risk', {}).get('averaging_distance_from_liq_pct', 1.0)
            self.gui.control_panel.set_averaging_distance(current_distance, silent=True)
            self.gui.show()
            self.gui.raise_()  # Bring window to front
            self.gui.activateWindow()  # Activate window
            
            # Connect GUI signals to bot methods
            self.gui.control_panel.connectionToggled.connect(self._on_connection_toggle)
            self.gui.control_panel.singleOrderModeToggled.connect(self._on_single_order_mode_toggle)
            self.gui.control_panel.refreshRequested.connect(self._on_refresh_requested)
            self.gui.control_panel.averagingDistanceChanged.connect(self._on_averaging_distance_changed)
            
            # Set close callback
            self.app.aboutToQuit.connect(self._on_window_close)
            # Also handle window close event directly
            self.gui.closeEvent = lambda event: self._on_window_close() or event.accept()
            
            # Auto-start bot
            logger.info("🚀 Auto-starting bot...")
            # Check if asyncio thread already exists (prevent duplicates)
            existing_threads = [t for t in threading.enumerate() if hasattr(t, 'name') and t.name == 'asyncio_thread']
            if not existing_threads:
                asyncio_thread = threading.Thread(target=self._asyncio_thread, daemon=True, name='asyncio_thread')
                asyncio_thread.start()
                logger.info("✅ Asyncio thread started")
            else:
                logger.warning("⚠️ Asyncio thread already exists, not creating duplicate")
            
            # Update GUI to show initial data (balance, etc.)
            self._update_gui()
            
            # Update GUI to show connected state
            self.gui.control_panel.set_connection_toggle_state(True, silent=True)
            self.gui.statusBar().showMessage("Подключение к Binance...", 3000)
            
            # Ensure window is visible
            self.gui.show()
            self.gui.raise_()
            self.gui.activateWindow()
            
            logger.info("GUI window created and shown")
            
            # Start Qt event loop
            sys.exit(self.app.exec())
            
        except KeyboardInterrupt:
            logger.info("⏹️ Ctrl+C received")
        except Exception as e:
            logger.error(f"❌ GUI launch error: {e}", exc_info=True)


def main():
    """Entry point."""
    # STRICT duplicate prevention - check BEFORE anything else
    lock_file = Path("bot.lock")
    script_name = os.path.basename(__file__)
    script_path = os.path.abspath(__file__)
    current_pid = os.getpid()
    
    # Load duplicate handling preference from config (defaults to auto-terminate duplicates)
    auto_terminate_duplicates = True
    try:
        import json
        with open('config.json', 'r', encoding='utf-8') as cfg_f:
            cfg_json = json.load(cfg_f)
        auto_terminate_duplicates = cfg_json.get('safety', {}).get('auto_terminate_duplicates', True)
    except Exception:
        pass
    
    # Step 1: Check for QApplication instance FIRST (before any other checks)
    try:
        from PySide6 import QtWidgets
        existing_app = QtWidgets.QApplication.instance()
        if existing_app:
            logger.error("="*60)
            logger.error("ERROR: Another bot window is already open!")
            logger.error("="*60)
            logger.error("Please close the existing window first before starting a new one.")
            sys.exit(1)
    except Exception:
        pass  # Qt not available yet, skip
    
    # Step 2: Check for running Python processes with this script
    # Improved: Only check processes that have been running for at least 3 seconds
    # This prevents false positives from processes that are just starting up
    try:
        import psutil
        import time
        found_instances = []
        current_time = time.time()
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe', 'status', 'create_time']):
            try:
                proc_pid = proc.info['pid']
                if proc_pid == current_pid:
                    continue  # Skip current process
                
                # Skip zombie or dead processes
                proc_status = proc.info.get('status', '').lower()
                if proc_status in ['zombie', 'dead']:
                    continue
                
                # Check if it's a Python process
                proc_name = proc.info.get('name', '').lower()
                if 'python' not in proc_name:
                    continue
                
                # Check command line
                cmdline = proc.info.get('cmdline', [])
                if not cmdline:
                    continue
                
                cmdline_str = ' '.join(cmdline).lower()
                # Check if this script is in command line
                if script_name.lower() in cmdline_str or script_path.lower() in cmdline_str:
                    # Double-check: verify process is actually running and stable
                    try:
                        proc_obj = psutil.Process(proc_pid)
                        if not proc_obj.is_running():
                            continue
                        
                        if proc_obj.status() == psutil.STATUS_ZOMBIE:
                            continue
                        
                        # IMPORTANT: Only consider processes that have been running for at least 5 seconds
                        # This filters out processes that are just starting up (like this one)
                        # Also check if this process is a child of current process (Qt subprocess)
                        proc_create_time = proc_obj.create_time()
                        process_age = current_time - proc_create_time
                        
                        if process_age < 5.0:
                            # Process is too new, likely just starting up - skip it
                            continue
                        
                        # Check if this process is a child of current process (Qt subprocess)
                        # If so, it's not a duplicate, it's part of the same application
                        try:
                            current_proc = psutil.Process(current_pid)
                            proc_parent = proc_obj.parent()
                            if proc_parent and proc_parent.pid == current_pid:
                                # This is a child process of current process - not a duplicate
                                continue
                        except:
                            pass
                        
                        # Process is stable and running - this is a real duplicate
                        found_instances.append((proc_pid, cmdline, process_age))
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        # Process already dead, skip it
                        continue
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception:
                continue
        
        if found_instances:
            logger.error("="*60)
            logger.error("ERROR: Another bot instance is already running!")
            logger.error("="*60)
            for pid, cmdline, age in found_instances:
                logger.error(f"   PID: {pid} (running for {age:.1f} seconds)")
                logger.error(f"   Command: {' '.join(cmdline[:3])}...")
            logger.error("="*60)
            if auto_terminate_duplicates:
                logger.error("Attempting to terminate duplicate instances automatically...")
                for pid, _, _ in found_instances:
                    try:
                        proc_obj = psutil.Process(pid)
                        proc_obj.terminate()
                        try:
                            proc_obj.wait(timeout=5)
                        except psutil.TimeoutExpired:
                            logger.warning(f"PID {pid} did not terminate in time, forcing kill.")
                            proc_obj.kill()
                            proc_obj.wait(timeout=3)
                        logger.info(f"✅ Duplicate instance PID {pid} terminated.")
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        logger.info(f"ℹ️ PID {pid} already stopped: {e}")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not terminate duplicate PID {pid}: {e}")
                # Short pause to allow OS to release resources
                time.sleep(1.0)
                logger.info("Duplicate termination complete, continuing startup.")
            else:
                logger.error("Please close the existing instance first before starting a new one.")
                sys.exit(1)
    except ImportError:
        # psutil not available, use lock file only
        pass
    except Exception as e:
        logger.warning(f"Warning: Could not check for duplicate processes: {e}")
    
    # Step 3: Check lock file
    if lock_file.exists():
        try:
            with open(lock_file, 'r') as f:
                old_pid = int(f.read().strip())
            
            # Check if process still exists
            try:
                import psutil
                if psutil.pid_exists(old_pid):
                    logger.error("="*60)
                    logger.error(f"ERROR: Lock file found! Another bot instance may be running (PID: {old_pid})")
                    logger.error("="*60)
                    logger.error("Please close the existing instance first before starting a new one.")
                    logger.error("If the instance is not running, delete bot.lock file manually.")
                    sys.exit(1)
                else:
                    # Stale lock file, remove it
                    lock_file.unlink()
                    logger.info("Removed stale lock file")
            except ImportError:
                # psutil not available, try alternative check
                try:
                    os.kill(old_pid, 0)  # Check if process exists (doesn't kill it)
                    logger.error("="*60)
                    logger.error(f"ERROR: Lock file found! Another bot instance may be running (PID: {old_pid})")
                    logger.error("="*60)
                    logger.error("Please close the existing instance first before starting a new one.")
                    logger.error("If the instance is not running, delete bot.lock file manually.")
                    sys.exit(1)
                except (OSError, ProcessLookupError):
                    # Process doesn't exist, remove stale lock
                    lock_file.unlink()
                    logger.info("Removed stale lock file")
        except (ValueError, FileNotFoundError):
            # Invalid lock file, remove it
            lock_file.unlink()
            logger.info("Removed invalid lock file")
    
    # Step 4: Create lock file with current PID
    try:
        with open(lock_file, 'w') as f:
            f.write(str(current_pid))
    except Exception as e:
        logger.warning(f"Warning: Could not create lock file: {e}")
        sys.exit(1)
    
    Path("logs").mkdir(exist_ok=True)
    Path("results").mkdir(exist_ok=True)
    
    if not Path("config.json").exists():
        logger.error("config.json not found!")
        return
    
    try:
        logger.info("Creating bot instance...")
        bot = AutoScalpingBot()
        logger.info("Bot instance created successfully")
    except Exception as e:
        logger.error(f"Failed to create bot: {e}", exc_info=True)
        return
    
    # Log startup info instead of printing (prevents console windows)
    logger.info("="*60)
    logger.info("AUTO SCALPING BOT - CONSOLIDATED RELEASE")
    logger.info("="*60)
    logger.info("Configuration:")
    logger.info(f"  Starting balance: ${bot.config['account']['starting_balance']}")
    logger.info(f"  Leverage: {bot.config['account']['leverage']}x")
    logger.info(f"  Pairs: {len(bot.pairs)}")
    logger.info(f"  Minimum confidence: {bot.config['signals']['min_confidence']}%")
    logger.info("Starting bot...")
    logger.info("To stop: press Ctrl+C or close the GUI window")
    
    try:
        logger.info("Starting bot GUI...")
        bot.run()
    except Exception as e:
        logger.error(f"Bot run failure: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("⏹️ Program stopped by user (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Critical error in main(): {e}", exc_info=True)
        sys.exit(1)

