#!/usr/bin/env python3
"""
Live trader adapter that mirrors the real Binance Futures account state.
It does NOT submit orders yet – only provides read-only data for the GUI.
"""

from __future__ import annotations

import logging
from datetime import datetime
from time import time
from typing import Dict, List

from binance.client import Client

from simulation.paper_trader import PaperTrader, Position

logger = logging.getLogger(__name__)


class LiveTrader(PaperTrader):
    """
    Read-only live trader that syncs balances, positions and open orders from Binance Futures.
    """

    def __init__(
        self,
        config: Dict,
        api_key: str,
        api_secret: str,
        starting_balance: float = 0.0,
        refresh_interval: float = 1.5,
    ):
        super().__init__(config, starting_balance)
        self.client = Client(api_key, api_secret)
        self.refresh_interval = max(0.5, float(refresh_interval))
        self._last_refresh_ts: float = 0.0

        # Snapshots used by the GUI
        self.account_overview: Dict[str, float] = {
            "walletBalance": starting_balance,
            "availableBalance": starting_balance,
            "marginBalance": starting_balance,
            "unrealizedProfit": 0.0,
            "initialMargin": 0.0,
            "maintMargin": 0.0,
        }
        self.open_orders: List[Dict] = []

        logger.info("🔌 Live trader initialised (read-only).")

    # ------------------------------------------------------------------ #
    # Binance data sync
    # ------------------------------------------------------------------ #

    def refresh_from_exchange(self, force: bool = False) -> Dict[str, float]:
        """Fetch latest futures account snapshot and open orders."""
        now = time()
        if not force and (now - self._last_refresh_ts) < self.refresh_interval:
            return self.account_overview

        try:
            account = self.client.futures_account()
            self._update_account_overview(account)
            self._update_positions(account.get("positions", []))
            self.open_orders = self._simplify_orders(self.client.futures_get_open_orders())
            self._last_refresh_ts = now
        except Exception as exc:
            logger.error("❌ Live account refresh failed: %s", exc, exc_info=True)

        return self.account_overview

    def _update_account_overview(self, account_payload: Dict) -> None:
        """Store balances extracted from the futures account payload."""
        snapshot = {
            "walletBalance": float(account_payload.get("totalWalletBalance", self.balance)),
            "availableBalance": float(account_payload.get("availableBalance", 0.0)),
            "marginBalance": float(account_payload.get("totalMarginBalance", 0.0)),
            "unrealizedProfit": float(account_payload.get("totalUnrealizedProfit", 0.0)),
            "initialMargin": float(account_payload.get("totalInitialMargin", 0.0)),
            "maintMargin": float(account_payload.get("totalMaintMargin", 0.0)),
        }
        self.account_overview = snapshot
        self.balance = snapshot["walletBalance"]

    def _update_positions(self, raw_positions: List[Dict]) -> None:
        """Convert Binance position payloads into Position objects for the GUI."""
        positions: Dict[str, Position] = {}
        for payload in raw_positions:
            try:
                qty = float(payload.get("positionAmt", 0.0))
                if qty == 0.0:
                    continue

                symbol = payload.get("symbol")
                side = "LONG" if qty > 0 else "SHORT"
                entry_price = float(payload.get("entryPrice", 0.0))
                leverage = int(float(payload.get("leverage", self.leverage)) or self.leverage)
                isolated_margin = float(payload.get("isolatedMargin", 0.0))
                mark_price = float(payload.get("markPrice", entry_price))
                notional = abs(qty) * entry_price
                margin_used = isolated_margin if isolated_margin > 0 else (notional / leverage if leverage else 0.0)

                # Re-use Position dataclass for GUI compatibility
                position = Position(
                    id=f"live-{symbol}-{side}",
                    symbol=symbol,
                    side=side,
                    entry_price=entry_price,
                    size=abs(qty),
                    leverage=leverage,
                    stop_loss=0.0,
                    take_profit_1=0.0,
                    take_profit_2=0.0,
                    margin_usdt=margin_used,
                    position_value_usdt=notional,
                    order_type="MARKET",
                    entry_time=datetime.utcnow(),
                )

                # Store mark price so GUI can compute PNL
                setattr(position, "mark_price", mark_price)

                positions[f"{symbol}|{side}"] = position
            except Exception as exc:
                logger.debug("Failed to parse live position payload %s: %s", payload, exc)

        self.positions = positions

    @staticmethod
    def _simplify_orders(raw_orders: List[Dict]) -> List[Dict]:
        """Reduce Binance order payloads to the fields required by the GUI."""
        simplified: List[Dict] = []
        for order in raw_orders or []:
            try:
                simplified.append(
                    {
                        "symbol": order.get("symbol"),
                        "side": order.get("side"),
                        "type": order.get("type"),
                        "price": float(order.get("price", 0.0)),
                        "origQty": float(order.get("origQty", 0.0)),
                        "executedQty": float(order.get("executedQty", 0.0)),
                        "status": order.get("status"),
                        "reduceOnly": order.get("reduceOnly", False),
                        "time": datetime.fromtimestamp(order.get("time", 0) / 1000) if order.get("time") else None,
                    }
                )
            except Exception as exc:
                logger.debug("Failed to parse live order payload %s: %s", order, exc)
        return simplified

    # ------------------------------------------------------------------ #
    # Interfaces expected by the GUI
    # ------------------------------------------------------------------ #

    def get_account_overview(self) -> Dict[str, float]:
        return self.account_overview

    def get_open_orders(self) -> List[Dict]:
        return self.open_orders

    # ------------------------------------------------------------------ #
    # Trading operations are intentionally disabled for now
    # ------------------------------------------------------------------ #

    def open_position(self, *args, **kwargs):
        logger.warning("LiveTrader.open_position() called – live order routing not implemented.")
        return None

    def close_position_manually(self, *args, **kwargs):
        logger.warning("LiveTrader.close_position_manually() called – manual close is not implemented in live mode.")
        return None

    def close_all_positions(self, *args, **kwargs):
        logger.warning("LiveTrader.close_all_positions() called – bulk close is not implemented in live mode.")
        return None

