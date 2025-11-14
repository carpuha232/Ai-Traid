#!/usr/bin/env python3
"""
💹 LIVE TRADER
Operate against Binance Futures (UM) while keeping the interface aligned with PaperTrader.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Dict, Optional

from binance.client import Client

from simulation.paper_trader import Position, ClosedTrade
from core.risk_manager import RiskManager


logger = logging.getLogger(__name__)


class LiveTrader:
    """Execute trades on Binance Futures (UM)."""

    def __init__(self, config: Dict, api_key: str, api_secret: str):
        self.config = config
        testnet = config.get('api', {}).get('testnet', False)
        
        # Initialize client with proper testnet configuration
        if testnet:
            # Monkey-patch ping to avoid connecting to mainnet during init
            original_ping = Client.ping
            Client.ping = lambda self: None  # Temporarily disable ping
            
            try:
                self.client = Client(api_key, api_secret, {'timeout': 30})
                
                # Override URLs for Futures Testnet
                self.client.FUTURES_URL = 'https://testnet.binancefuture.com/fapi'
                self.client.FUTURES_DATA_URL = 'https://testnet.binancefuture.com/fapi'
                self.client.FUTURES_COIN_URL = 'https://testnet.binancefuture.com/dapi'
                
                logger.info("🔧 Configured client for Binance Futures Testnet")
                logger.info(f"   FUTURES_URL: {self.client.FUTURES_URL}")
            finally:
                # Restore original ping
                Client.ping = original_ping
        else:
            self.client = Client(api_key, api_secret)

        # Use large recvWindow for testnet (timestamp sync issues)
        account_info = self.client.futures_account(recvWindow=60000)
        self.starting_balance = self._extract_wallet_balance(account_info)
        self.balance = self.starting_balance
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.min_balance = self.starting_balance
        self.max_balance = self.starting_balance

        self.positions: Dict[str, Position] = {}
        self.closed_trades: list[ClosedTrade] = []
        self.trade_counter = 0

        # Initialize Risk Manager
        self.risk_manager = RiskManager(self.client, config)
        logger.info("🛡️ RiskManager initialized")
        
        # Protective order lock (prevent race conditions)
        self._protective_lock = threading.Lock()
        self.protective_pending = set()  # Symbols currently updating protective orders
        
        # Balance cache
        self.cached_futures_balance = None
        self.balance_cache_time = 0
        self.balance_cache_ttl = config.get('risk', {}).get('balance_cache_ttl', 10.0)
        self.defer_averaging_until_loss = config.get('risk', {}).get(
            'averaging_require_negative_roi', True
        )
        
        # Load existing open positions from Binance
        self._load_existing_positions()
        
        margin_type = self.config.get('account', {}).get('margin_type', 'ISOLATED')
        logger.info("💹 LiveTrader initialised. Balance: $%.2f, Margin: %s", self.balance, margin_type)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _extract_wallet_balance(self, account_info: Dict) -> float:
        for asset in account_info.get('assets', []):
            if asset.get('asset') == 'USDT':
                return float(asset.get('walletBalance', 0.0))
        return 0.0

    def _refresh_balance(self):
        info = self.client.futures_account()
        new_balance = self._extract_wallet_balance(info)
        self.balance = new_balance
        if new_balance > self.max_balance:
            self.max_balance = new_balance
        if new_balance < self.min_balance:
            self.min_balance = new_balance
        if self.max_balance > 0:
            drawdown = (self.max_balance - self.balance) / self.max_balance * 100
            self.max_drawdown = max(self.max_drawdown, drawdown)

    def _ensure_isolated_margin(self, symbol: str):
        """Set margin type to ISOLATED for a symbol."""
        try:
            self.client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
            logger.debug(f"✅ {symbol}: Margin type set to ISOLATED")
        except Exception as exc:
            # If already ISOLATED, API returns error - ignore it
            if 'No need to change margin type' in str(exc):
                logger.debug(f"ℹ️ {symbol}: Already in ISOLATED mode")
            else:
                logger.warning(f"⚠️ Failed to set ISOLATED margin for {symbol}: {exc}")

    def _ensure_leverage(self, symbol: str, leverage: int):
        """Set leverage for a symbol (must be called after setting margin type)."""
        try:
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            logger.debug(f"✅ {symbol}: Leverage set to {leverage}x")
        except Exception as exc:
            logger.warning("⚠️ Failed to adjust leverage %s: %s", symbol, exc)
    
    def _load_existing_positions(self):
        """Load existing open positions from Binance."""
        try:
            # First, get all open orders
            open_orders = self.client.futures_get_open_orders()
            orders_by_symbol = {}
            for order in open_orders:
                symbol = order['symbol']
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = []
                orders_by_symbol[symbol].append(order)
            
            logger.info(f"📋 Found {len(open_orders)} open orders on exchange")
            
            positions_data = self.client.futures_position_information()
            loaded_count = 0
            
            for pos_data in positions_data:
                position_amt = float(pos_data.get('positionAmt', 0))
                if position_amt == 0:
                    continue  # Skip closed positions
                
                symbol = pos_data['symbol']
                entry_price = float(pos_data['entryPrice'])
                mark_price = float(pos_data['markPrice'])
                unrealized_pnl = float(pos_data['unRealizedProfit'])
                
                # Determine side
                side = 'LONG' if position_amt > 0 else 'SHORT'
                quantity = abs(position_amt)
                
                # Create Position object
                # Calculate take profit levels (mock, as we don't know the original values)
                tp_distance = entry_price * 0.01  # 1% from entry
                take_profit_1 = entry_price + tp_distance if side == 'LONG' else entry_price - tp_distance
                take_profit_2 = entry_price + tp_distance * 2 if side == 'LONG' else entry_price - tp_distance * 2
                
                leverage = int(pos_data.get('leverage', 1))
                position_value = quantity * entry_price * leverage
                margin = position_value / leverage
                
                # Calculate liquidation price using RiskManager
                liquidation_price = self.risk_manager.calculate_liquidation_price(
                    entry_price=entry_price,
                    side=side,
                    leverage=leverage
                )
                
                position = Position(
                    id=f"{symbol}_{int(datetime.now().timestamp())}",
                    symbol=symbol,
                    side=side,
                    entry_price=entry_price,
                    size=quantity,  # Position class uses 'size' not 'quantity'
                    leverage=leverage,
                    stop_loss=0.0,  # Unknown from API
                    take_profit_1=take_profit_1,
                    take_profit_2=take_profit_2,
                    entry_time=datetime.now(),
                    entry_commission=0.0,
                    liquidation_price=liquidation_price,
                    confidence=75.0,
                    position_value_usdt=position_value,
                    margin_usdt=margin,
                    # Initialize advanced risk management fields
                    initial_margin=margin,
                    initial_entry_price=entry_price,
                    initial_size=quantity,  # CRITICAL: Set initial_size for Martingale!
                    averaging_count=0,
                    total_margin=margin
                )
                
                # Update dynamic fields
                position.current_price = mark_price
                position.unrealized_pnl = unrealized_pnl
                
                self.positions[symbol] = position
                loaded_count += 1
                logger.info(f"📥 Loaded existing position: {symbol} {side} @ ${entry_price:.2f}")
                
                # Check for existing orders for this position
                existing_orders = orders_by_symbol.get(symbol, [])
                
                # Find averaging order (LIMIT BUY/SELL)
                averaging_order = None
                stop_order = None
                
                for order in existing_orders:
                    order_type = order.get('type')
                    order_side = order.get('side')
                    
                    # Averaging order: LIMIT order in same direction as position
                    if order_type == 'LIMIT':
                        if (side == 'LONG' and order_side == 'BUY') or (side == 'SHORT' and order_side == 'SELL'):
                            averaging_order = order
                    
                    # Stop-loss order: STOP/STOP_MARKET in opposite direction
                    # TAKE_PROFIT orders are legacy and should be canceled
                    elif order_type in ['STOP', 'STOP_MARKET']:
                        if (side == 'LONG' and order_side == 'SELL') or (side == 'SHORT' and order_side == 'BUY'):
                            stop_order = order
                    elif order_type in ['TAKE_PROFIT', 'TAKE_PROFIT_MARKET']:
                        # Cancel legacy TAKE_PROFIT orders - we don't use them anymore
                        try:
                            self.client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
                            logger.info(f"🗑️ Canceled legacy TAKE_PROFIT order {order['orderId']} for {symbol} (we only use trailing stop now)")
                        except Exception as e:
                            logger.debug(f"Failed to cancel TAKE_PROFIT order: {e}")
                
                # Assign existing order IDs
                if stop_order:
                    position.stepped_stop_order_id = str(stop_order['orderId'])
                    position.stepped_stop_active = True
                    position.is_protected = True
                    logger.info(f"📌 Found existing stop-loss order for {symbol}: {position.stepped_stop_order_id}")
                    
                    # If position is protected but has averaging order - cancel it
                    if averaging_order:
                        try:
                            self.client.futures_cancel_order(symbol=symbol, orderId=averaging_order['orderId'])
                            logger.info(f"🗑️ Canceled averaging order {averaging_order['orderId']} for {symbol} (position protected)")
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to cancel averaging order: {e}")
                
                elif averaging_order:
                    # Position not protected, keep averaging order
                    position.averaging_order_id = str(averaging_order['orderId'])
                    logger.info(f"📌 Found existing averaging order for {symbol}: {position.averaging_order_id}")
                
                # Only create new averaging order if none exists AND position not protected
                if not averaging_order and not stop_order and hasattr(self, 'risk_manager') and self.risk_manager:
                    order_id = self.risk_manager.place_averaging_order(
                        position=position,
                        liquidation_price=liquidation_price
                    )
                    if order_id:
                        position.averaging_order_id = order_id
                        logger.info(f"🎯 New averaging order placed for {symbol}: {order_id}")
            
            if loaded_count > 0:
                logger.info(f"✅ Loaded {loaded_count} existing positions from Binance")
            
            # Clean up orphaned orders (orders without positions)
            self._cleanup_orphaned_orders(open_orders, orders_by_symbol)
            
        except Exception as e:
            logger.error(f"❌ Failed to load existing positions: {e}")
    
    def _cleanup_orphaned_orders(self, open_orders, orders_by_symbol):
        """Cancel orders that don't belong to any open position."""
        try:
            position_symbols = set(self.positions.keys())
            orphaned_count = 0
            
            # FIRST: Cancel ALL TAKE_PROFIT orders (legacy - we don't use them anymore)
            for order in open_orders:
                order_type = order.get('type')
                if order_type in ['TAKE_PROFIT', 'TAKE_PROFIT_MARKET']:
                    symbol = order['symbol']
                    order_id = str(order['orderId'])
                    try:
                        self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
                        orphaned_count += 1
                        logger.info(f"🗑️ Canceled legacy TAKE_PROFIT order {order_id} for {symbol} (we only use trailing stop now)")
                    except Exception as e:
                        logger.debug(f"Failed to cancel TAKE_PROFIT order {order_id}: {e}")
            
            for symbol, orders in orders_by_symbol.items():
                if symbol not in position_symbols:
                    # Cancel all orders for symbols without positions (except TAKE_PROFIT - already canceled above)
                    for order in orders:
                        order_type = order.get('type')
                        if order_type in ['TAKE_PROFIT', 'TAKE_PROFIT_MARKET']:
                            continue  # Already canceled above
                        try:
                            self.client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
                            orphaned_count += 1
                            logger.info(f"🗑️ Canceled orphaned order {order['orderId']} for {symbol} (no position)")
                        except Exception as e:
                            logger.debug(f"Failed to cancel order {order['orderId']}: {e}")
                else:
                    # For positions with orders, keep only the most recent averaging/stop orders
                    position = self.positions[symbol]
                    side = position.side
                    skip_stop_cleanup = getattr(position, 'stepped_stop_replacing', False)
                    
                    # Group orders by type
                    averaging_orders = []
                    stop_orders = []
                    
                    assigned_avg_id = str(position.averaging_order_id) if hasattr(position, 'averaging_order_id') and position.averaging_order_id else None
                    assigned_stop_id = str(position.stepped_stop_order_id) if hasattr(position, 'stepped_stop_order_id') and position.stepped_stop_order_id else None
                    assigned_avg_found = False
                    assigned_stop_found = False
                    
                    for order in orders:
                        order_type = order.get('type')
                        order_side = order.get('side')
                        order_id = str(order['orderId'])
                        
                        # Averaging orders (LIMIT in same direction)
                        if order_type == 'LIMIT':
                            if (side == 'LONG' and order_side == 'BUY') or (side == 'SHORT' and order_side == 'SELL'):
                                averaging_orders.append(order)
                                if assigned_avg_id and order_id == assigned_avg_id:
                                    assigned_avg_found = True
                        
                        # Stop orders (STOP/STOP_MARKET in opposite direction)
                        # TAKE_PROFIT orders are legacy and should be canceled
                        elif order_type in ['STOP', 'STOP_MARKET']:
                            if (side == 'LONG' and order_side == 'SELL') or (side == 'SHORT' and order_side == 'BUY'):
                                stop_orders.append(order)
                                if assigned_stop_id and order_id == assigned_stop_id:
                                    assigned_stop_found = True
                        elif order_type in ['TAKE_PROFIT', 'TAKE_PROFIT_MARKET']:
                            # Cancel legacy TAKE_PROFIT orders - we don't use them anymore
                            try:
                                self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
                                orphaned_count += 1
                                logger.info(f"🗑️ Canceled legacy TAKE_PROFIT order {order_id} for {symbol} (we only use trailing stop now)")
                            except Exception as e:
                                logger.debug(f"Failed to cancel TAKE_PROFIT order {order_id}: {e}")
                    
                    # Cancel ALL averaging orders if we have an assigned one, or keep only the most recent
                    if assigned_avg_id:
                        # Verify assigned order exists on exchange
                        assigned_exists = assigned_avg_found
                        
                        if assigned_exists:
                            # We have a valid assigned averaging order - cancel ALL others
                            for order in averaging_orders:
                                order_id_str = str(order['orderId'])
                                if order_id_str != assigned_avg_id:
                                    try:
                                        self.client.futures_cancel_order(symbol=symbol, orderId=order_id_str)
                                        orphaned_count += 1
                                        logger.info(f"🗑️ Canceled extra averaging order {order_id_str} for {symbol} (have assigned: {assigned_avg_id})")
                                    except Exception as e:
                                        logger.debug(f"Failed to cancel order {order_id_str}: {e}")
                        else:
                            # Assigned order doesn't exist - clear it and keep only the most recent
                            position.averaging_order_id = None
                            if len(averaging_orders) > 1:
                                averaging_orders.sort(key=lambda x: int(x.get('time', 0)), reverse=True)
                                for order in averaging_orders[1:]:
                                    try:
                                        self.client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
                                        orphaned_count += 1
                                        logger.info(f"🗑️ Canceled duplicate averaging order {order['orderId']} for {symbol} (assigned order missing)")
                                    except Exception as e:
                                        logger.debug(f"Failed to cancel order {order['orderId']}: {e}")
                    elif len(averaging_orders) > 1:
                        # No assigned order, but multiple exist - keep only the most recent
                        averaging_orders.sort(key=lambda x: int(x.get('time', 0)), reverse=True)
                        for order in averaging_orders[1:]:
                            try:
                                self.client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
                                orphaned_count += 1
                                logger.info(f"🗑️ Canceled duplicate averaging order {order['orderId']} for {symbol}")
                            except Exception as e:
                                logger.debug(f"Failed to cancel order {order['orderId']}: {e}")
                    
                    # Cancel ALL stop orders if we have an assigned one, or keep only the most recent
                    if skip_stop_cleanup:
                        logger.debug(f"⏳ {symbol}: Skipping stop cleanup (replacement in progress)")
                    else:
                        if assigned_stop_id:
                            # Verify assigned stop order exists on exchange
                            assigned_exists = assigned_stop_found
                            
                            if assigned_exists:
                                # We have a valid assigned stop order - cancel ALL others
                                for order in stop_orders:
                                    order_id_str = str(order['orderId'])
                                    if order_id_str != assigned_stop_id:
                                        try:
                                            self.client.futures_cancel_order(symbol=symbol, orderId=order_id_str)
                                            orphaned_count += 1
                                            logger.info(f"🗑️ Canceled extra stop order {order_id_str} for {symbol} (have assigned stepped: {assigned_stop_id})")
                                        except Exception as e:
                                            logger.debug(f"Failed to cancel order {order_id_str}: {e}")
                            else:
                                # Assigned stop doesn't exist - clear it and keep only the most recent
                                position.stepped_stop_order_id = None
                                position.stepped_stop_active = False
                                
                                if len(stop_orders) > 1:
                                    stop_orders.sort(key=lambda x: int(x.get('time', 0)), reverse=True)
                                    for order in stop_orders[1:]:
                                        try:
                                            self.client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
                                            orphaned_count += 1
                                            logger.info(f"🗑️ Canceled duplicate stop order {order['orderId']} for {symbol} (assigned stepped order missing)")
                                        except Exception as e:
                                            logger.debug(f"Failed to cancel order {order['orderId']}: {e}")
                        elif len(stop_orders) > 1:
                            # No assigned order, but multiple exist - keep only the most recent
                            stop_orders.sort(key=lambda x: int(x.get('time', 0)), reverse=True)
                            for order in stop_orders[1:]:
                                try:
                                    self.client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
                                    orphaned_count += 1
                                    logger.info(f"🗑️ Canceled duplicate stop order {order['orderId']} for {symbol}")
                                except Exception as e:
                                    logger.debug(f"Failed to cancel order {order['orderId']}: {e}")
            
            if orphaned_count > 0:
                logger.info(f"🧹 Cleaned up {orphaned_count} orphaned/duplicate orders")
        except Exception as e:
            logger.warning(f"⚠️ Failed to cleanup orphaned orders: {e}")

    # ------------------------------------------------------------------
    # Public interface compatible with PaperTrader
    # ------------------------------------------------------------------
    def get_futures_balance(self, use_cache: bool = True) -> float:
        """
        Get futures account balance with caching.
        
        Args:
            use_cache: Use cached value if available (default True)
            
        Returns:
            Available balance in USDT
        """
        now = time.time()
        
        # Return cached if valid
        if use_cache and self.cached_futures_balance is not None:
            if now - self.balance_cache_time < self.balance_cache_ttl:
                logger.debug(f"💰 Using cached balance: ${self.cached_futures_balance:.2f}")
                return self.cached_futures_balance
        
        # Fetch fresh balance
        try:
            account_info = self.client.futures_account(recvWindow=60000)
            for asset in account_info.get('assets', []):
                if asset.get('asset') == 'USDT':
                    balance = float(asset.get('availableBalance', 0.0))
                    self.cached_futures_balance = balance
                    self.balance_cache_time = now
                    logger.debug(f"💰 Fresh balance fetched: ${balance:.2f}")
                    return balance
            return 0.0
        except Exception as e:
            logger.error(f"❌ Failed to get futures balance: {e}")
            # Return cached if available, otherwise 0
            return self.cached_futures_balance if self.cached_futures_balance is not None else 0.0
    
    def get_available_balance(self) -> float:
        """
        Get available balance for new positions from Binance API.
        Uses availableBalance which accounts for margin requirements automatically.
        """
        try:
            account_info = self.client.futures_account(recvWindow=60000)
            
            # Get availableBalance (free balance after margin requirements)
            for asset in account_info.get('assets', []):
                if asset.get('asset') == 'USDT':
                    available = float(asset.get('availableBalance', 0.0))
                    wallet = float(asset.get('walletBalance', 0.0))
                    logger.debug(
                        f"💰 Balance: wallet=${wallet:.2f}, available=${available:.2f}"
                    )
                    return available
            
            return 0.0
        except Exception as e:
            logger.error(f"❌ Failed to get available balance: {e}")
        return 0.0

    def reduce_position_to_initial_size(self, symbol: str, target_size: float, limits=None) -> bool:
        """Reduce live position to its initial size via reduce-only MARKET order."""
        position = self.positions.get(symbol)
        if not position:
            logger.info(f"⏸️ {symbol}: Нет позиции для сброса маржи (live)")
            return False
        
        reduce_qty = position.size - target_size
        if reduce_qty <= 0:
            logger.debug(
                f"ℹ️ {symbol}: Размер позиции уже равен стартовому "
                f"(current={position.size:.6f}, target={target_size:.6f})"
            )
            return False
        
        limits = limits or self.risk_manager._get_symbol_limits(symbol)
        if limits and limits.step_size > 0:
            reduce_qty = self.risk_manager._round_to_step(reduce_qty, limits.step_size)
        if limits and reduce_qty < limits.min_qty:
            reduce_qty = limits.min_qty
        
        if reduce_qty <= 0:
            logger.debug(f"ℹ️ {symbol}: После округления количество к сбросу слишком мало")
            return False
        
        order_side = 'SELL' if position.side == 'LONG' else 'BUY'
        try:
            logger.info(
                f"🔁 {symbol}: Reduce-only MARKET {order_side} для сброса маржи "
                f"(qty={reduce_qty:.6f})"
            )
            self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type='MARKET',
                quantity=reduce_qty,
                reduceOnly='true'
            )
            self.refresh_all_positions()
            return True
        except Exception as exc:
            logger.error(f"❌ {symbol}: Не удалось сбросить маржу reduceOnly ордером: {exc}")
            return False

    def open_position(self, signal, orderbook, adaptive_params=None) -> Optional[Position]:
        symbol = signal.symbol
        direction = signal.direction
        if symbol in self.positions:
            return None

        account_balance = self.get_available_balance()
        entry_price = signal.entry_price
        confidence = signal.confidence
        
        # ✅ Dynamic leverage based on confidence (50x-100x)
        # Formula: leverage = 50 + (confidence - 65) * (50 / 35)
        # 65% → 50x, 80% → 71x, 100% → 100x
        leverage_min = self.config['account']['leverage_min']
        leverage_max = self.config['account']['leverage_max']
        
        if confidence <= 65:
            leverage = leverage_min
        elif confidence >= 100:
            leverage = leverage_max
        else:
            # Linear interpolation between 65% and 100%
            leverage = leverage_min + (confidence - 65) * ((leverage_max - leverage_min) / 35)
            leverage = int(leverage)
        
        # Clamp between min and max
        leverage = max(leverage_min, min(leverage_max, leverage))
        
        logger.info(f"📊 {symbol}: Confidence {confidence:.1f}% → Leverage {leverage}x")

        # ✅ Set ISOLATED margin mode first, then leverage
        self._ensure_isolated_margin(symbol)
        self._ensure_leverage(symbol, leverage)

        # ✅ New position sizing: 2% from leveraged balance
        # position_notional = account_balance × leverage × 2%
        position_size_percent = self.config['account'].get('position_size_percent', 2.0)
        max_position_notional = account_balance * leverage  # Full leveraged balance
        position_notional = max_position_notional * (position_size_percent / 100)
        
        # Calculate quantity from position notional
        quantity = position_notional / entry_price
        margin_used = position_notional / leverage
        
        logger.info(
            f"💰 {symbol}: Balance=${account_balance:.2f}, Leverage={leverage}x, "
            f"Position={position_size_percent}% → Notional=${position_notional:.2f}, "
            f"Margin=${margin_used:.2f}"
        )
        
        # Check minimum margin requirements using RiskManager
        min_margin, min_qty = self.risk_manager.calculate_minimum_margin(
            symbol, entry_price, leverage
        )
        
        # Ensure quantity meets minimum requirements
        if quantity < min_qty:
            logger.warning(
                f"⚠️ {symbol}: Calculated qty {quantity:.4f} < minimum {min_qty}, adjusting"
            )
            quantity = min_qty
            # Recalculate actual margin needed
            margin_used = (min_qty * entry_price) / leverage
            
            # ✅ Check if we have enough balance for minimum quantity
            if margin_used > account_balance:
                logger.warning(
                    f"❌ {symbol}: Insufficient balance for minimum qty. "
                    f"Required: ${margin_used:.2f}, Available: ${account_balance:.2f}"
                )
                return None
        
        if quantity <= 0:
            return None
        
        # ✅ Round quantity to symbol's step_size precision
        limits = self.risk_manager.symbol_limits.get(symbol)
        if limits:
            step_size = limits.step_size
            if step_size > 0:
                # Round to nearest step_size
                quantity = round(quantity / step_size) * step_size
                # Format to correct decimal places
                import math
                decimals = int(round(-math.log(step_size, 10), 0)) if step_size < 1 else 0
                quantity = round(quantity, decimals)
        else:
            # Fallback: round to 4 decimals
            quantity = round(quantity, 4)
        
        logger.debug(f"📊 {symbol}: Final qty={quantity} (after step_size rounding)")

        side = 'BUY' if direction == 'LONG' else 'SELL'

        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=quantity
            )
        except Exception as exc:
            logger.error("❌ Market order submission failed for %s: %s", symbol, exc)
            return None

        fills = order.get('fills') or []
        if fills:
            avg_price = sum(float(f['price']) * float(f['qty']) for f in fills) / sum(float(f['qty']) for f in fills)
        else:
            avg_price = entry_price

        position_value = avg_price * quantity * leverage
        margin = position_value / leverage

        # Calculate liquidation price using RiskManager
        liquidation_price = self.risk_manager.calculate_liquidation_price(
            entry_price=avg_price,
            side=direction,
            leverage=leverage
        )
        
        logger.info(
            f"🛡️ {symbol} {direction}: Entry=${avg_price:.2f}, "
            f"Liquidation=${liquidation_price:.2f}, Margin=${margin:.2f}"
        )

        self.trade_counter += 1
        position = Position(
            id=f"L{self.trade_counter:04d}",
            symbol=symbol,
            side=direction,
            entry_price=avg_price,
            stop_loss=signal.stop_loss,
            take_profit_1=signal.take_profit_1,
            take_profit_2=signal.take_profit_2,
            size=quantity,
            leverage=leverage,
            entry_time=datetime.utcnow(),
            entry_commission=0.0,
            confidence=signal.confidence,
            liquidation_price=liquidation_price,
            position_value_usdt=position_value,
            margin_usdt=margin,
            current_price=avg_price,
            # Initialize advanced risk management fields
            initial_margin=margin,
            initial_entry_price=avg_price,
            initial_size=quantity,  # For Martingale strategy
            averaging_count=0,
            total_margin=margin
        )

        self.positions[symbol] = position
        
        if self.defer_averaging_until_loss:
            logger.debug(
                f"⏸️ {symbol}: Skipping initial averaging order until ROI < 0 (averaging_require_negative_roi)"
            )
            position.averaging_order_id = None
        else:
            # ✅ Place averaging down order immediately after position opens (Martingale)
            available_balance = self.get_available_balance()
            averaging_order_id = self.risk_manager.place_averaging_order(
                position=position,
                liquidation_price=liquidation_price,
                available_balance=available_balance
            )
            if averaging_order_id:
                position.averaging_order_id = averaging_order_id
                logger.info(f"🎯 Martingale averaging order #1 placed for {symbol}: {averaging_order_id}")

        # Stop-loss and Take-profit removed - we only use trailing stop now
        # Trailing stop will be set by _monitor_position_protection when PNL >= +20%
        # No orders are created at position opening - only trailing stop in profit or martingale in loss

        logger.info(
            "%s Opened live position %s %s: price %.4f, qty %.4f, leverage %sx",
            '🟢' if direction == 'LONG' else '🔴', symbol, direction, avg_price, quantity, leverage
        )

        return position

    def update_positions(self, symbol: str, current_price: float) -> Optional[ClosedTrade]:
        if symbol not in self.positions:
            return None

        position_info = self.client.futures_position_information(symbol=symbol)
        if not position_info:
            return None

        info = position_info[0]
        position_amt = float(info.get('positionAmt', 0.0))
        unrealized = float(info.get('unRealizedProfit', 0.0))
        entry_price_from_exchange = float(info.get('entryPrice', 0.0))

        position = self.positions[symbol]
        position.current_price = current_price
        position.unrealized_pnl = unrealized
        if position.entry_price:
            price_diff_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            if position.side == 'SHORT':
                price_diff_pct = -price_diff_pct
            position.unrealized_pnl_percent = price_diff_pct * position.leverage
        else:
            position.unrealized_pnl_percent = 0.0
        
        # ═══════════════════════════════════════════════════════
        # MARTINGALE AVERAGING: Check if averaging order executed
        # ═══════════════════════════════════════════════════════
        current_size_abs = abs(position_amt)
        stored_size_abs = abs(position.size)
        
        # If position size increased significantly (averaging executed)
        if current_size_abs > stored_size_abs * 1.5:  # More than 50% increase
            logger.info(
                f"🎯 {symbol}: Averaging executed! Size: {stored_size_abs:.6f} → {current_size_abs:.6f}"
            )
            
            # Update position data
            position.size = position_amt
            position.averaging_count += 1
            position.entry_price = entry_price_from_exchange  # Exchange calculates average
            position.averaging_order_id = None  # Clear executed order
            
            # Recalculate liquidation price with new entry
            new_liquidation = self.risk_manager.calculate_liquidation_price(
                entry_price=position.entry_price,
                side=position.side,
                leverage=position.leverage
            )
            position.liquidation_price = new_liquidation
            
            logger.info(
                f"📊 {symbol}: Position updated after averaging #{position.averaging_count} | "
                f"New Entry: ${position.entry_price:.4f}, New Liq: ${new_liquidation:.4f}"
            )
            
            pnl_pct = getattr(position, 'unrealized_pnl_percent', None)
            should_place_next = True
            if self.defer_averaging_until_loss:
                if pnl_pct is not None and pnl_pct >= 0:
                    should_place_next = False
            
            if should_place_next:
                # Place next Martingale averaging order (if balance available)
                available_balance = self.get_available_balance()
                next_order_id = self.risk_manager.place_averaging_order(
                    position=position,
                    liquidation_price=new_liquidation,
                    available_balance=available_balance
                )
                
                if next_order_id:
                    position.averaging_order_id = next_order_id
                    multiplier = 2 ** position.averaging_count
                    logger.info(
                        f"🎯 {symbol}: Next Martingale averaging #{position.averaging_count + 1} placed "
                        f"(multiplier={multiplier}x) → Order #{next_order_id}"
                    )
                else:
                    logger.warning(
                        f"⚠️ {symbol}: Cannot place next averaging order "
                        f"(insufficient balance or max count reached)"
                    )
            else:
                logger.info(
                    f"⏸️ {symbol}: Averaging paused after execution "
                    f"(ROI={(pnl_pct if pnl_pct is not None else 0.0):.2f}% ≥ 0). "
                    "Will resume when position returns to loss."
                )
                position.averaging_order_id = None
        
        # ═══════════════════════════════════════════════════════

        if abs(position_amt) < 1e-8:
            # Position closed on exchange (stop/take or manual)
            trades = self.client.futures_account_trades(symbol=symbol, limit=1)
            if trades:
                last_trade = trades[-1]
                close_price = float(last_trade.get('price', current_price))
                realized = float(last_trade.get('realizedPnl', 0.0))
            else:
                close_price = current_price
                realized = unrealized

            close_reason = 'Exchange Close'
            closed_trade = self._finalize_trade(position, close_price, realized, close_reason)
            return closed_trade

        return None

    def _finalize_trade(self, position: Position, close_price: float, realized_pnl: float, reason: str) -> ClosedTrade:
        if position.symbol not in self.positions:
            return None

        self._refresh_balance()
        
        # Fetch commission from recent trades
        total_commission = 0.0
        try:
            trades = self.client.futures_account_trades(symbol=position.symbol, limit=10, recvWindow=60000)
            for trade in trades:
                # Only count trades from this position (recent)
                trade_time = datetime.fromtimestamp(trade['time'] / 1000)
                if trade_time >= position.entry_time:
                    total_commission += float(trade.get('commission', 0))
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch commission for {position.symbol}: {e}")

        pnl_percent = (realized_pnl / position.margin_usdt * 100) if position.margin_usdt else 0.0
        net_pnl = realized_pnl - total_commission

        closed_trade = ClosedTrade(
            id=position.id,
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=close_price,
            size=position.size,
            leverage=position.leverage,
            entry_time=position.entry_time,
            exit_time=datetime.utcnow(),
            duration_seconds=(datetime.utcnow() - position.entry_time).total_seconds(),
            pnl=realized_pnl,
            pnl_percent=pnl_percent,
            close_reason=reason,
            total_commission=total_commission,
            confidence=position.confidence
        )

        self.closed_trades.append(closed_trade)
        self.total_pnl += realized_pnl

        del self.positions[position.symbol]

        pnl_sign = '+' if realized_pnl >= 0 else ''
        net_sign = '+' if net_pnl >= 0 else ''
        emoji = '✅' if net_pnl >= 0 else '❌'
        
        # Detailed logging with commission
        logger.info(
            f"{emoji} CLOSED {position.symbol} {position.side}: "
            f"PNL={pnl_sign}${realized_pnl:.2f}, Commission=${total_commission:.4f}, "
            f"Net={net_sign}${net_pnl:.2f} ({reason})"
        )

        return closed_trade

    def close_position_manually(self, symbol: str, current_price: float, reason: str):
        if symbol not in self.positions:
            return None

        position_info = self.client.futures_position_information(symbol=symbol)
        if not position_info:
            return None

        amt = float(position_info[0].get('positionAmt', 0.0))
        if abs(amt) < 1e-8:
            return None

        quantity = abs(amt)
        side = 'SELL' if amt > 0 else 'BUY'

        try:
            self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=quantity,
                reduceOnly='true'
            )
        except Exception as exc:
            logger.error("❌ Manual close failed for %s: %s", symbol, exc)
            return None

        return self._finalize_trade(self.positions[symbol], current_price, self.positions[symbol].unrealized_pnl, reason)

    def refresh_all_positions(self):
        """Refresh current prices and PNL for all open positions from Binance API.
        Also loads new positions that were opened manually on exchange."""
        try:
            # Fetch positions with increased timeout for testnet
            positions_data = self.client.futures_position_information(recvWindow=10000)
            
            for pos_data in positions_data:
                position_amt = float(pos_data.get('positionAmt', 0))
                if position_amt == 0:
                    continue  # Skip closed positions
                
                symbol = pos_data['symbol']
                entry_price = float(pos_data['entryPrice'])
                mark_price = float(pos_data['markPrice'])
                unrealized_pnl = float(pos_data['unRealizedProfit'])
                
                # Update existing position
                if symbol in self.positions:
                    position = self.positions[symbol]
                    # IMPORTANT: Preserve order IDs and risk management state before updating
                    # These are set by _monitor_position_protection and must not be lost
                    saved_averaging_order_id = getattr(position, 'averaging_order_id', None)
                    saved_stepped_stop_order_id = getattr(position, 'stepped_stop_order_id', None)
                    saved_stepped_stop_active = getattr(position, 'stepped_stop_active', False)
                    saved_is_protected = getattr(position, 'is_protected', False)
                    saved_initial_size = getattr(position, 'initial_size', None)
                    saved_averaging_count = getattr(position, 'averaging_count', 0)
                    
                    # Update price and PNL
                    position.current_price = mark_price
                    position.unrealized_pnl = unrealized_pnl
                    
                    # Calculate PNL percentage
                    if position.entry_price > 0:
                        price_diff_pct = ((mark_price - position.entry_price) / position.entry_price) * 100
                        if position.side == 'SHORT':
                            price_diff_pct = -price_diff_pct
                        position.unrealized_pnl_percent = price_diff_pct * position.leverage
                    else:
                        # Entry price is 0 or invalid - set PNL to 0
                        position.unrealized_pnl_percent = 0.0
                        logger.warning(f"⚠️ {symbol}: Entry price is 0 or invalid, cannot calculate PNL%")
                    
                    # Restore preserved fields (ALWAYS restore, even if None/False)
                    # This ensures fields are not lost during refresh
                    position.averaging_order_id = saved_averaging_order_id
                    position.stepped_stop_order_id = saved_stepped_stop_order_id
                    position.stepped_stop_active = saved_stepped_stop_active
                    position.is_protected = saved_is_protected
                    position.initial_size = saved_initial_size if saved_initial_size else position.size
                    position.averaging_count = saved_averaging_count
                    
                    # Log if order IDs were preserved
                    if saved_averaging_order_id:
                        logger.debug(
                            f"💾 {symbol}: Preserved order IDs - "
                            f"averaging={saved_averaging_order_id}"
                        )
                else:
                    # Load new position that was opened manually
                    side = 'LONG' if position_amt > 0 else 'SHORT'
                    quantity = abs(position_amt)
                    
                    # Calculate take profit levels
                    tp_distance = entry_price * 0.01
                    take_profit_1 = entry_price + tp_distance if side == 'LONG' else entry_price - tp_distance
                    take_profit_2 = entry_price + tp_distance * 2 if side == 'LONG' else entry_price - tp_distance * 2
                    
                    position = Position(
                        id=f"{symbol}_{int(datetime.now().timestamp())}",
                        symbol=symbol,
                        side=side,
                        entry_price=entry_price,
                        size=quantity,
                        leverage=int(pos_data.get('leverage', 1)),
                        stop_loss=0.0,
                        take_profit_1=take_profit_1,
                        take_profit_2=take_profit_2,
                        entry_time=datetime.now(),
                        entry_commission=0.0,
                        liquidation_price=0.0,
                        confidence=75.0,
                        position_value_usdt=quantity * entry_price
                    )
                    
                    position.current_price = mark_price
                    position.unrealized_pnl = unrealized_pnl
                    
                    self.positions[symbol] = position
                    logger.info(f"📥 Loaded new manual position: {symbol} {side} @ ${entry_price:.2f}")
                
        except Exception as e:
            # Timeouts are common on Testnet, log as warning
            if 'timeout' in str(e).lower() or 'timed out' in str(e).lower():
                logger.debug(f"⏱️ Position refresh timeout (testnet): {e}")
            else:
                logger.warning(f"⚠️ Failed to refresh positions: {e}")

    def close_all_positions(self, current_prices: Dict[str, float]):
        for symbol in list(self.positions.keys()):
            price = current_prices.get(symbol, self.positions[symbol].current_price)
            self.close_position_manually(symbol, price, 'Manual Close')

    def get_statistics(self) -> Dict:
        if not self.closed_trades:
            return {
                'total_trades': 0,
                'winners': 0,
                'losers': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'best_trade': 0,
                'worst_trade': 0,
                'avg_duration': 0,
                'avg_pnl': 0,
                'long_count': 0,
                'short_count': 0,
                'roi_pct': 0
            }

        winners = [t for t in self.closed_trades if t.pnl > 0]
        losers = [t for t in self.closed_trades if t.pnl <= 0]

        total_profit = sum(t.pnl for t in winners)
        total_loss = abs(sum(t.pnl for t in losers))

        long_trades = [t for t in self.closed_trades if t.side == 'LONG']
        short_trades = [t for t in self.closed_trades if t.side == 'SHORT']

        roi_pct = ((self.balance - self.starting_balance) / self.starting_balance * 100) if self.starting_balance else 0

        return {
            'total_trades': len(self.closed_trades),
            'winners': len(winners),
            'losers': len(losers),
            'win_rate': (len(winners) / len(self.closed_trades)) * 100,
            'avg_win': (total_profit / len(winners)) if winners else 0,
            'avg_loss': (total_loss / len(losers)) if losers else 0,
            'profit_factor': (total_profit / total_loss) if total_loss > 0 else 0,
            'best_trade': max((t.pnl for t in self.closed_trades), default=0),
            'worst_trade': min((t.pnl for t in self.closed_trades), default=0),
            'avg_duration': sum(t.duration_seconds for t in self.closed_trades) / len(self.closed_trades),
            'avg_pnl': sum(t.pnl for t in self.closed_trades) / len(self.closed_trades),
            'long_count': len(long_trades),
            'short_count': len(short_trades),
            'roi_pct': roi_pct
        }

    def save_session(self, filename: str):
        # Placeholder: could be extended to export order history for live trading
        pass

