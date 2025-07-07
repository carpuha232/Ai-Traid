"""
📊 Мультитаймфреймовый анализатор
Анализирует данные на всех таймфреймах для принятия торговых решений
Интегрирован с OnlineDataManager для прямого доступа к данным
"""

import os
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional

# Импортируем онлайн менеджер данных
from online_data_manager import get_data_manager

class MultiTimeframeAnalyzer:
    """Анализатор мультитаймфреймовых данных с онлайн доступом"""
    
    def __init__(self, data_path="enhanced_data"):
        self.data_path = data_path
        self.timeframes = ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d']
        self.timeframe_weights = {
            '1m': 0.05,   # 5% веса
            '5m': 0.10,   # 10% веса
            '15m': 0.15,  # 15% веса
            '30m': 0.20,  # 20% веса
            '1h': 0.25,   # 25% веса
            '2h': 0.15,   # 15% веса
            '4h': 0.07,   # 7% веса
            '1d': 0.03    # 3% веса
        }
        self.cached_data = {}
        self.analysis_cache = {}
        
        # Интеграция с онлайн менеджером данных
        self.data_manager = None
        self.online_mode = False
        self._initialize_online_manager()
    
    def _initialize_online_manager(self):
        """Инициализация онлайн менеджера данных"""
        try:
            self.data_manager = get_data_manager()
            self.online_mode = True
            print("✅ Мультитаймфреймовый анализатор подключен к онлайн данным")
        except Exception as e:
            print(f"⚠️ Ошибка подключения к онлайн данным: {e}")
            self.online_mode = False
        
    def load_historical_data(self, symbol: str, timeframe: str):
        """Загружает исторические данные для символа и таймфрейма"""
        try:
            # Проверяем кэш
            cache_key = f"{symbol}_{timeframe}"
            if cache_key in self.cached_data:
                return self.cached_data[cache_key]
            
            # Пытаемся получить онлайн данные
            if self.online_mode and self.data_manager:
                try:
                    # Получаем данные через онлайн менеджер (синхронно)
                    market_data = self.data_manager.get_dataframe(symbol, timeframe, limit=100)
                    if not market_data.empty:
                        # Кэшируем данные
                        self.cached_data[cache_key] = market_data
                        return market_data
                except Exception as e:
                    print(f"⚠️ Ошибка получения онлайн данных {symbol} {timeframe}: {e}")
            
            # Fallback на файловые данные
            file_path = os.path.join(self.data_path, symbol, f"{timeframe}.parquet")
            
            if os.path.exists(file_path):
                df = pd.read_parquet(file_path)
                # Кэшируем данные
                self.cached_data[cache_key] = df
                return df
            else:
                print(f"⚠️ Файл не найден: {file_path}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка загрузки данных {symbol} {timeframe}: {e}")
            return None
    
    def calculate_technical_indicators(self, df) -> dict:
        """Рассчитывает технические индикаторы"""
        if df is None or len(df) < 20:
            return {}
        
        try:
            close_prices = df['close']
            
            # RSI
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # MACD
            ema12 = close_prices.ewm(span=12).mean()
            ema26 = close_prices.ewm(span=26).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9).mean()
            histogram = macd - signal
            
            # Bollinger Bands
            sma20 = close_prices.rolling(window=20).mean()
            std20 = close_prices.rolling(window=20).std()
            bb_upper = sma20 + (std20 * 2)
            bb_lower = sma20 - (std20 * 2)
            
            # Волатильность
            volatility = close_prices.pct_change().rolling(window=20).std() * 100
            
            # Тренд
            sma50 = close_prices.rolling(window=50).mean()
            sma200 = close_prices.rolling(window=200).mean()
            
            return {
                'rsi': rsi.iloc[-1] if not rsi.empty else 50,
                'macd': macd.iloc[-1] if not macd.empty else 0,
                'macd_signal': signal.iloc[-1] if not signal.empty else 0,
                'macd_histogram': histogram.iloc[-1] if not histogram.empty else 0,
                'bb_upper': bb_upper.iloc[-1] if not bb_upper.empty else close_prices.iloc[-1],
                'bb_lower': bb_lower.iloc[-1] if not bb_lower.empty else close_prices.iloc[-1],
                'bb_position': (close_prices.iloc[-1] - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1]) if not bb_upper.empty and not bb_lower.empty else 0.5,
                'volatility': volatility.iloc[-1] if not volatility.empty else 0,
                'trend_50': 'up' if close_prices.iloc[-1] > sma50.iloc[-1] else 'down' if not sma50.empty else 'neutral',
                'trend_200': 'up' if close_prices.iloc[-1] > sma200.iloc[-1] else 'down' if not sma200.empty else 'neutral',
                'price_change_1h': ((close_prices.iloc[-1] - close_prices.iloc[-12]) / close_prices.iloc[-12] * 100) if len(close_prices) >= 12 else 0,
                'price_change_4h': ((close_prices.iloc[-1] - close_prices.iloc[-48]) / close_prices.iloc[-48] * 100) if len(close_prices) >= 48 else 0,
                'volume_avg': df['volume'].rolling(window=20).mean().iloc[-1] if 'volume' in df.columns else 0
            }
            
        except Exception as e:
            print(f"❌ Ошибка расчета индикаторов: {e}")
            return {}
    
    def analyze_symbol_multi_timeframe(self, symbol: str) -> dict:
        """Анализирует символ на всех таймфреймах"""
        try:
            # Проверяем кэш
            if symbol in self.analysis_cache:
                return self.analysis_cache[symbol]
            
            analysis = {
                'symbol': symbol,
                'timeframes': {},
                'aggregated_signals': {
                    'buy_signals': 0,
                    'sell_signals': 0,
                    'hold_signals': 0,
                    'confidence': 0.0,
                    'trend_strength': 0.0,
                    'volatility_score': 0.0
                },
                'recommendation': 'HOLD',
                'reasoning': []
            }
            
            total_weight = 0
            weighted_buy = 0
            weighted_sell = 0
            weighted_hold = 0
            
            for timeframe in self.timeframes:
                # Загружаем данные
                df = self.load_historical_data(symbol, timeframe)
                if df is None or len(df) < 50:
                    continue
                
                # Рассчитываем индикаторы
                indicators = self.calculate_technical_indicators(df)
                if not indicators:
                    continue
                
                # Анализируем сигналы для данного таймфрейма
                tf_analysis = self._analyze_timeframe_signals(indicators, timeframe)
                
                # Сохраняем анализ таймфрейма
                analysis['timeframes'][timeframe] = {
                    'indicators': indicators,
                    'signal': tf_analysis['signal'],
                    'strength': tf_analysis['strength'],
                    'reasoning': tf_analysis['reasoning']
                }
                
                # Взвешенное голосование
                weight = self.timeframe_weights.get(timeframe, 0.1)
                total_weight += weight
                
                if tf_analysis['signal'] == 'BUY':
                    weighted_buy += weight * tf_analysis['strength']
                elif tf_analysis['signal'] == 'SELL':
                    weighted_sell += weight * tf_analysis['strength']
                else:
                    weighted_hold += weight * tf_analysis['strength']
            
            # Рассчитываем агрегированные сигналы
            if total_weight > 0:
                analysis['aggregated_signals']['buy_signals'] = weighted_buy / total_weight
                analysis['aggregated_signals']['sell_signals'] = weighted_sell / total_weight
                analysis['aggregated_signals']['hold_signals'] = weighted_hold / total_weight
                
                # Определяем рекомендацию
                max_signal = max(weighted_buy, weighted_sell, weighted_hold)
                if max_signal == weighted_buy and weighted_buy > 0.3:
                    analysis['recommendation'] = 'BUY'
                    analysis['aggregated_signals']['confidence'] = weighted_buy
                elif max_signal == weighted_sell and weighted_sell > 0.3:
                    analysis['recommendation'] = 'SELL'
                    analysis['aggregated_signals']['confidence'] = weighted_sell
                else:
                    analysis['recommendation'] = 'HOLD'
                    analysis['aggregated_signals']['confidence'] = weighted_hold
                
                # Рассчитываем силу тренда и волатильность
                trend_strength = 0
                volatility_score = 0
                for tf, tf_data in analysis['timeframes'].items():
                    weight = self.timeframe_weights.get(tf, 0.1)
                    trend_strength += weight * tf_data['strength']
                    volatility_score += weight * tf_data['indicators'].get('volatility', 0)
                
                analysis['aggregated_signals']['trend_strength'] = trend_strength
                analysis['aggregated_signals']['volatility_score'] = volatility_score / len(analysis['timeframes'])
            
            # Генерируем объяснение
            analysis['reasoning'] = self._generate_analysis_reasoning(analysis)
            
            # Кэшируем результат
            self.analysis_cache[symbol] = analysis
            
            return analysis
            
        except Exception as e:
            print(f"❌ Ошибка анализа {symbol}: {e}")
            return {
                'symbol': symbol,
                'recommendation': 'HOLD',
                'reasoning': [f"Ошибка анализа: {e}"]
            }
    
    def _analyze_timeframe_signals(self, indicators: dict, timeframe: str) -> dict:
        """Анализирует сигналы для конкретного таймфрейма"""
        signal = 'HOLD'
        strength = 0.0
        reasoning = []
        
        try:
            # RSI анализ
            rsi = indicators.get('rsi', 50)
            if rsi < 30:
                signal = 'BUY'
                strength += 0.3
                reasoning.append(f"RSI перепродан ({rsi:.1f})")
            elif rsi > 70:
                signal = 'SELL'
                strength += 0.3
                reasoning.append(f"RSI перекуплен ({rsi:.1f})")
            
            # MACD анализ
            macd = indicators.get('macd', 0)
            macd_signal = indicators.get('macd_signal', 0)
            macd_histogram = indicators.get('macd_histogram', 0)
            
            if macd > macd_signal and macd_histogram > 0:
                if signal == 'BUY':
                    strength += 0.2
                elif signal == 'HOLD':
                    signal = 'BUY'
                    strength += 0.2
                reasoning.append("MACD выше сигнальной линии")
            elif macd < macd_signal and macd_histogram < 0:
                if signal == 'SELL':
                    strength += 0.2
                elif signal == 'HOLD':
                    signal = 'SELL'
                    strength += 0.2
                reasoning.append("MACD ниже сигнальной линии")
            
            # Bollinger Bands анализ
            bb_position = indicators.get('bb_position', 0.5)
            if bb_position < 0.2:
                if signal == 'BUY':
                    strength += 0.2
                elif signal == 'HOLD':
                    signal = 'BUY'
                    strength += 0.2
                reasoning.append("Цена у нижней полосы Боллинджера")
            elif bb_position > 0.8:
                if signal == 'SELL':
                    strength += 0.2
                elif signal == 'HOLD':
                    signal = 'SELL'
                    strength += 0.2
                reasoning.append("Цена у верхней полосы Боллинджера")
            
            # Тренд анализ
            trend_50 = indicators.get('trend_50', 'neutral')
            trend_200 = indicators.get('trend_200', 'neutral')
            
            if trend_50 == 'up' and trend_200 == 'up':
                if signal == 'BUY':
                    strength += 0.15
                reasoning.append("Сильный восходящий тренд")
            elif trend_50 == 'down' and trend_200 == 'down':
                if signal == 'SELL':
                    strength += 0.15
                reasoning.append("Сильный нисходящий тренд")
            
            # Изменение цены
            price_change_1h = indicators.get('price_change_1h', 0)
            price_change_4h = indicators.get('price_change_4h', 0)
            
            if price_change_1h > 2 and price_change_4h > 5:
                if signal == 'BUY':
                    strength += 0.15
                reasoning.append(f"Сильный рост: +{price_change_1h:.1f}% (1ч), +{price_change_4h:.1f}% (4ч)")
            elif price_change_1h < -2 and price_change_4h < -5:
                if signal == 'SELL':
                    strength += 0.15
                reasoning.append(f"Сильное падение: {price_change_1h:.1f}% (1ч), {price_change_4h:.1f}% (4ч)")
            
            # Ограничиваем силу сигнала
            strength = min(strength, 1.0)
            
            return {
                'signal': signal,
                'strength': strength,
                'reasoning': reasoning
            }
            
        except Exception as e:
            print(f"❌ Ошибка анализа таймфрейма {timeframe}: {e}")
            return {
                'signal': 'HOLD',
                'strength': 0.0,
                'reasoning': [f"Ошибка анализа: {e}"]
            }
    
    def _generate_analysis_reasoning(self, analysis: dict) -> list:
        """Генерирует объяснение анализа"""
        reasoning = []
        
        try:
            symbol = analysis['symbol']
            recommendation = analysis['recommendation']
            signals = analysis['aggregated_signals']
            
            # Основная рекомендация
            if recommendation == 'BUY':
                reasoning.append(f"🎯 Рекомендую BUY {symbol} (уверенность: {signals['confidence']:.1%})")
            elif recommendation == 'SELL':
                reasoning.append(f"🎯 Рекомендую SELL {symbol} (уверенность: {signals['confidence']:.1%})")
            else:
                reasoning.append(f"⏸️ Рекомендую HOLD {symbol} - недостаточно сигналов")
            
            # Анализ по таймфреймам
            strong_signals = []
            for tf, tf_data in analysis['timeframes'].items():
                if tf_data['strength'] > 0.5:
                    strong_signals.append(f"{tf}: {tf_data['signal']} ({tf_data['strength']:.1%})")
            
            if strong_signals:
                reasoning.append(f"📊 Сильные сигналы: {' | '.join(strong_signals[:3])}")
            
            # Волатильность
            volatility = signals.get('volatility_score', 0)
            if volatility > 5:
                reasoning.append(f"⚡ Высокая волатильность: {volatility:.1f}% - повышенный риск")
            elif volatility < 1:
                reasoning.append(f"🛡️ Низкая волатильность: {volatility:.1f}% - стабильный рынок")
            
            # Сила тренда
            trend_strength = signals.get('trend_strength', 0)
            if trend_strength > 0.7:
                reasoning.append(f"🚀 Сильный тренд: {trend_strength:.1%}")
            elif trend_strength < 0.3:
                reasoning.append(f"📉 Слабый тренд: {trend_strength:.1%}")
            
        except Exception as e:
            reasoning.append(f"❌ Ошибка генерации объяснения: {e}")
        
        return reasoning 