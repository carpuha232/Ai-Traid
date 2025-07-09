"""
🎨 Компактный торговый терминал
Все 30 монет на одном экране без скролла
Модульная архитектура
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
from datetime import datetime
import random
import sys
import os

# Импорты модулей из корня проекта
try:
    from core.dashboard_core import DashboardCore
    from core.dashboard_ui import DashboardUI
    from core.dashboard_logic import DashboardLogic
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"ImportError: {e}")
    MODULES_AVAILABLE = False

class CompactTradingDashboard:
    """Компактный торговый дашборд с модульной архитектурой"""
    
    def __init__(self, root):
        self.root = root
        
        if MODULES_AVAILABLE:
            # Инициализация модулей
            self.core = DashboardCore(root)
            self.ui = DashboardUI(self.core)
            self.logic = DashboardLogic(self.core, self.ui)
            # Связываем core, ui, logic для корректного доступа
            self.core.logic = self.logic
            self.core.ui = self.ui
            
            # Настройка интерфейса
            self.ui.setup_compact_ui()
            
            # Запуск обновления цен
            self.logic.start_price_updates()
            
            # Запускаем немедленный анализ ИИ только после полной инициализации GUI
            self.root.after(3000, self.logic.delayed_ai_start)
        else:
            # Fallback - простая версия без модулей
            self._init_fallback()
    
    def _init_fallback(self):
        """Инициализация fallback версии"""
        self.root.title("📊 Компактный торговый терминал (Fallback)")
        self.root.geometry("1920x1080")
        
        # Простой интерфейс
        label = tk.Label(self.root, text="Модули дашборда недоступны\nПроверьте файлы в папке trading_bot/", 
                        font=("Arial", 16), fg="white", bg="#0f1419")
        label.pack(expand=True)

    def start_simulation(self):
        """Запускает симуляцию (отключено)"""
        pass

    def stop_simulation(self):
        """Останавливает симуляцию (отключено)"""
        pass

    def clear_terminal(self):
        """Очищает терминал"""
        if hasattr(self.ui, 'terminal_text') and self.ui.terminal_text is not None:
            self.ui.terminal_text.config(state=tk.NORMAL)
            self.ui.terminal_text.delete(1.0, tk.END)
            self.ui.terminal_text.config(state=tk.DISABLED)

    def update_positions_table(self):
        """Обновляет таблицу открытых позиций (отключено)"""
        pass

    def on_position_action(self, event):
        """Обработка ручного закрытия позиции (отключено)"""
        pass

    def start_positions_update(self):
        """Запускает периодическое обновление таблицы открытых позиций (отключено)"""
        pass

def main():
    """Главная функция"""
    root = tk.Tk()
    
    # Принудительно отображаем окно на переднем плане
    root.lift()
    root.attributes('-topmost', True)
    root.after_idle(root.attributes, '-topmost', False)
    
    app = CompactTradingDashboard(root)
    
    # Убеждаемся, что окно видимо
    root.deiconify()
    root.focus_force()
    
    print("🚀 Торговый дашборд запущен!")
    print("📝 Проверьте, отображается ли окно с терминалом")
    
    root.mainloop()

if __name__ == "__main__":
    main() 