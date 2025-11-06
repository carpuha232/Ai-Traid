#!/usr/bin/env python3
"""
⚙️ CONFIG MANAGER
Управление конфигурацией бота - чтение, запись, валидация
Позволяет AI чату динамически изменять настройки без переписывания кода
"""

import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from copy import deepcopy

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Менеджер конфигурации для динамического изменения параметров
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        Args:
            config_path: Путь к файлу конфигурации
        """
        self.config_path = Path(config_path)
        self.config: Dict = {}
        self.backup_path = Path("config_backup.json")
        
        # Загружаем конфиг при инициализации
        self.load()
    
    def load(self) -> Dict:
        """Загрузить конфигурацию из файла"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info(f"✅ Конфигурация загружена из {self.config_path}")
            return self.config
        except FileNotFoundError:
            logger.error(f"❌ Файл конфигурации не найден: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки конфигурации: {e}")
            raise
    
    def save(self) -> bool:
        """Сохранить конфигурацию в файл"""
        try:
            # Создаем backup перед сохранением
            if self.config_path.exists():
                with open(self.backup_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            # Сохраняем новую конфигурацию
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Конфигурация сохранена в {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения конфигурации: {e}")
            return False
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Получить значение по пути (например: 'signals.min_confidence')
        
        Args:
            path: Путь к значению через точку (например: 'signals.min_confidence')
            default: Значение по умолчанию
            
        Returns:
            Значение или default
        """
        keys = path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, path: str, value: Any) -> bool:
        """
        Установить значение по пути (например: 'signals.min_confidence' = 80)
        
        Args:
            path: Путь к значению через точку
            value: Новое значение
            
        Returns:
            True если успешно, False при ошибке
        """
        keys = path.split('.')
        config = self.config
        
        try:
            # Создаем вложенные словари если нужно
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]
            
            # Сохраняем старое значение для логирования
            old_value = config.get(keys[-1])
            
            # Устанавливаем новое значение
            config[keys[-1]] = value
            
            logger.info(f"⚙️ Изменено: {path} = {value} (было: {old_value})")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка установки {path}: {e}")
            return False
    
    def update(self, updates: Dict[str, Any]) -> bool:
        """
        Обновить несколько параметров сразу
        
        Args:
            updates: Словарь {path: value} например {'signals.min_confidence': 80, 'risk.base_risk_percent': 1.5}
            
        Returns:
            True если все успешно, False при ошибке
        """
        success = True
        for path, value in updates.items():
            if not self.set(path, value):
                success = False
        
        if success:
            logger.info(f"✅ Обновлено {len(updates)} параметров")
        return success
    
    def get_changeable_params(self) -> Dict[str, Dict]:
        """
        Получить список параметров которые можно изменять через AI
        
        Returns:
            Словарь с описанием доступных параметров
        """
        return {
            # Параметры сигналов
            "signals.min_confidence": {
                "name": "Минимальная уверенность (LONG)",
                "type": "float",
                "range": [50, 95],
                "current": self.get("signals.min_confidence"),
                "description": "Минимальная уверенность сигнала для входа в LONG позицию (%)"
            },
            "signals.min_confidence_short": {
                "name": "Минимальная уверенность (SHORT)",
                "type": "float",
                "range": [50, 95],
                "current": self.get("signals.min_confidence_short"),
                "description": "Минимальная уверенность сигнала для входа в SHORT позицию (%)"
            },
            "signals.cooldown_seconds": {
                "name": "Cooldown между сигналами",
                "type": "int",
                "range": [10, 300],
                "current": self.get("signals.cooldown_seconds"),
                "description": "Время между сигналами по одной паре (секунды)"
            },
            "signals.tape_window_seconds": {
                "name": "Окно анализа сделок",
                "type": "int",
                "range": [5, 60],
                "current": self.get("signals.tape_window_seconds"),
                "description": "Окно времени для анализа последних сделок (секунды)"
            },
            
            # Параметры риска
            "risk.base_risk_percent": {
                "name": "Базовый риск на сделку",
                "type": "float",
                "range": [0.5, 5.0],
                "current": self.get("risk.base_risk_percent"),
                "description": "Процент баланса который рискуем на каждую сделку (%)"
            },
            "risk.stop_loss_percent": {
                "name": "Стоп-лосс",
                "type": "float",
                "range": [0.1, 2.0],
                "current": self.get("risk.stop_loss_percent"),
                "description": "Расстояние стоп-лосса от входа (%)"
            },
            "risk.take_profit_multiplier": {
                "name": "Множитель тейк-профита",
                "type": "float",
                "range": [1.0, 5.0],
                "current": self.get("risk.take_profit_multiplier"),
                "description": "Множитель для расчета тейк-профита (например 2.0 = риск:прибыль 1:2)"
            },
            
            # Параметры аккаунта
            "account.max_positions": {
                "name": "Максимум позиций",
                "type": "int",
                "range": [1, 20],
                "current": self.get("account.max_positions"),
                "description": "Максимальное количество открытых позиций одновременно"
            },
            "account.leverage": {
                "name": "Базовое плечо",
                "type": "int",
                "range": [10, 100],
                "current": self.get("account.leverage"),
                "description": "Базовое плечо для торговли"
            },
            "account.leverage_min": {
                "name": "Минимальное плечо",
                "type": "int",
                "range": [10, 100],
                "current": self.get("account.leverage_min"),
                "description": "Минимальное плечо при динамическом плече"
            },
            "account.leverage_max": {
                "name": "Максимальное плечо",
                "type": "int",
                "range": [10, 100],
                "current": self.get("account.leverage_max"),
                "description": "Максимальное плечо при динамическом плече"
            },
        }
    
    def validate_value(self, path: str, value: Any) -> tuple[bool, Optional[str]]:
        """
        Валидация значения перед установкой
        
        Args:
            path: Путь к параметру
            value: Значение для проверки
            
        Returns:
            (is_valid, error_message)
        """
        changeable = self.get_changeable_params()
        
        if path not in changeable:
            return False, f"Параметр '{path}' нельзя изменять"
        
        param_info = changeable[path]
        
        # Проверка типа
        if param_info['type'] == 'int' and not isinstance(value, int):
            try:
                value = int(value)
            except (ValueError, TypeError):
                return False, f"Параметр '{path}' должен быть целым числом"
        
        elif param_info['type'] == 'float' and not isinstance(value, (int, float)):
            try:
                value = float(value)
            except (ValueError, TypeError):
                return False, f"Параметр '{path}' должен быть числом"
        
        # Проверка диапазона
        if 'range' in param_info:
            min_val, max_val = param_info['range']
            if value < min_val or value > max_val:
                return False, f"Значение должно быть в диапазоне {min_val}-{max_val}"
        
        return True, None
    
    def suggest_optimization(self, stats: Dict) -> Dict[str, Any]:
        """
        Предложить оптимизацию параметров на основе статистики
        
        Args:
            stats: Статистика торговли
            
        Returns:
            Словарь с предложенными изменениями
        """
        suggestions = {}
        
        win_rate = stats.get('win_rate', 50)
        profit_factor = stats.get('profit_factor', 1.0)
        avg_win = stats.get('avg_win', 0)
        avg_loss = stats.get('avg_loss', 0)
        
        # Если низкий win rate - повышаем минимальную уверенность
        if win_rate < 50:
            current_conf = self.get('signals.min_confidence', 75)
            if current_conf < 85:
                suggestions['signals.min_confidence'] = min(85, current_conf + 5)
                suggestions['signals.min_confidence_short'] = min(83, self.get('signals.min_confidence_short', 73) + 5)
        
        # Если profit factor низкий - снижаем риск
        if profit_factor < 1.2:
            current_risk = self.get('risk.base_risk_percent', 1.0)
            if current_risk > 0.5:
                suggestions['risk.base_risk_percent'] = max(0.5, current_risk - 0.2)
        
        # Если средний убыток больше прибыли - ужесточаем стоп
        if avg_loss > 0 and avg_win > 0 and avg_loss > avg_win * 1.5:
            current_sl = self.get('risk.stop_loss_percent', 0.5)
            if current_sl > 0.3:
                suggestions['risk.stop_loss_percent'] = max(0.3, current_sl - 0.1)
        
        return suggestions
    
    def restore_backup(self) -> bool:
        """Восстановить конфигурацию из backup"""
        try:
            if not self.backup_path.exists():
                logger.error("❌ Backup файл не найден")
                return False
            
            with open(self.backup_path, 'r', encoding='utf-8') as f:
                backup_config = json.load(f)
            
            self.config = backup_config
            return self.save()
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления backup: {e}")
            return False
    
    def get_config_summary(self) -> str:
        """Получить краткую сводку конфигурации"""
        return f"""
📊 ТЕКУЩАЯ КОНФИГУРАЦИЯ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 СИГНАЛЫ:
  • Минимальная уверенность (LONG): {self.get('signals.min_confidence', 75)}%
  • Минимальная уверенность (SHORT): {self.get('signals.min_confidence_short', 73)}%
  • Cooldown: {self.get('signals.cooldown_seconds', 45)} сек
  • Окно анализа: {self.get('signals.tape_window_seconds', 13)} сек

💰 РИСК-МЕНЕДЖМЕНТ:
  • Риск на сделку: {self.get('risk.base_risk_percent', 1.0)}%
  • Стоп-лосс: {self.get('risk.stop_loss_percent', 0.5)}%
  • Множитель TP: {self.get('risk.take_profit_multiplier', 2.0)}x

📈 АККАУНТ:
  • Макс. позиций: {self.get('account.max_positions', 10)}
  • Плечо: {self.get('account.leverage', 75)}x
  • Диапазон плеча: {self.get('account.leverage_min', 50)}x - {self.get('account.leverage_max', 100)}x
"""

