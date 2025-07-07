"""
💬 Менеджер терминала и чата для торгового дашборда
Управляет отображением сообщений, логов и ИИ анализа
"""

import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime
from typing import Dict, List, Optional, Callable

class TerminalManager:
    """Менеджер терминала для отображения сообщений и логов"""
    
    def __init__(self, parent, colors, ai_analysis_engine=None):
        self.parent = parent
        self.colors = colors
        self.ai_analysis_engine = ai_analysis_engine
        self.terminal_text = None
        self.message_count = 0
        
        self.create_terminal()
    
    def create_terminal(self):
        """Создание единого терминала/чата в правой колонке"""
        # Панель терминала
        terminal_frame = tk.Frame(self.parent, bg=self.colors.colors['bg_header'], 
                                relief=tk.FLAT, bd=0)
        terminal_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Заголовок терминала
        terminal_header = tk.Label(terminal_frame, text="📊 ТЕРМИНАЛ", 
                                 font=("Arial", 12, "bold"),
                                 fg="#06b6d4", 
                                 bg="#0a0a0a")
        terminal_header.pack(anchor=tk.W, pady=(0, 10))
        
        # Терминал
        self.terminal_text = scrolledtext.ScrolledText(
            terminal_frame,
            width=110,
            height=30,
            font=("Consolas", 12),
            bg="#1a1a1a",
            fg="#ffffff",
            insertbackground="#06b6d4",
            selectbackground="#6366f1",
            relief=tk.FLAT,
            borderwidth=0,
            wrap=tk.WORD
        )
        self.terminal_text.pack(fill=tk.BOTH, expand=True)
        self.terminal_text.config(state=tk.DISABLED)

        # Настраиваем теги для цветов
        self.terminal_text.tag_configure("INFO", foreground="#06b6d4")
        self.terminal_text.tag_configure("SUCCESS", foreground="#10b981")
        self.terminal_text.tag_configure("ERROR", foreground="#ef4444")
        self.terminal_text.tag_configure("SIGNAL", foreground="#f59e0b")
        self.terminal_text.tag_configure("METRICS", foreground="#8b5cf6")

        # Кнопки управления
        button_frame = tk.Frame(terminal_frame, bg="#0a0a0a")
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Кнопка очистки терминала
        clear_button = tk.Button(
            button_frame,
            text="🗑️ Очистить терминал",
            command=self.clear_terminal,
            font=("Arial", 12),
            bg="#6366f1",
            fg="#ffffff",
            relief=tk.FLAT,
            borderwidth=0,
            padx=10
        )
        clear_button.pack(side=tk.RIGHT, padx=5)
    
    def add_message(self, message: str, level: str = "INFO"):
        """Добавляет сообщение в единый терминал/чат (с автоскроллом и цветом)"""
        try:
            # Проверяем, что терминал существует
            if not self.terminal_text or not self.terminal_text.winfo_exists():
                return
                
            self.terminal_text.config(state=tk.NORMAL)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            formatted_message = f"[{timestamp}] {message}\n"
            # Используем тег для цвета
            self.terminal_text.insert(tk.END, formatted_message, level.upper())
            self.terminal_text.see(tk.END)
            # Ограничиваем количество строк
            lines = self.terminal_text.get(1.0, tk.END).split('\n')
            if len(lines) > 500:
                self.terminal_text.delete(1.0, f"{len(lines)-500}.0")
            self.terminal_text.config(state=tk.DISABLED)
            
            # Показываем последние уроки ИИ каждые 10 сообщений
            self.message_count += 1
            if self.message_count % 10 == 0:
                self.show_recent_ai_insights()
                
        except Exception as e:
            # Тихо обрабатываем ошибки добавления сообщений
            pass
    
    def show_recent_ai_insights(self):
        """Показывает последние уроки ИИ"""
        if self.ai_analysis_engine:
            insights = self.ai_analysis_engine.get_recent_insights(3)
            if insights:
                self.add_message("📚 Последние уроки ИИ:", "INFO")
                for insight in insights:
                    self.add_message(f"   • {insight}", "INFO")
    
    def clear_terminal(self):
        """Очищает терминал"""
        if self.terminal_text:
            self.terminal_text.config(state=tk.NORMAL)
            self.terminal_text.delete(1.0, tk.END)
            self.terminal_text.config(state=tk.DISABLED)

