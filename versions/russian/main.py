#!/usr/bin/env python3
"""
🤖 AUTO SCALPING BOT - UNIFIED VERSION
Объединенная версия с лучшими функциями из V1, V2, V3
"""

import asyncio
import logging
import sys
import traceback
import tkinter as tk
import threading
from pathlib import Path
from datetime import datetime

# Импорты наших модулей
from core.binance_client import BinanceRealtimeClient
from core.signal_analyzer import SignalAnalyzer
from core.adaptive_learning import AdaptiveLearning
from core.config_manager import ConfigManager
from core.bot_core import BotCore
from simulation.paper_trader import PaperTrader
from gui.premium_window import PremiumScalpingGUI

# Глобальный обработчик исключений (V3)
def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Глобальный обработчик всех необработанных исключений"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    try:
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        try:
            logger.error(f"❌ Необработанное исключение: {error_msg}", exc_info=False)
        except:
            print(f"❌ Необработанное исключение (logger недоступен): {error_msg}")
        
        print(f"❌ Необработанное исключение: {exc_type.__name__}: {exc_value}")
        print("Подробности в логе.")
    except Exception as e:
        print(f"❌ Критическая ошибка при обработке исключения: {e}")
        print(f"Оригинальная ошибка: {exc_type.__name__}: {exc_value}")

sys.excepthook = global_exception_handler

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/bot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)


