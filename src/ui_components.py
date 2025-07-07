"""
🎨 UI компоненты для торгового дашборда
Компоненты интерфейса: карточки монет, панели, кнопки
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime
from typing import Dict, List

class UIColors:
    """Современная цветовая схема с градиентными оттенками"""
    
    def __init__(self):
        self.colors = {
            # Основные цвета фона
            'bg_dark': '#0a0a0a',           # Очень тёмный фон
            'bg_card': '#1a1a1a',           # Карточки
            'bg_header': '#2d2d2d',         # Заголовки
            
            # Текст
            'text_white': '#ffffff',        # Белый текст
            'text_gray': '#b0b0b0',         # Серый текст
            
            # Акцентные цвета
            'blue': '#6366f1',              # Современный синий
            'green': '#10b981',             # Современный зелёный
            'red': '#ef4444',               # Современный красный
            'yellow': '#f59e0b',            # Современный жёлтый
            'cyan': '#06b6d4',              # Современный циан
            'purple': '#8b5cf6',            # Современный фиолетовый
            'orange': '#f97316',            # Современный оранжевый
            'pink': '#ec4899',              # Современный розовый
            
            # Дополнительные оттенки
            'blue_light': '#818cf8',        # Светлый синий
            'green_light': '#34d399',       # Светлый зелёный
            'red_light': '#f87171',         # Светлый красный
            'yellow_light': '#fbbf24',      # Светлый жёлтый
        }

class RoundedCanvas:
    """Canvas с закругленными углами"""
    
    @staticmethod
    def create_rounded_rectangle(canvas, x1, y1, x2, y2, radius, **kwargs):
        """Создание закругленного прямоугольника на canvas"""
        # Создаем закругленный прямоугольник
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1
        ]
        
        # Рисуем основной прямоугольник
        canvas.create_polygon(points, smooth=True, **kwargs)
        
        # Рисуем закругленные углы
        canvas.create_arc(x1, y1, x1 + 2*radius, y1 + 2*radius, 
                         start=90, extent=90, **kwargs)
        canvas.create_arc(x2 - 2*radius, y1, x2, y1 + 2*radius, 
                         start=0, extent=90, **kwargs)
        canvas.create_arc(x2 - 2*radius, y2 - 2*radius, x2, y2, 
                         start=270, extent=90, **kwargs)
        canvas.create_arc(x1, y2 - 2*radius, x1 + 2*radius, y2, 
                         start=180, extent=90, **kwargs)

class TradingStatsPanel:
    """Панель статистики торговли"""
    
    def __init__(self, parent, colors: UIColors):
        self.colors = colors
        self.trading_stats_labels = {}
        self.api_status_var = tk.StringVar(value="API: ...")
        self.trading_time_label = None
        
        self.create_panel(parent)
    
    def create_panel(self, parent):
        """Создание панели статистики торговли"""
        stats_frame = tk.Frame(parent, bg=self.colors.colors['bg_dark'], height=60)
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        stats_frame.pack_propagate(False)
        
        # Canvas для статистики с закругленными углами
        stats_canvas = tk.Canvas(stats_frame, bg=self.colors.colors['bg_header'], 
                               highlightthickness=0, height=60)
        stats_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        
        # Рисуем закругленный фон для статистики
        RoundedCanvas.create_rounded_rectangle(stats_canvas, 0, 0, 1920, 60, 8, 
                                            fill=self.colors.colors['bg_header'], 
                                            outline=self.colors.colors['blue'], width=1)
        
        # Статистика торговли
        trading_stats = [
            ("💰 Баланс: $100.00", self.colors.colors['yellow']),
            ("📈 Винрейт: 0.0%", self.colors.colors['green']),
            ("📊 Сделок: 0", self.colors.colors['cyan']),
            ("💵 PnL: $0.00", self.colors.colors['text_white']),
            ("🎯 Прибыльных: 0", self.colors.colors['green']),
            ("❌ Убыточных: 0", self.colors.colors['red']),
            ("📉 Макс. просадка: 0.0%", self.colors.colors['orange']),
            ("⚡ Открытых позиций: 0", self.colors.colors['purple'])
        ]
        
        for i, (text, color) in enumerate(trading_stats):
            label = tk.Label(stats_canvas, text=text, 
                           font=("Arial", 11, "bold"),
                           fg=color, 
                           bg=self.colors.colors['bg_header'])
            label.pack(side=tk.LEFT, padx=15)
            self.trading_stats_labels[text] = label
        
        # Статус API справа
        api_status_label = tk.Label(stats_canvas, textvariable=self.api_status_var, 
                                  font=("Arial", 10, "bold"), 
                                  fg=self.colors.colors['yellow'], 
                                  bg=self.colors.colors['bg_header'])
        api_status_label.pack(side=tk.RIGHT, padx=10)
        
        # Время справа
        self.trading_time_label = tk.Label(stats_canvas, text="", 
                                         font=("Arial", 11, "bold"),
                                         fg=self.colors.colors['text_white'], 
                                         bg=self.colors.colors['bg_header'])
        self.trading_time_label.pack(side=tk.RIGHT, padx=20)
    
    def update_trading_stats(self, simulation):
        """Обновляет статистику торговли (отключено)"""
        return
        
        # Рассчитываем винрейт
        winrate = 0.0
        if stats['total_trades'] > 0:
            winrate = (stats['winning_trades'] / stats['total_trades']) * 100
        
        # Рассчитываем просадку
        max_drawdown = 0.0
        if simulation.initial_balance > 0:
            current_drawdown = ((simulation.initial_balance - balance) / simulation.initial_balance) * 100
            max_drawdown = max(max_drawdown, current_drawdown)
        
        # Обновляем метки
        self.trading_stats_labels["💰 Баланс: $100.00"].config(
            text=f"💰 Баланс: ${balance:.2f}")
        
        self.trading_stats_labels["📈 Винрейт: 0.0%"].config(
            text=f"📈 Винрейт: {winrate:.1f}%")
        
        self.trading_stats_labels["📊 Сделок: 0"].config(
            text=f"📊 Сделок: {stats['total_trades']}")
        
        self.trading_stats_labels["💵 PnL: $0.00"].config(
            text=f"💵 PnL: ${stats['total_pnl']:+.2f}")
        
        self.trading_stats_labels["🎯 Прибыльных: 0"].config(
            text=f"🎯 Прибыльных: {stats['winning_trades']}")
        
        self.trading_stats_labels["❌ Убыточных: 0"].config(
            text=f"❌ Убыточных: {stats['losing_trades']}")
        
        self.trading_stats_labels["📉 Макс. просадка: 0.0%"].config(
            text=f"📉 Макс. просадка: {max_drawdown:.1f}%")
        
        self.trading_stats_labels["⚡ Открытых позиций: 0"].config(
            text=f"⚡ Открытых позиций: {len(simulation.open_positions)}")
    
    def update_time(self, root):
        """Обновление времени"""
        def update_trading_time():
            current_time = datetime.now().strftime("%H:%M:%S")
            if self.trading_time_label:
                self.trading_time_label.config(text=f"🕐 {current_time}")
            root.after(1000, update_trading_time)
        
        update_trading_time()

class MarketTicker:
    """Бегущая строка с состоянием рынка"""
    
    def __init__(self, parent, colors: UIColors):
        self.colors = colors
        self.ticker_position = 0
        self.market_data = {
            'total_market_cap': 0,
            'total_volume_24h': 0,
            'bitcoin_dominance': 0,
            'market_sentiment': 'neutral',
            'top_gainers': [],
            'top_losers': []
        }
        
        self.create_ticker(parent)
    
    def create_ticker(self, parent):
        """Создание бегущей строки с состоянием рынка"""
        ticker_frame = tk.Frame(parent, bg=self.colors.colors['bg_dark'], height=35)
        ticker_frame.pack(fill=tk.X, pady=(0, 10))
        ticker_frame.pack_propagate(False)
        
        # Canvas для бегущей строки с закругленными углами
        self.ticker_canvas = tk.Canvas(ticker_frame, bg=self.colors.colors['bg_header'], 
                                     highlightthickness=0, height=35)
        self.ticker_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        
        # Рисуем закругленный фон для бегущей строки
        RoundedCanvas.create_rounded_rectangle(self.ticker_canvas, 0, 0, 1920, 35, 8, 
                                            fill=self.colors.colors['bg_header'], 
                                            outline=self.colors.colors['blue'], width=1)
    
    def update_market_data(self, prices: Dict):
        """Обновление данных о состоянии рынка"""
        # Расчет данных рынка на основе реальных цен
        total_market_cap = sum(price_data['current'] * 1000000 
                              for price_data in prices.values())
        
        total_volume = sum(price_data['volume_24h'] for price_data in prices.values())
        
        # Определяем топ-монеты
        sorted_coins = sorted(prices.items(), 
                            key=lambda x: x[1]['change_24h'], reverse=True)
        
        top_gainers = [f"{symbol}: +{data['change_24h']:.1f}%" 
                      for symbol, data in sorted_coins[:3]]
        top_losers = [f"{symbol}: {data['change_24h']:.1f}%" 
                     for symbol, data in sorted_coins[-3:]]
        
        # Определяем настроение рынка
        positive_count = sum(1 for data in prices.values() if data['change_24h'] > 0)
        if positive_count > len(prices) * 0.7:
            sentiment = "bullish"
        elif positive_count < len(prices) * 0.3:
            sentiment = "bearish"
        else:
            sentiment = "neutral"
        
        self.market_data = {
            'total_market_cap': total_market_cap,
            'total_volume_24h': total_volume,
            'bitcoin_dominance': 45.5,
            'market_sentiment': sentiment,
            'top_gainers': top_gainers,
            'top_losers': top_losers
        }
    
    def animate_ticker(self, root):
        """Анимация бегущей строки рынка"""
        # Очищаем canvas
        self.ticker_canvas.delete("all")
        
        # Получаем размеры canvas
        canvas_width = self.ticker_canvas.winfo_width()
        canvas_height = self.ticker_canvas.winfo_height()
        
        if canvas_width > 0:
            # Формируем текст бегущей строки
            sentiment_emoji = {
                'bullish': '📈',
                'bearish': '📉',
                'neutral': '➡️'
            }
            
            ticker_text = (
                f"🌐 РЫНОК КРИПТОВАЛЮТ • "
                f"Капитализация: ${self.market_data['total_market_cap']/1e12:.1f}T • "
                f"Объем 24ч: ${self.market_data['total_volume_24h']/1e9:.1f}B • "
                f"BTC доминирование: {self.market_data['bitcoin_dominance']:.1f}% • "
                f"Настроение: {sentiment_emoji[self.market_data['market_sentiment']]} "
                f"{self.market_data['market_sentiment'].upper()} • "
                f"Топ рост: {' | '.join(self.market_data['top_gainers'])} • "
                f"Топ падение: {' | '.join(self.market_data['top_losers'])} • "
            )
            
            # Создаем текст бегущей строки
            text_id = self.ticker_canvas.create_text(
                canvas_width - self.ticker_position, 
                canvas_height // 2,
                text=ticker_text,
                font=("Arial", 12, "bold"),
                fill=self.colors.colors['text_white'],
                anchor=tk.W
            )
            
            # Дублируем текст для бесконечной прокрутки
            text_width = self.ticker_canvas.bbox(text_id)[2] - self.ticker_canvas.bbox(text_id)[0]
            if self.ticker_position > text_width:
                self.ticker_canvas.create_text(
                    canvas_width - self.ticker_position + text_width, 
                    canvas_height // 2,
                    text=ticker_text,
                    font=("Arial", 12, "bold"),
                    fill=self.colors.colors['text_white'],
                    anchor=tk.W
                )
            
            # Обновляем позицию
            self.ticker_position += 1.5
            if self.ticker_position > text_width:
                self.ticker_position = 0
        
        # Планируем следующее обновление
        root.after(50, lambda: self.animate_ticker(root))

class CompactStatsPanel:
    """Компактная панель статистики"""
    
    def __init__(self, parent, colors: UIColors):
        self.colors = colors
        self.stats_labels = {}
        self.time_label = None
        
        self.create_panel(parent)
    
    def create_panel(self, parent):
        """Создание компактной статистики"""
        stats_frame = tk.Frame(parent, bg=self.colors.colors['bg_dark'], height=40)
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        stats_frame.pack_propagate(False)
        
        # Canvas для статистики с закругленными углами
        stats_canvas = tk.Canvas(stats_frame, bg=self.colors.colors['bg_header'], 
                               highlightthickness=0, height=40)
        stats_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        
        # Рисуем закругленный фон для статистики
        RoundedCanvas.create_rounded_rectangle(stats_canvas, 0, 0, 1920, 40, 8, 
                                            fill=self.colors.colors['bg_header'], 
                                            outline=self.colors.colors['blue'], width=1)
        
        # Статистика в одну строку
        stats_data = [
            ("📊 30", "#06b6d4"),
            ("📈 0", "#10b981"),
            ("📉 0", "#ef4444"),
            ("💰 $0", "#f59e0b"),
            ("⚡ 30", "#8b5cf6")
        ]
        
        for i, (text, color) in enumerate(stats_data):
            label = tk.Label(stats_canvas, text=text, 
                           font=("Arial", 12, "bold"),
                           fg=color, 
                           bg=self.colors.colors['bg_header'])
            label.pack(side=tk.LEFT, padx=20)
            self.stats_labels[text] = label
        
        # Время справа
        self.time_label = tk.Label(stats_canvas, text="", 
                                 font=("Arial", 12, "bold"),
                                 fg=self.colors.colors['text_white'], 
                                 bg=self.colors.colors['bg_header'])
        self.time_label.pack(side=tk.RIGHT, padx=20)
    
    def update_statistics(self, prices: Dict):
        """Обновление статистики"""
        positive_count = 0
        negative_count = 0
        total_volume = 0
        
        for symbol, price_data in prices.items():
            if price_data['change_24h'] > 0:
                positive_count += 1
            elif price_data['change_24h'] < 0:
                negative_count += 1
            
            total_volume += price_data['volume_24h']
        
        # Обновляем метки статистики
        self.stats_labels["📈 0"].config(text=f"📈 {positive_count}")
        self.stats_labels["📉 0"].config(text=f"📉 {negative_count}")
        
        if total_volume >= 1_000_000_000:
            volume_text = f"💰 ${total_volume/1_000_000_000:.1f}B"
        elif total_volume >= 1_000_000:
            volume_text = f"💰 ${total_volume/1_000_000:.1f}M"
        else:
            volume_text = f"💰 ${total_volume/1_000:.1f}K"
        
        self.stats_labels["💰 $0"].config(text=volume_text)
    
    def update_time(self, root):
        """Обновление времени"""
        def update_time():
            current_time = datetime.now().strftime("%H:%M:%S")
            if self.time_label:
                self.time_label.config(text=f"🕐 {current_time}")
            root.after(1000, update_time)
        
        update_time() 