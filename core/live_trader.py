#!/usr/bin/env python3
"""
Live trader adapter that mirrors the real Binance Futures account state.
It does NOT submit orders yet – only provides read-only data for the GUI.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from time import time
from typing import Any, Dict, List, Optional

import websockets
from binance.client import Client
from binance.exceptions import BinanceAPIException  # type: ignore

from simulation.paper_trader import PaperTrader, Position, ClosedTrade

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
        refresh_interval: float = 3.0,
    ):
        super().__init__(config, starting_balance)
        self.client = Client(api_key, api_secret)
        self.refresh_interval = max(0.5, float(refresh_interval))
        self._last_refresh_ts: float = 0.0
        self._last_time_sync_ts: float = 0.0
        self._leverage_cache: Dict[str, int] = {}
        self._open_orders_map: Dict[int, Dict] = {}
        self._user_stream_task: Optional[asyncio.Task] = None
        self._user_keepalive_task: Optional[asyncio.Task] = None
        self._user_stream_running: bool = False
        self._user_stream_listen_key: Optional[str] = None
        self._stream_refresh_lock: Optional[asyncio.Lock] = None
        self._last_stream_refresh_ts: float = 0.0
        self.stream_refresh_min_interval: float = 2.0
        self.grid_orders_tracker: Dict[str, Dict[str, Any]] = {}
        self.take_profit_orders: Dict[str, int] = {}

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
        self._last_position_info: Dict[str, Dict[str, Any]] = {}

        logger.info("🔌 Live trader initialised (read-only).")
        try:
            self.refresh_from_exchange(force=True)
        except Exception:
            logger.debug("LiveTrader initial refresh failed", exc_info=True)

    # ------------------------------------------------------------------ #
    # Binance data sync
    # ------------------------------------------------------------------ #

    def refresh_from_exchange(self, force: bool = False) -> Dict[str, float]:
        """Fetch latest futures account snapshot and open orders."""
        now = time()
        if not force and (now - self._last_refresh_ts) < self.refresh_interval:
            return self.account_overview

        try:
            self._sync_server_time()
            account = self.client.futures_account()
            self._update_account_overview(account)
            self._update_positions(account.get("positions", []))
            orders = self._simplify_orders(self.client.futures_get_open_orders())
            self.open_orders = orders
            self._open_orders_map = {
                int(order.get("orderId", 0)): order
                for order in orders
                if order.get("orderId")
            }
            self._last_refresh_ts = now
            self._cache_position_info()
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
                break_even = float(payload.get("breakEvenPrice", entry_price))
                liquidation_price = float(payload.get("liquidationPrice", 0.0))
                margin_ratio = float(payload.get("marginRatio", 0.0))
                margin_type = payload.get("marginType", "cross").upper()
                unrealized = float(payload.get("unRealizedProfit" if "unRealizedProfit" in payload else "unrealizedProfit", 0.0))
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

                if liquidation_price <= 0 and entry_price > 0 and leverage > 0:
                    if side == "LONG":
                        liquidation_price = entry_price * (1 - (0.99 / leverage))
                    else:
                        liquidation_price = entry_price * (1 + (0.99 / leverage))

                # Store extra metadata for GUI
                setattr(position, "mark_price", mark_price)
                setattr(position, "break_even_price", break_even if break_even > 0 else entry_price)
                setattr(position, "liquidation_price", liquidation_price)
                setattr(position, "margin_ratio", margin_ratio)
                setattr(position, "margin_type", margin_type)
                setattr(position, "unrealized_pnl", unrealized)

                positions[f"{symbol}|{side}"] = position
            except Exception as exc:
                logger.debug("Failed to parse live position payload %s: %s", payload, exc)

        self.positions = positions
        active_symbols = {sym.split("|")[0] for sym in positions.keys()}
        for symbol in list(self._last_position_info.keys()):
            if symbol not in active_symbols:
                self._last_position_info.pop(symbol, None)

    @staticmethod
    def _simplify_orders(raw_orders: List[Dict]) -> List[Dict]:
        """Reduce Binance order payloads to the fields required by the GUI."""
        simplified: List[Dict] = []
        for order in raw_orders or []:
            try:
                order_id = int(order.get("orderId", 0) or 0)
                simplified.append(
                    {
                        "orderId": order_id,
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

    def get_cached_position_info(self, symbol: str) -> Dict[str, Any]:
        return self._last_position_info.get(symbol, {})

    # ------------------------------------------------------------------ #
    # User data stream (websocket) for realtime updates
    # ------------------------------------------------------------------ #

    async def start_user_stream(self):
        if self._user_stream_task:
            return
        self._stream_refresh_lock = asyncio.Lock()
        await self._ensure_listen_key()
        self._user_stream_running = True
        loop = asyncio.get_running_loop()
        self._user_stream_task = loop.create_task(self._user_stream_runner())
        self._user_keepalive_task = loop.create_task(self._user_stream_keepalive())
        logger.info("LiveTrader: user data stream started")

    async def stop_user_stream(self):
        self._user_stream_running = False
        tasks = [t for t in (self._user_stream_task, self._user_keepalive_task) if t]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._user_stream_task = None
        self._user_keepalive_task = None

    async def _ensure_listen_key(self):
        try:
            self._user_stream_listen_key = await asyncio.to_thread(
                self.client.futures_stream_get_listen_key
            )
            logger.info("LiveTrader: obtained listenKey")
        except Exception as exc:
            logger.error("LiveTrader: listenKey request failed: %s", exc)
            raise

    async def _user_stream_keepalive(self):
        try:
            while self._user_stream_running:
                await asyncio.sleep(30 * 60)
                if not self._user_stream_listen_key:
                    await self._ensure_listen_key()
                try:
                    await asyncio.to_thread(
                        self.client.futures_stream_keepalive,
                        self._user_stream_listen_key,
                    )
                except Exception as exc:
                    logger.warning("LiveTrader: listenKey keepalive failed: %s", exc)
        except asyncio.CancelledError:
            pass

    async def _user_stream_runner(self):
        url_base = "wss://fstream.binance.com/ws"
        try:
            while self._user_stream_running:
                try:
                    if not self._user_stream_listen_key:
                        await self._ensure_listen_key()
                    url = f"{url_base}/{self._user_stream_listen_key}"
                    async with websockets.connect(
                        url, ping_interval=10, ping_timeout=20
                    ) as ws:
                        logger.info("LiveTrader: user stream connected")
                        while self._user_stream_running:
                            raw = await ws.recv()
                            try:
                                data = json.loads(raw)
                            except json.JSONDecodeError:
                                logger.debug("LiveTrader: invalid stream payload %s", raw)
                                continue
                            await self._process_user_stream_event(data)
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    if self._user_stream_running:
                        logger.error("LiveTrader user stream error: %s", exc)
                        await asyncio.sleep(2)
        finally:
            logger.info("LiveTrader: user stream stopped")

    async def _process_user_stream_event(self, payload: Dict[str, Any]):
        event = payload.get("e")
        if event == "ACCOUNT_UPDATE":
            await self._handle_account_update(payload.get("a", {}))
        elif event == "ORDER_TRADE_UPDATE":
            self._handle_order_trade_update(payload.get("o", {}))

    async def _handle_account_update(self, account_payload: Dict[str, Any]):
        for balance in account_payload.get("B", []):
            if balance.get("a") == "USDT":
                self.account_overview["walletBalance"] = float(
                    balance.get("wb", self.balance)
                )
                self.account_overview["availableBalance"] = float(
                    balance.get("cw", self.account_overview.get("availableBalance", 0.0))
                )
                self.balance = self.account_overview["walletBalance"]
        await self._refresh_from_stream_snapshot()

    def _handle_order_trade_update(self, order_payload: Dict[str, Any]):
        if not order_payload:
            return
        order_id = int(order_payload.get("i", 0))
        if not order_id:
            return
        simplified = {
            "orderId": order_id,
            "symbol": order_payload.get("s"),
            "side": order_payload.get("S"),
            "type": order_payload.get("o"),
            "price": float(order_payload.get("p", 0.0)),
            "origQty": float(order_payload.get("q", 0.0) or 0.0),
            "executedQty": float(order_payload.get("z", 0.0) or 0.0),
            "status": order_payload.get("X"),
            "avgPrice": float(order_payload.get("ap", 0.0) or 0.0),
        }
        status = simplified["status"]
        if status in {"NEW", "PARTIALLY_FILLED"}:
            self._open_orders_map[order_id] = simplified
        else:
            self._open_orders_map.pop(order_id, None)
        self.open_orders = list(self._open_orders_map.values())

        if status == "FILLED":
            symbol = simplified.get("symbol")
            if self.take_profit_orders.get(symbol) == order_id:
                self.take_profit_orders.pop(symbol, None)
                return
            tracker = self.grid_orders_tracker.get(symbol)
            if tracker and tracker.get("pending_order_id") == order_id:
                tracker["level_index"] += 1
                tracker["pending_order_id"] = None
                loop = asyncio.get_running_loop()
                loop.create_task(self._spawn_next_averaging(symbol, tracker))

    async def _refresh_from_stream_snapshot(self):
        now = time()
        if now - self._last_stream_refresh_ts < self.stream_refresh_min_interval:
            return
        self._last_stream_refresh_ts = now
        if not self._stream_refresh_lock:
            self._stream_refresh_lock = asyncio.Lock()
        if self._stream_refresh_lock.locked():
            return
        async with self._stream_refresh_lock:
            await asyncio.to_thread(self.refresh_from_exchange, True)

    # ------------------------------------------------------------------ #
    # Trading operations are intentionally disabled for now
    # ------------------------------------------------------------------ #

    def open_position(self, signal, orderbook, adaptive_params=None):
        """Отправить реальный MARKET-ордер минимальным объёмом."""
        if signal.direction not in {"LONG", "SHORT"}:
            logger.debug("LiveTrader: no entry for %s (direction=%s)", signal.symbol, signal.direction)
            return None

        symbol = signal.symbol
        side = signal.direction
        key = self._make_key(symbol, side)

        self.refresh_from_exchange(force=True)
        if not self.can_open_new_leg(symbol=symbol, side=side):
            logger.debug("LiveTrader: %s already open", key)
            return None

        rules = self.symbol_rules.get(symbol)
        if not rules:
            logger.error("❌ LiveTrader: no exchange rules for %s", symbol)
            return None

        entry_price = self._pick_entry_price(side, orderbook, signal)
        if entry_price <= 0:
            logger.warning("⚠️ LiveTrader: no entry price for %s", symbol)
            return None

        quantity = self._calculate_min_quantity(entry_price, rules)
        if quantity <= 0:
            logger.warning("⚠️ LiveTrader: could not compute quantity for %s", symbol)
            return None

        try:
            self._sync_server_time()
            self._ensure_symbol_leverage(symbol)
            order = self.client.futures_create_order(
                symbol=symbol,
                side="BUY" if side == "LONG" else "SELL",
                type="MARKET",
                quantity=quantity,
                reduceOnly=False,
                recvWindow=10000,
                newOrderRespType="RESULT",
            )
        except BinanceAPIException as exc:
            logger.error("❌ LiveTrader: failed to open %s %s – %s", side, symbol, exc)
            return None
        except Exception as exc:
            logger.error("❌ LiveTrader: unexpected error on %s %s: %s", side, symbol, exc, exc_info=True)
            return None

        avg_price = float(order.get("avgPrice") or order.get("price") or entry_price)
        filled_qty = float(order.get("executedQty") or order.get("origQty") or quantity)

        logger.info(
            "🟢 LIVE OPEN %s %s | qty %.4f | avg %.5f | orderId %s",
            side,
            symbol,
            filled_qty,
            avg_price,
            order.get("orderId"),
        )

        self.refresh_from_exchange(force=True)
        position = self.positions.get(key)

        if not position:
            position_value = avg_price * filled_qty
            margin_used = position_value / self.leverage if self.leverage else 0.0
            position = Position(
                id=str(order.get("orderId", f"live-{symbol}")),
                symbol=symbol,
                side=side,
                entry_price=avg_price,
                size=filled_qty,
                leverage=self.leverage,
                margin_usdt=margin_used,
                position_value_usdt=position_value,
                order_type="MARKET",
                entry_time=datetime.utcnow(),
                averaging_orders=[],
            )
            self.positions[key] = position

        return position

    def open_min_long_with_averaging(
        self,
        symbol: str,
        buffer_ratio: float = 0.001,
    ) -> Dict[str, Any]:
        """
        Открывает LONG минимальным объёмом и ставит усреднение перед ликвидацией.

        Returns:
            Dict с информацией о позиции, цене ликвидации и ордере усреднения.
        """
        key = self._make_key(symbol, "LONG")
        if key in self.positions:
            raise RuntimeError(f"Position already open for {symbol}")

        rules = self.symbol_rules.get(symbol)
        if not rules:
            raise ValueError(f"No exchange rules configured for {symbol}")

        mark_payload = self.client.futures_mark_price(symbol=symbol)
        entry_price = float(mark_payload.get("markPrice", 0.0)) if mark_payload else 0.0

        quantity = self._calculate_min_quantity(entry_price, rules)
        if quantity <= 0:
            raise ValueError(f"Could not compute quantity for {symbol}")

        self._sync_server_time()
        self._ensure_symbol_leverage(symbol)

        try:
            market_order = self.client.futures_create_order(
                symbol=symbol,
                side="BUY",
                type="MARKET",
                quantity=quantity,
                reduceOnly=False,
                recvWindow=10000,
                newOrderRespType="RESULT",
            )
            avg_price = float(market_order.get("avgPrice") or market_order.get("price") or entry_price)
            logger.info(
                "LiveTrader: MARKET BUY %s qty %.4f avg %.6f (mark %.6f)",
                symbol,
                quantity,
                avg_price,
                entry_price,
            )
        except BinanceAPIException as exc:
            logger.error("LiveTrader: market entry failed for %s: %s", symbol, exc)
            raise

        self.refresh_from_exchange(force=True)

        position_info = self._last_position_info.get(symbol) or self._fetch_position_info(symbol)
        liq_price = float(position_info.get("liquidationPrice", 0.0)) if position_info else 0.0
        entry_price = float(position_info.get("entryPrice", entry_price)) if position_info else entry_price
        leverage = float(position_info.get("leverage", self.leverage)) if position_info else self.leverage

        if liq_price <= 0 and entry_price > 0 and leverage > 0:
            liq_price = entry_price * (1 - (0.99 / leverage))

        rules_tick = float(rules.get("tick_size", 0.0001) or 0.0001)
        tracker = {
            "base_qty": quantity,
            "level_index": 1,
            "pending_order_id": None,
        }
        self.grid_orders_tracker[symbol] = tracker
        pending_order = self._place_next_averaging_order(symbol, tracker, buffer_ratio)
        if pending_order is None:
            self.grid_orders_tracker.pop(symbol, None)
        take_order = self._place_take_profit_order(symbol)

        self.refresh_from_exchange(force=True)
        key = self._make_key(symbol, "LONG")
        position = self.positions.get(key)
        if position:
            position.averaging_orders = [pending_order] if pending_order else []
            setattr(position, "take_profit_order", take_order)

        return {
            "market_order": market_order,
            "grid_orders": position.averaging_orders if position else [],
            "entry_price": position.entry_price if position else avg_price,
            "liquidation_price": getattr(position, "liquidation_price", liq_price),
            "base_quantity": position.size if position else quantity,
            "symbol": symbol,
        }

    def close_position_manually(self, position_key: str, exit_price: float, reason: str) -> Optional[ClosedTrade]:
        position = self.positions.get(position_key)
        if not position:
            logger.warning("LiveTrader: position %s not found for manual close", position_key)
        return None

        symbol = position.symbol
        qty = round(position.size, 8)
        side = "SELL" if position.side == "LONG" else "BUY"

        try:
            self._sync_server_time()
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=qty,
                reduceOnly=True,
                recvWindow=10000,
                newOrderRespType="RESULT",
            )
            logger.info("LiveTrader: MARKET %s to close %s (qty %.4f)", side, position_key, qty)
        except BinanceAPIException as exc:
            logger.error("LiveTrader: close position failed for %s: %s", position_key, exc)
        return None

        avg_price = float(order.get("avgPrice") or order.get("price") or exit_price or position.entry_price)
        pnl = (avg_price - position.entry_price) * position.size if position.side == "LONG" else (position.entry_price - avg_price) * position.size
        pnl_percent = (pnl / position.margin_usdt * 100.0) if getattr(position, "margin_usdt", 0.0) else 0.0

        closed = ClosedTrade(
            id=position.id,
            symbol=symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=avg_price,
            size=position.size,
            leverage=position.leverage,
            entry_time=position.entry_time,
            exit_time=datetime.utcnow(),
            pnl=pnl,
            pnl_percent=pnl_percent,
            close_reason=reason,
        )

        self.closed_trades.append(closed)
        self.positions.pop(position_key, None)
        try:
            self._cancel_related_orders(position.symbol)
        except Exception as exc:
            logger.debug("LiveTrader: cancel related orders failed: %s", exc)
        self.grid_orders_tracker.pop(position.symbol, None)
        self.refresh_from_exchange(force=True)
        return closed

    def close_all_positions(self, *args, **kwargs):
        for key, position in list(self.positions.items()):
            mark_price = getattr(position, "mark_price", position.entry_price)
            self.close_position_manually(key, mark_price, "Bulk close")

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _sync_server_time(self, force: bool = False):
        """Синхронизация timestamp для избежания -1021."""
        now = time()
        if not force and (now - self._last_time_sync_ts) < 60:
            return
        try:
            server_time = self.client.futures_time()
            server_ms = int(server_time.get("serverTime", 0))
            if server_ms:
                local_ms = int(now * 1000)
                self.client.timestamp_offset = server_ms - local_ms
                self._last_time_sync_ts = now
        except Exception as exc:
            logger.debug("LiveTrader: time sync failed: %s", exc)

    def _ensure_symbol_leverage(self, symbol: str):
        target = int(self.leverage)
        if self._leverage_cache.get(symbol) == target:
            return
        try:
            self.client.futures_change_leverage(symbol=symbol, leverage=target, recvWindow=10000)
            self._leverage_cache[symbol] = target
            logger.info("LiveTrader: leverage %dx applied to %s", target, symbol)
        except BinanceAPIException as exc:
            logger.warning("LiveTrader: unable to set leverage for %s: %s", symbol, exc)

    def _place_next_averaging_order(self, symbol: str, tracker: Dict[str, Any], buffer_ratio: float = 0.001) -> Optional[Dict[str, Any]]:
        tracker.setdefault("buffer_ratio", buffer_ratio)
        position_key = self._make_key(symbol, "LONG")
        position = self.positions.get(position_key)
        if not position:
            logger.debug("LiveTrader: no position for %s to place averaging order", symbol)
            return None

        rules = self.symbol_rules.get(symbol)
        if not rules:
            logger.error("LiveTrader: missing rules for %s", symbol)
            return None

        position_info = self._fetch_position_info(symbol)
        liq_price = float(position_info.get("liquidationPrice", 0.0)) if position_info else 0.0
        entry_price = position.entry_price
        if position_info:
            entry_price = float(position_info.get("entryPrice", entry_price or 0.0)) or entry_price

        if liq_price <= 0 and entry_price > 0:
            leverage = float(position.leverage or self.leverage or 1)
            if position.side == "LONG":
                liq_price = entry_price * (1 - (0.99 / leverage))
            else:
                liq_price = entry_price * (1 + (0.99 / leverage))

        if liq_price <= 0:
            logger.warning("LiveTrader: no liquidation price for %s", symbol)
            return None

        rules_tick = float(rules.get("tick_size", 0.0001) or 0.0001)
        desired_price = self._align_price(liq_price * (1 + tracker["buffer_ratio"]), rules_tick)
        if desired_price <= liq_price:
            desired_price = liq_price + rules_tick

        level_idx = tracker.get("level_index", 1)
        base_qty = tracker.get("base_qty", position.size)
        if level_idx <= 2:
            qty = base_qty
        else:
            qty = max(position.size, base_qty)
        qty = max(qty, self._calculate_min_quantity(desired_price, rules))

        try:
            self._sync_server_time()
            order = self.client.futures_create_order(
                symbol=symbol,
                side="BUY",
                type="LIMIT",
                timeInForce="GTC",
                quantity=qty,
                price=f"{desired_price:.8f}",
                reduceOnly=False,
                recvWindow=10000,
            )
        except BinanceAPIException as exc:
            logger.error("LiveTrader: failed to place averaging order %s: %s", symbol, exc)
            return None

        order_id = order.get("orderId")
        tracker["pending_order_id"] = order_id
        simplified = {
            "orderId": order_id,
            "symbol": symbol,
            "side": "BUY",
            "type": "LIMIT",
            "price": desired_price,
            "origQty": qty,
            "executedQty": 0.0,
            "status": "NEW",
        }
        self._open_orders_map[int(order_id)] = simplified
        self.open_orders = list(self._open_orders_map.values())

        order_info = {
            "orderId": order_id,
            "price": desired_price,
            "quantity": qty,
            "level": level_idx,
        }
        position.averaging_orders = [order_info]
        logger.info("LiveTrader: placed averaging L%d for %s qty %.4f price %.6f", level_idx, symbol, qty, desired_price)
        return order_info

    def _place_take_profit_order(self, symbol: str):
        key = self._make_key(symbol, "LONG")
        self._cancel_take_profit_order(symbol)
        self.refresh_from_exchange(force=True)

        position = self.positions.get(key)
        position_info = self._fetch_position_info(symbol)

        entry_price = 0.0
        liq_price = 0.0
        qty = 0.0
        leverage = float(self.leverage)

        if position:
            entry_price = position.entry_price
            qty = position.size
            liq_price = getattr(position, "liquidation_price", 0.0)
            leverage = getattr(position, "leverage", leverage) or leverage
        if position_info:
            entry_price = float(position_info.get("entryPrice", entry_price or 0.0))
            liq_raw = float(position_info.get("liquidationPrice", 0.0))
            liq_price = liq_raw or liq_price
            qty = abs(float(position_info.get("positionAmt", qty or 0.0)))
            lev_raw = float(position_info.get("leverage", leverage) or leverage)
            leverage = lev_raw or leverage

        if liq_price <= 0 and entry_price > 0 and leverage > 0:
            liq_price = entry_price * (1 - (0.99 / leverage))

        if qty <= 0 or entry_price <= 0 or liq_price <= 0:
            logger.warning(
                "LiveTrader: skip TP for %s (qty=%.4f entry=%.4f liq=%.4f)",
                symbol,
                qty,
                entry_price,
                liq_price,
            )
            return None

        is_long = qty >= 0
        qty = abs(qty)
        distance = abs(entry_price - liq_price)
        take_price = entry_price + distance * 2.0 if is_long else entry_price - distance * 2.0
        side = "SELL" if is_long else "BUY"

        rules = self.symbol_rules.get(symbol)
        tick = float(rules.get("tick_size", 0.0001) or 0.0001) if rules else 0.0001
        take_price = self._align_price(take_price, tick)
        qty = round(qty, 8)

        try:
            self._sync_server_time()
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="LIMIT",
                timeInForce="GTC",
                quantity=qty,
                price=f"{take_price:.8f}",
                reduceOnly=True,
                recvWindow=10000,
            )
        except BinanceAPIException as exc:
            logger.error("LiveTrader: take-profit failed for %s: %s", symbol, exc)
        return None

        order_id = order.get("orderId")
        self._open_orders_map[int(order_id)] = {
            "orderId": order_id,
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "price": take_price,
            "origQty": qty,
            "executedQty": 0.0,
            "status": "NEW",
            "reduceOnly": True,
        }
        self.open_orders = list(self._open_orders_map.values())
        logger.info(
            "LiveTrader: take-profit placed for %s qty %.4f price %.6f (entry %.6f liq %.6f)",
            symbol,
            qty,
            take_price,
            entry_price,
            liq_price,
        )
        self.take_profit_orders[symbol] = order_id
        if position:
            setattr(position, "take_profit_order", {"orderId": order_id, "price": take_price})
        return {"orderId": order_id, "price": take_price}

    async def _spawn_next_averaging(self, symbol: str, tracker: Dict[str, Any]):
        result = await asyncio.to_thread(self._place_next_averaging_order, symbol, tracker)
        if result is None:
            self.grid_orders_tracker.pop(symbol, None)
        self._place_take_profit_order(symbol)

    def _fetch_position_info(self, symbol: str) -> Dict[str, Any]:
        try:
            info = self.client.futures_position_information(symbol=symbol)
            if info:
                self._last_position_info[symbol] = info[0]
                return info[0]
        except Exception as exc:
            logger.debug("LiveTrader: position info fetch failed for %s: %s", symbol, exc)
        return self._last_position_info.get(symbol, {})

    def _cache_position_info(self):
        try:
            info = self.client.futures_position_information()
            for payload in info or []:
                symbol = payload.get("symbol")
                if symbol:
                    self._last_position_info[symbol] = payload
        except Exception:
            pass

    @staticmethod
    def _align_price(price: float, tick_size: float) -> float:
        if tick_size <= 0:
            return price
        steps = round(price / tick_size)
        return round(steps * tick_size, 8)

    def _cancel_related_orders(self, symbol: str):
        orders_to_cancel = [
            order_id
            for order_id, order in list(self._open_orders_map.items())
            if order.get("symbol") == symbol
        ]
        for order_id in orders_to_cancel:
            try:
                self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
                logger.info("LiveTrader: cancelled order %s for %s after close", order_id, symbol)
            except BinanceAPIException as exc:
                if "Unknown order" not in str(exc):
                    logger.warning("LiveTrader: failed to cancel order %s: %s", order_id, exc)
            finally:
                self._open_orders_map.pop(order_id, None)
        self.open_orders = list(self._open_orders_map.values())
        self._cancel_take_profit_order(symbol)

    def _cancel_take_profit_order(self, symbol: str):
        order_id = self.take_profit_orders.pop(symbol, None)
        if not order_id:
            return
        try:
            self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            logger.info("LiveTrader: cancelled take-profit %s for %s", order_id, symbol)
        except BinanceAPIException as exc:
            if "Unknown order" not in str(exc):
                logger.warning("LiveTrader: failed to cancel TP order %s: %s", order_id, exc)
        finally:
            self._open_orders_map.pop(int(order_id), None)
            self.open_orders = list(self._open_orders_map.values())

