#!/usr/bin/env python3
"""
🧠 ADAPTIVE LEARNING - Самообучение бота
Статистика по каждой паре + направлению (BTCUSDT LONG/SHORT отдельно)
Скользящее окно последних N сделок
При плохой статистике - снижаем размер позиции и плечо на 10%
"""

import json
import logging
from typing import Dict, List, Optional
from pathlib import Path
from collections import deque
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Путь к файлу со статистикой
LEARNING_DATA_FILE = "learning_data.json"

# Размер скользящего окна (сколько последних сделок учитываем)
SLIDING_WINDOW_SIZE = 50


@dataclass
class TradeStats:
    """Статистика по направлению (LONG или SHORT) для конкретной пары"""
    total: int = 0  # Всего сделок (в скользящем окне)
    winners: int = 0  # Прибыльных
    total_pnl: float = 0.0  # Общий P&L
    total_pnl_percent: float = 0.0  # Общий P&L в процентах
    recent_trades: deque = None  # Последние N сделок (PNL, confidence)
    
    def __post_init__(self):
        if self.recent_trades is None:
            self.recent_trades = deque(maxlen=SLIDING_WINDOW_SIZE)
    
    @property
    def win_rate(self) -> float:
        """Процент прибыльных сделок"""
        if self.total == 0:
            return 0.0
        return (self.winners / self.total) * 100.0
    
    @property
    def avg_pnl(self) -> float:
        """Средний P&L на сделку"""
        if self.total == 0:
            return 0.0
        return self.total_pnl / self.total
    
    def add_trade(self, pnl: float, pnl_percent: float, confidence: float):
        """Добавить сделку в статистику (со скользящим окном)"""
        self.total += 1
        if pnl > 0:
            self.winners += 1
        self.total_pnl += pnl
        self.total_pnl_percent += pnl_percent
        
        # Добавляем в скользящее окно
        self.recent_trades.append({
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'confidence': confidence
        })
        
        # Пересчитываем статистику только по скользящему окну
        self._recalculate_from_window()
    
    def _recalculate_from_window(self):
        """Пересчитать статистику из скользящего окна"""
        if not self.recent_trades:
            self.total = 0
            self.winners = 0
            self.total_pnl = 0.0
            self.total_pnl_percent = 0.0
            return
        
        # Берем только последние N сделок
        window_trades = list(self.recent_trades)
        self.total = len(window_trades)
        self.winners = sum(1 for t in window_trades if t['pnl'] > 0)
        self.total_pnl = sum(t['pnl'] for t in window_trades)
        self.total_pnl_percent = sum(t['pnl_percent'] for t in window_trades)


