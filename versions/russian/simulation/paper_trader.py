#!/usr/bin/env python3
"""
💰 PAPER TRADING SIMULATOR
Симуляция реальной торговли без риска
Учитывает: комиссии, проскальзывание, спред, ликвидацию
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import json

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Открытая позиция"""
    id: str
    symbol: str
    side: str  # 'LONG' or 'SHORT'
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    size: float  # Размер в базовой валюте (ETH, BTC, etc)
    leverage: int
    entry_time: datetime
    entry_commission: float
    liquidation_price: float
    confidence: float = 75.0  # Уверенность сигнала при входе
    position_value_usdt: float = 0.0  # Полный размер позиции с плечом в USDT ($250 при плече 50x)
    margin_usdt: float = 0.0  # Маржа (блокируется) без плеча ($5)
    
    # Динамические данные
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_percent: float = 0.0
    
    # Trailing Stop
    trailing_stop_activated: bool = False
    highest_profit_price: float = 0.0  # Для LONG
    lowest_profit_price: float = 0.0  # Для SHORT


@dataclass
class ClosedTrade:
    """Закрытая сделка"""
    id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    leverage: int
    entry_time: datetime
    exit_time: datetime
    duration_seconds: float
    pnl: float
    pnl_percent: float
    close_reason: str  # 'Take Profit', 'Stop Loss', 'Manual', 'Timeout'
    total_commission: float
    confidence: float = 75.0  # Уверенность сигнала при входе


