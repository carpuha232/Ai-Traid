"""
Advanced Risk Management System
- Minimum margin calculation
- Liquidation price calculation
- Averaging down (martingale) orders
- Stepped stop-loss in profit
"""
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from binance.client import Client

logger = logging.getLogger(__name__)


@dataclass
class SymbolLimits:
    """Trading limits for a symbol."""
    symbol: str
    min_qty: float
    max_qty: float
    step_size: float
    min_notional: float
    tick_size: float
    
    
@dataclass
class AveragingOrder:
    """Averaging down order details."""
    symbol: str
    side: str  # 'BUY' or 'SELL'
    price: float  # Limit price
    quantity: float
    margin: float  # Margin for this order
    distance_from_liq_pct: float  # Distance from liquidation in %


class RiskManager:
    """
    Advanced risk management system with:
    - Minimum margin calculation per pair
    - Liquidation price calculation
    - Averaging down orders (martingale)
    - Stepped stop-loss for profit protection
    """
    
    def __init__(self, client: Client, config: Dict):
        """
        Args:
            client: Binance client
            config: Bot configuration
        """
        self.client = client
        self.config = config
        self.symbol_limits: Dict[str, SymbolLimits] = {}
        
        # Load symbol limits
        self._load_symbol_limits()
        
    def _load_symbol_limits(self):
        """Load trading limits for all configured pairs from exchange."""
        try:
            exchange_info = self.client.futures_exchange_info()
            pairs = self.config.get('signals', {}).get('pairs', [])
            
            for symbol_info in exchange_info['symbols']:
                symbol = symbol_info['symbol']
                if symbol not in pairs:
                    continue
                
                # Extract filters
                min_qty = 0.0
                max_qty = 0.0
                step_size = 0.0
                min_notional = 0.0
                tick_size = 0.0
                
                for f in symbol_info['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        min_qty = float(f['minQty'])
                        max_qty = float(f['maxQty'])
                        step_size = float(f['stepSize'])
                    elif f['filterType'] == 'PRICE_FILTER':
                        tick_size = float(f['tickSize'])
                    elif f['filterType'] == 'MIN_NOTIONAL':
                        min_notional = float(f['notional'])
                
                self.symbol_limits[symbol] = SymbolLimits(
                    symbol=symbol,
                    min_qty=min_qty,
                    max_qty=max_qty,
                    step_size=step_size,
                    min_notional=min_notional,
                    tick_size=tick_size
                )
                
                logger.info(
                    f"📊 {symbol}: minQty={min_qty}, minNotional={min_notional:.2f}, "
                    f"stepSize={step_size}, tickSize={tick_size}"
                )
                
        except Exception as e:
            logger.error(f"❌ Failed to load symbol limits: {e}")
    
    def _get_symbol_limits(self, symbol: str) -> Optional[SymbolLimits]:
        """
        Retrieve limits for symbol from cache or fetch on demand.
        Needed when managing positions for symbols outside configured pairs.
        """
        limits = self.symbol_limits.get(symbol)
        if limits:
            return limits

        try:
            exchange_info = self.client.futures_exchange_info()
            for symbol_info in exchange_info['symbols']:
                if symbol_info['symbol'] != symbol:
                    continue

                min_qty = 0.0
                max_qty = 0.0
                step_size = 0.0
                min_notional = 0.0
                tick_size = 0.0

                for f in symbol_info['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        min_qty = float(f['minQty'])
                        max_qty = float(f['maxQty'])
                        step_size = float(f['stepSize'])
                    elif f['filterType'] == 'PRICE_FILTER':
                        tick_size = float(f['tickSize'])
                    elif f['filterType'] == 'MIN_NOTIONAL':
                        min_notional = float(f.get('notional') or f.get('minNotional', 0))

                limits = SymbolLimits(
                    symbol=symbol,
                    min_qty=min_qty,
                    max_qty=max_qty,
                    step_size=step_size,
                    min_notional=min_notional,
                    tick_size=tick_size
                )
                self.symbol_limits[symbol] = limits

                logger.info(
                    f"📊 {symbol}: (on-demand) minQty={min_qty}, minNotional={min_notional:.2f}, "
                    f"stepSize={step_size}, tickSize={tick_size}"
                )

                return limits
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch limits for {symbol}: {e}")

        return None

    def calculate_minimum_margin(
        self, 
        symbol: str, 
        price: float, 
        leverage: int
    ) -> Tuple[float, float]:
        """
        Calculate minimum margin and quantity for a position.
        
        Args:
            symbol: Trading pair
            price: Entry price
            leverage: Position leverage
            
        Returns:
            (min_margin, min_quantity)
        """
        limits = self._get_symbol_limits(symbol)
        if not limits:
            logger.warning(f"⚠️ No limits found for {symbol}, using defaults")
            return 10.0, 0.001
        
        # Calculate minimum quantity from minNotional
        # notional = price * quantity
        # We need: price * quantity >= min_notional
        min_qty_from_notional = limits.min_notional / price
        
        # Use maximum of minQty and calculated quantity
        min_qty = max(limits.min_qty, min_qty_from_notional)
        
        # Round up to step_size
        min_qty = self._round_to_step(min_qty, limits.step_size)
        
        # Calculate margin needed for this quantity
        # margin = (price * quantity) / leverage
        position_value = price * min_qty
        min_margin = position_value / leverage
        
        logger.debug(
            f"💰 {symbol}: min_margin=${min_margin:.2f}, "
            f"min_qty={min_qty}, position_value=${position_value:.2f}"
        )
        
        return min_margin, min_qty
    
    def calculate_liquidation_price(
        self,
        entry_price: float,
        side: str,
        leverage: int,
        maintenance_margin_rate: float = 0.004  # 0.4% for most pairs
    ) -> float:
        """
        Calculate liquidation price for a position.
        
        Formula for LONG:
        liq_price = entry_price * (1 - (1/leverage) + mmr)
        
        Formula for SHORT:
        liq_price = entry_price * (1 + (1/leverage) - mmr)
        
        Args:
            entry_price: Position entry price
            side: 'LONG' or 'SHORT'
            leverage: Position leverage
            maintenance_margin_rate: MMR (default 0.4%)
            
        Returns:
            Liquidation price
        """
        if side == 'LONG':
            liq_price = entry_price * (1 - (1/leverage) + maintenance_margin_rate)
        else:  # SHORT
            liq_price = entry_price * (1 + (1/leverage) - maintenance_margin_rate)
        
        logger.debug(
            f"🔴 Liquidation price for {side} @ ${entry_price:.2f} "
            f"with {leverage}x: ${liq_price:.2f}"
        )
        
        return liq_price
    
    def calculate_averaging_order_price(
        self,
        entry_price: float,
        liquidation_price: float,
        side: str,
        distance_pct: Optional[float] = None
    ) -> float:
        """
        Calculate price for averaging down order.
        Order is placed at a fixed percentage distance from liquidation price.
        IMPORTANT: Order is ALWAYS placed BEFORE liquidation to ensure it executes before liquidation.
        
        Args:
            entry_price: Original entry price
            liquidation_price: Calculated liquidation price
            side: 'LONG' or 'SHORT'
            distance_pct: Distance from liquidation in % (overrides config if provided)
            
        Returns:
            Price for averaging order (guaranteed to be above liquidation for LONG, below for SHORT)
        """
        risk_cfg = self.config.get('risk', {})
        
        if distance_pct is None:
            distance_pct = risk_cfg.get('averaging_distance_from_liq_pct', 0.5)
        
        # Safety: distance_pct must be positive
        if distance_pct <= 0:
            logger.warning(
                f"⚠️ Averaging distance {distance_pct}% is invalid. "
                "Using default 0.5% distance from liquidation."
            )
            distance_pct = 0.5
        
        # Calculate fixed offset from liquidation price
        offset = liquidation_price * (distance_pct / 100.0)
        
        # Minimum safety margin (same as distance for clarity)
        min_distance_from_liq_pct = distance_pct
        
        if side == 'LONG':
            # For LONG: liq price is below entry
            # Order MUST be above liquidation to execute before liquidation
            order_price = liquidation_price + offset
            
            if order_price <= liquidation_price:
                # Emergency: place order at least distance_pct above liquidation
                order_price = liquidation_price * (1 + distance_pct / 100.0)
                logger.error(
                    f"🚨 {side}: Averaging order adjusted to ${order_price:.4f} "
                    f"to stay {distance_pct:.2f}% above liquidation ${liquidation_price:.4f}"
                )
        else:  # SHORT
            # For SHORT: liq price is above entry
            # Order MUST be below liquidation to execute before liquidation
            order_price = liquidation_price - offset
            
            if order_price >= liquidation_price:
                # Emergency: place order at least distance_pct below liquidation
                order_price = liquidation_price * (1 - distance_pct / 100.0)
                logger.error(
                    f"🚨 {side}: Averaging order adjusted to ${order_price:.4f} "
                    f"to stay {distance_pct:.2f}% below liquidation ${liquidation_price:.4f}"
                )
        
        # Calculate actual distance from liquidation for logging
        if side == 'LONG':
            actual_distance_pct = ((order_price - liquidation_price) / liquidation_price) * 100.0
        else:
            actual_distance_pct = ((liquidation_price - order_price) / liquidation_price) * 100.0
        
        logger.info(
            f"📍 Averaging order for {side}: entry=${entry_price:.4f}, "
            f"liq=${liquidation_price:.4f}, order=${order_price:.4f} "
            f"(fixed distance {distance_pct:.2f}% → actual {actual_distance_pct:.2f}% from liq)"
        )
        
        return order_price
    
    def calculate_stepped_stop_loss(self, pnl_percent: float) -> Optional[float]:
        """
        Calculate stepped stop-loss level based on current PNL.
        
        Logic:
        - Activates at +10% PNL → stop at +10%
        - +30% → stop at +15%
        - +40% → stop at +30%
        - +50% → stop at +40%
        - +60% → stop at +50%
        - +70% → stop at +60%
        - +80% → stop at +90%
        - +90% → stop at +90%
        - +100% → stop at +90%
        
        Args:
            pnl_percent: Current unrealized PNL in %
            
        Returns:
            Stop-loss level in % (or None if not activated)
        """
        if pnl_percent < 10.0:
            return None  # Not activated yet
        
        # Stepped logic (user's specification)
        if pnl_percent < 30:
            return 10.0  # PNL 10-29% → stop at +10%
        elif pnl_percent < 40:
            return 15.0  # PNL 30-39% → stop at +15%
        elif pnl_percent < 50:
            return 30.0  # PNL 40-49% → stop at +30%
        elif pnl_percent < 60:
            return 40.0  # PNL 50-59% → stop at +40%
        elif pnl_percent < 70:
            return 50.0  # PNL 60-69% → stop at +50%
        elif pnl_percent < 80:
            return 60.0  # PNL 70-79% → stop at +60%
        elif pnl_percent < 90:
            return 90.0  # PNL 80-89% → stop at +90%
        else:  # 90%+
            return 90.0  # PNL 90%+ → stop at +90%
    
    def calculate_stop_price_from_pnl(
        self,
        entry_price: float,
        side: str,
        stop_pnl_pct: float,
        leverage: int
    ) -> float:
        """
        Calculate stop price from desired PNL percentage.
        
        Args:
            entry_price: Position entry price
            side: 'LONG' or 'SHORT'
            stop_pnl_pct: Desired stop PNL in %
            leverage: Position leverage
            
        Returns:
            Stop price
        """
        # PNL % = ((exit - entry) / entry) * 100 * leverage (for LONG)
        # So: price_change_pct = stop_pnl_pct / leverage
        price_change_pct = stop_pnl_pct / leverage
        
        if side == 'LONG':
            stop_price = entry_price * (1 + price_change_pct / 100.0)
        else:  # SHORT
            stop_price = entry_price * (1 - price_change_pct / 100.0)
        
        return stop_price
    
    def calculate_protective_price(
        self,
        entry_price: float,
        liquidation_price: float,
        side: str
    ) -> float:
        """
        Calculate price for protective order (80% distance to liquidation).
        
        Args:
            entry_price: Position entry price
            liquidation_price: Calculated liquidation price
            side: 'LONG' or 'SHORT'
            
        Returns:
            Price for protective order
        """
        offset_pct = self.config.get('risk', {}).get('protective_liq_offset_pct', 0.016)
        
        if side == 'LONG':
            # For LONG: protective order between entry and liq
            # offset_pct = 0.016 means 80% of distance (1 - 0.016 = 0.984 ≈ 80%)
            price_diff = entry_price - liquidation_price
            protective_price = liquidation_price + price_diff * (1 - offset_pct)
        else:  # SHORT
            # For SHORT: protective order between entry and liq
            price_diff = liquidation_price - entry_price
            protective_price = liquidation_price - price_diff * (1 - offset_pct)
        
        logger.debug(
            f"📍 Protective order for {side}: entry=${entry_price:.2f}, "
            f"liq=${liquidation_price:.2f}, protective=${protective_price:.2f} "
            f"(offset={offset_pct*100:.2f}%)"
        )
        
        return protective_price
    
    def place_protective_order(
        self,
        position,
        liquidation_price: float
    ) -> Optional[str]:
        """
        Place a protective order near liquidation to close PART of position.
        Order size equals initial margin (not full position).
        
        Args:
            position: Position object
            liquidation_price: Calculated liquidation price
            
        Returns:
            Order ID or None if failed
        """
        if not self.config.get('risk', {}).get('protective_order_enabled', False):
            logger.debug("Protective orders disabled in config")
            return None
        
        # Calculate protective price (80% to liquidation)
        protective_price = self.calculate_protective_price(
            entry_price=position.entry_price,
            liquidation_price=liquidation_price,
            side=position.side
        )
        
        # Calculate quantity for MARGIN amount (not full position!)
        # This closes part of position equal to initial margin
        margin = getattr(position, 'initial_margin', position.margin_usdt)
        quantity = (margin * position.leverage) / protective_price
        
        # Round to symbol limits
        limits = self._get_symbol_limits(position.symbol)
        if limits:
            raw_price = protective_price
            raw_qty = quantity
            quantity = self._round_to_step(quantity, limits.step_size)
            protective_price = self._round_to_tick(protective_price, limits.tick_size)
            logger.debug(
                f"🔢 {position.symbol}: Rounded qty {raw_qty:.6f}→{quantity:.6f}, "
                f"price {raw_price:.6f}→{protective_price:.6f}"
            )
        
        # Determine order side (LONG sells to close, SHORT buys to close)
        order_side = 'SELL' if position.side == 'LONG' else 'BUY'
        
        try:
            logger.info(
                f"🛡️ Placing PROTECTIVE order for {position.symbol} {position.side}: "
                f"price=${protective_price:.4f}, qty={quantity}, margin=${margin:.2f}"
            )
            
            # Place LIMIT order with reduceOnly
            order = self.client.futures_create_order(
                symbol=position.symbol,
                side=order_side,
                type='LIMIT',
                timeInForce='GTC',
                price=protective_price,
                quantity=quantity,
                reduceOnly='true'  # This closes part of position
            )
            
            order_id = str(order.get('orderId', ''))
            logger.info(
                f"✅ ORDER PLACED: {position.symbol} PROTECTIVE #{order_id} | "
                f"Type=LIMIT {order_side} @ ${protective_price:.4f} | Qty={quantity}"
            )
            return order_id
            
        except Exception as e:
            logger.error(f"❌ Failed to place protective order for {position.symbol}: {e}")
            return None
    
    def place_averaging_order(
        self,
        position,
        liquidation_price: float,
        available_balance: Optional[float] = None
    ) -> Optional[str]:
        """
        Place a limit order for averaging down near liquidation.
        Supports Martingale strategy: each next order doubles in size.
        
        Args:
            position: Position object
            liquidation_price: Calculated liquidation price
            available_balance: Available balance for margin (optional)
            
        Returns:
            Order ID or None if failed
        """
        if not self.config.get('risk', {}).get('averaging_down_enabled', False):
            logger.debug("Averaging down disabled in config")
            return None
        
        # Check max averaging count
        max_count = self.config.get('risk', {}).get('averaging_max_count', 50)
        if position.averaging_count >= max_count:
            logger.warning(f"⚠️ {position.symbol}: Max averaging count {max_count} reached")
            return None
        
        martingale_enabled = self.config.get('risk', {}).get('averaging_martingale_enabled', False)
        
        # Calculate order price (fixed distance from liquidation)
        order_price = self.calculate_averaging_order_price(
            entry_price=position.entry_price,
            liquidation_price=liquidation_price,
            side=position.side
        )
        
        # Calculate quantity: размер равен текущей марже в сделке (та же маржа)
        # Используем текущий размер позиции (не умножаем на 2^averaging_count)
        quantity = position.size
        
        if quantity <= 0:
            logger.error(
                f"❌ {position.symbol}: Cannot calculate averaging order - position size is {position.size:.6f}"
            )
            return None
        
        logger.info(
            f"📊 {position.symbol}: Martingale averaging: "
            f"qty={quantity:.6f} (равно текущей марже в сделке)"
        )
        
        # Round to symbol limits
        limits = self._get_symbol_limits(position.symbol)
        if limits:
            raw_price = order_price
            raw_qty = quantity
            quantity = self._round_to_step(quantity, limits.step_size)
            order_price = self._round_to_tick(order_price, limits.tick_size)
            
            # Check if quantity is too small after rounding
            if quantity < limits.min_qty:
                logger.warning(
                    f"⚠️ {position.symbol}: Calculated quantity {raw_qty:.6f} too small after rounding. "
                    f"Min qty: {limits.min_qty}, rounded: {quantity:.6f}. Using min_qty instead."
                )
                quantity = limits.min_qty
            
            # Check if notional (price * quantity) meets minimum requirement
            notional = order_price * quantity
            if limits.min_notional > 0 and notional < limits.min_notional:
                # Calculate minimum quantity to meet notional requirement
                min_qty_from_notional = limits.min_notional / order_price
                # Round up to step_size
                min_qty_from_notional = ((int(min_qty_from_notional / limits.step_size) + 1) * limits.step_size)
                # Round to step_size again to ensure precision (fix floating point errors)
                min_qty_from_notional = self._round_to_step(min_qty_from_notional, limits.step_size)
                if min_qty_from_notional > quantity:
                    logger.warning(
                        f"⚠️ {position.symbol}: Notional ${notional:.2f} < min_notional ${limits.min_notional:.2f}. "
                        f"Increasing quantity from {quantity:.6f} to {min_qty_from_notional:.6f}"
                    )
                    quantity = min_qty_from_notional
                    # Recalculate notional and margin
                    notional = order_price * quantity
                    
                    # Verify that notional now meets requirement (safety check)
                    if notional < limits.min_notional:
                        # If still below, increase by one more step_size
                        quantity += limits.step_size
                        quantity = self._round_to_step(quantity, limits.step_size)
                        notional = order_price * quantity
                        logger.warning(
                            f"⚠️ {position.symbol}: Notional still below min after adjustment. "
                            f"Further increased quantity to {quantity:.6f}, notional=${notional:.2f}"
                        )
                    
                    required_margin = notional / position.leverage
                    # Check balance again with increased quantity
                    if available_balance is not None and required_margin > available_balance:
                        logger.warning(
                            f"⚠️ {position.symbol}: Insufficient balance for averaging with min_notional. "
                            f"Required: ${required_margin:.2f}, Available: ${available_balance:.2f}"
                        )
                        return None
            
            logger.debug(
                f"🔢 {position.symbol}: Rounded qty {raw_qty:.6f}→{quantity:.6f}, "
                f"price {raw_price:.6f}→{order_price:.6f}, notional=${notional:.2f}"
            )
        else:
            # No limits available - calculate notional for logging
            notional = order_price * quantity
        
        # Final check: quantity must be > 0
        if quantity <= 0:
            logger.error(
                f"❌ {position.symbol}: Cannot place averaging order - quantity is {quantity:.6f}. "
                f"Initial size: {initial_size:.6f}, multiplier: {multiplier if martingale_enabled else 1}"
            )
            return None
        
        # Calculate required margin for this order (after all adjustments)
        position_value = order_price * quantity
        required_margin = position_value / position.leverage
        
        # Final check: ensure notional meets minimum requirement (for all coins)
        limits = self._get_symbol_limits(position.symbol)
        if limits and limits.min_notional > 0:
            final_notional = order_price * quantity
            if final_notional < limits.min_notional:
                logger.error(
                    f"❌ {position.symbol}: Final notional ${final_notional:.2f} < min_notional ${limits.min_notional:.2f} "
                    f"after all adjustments. Cannot place order."
                )
                return None
        
        # Check if we have enough balance
        if available_balance is not None and required_margin > available_balance:
            logger.warning(
                f"⚠️ {position.symbol}: Insufficient balance for averaging. "
                f"Required: ${required_margin:.2f}, Available: ${available_balance:.2f}"
            )
            return None
        
        # Cancel old averaging orders FIRST (before placing new one)
        try:
            open_orders = self.client.futures_get_open_orders(symbol=position.symbol, recvWindow=60000)
            order_side = 'BUY' if position.side == 'LONG' else 'SELL'
            for order in open_orders:
                order_type = order.get('type')
                if order_type == 'LIMIT' and order.get('side') == order_side:
                    order_id = str(order.get('orderId', ''))
                    # Skip if this is the assigned order
                    if hasattr(position, 'averaging_order_id') and position.averaging_order_id == order_id:
                        continue
                    try:
                        self.client.futures_cancel_order(symbol=position.symbol, orderId=order_id)
                        logger.info(f"🗑️ Canceled old averaging order {order_id} for {position.symbol} before placing new one")
                    except Exception as e:
                        logger.debug(f"Failed to cancel old averaging order {order_id}: {e}")
        except Exception as e:
            logger.debug(f"Error checking old averaging orders: {e}")
        
        # Determine order side (LONG buys more, SHORT sells more)
        order_side = 'BUY' if position.side == 'LONG' else 'SELL'
        
        try:
            logger.info(
                f"🎯 Placing averaging order #{position.averaging_count + 1} for {position.symbol} {position.side}: "
                f"price=${order_price}, qty={quantity}, margin=${required_margin:.2f}"
            )
            
            order = self.client.futures_create_order(
                symbol=position.symbol,
                side=order_side,
                type='LIMIT',
                timeInForce='GTC',
                price=order_price,
                quantity=quantity,
                reduceOnly='false'  # This adds to position
            )
            
            order_id = str(order.get('orderId', ''))
            logger.info(
                f"✅ AVERAGING ORDER PLACED: {position.symbol} #{order_id} | "
                f"Type=LIMIT {order_side} @ ${order_price:.4f} | Qty={quantity} | "
                f"Count={position.averaging_count + 1} | Margin=${required_margin:.2f}"
            )
            return order_id
            
        except Exception as e:
            logger.error(f"❌ Failed to place averaging order for {position.symbol}: {e}")
            return None
    
    def place_progressive_stop_order(
        self,
        position,
        stop_pnl_pct: float
    ) -> Optional[str]:
        """
        Place progressive stop-loss order at specified PNL level.
        
        Стоп-лосс: лимитный ордер, новый ставится ПЕРВЫМ, потом удаляется старый.
        
        Args:
            position: Position object
            stop_pnl_pct: Stop level in PNL % (e.g., 10.0 for +10%)
            
        Returns:
            Order ID or None if failed
        """
        if not self.config.get('risk', {}).get('stepped_stop_enabled', False):
            logger.debug("Progressive stop disabled in config")
            return None
        
        # Calculate stop price from PNL percentage FIRST
        stop_price = self.calculate_stop_price_from_pnl(
            entry_price=position.entry_price,
            side=position.side,
            stop_pnl_pct=stop_pnl_pct,
            leverage=position.leverage
        )
        
        # Round to symbol limits
        limits = self._get_symbol_limits(position.symbol)
        if limits:
            stop_price = self._round_to_tick(stop_price, limits.tick_size)
        
        # Determine order side (LONG sells to close, SHORT buys to close)
        order_side = 'SELL' if position.side == 'LONG' else 'BUY'
        
        # Calculate limit price (slightly worse than stop to ensure execution)
        slippage = 0.002  # 0.2% slippage
        if position.side == 'LONG':
            limit_price = stop_price * (1 - slippage)
        else:  # SHORT
            limit_price = stop_price * (1 + slippage)
        
        limit_price = self._round_to_tick(limit_price, limits.tick_size) if limits else limit_price
        
        # ВАЖНО: Сначала ставим НОВЫЙ ордер, потом удаляем старый!
        old_order_id = None
        if hasattr(position, 'stepped_stop_order_id') and position.stepped_stop_order_id:
            old_order_id = position.stepped_stop_order_id
        
        try:
            logger.info(
                f"🛡️ Placing progressive stop (стоп-лосс) for {position.symbol} {position.side}: "
                f"stop @ +{stop_pnl_pct:.1f}% PNL (price=${stop_price:.4f})"
            )
            
            # СНАЧАЛА ставим новый ордер
            order = self.client.futures_create_order(
                symbol=position.symbol,
                side=order_side,
                type='STOP',
                stopPrice=stop_price,
                price=limit_price,
                quantity=position.size,
                reduceOnly='true',
                timeInForce='GTC'
            )
            
            new_order_id = str(order.get('orderId', ''))
            logger.info(
                f"✅ PROGRESSIVE STOP PLACED (стоп-лосс): {position.symbol} #{new_order_id} | "
                f"Type=STOP @ ${stop_price:.4f} (limit=${limit_price:.4f}) | Target PNL=+{stop_pnl_pct:.1f}%"
            )
            
            # ПОТОМ удаляем старый ордер (если есть и он отличается от нового)
            if old_order_id and old_order_id != new_order_id:
                try:
                    # Проверяем что старый ордер не является emergency stop
                    if hasattr(position, 'emergency_stop_order_id') and position.emergency_stop_order_id == old_order_id:
                        logger.debug(f"⚠️ {position.symbol}: Old order {old_order_id} is emergency stop, skipping cancel")
                    else:
                        self.client.futures_cancel_order(symbol=position.symbol, orderId=old_order_id)
                        logger.info(f"🗑️ Canceled old progressive stop order {old_order_id} for {position.symbol} (replaced with {new_order_id})")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to cancel old progressive stop {old_order_id}: {e}")
            
            return new_order_id
            
        except Exception as e:
            logger.error(f"❌ Failed to place progressive stop for {position.symbol}: {e}")
            return None
    
    def calculate_progressive_stop_level(self, current_pnl_pct: float) -> Optional[float]:
        """
        Calculate trailing stop level based on current PNL.
        
        Трейлинг стоп: только шаг 10% до бесконечности.
        
        Logic:
        - Activates at stepped_stop_activation_pnl% (default 20%) → stop at +10%
        - Шаг всегда 10% до бесконечности:
          - PNL +20% → стоп +10%
          - PNL +30% → стоп +20%
          - PNL +40% → стоп +30%
          - PNL +50% → стоп +40%
          - И так до бесконечности
        
        Args:
            current_pnl_pct: Current unrealized PNL in %
            
        Returns:
            Stop-loss level in % PNL (or None if not activated)
        """
        # Get activation PNL from config (default 20%)
        activation_pnl = self.config.get('risk', {}).get('stepped_stop_activation_pnl', 20.0)
        
        if current_pnl_pct < activation_pnl:
            return None  # Not activated yet (need activation_pnl%)
        
        # Шаг всегда 10% до бесконечности
        # Round down to nearest 10
        trigger_level = (int(current_pnl_pct / 10) * 10)
        stop_level = trigger_level - 10.0
        
        # Safety check: stop level must be at least 10% (minimum)
        if stop_level < 10.0:
            logger.warning(
                f"⚠️ Calculated stop level {stop_level:.2f}% < 10% for PNL={current_pnl_pct:.2f}%. "
                f"Using minimum 10% instead."
            )
            stop_level = 10.0
        
        return stop_level
    
    def place_emergency_stop_order(
        self,
        position,
        skip_if_exists: bool = False
    ) -> Optional[str]:
        """
        Place emergency stop-loss order at price where ROI = -85%.
        This protects against liquidation when position is in loss.
        
        Страховочный стоп: ставится на цену, где ROI достигнет -85%.
        
        Args:
            position: Position object
            skip_if_exists: If True, return existing order ID if valid order already exists (DEPRECATED - check before calling)
            
        Returns:
            Order ID or None if failed
        """
        if not self.config.get('risk', {}).get('emergency_stop_enabled', False):
            logger.debug("Emergency stop disabled in config")
            return None
        
        # Cancel old emergency stop orders FIRST (before placing new one)
        # Cancel ALL emergency stop orders except the assigned one (if it exists and is valid)
        assigned_order_id = str(position.emergency_stop_order_id) if hasattr(position, 'emergency_stop_order_id') and position.emergency_stop_order_id else None
        
        try:
            open_orders = self.client.futures_get_open_orders(symbol=position.symbol, recvWindow=60000)
            order_side = 'SELL' if position.side == 'LONG' else 'BUY'
            for order in open_orders:
                order_type = order.get('type')
                if order_type in ['STOP', 'STOP_MARKET'] and order.get('side') == order_side:
                    order_id = str(order.get('orderId', ''))
                    # Skip if this is the assigned order (don't cancel it - it's already valid)
                    if assigned_order_id and order_id == assigned_order_id:
                        continue  # Keep the assigned order
                    
                    # Cancel this order (it's either not assigned or a duplicate)
                    try:
                        self.client.futures_cancel_order(symbol=position.symbol, orderId=order_id)
                        logger.info(f"🗑️ Canceled old emergency stop order {order_id} for {position.symbol} before placing new one")
                    except Exception as e:
                        logger.debug(f"Failed to cancel old emergency stop {order_id}: {e}")
        except Exception as e:
            logger.debug(f"Error checking old emergency stops: {e}")
        
        # Calculate stop price where ROI = -85%
        # Используем calculate_stop_price_from_pnl с stop_pnl_pct = -85.0
        emergency_roi_level = self.config.get('risk', {}).get('emergency_stop_roi_level', -85.0)
        
        stop_price = self.calculate_stop_price_from_pnl(
            entry_price=position.entry_price,
            side=position.side,
            stop_pnl_pct=emergency_roi_level,  # -85.0%
            leverage=position.leverage
        )
        
        # Round to symbol limits
        limits = self._get_symbol_limits(position.symbol)
        if limits:
            stop_price = self._round_to_tick(stop_price, limits.tick_size)
        
        # Determine order side (LONG sells to close, SHORT buys to close)
        order_side = 'SELL' if position.side == 'LONG' else 'BUY'
        
        try:
            logger.info(
                f"🚨 Placing EMERGENCY stop (страховочный стоп) for {position.symbol} {position.side}: "
                f"stop @ ${stop_price:.4f} (ROI = {emergency_roi_level:.1f}%)"
            )
            
            # Calculate limit price (slightly worse than stop to ensure execution)
            slippage = 0.002  # 0.2% slippage
            if position.side == 'LONG':
                limit_price = stop_price * (1 - slippage)
            else:  # SHORT
                limit_price = stop_price * (1 + slippage)
            
            limit_price = self._round_to_tick(limit_price, limits.tick_size) if limits else limit_price
            
            order = self.client.futures_create_order(
                symbol=position.symbol,
                side=order_side,
                type='STOP',
                stopPrice=stop_price,
                price=limit_price,
                quantity=position.size,
                reduceOnly='true',
                timeInForce='GTC'
            )
            
            order_id = str(order.get('orderId', ''))
            logger.info(
                f"✅ EMERGENCY STOP PLACED (страховочный стоп): {position.symbol} #{order_id} | "
                f"Type=STOP @ ${stop_price:.4f} (limit=${limit_price:.4f}) | ROI = {emergency_roi_level:.1f}%"
            )
            return order_id
            
        except Exception as e:
            logger.error(f"❌ Failed to place emergency stop for {position.symbol}: {e}")
            return None
    
    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        Cancel an open order.
        
        Args:
            symbol: Trading pair
            order_id: Order ID to cancel
            
        Returns:
            True if successful
        """
        try:
            self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            logger.info(f"🗑️ ORDER CANCELLED: {symbol} #{order_id}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Failed to cancel order {order_id}: {e}")
            return False
    
    @staticmethod
    def _round_to_step(value: float, step_size: float) -> float:
        """Round value to step_size precision."""
        if step_size == 0:
            return value
        # Calculate precision from step_size
        step_str = f"{step_size:.10f}".rstrip('0')
        precision = len(step_str.split('.')[-1]) if '.' in step_str else 0
        rounded = round(value / step_size) * step_size
        return round(rounded, precision)
    
    @staticmethod
    def _round_to_tick(price: float, tick_size: float) -> float:
        """Round price to tick_size precision."""
        if tick_size == 0:
            return price
        
        # Handle scientific notation (e.g., 1e-05)
        if 'e' in str(tick_size).lower():
            import math
            # Convert scientific notation to decimal
            tick_size = float(f"{tick_size:.10f}")
        
        # Round to nearest tick_size multiple
        rounded = round(price / tick_size) * tick_size
        
        # Calculate precision from tick_size
        # Handle very small tick sizes (e.g., 0.0001, 1e-05)
        if tick_size < 1:
            # Count decimal places
            tick_str = f"{tick_size:.10f}".rstrip('0').rstrip('.')
            if '.' in tick_str:
                precision = len(tick_str.split('.')[-1])
            else:
                precision = 0
        else:
            precision = 0
        
        # Round to calculated precision and ensure no extra decimals
        result = round(rounded, precision)
        
        # Additional safety: format and parse to remove floating point artifacts
        if precision > 0:
            result = float(f"{result:.{precision}f}")
        
        return result

