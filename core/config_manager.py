#!/usr/bin/env python3
"""
⚙️ CONFIG MANAGER
Handles bot configuration: load, save, validate.
Enables AI chat to adjust settings without code changes.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from copy import deepcopy

logger = logging.getLogger(__name__)


class ConfigManager:
    """Configuration manager for dynamic parameter updates."""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Args:
            config_path: path to configuration file.
        """
        self.config_path = Path(config_path)
        self.config: Dict = {}
        self.backup_path = Path("config_backup.json")
        
        # Load config on initialisation
        self.load()
    
    def load(self) -> Dict:
        """Load configuration from file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info(f"✅ Configuration loaded from {self.config_path}")
            return self.config
        except FileNotFoundError:
            logger.error(f"❌ Configuration file not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parsing error: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to load configuration: {e}")
            raise
    
    def save(self) -> bool:
        """Persist configuration to file."""
        try:
            # Create backup before writing
            if self.config_path.exists():
                with open(self.backup_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            # Save new configuration
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Configuration saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to save configuration: {e}")
            return False
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Retrieve nested value by dot-separated path (e.g. 'signals.min_confidence').
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
        Set nested value by dot-separated path.
        """
        keys = path.split('.')
        config = self.config
        
        try:
            # Create nested dictionaries if needed
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]
            
            old_value = config.get(keys[-1])
            
            config[keys[-1]] = value
            
            logger.info(f"⚙️ Updated: {path} = {value} (was: {old_value})")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to set {path}: {e}")
            return False
    
    def update(self, updates: Dict[str, Any]) -> bool:
        """Bulk update via mapping {path: value}."""
        success = True
        for path, value in updates.items():
            if not self.set(path, value):
                success = False
        
        if success:
            logger.info(f"✅ Updated {len(updates)} parameters")
        return success
    
    def get_changeable_params(self) -> Dict[str, Dict]:
        """Return metadata for parameters that can be changed via AI."""
        return {
            # Signal parameters
            "signals.min_confidence": {
                "name": "Minimum confidence (LONG)",
                "type": "float",
                "range": [50, 95],
                "current": self.get("signals.min_confidence"),
                "description": "Minimum signal confidence to open a LONG position (%)"
            },
            "signals.min_confidence_short": {
                "name": "Minimum confidence (SHORT)",
                "type": "float",
                "range": [50, 95],
                "current": self.get("signals.min_confidence_short"),
                "description": "Minimum signal confidence to open a SHORT position (%)"
            },
            "signals.cooldown_seconds": {
                "name": "Cooldown between signals",
                "type": "int",
                "range": [10, 300],
                "current": self.get("signals.cooldown_seconds"),
                "description": "Cooldown between signals for the same symbol (seconds)"
            },
            "signals.tape_window_seconds": {
                "name": "Trade analysis window",
                "type": "int",
                "range": [5, 60],
                "current": self.get("signals.tape_window_seconds"),
                "description": "Time window for evaluating latest trades (seconds)"
            },
            
            # Risk parameters
            "risk.base_risk_percent": {
                "name": "Base risk per trade",
                "type": "float",
                "range": [0.5, 5.0],
                "current": self.get("risk.base_risk_percent"),
                "description": "Balance percentage at risk per trade (%)"
            },
            "risk.stop_loss_percent": {
                "name": "Stop-loss",
                "type": "float",
                "range": [0.1, 2.0],
                "current": self.get("risk.stop_loss_percent"),
                "description": "Stop-loss distance from entry price (%)"
            },
            "risk.take_profit_multiplier": {
                "name": "Take profit multiplier",
                "type": "float",
                "range": [1.0, 5.0],
                "current": self.get("risk.take_profit_multiplier"),
                "description": "Multiplier for take-profit target (e.g. 2.0 = risk:reward 1:2)"
            },
            
            # Account parameters
            "account.max_positions": {
                "name": "Max concurrent positions",
                "type": "int",
                "range": [1, 20],
                "current": self.get("account.max_positions"),
                "description": "Maximum number of simultaneous positions"
            },
            "account.leverage": {
                "name": "Base leverage",
                "type": "int",
                "range": [10, 100],
                "current": self.get("account.leverage"),
                "description": "Default leverage for trading"
            },
            "account.leverage_min": {
                "name": "Minimum leverage",
                "type": "int",
                "range": [10, 100],
                "current": self.get("account.leverage_min"),
                "description": "Minimum leverage when using dynamic leverage"
            },
            "account.leverage_max": {
                "name": "Maximum leverage",
                "type": "int",
                "range": [10, 100],
                "current": self.get("account.leverage_max"),
                "description": "Maximum leverage when using dynamic leverage"
            },
        }
    
    def validate_value(self, path: str, value: Any) -> tuple[bool, Optional[str]]:
        """Validate value before setting it."""
        changeable = self.get_changeable_params()
        
        if path not in changeable:
            return False, f"Parameter '{path}' is not changeable"
        
        param_info = changeable[path]
        
        if param_info['type'] == 'int' and not isinstance(value, int):
            try:
                value = int(value)
            except (ValueError, TypeError):
                return False, f"Parameter '{path}' must be an integer"
        
        elif param_info['type'] == 'float' and not isinstance(value, (int, float)):
            try:
                value = float(value)
            except (ValueError, TypeError):
                return False, f"Parameter '{path}' must be numeric"
        
        if 'range' in param_info:
            min_val, max_val = param_info['range']
            if value < min_val or value > max_val:
                return False, f"Value must be within {min_val}-{max_val}"
        
        return True, None
    
    def suggest_optimization(self, stats: Dict) -> Dict[str, Any]:
        """
        Suggest parameter tweaks based on trading statistics.
        """
        suggestions = {}
        
        win_rate = stats.get('win_rate', 50)
        profit_factor = stats.get('profit_factor', 1.0)
        avg_win = stats.get('avg_win', 0)
        avg_loss = stats.get('avg_loss', 0)
        
        if win_rate < 50:
            current_conf = self.get('signals.min_confidence', 75)
            if current_conf < 85:
                suggestions['signals.min_confidence'] = min(85, current_conf + 5)
                suggestions['signals.min_confidence_short'] = min(83, self.get('signals.min_confidence_short', 73) + 5)
        
        if profit_factor < 1.2:
            current_risk = self.get('risk.base_risk_percent', 1.0)
            if current_risk > 0.5:
                suggestions['risk.base_risk_percent'] = max(0.5, current_risk - 0.2)
        
        if avg_loss > 0 and avg_win > 0 and avg_loss > avg_win * 1.5:
            current_sl = self.get('risk.stop_loss_percent', 0.5)
            if current_sl > 0.3:
                suggestions['risk.stop_loss_percent'] = max(0.3, current_sl - 0.1)
        
        return suggestions
    
    def restore_backup(self) -> bool:
        """Restore configuration from backup."""
        try:
            if not self.backup_path.exists():
                logger.error("❌ Backup file not found")
                return False
            
            with open(self.backup_path, 'r', encoding='utf-8') as f:
                backup_config = json.load(f)
            
            self.config = backup_config
            return self.save()
        except Exception as e:
            logger.error(f"❌ Backup restore failed: {e}")
            return False
    
    def get_config_summary(self) -> str:
        """Return a formatted configuration summary."""
        return f"""
📊 CURRENT CONFIGURATION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 SIGNALS:
  • Minimum confidence (LONG): {self.get('signals.min_confidence', 75)}%
  • Minimum confidence (SHORT): {self.get('signals.min_confidence_short', 73)}%
  • Cooldown: {self.get('signals.cooldown_seconds', 45)} s
  • Trade window: {self.get('signals.tape_window_seconds', 13)} s

💰 RISK MANAGEMENT:
  • Risk per trade: {self.get('risk.base_risk_percent', 1.0)}%
  • Stop-loss: {self.get('risk.stop_loss_percent', 0.5)}%
  • TP multiplier: {self.get('risk.take_profit_multiplier', 2.0)}x

📈 ACCOUNT:
  • Max positions: {self.get('account.max_positions', 10)}
  • Leverage: {self.get('account.leverage', 75)}x
  • Leverage range: {self.get('account.leverage_min', 50)}x - {self.get('account.leverage_max', 100)}x
"""

