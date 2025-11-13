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
        limits = self.symbol_limits.get(symbol)
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
        distance_pct: float = 10.0
    ) -> float:
        """
        Calculate price for averaging down order.
        Order is placed X% away from liquidation price.
        
        Args:
            entry_price: Original entry price
            liquidation_price: Calculated liquidation price
            side: 'LONG' or 'SHORT'
            distance_pct: Distance from liquidation in % (default 10%)
            
        Returns:
            Price for averaging order
        """
        if side == 'LONG':
            # For LONG: liq price is below entry
            # Order should be between entry and liq, closer to liq
            price_diff = entry_price - liquidation_price
            offset = price_diff * (distance_pct / 100.0)
            order_price = liquidation_price + offset
        else:  # SHORT
            # For SHORT: liq price is above entry
            # Order should be between entry and liq, closer to liq
            price_diff = liquidation_price - entry_price
            offset = price_diff * (distance_pct / 100.0)
            order_price = liquidation_price - offset
        
        logger.debug(
            f"📍 Averaging order for {side}: entry=${entry_price:.2f}, "
            f"liq=${liquidation_price:.2f}, order=${order_price:.2f} "
            f"({distance_pct}% from liq)"
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
    
    def place_averaging_order(
        self,
        position,
        liquidation_price: float
    ) -> Optional[str]:
        """
        Place a limit order for averaging down near liquidation.
        Order size equals initial position margin.
        
        Args:
            position: Position object
            liquidation_price: Calculated liquidation price
            
        Returns:
            Order ID or None if failed
        """
        if not self.config.get('risk', {}).get('averaging_down_enabled', False):
            logger.debug("Averaging down disabled in config")
            return None
        
        distance_pct = self.config.get('risk', {}).get('averaging_trigger_distance_from_liq', 10.0)
        
        # Calculate order price (10% from liquidation towards entry)
        order_price = self.calculate_averaging_order_price(
            entry_price=position.entry_price,
            liquidation_price=liquidation_price,
            side=position.side,
            distance_pct=distance_pct
        )
        
        # Calculate quantity for same margin as initial position
        # For same margin: use same quantity as initial position
        # This ensures: (quantity * order_price) / leverage = initial_margin
        quantity = position.size
        
        # Round to symbol limits
        limits = self.symbol_limits.get(position.symbol)
        if limits:
            raw_price = order_price
            raw_qty = quantity
            quantity = self._round_to_step(quantity, limits.step_size)
            order_price = self._round_to_tick(order_price, limits.tick_size)
            logger.debug(
                f"🔢 {position.symbol}: Rounded qty {raw_qty:.6f}→{quantity:.6f}, "
                f"price {raw_price:.6f}→{order_price:.6f}"
            )
        
        # Determine order side (LONG buys more, SHORT sells more)
        order_side = 'BUY' if position.side == 'LONG' else 'SELL'
        
        try:
            logger.info(
                f"🎯 Placing averaging order for {position.symbol} {position.side}: "
                f"price=${order_price}, qty={quantity}, margin=${position.initial_margin:.2f}"
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
                f"✅ ORDER PLACED: {position.symbol} AVERAGING #{order_id} | "
                f"Type=LIMIT {order_side} @ ${order_price:.4f} | Qty={quantity}"
            )
            return order_id
            
        except Exception as e:
            logger.error(f"❌ Failed to place averaging order for {position.symbol}: {e}")
            return None
    
    def place_stepped_stop_order(
        self,
        position,
        stop_pnl_pct: float
    ) -> Optional[str]:
        """
        Place a limit stop-loss order at specified PNL level.
        
        Args:
            position: Position object
            stop_pnl_pct: Stop level in PNL % (e.g., 10.0 for +10%)
            
        Returns:
            Order ID or None if failed
        """
        if not self.config.get('risk', {}).get('stepped_stop_enabled', False):
            logger.debug("Stepped stop disabled in config")
            return None
        
        # Calculate stop price from PNL percentage
        stop_price = self.calculate_stop_price_from_pnl(
            entry_price=position.entry_price,
            side=position.side,
            stop_pnl_pct=stop_pnl_pct,
            leverage=position.leverage
        )
        
        # Round to symbol limits
        limits = self.symbol_limits.get(position.symbol)
        if limits:
            stop_price = self._round_to_tick(stop_price, limits.tick_size)
        
        # Determine order side (LONG sells to close, SHORT buys to close)
        order_side = 'SELL' if position.side == 'LONG' else 'BUY'
        
        try:
            logger.info(
                f"🛡️ Placing stepped stop for {position.symbol} {position.side}: "
                f"stop @ +{stop_pnl_pct:.1f}% PNL (price=${stop_price:.4f})"
            )
            
            # Cancel existing stepped stop if any
            if position.stepped_stop_order_id:
                self.cancel_order(position.symbol, position.stepped_stop_order_id)
            
            # Calculate limit price (slightly worse than stop to ensure execution)
            # For LONG (SELL stop): limit price slightly lower
            # For SHORT (BUY stop): limit price slightly higher
            slippage = 0.002  # 0.2% slippage
            if position.side == 'LONG':
                limit_price = stop_price * (1 - slippage)
            else:  # SHORT
                limit_price = stop_price * (1 + slippage)
            
            limit_price = self._round_to_tick(limit_price, position.symbol)
            
            order = self.client.futures_create_order(
                symbol=position.symbol,
                side=order_side,
                type='STOP',  # Stop limit order (triggers at stopPrice, executes as limit at price)
                stopPrice=stop_price,
                price=limit_price,
                quantity=position.size,
                reduceOnly='true',  # This closes the position
                timeInForce='GTC'
            )
            
            order_id = str(order.get('orderId', ''))
            logger.info(
                f"✅ ORDER PLACED: {position.symbol} STOP-LOSS #{order_id} | "
                f"Type=STOP @ ${stop_price:.4f} (limit=${limit_price:.4f}) | Target PNL=+{stop_pnl_pct:.1f}%"
            )
            return order_id
            
        except Exception as e:
            logger.error(f"❌ Failed to place stepped stop for {position.symbol}: {e}")
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
        # Calculate precision from tick_size
        tick_str = f"{tick_size:.10f}".rstrip('0')
        precision = len(tick_str.split('.')[-1]) if '.' in tick_str else 0
        rounded = round(price / tick_size) * tick_size
        return round(rounded, precision)