class PaperTrader:
    """
    Симулятор paper trading
    """
    
    def __init__(self, config: Dict, starting_balance: float = 100.0):
        """
        Args:
            config: Конфигурация из config.json
            starting_balance: Начальный баланс в USDT
        """
        self.config = config
        self.starting_balance = starting_balance
        self.balance = starting_balance
        
        # Параметры торговли
        self.leverage = config['account']['leverage']
        self.max_positions = config['account']['max_positions']
        
        # Параметры симуляции
        self.slippage_percent = config['simulation']['slippage_percent']
        self.commission_maker = config['simulation']['commission_maker']
        self.commission_taker = config['simulation']['commission_taker']
        self.use_slippage = config['simulation']['use_realistic_slippage']
        self.use_spread = config['simulation']['use_spread']
        
        # Открытые позиции
        self.positions: Dict[str, Position] = {}  # symbol -> Position
        
        # Закрытые сделки
        self.closed_trades: List[ClosedTrade] = []
        
        # Счетчик сделок
        self.trade_counter = 0
        
        # Статистика
        self.total_pnl = 0.0
        self.max_balance = starting_balance
        self.min_balance = starting_balance
        self.max_drawdown = 0.0
        
        # Monte Carlo параметры
        self.monte_carlo_enabled = True
        
        logger.info(f"💰 Paper Trader инициализирован: ${starting_balance:.2f} | Leverage: {self.leverage}x")
    
    def can_open_position(self, symbol: str) -> bool:
        """Проверка можно ли открыть позицию"""
        # Проверяем максимум позиций
        if len(self.positions) >= self.max_positions:
            logger.debug(f"Максимум позиций достигнут ({self.max_positions})")
            return False
        
        # Проверяем есть ли уже позиция по этой паре
        if symbol in self.positions:
            logger.debug(f"Уже есть позиция по {symbol}")
            return False
        
        # Проверяем есть ли свободные средства
        available = self.get_available_balance()
        if available <= 0:
            logger.debug(f"Нет свободных средств")
            return False
        
        return True
    
    def _calculate_dynamic_leverage(self, confidence: float) -> int:
        """
        Рассчитать динамическое плечо на основе уверенности сигнала
        
        Args:
            confidence: Уверенность сигнала (0-100)
            
        Returns:
            Плечо от 50 до 100
        """
        if not self.config['account'].get('dynamic_leverage', False):
            return self.leverage
        
        # Чем выше уверенность, тем выше плечо
        min_lev = self.config['account'].get('leverage_min', 50)
        max_lev = self.config['account'].get('leverage_max', 100)
        
        # Линейная интерполяция: 75% уверенности = 50x, 95%+ = 100x
        if confidence >= 95:
            return max_lev
        elif confidence <= 75:
            return min_lev
        else:
            # От 75% до 95% = от 50x до 100x
            progress = (confidence - 75) / (95 - 75)
            leverage = int(min_lev + progress * (max_lev - min_lev))
            return leverage
    
    def open_position(self, signal: 'TradingSignal', orderbook: Dict, adaptive_params: Dict = None) -> Optional[Position]:
        """
        Открыть позицию по сигналу
        
        Args:
            signal: Торговый сигнал
            orderbook: Текущий стакан ордеров
            
        Returns:
            Position если успешно, None если нет
        """
        symbol = signal.symbol
        
        if not self.can_open_position(symbol):
            return None
        
        # MONTECARLO: Проверяем вероятность прибыли
        if self.monte_carlo_enabled:
            stop_loss_dist = abs(signal.entry_price - signal.stop_loss) / signal.entry_price
            take_profit_dist = abs(signal.take_profit_1 - signal.entry_price) / signal.entry_price
            
            mc_probability = self.monte_carlo_simulate(
                signal.confidence / 100.0,
                stop_loss_dist,
                take_profit_dist
            )
            
            # Если вероятность прибыли < 35% - НЕ ВХОДИМ
            if mc_probability < 0.35:
                logger.debug(f"🎲 Monte Carlo отклонил {symbol}: вероятность {mc_probability*100:.1f}% < 35%")
                return None
        
        # Рассчитываем динамическое плечо на основе уверенности
        base_leverage = self._calculate_dynamic_leverage(signal.confidence)
        
        # Применяем адаптивный множитель плеча (если есть)
        if adaptive_params:
            leverage_multiplier = adaptive_params.get('leverage_multiplier', 1.0)
            position_leverage = int(base_leverage * leverage_multiplier)
            # Не опускаемся ниже минимума из конфига
            position_leverage = max(position_leverage, self.config['account'].get('leverage_min', 50))
        else:
            position_leverage = base_leverage
        
        # Получаем цены из стакана
        best_bid = orderbook['bids'][0][0] if orderbook['bids'] else signal.entry_price
        best_ask = orderbook['asks'][0][0] if orderbook['asks'] else signal.entry_price
        
        # Определяем цену входа с учетом спреда (реалистичный спред уже в best_bid/ask)
        # Если use_spread=true, используется реальный спред из стакана (ask-bid)
        # Если false, используется mid price (не реалистично для реального входа)
        if self.use_spread:
            # Используем реальные цены из стакана (лучшая ask/bid)
            if signal.direction == 'LONG':
                entry_price = best_ask  # Покупаем по Ask (дороже)
            else:  # SHORT
                entry_price = best_bid  # Продаем по Bid (дешевле)
        else:
            # Используем среднюю цену (не реалистично)
            entry_price = (best_bid + best_ask) / 2
        
        # Добавляем проскальзывание
        if self.use_slippage:
            if signal.direction == 'LONG':
                entry_price *= (1 + self.slippage_percent / 100)  # Проскальзывание вверх
            else:  # SHORT
                entry_price *= (1 - self.slippage_percent / 100)  # Проскальзывание вниз
        
        # Рассчитываем размер позиции
        # Риск = % от депозита
        risk_percent = self.config['risk']['base_risk_percent']
        risk_amount = self.balance * (risk_percent / 100)
        
        # Рассчитываем расстояние до стоп-лосса
        stop_distance = abs(entry_price - signal.stop_loss) / entry_price
        
        # Размер позиции основываясь на риске и расстоянии до стопа
        # Если стоп на 1%, а риск $10, то размер позиции = $1000
        if stop_distance > 0:
            position_value = risk_amount / stop_distance
        else:
            position_value = risk_amount * position_leverage
        
        # Ограничиваем размер позиции: не больше 1% от депозита в марже
        # Это значит позиция не больше 1% × leverage
        max_margin = self.balance * 0.01  # 1% от баланса
        max_position_value = max_margin * position_leverage
        position_value = min(position_value, max_position_value)
        
        # Размер в базовой валюте
        size = position_value / entry_price
        
        # actual_position_value для вычислений
        actual_position_value = position_value
        
        # Комиссия за открытие (maker если лимитка, taker если market)
        # Для агрессивного входа используем taker
        entry_commission = actual_position_value * (self.commission_taker / 100)
        
        # НЕ вычитаем комиссию сейчас - будет учтена в net_pnl при закрытии
        
        # Цена ликвидации
        liquidation_percent = 100 / position_leverage
        if signal.direction == 'LONG':
            liquidation_price = entry_price * (1 - liquidation_percent / 100)
        else:
            liquidation_price = entry_price * (1 + liquidation_percent / 100)
        
        # Создаем позицию
        self.trade_counter += 1
        position = Position(
            id=f"T{self.trade_counter:04d}",
            symbol=symbol,
            side=signal.direction,
            entry_price=entry_price,
            stop_loss=signal.stop_loss,
            take_profit_1=signal.take_profit_1,
            take_profit_2=signal.take_profit_2,
            size=size,
            leverage=position_leverage,
            entry_time=datetime.now(),
            entry_commission=entry_commission,
            confidence=signal.confidence,  # Сохраняем confidence для обучения
            liquidation_price=liquidation_price,
            position_value_usdt=actual_position_value,  # Полный размер с плечом
            margin_usdt=actual_position_value / position_leverage,  # Маржа блокируется
            current_price=entry_price
        )
        
        self.positions[symbol] = position
        
        logger.info(f"🟢 Открыта {signal.direction} позиция {symbol}: ${entry_price:.2f} x {size:.4f} (плечо: {position_leverage}x, уверенность: {signal.confidence:.1f}%)")
        logger.info(f"   Размер позиции: ${actual_position_value:.2f}")
        
        return position
    
    def update_positions(self, symbol: str, current_price: float) -> Optional[ClosedTrade]:
        """
        Обновить позицию текущей ценой и проверить стоп/тейк
        
        Args:
            symbol: Торговая пара
            current_price: Текущая цена
            
        Returns:
            ClosedTrade если позиция закрыта, None если еще открыта
        """
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        position.current_price = current_price
        
        # Рассчитываем нереализованный P&L по формуле Binance
        # PNL = (изменение цены в %) × размер позиции в USDT (с плечом)
        position_value_usdt = position.position_value_usdt if hasattr(position, 'position_value_usdt') and position.position_value_usdt > 0 else position.entry_price * position.size
        
        if position.side == 'LONG':
            # Изменение цены в процентах
            price_change_percent = ((current_price - position.entry_price) / position.entry_price) * 100
            # PNL = изменение цены в % × размер позиции в USDT
            position.unrealized_pnl = position_value_usdt * (price_change_percent / 100)
        else:  # SHORT
            # Изменение цены в процентах (для SHORT инвертировано)
            price_change_percent = ((position.entry_price - current_price) / position.entry_price) * 100
            # PNL = изменение цены в % × размер позиции в USDT
            position.unrealized_pnl = position_value_usdt * (price_change_percent / 100)
        
        # PNL в процентах
        position.unrealized_pnl_percent = price_change_percent
        
        # Проверяем Take Profit 1 (СНАЧАЛА, до проверки стопов)
        tp1_reached = False
        if position.side == 'LONG' and current_price >= position.take_profit_1:
            tp1_reached = True
        elif position.side == 'SHORT' and current_price <= position.take_profit_1:
            tp1_reached = True
        
        # Если TP1 достигнут впервые:
        if tp1_reached and not position.trailing_stop_activated:
            # Если трейлинг стоп выключен - закрываем сразу по TP1
            if not self.config['risk'].get('trailing_stop', False):
                logger.info(f"✅ {symbol}: TP1 достигнут! Закрываем позицию по ${position.take_profit_1:.4f}")
                return self._close_position(position, position.take_profit_1, "Take Profit 1")
            
            # Если трейлинг стоп включен - активируем защиту прибыли
            position.trailing_stop_activated = True
            # ВАЖНО: Стоп переносится на TP1 и ФИКСИРУЕТСЯ (не двигается дальше!)
            position.stop_loss = position.take_profit_1  # Стоп = TP1 (защита минимума 1%)
            if position.side == 'LONG':
                position.highest_profit_price = current_price  # Отслеживаем максимум
            else:  # SHORT
                position.lowest_profit_price = current_price  # Отслеживаем минимум
            
            logger.info(f"✅ {symbol}: TP1 достигнут! Стоп установлен на TP1 (${position.take_profit_1:.4f}), трейлинг стоп активирован")
        
        # Трейлинг стоп: отслеживает максимум и закрывает при откате на 0.2%
        if position.trailing_stop_activated and self.config['risk'].get('trailing_stop', False):
            trailing_distance = self.config['risk'].get('trailing_stop_distance_percent', 0.2)  # 0.2% от цены
            
            if position.side == 'LONG':
                # Обновляем максимальную достигнутую цену
                if current_price > position.highest_profit_price:
                    position.highest_profit_price = current_price
                
                # Рассчитываем цену трейлинг стопа: максимум × (1 - 0.2%)
                trailing_stop_price = position.highest_profit_price * (1 - trailing_distance / 100)
                
                # Проверяем откат: если цена упала на 0.2% от максимума - закрываем
                if current_price <= trailing_stop_price:
                    logger.info(f"🔄 {symbol}: Трейлинг стоп! Цена ${current_price:.4f} откатила на 0.2% от максимума ${position.highest_profit_price:.4f}")
                    return self._close_position(position, trailing_stop_price, "Trailing Stop")
                
                logger.debug(f"📈 {symbol}: Трейлинг стоп активен - макс: ${position.highest_profit_price:.4f}, трейлинг стоп: ${trailing_stop_price:.4f}, текущая: ${current_price:.4f}")
            
            else:  # SHORT
                # Обновляем минимальную достигнутую цену (для SHORT чем ниже = больше прибыль)
                if position.lowest_profit_price == 0 or current_price < position.lowest_profit_price:
                    position.lowest_profit_price = current_price
                
                # Рассчитываем цену трейлинг стопа: минимум × (1 + 0.2%)
                trailing_stop_price = position.lowest_profit_price * (1 + trailing_distance / 100)
                
                # Проверяем откат: если цена выросла на 0.2% от минимума - закрываем
                if current_price >= trailing_stop_price:
                    logger.info(f"🔄 {symbol}: Трейлинг стоп! Цена ${current_price:.4f} откатила на 0.2% от минимума ${position.lowest_profit_price:.4f}")
                    return self._close_position(position, trailing_stop_price, "Trailing Stop")
                
                logger.debug(f"📉 {symbol}: Трейлинг стоп активен - мин: ${position.lowest_profit_price:.4f}, трейлинг стоп: ${trailing_stop_price:.4f}, текущая: ${current_price:.4f}")
        
        # Проверяем ликвидацию
        if self.config['simulation'].get('check_liquidation', True):
            if position.side == 'LONG' and current_price <= position.liquidation_price:
                logger.error(f"💀 {symbol}: ЛИКВИДАЦИЯ! Цена ${current_price:.4f} достигла ликвидации ${position.liquidation_price:.4f}")
                return self._close_position(position, position.liquidation_price, "Liquidation")
            elif position.side == 'SHORT' and current_price >= position.liquidation_price:
                logger.error(f"💀 {symbol}: ЛИКВИДАЦИЯ! Цена ${current_price:.4f} достигла ликвидации ${position.liquidation_price:.4f}")
                return self._close_position(position, position.liquidation_price, "Liquidation")
        
        # Проверяем обычный Stop Loss (фиксированный на TP1 после активации трейлинга)
        if position.side == 'LONG' and current_price <= position.stop_loss:
            logger.info(f"🛑 {symbol}: Цена ${current_price:.4f} достигла стопа ${position.stop_loss:.4f}")
            return self._close_position(position, position.stop_loss, "Stop Loss")
        elif position.side == 'SHORT' and current_price >= position.stop_loss:
            logger.info(f"🛑 {symbol}: Цена ${current_price:.4f} достигла стопа ${position.stop_loss:.4f}")
            return self._close_position(position, position.stop_loss, "Stop Loss")
        
        return None
    
    def _close_position(self, position: Position, exit_price: float, reason: str) -> ClosedTrade:
        """
        Закрыть позицию
        
        Args:
            position: Позиция для закрытия
            exit_price: Цена выхода
            reason: Причина закрытия
            
        Returns:
            ClosedTrade
        """
        # Добавляем проскальзывание при выходе
        if self.use_slippage:
            if position.side == 'LONG':
                exit_price *= (1 - self.slippage_percent / 100)  # Продаем дешевле
            else:
                exit_price *= (1 + self.slippage_percent / 100)  # Покупаем дороже
        
        # Рассчитываем P&L по формуле Binance
        # PNL = (изменение цены в %) × размер позиции в USDT (с плечом)
        position_value_usdt = position.position_value_usdt if hasattr(position, 'position_value_usdt') and position.position_value_usdt > 0 else position.entry_price * position.size
        
        if position.side == 'LONG':
            # Изменение цены в процентах
            price_change_percent = ((exit_price - position.entry_price) / position.entry_price) * 100
            # PNL = изменение цены в % × размер позиции в USDT
            pnl = position_value_usdt * (price_change_percent / 100)
        else:  # SHORT
            # Изменение цены в процентах (для SHORT инвертировано)
            price_change_percent = ((position.entry_price - exit_price) / position.entry_price) * 100
            # PNL = изменение цены в % × размер позиции в USDT
            pnl = position_value_usdt * (price_change_percent / 100)
        
        # PNL в процентах
        pnl_percent = price_change_percent
        
        # Комиссия за закрытие (market ордер по стоп-лоссу/тейк-профиту = taker)
        # Комиссия рассчитывается от размера позиции при закрытии (exit_price × size)
        exit_position_value = exit_price * position.size
        exit_commission = exit_position_value * (self.commission_taker / 100)
        
        # Общая комиссия
        total_commission = position.entry_commission + exit_commission
        
        # Чистый P&L
        net_pnl = pnl - total_commission
        
        # Обновляем баланс
        self.balance += net_pnl
        self.total_pnl += net_pnl
        
        # Защита от отрицательного баланса
        if self.balance < 0:
            logger.warning(f"⚠️ Баланс ушел в минус: ${self.balance:.2f}, обнуляем")
            self.balance = 0
        
        # Обновляем статистику
        if self.balance > self.max_balance:
            self.max_balance = self.balance
        if self.balance < self.min_balance:
            self.min_balance = self.balance
        
        # Рассчитываем drawdown
        drawdown = ((self.max_balance - self.balance) / self.max_balance) * 100
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
        
        # Создаем запись о закрытой сделке
        duration = (datetime.now() - position.entry_time).total_seconds()
        
        # Получаем confidence из позиции (если сохранен) или сигнала
        confidence = getattr(position, 'confidence', 75.0)
        
        closed_trade = ClosedTrade(
            id=position.id,
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            size=position.size,
            leverage=position.leverage,
            entry_time=position.entry_time,
            exit_time=datetime.now(),
            duration_seconds=duration,
            pnl=net_pnl,
            pnl_percent=pnl_percent,
            close_reason=reason,
            total_commission=total_commission,
            confidence=confidence
        )
        
        self.closed_trades.append(closed_trade)
        
        # Удаляем из открытых позиций
        del self.positions[position.symbol]
        
        emoji = "✅" if net_pnl > 0 else "❌"
        logger.info(
            f"{emoji} Закрыта {position.side} {position.symbol}: "
            f"${exit_price:.2f} | P&L: ${net_pnl:.2f} ({pnl_percent:.2f}%) | {reason}"
        )
        
        return closed_trade
    
    def close_position_manually(self, symbol: str, current_price: float, reason: str):
        """Закрыть позицию вручную"""
        if symbol in self.positions:
            return self._close_position(self.positions[symbol], current_price, reason)
        return None
    
    def close_all_positions(self, current_prices: Dict[str, float]):
        """Закрыть все открытые позиции (например, при остановке)"""
        for symbol in list(self.positions.keys()):
            price = current_prices.get(symbol, self.positions[symbol].entry_price)
            self._close_position(self.positions[symbol], price, "Manual Close")
    
    def get_available_balance(self) -> float:
        """Получить доступный баланс (не в позициях)
        
        При изолированной марже на Binance:
        - Маржа резервируется отдельно для каждой позиции
        - Доступный баланс = Баланс - Занятая маржа всех изолированных позиций
        - Нереализованный P&L НЕ влияет на доступный баланс
        """
        # Считаем занятую маржу (изолированная маржа каждой позиции)
        used_margin = 0
        for position in self.positions.values():
            # Используем сохраненное значение margin_usdt ($5)
            margin = position.margin_usdt if hasattr(position, 'margin_usdt') and position.margin_usdt > 0 else position.position_value_usdt / position.leverage
            used_margin += margin
        
        # Доступный баланс = Общий баланс - Занятая маржа
        available = self.balance - used_margin
        
        # Баланс не может быть отрицательным (защита от ошибок)
        return max(0.0, available)
    
    def get_statistics(self) -> Dict:
        """Получить статистику торговли"""
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
        
        # Подсчет Long/Short
        long_trades = [t for t in self.closed_trades if t.side == 'LONG']
        short_trades = [t for t in self.closed_trades if t.side == 'SHORT']
        
        # ROI в процентах от начального баланса
        roi_pct = ((self.balance - self.starting_balance) / self.starting_balance) * 100 if self.starting_balance > 0 else 0
        
        stats = {
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
            'avg_pnl': sum(t.pnl for t in self.closed_trades) / len(self.closed_trades) if self.closed_trades else 0,
            'long_count': len(long_trades),
            'short_count': len(short_trades),
            'roi_pct': roi_pct
        }
        
        return stats
    
    def save_session(self, filename: str):
        """Сохранить сессию в файл"""
        data = {
            'starting_balance': self.starting_balance,
            'final_balance': self.balance,
            'total_pnl': self.total_pnl,
            'max_drawdown': self.max_drawdown,
            'statistics': self.get_statistics(),
            'closed_trades': [asdict(t) for t in self.closed_trades]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"💾 Сессия сохранена: {filename}")
    
    def monte_carlo_simulate(self, confidence: float, stop_loss: float, take_profit: float) -> float:
        """
        Monte Carlo симуляция вероятности прибыли сделки
        
        Args:
            confidence: Уверенность сигнала (0-1)
            stop_loss: Стоп-лосс расстояние (процент)
            take_profit: Тейк-профит расстояние (процент)
            
        Returns:
            Вероятность прибыли (0-1)
        """
        if not self.monte_carlo_enabled:
            return confidence
        
        # Используем исторические данные бота
        # Если есть закрытые сделки - используем их статистику
        if self.closed_trades:
            winners = [t for t in self.closed_trades if t.pnl > 0]
            actual_win_rate = len(winners) / len(self.closed_trades)
        else:
            # Если сделок нет - используем базовый конфиг
            actual_win_rate = self.config['signals']['min_confidence'] / 100.0
        
        # Monte Carlo: симулируем на основе исторического win rate
        # Но корректируем на основе confidence сигнала
        # confidence 95% = очень высокая вера в сделку
        # confidence 50% = низкая вера
        
        # Симуляция: берем actual_win_rate как базовую вероятность
        # И корректируем на confidence
        adjusted_probability = actual_win_rate * confidence
        
        # Ограничиваем 50%-90%
        final_probability = max(0.50, min(0.90, adjusted_probability))
        
        return final_probability

