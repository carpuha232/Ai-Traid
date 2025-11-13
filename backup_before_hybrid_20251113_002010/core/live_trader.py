#!/usr/bin/env python3
"""
💹 LIVE TRADER
Operate against Binance Futures (UM) while keeping the interface aligned with PaperTrader.
"""

from __future__ import annotations

import logging
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
                    elif order_type in ['STOP', 'STOP_MARKET', 'TAKE_PROFIT', 'TAKE_PROFIT_MARKET']:
                        if (side == 'LONG' and order_side == 'SELL') or (side == 'SHORT' and order_side == 'BUY'):
                            stop_order = order
                
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
            
            for symbol, orders in orders_by_symbol.items():
                if symbol not in position_symbols:
                    # Cancel all orders for symbols without positions
                    for order in orders:
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
                    
                    # Group orders by type
                    averaging_orders = []
                    stop_orders = []
                    
                    for order in orders:
                        order_type = order.get('type')
                        order_side = order.get('side')
                        order_id = str(order['orderId'])
                        
                        # Skip if this is the assigned order
                        if (hasattr(position, 'averaging_order_id') and position.averaging_order_id == order_id) or \
                           (hasattr(position, 'stepped_stop_order_id') and position.stepped_stop_order_id == order_id):
                            continue
                        
                        # Averaging orders (LIMIT in same direction)
                        if order_type == 'LIMIT':
                            if (side == 'LONG' and order_side == 'BUY') or (side == 'SHORT' and order_side == 'SELL'):
                                averaging_orders.append(order)
                        
                        # Stop orders (STOP/STOP_MARKET in opposite direction)
                        elif order_type in ['STOP', 'STOP_MARKET', 'TAKE_PROFIT', 'TAKE_PROFIT_MARKET']:
                            if (side == 'LONG' and order_side == 'SELL') or (side == 'SHORT' and order_side == 'BUY'):
                                stop_orders.append(order)
                    
                    # Cancel duplicate averaging orders
                    for order in averaging_orders:
                        try:
                            self.client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
                            orphaned_count += 1
                            logger.info(f"🗑️ Canceled duplicate averaging order {order['orderId']} for {symbol}")
                        except Exception as e:
                            logger.debug(f"Failed to cancel order {order['orderId']}: {e}")
                    
                    # Cancel duplicate stop orders
                    for order in stop_orders:
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
            averaging_count=0,
            total_margin=margin
        )

        self.positions[symbol] = position
        
        # ✅ Place averaging down order immediately after position opens
        averaging_order_id = self.risk_manager.place_averaging_order(
            position=position,
            liquidation_price=liquidation_price
        )
        if averaging_order_id:
            position.averaging_order_id = averaging_order_id
            logger.info(f"🎯 Averaging order placed for {symbol}: {averaging_order_id}")

        # Configure stop/take in reduceOnly mode (LIMIT orders)
        try:
            opposite = 'SELL' if direction == 'LONG' else 'BUY'
            
            # Calculate limit prices (slightly worse than trigger to ensure execution)
            slippage = 0.002  # 0.2%
            stop_price = float(signal.stop_loss)
            tp_price = float(signal.take_profit_1)
            
            if direction == 'LONG':
                stop_limit_price = stop_price * (1 - slippage)
                tp_limit_price = tp_price * (1 + slippage)
            else:  # SHORT
                stop_limit_price = stop_price * (1 + slippage)
                tp_limit_price = tp_price * (1 - slippage)
            
            # Round prices to tick size
            stop_limit_price = self.risk_manager._round_to_tick(stop_limit_price, symbol)
            tp_limit_price = self.risk_manager._round_to_tick(tp_limit_price, symbol)

            # Stop-loss (STOP limit order)
            self.client.futures_create_order(
                symbol=symbol,
                side=opposite,
                type='STOP',
                stopPrice=stop_price,
                price=stop_limit_price,
                quantity=quantity,
                reduceOnly='true',
                timeInForce='GTC'
            )

            # Take-profit (TAKE_PROFIT limit order)
            self.client.futures_create_order(
                symbol=symbol,
                side=opposite,
                type='TAKE_PROFIT',
                stopPrice=tp_price,
                price=tp_limit_price,
                quantity=quantity,
                reduceOnly='true',
                timeInForce='GTC'
            )
        except Exception as exc:
            logger.warning("⚠️ Failed to create stop/take orders for %s: %s", symbol, exc)

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

        position = self.positions[symbol]
        position.current_price = current_price
        position.unrealized_pnl = unrealized

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
                    position.current_price = mark_price
                    position.unrealized_pnl = unrealized_pnl
                    
                    # Calculate PNL percentage
                    if position.entry_price > 0:
                        price_diff_pct = ((mark_price - position.entry_price) / position.entry_price) * 100
                        if position.side == 'SHORT':
                            price_diff_pct = -price_diff_pct
                        position.unrealized_pnl_percent = price_diff_pct * position.leverage
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

