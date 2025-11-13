#!/usr/bin/env python3
"""
🔌 BINANCE WEBSOCKET CLIENT
Realtime access to Binance Futures market data.
"""

import asyncio
import json
import logging
from typing import Dict, List, Callable, Optional
from time import time
from collections import deque
import websockets
import aiohttp
from binance.client import Client

logger = logging.getLogger(__name__)


class BinanceRealtimeClient:
    """Realtime WebSocket client for Binance Futures."""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        """
        Args:
            api_key: Binance API key.
            api_secret: Binance API secret.
            testnet: Use Binance Testnet instead of mainnet.
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # Set base URLs based on testnet flag
        if testnet:
            self.ws_base = "wss://stream.binancefuture.com"
            self.api_base = "https://testnet.binancefuture.com"
        else:
            self.ws_base = "wss://fstream.binance.com"
            self.api_base = "https://fapi.binance.com"
        
        # Lazy-initialised REST client
        self.client = None
        
        # Data stores
        self.orderbooks: Dict[str, Dict] = {}
        self.trades: Dict[str, deque] = {}
        self.prices: Dict[str, float] = {}
        self.price_ts: Dict[str, float] = {}  # unix ts of the latest price update
        self.book_ticker: Dict[str, Dict[str, float]] = {}  # {'bid': float, 'ask': float, 'ts': float}
        # Order book sync state: bids/asks dict + lastUpdateId
        self.book_state: Dict[str, Dict] = {}
        # Resync throttling
        self._last_resync_ts: Dict[str, float] = {}
        self._resync_attempts: Dict[str, int] = {}
        
        # Callback registries
        self.orderbook_callbacks: List[Callable] = []
        self.trade_callbacks: List[Callable] = []
        self.price_callbacks: List[Callable] = []
        
        # Runtime state
        self.running = False
        self.tasks = []
        self.session = None  # aiohttp session
        
        logger.info("🔌 Binance WebSocket client initialised")
    
    async def start_streams(self, symbols: List[str]):
        """
        Launch WebSocket streams for provided symbols.

        Args:
            symbols: List of trading pairs (e.g. ['ETHUSDT', 'BTCUSDT']).
        """
        self.running = True
        
        # Clear old tasks to prevent duplicates
        if self.tasks:
            logger.info(f"🧹 Clearing {len(self.tasks)} old tasks")
            self.tasks = []
        
        # Create/recreate aiohttp session for async HTTP requests
        if self.session is None or self.session.closed:
            if self.session is not None and self.session.closed:
                logger.info("🔄 Recreating closed aiohttp session")
            self.session = aiohttp.ClientSession()
        
        # Initialise state for each symbol
        for symbol in symbols:
            self.orderbooks[symbol] = {'bids': [], 'asks': [], 'timestamp': 0}
            self.trades[symbol] = deque(maxlen=100)  # Last 100 trades
            self.prices[symbol] = 0.0
            self.price_ts[symbol] = 0.0
            self.book_state[symbol] = {'bids': {}, 'asks': {}, 'lastUpdateId': None, 'synced': False}
            self._last_resync_ts[symbol] = 0.0
            self._resync_attempts[symbol] = 0
            # Capture order book snapshot (UM Futures)
            try:
                # Use the direct REST UM Futures endpoint instead of client.futures_depth
                async with self.session.get(
                    f"{self.api_base}/fapi/v1/depth",
                    params={"symbol": symbol, "limit": 1000},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    resp.raise_for_status()
                    snapshot = await resp.json()
                    last_id = snapshot.get('lastUpdateId')
                    bids = {float(p): float(q) for p, q in snapshot.get('bids', [])}
                    asks = {float(p): float(q) for p, q in snapshot.get('asks', [])}
                    self.book_state[symbol] = {
                        'bids': bids,
                        'asks': asks,
                        'lastUpdateId': last_id,
                        'synced': True
                    }
                    # Precompute top 20 levels
                    top_bids = [[p, bids[p]] for p in sorted(bids.keys(), reverse=True)[:20]]
                    top_asks = [[p, asks[p]] for p in sorted(asks.keys())[:20]]
                    self.orderbooks[symbol] = {'bids': top_bids, 'asks': top_asks, 'timestamp': 0}
            except Exception as e:
                logger.error(f"❌ Snapshot depth fetch failed for {symbol}: {e}")
        
        # Launch streams
        for symbol in symbols:
            # Depth stream (order book)
            depth_task = asyncio.create_task(self._depth_stream(symbol))
            self.tasks.append(depth_task)
            
            # Trade stream (trade feed)
            trade_task = asyncio.create_task(self._trade_stream(symbol))
            self.tasks.append(trade_task)
            
            # BookTicker (best bid/ask) — to monitor live spread
            bt_task = asyncio.create_task(self._book_ticker_stream(symbol))
            self.tasks.append(bt_task)
        
        logger.info(f"🚀 Started {len(self.tasks)} WebSocket streams for {len(symbols)} pairs")
    
    def _futures_stream_url(self, stream_type: str, symbol_lower: str) -> str:
        """Build the UM Futures WebSocket URL.

        stream_type: 'depth' | 'aggtrade' | 'bookticker'
        """
        if stream_type == 'depth':
            # Partial depth 20 levels, 100ms
            return f"{self.ws_base}/ws/{symbol_lower}@depth20@100ms"
        if stream_type == 'aggtrade':
            return f"{self.ws_base}/ws/{symbol_lower}@aggTrade"
        if stream_type == 'bookticker':
            return f"{self.ws_base}/ws/{symbol_lower}@bookTicker"
        raise ValueError(f"Unknown stream_type: {stream_type}")

    async def _depth_stream(self, symbol: str):
        """Order book WebSocket stream."""
        symbol_lower = symbol.lower()
        url = self._futures_stream_url('depth', symbol_lower)
        while self.running:
            try:
                async with websockets.connect(url, ping_interval=20, max_queue=100) as ws:
                    while self.running:
                        raw = await ws.recv()
                        payload = json.loads(raw) if isinstance(raw, (bytes, str)) else raw
                        if not isinstance(payload, dict) or 'b' not in payload or 'a' not in payload:
                            continue
                        state = self.book_state.get(symbol)
                        if not state or not state.get('synced'):
                            continue
                        try:
                            U = payload.get('U')  # first update ID in event
                            u = payload.get('u')  # final update ID in event
                            pu = payload.get('pu')  # previous final update ID
                            last_id = state.get('lastUpdateId') or 0
                            # Sequence validation
                            if pu is not None and last_id is not None and pu != last_id:
                                raise ValueError(f"sequence gap: pu={pu}, last={last_id}")
                            if u is not None and last_id is not None and u < last_id:
                                continue  # stale event
                        except Exception as e:
                            now_ts = time()
                            # Throttle resyncs: max once every 2s and max 5 attempts
                            if now_ts - self._last_resync_ts.get(symbol, 0.0) < 2.0 or self._resync_attempts.get(symbol, 0) >= 5:
                                # Mark as unsynced, keep stream alive
                                state['synced'] = False
                                continue
                            logger.warning(f"⚠️ Depth sequence warning {symbol}: {e}, resyncing")
                            try:
                                if self.session is None:
                                    logger.error(f"❌ Session not initialised for {symbol}")
                                    state['synced'] = False
                                    await asyncio.sleep(1)
                                    continue
                                async with self.session.get(
                                    f"{self.api_base}/fapi/v1/depth",
                                    params={"symbol": symbol, "limit": 1000},
                                    timeout=aiohttp.ClientTimeout(total=5)
                                ) as resp:
                                    resp.raise_for_status()
                                    snapshot = await resp.json()
                                    last_id = snapshot.get('lastUpdateId')
                                    bids = {float(p): float(q) for p, q in snapshot.get('bids', [])}
                                    asks = {float(p): float(q) for p, q in snapshot.get('asks', [])}
                                    self.book_state[symbol] = {'bids': bids, 'asks': asks, 'lastUpdateId': last_id, 'synced': True}
                                    # Refresh top-20 for UI
                                    top_bids = [[p, bids[p]] for p in sorted(bids.keys(), reverse=True)[:20]]
                                    top_asks = [[p, asks[p]] for p in sorted(asks.keys())[:20]]
                                    self.orderbooks[symbol] = {'bids': top_bids, 'asks': top_asks, 'timestamp': 0}
                                    self._last_resync_ts[symbol] = now_ts
                                    self._resync_attempts[symbol] = 0
                                    logger.info(f"✅ Resync completed for {symbol}")
                            except Exception as ee:
                                self._resync_attempts[symbol] = self._resync_attempts.get(symbol, 0) + 1
                                logger.error(f"❌ Resync failed for {symbol} ({self._resync_attempts[symbol]}): {ee}")
                                state['synced'] = False
                                continue
                        # Apply deltas
                        bids_map = state['bids']
                        asks_map = state['asks']
                        for p, q in payload['b']:
                            price = float(p); qty = float(q)
                            if qty == 0.0:
                                bids_map.pop(price, None)
                            else:
                                bids_map[price] = qty
                        for p, q in payload['a']:
                            price = float(p); qty = float(q)
                            if qty == 0.0:
                                asks_map.pop(price, None)
                            else:
                                asks_map[price] = qty
                        state['lastUpdateId'] = payload.get('u', state.get('lastUpdateId'))
                        # Rebuild top-20
                        top_bids = [[p, bids_map[p]] for p in sorted(bids_map.keys(), reverse=True)[:20]]
                        top_asks = [[p, asks_map[p]] for p in sorted(asks_map.keys())[:20]]
                        ob = {'bids': top_bids, 'asks': top_asks, 'timestamp': payload.get('E') or payload.get('T') or 0}
                        self.orderbooks[symbol] = ob
                        # Update mid price
                        if top_bids and top_asks:
                            best_bid = top_bids[0][0]
                            best_ask = top_asks[0][0]
                            mid_price = (best_bid + best_ask) / 2
                            if mid_price > 0:
                                self.prices[symbol] = mid_price
                                self.price_ts[symbol] = time()
                        for callback in self.orderbook_callbacks:
                            try:
                                await callback(symbol, ob)
                            except Exception as e:
                                logger.error(f"Orderbook callback error: {e}")
            except Exception as e:
                logger.error(f"❌ Depth stream error for {symbol}: {e}")
                await asyncio.sleep(0.5)
    
    async def _trade_stream(self, symbol: str):
        """Trade tape WebSocket stream."""
        symbol_lower = symbol.lower()
        url = self._futures_stream_url('aggtrade', symbol_lower)
        while self.running:
            try:
                async with websockets.connect(url, ping_interval=20, max_queue=100) as ws:
                    while self.running:
                        raw = await ws.recv()
                        payload = json.loads(raw) if isinstance(raw, (bytes, str)) else raw
                        if not isinstance(payload, dict) or 'p' not in payload or 'T' not in payload or 'q' not in payload:
                            continue
                        try:
                            price_val = float(payload['p'])
                            qty_val = float(payload['q'])
                            ts_val = int(payload['T'])
                        except Exception:
                            continue
                        if price_val <= 0 or qty_val <= 0:
                            continue
                        trade = {
                            'symbol': symbol,
                            'price': price_val,
                            'quantity': qty_val,
                            'time': ts_val,
                            'is_buyer_maker': payload.get('m', False)
                        }
                        self.trades[symbol].append(trade)
                        self.prices[symbol] = trade['price']
                        self.price_ts[symbol] = time()
                        for callback in self.trade_callbacks:
                            try:
                                await callback(symbol, trade)
                            except Exception as e:
                                logger.error(f"Trade callback error: {e}")
            except Exception as e:
                logger.error(f"❌ Trade stream error for {symbol}: {e}")
                await asyncio.sleep(0.5)

    async def _book_ticker_stream(self, symbol: str):
        """UM Futures best bid/ask stream (bookTicker)."""
        symbol_lower = symbol.lower()
        url = self._futures_stream_url('bookticker', symbol_lower)
        while self.running:
            try:
                async with websockets.connect(url, ping_interval=20, max_queue=100) as ws:
                    while self.running:
                        raw = await ws.recv()
                        payload = json.loads(raw) if isinstance(raw, (bytes, str)) else raw
                        if not isinstance(payload, dict):
                            continue
                        try:
                            best_bid = float(payload.get('b', 0.0))
                            best_ask = float(payload.get('a', 0.0))
                            ts_val = float(payload.get('T', 0)) or time()
                        except Exception:
                            continue
                        if best_bid <= 0 or best_ask <= 0:
                            continue
                        self.book_ticker[symbol] = {'bid': best_bid, 'ask': best_ask, 'ts': ts_val}
            except Exception as e:
                logger.error(f"❌ BookTicker stream error for {symbol}: {e}")
                await asyncio.sleep(0.5)
    
    def get_orderbook(self, symbol: str) -> Dict:
        """Return the current order book snapshot."""
        return self.orderbooks.get(symbol, {'bids': [], 'asks': [], 'timestamp': 0})
    
    def get_recent_trades(self, symbol: str, count: int = 50, window_seconds: float = 20.0) -> List[Dict]:
        """
        Get recent trades for a symbol within a time window.

        Args:
            symbol: Trading pair.
            count: Maximum number of trades to return.
            window_seconds: Time window in seconds (default 20 seconds).

        Returns:
            List of trades within the last ``window_seconds`` seconds.
        """
        trades = list(self.trades.get(symbol, []))
        if not trades:
            return []
        
        # Filter trades by age within window_seconds
        now = time()
        recent_trades = []
        for trade in reversed(trades):  # Start with newest
            trade_time = trade.get('time', 0) / 1000.0  # Convert from ms to seconds
            if now - trade_time <= window_seconds:
                recent_trades.insert(0, trade)  # Maintain chronological order
                if len(recent_trades) >= count:
                    break
        
        return recent_trades
    
    def get_current_price(self, symbol: str) -> float:
        """
        Return the most recent price.

        Priority source: trade tape price, with order-book mid-price fallback.
        Freshness filter: if trade price is older than 3 seconds, use mid-price;
        If no WebSocket data available, fallback to REST API.
        """
        price = self.prices.get(symbol, 0.0)
        last_ts = self.price_ts.get(symbol, 0.0)
        now = time()
        # If trade price is fresh, use it
        if price > 0 and now - last_ts <= 3.0:
            return price
        # Otherwise use bookTicker mid
        bt = self.book_ticker.get(symbol)
        if bt and bt.get('bid') and bt.get('ask'):
            bid = bt['bid']
            ask = bt['ask']
            mid = (bid + ask) / 2
            if mid > 0:
                return mid
        
        # REST API fallback for symbols not in WebSocket (e.g. open positions)
        try:
            if self.client is None:
                if self.testnet:
                    # Monkey-patch ping to avoid mainnet connection
                    original_ping = Client.ping
                    Client.ping = lambda self: None
                    try:
                        self.client = Client(self.api_key, self.api_secret)
                        self.client.FUTURES_URL = 'https://testnet.binancefuture.com/fapi'
                        self.client.FUTURES_DATA_URL = 'https://testnet.binancefuture.com/fapi'
                    finally:
                        Client.ping = original_ping
                else:
                    self.client = Client(self.api_key, self.api_secret)
            
            ticker = self.client.futures_symbol_ticker(symbol=symbol, recvWindow=60000)
            rest_price = float(ticker.get('price', 0))
            if rest_price > 0:
                logger.debug(f"📡 REST fallback price for {symbol}: ${rest_price:.6f}")
                return rest_price
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch REST price for {symbol}: {e}")
        
        # No data available
        return 0.0

    def is_symbol_ready(self, symbol: str, min_trades: int = 5, max_trade_age_sec: float = 3.0) -> bool:
        """Is a symbol ready for trading (synced order book, fresh price, sufficient prints)."""
        # Order book synced
        state = self.book_state.get(symbol)
        if not state or not state.get('synced'):
            return False
        # Enough trades
        if len(self.trades.get(symbol, [])) < min_trades:
            return False
        # Fresh trade price
        now_ts = time()
        if now_ts - self.price_ts.get(symbol, 0.0) > max_trade_age_sec:
            return False
        # Valid bookTicker for spread control
        bt = self.book_ticker.get(symbol)
        if not bt or bt.get('bid', 0.0) <= 0 or bt.get('ask', 0.0) <= 0:
            return False
        return True

    def are_all_ready(self, symbols: List[str], min_trades: int = 5, max_trade_age_sec: float = 3.0) -> bool:
        """Check whether all symbols are ready to trade."""
        for s in symbols:
            if not self.is_symbol_ready(s, min_trades=min_trades, max_trade_age_sec=max_trade_age_sec):
                return False
        return True
    
    def get_account_balance(self) -> float:
        """Fetch futures account balance."""
        try:
            # Lazy client initialisation
            if self.client is None:
                if self.testnet:
                    # Monkey-patch ping to avoid mainnet connection
                    original_ping = Client.ping
                    Client.ping = lambda self: None
                    try:
                        self.client = Client(self.api_key, self.api_secret)
                        self.client.FUTURES_URL = 'https://testnet.binancefuture.com/fapi'
                        self.client.FUTURES_DATA_URL = 'https://testnet.binancefuture.com/fapi'
                    finally:
                        Client.ping = original_ping
                else:
                    self.client = Client(self.api_key, self.api_secret)
            
            account = self.client.futures_account(recvWindow=60000)
            
            # Extract USDT balance
            for asset in account['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['walletBalance'])
            
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch account balance: {e}")
            return 0.0
    
    def register_orderbook_callback(self, callback: Callable):
        """Register order book update callback."""
        self.orderbook_callbacks.append(callback)
    
    def register_trade_callback(self, callback: Callable):
        """Register trade feed update callback."""
        self.trade_callbacks.append(callback)
    
    async def stop(self):
        """Stop every running stream."""
        self.running = False
        
        # Cancel outstanding tasks
        for task in self.tasks:
            task.cancel()
        
        # Await completion
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Close aiohttp session
        if self.session:
            await self.session.close()
        
        logger.info("⏹️ WebSocket streams stopped")


# Quick manual test
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    async def test_client():
        # Demo keys (replace with your own)
        API_KEY = "your_api_key"
        API_SECRET = "your_api_secret"
        
        if API_KEY == "your_api_key":
            print("❌ Replace API_KEY and API_SECRET with your own credentials!")
            return
        
        client = BinanceRealtimeClient(API_KEY, API_SECRET)
        
        # Order book display callback
        async def on_orderbook_update(symbol: str, orderbook: Dict):
            best_bid = orderbook['bids'][0] if orderbook['bids'] else [0, 0]
            best_ask = orderbook['asks'][0] if orderbook['asks'] else [0, 0]
            print(f"{symbol}: Bid ${best_bid[0]:.2f} / Ask ${best_ask[0]:.2f}")
        
        client.register_orderbook_callback(on_orderbook_update)
        
        # Start streams
        await client.start_streams(['ETHUSDT', 'BTCUSDT'])
        
        # Keep running for 30 seconds
        await asyncio.sleep(30)
        
        # Stop
        await client.stop()
    
    asyncio.run(test_client())

