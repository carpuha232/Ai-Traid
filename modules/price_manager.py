"""
💰 Менеджер цен для торгового дашборда
Управляет получением и обновлением цен
Интегрирован с OnlineDataManager для прямого доступа к Binance API
"""

import random
import time
import threading
import tkinter as tk
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import requests

# Импортируем новый онлайн менеджер данных
from online_data_manager import get_data_manager, initialize_data_manager

class PriceManager:
    """Менеджер цен для торгового дашборда с прямым доступом к публичному Binance API"""
    def __init__(self, symbols: List[str], simulation=None):
        self.symbols = symbols
        self.simulation = None
        self.prices = {}
        self.price_history = {}
        self.initialize_prices()

    def initialize_prices(self):
        for symbol in self.symbols:
            self.prices[symbol] = {
                'current': 0.0,
                'previous': 0.0,
                'change_24h': 0.0,
                'volume_24h': 0,
                'high_24h': 0.0,
                'low_24h': 0.0
            }
            self.price_history[symbol] = []

    def simulate_price_change(self) -> bool:
        """Получение реальных цен с Binance API (публичный endpoint)"""
        base_url = "https://api.binance.com/api/v3/ticker/price"
        updated_count = 0
        for symbol in self.symbols:
            try:
                resp = requests.get(base_url, params={"symbol": symbol}, timeout=5)
                resp.raise_for_status()
                data = resp.json()
                price = float(data['price'])
                price_data = self.prices[symbol]
                price_data['previous'] = price_data['current']
                price_data['current'] = price
                # Обновляем high/low
                if price_data['current'] > price_data['high_24h']:
                    price_data['high_24h'] = price_data['current']
                if price_data['current'] < price_data['low_24h'] or price_data['low_24h'] == 0.0:
                    price_data['low_24h'] = price_data['current']
                self.price_history[symbol].append(price_data['current'])
                if len(self.price_history[symbol]) > 100:
                    self.price_history[symbol].pop(0)
                updated_count += 1
            except Exception:
                continue
        return updated_count > 0

    def _get_online_prices(self) -> bool:
        try:
            if not self.data_manager:
                return False
            
            # Получаем цены напрямую (это не корутина)
            current_prices = self.data_manager.get_all_current_prices()
            
            if not current_prices or not isinstance(current_prices, dict) or len(current_prices) == 0:
                return False  # Всегда fallback если нет цен
            updated_count = 0
            for symbol in self.symbols:
                if symbol in current_prices and symbol in self.prices:
                    price_data = self.prices[symbol]
                    new_price = current_prices[symbol]
                    if new_price is not None and new_price > 0:
                        price_data['previous'] = price_data['current']
                        price_data['current'] = new_price
                        if price_data['previous'] > 0:
                            change_percent = ((price_data['current'] - price_data['previous']) / price_data['previous']) * 100
                            price_data['change_24h'] = change_percent
                        if price_data['current'] > price_data['high_24h']:
                            price_data['high_24h'] = price_data['current']
                        if price_data['current'] < price_data['low_24h']:
                            price_data['low_24h'] = price_data['current']
                        self.price_history[symbol].append(price_data['current'])
                        if len(self.price_history[symbol]) > 100:
                            self.price_history[symbol].pop(0)
                        updated_count += 1
            if updated_count > 0:
                return True
            return False
        except Exception as e:
            # Тихо обрабатываем ошибки получения цен
            return False
    
    def _simulate_prices(self):
        """Симуляция отключена - используем только реальные цены"""
        # Ничего не делаем - ждем реальные цены с API
        pass
    
    def _get_real_prices(self):
        """Получение реальных цен с API (отключено)"""
        # Функция отключена - используем только онлайн данные
        return 0, False
    
    def get_price_data(self, symbol: str) -> Dict:
        """Получение данных цены для символа"""
        return self.prices.get(symbol, {})
    
    def get_all_prices(self) -> Dict:
        """Получение всех цен"""
        return self.prices
    
    def get_price_history(self, symbol: str) -> List[float]:
        """Получение истории цен для символа"""
        return self.price_history.get(symbol, [])
    
    def update_price(self, symbol: str, price: float, volume: float = None):
        """Обновление цены для символа"""
        if symbol in self.prices:
            price_data = self.prices[symbol]
            price_data['previous'] = price_data['current']
            price_data['current'] = price
            
            if volume is not None:
                price_data['volume_24h'] = volume
            
            # Добавляем в историю
            self.price_history[symbol].append(price)
            if len(self.price_history[symbol]) > 100:
                self.price_history[symbol].pop(0)

