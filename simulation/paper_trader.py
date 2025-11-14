#!/usr/bin/env python3
"""
Paper trading module customised for the Super-Scalper rebuild.

Current scope (Stage 1):
  • Track only XRPUSDT
  • Open the very first leg with a limit order placed at the current market price
  • Position size equals the Binance minimum notional ($5 on XRPUSDT) with 50x leverage

Protective logic (SL/TP, martingale averaging, exits) will be layered on top later.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Minimal representation of an open position."""

    id: str
    symbol: str
    side: str  # LONG / SHORT
    entry_price: float
    size: float
    leverage: int
    entry_time: datetime = field(default_factory=datetime.utcnow)
    stop_loss: float = 0.0
    take_profit_1: float = 0.0
    take_profit_2: float = 0.0
    margin_usdt: float = 0.0  # capital locked for the position (notional / leverage)
    position_value_usdt: float = 0.0  # notional exposure without leverage
    order_type: str = "LIMIT"


@dataclass
class ClosedTrade:
    """Minimal representation of a closed trade."""

    id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    leverage: int
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_percent: float
    close_reason: str


class PaperTrader:
    """
    Simplified paper trader. All trading mechanics are intentionally removed.
    """

    def __init__(self, config: Dict, starting_balance: float = 0.0):
        self.config = config
        self.starting_balance = starting_balance
        self.balance = starting_balance
        self.leverage = int(config["account"]["leverage"])
        self.max_positions = int(config["account"]["max_positions"])
        self.positions: Dict[str, Position] = {}
        self.closed_trades: List[ClosedTrade] = []
        self.trade_counter = 0
        self.max_drawdown = 0.0
        self.symbol_rules = config.get("exchange_rules", {})
        self._validate_symbol_rules()
        logger.info("💰 Paper trader initialised (logic removed).")

    # ------------------------------------------------------------------ #
    # Interfaces expected by surrounding code
    # ------------------------------------------------------------------ #

    def can_open_new_leg(self, *args, **kwargs) -> bool:
        """
        Stage 1: allow only one open leg per symbol+side and respect global cap.
        """
        symbol = kwargs.get("symbol")
        side = kwargs.get("side")

        if symbol and side:
            key = self._make_key(symbol, side)
            if key in self.positions:
                logger.debug("🚫 Leg already open for %s", key)
                return False

        if len(self.positions) >= self.max_positions:
            logger.debug("🚫 Max positions reached (%d)", self.max_positions)
            return False

        return True

    def open_position(
        self,
        signal: "TradingSignal",
        orderbook: Dict,
        adaptive_params: Optional[Dict] = None,
    ) -> Optional[Position]:
        """
        Stage 1 entry mechanic:
          • place a limit order at the current market price (best bid/ask)
          • size equals minimum Binance futures notional for XRPUSDT
          • leverage fixed at 50x (taken from config)
        """
        if signal.direction not in {"LONG", "SHORT"}:
            logger.debug("No entry for %s (direction=%s)", signal.symbol, signal.direction)
            return None

        symbol = signal.symbol
        side = signal.direction
        key = self._make_key(symbol, side)

        if key in self.positions:
            logger.debug("🚫 Position already open for %s", key)
            return None

        if not self.can_open_new_leg(symbol=symbol, side=side):
            return None

        rules = self.symbol_rules.get(symbol)
        if not rules:
            logger.error("❌ No exchange rules configured for %s", symbol)
            return None

        entry_price = self._pick_entry_price(side, orderbook, signal)
        if entry_price <= 0:
            logger.warning("⚠️ No valid price to enter %s", symbol)
            return None

        quantity = self._calculate_min_quantity(entry_price, rules)
        if quantity <= 0:
            logger.warning("⚠️ Could not compute valid quantity for %s", symbol)
            return None

        position_value = entry_price * quantity
        margin_required = position_value / self.leverage
        if margin_required > self.balance:
            logger.warning(
                "⚠️ Insufficient balance %.2f for margin %.2f on %s", self.balance, margin_required, symbol
            )
            return None

        self.trade_counter += 1
        position_id = f"{symbol}-{self.trade_counter}"

        position = Position(
            id=position_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            size=quantity,
            leverage=self.leverage,
            stop_loss=signal.stop_loss or entry_price,
            take_profit_1=signal.take_profit_1 or entry_price,
            take_profit_2=signal.take_profit_2 or signal.take_profit_1 or entry_price,
            margin_usdt=margin_required,
            position_value_usdt=position_value,
        )

        self.positions[key] = position
        self.balance -= margin_required

        logger.info(
            "🟢 OPEN %s %s @ %.4f | qty %.2f | notional $%.2f | margin $%.2f",
            side,
            symbol,
            entry_price,
            quantity,
            position_value,
            margin_required,
        )

        return position

    def update_positions(self, *args, **kwargs) -> Optional[ClosedTrade]:
        """Нет активного управления позицией."""
        return None

    def close_position_manually(self, position_key: str, exit_price: float, reason: str) -> Optional[ClosedTrade]:
        position = self.positions.pop(position_key, None)
        if not position:
            return None

        pnl = (exit_price - position.entry_price) * position.size if position.side == "LONG" else (position.entry_price - exit_price) * position.size
        pnl_percent = (pnl / (position.entry_price * position.size)) * 100 if position.size else 0.0

        closed = ClosedTrade(
            id=position.id,
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            size=position.size,
            leverage=position.leverage,
            entry_time=position.entry_time,
            exit_time=datetime.utcnow(),
            pnl=pnl,
            pnl_percent=pnl_percent,
            close_reason=reason,
        )
        self.closed_trades.append(closed)
        self.balance += position.margin_usdt + pnl
        return closed

    def close_all_positions(self, current_prices: Dict[str, float]):
        """Close every position using supplied mark prices."""
        for key, position in list(self.positions.items()):
            symbol = position.symbol
            current_price = current_prices.get(key) or current_prices.get(symbol, position.entry_price)
            self.close_position_manually(key, current_price, "Emergency close")

    # ------------------------------------------------------------------ #
    # Reporting helpers
    # ------------------------------------------------------------------ #

    def get_statistics(self) -> Dict[str, float]:
        winners = sum(1 for trade in self.closed_trades if trade.pnl > 0)
        losers = sum(1 for trade in self.closed_trades if trade.pnl < 0)
        total = winners + losers
        win_rate = (winners / total * 100) if total else 0.0
        avg_win = (sum(trade.pnl for trade in self.closed_trades if trade.pnl > 0) / winners) if winners else 0.0
        avg_loss = (sum(trade.pnl for trade in self.closed_trades if trade.pnl < 0) / losers) if losers else 0.0
        best_trade = max((trade.pnl for trade in self.closed_trades), default=0.0)
        worst_trade = min((trade.pnl for trade in self.closed_trades), default=0.0)

        return {
            "total_trades": total,
            "winners": winners,
            "losers": losers,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": abs(avg_win / avg_loss) if avg_loss else 0.0,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "avg_duration": 0.0,
        }

    def get_open_orders(self) -> List[Dict]:
        """Paper trader does not maintain a separate order book."""
        return []

    def save_session(self, path: str):
        snapshot = {
            "generated_at": datetime.utcnow().isoformat(),
            "balance": self.balance,
            "starting_balance": self.starting_balance,
            "open_positions": [asdict(pos) for pos in self.positions.values()],
            "closed_trades": [asdict(trade) for trade in self.closed_trades],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _make_key(symbol: str, side: str) -> str:
        return f"{symbol}|{side.upper()}"

    def _validate_symbol_rules(self):
        if not self.symbol_rules:
            logger.warning("⚠️ No exchange rules supplied. Entry sizing will fail.")

    @staticmethod
    def _pick_entry_price(side: str, orderbook: Dict, signal) -> float:
        bids = orderbook.get("bids", []) if orderbook else []
        asks = orderbook.get("asks", []) if orderbook else []

        if side == "LONG":
            if asks:
                return float(asks[0][0])
        else:
            if bids:
                return float(bids[0][0])

        # Fallback to signal entry price if available
        return getattr(signal, "entry_price", 0.0) or 0.0

    @staticmethod
    def _calculate_min_quantity(price: float, rules: Dict[str, float]) -> float:
        min_qty = float(rules.get("min_qty", 0.0))
        step = float(rules.get("step_size", 0.0))
        min_notional = float(rules.get("min_notional", 0.0))

        if price <= 0 or min_qty <= 0 or step <= 0:
            return 0.0

        qty = max(min_qty, min_notional / price if min_notional else min_qty)
        # align to step size upwards to satisfy notional
        steps = math.ceil(qty / step)
        return round(steps * step, 8)