class AdaptiveLearning:
    """
    Система самообучения с статистикой по каждой паре + направлению
    
    Хранится в JSON файле:
    {
      "BTCUSDT": {
        "LONG": { "total": 45, "winners": 28, ... },
        "SHORT": { "total": 32, "winners": 18, ... }
      },
      "ETHUSDT": { ... }
    }
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.data_file = Path(LEARNING_DATA_FILE)
        
        # Статистика: {symbol: {direction: TradeStats}}
        self.stats: Dict[str, Dict[str, TradeStats]] = {}
        
        # Загружаем сохраненные данные
        self._load_data()
        
        logger.info(f"🧠 Адаптивное обучение: загружено {len(self.stats)} пар")
    
    def _load_data(self):
        """Загрузить статистику из JSON файла"""
        if not self.data_file.exists():
            logger.info("📝 Файл статистики не найден, начинаем с нуля")
            return
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Конвертируем обратно в TradeStats
            for symbol, directions in data.items():
                self.stats[symbol] = {}
                for direction, stats_dict in directions.items():
                    stats = TradeStats()
                    stats.total = stats_dict.get('total', 0)
                    stats.winners = stats_dict.get('winners', 0)
                    stats.total_pnl = stats_dict.get('total_pnl', 0.0)
                    stats.total_pnl_percent = stats_dict.get('total_pnl_percent', 0.0)
                    
                    # Восстанавливаем скользящее окно
                    recent_trades = stats_dict.get('recent_trades', [])
                    stats.recent_trades = deque(recent_trades, maxlen=SLIDING_WINDOW_SIZE)
                    
                    self.stats[symbol][direction] = stats
            
            logger.info(f"✅ Загружено статистики для {len(self.stats)} пар")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки статистики: {e}")
            self.stats = {}
    
    def _save_data(self):
        """Сохранить статистику в JSON файл"""
        try:
            # Конвертируем в JSON-совместимый формат
            data = {}
            for symbol, directions in self.stats.items():
                data[symbol] = {}
                for direction, stats in directions.items():
                    data[symbol][direction] = {
                        'total': stats.total,
                        'winners': stats.winners,
                        'total_pnl': stats.total_pnl,
                        'total_pnl_percent': stats.total_pnl_percent,
                        'recent_trades': list(stats.recent_trades)  # deque -> list
                    }
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"💾 Сохранена статистика для {len(self.stats)} пар")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения статистики: {e}")
    
    def learn_from_trade(self, trade):
        """
        Учиться на закрытой сделке
        
        Args:
            trade: объект ClosedTrade с полями: symbol, direction, pnl, pnl_percent
        """
        try:
            symbol = trade.symbol
            direction = trade.side  # 'LONG' или 'SHORT' (в ClosedTrade используется 'side')
            
            # Инициализируем если нет
            if symbol not in self.stats:
                self.stats[symbol] = {}
            if direction not in self.stats[symbol]:
                self.stats[symbol][direction] = TradeStats()
            
            stats = self.stats[symbol][direction]
            
            # Получаем confidence из trade (если есть) или 75 как дефолт
            confidence = getattr(trade, 'confidence', 75.0)
            
            # Добавляем сделку (автоматически пересчитает скользящее окно)
            stats.add_trade(trade.pnl, trade.pnl_percent, confidence)
            
            # Сохраняем после каждого обновления
            self._save_data()
            
            # Логируем обновление статистики
            logger.info(
                f"📊 {symbol} {direction}: "
                f"WinRate={stats.win_rate:.1f}% ({stats.winners}/{stats.total}), "
                f"AvgP&L=${stats.avg_pnl:.2f}"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка обучения на сделке {trade.symbol}: {e}")
    
    def get_adaptive_params(self, symbol: str = None, direction: str = None) -> Dict:
        """
        Получить адаптированные параметры для конкретной пары + направления
        
        При плохой статистике (win_rate < 50% или avg_pnl < 0):
        - Снижаем размер позиции на 10%
        - Снижаем плечо на 10% (от базового)
        
        Returns:
            {
                'min_confidence': повышенная уверенность (если статистика плохая),
                'position_size_multiplier': множитель размера позиции (1.0 = норма, 0.9 = -10%),
                'leverage_multiplier': множитель плеча (1.0 = норма, 0.9 = -10%)
            }
        """
        base_min_confidence = self.config['signals']['min_confidence']
        base_leverage = self.config['account']['leverage']
        
        # Если нет статистики - возвращаем базовые значения
        if not symbol or not direction:
            return {
                'min_confidence': base_min_confidence,
                'position_size_multiplier': 1.0,
                'leverage_multiplier': 1.0
            }
        
        # Получаем статистику для этой пары + направления
        if symbol not in self.stats or direction not in self.stats[symbol]:
            return {
                'min_confidence': base_min_confidence,
                'position_size_multiplier': 1.0,
                'leverage_multiplier': 1.0
            }
        
        stats = self.stats[symbol][direction]
        
        # Если статистики недостаточно (меньше 10 сделок) - используем базовые
        if stats.total < 10:
            return {
                'min_confidence': base_min_confidence,
                'position_size_multiplier': 1.0,
                'leverage_multiplier': 1.0
            }
        
        # Анализируем статистику согласно стратегии
        win_rate = stats.win_rate
        avg_pnl = stats.avg_pnl
        
        # Определяем: плохая ли статистика?
        # Плохая если: win_rate < 50% ИЛИ avg_pnl < 0
        is_bad_performance = (win_rate < 50.0) or (avg_pnl < 0)
        
        if is_bad_performance:
            # ПЛОХАЯ СТАТИСТИКА: адаптация параметров
            # Уверенность: +10%
            # Размер: ×0.9
            # Плечо: ×0.9
            logger.warning(
                f"⚠️ Плохая статистика {symbol} {direction}: "
                f"WinRate={win_rate:.1f}%, AvgP&L=${avg_pnl:.2f} → "
                f"уверенность +10%, размер ×0.9, плечо ×0.9"
            )
            
            # Повышаем минимальную уверенность (требуем лучшие сигналы)
            adjusted_confidence = base_min_confidence * 1.1  # +10%
            
            return {
                'min_confidence': min(adjusted_confidence, 85.0),  # Максимум 85%
                'position_size_multiplier': 0.9,  # -10% размер позиции
                'leverage_multiplier': 0.9  # -10% плечо
            }
        else:
            # ХОРОШАЯ СТАТИСТИКА: работаем нормально
            return {
                'min_confidence': base_min_confidence,
                'position_size_multiplier': 1.0,
                'leverage_multiplier': 1.0
            }
    
    def should_trade_direction(self, symbol: str, direction: str) -> bool:
        """
        Проверить стоит ли торговать в данном направлении для конкретной пары
        
        Если статистика ОЧЕНЬ плохая (win_rate < 40% и avg_pnl сильно отрицательный):
        - Можем полностью блокировать направление
        
        Пока возвращаем True всегда (не блокируем, только снижаем риск)
        """
        if symbol not in self.stats or direction not in self.stats[symbol]:
            return True  # Нет данных - разрешаем
        
        stats = self.stats[symbol][direction]
        
        # Если меньше 20 сделок - нет достаточно данных для блокировки
        if stats.total < 20:
            return True
        
        # КРИТИЧЕСКАЯ БЛОКИРОВКА согласно стратегии:
        # Направление при WR <35% и avg_pnl <$2
        # Только после 20+ сделок
        if stats.win_rate < 35.0 and stats.avg_pnl < 2.0:
            logger.warning(
                f"🚫 КРИТИЧЕСКИ плохая статистика {symbol} {direction}: "
                f"WinRate={stats.win_rate:.1f}% < 35%, AvgP&L=${stats.avg_pnl:.2f} < $2 → блокируем"
            )
            return False  # Блокируем это направление
        
        return True
    
    def get_learning_summary(self) -> str:
        """Получить сводку по обучению для отображения в GUI"""
        if not self.stats:
            return "🧠 АДАПТИВНОЕ ОБУЧЕНИЕ: Нет данных (ожидание сделок)"
        
        summary_lines = ["🧠 АДАПТИВНОЕ ОБУЧЕНИЕ:"]
        
        # Показываем топ-5 пар с самой плохой и хорошей статистикой
        all_pairs_stats = []
        for symbol, directions in self.stats.items():
            for direction, stats in directions.items():
                if stats.total >= 10:  # Только если есть достаточно данных
                    all_pairs_stats.append({
                        'symbol': symbol,
                        'direction': direction,
                        'win_rate': stats.win_rate,
                        'avg_pnl': stats.avg_pnl,
                        'total': stats.total
                    })
        
        if not all_pairs_stats:
            return "🧠 АДАПТИВНОЕ ОБУЧЕНИЕ: Недостаточно данных (нужно минимум 10 сделок)"
        
        # Сортируем по среднему P&L
        all_pairs_stats.sort(key=lambda x: x['avg_pnl'], reverse=True)
        
        # Топ-3 лучших
        summary_lines.append("\n✅ ЛУЧШИЕ:")
        for item in all_pairs_stats[:3]:
            summary_lines.append(
                f"  {item['symbol']} {item['direction']}: "
                f"WR={item['win_rate']:.1f}% ({item['total']} сделок), "
                f"Avg=${item['avg_pnl']:.2f}"
            )
        
        # Топ-3 худших
        summary_lines.append("\n⚠️ ХУДШИЕ:")
        for item in all_pairs_stats[-3:]:
            summary_lines.append(
                f"  {item['symbol']} {item['direction']}: "
                f"WR={item['win_rate']:.1f}% ({item['total']} сделок), "
                f"Avg=${item['avg_pnl']:.2f}"
            )
        
        return "\n".join(summary_lines)
    
    def get_pair_stats(self, symbol: str) -> Optional[Dict]:
        """Получить статистику для конкретной пары"""
        if symbol not in self.stats:
            return None
        
        directions = {}
        for direction, stats in self.stats[symbol].items():
            directions[direction] = {
                'win_rate': stats.win_rate,
                'avg_pnl': stats.avg_pnl,
                'total': stats.total,
                'winners': stats.winners,
                'total_pnl': stats.total_pnl
            }
        
        return directions
