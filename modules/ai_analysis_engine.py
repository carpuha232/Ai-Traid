"""
🧠 ИИ анализатор для торгового дашборда
Обрабатывает мультитаймфреймовый анализ и генерирует торговые сигналы
"""

from typing import Dict, List
from datetime import datetime

class AIAnalysisEngine:
    """ИИ анализатор для торговых решений"""
    
    def __init__(self, multi_timeframe_analyzer=None):
        self.multi_timeframe_analyzer = multi_timeframe_analyzer
        self.analysis_history = []
        self.market_sentiment = 'neutral'
        
    def analyze_market_conditions(self, prices: Dict) -> Dict:
        """Анализирует рыночные условия для принятия решения"""
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'market_sentiment': 'neutral',
            'volatility': 'low',
            'trend_strength': 'weak',
            'risk_level': 'medium',
            'opportunity_score': 0.0,
            'recommendation': 'HOLD',
            'confidence': 0.0,
            'reasoning': []
        }
        
        if not prices:
            return analysis
        
        # Анализ настроения рынка
        positive_count = sum(1 for data in prices.values() if data.get('change_24h', 0) > 0)
        negative_count = sum(1 for data in prices.values() if data.get('change_24h', 0) < 0)
        total_coins = len(prices)
        
        if total_coins > 0:
            positive_ratio = positive_count / total_coins
            
            if positive_ratio > 0.6:
                analysis['market_sentiment'] = 'bullish'
                analysis['reasoning'].append(f"📈 Бычий рынок: {positive_count}/{total_coins} монет растут")
            elif positive_ratio < 0.4:
                analysis['market_sentiment'] = 'bearish'
                analysis['reasoning'].append(f"📉 Медвежий рынок: {negative_count}/{total_coins} монет падают")
            else:
                analysis['reasoning'].append(f"➡️ Боковой рынок: {positive_count}/{total_coins} растут, {negative_count}/{total_coins} падают")
        
        # Анализ волатильности
        max_change = max(abs(data.get('change_24h', 0)) for data in prices.values()) if prices else 0
        if max_change > 10:
            analysis['volatility'] = 'high'
            analysis['reasoning'].append(f"⚡ Высокая волатильность: макс. изменение {max_change:.1f}%")
        elif max_change > 5:
            analysis['volatility'] = 'medium'
            analysis['reasoning'].append(f"📊 Средняя волатильность: макс. изменение {max_change:.1f}%")
        else:
            analysis['reasoning'].append(f"🛡️ Низкая волатильность: макс. изменение {max_change:.1f}%")
        
        # Анализ объема
        total_volume = sum(data.get('volume_24h', 0) for data in prices.values())
        if total_volume > 1000000000:  # 1B+
            analysis['reasoning'].append("💰 Высокий общий объем - сильная ликвидность")
            analysis['opportunity_score'] += 0.2
        elif total_volume < 100000000:  # 100M-
            analysis['reasoning'].append("⚠️ Низкий общий объем - возможны проскальзывания")
            analysis['opportunity_score'] -= 0.1
        
        # Оценка риска
        if analysis['volatility'] == 'high':
            analysis['risk_level'] = 'high'
        elif analysis['volatility'] == 'low':
            analysis['risk_level'] = 'low'
        
        # Генерация рекомендации
        if analysis['opportunity_score'] > 0.3:
            if analysis['market_sentiment'] == 'bullish':
                analysis['recommendation'] = 'LONG'
                analysis['confidence'] = min(0.9, 0.5 + analysis['opportunity_score'])
                analysis['reasoning'].append("✅ Рекомендую LONG - благоприятные условия")
            elif analysis['market_sentiment'] == 'bearish':
                analysis['recommendation'] = 'SHORT'
                analysis['confidence'] = min(0.9, 0.5 + analysis['opportunity_score'])
                analysis['reasoning'].append("✅ Рекомендую SHORT - нисходящий тренд")
        else:
            analysis['reasoning'].append("⏸️ Рекомендую HOLD - недостаточно сигналов")
        
        return analysis
    
    def add_multi_timeframe_analysis(self, symbols: List[str], prices: Dict, log_callback=None) -> List[Dict]:
        """Добавляет мультитаймфреймовый анализ"""
        if not self.multi_timeframe_analyzer:
            return []
        
        results = []
        
        # Сортируем по изменению цены для выбора самых активных
        sorted_symbols = sorted(symbols, 
                              key=lambda s: abs(prices.get(s, {}).get('change_24h', 0)), 
                              reverse=True)[:5]
        
        if log_callback:
            log_callback("🧠 МУЛЬТИТАЙМФРЕЙМОВЫЙ АНАЛИЗ:", "SIGNAL")
        
        for symbol in sorted_symbols:
            try:
                # Получаем мультитаймфреймовый анализ
                analysis = self.multi_timeframe_analyzer.analyze_symbol_multi_timeframe(symbol)
                
                if analysis and 'recommendation' in analysis:
                    recommendation = analysis['recommendation']
                    confidence = analysis['aggregated_signals'].get('confidence', 0)
                    
                    # Формируем сообщение
                    if log_callback:
                        if recommendation == 'BUY':
                            message = f"🟢 {symbol}: BUY (уверенность: {confidence:.1%})"
                            log_callback(message, "SIGNAL")
                        elif recommendation == 'SELL':
                            message = f"🔴 {symbol}: SELL (уверенность: {confidence:.1%})"
                            log_callback(message, "SIGNAL")
                        else:
                            message = f"⚪ {symbol}: HOLD (уверенность: {confidence:.1%})"
                            log_callback(message, "INFO")
                        
                        # Добавляем детали анализа
                        for reason in analysis.get('reasoning', [])[:2]:  # Показываем первые 2 причины
                            log_callback(f"   • {reason}", "INFO")
                    
                    results.append(analysis)
                
            except Exception as e:
                print(f"❌ Ошибка анализа {symbol}: {e}")
                continue
        
        return results
    
    def add_market_summary(self, symbols: List[str], log_callback=None) -> Dict:
        """Добавляет сводку по рынку"""
        summary = {
            'buy_signals': 0,
            'sell_signals': 0,
            'hold_signals': 0,
            'total_analyzed': 0,
            'market_sentiment': 'neutral'
        }
        
        if not self.multi_timeframe_analyzer:
            return summary
        
        # Подсчитываем сигналы
        for symbol in symbols[:10]:  # Анализируем первые 10 монет
            try:
                analysis = self.multi_timeframe_analyzer.analyze_symbol_multi_timeframe(symbol)
                if analysis and 'recommendation' in analysis:
                    if analysis['recommendation'] == 'BUY':
                        summary['buy_signals'] += 1
                    elif analysis['recommendation'] == 'SELL':
                        summary['sell_signals'] += 1
                    else:
                        summary['hold_signals'] += 1
                    summary['total_analyzed'] += 1
            except:
                continue
        
        # Формируем сводку
        if log_callback and summary['total_analyzed'] > 0:
            summary_text = f"📊 Сводка: BUY: {summary['buy_signals']} | SELL: {summary['sell_signals']} | HOLD: {summary['hold_signals']}"
            log_callback(summary_text, "METRICS")
            
            # Определяем общее настроение
            if summary['buy_signals'] > summary['sell_signals'] * 2:
                summary['market_sentiment'] = 'bullish'
                log_callback("🎯 Общее настроение: БЫЧЬЕ - ищу возможности для покупок", "SIGNAL")
            elif summary['sell_signals'] > summary['buy_signals'] * 2:
                summary['market_sentiment'] = 'bearish'
                log_callback("🎯 Общее настроение: МЕДВЕЖЬЕ - ищу возможности для продаж", "SIGNAL")
            else:
                summary['market_sentiment'] = 'neutral'
                log_callback("🎯 Общее настроение: НЕЙТРАЛЬНОЕ - жду четких сигналов", "INFO")
        
        return summary
    
    def search_trading_opportunities(self, prices: Dict, log_callback=None) -> List[str]:
        """Ищет торговые возможности на основе анализа"""
        opportunities = []
        
        try:
            # Анализируем каждую монету на предмет торговых сигналов
            for symbol, price_data in prices.items():
                # Простые критерии для торговых сигналов
                change_24h = price_data.get('change_24h', 0)
                volume = price_data.get('volume_24h', 0)
                
                # Сигнал на покупку: сильный рост + высокий объем
                if change_24h > 5 and volume > 50000000:  # 5% рост + 50M объем
                    opportunities.append(f"🚀 {symbol}: Сильный рост +{change_24h:.1f}% (объем: ${volume/1e6:.1f}M)")
                
                # Сигнал на продажу: сильное падение + высокий объем
                elif change_24h < -5 and volume > 50000000:  # 5% падение + 50M объем
                    opportunities.append(f"📉 {symbol}: Сильное падение {change_24h:.1f}% (объем: ${volume/1e6:.1f}M)")
                
                # Сигнал на разворот: экстремальные значения
                elif change_24h > 15:  # Более 15% роста - возможен разворот
                    opportunities.append(f"⚠️ {symbol}: Экстремальный рост +{change_24h:.1f}% - возможен разворот")
                elif change_24h < -15:  # Более 15% падения - возможен разворот
                    opportunities.append(f"⚠️ {symbol}: Экстремальное падение {change_24h:.1f}% - возможен разворот")
            
            # Показываем найденные возможности
            if log_callback:
                if opportunities:
                    log_callback("🎯 Найденные торговые возможности:", "SIGNAL")
                    for opp in opportunities[:5]:  # Показываем максимум 5 возможностей
                        log_callback(f"   • {opp}", "INFO")
                else:
                    log_callback("🔍 Торговых возможностей не найдено - жду лучших условий", "INFO")
                    
        except Exception as e:
            print(f"Ошибка поиска торговых возможностей: {e}")
        
        return opportunities
    
    def learn_from_trade(self, trade_result: Dict):
        """Учится на основе результата сделки"""
        insight = {
            'timestamp': datetime.now().isoformat(),
            'symbol': trade_result.get('symbol', ''),
            'entry_price': trade_result.get('entry_price', 0),
            'exit_price': trade_result.get('exit_price', 0),
            'pnl': trade_result.get('pnl', 0),
            'pnl_pct': trade_result.get('pnl_pct', 0),
            'duration': trade_result.get('duration', 0),
            'analysis_at_entry': trade_result.get('analysis_at_entry', {}),
            'lessons_learned': []
        }
        
        # Анализируем результат
        if trade_result.get('pnl_pct', 0) > 0:
            insight['lessons_learned'].append("✅ Успешная сделка - условия входа были правильными")
            if trade_result.get('pnl_pct', 0) > 2:
                insight['lessons_learned'].append("🎯 Отличный результат - можно увеличить размер позиции")
        else:
            insight['lessons_learned'].append("❌ Убыточная сделка - нужно пересмотреть критерии входа")
            if trade_result.get('pnl_pct', 0) < -2:
                insight['lessons_learned'].append("⚠️ Большие потери - требуется улучшение управления рисками")
        
        # Анализируем длительность
        duration = trade_result.get('duration', 0)
        if duration < 300:  # 5 минут
            insight['lessons_learned'].append("⚡ Быстрая сделка - возможно, нужно дольше держать позицию")
        elif duration > 3600:  # 1 час
            insight['lessons_learned'].append("⏰ Долгая сделка - возможно, нужно быстрее фиксировать прибыль")
        
        self.analysis_history.append(insight)
        
        return insight
    
    def get_recent_insights(self, limit: int = 5) -> List[str]:
        """Возвращает последние уроки"""
        recent_insights = []
        for insight in self.analysis_history[-limit:]:
            for lesson in insight.get('lessons_learned', []):
                recent_insights.append(f"{insight.get('symbol', '')}: {lesson}")
        return recent_insights 