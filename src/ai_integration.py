"""
🤖 AI Integration Module
Интеграция ИИ системы с торговым дашбордом
"""

import sys
import os
import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional
import tkinter as tk
from tkinter import scrolledtext, ttk
import queue
import random

class AIInterface:
    """Интерфейс для интеграции ИИ с дашбордом"""
    
    def __init__(self):
        self.message_queue = queue.Queue()
        self.is_running = False
        self.current_status = "Инициализация..."
        self.performance_metrics = {
            'winrate': 0.0,
            'total_trades': 0,
            'profit': 0.0,
            'balance': 100.0
        }
        
    def initialize_ai_systems(self):
        """Инициализирует все ИИ системы"""
        try:
            print("🚀 Инициализация ИИ систем...")
            
            self.current_status = "ИИ системы готовы"
            self.message_queue.put(("SUCCESS", "✅ Все ИИ системы успешно инициализированы"))
            
        except Exception as e:
            error_msg = f"❌ Ошибка инициализации ИИ: {str(e)}"
            self.message_queue.put(("ERROR", error_msg))
            self.current_status = "Ошибка инициализации"
            print(error_msg)
    
    def start_ai_analysis(self):
        """Запускает анализ ИИ"""
        if not self.is_running:
            self.is_running = True
            self.message_queue.put(("INFO", "🔍 Запуск анализа ИИ..."))
            
            # Запускаем анализ в отдельном потоке
            analysis_thread = threading.Thread(target=self._run_ai_analysis, daemon=True)
            analysis_thread.start()
    
    def _run_ai_analysis(self):
        """Выполняет анализ ИИ в фоновом режиме"""
        try:
            while self.is_running:
                # Симулируем анализ ИИ
                self._simulate_ai_analysis()
                
                # Обновляем метрики
                self._update_performance_metrics()
                
                # Ждем 5 секунд
                time.sleep(5)
                
        except Exception as e:
            error_msg = f"❌ Ошибка анализа ИИ: {str(e)}"
            self.message_queue.put(("ERROR", error_msg))
    
    def _simulate_ai_analysis(self):
        """Симулирует анализ ИИ"""
        # Симулируем различные типы анализа
        analysis_types = [
            "Анализ технических индикаторов",
            "Оценка рыночных условий",
            "Прогнозирование движения цен",
            "Оптимизация параметров стратегий",
            "Анализ рисков",
            "Обучение на новых данных"
        ]
        
        current_analysis = random.choice(analysis_types)
        self.message_queue.put(("INFO", f"🔍 {current_analysis}"))
        
        # Симулируем результаты анализа
        if random.random() < 0.3:  # 30% шанс на сигнал
            signals = ["LONG", "SHORT", "NEUTRAL"]
            signal = random.choice(signals)
            confidence = random.uniform(0.6, 0.95)
            
            self.message_queue.put(("SIGNAL", f"📊 Сигнал: {signal} (уверенность: {confidence:.1%})"))
    
    def _update_performance_metrics(self):
        """Обновляет метрики производительности"""
        # Симулируем изменения метрик
        self.performance_metrics['winrate'] += random.uniform(-1, 1)
        self.performance_metrics['winrate'] = max(0, min(100, self.performance_metrics['winrate']))
        
        self.performance_metrics['total_trades'] += random.randint(0, 2)
        
        profit_change = random.uniform(-10, 20)
        self.performance_metrics['profit'] += profit_change
        self.performance_metrics['balance'] += profit_change
        
        # Отправляем обновленные метрики
        self.message_queue.put(("METRICS", json.dumps(self.performance_metrics)))
    
    def stop_ai_analysis(self):
        """Останавливает анализ ИИ"""
        self.is_running = False
        self.message_queue.put(("INFO", "⏹️ Анализ ИИ остановлен"))
    
    def get_current_status(self) -> str:
        """Возвращает текущий статус ИИ"""
        return self.current_status
    
    def get_performance_metrics(self) -> Dict:
        """Возвращает текущие метрики производительности"""
        return self.performance_metrics.copy()
    
    def get_message(self) -> Optional[tuple]:
        """Получает сообщение из очереди"""
        try:
            return self.message_queue.get_nowait()
        except queue.Empty:
            return None

