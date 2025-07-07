"""
🚀 Агрессивная торговая система v1.0
Скальпинг с адаптивной агрессией по волатильности
Цель: 100+ сделок в день с винрейтом >70%
"""

import numpy as np
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

class AggressiveTradeSystem:
    """Агрессивная торговая система для скальпинга"""
    
    def __init__(self, initial_balance: float = 100.0):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.open_positions = []
        self.closed_positions = []
        
        # Агрессивные настройки торговли
        self.trading_config = {
            'max_position_size': 0.01,  # 1% от баланса (риск)
            'risk_reward_ratio': 1/2,   # 1:2
            'leverage_range': (5, 20),  # Меньше плечо для безопасности
            'stop_loss_pct': 0.005,     # 0.5% стоп-лосс
            'take_profit_pct': 0.01,    # 1% тейк-профит
            'max_positions': 3,         # Максимум 3 позиции
            'monitoring_interval': 30,  # 30 секунд
            'min_confidence': 0.25,     # Еще более пониженная уверенность
            'min_signal_threshold': 0.08,  # Еще более пониженный порог сигналов
            'volatility_aggression': True,  # Адаптивная агрессия
            'scalping_mode': True       # Режим скальпинга
        }
        
        # Торговые пары для скальпинга
        self.symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
        
        # Таймфреймы для скальпинга
        self.timeframes = ['1m', '5m', '15m']
        
        # Логирование
        self.log_file = f"aggressive_trade_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # Статистика
        self.stats = {
            'total_signals': 0,
            'executed_trades': 0,
            'missed_opportunities': 0,
            'last_analysis_time': None
        }
        
        self.risk_per_trade = 0.01  # стартовый риск 1%
        self.min_risk = 0.003  # минимум 0.3%
        self.max_risk = 0.05   # максимум 5%
        self.risk_step = 0.002 # шаг изменения риска
        self.last_lessons = [] # уроки из ошибок
    
    def log_message(self, message: str, level: str = "INFO"):
        """Логирует сообщения"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {level}: {message}"
        
        print(log_entry)
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
    
    def get_online_data(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """Получает данные онлайн через Binance API"""
        try:
            # Параметры для Binance API
            base_url = "https://api.binance.com/api/v3"
            
            # Конвертируем таймфрейм
            interval_map = {
                '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
                '1h': '1h', '2h': '2h', '4h': '4h', '1d': '1d'
            }
            
            interval = interval_map.get(timeframe, '1m')
            
            # Получаем данные
            url = f"{base_url}/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            
            # Преобразуем в DataFrame
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Конвертируем типы данных
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df.set_index('timestamp', inplace=True)
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            return df
            
        except Exception as e:
            self.log_message(f"❌ Ошибка получения данных {symbol} {timeframe}: {e}", "ERROR")
            return pd.DataFrame()
    
    def calculate_volatility(self, df: pd.DataFrame, period: int = 20) -> float:
        """Рассчитывает текущую волатильность"""
        if len(df) < period:
            return 0.0
        
        returns = df['close'].pct_change().dropna()
        volatility = returns.rolling(window=period).std().iloc[-1]
        return float(volatility)
    
    def get_aggression_multiplier(self, volatility: float) -> float:
        """Возвращает множитель агрессии на основе волатильности"""
        if not self.trading_config['volatility_aggression']:
            return 1.0
        
        # Высокая волатильность = больше агрессии
        if volatility > 0.03:  # 3% волатильность
            return 2.0
        elif volatility > 0.02:  # 2% волатильность
            return 1.5
        elif volatility > 0.01:  # 1% волатильность
            return 1.2
        else:
            return 0.8  # Низкая волатильность = меньше агрессии
    
    def scalping_rsi_strategy(self, df: pd.DataFrame) -> float:
        """Агрессивная RSI стратегия для скальпинга"""
        if len(df) < 14:
            return 0.0
        
        # Быстрый RSI для скальпинга
        period = 5  # Еще более быстрый период
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        
        # Еще более агрессивные сигналы
        if current_rsi < 25:  # Сильная перепроданность
            return 0.9
        elif current_rsi < 35:  # Перепроданность
            return 0.6
        elif current_rsi > 75:  # Сильная перекупленность
            return -0.9
        elif current_rsi > 65:  # Перекупленность
            return -0.6
        else:
            return 0.0
    
    def scalping_macd_strategy(self, df: pd.DataFrame) -> float:
        """Агрессивная MACD стратегия для скальпинга"""
        if len(df) < 26:
            return 0.0
        
        # Еще более быстрый MACD для скальпинга
        fast = 3   # Очень быстрая EMA
        slow = 7   # Быстрая EMA
        signal = 2 # Очень быстрая сигнальная линия
        
        ema_fast = df['close'].ewm(span=fast).mean()
        ema_slow = df['close'].ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal).mean()
        histogram = macd - signal_line
        
        current_histogram = histogram.iloc[-1]
        prev_histogram = histogram.iloc[-2] if len(histogram) > 1 else 0
        
        # Более агрессивные сигналы
        if current_histogram > 0 and prev_histogram <= 0:  # Пересечение вверх
            return 0.8
        elif current_histogram < 0 and prev_histogram >= 0:  # Пересечение вниз
            return -0.8
        elif current_histogram > 0.0005:  # Положительный сигнал
            return 0.6
        elif current_histogram < -0.0005:  # Отрицательный сигнал
            return -0.6
        else:
            return 0.0
    
    def scalping_volume_strategy(self, df: pd.DataFrame) -> float:
        """Стратегия объема для скальпинга"""
        if len(df) < 10:
            return 0.0
        
        # Анализируем объем последних свечей
        recent_volume = df['volume'].tail(3).mean()  # Уменьшаем период
        avg_volume = df['volume'].tail(15).mean()    # Уменьшаем период
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Анализируем изменение цены
        price_change = (df['close'].iloc[-1] - df['close'].iloc[-3]) / df['close'].iloc[-3]
        
        # Более агрессивные сигналы
        if volume_ratio > 1.2 and price_change > 0.003:  # Высокий объем + рост
            return 0.7
        elif volume_ratio > 1.2 and price_change < -0.003:  # Высокий объем + падение
            return -0.7
        elif volume_ratio > 1.5:  # Очень высокий объем
            return 0.5 if price_change > 0 else -0.5
        else:
            return 0.0
    
    def scalping_momentum_strategy(self, df: pd.DataFrame) -> float:
        """Стратегия импульса для скальпинга"""
        if len(df) < 5:
            return 0.0
        
        # Быстрый импульс
        momentum_2 = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]  # Уменьшаем период
        momentum_3 = (df['close'].iloc[-1] - df['close'].iloc[-3]) / df['close'].iloc[-3]
        
        # Более агрессивные сигналы
        if momentum_2 > 0.005 and momentum_3 > 0.003:  # Сильный восходящий импульс
            return 0.8
        elif momentum_2 < -0.005 and momentum_3 < -0.003:  # Сильный нисходящий импульс
            return -0.8
        elif momentum_2 > 0.003:  # Умеренный восходящий импульс
            return 0.5
        elif momentum_2 < -0.003:  # Умеренный нисходящий импульс
            return -0.5
        else:
            return 0.0
    
    def analyze_symbol(self, symbol: str) -> Dict:
        """Анализирует торговую пару"""
        try:
            all_signals = []
            weights = []
            
            # Анализируем каждый таймфрейм
            for timeframe in self.timeframes:
                df = self.get_online_data(symbol, timeframe, limit=50)
                
                if df.empty:
                    continue
                
                # Рассчитываем волатильность
                volatility = self.calculate_volatility(df)
                aggression_multiplier = self.get_aggression_multiplier(volatility)
                
                # Применяем скальпинг стратегии
                strategies = [
                    (self.scalping_rsi_strategy, 1.0),
                    (self.scalping_macd_strategy, 1.2),
                    (self.scalping_volume_strategy, 1.5),
                    (self.scalping_momentum_strategy, 1.0)
                ]
                
                timeframe_signals = []
                timeframe_weights = []
                
                for strategy_func, weight in strategies:
                    try:
                        signal = strategy_func(df)
                        # Применяем множитель агрессии
                        adjusted_signal = signal * aggression_multiplier
                        
                        timeframe_signals.append(adjusted_signal)
                        timeframe_weights.append(weight)
                        
                    except Exception as e:
                        self.log_message(f"   ⚠️ Ошибка стратегии: {e}", "WARNING")
                        timeframe_signals.append(0)
                        timeframe_weights.append(0.5)
                
                # Взвешенный сигнал для таймфрейма
                if timeframe_signals and timeframe_weights:
                    timeframe_signal = sum(s * w for s, w in zip(timeframe_signals, timeframe_weights)) / sum(timeframe_weights)
                    
                    # Вес таймфрейма
                    timeframe_weight = 1.0 if timeframe == '1m' else 0.8 if timeframe == '5m' else 0.6
                    
                    all_signals.append(timeframe_signal)
                    weights.append(timeframe_weight)
                    
                    self.log_message(f"   📊 {timeframe}: сигнал {timeframe_signal:.3f}, волатильность {volatility:.3f}, агрессия x{aggression_multiplier:.1f}")
            
            # Итоговый взвешенный сигнал
            if all_signals and weights:
                final_signal = sum(s * w for s, w in zip(all_signals, weights)) / sum(weights)
                
                # Определяем направление и уверенность
                if abs(final_signal) >= self.trading_config['min_signal_threshold']:
                    direction = 'LONG' if final_signal > 0 else 'SHORT'
                    confidence = min(0.95, 0.4 + abs(final_signal) * 0.5)
                    
                    return {
                        'should_trade': True,
                        'symbol': symbol,
                        'direction': direction,
                        'confidence': confidence,
                        'signal_strength': abs(final_signal),
                        'volatility': volatility,
                        'aggression_multiplier': aggression_multiplier
                    }
            
            return {'should_trade': False}
            
        except Exception as e:
            self.log_message(f"❌ Ошибка анализа {symbol}: {e}", "ERROR")
            return {'should_trade': False}
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Получает текущую цену"""
        try:
            df = self.get_online_data(symbol, '1m', limit=1)
            if not df.empty:
                return float(df['close'].iloc[-1])
            return None
        except:
            return None
    
    def calculate_position_size(self, symbol: str, price: float, confidence: float) -> float:
        """Рассчитывает размер позиции с учётом динамического риска"""
        base_size = self.current_balance * self.risk_per_trade
        adjusted_size = base_size * (0.5 + confidence * 0.5)
        return adjusted_size / price
    
    def open_position(self, symbol: str, direction: str, price: float, confidence: float):
        """Открывает позицию"""
        try:
            # Проверяем лимиты
            if len(self.open_positions) >= self.trading_config['max_positions']:
                self.log_message(f"⚠️ Достигнут лимит позиций ({self.trading_config['max_positions']})")
                return
            
            # Проверяем, нет ли уже позиции по этой паре
            for position in self.open_positions:
                if position['symbol'] == symbol:
                    self.log_message(f"⚠️ Уже есть открытая позиция по {symbol}")
                    return
            
            # Рассчитываем размер позиции
            position_size = self.calculate_position_size(symbol, price, confidence)
            
            # Рассчитываем стоп-лосс и тейк-профит
            if direction == 'LONG':
                stop_loss = price * (1 - self.trading_config['stop_loss_pct'])
                take_profit = price * (1 + self.trading_config['take_profit_pct'])
            else:
                stop_loss = price * (1 + self.trading_config['stop_loss_pct'])
                take_profit = price * (1 - self.trading_config['take_profit_pct'])
            
            position = {
                'symbol': symbol,
                'direction': direction,
                'entry_price': price,
                'size': position_size,
                'confidence': confidence,
                'entry_time': datetime.now(),
                'stop_loss': stop_loss,
                'take_profit': take_profit
            }
            
            self.open_positions.append(position)
            
            # Выводим информацию
            self.log_message(f"🚀 ОТКРЫТА ПОЗИЦИЯ - {symbol} {direction}")
            self.log_message(f"   Размер: ${position_size * price:.2f} (уверенность {confidence:.1%})")
            self.log_message(f"   Вход: ${price:.4f}")
            self.log_message(f"   Стоп: ${stop_loss:.4f} (-0.5%)")
            self.log_message(f"   Тейк: ${take_profit:.4f} (+1%)")
            self.log_message(f"   Соотношение: 1:2")
            self.log_message("")
            
        except Exception as e:
            self.log_message(f"❌ Ошибка открытия позиции: {e}", "ERROR")
    
    def check_positions(self):
        """Проверяет и управляет открытыми позициями"""
        positions_to_close = []
        
        for position in self.open_positions:
            try:
                current_price = self.get_current_price(position['symbol'])
                if not current_price:
                    continue
                
                # Проверяем стоп-лосс и тейк-профит
                if position['direction'] == 'LONG':
                    if current_price <= position['stop_loss']:
                        positions_to_close.append((position, current_price, 'Stop Loss'))
                    elif current_price >= position['take_profit']:
                        positions_to_close.append((position, current_price, 'Take Profit'))
                else:  # SHORT
                    if current_price >= position['stop_loss']:
                        positions_to_close.append((position, current_price, 'Stop Loss'))
                    elif current_price <= position['take_profit']:
                        positions_to_close.append((position, current_price, 'Take Profit'))
                        
            except Exception as e:
                self.log_message(f"❌ Ошибка проверки позиции {position['symbol']}: {e}", "ERROR")
        
        # Закрываем позиции
        for position, close_price, reason in positions_to_close:
            self.close_position(position, close_price, reason)
    
    def close_position(self, position: Dict, close_price: float, reason: str):
        """Закрывает позицию с учётом комиссии"""
        try:
            # Рассчитываем P&L
            if position['direction'] == 'LONG':
                pnl_pct = (close_price - position['entry_price']) / position['entry_price']
            else:
                pnl_pct = (position['entry_price'] - close_price) / position['entry_price']
            pnl = position['size'] * position['entry_price'] * pnl_pct
            # Учёт комиссии (0.04% на вход и выход)
            commission_rate = 0.0004  # 0.04% на вход и выход
            trade_volume = position['size'] * position['entry_price']
            commission = trade_volume * commission_rate * 2  # вход + выход
            # Обновляем баланс с учётом комиссии
            self.current_balance += pnl - commission
            # Добавляем в закрытые позиции
            closed_position = position.copy()
            closed_position.update({
                'close_price': close_price,
                'close_time': datetime.now(),
                'reason': reason,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'commission': commission
            })
            self.closed_positions.append(closed_position)
            # Удаляем из открытых позиций
            self.open_positions = [p for p in self.open_positions if p != position]
            # Динамическое управление риском
            self._adjust_risk_after_trade(pnl)
            # Выводим результат
            status = "✅ ПРИБЫЛЬ" if pnl > 0 else "❌ УБЫТОК"
            self.log_message(f"{status} - {position['symbol']} {position['direction']}")
            self.log_message(f"   Вход: ${position['entry_price']:.4f} | Выход: ${close_price:.4f}")
            self.log_message(f"   P&L: ${pnl:.2f} ({pnl_pct:.2%}) | Комиссия: ${commission:.4f} | Причина: {reason}")
            self.log_message(f"   Баланс: ${self.current_balance:.2f}")
            self.log_message("")
        except Exception as e:
            self.log_message(f"❌ Ошибка закрытия позиции: {e}", "ERROR")
            self._learn_from_error(f"Ошибка закрытия позиции: {e}")

    def _adjust_risk_after_trade(self, pnl):
        """Динамически меняет риск в зависимости от результата сделки"""
        # Анализ последних 10 сделок
        recent = self.closed_positions[-10:]
        avg_pnl = sum(p['pnl'] for p in recent) / len(recent) if recent else 0
        winrate = sum(1 for p in recent if p['pnl'] > 0) / len(recent) * 100 if recent else 0
        old_risk = self.risk_per_trade
        # Если средний PnL и winrate растут — увеличиваем риск
        if avg_pnl > 0 and winrate > 60 and self.risk_per_trade < self.max_risk:
            self.risk_per_trade = min(self.risk_per_trade + self.risk_step, self.max_risk)
            self.log_message(f"⬆️ Риск увеличен до {self.risk_per_trade*100:.2f}% (winrate: {winrate:.1f}%, avg PnL: {avg_pnl:.2f})")
        # Если убытки или winrate падает — уменьшаем риск
        elif avg_pnl < 0 or winrate < 40:
            self.risk_per_trade = max(self.risk_per_trade - self.risk_step, self.min_risk)
            self.log_message(f"⬇️ Риск уменьшен до {self.risk_per_trade*100:.2f}% (winrate: {winrate:.1f}%, avg PnL: {avg_pnl:.2f})")
        # Если стабильность — не меняем
        if self.risk_per_trade != old_risk:
            self.log_message(f"[Риск] Новый риск на сделку: {self.risk_per_trade*100:.2f}%")

    def _learn_from_error(self, error_msg):
        """Извлекает урок из ошибки и корректирует стратегию"""
        lesson = f"Урок: {error_msg} — анализирую причину, снижаю риск."
        self.last_lessons.append(lesson)
        self.risk_per_trade = max(self.risk_per_trade - self.risk_step, self.min_risk)
        self.log_message(f"🧠 {lesson}")
        self.log_message(f"⬇️ Риск снижен до {self.risk_per_trade*100:.2f}% после ошибки.")
    
    def print_statistics(self):
        """Выводит статистику"""
        total_trades = len(self.closed_positions)
        if total_trades > 0:
            winning_trades = sum(1 for p in self.closed_positions if p['pnl'] > 0)
            winrate = (winning_trades / total_trades) * 100
            total_pnl = sum(p['pnl'] for p in self.closed_positions)
            
            self.log_message(f"📊 Статистика: {total_trades} сделок, винрейт: {winrate:.1f}%, P&L: ${total_pnl:.2f}")
            self.log_message(f"💰 Баланс: ${self.current_balance:.2f}, Открытых позиций: {len(self.open_positions)}")
            self.log_message(f"📈 Рост: {((self.current_balance / self.initial_balance - 1) * 100):.1f}%")
    
    def run(self):
        """Запускает агрессивную торговлю"""
        self.log_message("🚀 ЗАПУСК АГРЕССИВНОЙ ТОРГОВОЙ СИСТЕМЫ v1.0")
        self.log_message(f"   Начальный баланс: ${self.initial_balance:.2f}")
        self.log_message(f"   Режим: Скальпинг с адаптивной агрессией")
        self.log_message(f"   Риск: 1% на сделку, соотношение 1:2")
        self.log_message(f"   Мониторинг каждые {self.trading_config['monitoring_interval']} секунд")
        self.log_message("")
        
        iteration = 0
        max_iterations = 10000  # Больше итераций для скальпинга
        
        try:
            while iteration < max_iterations:
                iteration += 1
                
                if iteration % 10 == 0:
                    self.log_message(f"🔄 Итерация {iteration}")
                
                # Анализируем каждую торговую пару
                for symbol in self.symbols:
                    try:
                        # Анализируем символ
                        analysis = self.analyze_symbol(symbol)
                        
                        if analysis['should_trade']:
                            self.stats['total_signals'] += 1
                            
                            # Получаем текущую цену
                            current_price = self.get_current_price(symbol)
                            if current_price:
                                # Открываем позицию
                                self.open_position(
                                    symbol=analysis['symbol'],
                                    direction=analysis['direction'],
                                    price=current_price,
                                    confidence=analysis['confidence']
                                )
                                self.stats['executed_trades'] += 1
                            else:
                                self.stats['missed_opportunities'] += 1
                        
                        # Проверяем открытые позиции
                        self.check_positions()
                        
                    except Exception as e:
                        self.log_message(f"❌ Ошибка анализа {symbol}: {e}", "ERROR")
                
                # Выводим статистику каждые 50 итераций
                if iteration % 50 == 0:
                    self.print_statistics()
                    self.log_message(f"📈 Сигналов: {self.stats['total_signals']}, Сделок: {self.stats['executed_trades']}, Пропущено: {self.stats['missed_opportunities']}")
                
                # Ждем перед следующей итерацией
                time.sleep(self.trading_config['monitoring_interval'])
                
        except KeyboardInterrupt:
            self.log_message("⏹️ Торговля остановлена пользователем")
        except Exception as e:
            self.log_message(f"❌ Критическая ошибка: {e}", "ERROR")
        finally:
            self.print_statistics()
            self.log_message("🏁 Торговля завершена")

# Глобальный экземпляр системы
aggressive_trade_system = AggressiveTradeSystem() 