class AITradingSystem:
    """Интеллектуальная система принятия торговых решений"""
    
    def __init__(self, log_callback: Optional[Callable] = None):
        self.log_callback = log_callback
        self.trading_history = []
        self.learning_insights = []
        self.current_market_analysis = {}
        self.decision_reasons = {}
        
    def analyze_market_conditions(self, symbol: str, price: float, volume: float, change_24h: float) -> Dict:
        """Анализирует рыночные условия для принятия решения"""
        analysis = {
            'symbol': symbol,
            'price': price,
            'volume': volume,
            'change_24h': change_24h,
            'market_sentiment': 'neutral',
            'volatility': 'low',
            'trend_strength': 'weak',
            'risk_level': 'medium',
            'opportunity_score': 0.0,
            'recommendation': 'HOLD',
            'confidence': 0.0,
            'reasoning': []
        }
        
        # Анализ настроения рынка
        if change_24h > 5:
            analysis['market_sentiment'] = 'bullish'
            analysis['reasoning'].append(f"📈 Сильный рост за 24ч: +{change_24h:.1f}%")
        elif change_24h < -5:
            analysis['market_sentiment'] = 'bearish'
            analysis['reasoning'].append(f"📉 Сильное падение за 24ч: {change_24h:.1f}%")
        else:
            analysis['reasoning'].append(f"➡️ Стабильный рынок: {change_24h:.1f}%")
        
        # Анализ волатильности
        if abs(change_24h) > 10:
            analysis['volatility'] = 'high'
            analysis['reasoning'].append("⚡ Высокая волатильность - повышенный риск")
        elif abs(change_24h) > 5:
            analysis['volatility'] = 'medium'
            analysis['reasoning'].append("📊 Средняя волатильность")
        else:
            analysis['reasoning'].append("🛡️ Низкая волатильность - стабильный рынок")
        
        # Анализ объема
        if volume > 100000000:  # 100M+
            analysis['reasoning'].append("💰 Высокий объем торгов - сильная ликвидность")
            analysis['opportunity_score'] += 0.2
        elif volume < 10000000:  # 10M-
            analysis['reasoning'].append("⚠️ Низкий объем - возможны проскальзывания")
            analysis['opportunity_score'] -= 0.1
        
        # Анализ тренда
        if change_24h > 3:
            analysis['trend_strength'] = 'strong_up'
            analysis['reasoning'].append("🚀 Сильный восходящий тренд")
            analysis['opportunity_score'] += 0.3
        elif change_24h < -3:
            analysis['trend_strength'] = 'strong_down'
            analysis['reasoning'].append("🔻 Сильный нисходящий тренд")
            analysis['opportunity_score'] += 0.2
        
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
    
    def make_trading_decision(self, symbol: str, price_data: Dict) -> Dict:
        """Принимает торговое решение на основе анализа"""
        analysis = self.analyze_market_conditions(
            symbol, 
            price_data['current'], 
            price_data['volume_24h'], 
            price_data['change_24h']
        )
        
        # Сохраняем анализ
        self.current_market_analysis[symbol] = analysis
        
        # Логируем решение
        if self.log_callback:
            self.log_callback(f"🧠 Анализ {symbol}:", "INFO")
            for reason in analysis['reasoning']:
                self.log_callback(f"   {reason}", "INFO")
            self.log_callback(f"   Решение: {analysis['recommendation']} (уверенность: {analysis['confidence']:.1%})", "SIGNAL")
        
        return analysis
    
    def learn_from_trade(self, trade_result: Dict):
        """Учится на основе результата сделки"""
        insight = {
            'timestamp': datetime.now().isoformat(),
            'symbol': trade_result['symbol'],
            'entry_price': trade_result['entry_price'],
            'exit_price': trade_result['exit_price'],
            'pnl': trade_result['pnl'],
            'pnl_pct': trade_result['pnl_pct'],
            'duration': trade_result['duration'],
            'analysis_at_entry': trade_result.get('analysis_at_entry', {}),
            'lessons_learned': []
        }
        
        # Анализируем результат
        if trade_result['pnl_pct'] > 0:
            insight['lessons_learned'].append("✅ Успешная сделка - условия входа были правильными")
            if trade_result['pnl_pct'] > 2:
                insight['lessons_learned'].append("🎯 Отличный результат - можно увеличить размер позиции")
        else:
            insight['lessons_learned'].append("❌ Убыточная сделка - нужно пересмотреть критерии входа")
            if trade_result['pnl_pct'] < -2:
                insight['lessons_learned'].append("⚠️ Большие потери - требуется улучшение управления рисками")
        
        # Анализируем длительность
        if trade_result['duration'] < 300:  # 5 минут
            insight['lessons_learned'].append("⚡ Быстрая сделка - возможно, нужно дольше держать позицию")
        elif trade_result['duration'] > 3600:  # 1 час
            insight['lessons_learned'].append("⏰ Долгая сделка - возможно, нужно быстрее фиксировать прибыль")
        
        self.learning_insights.append(insight)
        
        # Логируем урок
        if self.log_callback:
            self.log_callback(f"📚 Урок по {trade_result['symbol']}:", "INFO")
            for lesson in insight['lessons_learned']:
                self.log_callback(f"   {lesson}", "INFO")
    
    def get_recent_insights(self, limit: int = 5) -> List[str]:
        """Возвращает последние уроки"""
        recent_insights = []
        for insight in self.learning_insights[-limit:]:
            for lesson in insight['lessons_learned']:
                recent_insights.append(f"{insight['symbol']}: {lesson}")
        return recent_insights

