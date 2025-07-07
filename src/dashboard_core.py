"""
🎨 Основная логика торгового дашборда
Инициализация, настройки, основные методы
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
from datetime import datetime
import random
from typing import Dict, List

# Импорты модулей
try:
    from trading_bot.ui_components import UIColors
    from trading_bot.price_manager import PriceManager
    from trading_bot.terminal_manager import AITradingSystem, TradingOpportunityFinder
    from trading_bot.online_data_manager import get_data_manager, initialize_data_manager
    UI_MODULES_AVAILABLE = True
    ONLINE_DATA_AVAILABLE = True
except ImportError:
    print("⚠️ UI модули не найдены")
    UI_MODULES_AVAILABLE = False
    ONLINE_DATA_AVAILABLE = False
    # Fallback классы
    class UIColors:
        def __init__(self):
            self.colors = {
                'bg_dark': '#0f1419', 'bg_card': '#1a1f2e', 'bg_header': '#2d3748',
                'text_white': '#ffffff', 'text_gray': '#a0aec0', 'green': '#48bb78',
                'red': '#f56565', 'blue': '#4299e1', 'yellow': '#ed8936',
                'purple': '#9f7aea', 'cyan': '#38b2ac', 'orange': '#ed64a6'
            }
    
    class PriceManager:
        def __init__(self, symbols, simulation=None): pass
    
    class AITradingSystem:
        def __init__(self, log_callback=None): pass
        def get_recent_insights(self, limit=5): return []
    
    class TradingOpportunityFinder:
        def __init__(self, log_callback=None): pass

# Импорты внешних модулей
try:
    from ai_integration import AIInterface, AIRightPanel
except ImportError:
    print("⚠️ Модуль ИИ интеграции не найден")
    AIInterface = None
    AIRightPanel = None



try:
    from trading_bot.multi_timeframe_analyzer import MultiTimeframeAnalyzer
    from trading_bot.ai_analysis_engine import AIAnalysisEngine
    PANDAS_AVAILABLE = True
except ImportError:
    print("⚠️ Модули анализа не найдены")
    MultiTimeframeAnalyzer = None
    AIAnalysisEngine = None
    PANDAS_AVAILABLE = False

# Используем классы из модулей
if UI_MODULES_AVAILABLE:
    IntelligentTradingSystem = AITradingSystem
else:
    # Fallback класс
    class IntelligentTradingSystem:
        """Интеллектуальная система принятия торговых решений (fallback)"""
        
        def __init__(self, log_callback=None):
            self.log_callback = log_callback
            self.trading_history = []
            self.learning_insights = []
            self.current_market_analysis = {}
            self.decision_reasons = {}
        
        def get_recent_insights(self, limit: int = 5):
            return []

class Colors:
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

class DashboardCore:
    """Основная логика торгового дашборда"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("📊 Компактный торговый терминал")
        self.root.geometry("1920x1080")
        
        # Инициализация цветовой схемы
        self.colors = UIColors()
        
        # Инициализация переменной статуса API
        self.api_status_var = tk.StringVar()
        self.futures_balance_var = tk.StringVar()
        
        # Устанавливаем фон корневого окна
        self.root.configure(bg=self.colors.colors['bg_dark'])
        
        # Настройки торговых пар
        self.symbols = [
            'BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'XRPUSDT', 'DOTUSDT',
            'LINKUSDT', 'LTCUSDT', 'BCHUSDT', 'EOSUSDT', 'TRXUSDT',
            'XLMUSDT', 'VETUSDT', 'FILUSDT', 'AAVEUSDT', 'ALGOUSDT',
            'NEARUSDT', 'FTMUSDT', 'SANDUSDT', 'MANAUSDT', 'AXSUSDT',
            'GALAUSDT', 'CHZUSDT', 'MATICUSDT', 'SOLUSDT', 'AVAXUSDT',
            'ATOMUSDT', 'UNIUSDT', 'CAKEUSDT', 'DOGEUSDT', 'SHIBUSDT'
        ]
        
        self.logic = None  # Позволяет присваивать self.core.logic
        self.ui = None     # Позволяет присваивать self.core.ui
        
        # Инициализация компонентов
        self._init_online_data_manager()
        self._init_price_manager()
        self._init_intelligent_system()
        self._init_analysis_engines()
        self._init_simulation()
        self._init_opportunity_finder()
        
        # Инициализационные сообщения
        self._send_init_messages()
    
    def _init_online_data_manager(self):
        """Инициализация онлайн менеджера данных"""
        self.online_data_manager = None
        if ONLINE_DATA_AVAILABLE:
            try:
                self.online_data_manager = get_data_manager()
            except Exception as e:
                # Тихо обрабатываем ошибки инициализации
                self.online_data_manager = None
        else:
            pass
    
    def _init_price_manager(self):
        """Инициализация менеджера цен с онлайн данными"""
        # Всегда инициализируем цены
        self.prices = {}
        self.price_history = {}
        
        if UI_MODULES_AVAILABLE:
            # Передаем правильный simulation engine, а не online_data_manager
            self.price_manager = PriceManager(self.symbols, simulation=None)
        else:
            self.price_manager = None
        
        # Всегда инициализируем цены
        self.initialize_prices()
    
    def _init_intelligent_system(self):
        """Инициализация интеллектуальной системы"""
        self.intelligent_system = IntelligentTradingSystem(self.add_terminal_message)
    
    def _init_analysis_engines(self):
        """Инициализация анализаторов (отключено)"""
        self.multi_timeframe_analyzer = None
        self.ai_analysis_engine = None
    
    def _init_simulation(self):
        """Инициализация симуляции (отключено)"""
        self.simulation = None
    
    def _init_opportunity_finder(self):
        """Инициализация поисковика возможностей"""
        if UI_MODULES_AVAILABLE:
            self.opportunity_finder = TradingOpportunityFinder(self.add_terminal_message)
        else:
            self.opportunity_finder = None
    
    def _send_init_messages(self):
        """Отправка инициализационных сообщений"""
        self.add_terminal_message("🚀 Система торгового терминала инициализирована", "SUCCESS")
        self.add_terminal_message("🧠 Интеллектуальная система анализа готова к работе", "INFO")
        
        # Система готова к работе
        self.add_terminal_message("🎯 Система готова к торговле", "SUCCESS")
    
    def initialize_prices(self):
        """Инициализация начальных цен - только реальные цены с API"""
        # Инициализируем структуры данных без фиксированных цен
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
    
    def add_terminal_message(self, message: str, level: str = "INFO"):
        """Добавляет сообщение в терминал (должен быть переопределен в наследнике)"""
        print(f"[{level}] {message}")
    
    def start_price_updates(self):
        """Запуск обновления цен (должен быть переопределен в наследнике)"""
        pass
    
    def setup_compact_ui(self):
        """Настройка интерфейса (должен быть переопределен в наследнике)"""
        pass 

    def update_dashboard(self):
        """Обновляет все элементы дашборда"""
        try:
            # Обновляем торговую статистику если доступна
            if hasattr(self, 'ui') and hasattr(self.ui, 'update_trading_stats'):
                self.ui.update_trading_stats()
            
            # Планируем следующее обновление
            self.root.after(1000, self.update_dashboard)
            
        except Exception as e:
            # Тихо обрабатываем ошибки обновления
            self.root.after(5000, self.update_dashboard)  # Повторяем через 5 секунд 