class AutoScalpingBot:
    """Главный класс бота автоматического скальпинга"""
    
    def __init__(self, config_path: str = "config.json"):
        """Инициализация бота"""
        try:
            self.config_manager = ConfigManager(config_path)
            self.config = self.config_manager.config
            
            logger.info("="*60)
            logger.info("🤖 АВТОМАТИЧЕСКИЙ СКАЛЬПИНГ-БОТ - ОБЪЕДИНЕННАЯ ВЕРСИЯ")
            logger.info("="*60)
            
            if self.config['api']['key'] == "ВСТАВЬ_СВОЙ_API_KEY_СЮДА":
                logger.error("❌ API ключи не настроены! Отредактируй config.json")
                raise ValueError("API ключи не настроены")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации бота: {e}", exc_info=True)
            raise
        
        # Инициализация компонентов
        self.binance_client = BinanceRealtimeClient(
            self.config['api']['key'],
            self.config['api']['secret']
        )
        
        self.learning = AdaptiveLearning(self.config)
        self.signal_analyzer = SignalAnalyzer(self.config, self.learning)
        self.signal_analyzer.set_trading_mode("Умеренная")
        
        self.paper_trader = PaperTrader(
            self.config,
            self.config['account']['starting_balance']
        )
        
        # GUI
        try:
            self.root = tk.Tk()
            self.gui = PremiumScalpingGUI(self.root, self.config)
            self.gui.bot_instance = self
            self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
            self.gui.set_close_position_callback(self._close_position_callback)
        except Exception as e:
            logger.error(f"❌ Ошибка создания GUI: {e}", exc_info=True)
            if hasattr(self, 'root'):
                try:
                    self.root.destroy()
                except:
                    pass
            raise
        
        # Состояние
        self.running = False
        self.pairs = self.config['pairs']
        self.current_signals = {}
        self._last_signal_log = None
        
        # Параметры жесткости анализа (V3)
        self.strictness_percent = 50.0  # По умолчанию 50% (умеренная)
        self.base_min_confidence = self.config['signals']['min_confidence']
        self.base_min_trades = 3
        self.base_max_price_diff = 0.002
        
        # Инициализация core логики
        self.core = BotCore(self)
        
        logger.info("✅ Все компоненты инициализированы")
    
    def set_strictness(self, strictness_percent: float):
        """Установить жесткость анализа (1-100%) с тремя режимами (V3)"""
        self.strictness_percent = max(1.0, min(100.0, strictness_percent))
        
        if strictness_percent <= 25:
            mode = "Консервативная"
        elif strictness_percent <= 75:
            mode = "Умеренная"
        else:
            mode = "Агрессивная"
        
        logger.info(f"🔧 Режим торговли: {mode} ({self.strictness_percent:.1f}%)")
        
        if hasattr(self, 'signal_analyzer'):
            self.signal_analyzer.set_trading_mode(mode)
    
    def _close_position_callback(self, symbol: str, order_type: str):
        """Callback для закрытия позиции через GUI"""
        if symbol in self.paper_trader.positions:
            position = self.paper_trader.positions[symbol]
            current_price = self.binance_client.get_current_price(symbol)
            if current_price > 0:
                closed_trade = self.paper_trader.close_position_manually(
                    symbol, current_price, f"Manual {order_type}"
                )
                if closed_trade:
                    self.learning.learn_from_trade(closed_trade)
                    logger.info(f"🔹 Закрыта позиция {symbol} вручную ({order_type})")
    
    def _on_window_close(self):
        """Обработчик закрытия окна GUI"""
        logger.info("⏹️ Окно GUI закрыто пользователем")
        self.running = False
        try:
            self.root.destroy()
        except tk.TclError:
            pass
    
    def _safe_gui_call(self, func, *args, **kwargs):
        """Безопасный вызов GUI функции из async потока"""
        try:
            if hasattr(self, 'root') and self.root.winfo_exists():
                self.root.after(0, func, *args, **kwargs)
        except (tk.TclError, AttributeError):
            pass
    
    async def start(self):
        """Запуск бота (V3: быстрый прогрев, минимальные задержки)"""
        connection_errors = 0
        max_connection_errors = 5
        self._boot_time = datetime.now()
        
        try:
            self.running = True
            
            logger.info("⏳ Ожидание готовности GUI...")
            await asyncio.sleep(0.1)  # V3: минимальная задержка
            
            logger.info("📡 Подключение к Binance...")
            await self.binance_client.start_streams(self.pairs)
            
            # V3: Быстрый прогрев
            logger.info("⏳ Быстрый прогрев...")
            warmup_deadline = datetime.now().timestamp() + 10
            ready_min = max(1, len(self.pairs)//3)
            logger.info(f"Требуется минимум {ready_min} готовых пар из {len(self.pairs)}")
            
            for _ in range(5):
                ready = []
                for symbol in self.pairs:
                    state = self.binance_client.book_state.get(symbol)
                    if state and state.get('synced'):
                        ready.append(symbol)
                
                if len(ready) >= ready_min:
                    logger.info(f"✅ Прогрев завершён: готово {len(ready)}/{len(self.pairs)} пар")
                    break
                
                if datetime.now().timestamp() > warmup_deadline:
                    logger.warning(
                        f"⚠️ Прогрев по тайм-ауту: готово {len(ready)}/{len(self.pairs)} — стартуем"
                    )
                    break
                
                await asyncio.sleep(0.2)
            
            self._safe_gui_call(self.gui.add_event, "🚀 Бот запущен! Мониторинг начат...", 'info')
            logger.info("🚀 Бот запущен и мониторит рынок...")
            
            # Главный цикл
            while self.running:
                try:
                    await self._main_loop()
                    connection_errors = 0
                    await asyncio.sleep(0.1)  # V3: минимальная задержка (100ms)
                    
                except ConnectionError as e:
                    connection_errors += 1
                    logger.warning(f"⚠️ Ошибка соединения ({connection_errors}/{max_connection_errors}): {e}")
                    
                    if connection_errors >= max_connection_errors:
                        logger.error("❌ Слишком много ошибок подключения. Остановка бота.")
                        self._safe_gui_call(self.gui.add_event, "❌ Критическая ошибка соединения", 'error')
                        break
                    
                    await asyncio.sleep(0.5)
                    
                except KeyboardInterrupt:
                    logger.info("⏹️ Получен сигнал остановки (Ctrl+C)")
                    break
                    
                except tk.TclError:
                    logger.info("⏹️ GUI окно закрыто")
                    break
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка в главном цикле: {e}", exc_info=True)
                    self._safe_gui_call(self.gui.add_event, f"⚠️ Ошибка в цикле: {str(e)[:50]}", 'error')
                    await asyncio.sleep(0.1)
            
        except KeyboardInterrupt:
            logger.info("⏹️ Получен сигнал остановки (Ctrl+C)...")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
            try:
                self._safe_gui_call(self.gui.add_event, f"❌ Критическая ошибка: {e}", 'error')
            except:
                pass
        finally:
            await self.stop()
    
    async def _main_loop(self):
        """Главный цикл анализа и торговли"""
        # Обновляем открытые позиции
        await self.core._update_positions()
        
        # Анализируем сигналы
        all_signals = await self.core._analyze_signals()
        
        # Открываем лучшие позиции
        await self.core._open_best_positions(all_signals)
        
        # Логируем статистику
        self.core._log_statistics()
        
        # Обновляем GUI
        self._update_gui()
    
    def _update_gui(self):
        """Обновление всех данных в GUI"""
        try:
            if not self.running or not hasattr(self, 'root'):
                return
            try:
                if not self.root.winfo_exists():
                    return
            except tk.TclError:
                return
            
            available = self.paper_trader.get_available_balance()
            pnl = self.paper_trader.balance - self.paper_trader.starting_balance
            
            self._safe_gui_call(self.gui.update_account,
                self.paper_trader.balance, pnl, available, self.paper_trader.max_drawdown
            )
            
            stats = self.paper_trader.get_statistics()
            self._safe_gui_call(self.gui.update_statistics, stats)
            
            current_prices_dict = {}
            for symbol in self.paper_trader.positions.keys():
                price = self.binance_client.get_current_price(symbol)
                if price > 0:
                    current_prices_dict[symbol] = price
            
            self._safe_gui_call(self.gui.update_positions, self.paper_trader.positions, current_prices_dict)
            
            if hasattr(self.gui, 'update_history'):
                self._safe_gui_call(self.gui.update_history, self.paper_trader.closed_trades)
            
            self._safe_gui_call(self.gui.update_signals, self.current_signals)
            
        except tk.TclError:
            self.running = False
        except Exception as e:
            logger.error(f"Ошибка обновления GUI: {e}")
    
    async def stop(self):
        """Остановка бота"""
        logger.info("⏹️ Остановка бота...")
        self.running = False
        
        if self.paper_trader.positions:
            logger.info("Закрываем все открытые позиции...")
            current_prices = {
                symbol: self.binance_client.get_current_price(symbol)
                for symbol in self.paper_trader.positions.keys()
            }
            self.paper_trader.close_all_positions(current_prices)
        
        await self.binance_client.stop()
        
        if self.config['logging']['save_session']:
            filename = f"results/session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            Path("results").mkdir(exist_ok=True)
            self.paper_trader.save_session(filename)
        
        self._show_final_stats()
        logger.info("✅ Бот остановлен")
    
    def _show_final_stats(self):
        """Показать итоговую статистику"""
        stats = self.paper_trader.get_statistics()
        
        logger.info("")
        logger.info("="*60)
        logger.info("📊 ИТОГОВАЯ СТАТИСТИКА")
        logger.info("="*60)
        logger.info(f"Starting Balance:  ${self.paper_trader.starting_balance:.2f}")
        logger.info(f"Final Balance:     ${self.paper_trader.balance:.2f}")
        logger.info(f"Total P&L:         ${self.paper_trader.total_pnl:+.2f} ({(self.paper_trader.total_pnl/self.paper_trader.starting_balance*100):+.2f}%)")
        logger.info(f"Max Drawdown:      {self.paper_trader.max_drawdown:.2f}%")
        logger.info("-"*60)
        logger.info(f"Total Trades:      {stats['total_trades']}")
        logger.info(f"Winners:           {stats['winners']} ({stats['win_rate']:.1f}%)")
        logger.info(f"Losers:            {stats['losers']}")
        logger.info(f"Avg Win:           ${stats['avg_win']:.2f}")
        logger.info(f"Avg Loss:          ${stats['avg_loss']:.2f}")
        logger.info(f"Profit Factor:     {stats['profit_factor']:.2f}")
        logger.info(f"Best Trade:        ${stats['best_trade']:.2f}")
        logger.info(f"Worst Trade:       ${stats['worst_trade']:.2f}")
        logger.info(f"Avg Duration:      {stats['avg_duration']:.0f}s")
        logger.info("-"*60)
        logger.info(self.learning.get_learning_summary())
        logger.info("="*60)
    
    def _asyncio_thread(self):
        """Запуск asyncio в отдельном потоке"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.start())
        except KeyboardInterrupt:
            logger.info("⏹️ Получен Ctrl+C в asyncio потоке")
        except Exception as e:
            logger.error(f"❌ Ошибка в asyncio потоке: {e}", exc_info=True)
    
    def run(self):
        """Запуск бота (синхронная обертка)"""
        try:
            try:
                self.root.update_idletasks()
                self.root.update()
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при подготовке окна: {e}")
            
            try:
                asyncio_thread = threading.Thread(target=self._asyncio_thread, daemon=True)
                asyncio_thread.start()
                logger.info("✅ Asyncio поток запущен")
            except Exception as e:
                logger.error(f"❌ Ошибка запуска asyncio потока: {e}", exc_info=True)
                raise
            
            try:
                self.root.mainloop()
            except Exception as e:
                logger.error(f"❌ Ошибка в mainloop: {e}", exc_info=True)
            
        except KeyboardInterrupt:
            logger.info("⏹️ Получен Ctrl+C")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска GUI: {e}", exc_info=True)


def main():
    """Главная функция"""
    Path("logs").mkdir(exist_ok=True)
    Path("results").mkdir(exist_ok=True)
    
    if not Path("config.json").exists():
        logger.error("❌ Файл config.json не найден!")
        return
    
    try:
        bot = AutoScalpingBot()
    except Exception as e:
        logger.error(f"❌ Ошибка создания бота: {e}", exc_info=True)
        print(f"❌ Ошибка создания бота: {e}")
        traceback.print_exc()
        return
    
    print()
    print("="*60)
    print("АВТОМАТИЧЕСКИЙ СКАЛЬПИНГ-БОТ - ОБЪЕДИНЕННАЯ ВЕРСИЯ")
    print("="*60)
    print()
    print("Настройки:")
    print(f"  Депозит: ${bot.config['account']['starting_balance']}")
    print(f"  Плечо: {bot.config['account']['leverage']}x")
    print(f"  Пары: {len(bot.config['pairs'])} пар")
    print(f"  Мин. уверенность: {bot.config['signals']['min_confidence']}%")
    print()
    print("Запуск бота...")
    print("Для остановки: Ctrl+C или закройте GUI окно")
    print()
    
    try:
        bot.run()
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}", exc_info=True)
        print(f"❌ Ошибка запуска бота: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ Программа остановлена пользователем (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в main(): {e}", exc_info=True)
        print(f"❌ Критическая ошибка: {e}")
        traceback.print_exc()
        sys.exit(1)

