#!/usr/bin/env python3
"""
PREMIUM GUI - современный дизайн как на бирже
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Dict, Callable
from datetime import datetime
import winsound
import threading
import time
import requests
import sys
from pathlib import Path


class PremiumScalpingGUI:
    """
    Современный GUI с таблицей как на бирже
    """
    
    def __init__(self, root: tk.Tk, config: Dict):
        self.root = root
        self.config = config
        
        # Callback для закрытия позиций
        self.close_position_callback: Callable = None
        
        # Флаг звуков (можно переключать)
        self.sounds_enabled = config['alerts'].get('sound_on_open', True)
        
        # Настройка окна (темная тема как на скриншоте)
        self.root.title("Scalping Bot")
        self.root.configure(bg='#1a1a1a')
        
        # Устанавливаем размер окна (если не в полноэкранном режиме)
        try:
            # Пытаемся развернуть на весь экран
            self.root.state('zoomed')
        except:
            # Если не поддерживается, устанавливаем размер
            self.root.geometry('1200x800')
        
        # Устанавливаем минимальный размер окна
        self.root.minsize(800, 600)
        
        # Яркие цвета (как на бирже)
        self.colors = {
            'bg': '#1a1a1a',
            'panel': '#252525',
            'header': '#1e1e1e',
            'fg': '#ffffff',
            'fg_bright': '#ffffff',
            'fg_dim': '#888888',
            'green': '#26a69a',
            'green_bright': '#4dd0e1',
            'red': '#ef5350',
            'yellow': '#ffa726',
            'yellow_dark': '#ff9800',
            'border': '#333333'
        }
        
        # Данные
        self.balance = config['account']['starting_balance']
        self.starting_balance = config['account']['starting_balance']
        self.pnl = 0.0
        self.positions = {}
        self.signals = {}
        self.events = []
        self.runtime_seconds = 0
        self.signals_text = None  # Инициализируется в _create_signals_panel
        self.events_text = None  # Инициализируется в _create_events_panel
        self.position_rows = {}  # Сохраняем ссылки на строки позиций для плавного обновления
        self.sound_button = None  # Инициализируется в _create_widgets
        self.signals_history = []  # История всех сигналов для отображения
        
        try:
            self._create_widgets()
            # Обновляем окно после создания всех виджетов
            self.root.update_idletasks()
            self.root.update()
        except Exception as e:
            import logging
            logging.error(f"❌ Ошибка создания виджетов GUI: {e}", exc_info=True)
            # Логируем ошибку, но не показываем всплывающее окно
            # Просто выводим в консоль и лог
            print(f"❌ Ошибка создания виджетов GUI: {e}")
            # Показываем сообщение об ошибке в GUI (не всплывающее окно)
            try:
                error_label = tk.Label(
                    self.root,
                    text=f"Ошибка создания интерфейса: {str(e)[:100]}",
                    font=('Arial', 10),
                    bg='#1a1a1a',
                    fg='#ef5350',
                    wraplength=800
                )
                error_label.pack(expand=True, padx=20, pady=20)
            except:
                pass  # Если даже это не работает, просто логируем
        
        self._update_runtime()
    
    def set_close_position_callback(self, callback: Callable):
        """Установить callback для закрытия позиций"""
        self.close_position_callback = callback
    
    def _create_widgets(self):
        """Создание интерфейса"""
        
        # === HEADER (современный темный) ===
        header = tk.Frame(self.root, bg='#1e1e1e', height=45)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        tk.Label(
            header,
            text="🤖 SCALPING BOT",
            font=('Arial', 12, 'bold'),
            bg='#1e1e1e',
            fg='#42a5f5'
        ).pack(side='left', padx=15, pady=12)
        
        
        tk.Label(
            header,
            text="● LIVE",
            font=('Arial', 10, 'bold'),
            bg='#1e1e1e',
            fg='#26a69a'
        ).pack(side='right', padx=5)
        
        self.runtime_label = tk.Label(
            header,
            text="00:00:00",
            font=('Consolas', 9),
            bg='#1e1e1e',
            fg='#ffffff'
        )
        self.runtime_label.pack(side='right', padx=10)
        
        # Ползунок жесткости анализа (V3)
        strictness_frame = tk.Frame(header, bg='#1e1e1e')
        strictness_frame.pack(side='right', padx=15)
        
        tk.Label(
            strictness_frame,
            text="Жесткость:",
            font=('Arial', 8),
            bg='#1e1e1e',
            fg='#888888'
        ).pack(side='left', padx=(0, 5))
        
        self.strictness_var = tk.DoubleVar(value=50.0)  # По умолчанию 50% (умеренная)
        self.strictness_scale = tk.Scale(
            strictness_frame,
            from_=1,
            to=100,
            orient='horizontal',
            variable=self.strictness_var,
            length=150,
            bg='#1e1e1e',
            fg='#ffffff',
            highlightthickness=0,
            troughcolor='#333333',
            activebackground='#42a5f5',
            command=self._on_strictness_change
        )
        self.strictness_scale.pack(side='left')
        
        self.strictness_label = tk.Label(
            strictness_frame,
            text="50%",
            font=('Arial', 8, 'bold'),
            bg='#1e1e1e',
            fg='#42a5f5',
            width=4
        )
        self.strictness_label.pack(side='left', padx=(5, 0))
        
        # Метка режима торговли
        self.mode_label = tk.Label(
            strictness_frame,
            text="(Умеренная)",
            font=('Arial', 7),
            bg='#1e1e1e',
            fg='#888888',
            width=10
        )
        self.mode_label.pack(side='left', padx=(5, 0))
        
        # === MAIN CONTAINER ===
        main_container = tk.Frame(self.root, bg=self.colors['bg'])
        main_container.pack(fill='both', expand=True, padx=5, pady=(5, 0))
        # Сохраняем ссылку на контейнер
        self.main_container = main_container
        
        # ВЕРХНИЙ РЯД: Счет + Статистика + История (меньше размер - 120px вместо 170px)
        top_row = tk.Frame(main_container, bg=self.colors['bg'], height=120)
        top_row.pack(fill='x', pady=(0, 5))
        top_row.pack_propagate(False)
        
        # Счет слева
        account_frame = tk.Frame(top_row, bg=self.colors['bg'])
        account_frame.pack(side='left', fill='both', expand=True, padx=(0, 2))
        self._create_account_panel(account_frame)
        
        # Статистика по центру
        stats_frame = tk.Frame(top_row, bg=self.colors['bg'])
        stats_frame.pack(side='left', fill='both', expand=True, padx=2)
        self._create_stats_panel(stats_frame)
        
        # История сделок справа
        history_frame = tk.Frame(top_row, bg=self.colors['bg'])
        history_frame.pack(side='left', fill='both', expand=True, padx=(2, 0))
        self._create_history_panel(history_frame)
        
        # НИЖНИЙ РЯД: Позиции 60% + Сигналы 40%
        bottom_row = tk.Frame(main_container, bg=self.colors['bg'])
        bottom_row.pack(fill='both', expand=True)
        
        # Позиции слева (60%)
        positions_panel = tk.Frame(bottom_row, bg=self.colors['bg'])
        positions_panel.pack(side='left', fill='both', expand=True, padx=(0, 2))
        self._create_positions_panel(positions_panel)
        
        # Сигналы/Торговые возможности справа (40%)
        signals_panel = tk.Frame(bottom_row, bg=self.colors['bg'])
        signals_panel.pack(side='left', fill='both', expand=True, padx=(2, 0))
        self._create_signals_panel(signals_panel)
    
    def _create_account_panel(self, parent):
        """Создать панель счета"""
        panel = self._panel(parent, "СЧЕТ", height=110)
        
        self.balance_label = self._row(panel, "Баланс:", "$500.00")
        self.pnl_label = self._row(panel, "P&L:", "+$0.00", self.colors['green'])
        self.available_label = self._row(panel, "Доступно:", "$500.00")
        self.drawdown_label = self._row(panel, "Просадка:", "0%")
    
    def _create_stats_panel(self, parent):
        """Создать панель статистики"""
        panel = self._panel(parent, "СТАТИСТИКА", height=110)
        
        self.trades_label = self._row(panel, "Сделок:", "0")
        self.winrate_label = self._row(panel, "Win Rate:", "0%")
        self.pf_label = self._row(panel, "PF:", "0.0")
        self.avg_pnl_label = self._row(panel, "Avg P&L:", "+$0.00")
        self.costs_label = self._row(panel, "Ком./Фанд.:", "$0.00")
    
    def _create_margin_panel(self, parent):
        """Создать панель коэффициента маржи"""
        panel = self._panel(parent, "КОЭФФИЦИЕНТ МАРЖИ")
        panel.pack(fill='both', expand=True)
        
        # Данные маржи
        tk.Label(
            panel,
            text="Коэфф. маржи аккаунта:",
            font=('Arial', 9),
            bg=self.colors['panel'],
            fg=self.colors['fg_dim'],
            anchor='w'
        ).pack(anchor='w', padx=10, pady=(10, 2))
        
        self.margin_ratio_label = tk.Label(
            panel,
            text="1.16%",
            font=('Arial', 12, 'bold'),
            bg=self.colors['panel'],
            fg=self.colors['green'],
            anchor='w'
        )
        self.margin_ratio_label.pack(anchor='w', padx=10, pady=(0, 10))
        
        tk.Label(
            panel,
            text="Поддерживающая маржа:",
            font=('Arial', 9),
            bg=self.colors['panel'],
            fg=self.colors['fg_dim'],
            anchor='w'
        ).pack(anchor='w', padx=10, pady=(0, 2))
        
        self.maintenance_margin_label = tk.Label(
            panel,
            text="$126.39",
            font=('Arial', 10, 'bold'),
            bg=self.colors['panel'],
            fg=self.colors['fg'],
            anchor='w'
        )
        self.maintenance_margin_label.pack(anchor='w', padx=10, pady=(0, 10))
        
        tk.Label(
            panel,
            text="Стоимость активов:",
            font=('Arial', 9),
            bg=self.colors['panel'],
            fg=self.colors['fg_dim'],
            anchor='w'
        ).pack(anchor='w', padx=10, pady=(0, 2))
        
        self.assets_value_label = tk.Label(
            panel,
            text="$1,263.87",
            font=('Arial', 10, 'bold'),
            bg=self.colors['panel'],
            fg=self.colors['fg'],
            anchor='w'
        )
        self.assets_value_label.pack(anchor='w', padx=10, pady=(0, 10))
        
        # Разделитель
        tk.Frame(panel, bg=self.colors['border'], height=1).pack(fill='x', padx=10, pady=5)
        
        tk.Label(
            panel,
            text="АКТИВЫ",
            font=('Arial', 9, 'bold'),
            bg=self.colors['panel'],
            fg=self.colors['fg'],
            anchor='w'
        ).pack(anchor='w', padx=10, pady=(10, 2))
        
        tk.Label(
            panel,
            text="Баланс кошелька:",
            font=('Arial', 9),
            bg=self.colors['panel'],
            fg=self.colors['fg_dim'],
            anchor='w'
        ).pack(anchor='w', padx=10, pady=(0, 2))
        
        self.wallet_balance_label = tk.Label(
            panel,
            text="$500.00",
            font=('Arial', 10, 'bold'),
            bg=self.colors['panel'],
            fg=self.colors['fg'],
            anchor='w'
        )
        self.wallet_balance_label.pack(anchor='w', padx=10, pady=(0, 10))
        
        tk.Label(
            panel,
            text="Нереализованная PNL:",
            font=('Arial', 9),
            bg=self.colors['panel'],
            fg=self.colors['fg_dim'],
            anchor='w'
        ).pack(anchor='w', padx=10, pady=(0, 2))
        
        self.unrealized_pnl_label = tk.Label(
            panel,
            text="$0.00",
            font=('Arial', 10, 'bold'),
            bg=self.colors['panel'],
            fg=self.colors['fg'],
            anchor='w'
        )
        self.unrealized_pnl_label.pack(anchor='w', padx=10, pady=(0, 10))
    
    def _panel(self, parent, title: str, height: int = None):
        """Создать панель с заголовком"""
        frame = tk.Frame(parent, bg=self.colors['panel'], relief='flat', borderwidth=1)
        if height:
            frame.config(height=height)
        
        # Упаковываем frame в parent
        frame.pack(fill='both', expand=True, padx=2, pady=2)
        
        tk.Label(
            frame,
            text=title,
            font=('Arial', 9, 'bold'),
            bg=self.colors['border'],
            fg='#42a5f5',
            anchor='w'
        ).pack(fill='x', padx=0, pady=0)
        
        content = tk.Frame(frame, bg=self.colors['panel'])
        content.pack(fill='both', expand=True, padx=0, pady=0)
        
        return content
    
    def _row(self, parent, label: str, value: str, value_color: str = None):
        """Создать строку с меткой и значением"""
        row = tk.Frame(parent, bg=self.colors['panel'])
        row.pack(fill='x', padx=10, pady=2)
        
        tk.Label(
            row,
            text=label,
            font=('Arial', 9),
            bg=self.colors['panel'],
            fg=self.colors['fg_dim'],
            anchor='w'
        ).pack(side='left')
        
        label_widget = tk.Label(
            row,
            text=value,
            font=('Arial', 9, 'bold'),
            bg=self.colors['panel'],
            fg=value_color or self.colors['fg'],
            anchor='e'
        )
        label_widget.pack(side='right')
        
        return label_widget
    
    def _create_positions_panel(self, parent):
        """Создать панель позиций"""
        panel = self._panel(parent, "📈 АКТИВНЫЕ ПОЗИЦИИ")
        
        # Контейнер для таблицы позиций
        self.positions_container = tk.Frame(panel, bg=self.colors['panel'])
        self.positions_container.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Заголовок таблицы
        self._create_table_header(self.positions_container)
    
    def _create_table_header(self, parent):
        """Создать заголовок таблицы позиций"""
        header_frame = tk.Frame(parent, bg=self.colors['border'], height=30)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        headers = [
            ('Пара', 80),
            ('Направление', 100),
            ('Размер', 80),
            ('Вход', 80),
            ('Текущая', 80),
            ('SL', 80),
            ('TP', 80),
            ('Плечо', 60),
            ('Маржа', 80),
            ('PNL', 80),
            ('Действие', 80)
        ]
        
        for i, (text, width) in enumerate(headers):
            label = tk.Label(
                header_frame,
                text=text,
                font=('Arial', 9, 'bold'),
                bg=self.colors['border'],
                fg='#ffffff',
                anchor='w'
            )
            label.grid(row=0, column=i, sticky='w', padx=5, pady=4)
            header_frame.grid_columnconfigure(i, minsize=width)
    
    def _create_history_panel(self, parent):
        """Создать панель истории сделок"""
        panel = self._panel(parent, "ИСТОРИЯ СДЕЛОК", height=110)
        
        # Контейнер для истории
        self.history_container = tk.Frame(panel, bg=self.colors['panel'])
        self.history_container.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Заголовок таблицы
        header_frame = tk.Frame(self.history_container, bg=self.colors['border'], height=20)
        header_frame.pack(fill='x', pady=(0, 2))
        header_frame.pack_propagate(False)
        
        headers = [('Время', 50), ('Пара', 60), ('Напр.', 50), ('Цена', 70), ('PNL', 70)]
        for i, (text, width) in enumerate(headers):
            tk.Label(
                header_frame,
                text=text,
                font=('Arial', 8, 'bold'),
                bg=self.colors['border'],
                fg='#ffffff',
                anchor='w'
            ).grid(row=0, column=i, sticky='w', padx=2)
        
        # Внутренний фрейм для строк - используем pack для совместимости
        self.history_content_frame = tk.Frame(self.history_container, bg=self.colors['panel'])
        self.history_content_frame.pack(fill='both', expand=True)
        
        # Пустой список - будет заполняться через update_history
        self.history_rows = []
    
    def _create_signals_panel(self, parent):
        """Создать панель торговых сигналов/возможностей"""
        panel = self._panel(parent, "🎯 ТОРГОВЫЕ ВОЗМОЖНОСТИ")
        
        # Контейнер для сигналов с прокруткой
        signals_frame = tk.Frame(panel, bg=self.colors['panel'])
        signals_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Заголовок таблицы
        header_frame = tk.Frame(signals_frame, bg=self.colors['border'], height=25)
        header_frame.pack(fill='x', pady=(0, 2))
        header_frame.pack_propagate(False)
        
        headers = [('Пара', 70), ('Напр.', 60), ('Уверенность', 90), ('Цена входа', 90), ('R/R', 60)]
        for i, (text, width) in enumerate(headers):
            tk.Label(
                header_frame,
                text=text,
                font=('Arial', 8, 'bold'),
                bg=self.colors['border'],
                fg='#ffffff',
                anchor='w'
            ).grid(row=0, column=i, sticky='w', padx=3, pady=3)
        
        # Область для сигналов с прокруткой
        scroll_frame = tk.Frame(signals_frame, bg=self.colors['panel'])
        scroll_frame.pack(fill='both', expand=True)
        
        # Scrollbar
        scrollbar = tk.Scrollbar(scroll_frame, bg=self.colors['panel'])
        scrollbar.pack(side='right', fill='y')
        
        # Canvas для прокрутки
        canvas = tk.Canvas(
            scroll_frame,
            bg=self.colors['panel'],
            highlightthickness=0,
            yscrollcommand=scrollbar.set
        )
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=canvas.yview)
        
        # Контейнер для сигналов внутри canvas
        self.signals_container = tk.Frame(canvas, bg=self.colors['panel'])
        canvas_window = canvas.create_window((0, 0), window=self.signals_container, anchor='nw')
        
        # Настройка прокрутки
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox('all'))
        
        def configure_canvas_width(event):
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
        
        self.signals_container.bind('<Configure>', configure_scroll_region)
        canvas.bind('<Configure>', configure_canvas_width)
        
        # Сохраняем ссылки
        self.signals_canvas = canvas
        self.signals_rows = []
    
    def _create_events_panel(self, parent):
        """Панель событий"""
        # Создаем Text виджет для событий (используется в add_event)
        self.events_text = tk.Text(
            parent,
            bg=self.colors['panel'],
            fg=self.colors['fg'],
            font=('Consolas', 8),
            relief='flat',
            wrap='word',
            state='disabled'
        )
        self.events_text.pack(fill='both', expand=True, padx=5, pady=5)
    
    def _create_ai_chat_panel(self, parent):
        """Создать встроенную панель AI чата"""
        from tkinter import messagebox
        import logging
        
        logging.info("🔄 Начало создания панели AI чата...")
        
        try:
            # Добавляем путь к core для импорта ConfigManager
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from core.config_manager import ConfigManager
            logging.info("✅ ConfigManager импортирован успешно")
        except ImportError as e:
            logging.error(f"❌ Ошибка импорта ConfigManager: {e}", exc_info=True)
            error_frame = tk.Frame(parent, bg='#252525', relief='flat', borderwidth=2)
            error_frame.pack(fill='both', expand=True, padx=5, pady=5)
            
            tk.Label(
                error_frame,
                text="❌ Ошибка импорта ConfigManager",
                font=('Arial', 10, 'bold'),
                bg='#252525',
                fg='#ef5350'
            ).pack(pady=5)
            
            error_label = tk.Label(
                error_frame,
                text=f"{str(e)}\n\nУбедитесь что файл core/config_manager.py существует.",
                font=('Arial', 9),
                bg='#252525',
                fg='#ef5350',
                justify='left',
                wraplength=330
            )
            error_label.pack(fill='both', expand=True, padx=10, pady=10)
            return
        
        try:
            # Создаем основной фрейм чата
            chat_frame = tk.Frame(parent, bg=self.colors['panel'], relief='flat', borderwidth=1)
            chat_frame.pack(fill='both', expand=True, padx=5, pady=5)
            logging.info("✅ chat_frame создан успешно")
        except Exception as e:
            logging.error(f"❌ Ошибка создания chat_frame: {e}", exc_info=True)
            raise
        
        # Заголовок
        header_frame = tk.Frame(chat_frame, bg=self.colors['border'], height=30)
        header_frame.pack(fill='x', padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        tk.Label(
            header_frame,
            text="💬 AI ЧАТ",
            font=('Arial', 10, 'bold'),
            bg=self.colors['border'],
            fg='#42a5f5',
            anchor='w'
        ).pack(side='left', padx=10, pady=5)
        
        # Статус подключения
        self.ai_status_label = tk.Label(
            header_frame,
            text="●",
            font=('Arial', 8),
            bg=self.colors['border'],
            fg=self.colors['fg_dim'],
            anchor='e'
        )
        self.ai_status_label.pack(side='right', padx=10, pady=5)
        
        # Область чата
        chat_area = tk.Frame(chat_frame, bg=self.colors['panel'])
        chat_area.pack(fill='both', expand=True, padx=0, pady=(0, 0))
        
        # Текстовое поле с историей (read-only)
        chat_scroll = tk.Scrollbar(chat_area, bg=self.colors['panel'])
        chat_scroll.pack(side='right', fill='y')
        
        self.ai_chat_text = scrolledtext.ScrolledText(
            chat_area,
            wrap=tk.WORD,
            bg=self.colors['panel'],
            fg=self.colors['fg'],
            font=('Consolas', 9),
            relief='flat',
            borderwidth=0,
            padx=10,
            pady=10,
            state='disabled',
            yscrollcommand=chat_scroll.set,
            height=35  # Увеличено для большего пространства чата
        )
        self.ai_chat_text.pack(fill='both', expand=True)
        chat_scroll.config(command=self.ai_chat_text.yview)
        
        # Настройка тегов для цветов
        self.ai_chat_text.tag_config('ai', foreground='#42a5f5', font=('Consolas', 9, 'bold'))
        self.ai_chat_text.tag_config('user', foreground='#26a69a', font=('Consolas', 9, 'bold'))
        self.ai_chat_text.tag_config('system', foreground=self.colors['fg_dim'], font=('Consolas', 8, 'italic'))
        self.ai_chat_text.tag_config('message', foreground=self.colors['fg'], font=('Consolas', 9))
        
        # Поле ввода внизу
        input_frame = tk.Frame(chat_frame, bg=self.colors['panel'], height=60)
        input_frame.pack(fill='x', padx=5, pady=(5, 5))
        input_frame.pack_propagate(False)
        
        self.ai_entry = tk.Entry(
            input_frame,
            bg=self.colors['bg'],
            fg=self.colors['fg'],
            font=('Consolas', 9),
            relief='flat',
            borderwidth=1,
            insertbackground=self.colors['fg']
        )
        self.ai_entry.pack(side='left', fill='both', expand=True, padx=(0, 5), pady=5)
        self.ai_entry.bind('<Return>', lambda e: self._send_ai_message())
        
        # Кнопка отправки
        send_button = tk.Button(
            input_frame,
            text="▶",
            font=('Arial', 10, 'bold'),
            bg='#26a69a',
            fg='#ffffff',
            relief='flat',
            padx=15,
            pady=5,
            cursor='hand2',
            command=self._send_ai_message
        )
        send_button.pack(side='right', pady=5)
        
        # Инициализация для AI чата
        import logging
        try:
            logging.info("🔄 Инициализация AI чата...")
            self.config_manager = ConfigManager()
            self.model_name = self.config.get('local_ai', {}).get('model_name', 'gemma3:4b')
            self.ai_last_code = None
            
            # Контекстный менеджер для AI (инициализируется позже когда бот готов)
            self.ai_context = None
            
            logging.info(f"✅ AI чат инициализирован, модель: {self.model_name}")
            
            # Приветствие
            welcome = "Привет! Я AI помощник вашего торгового бота.\n\n"
            welcome += "Я понимаю структуру программы и могу:\n"
            welcome += "• Изменять параметры в config.json\n"
            welcome += "• Редактировать код программы\n"
            welcome += "• Оптимизировать стратегию\n"
            welcome += "• Генерировать новый функционал\n\n"
            welcome += "Задавайте вопросы или давайте команды!"
            self._add_ai_chat_message("AI", welcome)
            
            # Проверка подключения
            self._check_ai_connection()
            logging.info("✅ AI чат готов к использованию")
        except Exception as e:
            logging.error(f"❌ Ошибка инициализации AI чата: {e}", exc_info=True)
            try:
                self._add_ai_chat_message("Система", f"❌ Ошибка инициализации: {str(e)}", 'system')
            except:
                pass
    
    def _send_ai_message(self):
        """Отправить сообщение AI"""
        if not hasattr(self, 'ai_entry'):
            return
        
        message = self.ai_entry.get().strip()
        if not message:
            return
        
        # Очищаем поле ввода
        self.ai_entry.delete(0, 'end')
        
        # Добавляем сообщение пользователя
        self._add_ai_chat_message("Вы", message, 'user')
        
        # Отправляем запрос AI в отдельном потоке
        def send_ai():
            try:
                import requests
                
                # Проверяем подключение
                try:
                    requests.get("http://localhost:11434/api/tags", timeout=2)
                except:
                    self.root.after(0, lambda: self._add_ai_chat_message("Система", "❌ Ollama недоступен. Запустите: ollama serve", 'system'))
                    return
                
                # Собираем простой промпт
                prompt = f"""ОБЯЗАТЕЛЬНО отвечай ТОЛЬКО на русском языке!

