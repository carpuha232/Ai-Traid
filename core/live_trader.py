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


logger = logging.getLogger(__name__)


class LiveTrader:
    """Execute trades on Binance Futures (UM)."""

    def __init__(self, config: Dict, api_key: str, api_secret: str):
        self.config = config
        self.client = Client(api_key, api_secret)

        account_info = self.client.futures_account()
        self.starting_balance = self._extract_wallet_balance(account_info)
        self.balance = self.starting_balance
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.min_balance = self.starting_balance
        self.max_balance = self.starting_balance

        self.positions: Dict[str, Position] = {}
        self.closed_trades: list[ClosedTrade] = []
        self.trade_counter = 0

        logger.info("💹 LiveTrader initialised. Balance: $%.2f", self.balance)

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

    def _ensure_leverage(self, symbol: str, leverage: int):
        try:
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
        except Exception as exc:
            logger.warning("⚠️ Failed to adjust leverage %s: %s", symbol, exc)

    # ------------------------------------------------------------------
    # Public interface compatible with PaperTrader
    # ------------------------------------------------------------------
    def get_available_balance(self) -> float:
        info = self.client.futures_account_balance()
        for asset in info:
            if asset.get('asset') == 'USDT':
                return float(asset.get('withdrawAvailable', 0.0))
        return 0.0

    def open_position(self, signal, orderbook, adaptive_params=None) -> Optional[Position]:
        symbol = signal.symbol
        direction = signal.direction
        if symbol in self.positions:
            return None

        risk_percent = self.config['risk']['base_risk_percent'] * (adaptive_params.get('position_size_multiplier', 1.0) if adaptive_params else 1.0)
        account_balance = self.get_available_balance()
        risk_amount = account_balance * (risk_percent / 100)

        entry_price = signal.entry_price
        stop_price = signal.stop_loss
        stop_distance = abs(entry_price - stop_price) / entry_price
        if stop_distance <= 0:
            return None

        notional = risk_amount / stop_distance
        leverage = self.config['account']['leverage']
        if adaptive_params:
            leverage = max(int(leverage * adaptive_params.get('leverage_multiplier', 1.0)), 1)

        self._ensure_leverage(symbol, leverage)

        quantity = round(notional / entry_price, 4)
        if quantity <= 0:
            return None

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
            liquidation_price=0.0,
            position_value_usdt=position_value,
            margin_usdt=margin,
            current_price=avg_price
        )

        self.positions[symbol] = position

        # Configure stop/take in reduceOnly mode
        try:
            opposite = 'SELL' if direction == 'LONG' else 'BUY'
            stop_type = 'STOP_MARKET'
            tp_type = 'TAKE_PROFIT_MARKET'

            self.client.futures_create_order(
                symbol=symbol,
                side=opposite,
                type=stop_type,
                stopPrice=signal.stop_loss,
                quantity=quantity,
                reduceOnly='true',
                timeInForce='GTC'
            )

            self.client.futures_create_order(
                symbol=symbol,
                side=opposite,
                type=tp_type,
                stopPrice=signal.take_profit_1,
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

        pnl_percent = (realized_pnl / position.margin_usdt * 100) if position.margin_usdt else 0.0

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
            total_commission=0.0,
            confidence=position.confidence
        )

        self.closed_trades.append(closed_trade)
        self.total_pnl += realized_pnl

        del self.positions[position.symbol]

        pnl_sign = '+' if realized_pnl >= 0 else ''
        logger.info("%s Closed live position %s %s: %s$%.2f", '✅' if realized_pnl >= 0 else '❌', position.symbol, position.side, pnl_sign, realized_pnl)

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

