#!/usr/bin/env python3
"""
🔌 BINANCE WEBSOCKET CLIENT
Подключение к Binance Futures для получения реал-тайм данных
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
    """
    Клиент для получения данных в реальном времени через WebSocket
    """
    
    def __init__(self, api_key: str, api_secret: str):
        """
        Args:
            api_key: Binance API ключ
            api_secret: Binance API секретный ключ
        """
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Синхронный клиент для REST запросов (ленивая инициализация)
        self.client = None
        
        # Хранилища данных
        self.orderbooks: Dict[str, Dict] = {}
        self.trades: Dict[str, deque] = {}
        self.prices: Dict[str, float] = {}
        self.price_ts: Dict[str, float] = {}  # unix time последнего обновления цены
        self.book_ticker: Dict[str, Dict[str, float]] = {}  # {'bid': float, 'ask': float, 'ts': float}
        # Состояние синхронизации стакана: bids/asks dict + lastUpdateId
        self.book_state: Dict[str, Dict] = {}
        # Троттлинг ресинка
        self._last_resync_ts: Dict[str, float] = {}
        self._resync_attempts: Dict[str, int] = {}
        
        # Callback функции
        self.orderbook_callbacks: List[Callable] = []
        self.trade_callbacks: List[Callable] = []
        self.price_callbacks: List[Callable] = []
        
        # Состояние
        self.running = False
        self.tasks = []
        self.session = None  # aiohttp session
        
        logger.info("🔌 Binance WebSocket клиент инициализирован")
    
    async def start_streams(self, symbols: List[str]):
        """
        Запуск WebSocket стримов для списка символов
        
        Args:
            symbols: Список торговых пар (например: ['ETHUSDT', 'BTCUSDT'])
        """
        self.running = True
        
        # Создаем aiohttp session для асинхронных HTTP запросов
        if self.session is None:
            self.session = aiohttp.ClientSession()
        
        # Инициализируем хранилища для каждого символа
        for symbol in symbols:
            self.orderbooks[symbol] = {'bids': [], 'asks': [], 'timestamp': 0}
            self.trades[symbol] = deque(maxlen=100)  # Последние 100 сделок
            self.prices[symbol] = 0.0
            self.price_ts[symbol] = 0.0
            self.book_state[symbol] = {'bids': {}, 'asks': {}, 'lastUpdateId': None, 'synced': False}
            self._last_resync_ts[symbol] = 0.0
            self._resync_attempts[symbol] = 0
            # Снапшот стакана (UM Futures)
            try:
                # Используем прямой REST UM Futures endpoint вместо client.futures_depth
                async with self.session.get(
                    "https://fapi.binance.com/fapi/v1/depth",
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
                    # Сформируем топ-20
                    top_bids = [[p, bids[p]] for p in sorted(bids.keys(), reverse=True)[:20]]
                    top_asks = [[p, asks[p]] for p in sorted(asks.keys())[:20]]
                    self.orderbooks[symbol] = {'bids': top_bids, 'asks': top_asks, 'timestamp': 0}
            except Exception as e:
                logger.error(f"❌ Ошибка получения snapshot depth для {symbol}: {e}")
        
        # Запускаем стримы
        for symbol in symbols:
            # Depth stream (стакан)
            depth_task = asyncio.create_task(self._depth_stream(symbol))
            self.tasks.append(depth_task)
            
            # Trade stream (лента сделок)
            trade_task = asyncio.create_task(self._trade_stream(symbol))
            self.tasks.append(trade_task)
            
            # BookTicker (best bid/ask) — для отображения актуального спреда
            bt_task = asyncio.create_task(self._book_ticker_stream(symbol))
            self.tasks.append(bt_task)
        
        logger.info(f"🚀 Запущено {len(self.tasks)} WebSocket стримов для {len(symbols)} пар")
    
    def _futures_stream_url(self, stream_type: str, symbol_lower: str) -> str:
        """Построить URL для UM Futures WebSocket (fstream).
        stream_type: 'depth'|'aggtrade'|'bookticker'
        """
        if stream_type == 'depth':
            # Partial depth 20 levels, 100ms
            return f"wss://fstream.binance.com/ws/{symbol_lower}@depth20@100ms"
        if stream_type == 'aggtrade':
            return f"wss://fstream.binance.com/ws/{symbol_lower}@aggTrade"
        if stream_type == 'bookticker':
            return f"wss://fstream.binance.com/ws/{symbol_lower}@bookTicker"
        raise ValueError(f"Unknown stream_type: {stream_type}")

    async def _depth_stream(self, symbol: str):
        """WebSocket стрим для стакана ордеров"""
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
                            # Валидация последовательности
                            if pu is not None and last_id is not None and pu != last_id:
                                raise ValueError(f"sequence gap: pu={pu}, last={last_id}")
                            if u is not None and last_id is not None and u < last_id:
                                continue  # старое событие
                        except Exception as e:
                            now_ts = time()
                            # Троттлим ресинки: не чаще раза в 2с и не более 5 подряд
                            if now_ts - self._last_resync_ts.get(symbol, 0.0) < 2.0 or self._resync_attempts.get(symbol, 0) >= 5:
                                # Помечаем как не синхронизированное, но не блокируем поток
                                state['synced'] = False
                                continue
                            logger.warning(f"⚠️ Предупреждение последовательности глубины {symbol}: {e}, ресинк")
                            try:
                                if self.session is None:
                                    logger.error(f"❌ Сессия не инициализирована для {symbol}")
                                    state['synced'] = False
                                    await asyncio.sleep(1)
                                    continue
                                async with self.session.get(
                                    "https://fapi.binance.com/fapi/v1/depth",
                                    params={"symbol": symbol, "limit": 1000},
                                    timeout=aiohttp.ClientTimeout(total=5)
                                ) as resp:
                                    resp.raise_for_status()
                                    snapshot = await resp.json()
                                    last_id = snapshot.get('lastUpdateId')
                                    bids = {float(p): float(q) for p, q in snapshot.get('bids', [])}
                                    asks = {float(p): float(q) for p, q in snapshot.get('asks', [])}
                                    self.book_state[symbol] = {'bids': bids, 'asks': asks, 'lastUpdateId': last_id, 'synced': True}
                                    # Обновим top20 для визуализации
                                    top_bids = [[p, bids[p]] for p in sorted(bids.keys(), reverse=True)[:20]]
                                    top_asks = [[p, asks[p]] for p in sorted(asks.keys())[:20]]
                                    self.orderbooks[symbol] = {'bids': top_bids, 'asks': top_asks, 'timestamp': 0}
                                    self._last_resync_ts[symbol] = now_ts
                                    self._resync_attempts[symbol] = 0
                                    logger.info(f"✅ Ресинк успешен {symbol}")
                            except Exception as ee:
                                self._resync_attempts[symbol] = self._resync_attempts.get(symbol, 0) + 1
                                logger.error(f"❌ Ресинк не удался {symbol} ({self._resync_attempts[symbol]}): {ee}")
                                state['synced'] = False
                                continue
                        # Применяем диффы
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
                        # Пересобираем топ-20
                        top_bids = [[p, bids_map[p]] for p in sorted(bids_map.keys(), reverse=True)[:20]]
                        top_asks = [[p, asks_map[p]] for p in sorted(asks_map.keys())[:20]]
                        ob = {'bids': top_bids, 'asks': top_asks, 'timestamp': payload.get('E') or payload.get('T') or 0}
                        self.orderbooks[symbol] = ob
                        # Обновим mid для отображения
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
                                logger.error(f"Ошибка в orderbook callback: {e}")
            except Exception as e:
                logger.error(f"❌ Ошибка в depth stream для {symbol}: {e}")
                await asyncio.sleep(0.5)
    
    async def _trade_stream(self, symbol: str):
        """WebSocket стрим для ленты сделок"""
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
                                logger.error(f"Ошибка в trade callback: {e}")
            except Exception as e:
                logger.error(f"❌ Ошибка в trade stream для {symbol}: {e}")
                await asyncio.sleep(0.5)

    async def _book_ticker_stream(self, symbol: str):
        """UM Futures лучший bid/ask поток (bookTicker)"""
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
                logger.error(f"❌ Ошибка в bookTicker stream для {symbol}: {e}")
                await asyncio.sleep(0.5)
    
    def get_orderbook(self, symbol: str) -> Dict:
        """Получить текущий стакан ордеров"""
        return self.orderbooks.get(symbol, {'bids': [], 'asks': [], 'timestamp': 0})
    
    def get_recent_trades(self, symbol: str, count: int = 50, window_seconds: float = 20.0) -> List[Dict]:
        """
        Получить последние сделки за указанное окно времени
        
        Args:
            symbol: Торговая пара
            count: Максимальное количество сделок
            window_seconds: Окно времени в секундах (по умолчанию 20 секунд)
        
        Returns:
            Список сделок за последние window_seconds секунд
        """
        trades = list(self.trades.get(symbol, []))
        if not trades:
            return []
        
        # Фильтруем сделки по времени (за последние window_seconds секунд)
        now = time()
        recent_trades = []
        for trade in reversed(trades):  # Идем с конца (самые свежие сначала)
            trade_time = trade.get('time', 0) / 1000.0  # Конвертируем из ms в секунды
            if now - trade_time <= window_seconds:
                recent_trades.insert(0, trade)  # Вставляем в начало для сохранения порядка
                if len(recent_trades) >= count:
                    break
        
        return recent_trades
    
    def get_current_price(self, symbol: str) -> float:
        """
        Возвращает АКТУАЛЬНУЮ цену.
        - Источник: лента сделок (приоритет) или mid-price стакана как резерв.
        - Фильтр свежести: если последняя цена из сделок старше 3 секунд — используем mid из фьючерсного стакана,
          иначе 0.0. Никаких REST фоллбеков.
        """
        price = self.prices.get(symbol, 0.0)
        last_ts = self.price_ts.get(symbol, 0.0)
        now = time()
        # Если цена из ленты свежая — используем её
        if price > 0 and now - last_ts <= 3.0:
            return price
        # Иначе пробуем свежий bookTicker (best bid/ask) и возвращаем mid
        bt = self.book_ticker.get(symbol)
        if bt and bt.get('bid') and bt.get('ask'):
            bid = bt['bid']
            ask = bt['ask']
            mid = (bid + ask) / 2
            if mid > 0:
                return mid
        # Нет свежих данных — возвращаем 0.0 (лучше пропустить шаг, чем использовать сомнительную цену)
        return 0.0

    def is_symbol_ready(self, symbol: str, min_trades: int = 5, max_trade_age_sec: float = 3.0) -> bool:
        """Готов ли символ к торговле: есть синхронизированный стакан, свежая цена и достаточно принтов."""
        # Стакан синхронизирован
        state = self.book_state.get(symbol)
        if not state or not state.get('synced'):
            return False
        # Достаточно принтов
        if len(self.trades.get(symbol, [])) < min_trades:
            return False
        # Свежая цена из принтов
        now_ts = time()
        if now_ts - self.price_ts.get(symbol, 0.0) > max_trade_age_sec:
            return False
        # Есть актуальный bookTicker для контроля спреда
        bt = self.book_ticker.get(symbol)
        if not bt or bt.get('bid', 0.0) <= 0 or bt.get('ask', 0.0) <= 0:
            return False
        return True

    def are_all_ready(self, symbols: List[str], min_trades: int = 5, max_trade_age_sec: float = 3.0) -> bool:
        """Все ли символы готовы к началу торговли."""
        for s in symbols:
            if not self.is_symbol_ready(s, min_trades=min_trades, max_trade_age_sec=max_trade_age_sec):
                return False
        return True
    
    def get_account_balance(self) -> float:
        """Получить баланс аккаунта (Futures)"""
        try:
            # Ленивая инициализация клиента
            if self.client is None:
                self.client = Client(self.api_key, self.api_secret)
            
            account = self.client.futures_account()
            
            # Ищем USDT баланс
            for asset in account['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['walletBalance'])
            
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса: {e}")
            return 0.0
    
    def register_orderbook_callback(self, callback: Callable):
        """Регистрация callback для обновлений стакана"""
        self.orderbook_callbacks.append(callback)
    
    def register_trade_callback(self, callback: Callable):
        """Регистрация callback для обновлений ленты сделок"""
        self.trade_callbacks.append(callback)
    
    async def stop(self):
        """Остановка всех стримов"""
        self.running = False
        
        # Отменяем все задачи
        for task in self.tasks:
            task.cancel()
        
        # Ждем завершения
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Закрываем aiohttp session
        if self.session:
            await self.session.close()
        
        logger.info("⏹️ WebSocket стримы остановлены")


# Простой тест
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    async def test_client():
        # Тестовые ключи (замени на свои)
        API_KEY = "your_api_key"
        API_SECRET = "your_api_secret"
        
        if API_KEY == "your_api_key":
            print("❌ Замени API_KEY и API_SECRET на свои ключи!")
            return
        
        client = BinanceRealtimeClient(API_KEY, API_SECRET)
        
        # Callback для отображения стакана
        async def on_orderbook_update(symbol: str, orderbook: Dict):
            best_bid = orderbook['bids'][0] if orderbook['bids'] else [0, 0]
            best_ask = orderbook['asks'][0] if orderbook['asks'] else [0, 0]
            print(f"{symbol}: Bid ${best_bid[0]:.2f} / Ask ${best_ask[0]:.2f}")
        
        client.register_orderbook_callback(on_orderbook_update)
        
        # Запускаем стримы
        await client.start_streams(['ETHUSDT', 'BTCUSDT'])
        
        # Работаем 30 секунд
        await asyncio.sleep(30)
        
        # Останавливаем
        await client.stop()
    
    asyncio.run(test_client())