class AIRightPanel:
    """Правая панель с ИИ интерфейсом"""
    
    def __init__(self, parent, ai_interface: AIInterface):
        self.parent = parent
        self.ai_interface = ai_interface
        self.colors = {
            'bg_dark': '#1a1a2e',        # Темно-синий с фиолетовым оттенком
            'bg_card': '#16213e',        # Синий с глубиной
            'bg_header': '#0f3460',      # Темно-синий
            'text_white': '#e94560',     # Розово-красный для акцентов
            'text_gray': '#c7c7c7',      # Светло-серый
            'green': '#00d4aa',          # Бирюзовый зеленый
            'red': '#ff6b6b',            # Коралловый красный
            'blue': '#4ecdc4',           # Бирюзовый
            'yellow': '#ffe66d',         # Мягкий желтый
            'purple': '#a8e6cf',         # Мятно-зеленый
            'cyan': '#ffd93d',           # Золотистый
            'orange': '#ff8b94'          # Розовый
        }
        
        self.setup_ui()
        self.start_message_polling()
    
    def setup_ui(self):
        """Настраивает интерфейс правой панели"""
        # Основной контейнер
        self.main_frame = tk.Frame(self.parent, bg=self.colors['bg_dark'])
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Canvas с закругленными углами
        self.canvas = tk.Canvas(self.main_frame, bg=self.colors['bg_header'], 
                              highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Рисуем закругленный фон
        self.create_rounded_rectangle(self.canvas, 0, 0, 400, 600, 12, 
                                    fill=self.colors['bg_header'], 
                                    outline=self.colors['blue'], width=2)
        
        # Создаем элементы интерфейса
        self.create_header()
        self.create_status_section()
        self.create_metrics_section()
        self.create_log_section()
        self.create_control_buttons()
    
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
    
    def create_header(self):
        """Создает заголовок"""
        header_label = tk.Label(self.canvas, text="🧠 ИИ Анализ", 
                               font=("Arial", 16, "bold"),
                               fg=self.colors['text_white'], 
                               bg=self.colors['bg_header'])
        header_label.pack(pady=20)
    
    def create_status_section(self):
        """Создает секцию статуса"""
        status_frame = tk.Frame(self.canvas, bg=self.colors['bg_header'])
        status_frame.pack(fill=tk.X, padx=20, pady=10)
        
        status_label = tk.Label(status_frame, text="Статус:", 
                               font=("Arial", 12, "bold"),
                               fg=self.colors['text_gray'], 
                               bg=self.colors['bg_header'])
        status_label.pack(anchor=tk.W)
        
        self.status_var = tk.StringVar(value="Инициализация...")
        self.status_display = tk.Label(status_frame, textvariable=self.status_var,
                                      font=("Arial", 11),
                                      fg=self.colors['green'], 
                                      bg=self.colors['bg_header'])
        self.status_display.pack(anchor=tk.W, pady=5)
    
    def create_metrics_section(self):
        """Создает секцию метрик"""
        metrics_frame = tk.Frame(self.canvas, bg=self.colors['bg_header'])
        metrics_frame.pack(fill=tk.X, padx=20, pady=10)
        
        metrics_label = tk.Label(metrics_frame, text="Метрики:", 
                                font=("Arial", 12, "bold"),
                                fg=self.colors['text_gray'], 
                                bg=self.colors['bg_header'])
        metrics_label.pack(anchor=tk.W)
        
        self.metrics_display = tk.Label(metrics_frame, text="Загрузка...",
                                       font=("Arial", 10),
                                       fg=self.colors['text_white'], 
                                       bg=self.colors['bg_header'],
                                       justify=tk.LEFT)
        self.metrics_display.pack(anchor=tk.W, pady=5)
    
    def create_log_section(self):
        """Создает секцию лога"""
        log_frame = tk.Frame(self.canvas, bg=self.colors['bg_header'])
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        log_label = tk.Label(log_frame, text="Лог ИИ:", 
                            font=("Arial", 12, "bold"),
                            fg=self.colors['text_gray'], 
                            bg=self.colors['bg_header'])
        log_label.pack(anchor=tk.W)
        
        # Создаем текстовое поле для лога
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            width=40,
            height=15,
            font=("Consolas", 10),
            bg=self.colors['bg_card'],
            fg=self.colors['text_white'],
            insertbackground=self.colors['text_white'],
            selectbackground=self.colors['blue'],
            relief=tk.FLAT,
            borderwidth=0,
            wrap=tk.WORD
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text.config(state=tk.DISABLED)
        
        # Настраиваем теги для цветов
        self.log_text.tag_configure("INFO", foreground=self.colors['cyan'])
        self.log_text.tag_configure("SUCCESS", foreground=self.colors['green'])
        self.log_text.tag_configure("ERROR", foreground=self.colors['red'])
        self.log_text.tag_configure("SIGNAL", foreground=self.colors['yellow'])
        self.log_text.tag_configure("METRICS", foreground=self.colors['purple'])
    
    def create_control_buttons(self):
        """Создает кнопки управления"""
        button_frame = tk.Frame(self.canvas, bg=self.colors['bg_header'])
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Кнопка запуска/остановки анализа
        self.analysis_button = tk.Button(
            button_frame,
            text="▶️ Запустить анализ",
            command=self.toggle_ai_analysis,
            font=("Arial", 11, "bold"),
            bg=self.colors['green'],
            fg=self.colors['text_white'],
            relief=tk.FLAT,
            borderwidth=0,
            padx=15,
            pady=5
        )
        self.analysis_button.pack(side=tk.LEFT, padx=5)
        
        # Кнопка очистки лога
        clear_button = tk.Button(
            button_frame,
            text="🗑️ Очистить",
            command=self.clear_log,
            font=("Arial", 11),
            bg=self.colors['red'],
            fg=self.colors['text_white'],
            relief=tk.FLAT,
            borderwidth=0,
            padx=15,
            pady=5
        )
        clear_button.pack(side=tk.RIGHT, padx=5)
    
    def toggle_ai_analysis(self):
        """Переключает состояние анализа ИИ"""
        if self.ai_interface.is_running:
            self.ai_interface.stop_ai_analysis()
            self.analysis_button.config(text="▶️ Запустить анализ", bg=self.colors['green'])
        else:
            self.ai_interface.start_ai_analysis()
            self.analysis_button.config(text="⏹️ Остановить анализ", bg=self.colors['red'])
    
    def clear_log(self):
        """Очищает лог"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def add_log_message(self, message: str, level: str = "INFO"):
        """Добавляет сообщение в лог"""
        try:
            self.log_text.config(state=tk.NORMAL)
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}\n"
            
            # Используем тег для цвета
            self.log_text.insert(tk.END, formatted_message, level.upper())
            self.log_text.see(tk.END)
            
            # Ограничиваем количество строк
            lines = self.log_text.get(1.0, tk.END).split('\n')
            if len(lines) > 200:
                self.log_text.delete(1.0, f"{len(lines)-200}.0")
                
            self.log_text.config(state=tk.DISABLED)
            
        except Exception as e:
            print(f"Ошибка добавления сообщения в лог ИИ: {e}")
    
    def update_metrics(self, metrics: dict):
        """Обновляет отображение метрик"""
        try:
            metrics_text = f"Винрейт: {metrics.get('winrate', 0):.1f}%\n"
            metrics_text += f"Сделок: {metrics.get('total_trades', 0)}\n"
            metrics_text += f"Прибыль: ${metrics.get('profit', 0):.2f}\n"
            metrics_text += f"Баланс: ${metrics.get('balance', 0):.2f}"
            
            self.metrics_display.config(text=metrics_text)
        except Exception as e:
            print(f"Ошибка обновления метрик: {e}")
    
    def update_status(self, status: str):
        """Обновляет статус"""
        try:
            self.status_var.set(status)
        except Exception as e:
            print(f"Ошибка обновления статуса: {e}")
    
    def start_message_polling(self):
        """Запускает опрос сообщений от ИИ"""
        def poll_messages():
            while True:
                try:
                    message = self.ai_interface.get_message()
                    if message:
                        level, content = message
                        
                        if level == "METRICS":
                            try:
                                metrics = json.loads(content)
                                self.update_metrics(metrics)
                            except:
                                pass
                        else:
                            self.add_log_message(content, level)
                    
                    # Обновляем статус
                    self.update_status(self.ai_interface.get_current_status())
                    
                    time.sleep(0.1)  # Проверяем каждые 100мс
                    
                except Exception as e:
                    print(f"Ошибка опроса сообщений ИИ: {e}")
                    time.sleep(1)
        
        # Запускаем опрос в отдельном потоке
        polling_thread = threading.Thread(target=poll_messages, daemon=True)
        polling_thread.start() 