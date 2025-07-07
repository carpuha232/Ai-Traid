"""
🎨 UI компоненты торгового дашборда
Создание интерфейса, панелей, карточек
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime, timedelta
import time
from typing import Dict, List, Optional
import random

class DashboardUI:
    """UI компоненты торгового дашборда"""
    
    def __init__(self, dashboard_core):
        self.core = dashboard_core
        self.colors = dashboard_core.colors
        
        # UI элементы
        self.coin_cards = {}
        self.trading_stats_labels = {}
        self.stats_labels = {}
        self.terminal_text = None
        self.positions_table = None
        self.ticker_canvas = None
        self.ticker_position = 0
        self.market_data = {}
        self.status_var = None
        self.trading_time_label = None
        self.time_label = None
        self.positions_frame = None
        self.start_sim_button = None
        self.stop_sim_button = None
    
    def setup_compact_ui(self):
        """Настройка компактного интерфейса с пустым местом снизу 20% высоты"""
        # Главный контейнер
        main_frame = tk.Frame(self.core.root, bg=self.colors.colors['bg_dark'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Создаем пустое место снизу ПЕРВЫМ (20% высоты)
        self.create_empty_bottom_space(main_frame)
        
        # Создаем основной контент ВТОРЫМ (80% высоты)
        self.create_main_content(main_frame)
    
    def create_main_content(self, parent):
        """Создание основного контента (80% высоты)"""
        # Основной контент занимает оставшееся место сверху
        content_frame = tk.Frame(parent, bg=self.colors.colors['bg_dark'])
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # ЕДИНАЯ шапка - объединяем все в одну панель
        self.create_unified_header_panel(content_frame)
        
        # Основная область с монетами и правой колонкой
        main_area = tk.Frame(content_frame, bg=self.colors.colors['bg_dark'])
        main_area.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Левая область с монетами
        coins_frame = tk.Frame(main_area, bg=self.colors.colors['bg_dark'])
        coins_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Создаем сетку монет
        self.create_compact_grid(coins_frame)
        
        # Правая колонка с ЕДИНЫМ терминалом
        self.create_right_column(main_area)
        
        # Компактный статус бар
        self.create_compact_status(content_frame)
    
    def create_unified_header_panel(self, parent):
        """
        Создание шапки в две строки: верхняя — управление и статистика, нижняя — выбор периода
        """
        # --- Первая строка: управление, статус, статистика ---
        header_frame = tk.Frame(parent, bg=self.colors.colors['bg_dark'], height=60)
        header_frame.pack(fill=tk.X, pady=(0, 0))
        header_frame.pack_propagate(False)

        header_canvas = tk.Canvas(header_frame, bg=self.colors.colors['bg_header'], 
                                highlightthickness=0, height=60)
        header_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        self.create_rounded_rectangle(header_canvas, 0, 0, 1920, 60, 8, 
                                    fill=self.colors.colors['bg_header'], 
                                    outline=self.colors.colors['blue'], width=1)

        self.create_trading_controls_block(header_canvas)
        self.create_trading_stats_block(header_canvas)
        self.create_status_block(header_canvas)
        self.create_time_block(header_canvas)

        # --- Вторая строка: выбор периода ---
        period_row_frame = tk.Frame(parent, bg=self.colors.colors['bg_header'])
        period_row_frame.pack(fill=tk.X, pady=(0, 10))
        self.create_period_selection_block(period_row_frame)

        # --- Вторая строка статистики (если нужна) ---
        self.create_second_row_stats(parent)

        # Инициализация данных и времени
        self.ticker_position = 0
        self.market_data = {
            'total_market_cap': 0,
            'total_volume_24h': 0,
            'bitcoin_dominance': 0,
        }
        self.start_time_update()

    def create_trading_controls_block(self, header_canvas):
        """
        Блок управления торговлей (кнопки запуска/остановки и статус)
        """
        trading_controls_frame = tk.Frame(header_canvas, bg=self.colors.colors['bg_header'])
        trading_controls_frame.pack(side=tk.LEFT, padx=10, pady=10)

        # Удаляем старые кнопки управления торговлей (если есть)
        for widget in trading_controls_frame.winfo_children():
            widget.destroy()
            
        # Кнопка запуска (белый фон, красный текст)
        self.start_trading_btn = tk.Button(trading_controls_frame, text="🚀 ЗАПУСТИТЬ ТОРГОВЛЮ", 
                                          font=("Arial", 14, "bold"),
                                          bg="#ffffff", fg="#e74c3c", 
                                          activebackground="#f5f5f5", activeforeground="#c0392b",
                                          borderwidth=0, highlightthickness=0,
                                          command=self.start_aggressive_trading)
        self.start_trading_btn.pack(side='left', padx=4, pady=6)
        
        # Кнопка остановки (белый фон, красный текст)
        self.stop_trading_btn = tk.Button(trading_controls_frame, text="⏹️ ОСТАНОВИТЬ", 
                                         font=("Arial", 14, "bold"),
                                         bg="#ffffff", fg="#e74c3c", 
                                         activebackground="#f5f5f5", activeforeground="#c0392b",
                                         borderwidth=0, highlightthickness=0,
                                         command=self.stop_aggressive_trading)
        self.stop_trading_btn.pack(side='left', padx=4, pady=6)
        
        # Статус торговли
        self.trading_status_label = tk.Label(trading_controls_frame, text="Статус: ОСТАНОВЛЕНА", 
                                            font=("Arial", 13, "bold"), fg="#f1c40f", 
                                            bg=self.colors.colors['bg_header'])
        self.trading_status_label.pack(side='left', padx=6)
        
        # Кнопка анализа базы знаний
        self.analyze_knowledge_btn = tk.Button(trading_controls_frame, text="🔍 Анализ", 
                                              font=("Arial", 12, "bold"),
                                              bg="#ffffff", fg="#e67e22", 
                                              activebackground="#f5f5f5", activeforeground="#d35400",
                                              borderwidth=0, highlightthickness=0,
                                              command=self.analyze_knowledge_base)
        self.analyze_knowledge_btn.pack(side='left', padx=4, pady=6)

    def create_trading_stats_block(self, header_canvas):
        """
        Блок основной статистики торговли (первый ряд)
        """
        trading_stats = [
            ("💰 Баланс: $100.00", "#f59e0b"),
            ("📈 Винрейт: 0.0%", "#10b981"),
            ("📊 Сделок: 0", "#06b6d4"),
            ("💵 PnL: $0.00", "#ffffff")
        ]
        self.trading_stats_labels = {}
        for i, (text, color) in enumerate(trading_stats):
            label = tk.Label(header_canvas, text=text, 
                           font=("Arial", 13, "bold"),
                           fg=color, 
                           bg=self.colors.colors['bg_header'])
            label.pack(side=tk.LEFT, padx=6)
            self.trading_stats_labels[text] = label

    def create_second_row_stats(self, parent):
        """
        Блок дополнительной статистики (второй ряд)
        """
        second_row_frame = tk.Frame(parent, bg=self.colors.colors['bg_header'])
        second_row_frame.pack(fill=tk.X, padx=0, pady=(0, 0))
        second_row_stats = [
            ("🎯 Прибыльных: 0", "#10b981"),
            ("❌ Убыточных: 0", "#ef4444"),
            ("⚡ Открытых позиций: 0", "#8b5cf6")
        ]
        for i, (text, color) in enumerate(second_row_stats):
            label = tk.Label(second_row_frame, text=text, 
                           font=("Arial", 12, "bold"),
                           fg=color, 
                           bg=self.colors.colors['bg_header'])
            label.pack(side=tk.LEFT, padx=10)
            self.trading_stats_labels[text] = label

    def create_period_selection_block(self, parent):
        """
        Блок выбора периода анализа (компактный календарный интерфейс)
        """
        period_frame = tk.Frame(parent, bg=self.colors.colors['bg_header'])
        period_frame.pack(side=tk.LEFT, padx=10, pady=2)
        
        period_label = tk.Label(period_frame, text="📅 Период:", 
                              font=("Arial", 11, "bold"),
                              fg=self.colors.colors['text_white'], 
                              bg=self.colors.colors['bg_header'])
        period_label.pack(side=tk.LEFT, pady=(0, 0), padx=(0, 8))
        
        # Компактный календарный интерфейс
        calendar_frame = tk.Frame(period_frame, bg=self.colors.colors['bg_header'])
        calendar_frame.pack(side=tk.LEFT)
        
        # Начальная дата
        from_label = tk.Label(calendar_frame, text="От:", 
                            font=("Arial", 10, "bold"),
                            fg=self.colors.colors['text_white'], 
                            bg=self.colors.colors['bg_header'])
        from_label.pack(side=tk.LEFT, padx=(0, 5))
        
        # Выпадающий список для месяца начала (только доступные месяцы)
        self.start_month_var = tk.StringVar(value="07")
        start_month_menu = tk.OptionMenu(calendar_frame, self.start_month_var,
                                       "07", "08", "09", "10", "11", "12",  # 2024
                                       "01", "02", "03", "04", "05")        # 2025
        start_month_menu.config(font=("Arial", 10), bg=self.colors.colors['bg_dark'],
                              fg=self.colors.colors['text_white'],
                              highlightthickness=0, relief=tk.FLAT, width=3)
        start_month_menu.pack(side=tk.LEFT, padx=2)
        
        # Выпадающий список для года начала (только доступные годы)
        self.start_year_var = tk.StringVar(value="2024")
        start_year_menu = tk.OptionMenu(calendar_frame, self.start_year_var,
                                      "2024", "2025")
        start_year_menu.config(font=("Arial", 10), bg=self.colors.colors['bg_dark'],
                             fg=self.colors.colors['text_white'],
                             highlightthickness=0, relief=tk.FLAT, width=6)
        start_year_menu.pack(side=tk.LEFT, padx=2)
        
        # Конечная дата
        to_label = tk.Label(calendar_frame, text="До:", 
                          font=("Arial", 10, "bold"),
                          fg=self.colors.colors['text_white'], 
                          bg=self.colors.colors['bg_header'])
        to_label.pack(side=tk.LEFT, padx=(10, 5))
        
        # Выпадающий список для месяца конца (только доступные месяцы)
        self.end_month_var = tk.StringVar(value="05")
        end_month_menu = tk.OptionMenu(calendar_frame, self.end_month_var,
                                     "07", "08", "09", "10", "11", "12",  # 2024
                                     "01", "02", "03", "04", "05")        # 2025
        end_month_menu.config(font=("Arial", 10), bg=self.colors.colors['bg_dark'],
                            fg=self.colors.colors['text_white'],
                            highlightthickness=0, relief=tk.FLAT, width=3)
        end_month_menu.pack(side=tk.LEFT, padx=2)
        
        # Выпадающий список для года конца (только доступные годы)
        self.end_year_var = tk.StringVar(value="2025")
        end_year_menu = tk.OptionMenu(calendar_frame, self.end_year_var,
                                    "2024", "2025")
        end_year_menu.config(font=("Arial", 10), bg=self.colors.colors['bg_dark'],
                           fg=self.colors.colors['text_white'],
                           highlightthickness=0, relief=tk.FLAT, width=6)
        end_year_menu.pack(side=tk.LEFT, padx=2)
        
        # Кнопка применения периода
        apply_btn = tk.Button(calendar_frame, text="✓", 
                            font=("Arial", 12, "bold"),
                            bg=self.colors.colors['green'], 
                            fg=self.colors.colors['text_white'],
                            relief=tk.FLAT, bd=0, padx=8, pady=2,
                            command=self.apply_calendar_period)
        apply_btn.pack(side=tk.LEFT, padx=(10, 5))
        
        # Кнопка проверки данных
        check_btn = tk.Button(calendar_frame, text="📊", 
                            font=("Arial", 10, "bold"),
                            bg=self.colors.colors['orange'], 
                            fg=self.colors.colors['text_white'],
                            relief=tk.FLAT, bd=0, padx=6, pady=2,
                            command=self.check_available_data)
        check_btn.pack(side=tk.LEFT, padx=2)
        
        # Добавляем подсказки
        self.create_tooltip(apply_btn, "Применить выбранный период")
        self.create_tooltip(check_btn, "Проверить доступность данных")
        
        # Остальные элементы (скорость симуляции, таймфреймы)
        self.create_simulation_controls(period_frame)
        self.create_timeframe_selection(period_frame)

    def create_simulation_controls(self, parent):
        """Создание панели выбора скорости симуляции"""
        speed_frame = tk.Frame(parent, bg=self.colors.colors['bg_header'])
        speed_frame.pack(side=tk.LEFT, padx=(20, 0))
        speed_label = tk.Label(speed_frame, text="Скорость симуляции:",
                              font=("Arial", 11, "bold"),
                              fg=self.colors.colors['text_white'],
                              bg=self.colors.colors['bg_header'])
        speed_label.pack(side=tk.LEFT, padx=(0, 8))
        self.sim_speed_var = tk.StringVar(value="1:1")
        speed_options = [
            ("Минута = минуте", "1:1"),
            ("Минута = часу", "1:60"),
            ("Минута = 1 дню", "1:1440")
        ]
        speed_menu = tk.OptionMenu(speed_frame, self.sim_speed_var,
                                  *[opt[0] for opt in speed_options])
        speed_menu.config(font=("Arial", 11), bg=self.colors.colors['bg_dark'],
                         fg=self.colors.colors['text_white'],
                         highlightthickness=0, relief=tk.FLAT, width=16)
        speed_menu.pack(side=tk.LEFT)
        self.sim_speed_map = {opt[0]: opt[1] for opt in speed_options}

    def create_timeframe_selection(self, parent):
        """Создание панели выбора таймфреймов анализа"""
        tf_frame = tk.Frame(parent, bg=self.colors.colors['bg_header'])
        tf_frame.pack(side=tk.LEFT, padx=(20, 0))
        tf_label = tk.Label(tf_frame, text="Таймфреймы:",
                            font=("Arial", 11, "bold"),
                            fg=self.colors.colors['text_white'],
                            bg=self.colors.colors['bg_header'])
        tf_label.pack(side=tk.LEFT, padx=(0, 8))
        self.timeframe_options = ["1m", "5m", "15m", "1h", "4h", "1d"]
        self.timeframe_vars = {}
        self.selected_timeframes = []
        def on_tf_change():
            self.selected_timeframes = [tf for tf, var in self.timeframe_vars.items() if var.get()]
        for tf in self.timeframe_options:
            var = tk.BooleanVar(value=(tf in ["5m", "1h"]))  # по умолчанию выбраны 5m и 1h
            cb = tk.Checkbutton(tf_frame, text=tf, variable=var,
                                font=("Arial", 11),
                                fg=self.colors.colors['text_white'],
                                bg=self.colors.colors['bg_header'],
                                selectcolor=self.colors.colors['bg_dark'],
                                activebackground=self.colors.colors['bg_header'],
                                activeforeground=self.colors.colors['text_white'],
                                command=on_tf_change)
            cb.pack(side=tk.LEFT, padx=2)
            self.timeframe_vars[tf] = var
        on_tf_change()  # инициализация списка выбранных таймфреймов



    def create_status_block(self, header_canvas):
        """
        Блок статуса API и баланса фьючерсов
        """
        # Статус API справа от периода
        api_status_label = tk.Label(header_canvas, textvariable=self.core.api_status_var, 
                                  font=("Arial", 12, "bold"), 
                                  fg="#f59e0b", 
                                  bg=self.colors.colors['bg_header'])
        api_status_label.pack(side=tk.RIGHT, padx=10, pady=(0, 25))
        
        # Баланс фьючерсов справа от статуса API
        futures_balance_label = tk.Label(header_canvas, textvariable=self.core.futures_balance_var, 
                                  font=("Arial", 12, "bold"), 
                                  fg="#00ff00", 
                                  bg=self.colors.colors['bg_header'])
        futures_balance_label.pack(side=tk.RIGHT, padx=10, pady=(0, 25))

    def create_time_block(self, header_canvas):
        """
        Блок отображения времени
        """
        # Время справа
        self.trading_time_label = tk.Label(header_canvas, text="", 
                                         font=("Arial", 13, "bold"),
                                         fg=self.colors.colors['text_white'], 
                                         bg=self.colors.colors['bg_header'])
        self.trading_time_label.pack(side=tk.RIGHT, padx=20, pady=(0, 25))

    def start_time_update(self):
        """
        Запуск обновления времени
        """
        def update_trading_time():
            current_time = datetime.now().strftime("%H:%M:%S")
            if hasattr(self, 'trading_time_label') and self.trading_time_label:
                self.trading_time_label.config(text=f"🕐 {current_time}")
            self.core.root.after(1000, update_trading_time)
        update_trading_time()
    
    def create_empty_bottom_space(self, parent):
        """Создание панели открытых позиций внизу (на всю ширину)"""
        # Панель с фиксированной высотой (20% от 1080px = 216px)
        positions_frame = tk.Frame(parent, bg=self.colors.colors['bg_header'], height=216)
        positions_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        positions_frame.pack_propagate(False)

        # Заголовок
        positions_title = tk.Label(positions_frame, text="📈 Открытые позиции", 
                                 font=("Arial", 14, "bold"),
                                 fg=self.colors.colors['text_white'], 
                                 bg=self.colors.colors['bg_header'])
        positions_title.pack(anchor=tk.W, padx=10, pady=5)

        # Таблица позиций
        columns = [
            "Символ", "Размер", "Цена входа", "Цена безубытка", "Цена маркировки", "Цена ликвидации",
            "Коэф. маржи", "Маржа", "PnL", "Стоп-лосс", "Тейк-профит", "Действия"
        ]
        self.positions_table = ttk.Treeview(positions_frame, columns=columns, show="headings", height=7)
        for col in columns:
            self.positions_table.heading(col, text=col)
            self.positions_table.column(col, anchor=tk.CENTER, width=110)
        self.positions_table.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Стилизация
        style = ttk.Style()
        style.configure("Treeview.Heading", font=("Arial", 11, "bold"), 
                       background=self.colors.colors['bg_header'], 
                       foreground=self.colors.colors['text_white'])
        style.configure("Treeview", font=("Arial", 10), rowheight=28, 
                       background=self.colors.colors['bg_card'], 
                       fieldbackground=self.colors.colors['bg_card'], 
                       foreground=self.colors.colors['text_white'])
        style.map("Treeview", background=[('selected', self.colors.colors['blue'])])

        # Кнопка обновления позиций
        update_btn = tk.Button(positions_frame, text="🔄 Обновить", 
                              command=lambda: self.update_positions_table([]), 
                              font=("Arial", 10), 
                              bg=self.colors.colors['blue'], 
                              fg=self.colors.colors['text_white'])
        update_btn.pack(side=tk.RIGHT, padx=10, pady=5)

        self.positions_frame = positions_frame

        # Запуск автообновления таблицы сразу после создания панели
        self.start_positions_update()
    
    def create_trading_controls(self, parent):
        """Создает панель управления торговлей"""
        trading_frame = tk.Frame(parent, bg='#1a1a1a', relief='raised', bd=1)
        trading_frame.pack(fill='x', padx=5, pady=5)
        
        # Заголовок
        title_label = tk.Label(trading_frame, text="🚀 УПРАВЛЕНИЕ ТОРГОВЛЕЙ", 
                              font=('Arial', 12, 'bold'), fg='#00ff00', bg='#1a1a1a')
        title_label.pack(pady=5)
        
        # Кнопки управления
        button_frame = tk.Frame(trading_frame, bg='#1a1a1a')
        button_frame.pack(pady=5)
        
        # Кнопка запуска агрессивной торговли
        self.start_trading_btn = tk.Button(button_frame, text="🚀 ЗАПУСТИТЬ ТОРГОВЛЮ", 
                                          font=('Arial', 10, 'bold'),
                                          bg='#00aa00', fg='white', 
                                          command=self.start_aggressive_trading,
                                          relief='raised', bd=2)
        self.start_trading_btn.pack(side='left', padx=5)
        
        # Кнопка остановки торговли
        self.stop_trading_btn = tk.Button(button_frame, text="⏹️ ОСТАНОВИТЬ", 
                                         font=('Arial', 10, 'bold'),
                                         bg='#aa0000', fg='white', 
                                         command=self.stop_aggressive_trading,
                                         relief='raised', bd=2)
        self.stop_trading_btn.pack(side='left', padx=5)
        
        # Статус торговли
        self.trading_status_label = tk.Label(trading_frame, text="Статус: ОСТАНОВЛЕНА", 
                                            font=('Arial', 10), fg='#ff0000', bg='#1a1a1a')
        self.trading_status_label.pack(pady=5)
        
        # Статистика торговли
        stats_frame = tk.Frame(trading_frame, bg='#1a1a1a')
        stats_frame.pack(fill='x', padx=10, pady=5)
        
        # Баланс
        self.balance_label = tk.Label(stats_frame, text="💰 Баланс: $10,000.00", 
                                     font=('Arial', 9), fg='#00ff00', bg='#1a1a1a')
        self.balance_label.pack(anchor='w')
        
        # Винрейт
        self.winrate_label = tk.Label(stats_frame, text="📊 Винрейт: 0.0%", 
                                     font=('Arial', 9), fg='#00ff00', bg='#1a1a1a')
        self.winrate_label.pack(anchor='w')
        
        # P&L
        self.pnl_label = tk.Label(stats_frame, text="📈 P&L: $0.00", 
                                 font=('Arial', 9), fg='#00ff00', bg='#1a1a1a')
        self.pnl_label.pack(anchor='w')
        
        # Открытые позиции
        self.positions_label = tk.Label(stats_frame, text="📋 Позиций: 0", 
                                       font=('Arial', 9), fg='#00ff00', bg='#1a1a1a')
        self.positions_label.pack(anchor='w')
        
        return trading_frame

    def start_aggressive_trading(self):
        """Обработчик кнопки запуска торговли"""
        try:
            print("[DEBUG] Кнопка ЗАПУСТИТЬ ТОРГОВЛЮ нажата")
            self.add_terminal_message("[DEBUG] Кнопка ЗАПУСТИТЬ ТОРГОВЛЮ нажата", "DEBUG")
            if hasattr(self, 'core') and hasattr(self.core, 'logic'):
                print("[DEBUG] Вызов self.core.logic.start_aggressive_trading()")
                self.add_terminal_message("[DEBUG] Вызов self.core.logic.start_aggressive_trading()", "DEBUG")
                self.core.logic.start_aggressive_trading()
            else:
                print("[DEBUG] Нет доступа к core.logic!")
                self.add_terminal_message("[DEBUG] Нет доступа к core.logic!", "ERROR")
        except Exception as e:
            print(f"[DEBUG] Ошибка запуска торговли: {e}")
            self.add_terminal_message(f"❌ Ошибка запуска торговли: {e}", "ERROR")

    def stop_aggressive_trading(self):
        """Останавливает агрессивную торговлю"""
        try:
            if hasattr(self, 'core') and hasattr(self.core, 'logic'):
                self.core.logic.stop_aggressive_trading()
            self.trading_status_label.config(text="Статус: ОСТАНОВЛЕНА", fg='#ff0000')
            self.start_trading_btn.config(state='normal')
            self.stop_trading_btn.config(state='disabled')
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка остановки торговли: {e}", "ERROR")
    
    def sync_to_github(self):
        """Синхронизация базы знаний с GitHub"""
        try:
            if hasattr(self, 'core') and hasattr(self.core, 'logic'):
                self.core.logic.sync_knowledge_to_github()
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка синхронизации: {e}", "ERROR")
    
    def sync_from_github(self):
        """Загрузка базы знаний с GitHub"""
        try:
            if hasattr(self, 'core') and hasattr(self.core, 'logic'):
                self.core.logic.sync_knowledge_from_github()
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка загрузки: {e}", "ERROR")
    
    def analyze_knowledge_base(self):
        """Анализ базы знаний"""
        try:
            if hasattr(self, 'core') and hasattr(self.core, 'logic'):
                self.core.logic.analyze_knowledge_base()
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка анализа: {e}", "ERROR")

    def update_trading_stats(self):
        """Обновляет торговую статистику"""
        try:
            if hasattr(self, 'core') and hasattr(self.core, 'logic'):
                status = self.core.logic.get_trading_status()
                
                # Обновляем статус
                if status['active']:
                    self.trading_status_label.config(text="Статус: АКТИВНА", fg='#00ff00')
                else:
                    self.trading_status_label.config(text="Статус: ОСТАНОВЛЕНА", fg='#ff0000')
                
                # Обновляем статистику
                self.balance_label.config(text=f"💰 Баланс: ${status['balance']:,.2f}")
                self.winrate_label.config(text=f"📊 Винрейт: {status['winrate']:.1f}%")
                
                pnl_color = '#00ff00' if status['total_pnl'] >= 0 else '#ff0000'
                self.pnl_label.config(text=f"📈 P&L: ${status['total_pnl']:,.2f}", fg=pnl_color)
                self.positions_label.config(text=f"📋 Позиций: {status['open_positions']}")
            
        except Exception as e:
            pass  # Игнорируем ошибки обновления статистики

    def create_right_column(self, parent):
        """
        Создает правую колонку только с терминалом (без панели управления торговлей)
        """
        right_frame = tk.Frame(parent, bg='#0a0a0a', width=900)
        right_frame.pack(side='right', fill='y', padx=5, pady=5)
        right_frame.pack_propagate(False)
        
        # Только терминал
        terminal_frame = tk.Frame(right_frame, bg='#0a0a0a')
        terminal_frame.pack(fill='both', expand=True, pady=5)
        
        # Заголовок терминала с кнопкой очистки
        terminal_header_frame = tk.Frame(terminal_frame, bg='#0a0a0a')
        terminal_header_frame.pack(fill='x', pady=5)
        
        terminal_header = tk.Label(terminal_header_frame, text="📝 ТЕРМИНАЛ", 
                                  font=('Arial', 10, 'bold'), fg='#06b6d4', bg='#0a0a0a')
        terminal_header.pack(side='left', padx=5)
        
        # Кнопка очистки терминала
        clear_terminal_btn = tk.Button(terminal_header_frame, text="🗑️ Очистить", 
                                      font=('Arial', 8, 'bold'),
                                      bg='#dc2626', fg='white',
                                      activebackground='#b91c1c', activeforeground='white',
                                      borderwidth=0, highlightthickness=0,
                                      command=self.clear_terminal)
        clear_terminal_btn.pack(side='right', padx=5)
        
        # Используем ScrolledText для правильной работы скроллинга
        self.terminal_text = scrolledtext.ScrolledText(
            terminal_frame, 
            wrap=tk.WORD, 
            height=15, 
            state=tk.DISABLED,
            font=("Consolas", 11), 
            bg='#1a1a1a', 
            fg='#ffffff',
            insertbackground='#ffffff',
            selectbackground='#3b82f6',
            selectforeground='#ffffff'
        )
        self.terminal_text.pack(fill='both', expand=True, padx=5)
        
        # Добавляем подсказку о скроллинге
        self.terminal_text.config(state=tk.NORMAL)
        self.terminal_text.insert(tk.END, "[ИНФО] Терминал готов к работе. Используйте скролл для просмотра истории сообщений.\n")
        self.terminal_text.insert(tk.END, "[ИНФО] 🖱️ Колесико мыши или полоса прокрутки справа для навигации.\n")
        self.terminal_text.insert(tk.END, "[ИНФО] 📱 Новые сообщения автоматически прокручиваются вниз.\n\n")
        self.terminal_text.config(state=tk.DISABLED)
        
        return right_frame

    def create_rounded_rectangle(self, canvas, x1, y1, x2, y2, radius, **kwargs):
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

    def create_fallback_right_panel(self, parent):
        """Создание простой правой панели без ИИ"""
        # Canvas для правой колонки с закругленными углами
        right_canvas = tk.Canvas(parent, bg=self.colors.colors['bg_header'], 
                               highlightthickness=0, width=400)
        right_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Рисуем закругленный фон для правой колонки
        self.create_rounded_rectangle(right_canvas, 0, 0, 400, 600, 12, 
                                    fill=self.colors.colors['bg_header'], 
                                    outline=self.colors.colors['blue'], width=2)
        
        # Заголовок колонки
        header_label = tk.Label(right_canvas, text="📊 Дополнительная информация", 
                               font=("Arial", 14, "bold"),
                               fg=self.colors.colors['text_white'], 
                               bg=self.colors.colors['bg_header'])
        header_label.pack(pady=20)
        
        # Информация о том, что ИИ недоступен
        info_label = tk.Label(right_canvas, text="ИИ модуль недоступен\nПроверьте файл ai_integration.py", 
                             font=("Arial", 12),
                             fg=self.colors.colors['text_gray'], 
                             bg=self.colors.colors['bg_header'])
        info_label.pack(pady=50)
    
    def create_compact_grid(self, parent):
        """Создание компактной сетки монет"""
        # Настройка весов для всех колонок и строк заранее
        for col in range(5):
            parent.grid_columnconfigure(col, weight=1)
        for row in range(6):
            parent.grid_rowconfigure(row, weight=1)
        
        # Создаем сетку 6x5 для всех 30 монет
        self.coin_cards = {}
        for i, symbol in enumerate(self.core.symbols):
            row = i // 5
            col = i % 5
            
            card = self.create_compact_coin_card(parent, symbol)
            card.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
            
            self.coin_cards[symbol] = card
    
    def create_compact_coin_card(self, parent, symbol):
        """Создание компактной карточки монеты"""
        # Карточка с закругленными углами, растягивается по ширине
        card = tk.Frame(parent, bg=self.colors.colors['bg_dark'], 
                       relief=tk.FLAT, bd=0)
        
        # Canvas для карточки с закругленными углами
        card_canvas = tk.Canvas(card, bg=self.colors.colors['bg_card'], 
                              highlightthickness=0, height=80)
        card_canvas.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        # Функция для отрисовки закругленного фона с адаптивной шириной
        def draw_card_background():
            canvas_width = card_canvas.winfo_width()
            canvas_height = card_canvas.winfo_height()
            if canvas_width > 0 and canvas_height > 0:
                card_canvas.delete("all")
                self.create_rounded_rectangle(card_canvas, 0, 0, canvas_width, canvas_height, 6, 
                                            fill=self.colors.colors['bg_card'], 
                                            outline="#4a5568", width=1)
        
        # Привязываем функцию к изменению размера canvas
        card_canvas.bind('<Configure>', lambda e: draw_card_background())
        
        # Вызываем функцию один раз для начальной отрисовки
        self.core.root.after(100, draw_card_background)
        
        # Заголовок (символ)
        symbol_label = tk.Label(card_canvas, text=symbol, 
                               font=("Arial", 12, "bold"),
                               fg="#e2e8f0", 
                               bg=self.colors.colors['bg_card'])
        symbol_label.pack(anchor=tk.W, padx=(5, 0), pady=(2, 0))
        
        # Цена (крупно)
        price_label = tk.Label(card_canvas, text="$0.00", 
                              font=("Arial", 16, "bold"),
                              fg="#f7fafc", 
                              bg=self.colors.colors['bg_card'])
        price_label.pack(anchor=tk.W, padx=(5, 0))
        
        # Изменение цены
        change_label = tk.Label(card_canvas, text="0.00%", 
                               font=("Arial", 12),
                               fg="#a0aec0", 
                               bg=self.colors.colors['bg_card'])
        change_label.pack(anchor=tk.W, padx=(5, 0))
        
        # Объем (компактно)
        volume_label = tk.Label(card_canvas, text="Vol: $0", 
                               font=("Arial", 10),
                               fg="#a0aec0", 
                               bg=self.colors.colors['bg_card'])
        volume_label.pack(anchor=tk.W, padx=(5, 0), pady=(0, 2))
        
        # Сохраняем ссылки на метки в словаре
        setattr(card, 'labels', {
            'price': price_label,
            'change': change_label,
            'volume': volume_label,
            'symbol': symbol_label
        })
        
        return card
    
    def create_compact_status(self, parent):
        """Создание компактного статус бара"""
        status_frame = tk.Frame(parent, bg=self.colors.colors['bg_dark'], height=30)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        status_frame.pack_propagate(False)
        
        # Canvas для статус бара с закругленными углами
        status_canvas = tk.Canvas(status_frame, bg=self.colors.colors['bg_header'], 
                                highlightthickness=0, height=30)
        status_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        
        # Рисуем закругленный фон для статус бара
        self.create_rounded_rectangle(status_canvas, 0, 0, 1920, 30, 6, 
                                    fill=self.colors.colors['bg_header'], 
                                    outline=self.colors.colors['blue'], width=1)
        
        self.status_var = tk.StringVar(value="🚀 Система готова")
        status_label = tk.Label(status_canvas, textvariable=self.status_var, 
                               font=("Arial", 10),
                               fg=self.colors.colors['text_white'], 
                               bg=self.colors.colors['bg_header'])
        status_label.pack(side=tk.LEFT, padx=10)
    
    # Методы для работы с симуляцией (отключены)
    def start_simulation(self):
        pass
    
    def stop_simulation(self):
        pass
    
    def create_terminal_panel(self, parent):
        """Создаёт скроллируемый терминал для вывода сообщений"""
        terminal_frame = tk.Frame(parent, bg=self.colors.colors['bg_dark'])
        terminal_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.terminal_text = scrolledtext.ScrolledText(
            terminal_frame, wrap=tk.WORD, height=15, state=tk.DISABLED,
            font=("Consolas", 11), bg=self.colors.colors['bg_card'], fg=self.colors.colors['text_white']
        )
        self.terminal_text.pack(fill=tk.BOTH, expand=True)

    def add_terminal_message(self, message: str, level: str = "INFO"):
        """Добавляет сообщение в скроллируемый терминал с автоскроллом вниз"""
        if hasattr(self, 'terminal_text') and self.terminal_text is not None:
            try:
                self.terminal_text.config(state=tk.NORMAL)
                timestamp = datetime.now().strftime("%H:%M:%S")
                formatted_message = f"[{timestamp}] {message}\n"
                self.terminal_text.insert(tk.END, formatted_message)
                
                # Автоскролл вниз для показа последних сообщений
                self.terminal_text.see(tk.END)
                
                # Убираем ограничение на количество строк - позволяем свободно скроллить
                # Теперь можно просматривать всю историю сообщений
                
                self.terminal_text.config(state=tk.DISABLED)
            except Exception as e:
                # Тихо обрабатываем ошибки добавления сообщений
                pass

    def clear_terminal(self):
        if not self.terminal_text:
            return
        try:
            self.terminal_text.config(state=tk.NORMAL)
            self.terminal_text.delete(1.0, tk.END)
            self.terminal_text.config(state=tk.DISABLED)
        except Exception as e:
            # Тихо обрабатываем ошибки очистки терминала
            pass

    def update_positions_table(self, positions):
        if not self.positions_table:
            return
        try:
            for row in self.positions_table.get_children():
                self.positions_table.delete(row)
            for pos in positions:
                symbol = pos.get('symbol', '')
                size = f"{pos.get('size', 0):.4f} {symbol.replace('USDT','')}"
                entry = f"{pos.get('entry_price', 0):.2f}"
                breakeven = f"{pos.get('entry_price', 0):.2f}"
                mark = f"{pos.get('current_price', 0):.2f}"
                leverage = pos.get('leverage', 1)
                side = pos.get('side', 'LONG')
                if side == 'LONG':
                    liq = f"{pos.get('entry_price', 0) * (1 - 1/max(leverage,1)):.2f}"
                else:
                    liq = f"{pos.get('entry_price', 0) * (1 + 1/max(leverage,1)):.2f}"
                margin_rate = f"{100/max(leverage,1):.2f}%"
                margin = f"{(pos.get('size',0)*pos.get('entry_price',0)/max(leverage,1)):.2f} USDT"
                pnl = f"{pos.get('pnl_dollars',0):+.2f} USDT ({pos.get('pnl_pct',0)*100:+.2f}%)"
                stop = f"{pos.get('stop_loss', 0):.2f}"
                take = f"{pos.get('take_profit', 0):.2f}"
                iid = self.positions_table.insert("", "end", values=(symbol, size, entry, breakeven, mark, liq, margin_rate, margin, pnl, stop, take, "Закрыть"))
                self.positions_table.set(iid, column="Действия", value="Закрыть")
        except Exception as e:
            # Тихо обрабатываем ошибки таблицы позиций
            pass
    
    def start_positions_update(self):
        pass
    
    def update_market_data(self):
        pass
    
    def animate_market_ticker(self):
        pass
    
    def apply_calendar_period(self):
        """Применение выбранного периода анализа из календарного интерфейса"""
        try:
            # Формируем даты из выбранных месяца и года
            start_date = f"{self.start_year_var.get()}-{self.start_month_var.get()}-01"
            end_date = f"{self.end_year_var.get()}-{self.end_month_var.get()}-31"
            
            # Валидация дат
            from datetime import datetime
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            if start_dt >= end_dt:
                self.add_terminal_message("❌ Ошибка: начальная дата должна быть раньше конечной", "ERROR")
                return
            
            # Передаем выбранный период в логику
            if hasattr(self.core, 'logic') and self.core.logic:
                self.core.logic.set_analysis_period(start_date, end_date)
            
            # Обновляем статус
            status_text = f"📅 Период анализа: {start_date} - {end_date}"
            self.add_terminal_message(f"✅ {status_text}", "INFO")
            
        except ValueError as e:
            self.add_terminal_message("❌ Ошибка формата даты", "ERROR")
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка применения периода: {str(e)}", "ERROR")

    def apply_period_selection(self):
        """Применение выбранного периода анализа (для обратной совместимости)"""
        self.apply_calendar_period()



    def check_available_data(self):
        """Проверяет доступность данных для выбранного периода"""
        try:
            # Формируем даты из выбранных месяца и года
            start_date = f"{self.start_year_var.get()}-{self.start_month_var.get()}-01"
            end_date = f"{self.end_year_var.get()}-{self.end_month_var.get()}-31"
            
            if not start_date or not end_date:
                self.add_terminal_message("❌ Необходимо выбрать даты для проверки.", "ERROR")
                return

            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            if start_dt >= end_dt:
                self.add_terminal_message("❌ Начальная дата должна быть раньше конечной для проверки.", "ERROR")
                return

            if hasattr(self.core, 'logic') and self.core.logic:
                available = self.core.logic.check_data_availability(start_date, end_date)
                if available:
                    self.add_terminal_message(f"✅ Данные для периода {start_date} - {end_date} доступны.", "INFO")
                else:
                    self.add_terminal_message(f"❌ Данные для периода {start_date} - {end_date} НЕ доступны.", "ERROR")
            else:
                self.add_terminal_message("❌ Логика не инициализирована для проверки данных.", "ERROR")
        except ValueError as e:
            self.add_terminal_message("❌ Ошибка формата даты", "ERROR")
        except Exception as e:
            self.add_terminal_message(f"❌ Ошибка проверки данных: {e}", "ERROR")

    def create_tooltip(self, widget, text):
        """Создание подсказки для виджета"""
        tooltip = tk.Toplevel(widget)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry("+%d+%d" % (widget.winfo_x() + widget.winfo_width() + 5, widget.winfo_y() + widget.winfo_height() + 5))
        label = tk.Label(tooltip, text=text, bg="black", fg="white", font=("Arial", 10))
        label.pack(ipadx=5, ipady=3)
        tooltip.wm_attributes("-topmost", True)
        return tooltip


 