Пользователь написал: "{message}"

Что нужно сделать? Ответь на русском коротко и понятно.

Если не понял - скажи: "Не понял, уточните пожалуйста".

Короткий ответ на русском:"""
                
                self.root.after(0, lambda: self._add_ai_chat_message("AI", "Думаю...", 'system'))
                
                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.5,
                            "num_predict": 150
                        }
                    },
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    ai_response = result.get("response", "").strip()
                    
                    if ai_response:
                        # Удаляем "Думаю..."
                        self.root.after(0, lambda: self._remove_last_ai_message())
                        self.root.after(0, lambda: self._add_ai_chat_message("AI", ai_response))
                    else:
                        self.root.after(0, lambda: self._remove_last_ai_message())
                        self.root.after(0, lambda: self._add_ai_chat_message("AI", "Не понял запрос. Уточните пожалуйста.", 'system'))
                else:
                    self.root.after(0, lambda: self._remove_last_ai_message())
                    self.root.after(0, lambda: self._add_ai_chat_message("Система", f"❌ Ошибка: статус {response.status_code}", 'system'))
            except Exception as e:
                import logging
                logging.error(f"Ошибка отправки AI: {e}")
                self.root.after(0, lambda: self._remove_last_ai_message())
                self.root.after(0, lambda: self._add_ai_chat_message("Система", f"❌ Ошибка: {str(e)}", 'system'))
        
        threading.Thread(target=send_ai, daemon=True).start()
    
    def _add_ai_chat_message(self, sender: str, message: str, tag: str = 'message'):
        """Добавить сообщение в AI чат"""
        if not hasattr(self, 'ai_chat_text'):
            return
        
        try:
            self.ai_chat_text.config(state='normal')
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            self.ai_chat_text.insert('end', f"[{timestamp}] {sender}: ", tag)
            self.ai_chat_text.insert('end', f"{message}\n\n", tag)
            
            self.ai_chat_text.see('end')
            self.ai_chat_text.config(state='disabled')
        except Exception as e:
            import logging
            logging.error(f"Ошибка добавления сообщения в чат: {e}")
    
    def _remove_last_ai_message(self):
        """Удалить последнее системное сообщение"""
        if not hasattr(self, 'ai_chat_text'):
            return
        
        try:
            self.ai_chat_text.config(state='normal')
            content = self.ai_chat_text.get('1.0', 'end')
            lines = content.split('\n')
            if len(lines) >= 2:
                self.ai_chat_text.delete(f'end-{len(lines[-1])-1}c', 'end')
            self.ai_chat_text.config(state='disabled')
        except:
            pass
    
    def _check_ai_connection(self):
        """Проверка подключения к Ollama"""
        def check():
            try:
                import requests
                response = requests.get("http://localhost:11434/api/tags", timeout=3)
                if response.status_code == 200:
                    models = response.json().get('models', [])
                    model_names = [m['name'] for m in models]
                    if any(self.model_name in name for name in model_names):
                        self.root.after(0, lambda: self.ai_status_label.config(text="●", fg='#26a69a'))
                    else:
                        self.root.after(0, lambda: self.ai_status_label.config(text="●", fg='#ffa726'))
                else:
                    self.root.after(0, lambda: self.ai_status_label.config(text="●", fg='#ef5350'))
            except Exception:
                self.root.after(0, lambda: self.ai_status_label.config(text="●", fg='#ef5350'))
        
        threading.Thread(target=check, daemon=True).start()
    
    def _update_runtime(self):
        """Обновление времени работы"""
        try:
            self.runtime_seconds += 1
            h = self.runtime_seconds // 3600
            m = (self.runtime_seconds % 3600) // 60
            s = self.runtime_seconds % 60
            if hasattr(self, 'runtime_label'):
                self.runtime_label.config(text=f"{h:02d}:{m:02d}:{s:02d}")
        except (tk.TclError, AttributeError, Exception):
            # Окно уже закрыто или виджет уничтожен
            pass
        
        # Повторяем через 1 секунду
        if hasattr(self, 'root'):
            try:
                if self.root.winfo_exists():
                    self.root.after(1000, self._update_runtime)
            except:
                pass
    
    def update_account(self, balance, pnl, available, max_drawdown):
        """Обновить информацию о счете"""
        try:
            if not hasattr(self, 'balance_label'):
                return
            try:
                if not self.balance_label.winfo_exists():
                    return
            except:
                return
            
            pnl_percent = (pnl / self.starting_balance) * 100 if self.starting_balance > 0 else 0
            pnl_color = self.colors['green'] if pnl >= 0 else self.colors['red']
            pnl_sign = "+" if pnl >= 0 else ""
            
            self.balance_label.config(text=f"${balance:.2f}")
            self.pnl_label.config(text=f"{pnl_sign}${pnl:.2f} ({pnl_percent:+.2f}%)", fg=pnl_color)
            self.available_label.config(text=f"${available:.2f}")
            self.drawdown_label.config(text=f"{max_drawdown:.2f}%")
        except (tk.TclError, AttributeError, Exception) as e:
            # ВСЕГДА логируем ошибки GUI, но не показываем всплывающие окна
            try:
                import logging
                logging.error(f"❌ Ошибка GUI: {e}", exc_info=True)
            except:
                pass  # Если даже логирование не работает, просто пропускаем
            pass
    
    def update_statistics(self, stats):
        """Обновить статистику"""
        try:
            if not hasattr(self, 'trades_label'):
                return
            try:
                if not self.trades_label.winfo_exists():
                    return
            except:
                return
            
            self.trades_label.config(text=f"{stats.get('total_trades', 0)}")
            
            win_rate = stats.get('win_rate', 0)
            wr_color = self.colors['green'] if win_rate >= 55 else self.colors['red']
            winners = stats.get('winners', 0)
            self.winrate_label.config(text=f"{win_rate:.1f}% ({winners}/{stats.get('total_trades', 0)})", fg=wr_color)
            
            profit_factor = stats.get('profit_factor', 0)
            pf_color = self.colors['green'] if profit_factor >= 1.5 else self.colors['red']
            self.pf_label.config(text=f"{profit_factor:.2f}", fg=pf_color)
            
            avg_pnl = stats.get('avg_pnl', 0)
            avg_color = self.colors['green'] if avg_pnl >= 0 else self.colors['red']
            avg_sign = "+" if avg_pnl >= 0 else ""
            self.avg_pnl_label.config(text=f"{avg_sign}${avg_pnl:.2f}", fg=avg_color)
            
            total_costs = stats.get('total_commission', 0) + stats.get('total_funding', 0)
            self.costs_label.config(text=f"${total_costs:.2f}")
        except (tk.TclError, AttributeError, Exception) as e:
            # ВСЕГДА логируем ошибки GUI, но не показываем всплывающие окна
            try:
                import logging
                logging.error(f"❌ Ошибка GUI: {e}", exc_info=True)
            except:
                pass  # Если даже логирование не работает, просто пропускаем
            pass
    
    def update_history(self, closed_trades):
        """Обновить историю сделок"""
        try:
            if not hasattr(self, 'history_container') or not hasattr(self, 'history_content_frame'):
                return
            try:
                if not self.history_container.winfo_exists():
                    return
                if not self.history_content_frame.winfo_exists():
                    return
            except:
                return
            
            # Удаляем старые строки из контентного фрейма
            for widget in self.history_content_frame.winfo_children():
                widget.destroy()
            
            self.history_rows = []
            
            # Сортируем сделки по времени закрытия (новые сверху)
            sorted_trades = sorted(closed_trades, key=lambda t: t.exit_time, reverse=True)
            
            # Показываем последние 10 сделок
            for i, trade in enumerate(sorted_trades[:10]):
                row = tk.Frame(self.history_content_frame, bg=self.colors['panel'], height=20)
                row.pack(fill='x', padx=2, pady=1)
                
                # Время закрытия
                time_str = trade.exit_time.strftime("%H:%M:%S") if hasattr(trade.exit_time, 'strftime') else str(trade.exit_time)[:8]
                tk.Label(row, text=time_str, font=('Arial', 7), bg=self.colors['panel'], fg=self.colors['fg'], anchor='w').pack(side='left', padx=2)
                
                # Символ
                tk.Label(row, text=trade.symbol, font=('Arial', 7), bg=self.colors['panel'], fg=self.colors['fg'], anchor='w').pack(side='left', padx=2)
                
                # Направление
                direction_color = self.colors['green'] if trade.side == 'LONG' else self.colors['red']
                tk.Label(row, text=trade.side, font=('Arial', 7, 'bold'), bg=self.colors['panel'], fg=direction_color, anchor='w').pack(side='left', padx=2)
                
                # Цена выхода
                tk.Label(row, text=f"${trade.exit_price:.2f}", font=('Arial', 7), bg=self.colors['panel'], fg=self.colors['fg'], anchor='w').pack(side='left', padx=2)
                
                # PnL
                pnl_color = self.colors['green'] if trade.pnl >= 0 else self.colors['red']
                pnl_sign = "+" if trade.pnl >= 0 else ""
                tk.Label(row, text=f"{pnl_sign}${trade.pnl:.2f}", font=('Arial', 7, 'bold'), bg=self.colors['panel'], fg=pnl_color, anchor='w').pack(side='left', padx=2)
                
                self.history_rows.append(row)
        except (tk.TclError, AttributeError, Exception) as e:
            # ВСЕГДА логируем ошибки GUI, но не показываем всплывающие окна
            try:
                import logging
                logging.error(f"❌ Ошибка GUI: {e}", exc_info=True)
            except:
                pass  # Если даже логирование не работает, просто пропускаем
            pass
    
    def update_positions(self, positions, current_prices=None):
        """Обновить позиции"""
        try:
            if not hasattr(self, 'positions_container'):
                return
            try:
                if not self.positions_container.winfo_exists():
                    return
            except:
                return
            
            self.positions = positions
            
            # Удаляем старые строки (кроме заголовка)
            for widget in self.positions_container.winfo_children()[1:]:
                widget.destroy()
            
            self.position_rows = {}
            
            # Добавляем новые позиции - используем pack для совместимости
            for i, (symbol, position) in enumerate(positions.items()):
                row = tk.Frame(self.positions_container, bg=self.colors['panel'], height=25)
                row.pack(fill='x', padx=2, pady=1)
                
                # Position это dataclass, обращаемся к атрибутам напрямую
                entry = position.entry_price
                current = current_prices.get(symbol, position.current_price) if current_prices else position.current_price
                size = position.size
                direction = position.side  # 'side' в Position, а не 'direction'
                sl = position.stop_loss
                tp = position.take_profit_1  # Используем take_profit_1
                leverage = position.leverage
                margin = position.margin_usdt  # margin_usdt в Position
                pnl = position.unrealized_pnl
                
                tk.Label(row, text=symbol, font=('Arial', 8), bg=self.colors['panel'], fg=self.colors['fg'], anchor='w').pack(side='left', padx=5)
                tk.Label(row, text=direction, font=('Arial', 8), bg=self.colors['panel'], fg=self.colors['green'] if direction == 'LONG' else self.colors['red'], anchor='w').pack(side='left', padx=5)
                tk.Label(row, text=f"{size:.4f}", font=('Arial', 8), bg=self.colors['panel'], fg=self.colors['fg'], anchor='w').pack(side='left', padx=5)
                tk.Label(row, text=f"${entry:.2f}", font=('Arial', 8), bg=self.colors['panel'], fg=self.colors['fg'], anchor='w').pack(side='left', padx=5)
                tk.Label(row, text=f"${current:.2f}", font=('Arial', 8), bg=self.colors['panel'], fg=self.colors['fg'], anchor='w').pack(side='left', padx=5)
                tk.Label(row, text=f"${sl:.2f}", font=('Arial', 8), bg=self.colors['panel'], fg=self.colors['red'], anchor='w').pack(side='left', padx=5)
                tk.Label(row, text=f"${tp:.2f}", font=('Arial', 8), bg=self.colors['panel'], fg=self.colors['green'], anchor='w').pack(side='left', padx=5)
                tk.Label(row, text=f"{leverage}x", font=('Arial', 8), bg=self.colors['panel'], fg=self.colors['fg'], anchor='w').pack(side='left', padx=5)
                tk.Label(row, text=f"${margin:.2f}", font=('Arial', 8), bg=self.colors['panel'], fg=self.colors['fg'], anchor='w').pack(side='left', padx=5)
                
                pnl_color = self.colors['green'] if pnl >= 0 else self.colors['red']
                pnl_sign = "+" if pnl >= 0 else ""
                tk.Label(row, text=f"{pnl_sign}${pnl:.2f}", font=('Arial', 8), bg=self.colors['panel'], fg=pnl_color, anchor='w').pack(side='left', padx=5)
                
                close_btn = tk.Button(row, text="✕", font=('Arial', 8), bg=self.colors['red'], fg='#ffffff', width=3, cursor='hand2',
                                     command=lambda s=symbol: self._close_position(s))
                close_btn.pack(side='right', padx=5)
                
                self.position_rows[symbol] = row
        except (tk.TclError, AttributeError, Exception) as e:
            # ВСЕГДА логируем ошибки GUI, но не показываем всплывающие окна
            try:
                import logging
                logging.error(f"❌ Ошибка GUI: {e}", exc_info=True)
            except:
                pass  # Если даже логирование не работает, просто пропускаем
            pass
    
    def update_signals(self, signals):
        """Обновить панель торговых сигналов"""
        try:
            if not hasattr(self, 'signals_container'):
                return
            try:
                if not self.signals_container.winfo_exists():
                    return
            except:
                return
            
            # Удаляем старые строки
            for row in self.signals_rows:
                try:
                    row.destroy()
                except:
                    pass
            self.signals_rows = []
            
            # Сортируем сигналы по уверенности (убывание)
            sorted_signals = sorted(
                signals.items(),
                key=lambda x: x[1].confidence if hasattr(x[1], 'confidence') else 0,
                reverse=True
            )
            
            # Добавляем только торговые сигналы (LONG/SHORT)
            for i, (symbol, signal) in enumerate(sorted_signals):
                if not hasattr(signal, 'direction') or signal.direction not in ['LONG', 'SHORT']:
                    continue
                
                row = tk.Frame(self.signals_container, bg=self.colors['panel'], height=25)
                row.grid(row=i, column=0, sticky='ew', padx=2, pady=1)
                row.grid_columnconfigure(0, minsize=70)
                row.grid_columnconfigure(1, minsize=60)
                row.grid_columnconfigure(2, minsize=90)
                row.grid_columnconfigure(3, minsize=90)
                row.grid_columnconfigure(4, minsize=60)
                
                # Пара
                tk.Label(
                    row,
                    text=symbol,
                    font=('Arial', 8),
                    bg=self.colors['panel'],
                    fg=self.colors['fg'],
                    anchor='w'
                ).grid(row=0, column=0, sticky='w', padx=3)
                
                # Направление
                direction_color = self.colors['green'] if signal.direction == 'LONG' else self.colors['red']
                tk.Label(
                    row,
                    text=signal.direction,
                    font=('Arial', 8, 'bold'),
                    bg=self.colors['panel'],
                    fg=direction_color,
                    anchor='w'
                ).grid(row=0, column=1, sticky='w', padx=3)
                
                # Уверенность
                conf_color = self.colors['green'] if signal.confidence >= 70 else self.colors['yellow'] if signal.confidence >= 60 else self.colors['fg_dim']
                tk.Label(
                    row,
                    text=f"{signal.confidence:.1f}%",
                    font=('Arial', 8, 'bold'),
                    bg=self.colors['panel'],
                    fg=conf_color,
                    anchor='w'
                ).grid(row=0, column=2, sticky='w', padx=3)
                
                # Цена входа
                tk.Label(
                    row,
                    text=f"${signal.entry_price:.2f}",
                    font=('Arial', 8),
                    bg=self.colors['panel'],
                    fg=self.colors['fg'],
                    anchor='w'
                ).grid(row=0, column=3, sticky='w', padx=3)
                
                # R/R
                risk_reward = getattr(signal, 'risk_reward', 0)
                rr_color = self.colors['green'] if risk_reward >= 2 else self.colors['yellow'] if risk_reward >= 1.5 else self.colors['fg_dim']
                tk.Label(
                    row,
                    text=f"{risk_reward:.2f}",
                    font=('Arial', 8),
                    bg=self.colors['panel'],
                    fg=rr_color,
                    anchor='w'
                ).grid(row=0, column=4, sticky='w', padx=3)
                
                self.signals_rows.append(row)
            
            # Настраиваем колонки
            self.signals_container.grid_columnconfigure(0, weight=1)
            
            # Обновляем прокрутку
            if hasattr(self, 'signals_canvas'):
                self.signals_canvas.update_idletasks()
                self.signals_canvas.configure(scrollregion=self.signals_canvas.bbox('all'))
        except (tk.TclError, AttributeError, Exception) as e:
            # ВСЕГДА логируем ошибки GUI, но не показываем всплывающие окна
            try:
                import logging
                logging.error(f"❌ Ошибка GUI: {e}", exc_info=True)
            except:
                pass  # Если даже логирование не работает, просто пропускаем
            pass
    
    def add_event(self, event_text: str, event_type: str = 'info'):
        """Добавить событие в лог"""
        try:
            if not hasattr(self, 'events_text'):
                return
            try:
                if not self.events_text.winfo_exists():
                    return
            except:
                return
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            self.events.append((timestamp, event_text, event_type))
            
            # Ограничиваем размер
            if len(self.events) > 50:
                self.events = self.events[-50:]
            
            self.events_text.config(state='normal')
            self.events_text.insert('end', f"[{timestamp}] {event_text}\n")
            self.events_text.see('end')
            self.events_text.config(state='disabled')
        except (tk.TclError, AttributeError, Exception) as e:
            # ВСЕГДА логируем ошибки GUI, но не показываем всплывающие окна
            try:
                import logging
                logging.error(f"❌ Ошибка GUI: {e}", exc_info=True)
            except:
                pass  # Если даже логирование не работает, просто пропускаем
            pass
    
    def _on_strictness_change(self, value):
        """Обработчик изменения ползунка жесткости"""
        try:
            strictness = float(value)
            self.strictness_label.config(text=f"{strictness:.0f}%")
            
            # Определяем режим торговли
            if strictness <= 25:  # 1-25% - консервативная
                mode = "Консервативная"
                mode_color = '#26a69a'  # Зеленый
            elif strictness <= 75:  # 26-75% - умеренная
                mode = "Умеренная"
                mode_color = '#42a5f5'  # Синий
            else:  # 76-100% - агрессивная
                mode = "Агрессивная"
                mode_color = '#ef5350'  # Красный
            
            self.mode_label.config(text=f"({mode})", fg=mode_color)
            
            # Передаем значение жесткости в бот
            if hasattr(self, 'bot_instance') and self.bot_instance:
                if hasattr(self.bot_instance, 'set_strictness'):
                    self.bot_instance.set_strictness(strictness)
                    # Добавляем событие в лог
                    self.add_event(f"🔧 Режим торговли: {mode} ({strictness:.0f}%)", 'info')
        except Exception as e:
            import logging
            logging.error(f"Ошибка изменения жесткости: {e}")
    
    def _close_position(self, symbol):
        """Закрыть позицию"""
        if self.close_position_callback:
            self.close_position_callback(symbol)