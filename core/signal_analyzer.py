#!/usr/bin/env python3
"""
📊 SIGNAL ANALYZER
Анализ стаканов и генерация торговых сигналов
Использует: Фибоначчи + Число Пи + Принцип Парето
"""

import math
import logging
from typing import Dict, List, Tuple, Optional
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Математические константы
PI = math.pi  # 3.14159...
PHI = 1.618033988749  # Золотое сечение (Фибоначчи)
FIB_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]


@dataclass
class TradingSignal:
    """Торговый сигнал"""
    symbol: str
    direction: str  # 'LONG', 'SHORT', 'WAIT'
    confidence: float  # 0-100
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward: float
    reasons: List[str]
    timestamp: datetime


class SignalAnalyzer:
    """
    Анализатор сигналов на основе стакана ордеров
    Использует теорию вероятности для повышения винрейта:
    - Байесовское обновление уверенности
    - Expected Value (EV) расчет
    - Адаптивные веса факторов
    """
    
    def __init__(self, config: Dict, learning_system=None):
        """
        Args:
            config: Словарь с настройками из config.json
            learning_system: Система адаптивного обучения (опционально)
        """
        self.config = config
        self.learning_system = learning_system  # Для доступа к статистике
        
        # Параметры анализа
        self.min_confidence = config['signals']['min_confidence']
        self.min_imbalance = config['signals']['min_imbalance']
        self.large_order_threshold = config['signals']['large_order_threshold']
        self.tape_window = config['signals']['tape_window_seconds']

        # История сигналов по паре (для cooldown)
        self.last_signal_time: Dict[str, datetime] = {}
        self.cooldown_seconds = config['signals']['cooldown_seconds']
        self.strictness_percent = 50.0
        self.prob_threshold_long = 0.55
        self.prob_threshold_short = 0.53
        
        logger.info("📊 Анализатор сигналов инициализирован (вероятностная модель активна)")
    
    def set_trading_mode(self, mode: str):
        self.trading_mode = mode
        mapping = {
            "Консервативная": 30.0,
            "Умеренная": 50.0,
            "Агрессивная": 80.0
        }
        self.strictness_percent = mapping.get(mode, 50.0)
        self._update_prob_thresholds()
        logger.debug(f"📊 Режим торговли: {mode} ({self.strictness_percent:.1f}%)")

    def set_strictness(self, value: float):
        self.strictness_percent = max(1.0, min(100.0, value))
        self._update_prob_thresholds()

    def _update_prob_thresholds(self):
        # Привязка порога к жесткости: 10% → ~0.50, 50% → ~0.57, 80% → ~0.62, 100% → ~0.66
        base = 0.48 + (self.strictness_percent / 100.0) * 0.18
        self.prob_threshold_long = min(0.70, max(0.50, base))
        self.prob_threshold_short = min(0.68, max(0.48, self.prob_threshold_long - 0.01))
    
    def analyze(self, symbol: str, orderbook: Dict, recent_trades: List[Dict]) -> TradingSignal:
        """
        Полный анализ и генерация сигнала
        
        Args:
            symbol: Торговая пара
            orderbook: Стакан ордеров {'bids': [[price, qty], ...], 'asks': [...]}
            recent_trades: Последние сделки
            
        Returns:
            TradingSignal с рекомендацией
        """
        if not orderbook['bids'] or not orderbook['asks']:
            return self._wait_signal(symbol, "Пустой стакан")
        
        # Текущая цена (mid price)
        best_bid = orderbook['bids'][0][0]
        best_ask = orderbook['asks'][0][0]
        current_price = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        spread_percent = (spread / current_price) * 100
        
        # ФИЛЬТР: Если спред слишком широкий - не торгуем
        if spread_percent > 0.1:  # >0.1% - пропуск
            return self._wait_signal(symbol, f"Широкий спред ({spread_percent:.3f}% > 0.1%)")
        
        # --- АНАЛИЗ СТАКАНА ---
        
        # 1. Дисбаланс bid/ask (Принцип Парето 80/20)
        imbalance_score, bid_percent, reasons_imbalance = self._analyze_imbalance(orderbook)
        
        # 2. Крупные стены (order walls)
        wall_score, reasons_walls = self._analyze_walls(orderbook, current_price)
        
        # 3. Агрессивные покупки/продажи (tape reading)
        aggression_score, reasons_aggression = self._analyze_aggression(recent_trades)
        
        # 4. Фибоначчи уровни из стакана
        fib_score, reasons_fib = self._analyze_fibonacci_levels(orderbook, current_price)
        
        # 5. Спред и ликвидность (скальперский индикатор)
        spread_score, reasons_spread = self._analyze_spread(orderbook, current_price)
        
        # 6. Momentum (изменение цены vs объем)
        momentum_score, reasons_momentum = self._analyze_momentum(recent_trades)
        
        support_price, resistance_price = self._find_probability_levels(orderbook, current_price)

        strictness = getattr(self, 'strictness_percent', 50.0)
        strictness = max(1.0, min(100.0, strictness))

        sigma = self._estimate_volatility(recent_trades, current_price)
        horizon = self._estimate_horizon(recent_trades)

        sigma *= (1.0 + (strictness - 50.0) / 200.0)
        horizon *= (1.0 - (strictness - 50.0) / 250.0)

        base_prob_up = self._probability_to_level(resistance_price - current_price, sigma, horizon, current_price)
        base_prob_down = self._probability_to_level(current_price - support_price, sigma, horizon, current_price)

        # Lowered liquidity requirements - 40 instead of 55
        if wall_score < 40 or spread_score < 40:
            return self._wait_signal(symbol, "Недостаточно ликвидности")

        bullish_strength = 0
        bearish_strength = 0

        key_conditions = 0
        if wall_score >= 65 and spread_score >= 60:
            key_conditions += 1
        if imbalance_score >= 60:
            key_conditions += 1
        if aggression_score >= 60:
            key_conditions += 1
        if momentum_score >= 60:
            key_conditions += 1

        # Дисбаланс (симметрично: 70% bid = 70% ask по силе)
        if bid_percent >= 0.70:
            bullish_strength += 3
        elif bid_percent >= 0.60:
            bullish_strength += 2
        elif bid_percent >= 0.55:
            bullish_strength += 1
        
        ask_percent = 1 - bid_percent
        if ask_percent >= 0.70:  # Симметрично!
            bearish_strength += 3
        elif ask_percent >= 0.60:
            bearish_strength += 2
        elif ask_percent >= 0.55:
            bearish_strength += 1
        
        # Агрессия (симметрично)
        if aggression_score >= 75:
            bullish_strength += 2
        elif aggression_score >= 60:
            bullish_strength += 1
        
        if aggression_score <= 25:  # Симметрично!
            bearish_strength += 2
        elif aggression_score <= 40:
            bearish_strength += 1
        
        # Momentum (симметрично)
        if momentum_score >= 75:
            bullish_strength += 2
        elif momentum_score >= 60:
            bullish_strength += 1
        
        if momentum_score <= 25:  # Симметрично!
            bearish_strength += 2
        elif momentum_score <= 40:
            bearish_strength += 1
        
        # Стены (симметрично)
        if wall_score >= 65:
            bullish_strength += 1
        
        if wall_score <= 35:  # Симметрично!
            bearish_strength += 1
        
        adjust_long = min(1.2, 0.8 + bullish_strength * 0.05)
        adjust_short = min(1.2, 0.8 + bearish_strength * 0.05)
        prob_up = min(0.99, max(0.0, base_prob_up * adjust_long))
        prob_down = min(0.99, max(0.0, base_prob_down * adjust_short))

        logger.debug(
            f"{symbol}: prob_up={prob_up:.2f}, prob_down={prob_down:.2f}, bull={bullish_strength}, bear={bearish_strength}"
        )

        threshold_long = getattr(self, 'prob_threshold_long', self.min_confidence / 100.0)
        threshold_short = getattr(self, 'prob_threshold_short', self.config['signals'].get('min_confidence_short', 66) / 100.0)

        if prob_up >= threshold_long and prob_up > prob_down and bullish_strength > bearish_strength and key_conditions >= 2:
            direction = 'LONG'
            confidence = prob_up * 100.0
            # Bonus for strong signals
            if bullish_strength >= 5:
                confidence += 3.0
            if key_conditions >= 3:
                confidence += 2.0
        elif prob_down >= threshold_short and prob_down > prob_up and bearish_strength > bullish_strength and key_conditions >= 2:
            direction = 'SHORT'
            confidence = prob_down * 100.0
            # Bonus for strong signals
            if bearish_strength >= 5:
                confidence += 3.0
            if key_conditions >= 3:
                confidence += 2.0
        else:
            return self._wait_signal(symbol, f"P(up)={prob_up:.2f}, P(down)={prob_down:.2f}")

        confidence = min(confidence, 99.0)
        
        # Устанавливаем expected_value = 0 (для обратной совместимости с логированием)
        expected_value = 0.0
        
        # Собираем все причины
        all_reasons = reasons_imbalance + reasons_walls + reasons_aggression + reasons_fib + reasons_spread + reasons_momentum
        all_reasons.append(f"Support={support_price:.4f}, Resistance={resistance_price:.4f}")
        all_reasons.append(f"P↑={prob_up:.2f}, P↓={prob_down:.2f}")
        
        # Если WAIT - возвращаем сразу
        if direction == 'WAIT':
            return self._wait_signal(symbol, f"Уверенность {confidence:.1f}%")
        
        # --- РАСЧЕТ УРОВНЕЙ (риск-менеджмент) ---
        
        # РИСК-МЕНЕДЖМЕНТ:
        # Стоп-лосс и тейк-профит задаются из конфигурации (например 0.8% и 1:2.5)
        stop_distance_percent = self.config['risk']['stop_loss_percent']
        take_profit_percent = stop_distance_percent * self.config['risk']['take_profit_multiplier']
        
        if direction == 'LONG':
            entry_price = best_ask  # Входим по Ask
            stop_loss = entry_price * (1 - stop_distance_percent / 100)  # -0.5%
            take_profit_1 = entry_price * (1 + (stop_distance_percent * self.config['risk']['take_profit_multiplier']) / 100)  # +1.0%
            take_profit_2 = entry_price * (1 + (stop_distance_percent * self.config['risk']['take_profit_multiplier'] * PI) / 100)  # PI
        else:  # SHORT
            entry_price = best_bid  # Входим по Bid
            stop_loss = entry_price * (1 + stop_distance_percent / 100)  # +0.5%
            take_profit_1 = entry_price * (1 - (stop_distance_percent * self.config['risk']['take_profit_multiplier']) / 100)  # -1.0%
            take_profit_2 = entry_price * (1 - (stop_distance_percent * self.config['risk']['take_profit_multiplier'] * PI) / 100)  # PI
        
        # Risk/Reward ratio
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit_1 - entry_price)
        risk_reward = reward / risk if risk > 0 else 0
        
        # ФИЛЬТР: Cooldown - проверяем что прошло достаточно времени после последнего сигнала
        if not self._check_cooldown(symbol):
            elapsed = (datetime.now() - self.last_signal_time[symbol]).total_seconds()
            return self._wait_signal(symbol, f"Cooldown ({self.cooldown_seconds - elapsed:.0f}s осталось)")
        
        # Обновляем время последнего сигнала
        self.last_signal_time[symbol] = datetime.now()
        
        signal = TradingSignal(
            symbol=symbol,
            direction=direction,
            confidence=min(confidence, 99.9),  # Максимум 99.9%
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            risk_reward=risk_reward,
            reasons=all_reasons,
            timestamp=datetime.now()
        )
        
        # Сохраняем факторы в сигнале для последующего обновления производительности
        signal.wall_score = wall_score
        signal.spread_score = spread_score
        signal.imbalance_score = imbalance_score
        signal.aggression_score = aggression_score
        signal.momentum_score = momentum_score
        signal.fib_score = fib_score
        signal.expected_value = expected_value
        
        # Всегда логируем торговые сигналы на уровне INFO
        logger.info(f"🎯 {symbol}: {direction} сигнал ({confidence:.1f}%, EV=${expected_value:.2f}, wall={wall_score:.1f}, spread={spread_score:.1f}, imbalance={imbalance_score:.1f})")
        
        return signal
    
    def _analyze_imbalance(self, orderbook: Dict) -> Tuple[float, float, List[str]]:
        """
        Анализ дисбаланса bid/ask (Парето 80/20)
        Сбалансированный для LONG и SHORT
        
        Returns:
            (score 0-100, bid_percent, reasons)
        """
        # Используем Фибоначчи уровни глубины: 10 и 21 уровень
        bids_near = orderbook['bids'][:10]  # Ближние (Фибо 10)
        asks_near = orderbook['asks'][:10]
        bids_far = orderbook['bids'][:21]  # Дальние (Фибо 21)
        asks_far = orderbook['asks'][:21]
        
        # Анализ ближнего стакана
        bid_volume_near = sum(qty for price, qty in bids_near)
        ask_volume_near = sum(qty for price, qty in asks_near)
        total_near = bid_volume_near + ask_volume_near
        
        # Анализ глубокого стакана (Фибоначчи)
        bid_volume_far = sum(qty for price, qty in bids_far) if len(bids_far) > 10 else bid_volume_near
        ask_volume_far = sum(qty for price, qty in asks_far) if len(asks_far) > 10 else ask_volume_near
        total_far = bid_volume_far + ask_volume_far
        
        if total_near == 0:
            return 50, 0.5, ["Нет объемов"]
        
        bid_percent = bid_volume_near / total_near
        ask_percent = ask_volume_near / total_near
        
        # Глубокий дисбаланс (для подтверждения)
        bid_percent_far = bid_volume_far / total_far if total_far > 0 else 0.5
        
        reasons = []
        score = 50  # Нейтрально по умолчанию
        
        # Принцип Парето: 80/20 - СБАЛАНСИРОВАННО для LONG и SHORT
        if bid_percent >= 0.80:  # 80% покупателей (Парето)
            score = 100
            reasons.append(f"🔥 Сильный BID {bid_percent*100:.0f}% (Парето 80/20)")
        elif bid_percent >= 0.70:  # 70% покупателей
            score = 80
            reasons.append(f"📈 Дисбаланс BID {bid_percent*100:.0f}%")
        elif bid_percent >= 0.62:  # 62% (золотое сечение)
            score = 65
            reasons.append(f"📊 BID {bid_percent*100:.0f}% (Фибо 0.618)")
        elif ask_percent >= 0.80:  # 80% продавцов (Парето)
            score = 0  # Сильный SHORT!
            reasons.append(f"🔥 Сильный ASK {ask_percent*100:.0f}% (Парето 80/20)")
        elif ask_percent >= 0.70:  # 70% продавцов
            score = 20  # SHORT
            reasons.append(f"📉 Дисбаланс ASK {ask_percent*100:.0f}%")
        elif ask_percent >= 0.62:  # 62% (золотое сечение)
            score = 35  # SHORT
            reasons.append(f"📊 ASK {ask_percent*100:.0f}% (Фибо 0.618)")
        else:
            score = 50
            reasons.append(f"⚖️ Баланс {bid_percent*100:.0f}/{ask_percent*100:.0f}")
        
        # Бонус если глубокий стакан подтверждает
        if bid_percent >= 0.65 and bid_percent_far >= 0.65:
            score = min(100, score + 10)
            reasons.append(f"✅ Глубина подтверждает")
        
        return score, bid_percent, reasons
    
    def _analyze_walls(self, orderbook: Dict, current_price: float) -> Tuple[float, List[str]]:
        """
        Анализ крупных стен (order walls) - STRATEGY: Wall War
        
        Returns:
            (score 0-100, reasons)
        """
        bids = orderbook['bids']
        asks = orderbook['asks']
        
        # Находим средний объем
        all_orders = bids + asks
        avg_volume = sum(qty for price, qty in all_orders) / len(all_orders) if all_orders else 0
        
        # Wall War Strategy: Крупная стена = объем > среднего × 3
        large_order_min = max(avg_volume * 3, self.large_order_threshold / current_price)
        
        reasons = []
        score = 50  # Нейтрально по умолчанию
        
        # Ищем крупные BID стены (поддержка)
        large_bids = [(p, q) for p, q in bids if q >= large_order_min]
        # Ищем крупные ASK стены (сопротивление)
        large_asks = [(p, q) for p, q in asks if q >= large_order_min]
        
        if large_bids:
            closest_bid = large_bids[0]  # Ближайшая к цене
            support_level = closest_bid[0]
            support_value = closest_bid[1] * support_level
            reasons.append(f"🛡️ Стена BID ${support_level:.2f} (${support_value:.0f})")
            score += 15
        
        if large_asks:
            closest_ask = large_asks[0]
            resistance_level = closest_ask[0]
            resistance_value = closest_ask[1] * resistance_level
            reasons.append(f"🧱 Стена ASK ${resistance_level:.2f} (${resistance_value:.0f})")
            score -= 15
        
        # Если стен больше снизу чем сверху = bullish
        if len(large_bids) > len(large_asks):
            score += 20
            reasons.append(f"✅ Больше поддержки ({len(large_bids)} vs {len(large_asks)})")
        elif len(large_asks) > len(large_bids):
            score -= 20
            reasons.append(f"❌ Больше сопротивления ({len(large_asks)} vs {len(large_bids)})")
        
        return max(0, min(100, score)), reasons
    
    def _analyze_aggression(self, recent_trades: List[Dict]) -> Tuple[float, List[str]]:
        """
        Анализ агрессивных покупок/продаж (tape reading)
        
        Returns:
            (score 0-100, reasons)
        """
        if not recent_trades:
            return 50, ["Нет данных по сделкам"]
        
        # Считаем агрессивные покупки (buy market orders)
        # is_buyer_maker=True означает продажу, False - покупку
        aggressive_buys = [t for t in recent_trades if not t['is_buyer_maker']]
        aggressive_sells = [t for t in recent_trades if t['is_buyer_maker']]
        
        buy_volume = sum(t['quantity'] for t in aggressive_buys)
        sell_volume = sum(t['quantity'] for t in aggressive_sells)
        total = buy_volume + sell_volume
        
        if total == 0:
            return 50, ["Нет агрессивных сделок"]
        
        buy_percent = buy_volume / total
        
        reasons = []
        score = 0
        
        if buy_percent >= 0.75:  # 75% агрессивные покупки
            score = 100
            reasons.append(f"🚀 Агрессивные покупки {len(aggressive_buys)}/{len(recent_trades)}")
        elif buy_percent >= 0.65:
            score = 80
            reasons.append(f"📈 Преобладают покупки {len(aggressive_buys)}/{len(recent_trades)}")
        elif buy_percent >= 0.55:
            score = 60
            reasons.append(f"↗️ Больше покупок {len(aggressive_buys)}/{len(recent_trades)}")
        elif buy_percent <= 0.25:  # 75% агрессивные продажи
            score = 0
            reasons.append(f"💥 Агрессивные продажи {len(aggressive_sells)}/{len(recent_trades)}")
        elif buy_percent <= 0.35:
            score = 20
            reasons.append(f"📉 Преобладают продажи {len(aggressive_sells)}/{len(recent_trades)}")
        elif buy_percent <= 0.45:
            score = 40
            reasons.append(f"↘️ Больше продаж {len(aggressive_sells)}/{len(recent_trades)}")
        else:
            score = 50
            reasons.append(f"⚖️ Равновесие покупок/продаж")
        
        return score, reasons
    
    def _analyze_fibonacci_levels(self, orderbook: Dict, current_price: float) -> Tuple[float, List[str]]:
        """
        Анализ Фибоначчи уровней из стакана
        
        Returns:
            (score 0-100, reasons)
        """
        bids = orderbook['bids']
        asks = orderbook['asks']
        
        # Находим максимальную заявку в стакане
        max_bid = max(bids, key=lambda x: x[1]) if bids else [0, 0]
        max_ask = max(asks, key=lambda x: x[1]) if asks else [0, 0]
        
        max_order = max_bid if max_bid[1] > max_ask[1] else max_ask
        max_price = max_order[0]
        max_volume = max_order[1]
        
        reasons = []
        score = 50
        
        # Рассчитываем Фибоначчи уровни от максимальной заявки
        for fib_level in FIB_LEVELS:
            level_volume = max_volume * fib_level
            
            # Ищем заявки близкие к этому объему
            close_orders = [
                (p, q) for p, q in bids + asks
                if abs(q - level_volume) / max_volume < 0.1  # В пределах 10%
            ]
            
            if close_orders:
                reasons.append(f"📐 Фибо {fib_level} совпадает с уровнем")
                score += 5
        
        # Если текущая цена близка к максимальной заявке
        price_distance = abs(current_price - max_price) / current_price
        if price_distance < 0.005:  # В пределах 0.5%
            reasons.append(f"🎯 Цена рядом с крупной заявкой ${max_price:.2f}")
            score += 15
        
        return max(0, min(100, score)), reasons
    
    def _check_cooldown(self, symbol: str) -> bool:
        """
        Проверка cooldown между сигналами (41 секунда на пару)
        
        Returns:
            True если можно торговать, False если cooldown активен
        """
        if symbol not in self.last_signal_time:
            return True
        
        elapsed = (datetime.now() - self.last_signal_time[symbol]).total_seconds()
        return elapsed >= self.cooldown_seconds
    
    def _analyze_spread(self, orderbook: Dict, current_price: float) -> Tuple[float, List[str]]:
        """
        Анализ спреда и ликвидности - STRATEGY: Spread Tightness
        Оценивает качество спреда (≤0.02% - отлично, >0.1% - пропуск)
        
        Returns:
            (score 0-100, reasons)
        """
        if not orderbook['bids'] or not orderbook['asks']:
            return 50, ["Нет данных"]
        
        best_bid = orderbook['bids'][0][0]
        best_ask = orderbook['asks'][0][0]
        spread = best_ask - best_bid
        spread_percent = (spread / current_price) * 100
        
        reasons = []
        
        # Spread Tightness Strategy: Узкий спред = хороший сигнал
        # ≤0.02% - отлично (максимальный score)
        if spread_percent <= 0.02:
            score = 100
            reasons.append(f"✅ Отличный спред {spread_percent:.3f}% ≤0.02%")
        elif spread_percent <= 0.03:
            score = 80
            reasons.append(f"✅ Хороший спред {spread_percent:.3f}%")
        elif spread_percent <= 0.05:
            score = 60
            reasons.append(f"⚖️ Средний спред {spread_percent:.3f}%")
        elif spread_percent <= 0.1:
            score = 40
            reasons.append(f"⚠️ Широкий спред {spread_percent:.3f}%")
        else:
            # >0.1% - должно быть отфильтровано выше, но на всякий случай
            score = 0
            reasons.append(f"❌ Очень широкий спред {spread_percent:.3f}%")
        
        return score, reasons
    
    def _analyze_momentum(self, recent_trades: List[Dict]) -> Tuple[float, List[str]]:
        """
        Анализ momentum - скорость и направление движения
        Использует последние 21 сделку для анализа импульса
        
        Returns:
            (score 0-100, reasons)
        """
        # ФИЛЬТР: Минимум 5 сделок для анализа
        if len(recent_trades) < 5:
            return 50, ["Недостаточно данных (минимум 5 сделок)"]
        
        # Используем последние 21 сделку (или все доступные если меньше)
        last_21 = recent_trades[-21:] if len(recent_trades) >= 21 else recent_trades
        
        # Рассчитываем weighted momentum (недавние сделки важнее)
        total_buy_volume = 0
        total_sell_volume = 0
        
        for i, trade in enumerate(last_21):
            # Вес по Фибоначчи - недавние сделки весят больше
            weight = (i + 1) / len(last_21)  # От 0.05 до 1.0
            
            volume = trade['quantity'] * weight
            
            if not trade['is_buyer_maker']:  # Покупка
                total_buy_volume += volume
            else:  # Продажа
                total_sell_volume += volume
        
        total = total_buy_volume + total_sell_volume
        if total == 0:
            return 50, ["Нет объема"]
        
        buy_percent = total_buy_volume / total
        
        reasons = []
        
        if buy_percent >= 0.80:  # 80% (Парето)
            score = 100
            reasons.append(f"🚀 Сильный momentum UP {buy_percent*100:.0f}%")
        elif buy_percent >= 0.70:
            score = 85
            reasons.append(f"📈 Momentum UP {buy_percent*100:.0f}%")
        elif buy_percent >= 0.62:  # Золотое сечение
            score = 70
            reasons.append(f"↗️ Слабый momentum UP {buy_percent*100:.0f}%")
        elif buy_percent <= 0.20:  # 80% продажи (Парето)
            score = 0
            reasons.append(f"💥 Сильный momentum DOWN {(1-buy_percent)*100:.0f}%")
        elif buy_percent <= 0.30:
            score = 15
            reasons.append(f"📉 Momentum DOWN {(1-buy_percent)*100:.0f}%")
        elif buy_percent <= 0.38:  # 1 - 0.618
            score = 30
            reasons.append(f"↘️ Слабый momentum DOWN {(1-buy_percent)*100:.0f}%")
        else:
            score = 50
            reasons.append(f"⚖️ Нейтральный momentum")
        
        return score, reasons
    
    def _find_probability_levels(self, orderbook: Dict, current_price: float) -> Tuple[float, float]:
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        support_price = current_price * 0.999
        resistance_price = current_price * 1.001

        if bids:
            max_bid_volume = max(q for _, q in bids)
            candidates = []
            for price, qty in bids[:100]:
                if price > current_price:
                    continue
                ratio = qty / max_bid_volume if max_bid_volume else 0
                for fib in FIB_LEVELS:
                    if abs(ratio - fib) <= 0.08:
                        candidates.append((current_price - price, price))
                        break
            if candidates:
                support_price = min(candidates)[1]
            else:
                support_price = bids[0][0]

        if asks:
            max_ask_volume = max(q for _, q in asks)
            candidates = []
            for price, qty in asks[:100]:
                if price < current_price:
                    continue
                ratio = qty / max_ask_volume if max_ask_volume else 0
                for fib in FIB_LEVELS:
                    if abs(ratio - fib) <= 0.08:
                        candidates.append((price - current_price, price))
                        break
            if candidates:
                resistance_price = min(candidates)[1]
            else:
                resistance_price = asks[0][0]

        support_price = max(support_price, current_price * 0.95)
        resistance_price = min(resistance_price, current_price * 1.05)

        return support_price, resistance_price

    def _estimate_volatility(self, recent_trades: List[Dict], current_price: float) -> float:
        if not recent_trades:
            return current_price * 0.0008

        prices = [t.get('price') for t in recent_trades[-50:] if t.get('price')]
        if len(prices) < 2:
            return current_price * 0.0008

        diffs = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
        if not diffs:
            return current_price * 0.0008

        avg = sum(diffs) / len(diffs)
        variance = sum((d - avg) ** 2 for d in diffs) / len(diffs)
        sigma = math.sqrt(max(variance, 1e-12))

        return max(sigma, current_price * 0.0005)

    def _estimate_horizon(self, recent_trades: List[Dict]) -> float:
        if len(recent_trades) < 2:
            return 30.0
        times = [t.get('time', 0) for t in recent_trades if t.get('time')]
        if len(times) < 2:
            return 30.0
        horizon = (max(times) - min(times)) / 1000.0
        return max(horizon, 30.0)

    def _probability_to_level(self, delta: float, sigma: float, horizon: float, current_price: float) -> float:
        if delta <= 0:
            return 0.5
        denom = max(sigma, current_price * 0.0005) * math.sqrt(max(horizon, 1.0))
        if denom <= 0:
            denom = current_price * 0.0005
        z = delta / denom
        return self._normal_cdf(z)

    def _normal_cdf(self, x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _apply_bayesian_update(self, symbol: str, direction: str, prior_confidence: float) -> float:
        """
        БАЙЕСОВСКОЕ ОБНОВЛЕНИЕ уверенности на основе исторического win rate
        
        Теорема Байеса: P(win|signal) = P(signal|win) × P(win) / P(signal)
        
        Args:
            symbol: Торговая пара
            direction: Направление (LONG/SHORT)
            prior_confidence: Априорная уверенность (0-100)
            
        Returns:
            Обновленная уверенность (0-100), или 0 если нет данных
        """
        if not self.learning_system:
            return 0.0
        
        # Получаем статистику для этой пары + направления
        stats = self.learning_system.stats.get(symbol, {}).get(direction)
        if not stats or stats.total < 10:
            return 0.0  # Недостаточно данных
        
        # Исторический win rate (likelihood)
        historical_win_rate = stats.win_rate / 100.0  # 0-1
        
        # Prior probability (априорная вероятность из уверенности)
        prior_prob = prior_confidence / 100.0  # 0-1
        
        # Bayesian update: P(win|signal) = likelihood × prior
        # Упрощенная формула без нормализации (для ускорения)
        posterior_prob = historical_win_rate * prior_prob
        
        # Если исторический WR низкий - снижаем уверенность
        if historical_win_rate < 0.40:  # WR < 40%
            posterior_prob *= 0.7  # Снижаем на 30%
        
        # Конвертируем обратно в проценты
        posterior_confidence = posterior_prob * 100.0
        
        return max(0.0, min(95.0, posterior_confidence))
    
    def _calculate_expected_value(self, symbol: str, direction: str, confidence: float) -> float:
        """
        EXPECTED VALUE (EV) расчет: математическое ожидание прибыли
        
        EV = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
        
        Args:
            symbol: Торговая пара
            direction: Направление (LONG/SHORT)
            confidence: Уверенность сигнала
            
        Returns:
            Expected Value в долларах, или 0 если нет данных
        """
        if not self.learning_system:
            return 0.0
        
        # Получаем статистику
        stats = self.learning_system.stats.get(symbol, {}).get(direction)
        if not stats or stats.total < 10:
            # Если нет данных - используем оптимистичный EV на основе уверенности
            # При уверенности 70% предполагаем WR 50% и R:R 1:2
            estimated_win_rate = 0.50
            estimated_avg_win = 2.50  # $2.50 при R:R 1:2
            estimated_avg_loss = 1.25  # $1.25 (риск 0.5%)
            ev = (estimated_win_rate * estimated_avg_win) - ((1 - estimated_win_rate) * estimated_avg_loss)
            return ev
        
        # Реальный EV на основе исторических данных
        win_rate = stats.win_rate / 100.0
        
        # Вычисляем avg_win и avg_loss из последних сделок
        recent_trades = list(stats.recent_trades) if stats.recent_trades else []
        winners = [t for t in recent_trades if t['pnl'] > 0]
        losers = [t for t in recent_trades if t['pnl'] <= 0]
        
        avg_win = sum(t['pnl'] for t in winners) / len(winners) if winners else 2.50
        avg_loss = abs(sum(t['pnl'] for t in losers) / len(losers)) if losers else 1.25
        
        # EV = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
        ev = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        return ev
    
    def update_factor_performance(self, factors: Dict[str, float], trade_result: bool):
        """
        Обновить производительность факторов после закрытия сделки
        
        Args:
            factors: Словарь с оценками факторов {'wall': 75, 'spread': 80, ...}
            trade_result: True если сделка прибыльная, False если убыточная
        """
        for factor_name, score in factors.items():
            if factor_name in self.factor_performance:
                self.factor_performance[factor_name]['total'] += 1
                if trade_result:
                    self.factor_performance[factor_name]['wins'] += 1
        
        # Адаптируем веса факторов каждые 20 сделок
        total_trades = sum(perf['total'] for perf in self.factor_performance.values())
        if total_trades >= 20 and total_trades % 20 == 0:
            self._adapt_factor_weights()
    
    def _adapt_factor_weights(self):
        """
        АДАПТИВНЫЕ ВЕСА: динамически меняем веса факторов на основе их производительности
        
        Факторы с высоким win rate получают больший вес
        Факторы с низким win rate получают меньший вес
        """
        # Вычисляем win rate для каждого фактора
        factor_win_rates = {}
        for factor_name, perf in self.factor_performance.items():
            if perf['total'] >= 5:  # Минимум 5 сделок для оценки
                factor_win_rates[factor_name] = perf['wins'] / perf['total']
            else:
                factor_win_rates[factor_name] = 0.5  # Нейтральный WR 50%
        
        if not factor_win_rates:
            return
        
        # Нормализуем win rates (относительно среднего)
        avg_win_rate = sum(factor_win_rates.values()) / len(factor_win_rates)
        
        # Вычисляем новые веса на основе относительной производительности
        total_weight = 0
        new_weights = {}
        
        for factor_name, win_rate in factor_win_rates.items():
            # Относительная производительность (1.0 = средняя)
            relative_performance = win_rate / avg_win_rate if avg_win_rate > 0 else 1.0
            
            # Новый вес = базовый вес × относительная производительность
            base_weight = {
                'wall': 0.35,
                'spread': 0.25,
                'imbalance': 0.20,
                'aggression': 0.10,
                'momentum': 0.05,
                'fib': 0.05
            }[factor_name]
            
            new_weights[factor_name] = base_weight * relative_performance
            total_weight += new_weights[factor_name]
        
        # Нормализуем веса чтобы сумма была 1.0
        if total_weight > 0:
            for factor_name in new_weights:
                new_weights[factor_name] /= total_weight
                self.factor_weights[factor_name] = new_weights[factor_name]
            
            logger.info(f"🔄 Адаптированы веса факторов: {self.factor_weights}")
    
    def _wait_signal(self, symbol: str, reason: str) -> TradingSignal:
        """Создать WAIT сигнал"""
        return TradingSignal(
            symbol=symbol,
            direction='WAIT',
            confidence=0,
            entry_price=0,
            stop_loss=0,
            take_profit_1=0,
            take_profit_2=0,
            risk_reward=0,
            reasons=[reason],
            timestamp=datetime.now()
        )