class CoinCard:
    """Карточка монеты для отображения в сетке"""
    
    def __init__(self, parent, symbol: str, colors):
        self.symbol = symbol
        self.colors = colors
        self.card = None
        self.labels = {}
        
        self.create_card(parent)
    
    def create_card(self, parent):
        """Создание компактной карточки монеты"""
        # Карточка с закругленными углами, растягивается по ширине
        self.card = tk.Frame(parent, bg=self.colors.colors['bg_dark'], 
                           relief=tk.FLAT, bd=0)
        
        # Canvas для карточки с закругленными углами
        card_canvas = tk.Canvas(self.card, bg=self.colors.colors['bg_card'], 
                              highlightthickness=0, height=80)
        card_canvas.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        # Функция для отрисовки закругленного фона с адаптивной шириной
        def draw_card_background():
            canvas_width = card_canvas.winfo_width()
            canvas_height = card_canvas.winfo_height()
            if canvas_width > 0 and canvas_height > 0:
                card_canvas.delete("all")
                from trading_bot.ui_components import RoundedCanvas
                RoundedCanvas.create_rounded_rectangle(card_canvas, 0, 0, canvas_width, canvas_height, 6, 
                                                    fill=self.colors.colors['bg_card'], 
                                                    outline=self.colors.colors['blue'], width=1)
        
        # Привязываем функцию к изменению размера canvas
        card_canvas.bind('<Configure>', lambda e: draw_card_background())
        
        # Вызываем функцию один раз для начальной отрисовки
        root = parent.winfo_toplevel()
        root.after(100, draw_card_background)
        
        # Заголовок (символ)
        symbol_label = tk.Label(card_canvas, text=self.symbol, 
                               font=("Arial", 12, "bold"),
                               fg=self.colors.colors['text_white'], 
                               bg=self.colors.colors['bg_card'])
        symbol_label.pack(anchor=tk.W, padx=(5, 0), pady=(2, 0))
        # Цена (крупно) - отдельный label
        price_label = tk.Label(card_canvas, text="$0.00", 
                              font=("Arial", 16, "bold"),
                              fg=self.colors.colors['text_white'], 
                              bg=self.colors.colors['bg_card'])
        price_label.pack(anchor=tk.W, padx=(5, 0))
        
        # Изменение цены
        change_label = tk.Label(card_canvas, text="0.00%", 
                               font=("Arial", 12),
                               fg=self.colors.colors['text_gray'], 
                               bg=self.colors.colors['bg_card'])
        change_label.pack(anchor=tk.W, padx=(5, 0))
        
        # Объем (компактно)
        volume_label = tk.Label(card_canvas, text="Vol: $0", 
                               font=("Arial", 10),
                               fg=self.colors.colors['text_gray'], 
                               bg=self.colors.colors['bg_card'])
        volume_label.pack(anchor=tk.W, padx=(5, 0), pady=(0, 2))
        
        # Сохраняем ссылки на метки в словаре
        self.labels = {
            'price': price_label,
            'change': change_label,
            'volume': volume_label,
            'symbol': symbol_label
        }
    
    def update_card(self, price_data: Dict):
        """Обновление карточки монеты"""
        if not price_data:
            return
        
        # Форматирование цены
        current_price = price_data['current']
        if current_price >= 1:
            price_text = f"${current_price:.2f}"
        elif current_price >= 0.01:
            price_text = f"${current_price:.4f}"
        else:
            price_text = f"${current_price:.8f}"
        
        if hasattr(self, 'card') and self.card is not None and 'price' in self.labels and self.labels['price'] is not None:
            self.labels['price'].config(text=price_text)
        
        # Изменение цены с цветовой индикацией
        change_24h = price_data['change_24h']
        if change_24h > 0:
            change_text = f"+{change_24h:.1f}%"
            change_color = self.colors.colors['green']
        elif change_24h < 0:
            change_text = f"{change_24h:.1f}%"
            change_color = self.colors.colors['red']
        else:
            change_text = f"{change_24h:.1f}%"
            change_color = self.colors.colors['text_gray']
        
        if hasattr(self, 'card') and self.card is not None and 'change' in self.labels and self.labels['change'] is not None:
            self.labels['change'].config(text=change_text, fg=change_color)
        
        # Объем (компактно)
        volume = price_data['volume_24h']
        if volume >= 1_000_000_000:
            volume_text = f"Vol: ${volume/1_000_000_000:.1f}B"
        elif volume >= 1_000_000:
            volume_text = f"Vol: ${volume/1_000_000:.1f}M"
        else:
            volume_text = f"Vol: ${volume/1_000:.1f}K"
        
        if hasattr(self, 'card') and self.card is not None and 'volume' in self.labels and self.labels['volume'] is not None:
            self.labels['volume'].config(text=volume_text)
        
        # Анимация изменения цены
        if price_data['current'] > price_data['previous']:
            if hasattr(self, 'card') and self.card is not None:
                self.card.configure(bg=self.colors.colors['green'])
                self.card.after(200, lambda: self.card.configure(bg=self.colors.colors['bg_dark']))
        elif price_data['current'] < price_data['previous']:
            if hasattr(self, 'card') and self.card is not None:
                self.card.configure(bg=self.colors.colors['red'])
                self.card.after(200, lambda: self.card.configure(bg=self.colors.colors['bg_dark']))
    
    def get_widget(self):
        """Получение виджета карточки"""
        return self.card