class TradingOpportunityFinder:
    """Поиск торговых возможностей"""
    
    def __init__(self, log_callback: Optional[Callable] = None):
        self.log_callback = log_callback
    
    def search_trading_opportunities(self, prices: Dict):
        """Ищет торговые возможности на основе анализа"""
        try:
            # Анализируем каждую монету на предмет торговых сигналов
            opportunities = []
            
            for symbol, price_data in prices.items():
                # Простые критерии для торговых сигналов
                change_24h = price_data['change_24h']
                volume = price_data['volume_24h']
                
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
            if opportunities:
                if self.log_callback:
                    self.log_callback("🎯 Найденные торговые возможности:", "SIGNAL")
                    for opp in opportunities[:5]:  # Показываем максимум 5 возможностей
                        self.log_callback(f"   • {opp}", "INFO")
            else:
                if self.log_callback:
                    self.log_callback("🔍 Торговых возможностей не найдено - жду лучших условий", "INFO")
                    
        except Exception as e:
            # Тихо обрабатываем ошибки поиска возможностей
            pass
    
    def add_simple_market_analysis(self, prices: Dict, log_callback: Callable):
        """Добавляет простой анализ рынка (fallback)"""
        try:
            # Анализируем текущее состояние рынка
            positive_count = sum(1 for data in prices.values() if data['change_24h'] > 0)
            negative_count = sum(1 for data in prices.values() if data['change_24h'] < 0)
            total_coins = len(prices)
            
            # Анализ рынка
            
            # Определяем настроение рынка
            if positive_count > total_coins * 0.6:
                sentiment = "📈 Бычий рынок"
                analysis = "Большинство монет растут, ищу возможности для LONG позиций"
            elif negative_count > total_coins * 0.6:
                sentiment = "📉 Медвежий рынок"
                analysis = "Большинство монет падают, ищу возможности для SHORT позиций"
            else:
                sentiment = "➡️ Боковой рынок"
                analysis = "Рынок в боковике, жду четких сигналов для входа"
            
            # Находим топ-монеты
            sorted_coins = sorted(prices.items(), key=lambda x: abs(x[1]['change_24h']), reverse=True)
            top_volatile = [f"{symbol}: {data['change_24h']:+.1f}%" for symbol, data in sorted_coins[:3]]
            
            # Формируем сообщение
            message = f"🧠 Анализ рынка: {sentiment} | {analysis} | Топ волатильность: {' | '.join(top_volatile)}"
            log_callback(message, "SIGNAL")
            
            # Добавляем поиск торговых возможностей
            self.search_trading_opportunities(prices)
            
        except Exception as e:
            # Тихо обрабатываем ошибки анализа
            pass
    
    def add_market_summary(self, prices: Dict, log_callback: Callable):
        """Добавляет сводку по рынку"""
        try:
            positive_count = sum(1 for data in prices.values() if data['change_24h'] > 0)
            negative_count = sum(1 for data in prices.values() if data['change_24h'] < 0)
            total_coins = len(prices)
            
            summary = f"📊 Сводка: Рост: {positive_count} | Падение: {negative_count} | Всего: {total_coins}"
            log_callback(summary, "METRICS")
            
            if positive_count > negative_count * 1.5:
                log_callback("🎯 Общее настроение: БЫЧЬЕ", "SIGNAL")
            elif negative_count > positive_count * 1.5:
                log_callback("🎯 Общее настроение: МЕДВЕЖЬЕ", "SIGNAL")
            else:
                log_callback("🎯 Общее настроение: НЕЙТРАЛЬНОЕ", "INFO")
                
        except Exception as e:
            # Тихо обрабатываем ошибки сводки рынка
            pass 