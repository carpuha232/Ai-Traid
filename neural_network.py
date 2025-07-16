"""
🧠 Автономная нейросеть для риск-менеджмента и мани-менеджмента
Обучение методом проб и ошибок для достижения винрейта 70%+
"""

import numpy as np
import pandas as pd
import random
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import os

class AutonomousNeuralNetwork:
    """Автономная нейросеть для торговли криптовалютами"""
    
    def __init__(self, initial_capital: float = 100.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.learning_rate = 0.01
        self.experience_memory = []
        self.success_patterns = []
        self.failure_patterns = []
        self.current_cycle = 0
        self.total_trades = 0
        self.profitable_trades = 0
        
        # Параметры для автономного принятия решений
        self.position_size_range = (0.01, 1.0)  # 1-100% от капитала
        self.leverage_range = (1, 20)  # 1x-20x плечо
        self.stop_loss_range = (0.001, 0.5)  # 0.1%-50%
        self.take_profit_range = (0.005, 2.0)  # 0.5%-200%
        
        # Нейронные веса (упрощенная модель)
        self.weights = {
            'price_data': np.random.randn(10),
            'volume_data': np.random.randn(10),
            'time_data': np.random.randn(10),
            'risk_appetite': np.random.randn(10),
            'market_conditions': np.random.randn(10)
        }
        
        # Статистика обучения
        self.learning_stats = {
            'cycles_completed': 0,
            'total_profit': 0.0,
            'max_drawdown': 0.0,
            'win_rate_history': [],
            'capital_history': [initial_capital]
        }

        self.exploration_rate = 1.0  # Начинаем с максимальной случайности
        self.exploration_decay = 0.995  # Медленно уменьшаем случайность
        self.min_exploration = 0.05  # Минимальный уровень случайности
        
        # 🧠 НОВЫЕ МЕХАНИЗМЫ ДЛЯ ПОВЫШЕНИЯ ВИНРЕЙТА
        # 1. Умное обучение на паттернах
        self.pattern_learning = {
            'successful_conditions': [],  # Условия успешных сделок
            'failure_conditions': [],     # Условия неудачных сделок
            'pattern_weights': {},        # Веса для разных паттернов
            'pattern_confidence': 0.0     # Уверенность в паттернах
        }
        
        # 2. Штрафы за частые убытки
        self.loss_penalty = {
            'consecutive_losses': 0,      # Подряд убытков
            'max_consecutive_losses': 5,  # Максимум подряд убытков
            'penalty_multiplier': 1.0,    # Множитель штрафа
            'recovery_threshold': 3       # Убытков для восстановления
        }
        
        # 3. Адаптивная стратегия
        self.adaptive_strategy = {
            'current_performance': 0.0,   # Текущая производительность
            'strategy_confidence': 0.5,   # Уверенность в стратегии
            'adaptation_rate': 0.1,       # Скорость адаптации
            'performance_history': []     # История производительности
        }
    
    def make_autonomous_decision(self, market_data: Dict) -> Dict:
        """Принимает автономное торговое решение на основе сырых данных с умным обучением"""
        
        # 🧠 1. УМНОЕ ОБУЧЕНИЕ НА ПАТТЕРНАХ
        pattern_decision = self._get_pattern_based_decision(market_data)
        
        # 🧠 2. ШТРАФЫ ЗА ЧАСТЫЕ УБЫТКИ - снижаем exploration при плохих результатах
        adjusted_exploration_rate = self._adjust_exploration_for_losses()
        
        # Exploration: с вероятностью adjusted_exploration_rate принимаем случайное решение
        if random.random() < adjusted_exploration_rate:
            decision = {
                'action': random.choice(['buy', 'sell']),
                'position_size': min(random.uniform(*self.position_size_range), 0.2),  # максимум 20%
                'leverage': min(random.randint(*self.leverage_range), 10),  # максимум 10x
                'stop_loss': random.uniform(*self.stop_loss_range),
                'take_profit': random.uniform(*self.take_profit_range),
                'timeframe': random.choice(['3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '1w', '1M']),
                'confidence': random.uniform(0, 1),
                'exploration': True
            }
        else:
            # 🧠 3. АДАПТИВНАЯ СТРАТЕГИЯ - используем паттерны и адаптируемся
            decision = self._get_adaptive_decision(market_data, pattern_decision)
            decision['exploration'] = False
            # Ограничения для адаптивного решения
            decision['position_size'] = min(decision.get('position_size', 0.05), 0.2)
            decision['leverage'] = min(decision.get('leverage', 1), 10)
        
        return decision
    
    def _decide_action(self, market_data: Dict) -> str:
        """Решение о действии: buy, sell на основе сырых данных"""
        # Нейросеть учится принимать решения только на основе цены, объема и времени
        # Никаких готовых индикаторов!
        
        # Простая логика на основе сырых данных
        close_price = market_data.get('close', 0)
        volume = market_data.get('volume', 0)
        hour = market_data.get('hour_of_day', 12)
        
        # Случайное решение (нейросеть будет учиться через ошибки)
        action_score = random.uniform(-1, 1)
        
        if action_score > 0:
            return 'buy'
        else:
            return 'sell'
    
    def _decide_position_size(self) -> float:
        """Автономное решение о размере позиции"""
        # Нейросеть учится выбирать оптимальный размер
        base_size = random.uniform(*self.position_size_range)
        
        # Корректировка на основе опыта
        if self.learning_stats['win_rate_history']:
            recent_win_rate = np.mean(self.learning_stats['win_rate_history'][-10:])
            if recent_win_rate > 0.6:
                base_size *= 1.2  # Увеличиваем размер при хороших результатах
            elif recent_win_rate < 0.4:
                base_size *= 0.8  # Уменьшаем при плохих результатах
        
        return min(base_size, 1.0)  # Максимум 100% капитала
    
    def _decide_leverage(self) -> int:
        """Автономное решение о плече"""
        # Нейросеть экспериментирует с разными плечами
        leverage = random.randint(*self.leverage_range)
        
        # Корректировка на основе риска
        if self.current_capital < self.initial_capital * 0.8:  # Просадка
            leverage = max(leverage // 2, 1)  # Уменьшаем плечо
        
        return leverage
    
    def _decide_stop_loss(self) -> float:
        """Автономное решение о стоп-лоссе"""
        return random.uniform(*self.stop_loss_range)
    
    def _decide_take_profit(self) -> float:
        """Автономное решение о тейк-профите"""
        return random.uniform(*self.take_profit_range)
    
    def _decide_timeframe(self) -> str:
        """Автономное решение о таймфрейме"""
        timeframes = ['3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '1w', '1M']
        return random.choice(timeframes)
    
    def _calculate_confidence(self, market_data: Dict) -> float:
        """Расчет уверенности в решении"""
        # Простая уверенность на основе сырых данных
        confidence = random.uniform(0, 1)
        return confidence
    
    def learn_from_result(self, decision: Dict, result: Dict):
        """Обучение на результате сделки с новыми механизмами"""
        
        # Сохраняем опыт
        experience = {
            'decision': decision,
            'result': result,
            'timestamp': datetime.now().isoformat(),
            'cycle': self.current_cycle
        }
        self.experience_memory.append(experience)
        
        # Обновляем статистику с защитой от nan
        profit = float(result.get('profit', 0))
        if np.isnan(profit):
            profit = 0.0
        
        self.total_trades += 1
        if profit > 0:
            self.profitable_trades += 1
            self.success_patterns.append(decision)
            
            # 🧠 1. УМНОЕ ОБУЧЕНИЕ НА ПАТТЕРНАХ - сохраняем успешные условия
            market_conditions = self._extract_market_conditions(result.get('market_data', {}))
            successful_pattern = {
                'conditions': market_conditions,
                'decision': decision,
                'profit': profit,
                'timestamp': datetime.now().isoformat()
            }
            self.pattern_learning['successful_conditions'].append(successful_pattern)
            
            # Сбрасываем счетчик убытков при прибыли
            self.loss_penalty['consecutive_losses'] = 0
            
        else:
            self.failure_patterns.append(decision)
            
            # 🧠 2. ШТРАФЫ ЗА ЧАСТЫЕ УБЫТКИ - отслеживаем подряд убытки
            self.loss_penalty['consecutive_losses'] += 1
            
            # Сохраняем неудачные условия для анализа
            market_conditions = self._extract_market_conditions(result.get('market_data', {}))
            failure_pattern = {
                'conditions': market_conditions,
                'decision': decision,
                'loss': abs(profit),
                'timestamp': datetime.now().isoformat()
            }
            self.pattern_learning['failure_conditions'].append(failure_pattern)
        
        # Обновляем капитал с защитой от nan
        self.current_capital += profit
        if np.isnan(self.current_capital):
            self.current_capital = self.initial_capital
        
        self.learning_stats['total_profit'] += profit
        if np.isnan(self.learning_stats['total_profit']):
            self.learning_stats['total_profit'] = 0.0
        
        self.learning_stats['capital_history'].append(self.current_capital)
        
        # Обновляем винрейт
        current_win_rate = self.profitable_trades / self.total_trades
        self.learning_stats['win_rate_history'].append(current_win_rate)
        
        # 🧠 3. АДАПТИВНАЯ СТРАТЕГИЯ - обновляем производительность
        self._update_adaptive_strategy(profit, current_win_rate)
        
        # Обновляем максимальную просадку
        max_capital = max(self.learning_stats['capital_history'])
        current_drawdown = (max_capital - self.current_capital) / max_capital
        self.learning_stats['max_drawdown'] = max(self.learning_stats['max_drawdown'], current_drawdown)
        
        # Ограничиваем размер памяти - УЛУЧШЕННАЯ ВЕРСИЯ
        if len(self.experience_memory) > 50000:  # Увеличили с 10000 до 50000
            self.experience_memory = self.experience_memory[-25000:]  # Сохраняем больше
        
        if len(self.success_patterns) > 2000:  # Увеличили с 1000 до 2000
            self.success_patterns = self.success_patterns[-1000:]  # Сохраняем больше
        
        if len(self.failure_patterns) > 2000:  # Увеличили с 1000 до 2000
            self.failure_patterns = self.failure_patterns[-1000:]  # Сохраняем больше
        
        # Ограничиваем паттерны - УЛУЧШЕННАЯ ВЕРСИЯ
        if len(self.pattern_learning['successful_conditions']) > 1000:  # Увеличили с 500 до 1000
            self.pattern_learning['successful_conditions'] = self.pattern_learning['successful_conditions'][-500:]  # Сохраняем больше
        
        if len(self.pattern_learning['failure_conditions']) > 1000:  # Увеличили с 500 до 1000
            self.pattern_learning['failure_conditions'] = self.pattern_learning['failure_conditions'][-500:]  # Сохраняем больше
        
        # Уменьшаем exploration rate
        self.exploration_rate = max(self.min_exploration, self.exploration_rate * self.exploration_decay)
    
    def _update_adaptive_strategy(self, profit: float, win_rate: float):
        """Обновляет адаптивную стратегию на основе результатов"""
        # Обновляем текущую производительность
        performance_score = 0.0
        
        # 50% веса для винрейта
        performance_score += win_rate * 0.5
        
        # 30% веса для прибыльности (нормализованной)
        if self.total_trades > 0:
            avg_profit = self.learning_stats['total_profit'] / self.total_trades
            normalized_profit = min(1.0, max(-1.0, avg_profit / 10.0))  # Нормализуем к ±10$
            performance_score += (normalized_profit + 1.0) * 0.15  # Сдвигаем к 0-1
        
        # 20% веса для стабильности капитала
        if len(self.learning_stats['capital_history']) > 10:
            recent_capital = self.learning_stats['capital_history'][-10:]
            capital_stability = 1.0 - (max(recent_capital) - min(recent_capital)) / max(recent_capital)
            performance_score += capital_stability * 0.2
        
        self.adaptive_strategy['current_performance'] = performance_score
        self.adaptive_strategy['performance_history'].append(performance_score)
        
        # Обновляем уверенность в стратегии
        if len(self.adaptive_strategy['performance_history']) > 10:
            recent_performance = self.adaptive_strategy['performance_history'][-10:]
            avg_performance = np.mean(recent_performance)
            
            if avg_performance > 0.6:
                self.adaptive_strategy['strategy_confidence'] = min(1.0, self.adaptive_strategy['strategy_confidence'] + 0.1)
            elif avg_performance < 0.4:
                self.adaptive_strategy['strategy_confidence'] = max(0.1, self.adaptive_strategy['strategy_confidence'] - 0.1)
        
        # Ограничиваем историю производительности
        if len(self.adaptive_strategy['performance_history']) > 100:
            self.adaptive_strategy['performance_history'] = self.adaptive_strategy['performance_history'][-50:]
    
    def get_learning_stats(self) -> Dict:
        """Получение статистики обучения с новыми механизмами"""
        current_capital = float(self.current_capital or 100.0)
        if np.isnan(current_capital):
            current_capital = 100.0
        
        current_win_rate = self.profitable_trades / self.total_trades if self.total_trades > 0 else 0.0
        if np.isnan(current_win_rate):
            current_win_rate = 0.0
        
        return {
            'current_capital': current_capital,
            'total_profit': self.learning_stats['total_profit'],
            'total_trades': self.total_trades,
            'profitable_trades': self.profitable_trades,
            'win_rate': current_win_rate,
            'max_drawdown': self.learning_stats['max_drawdown'],
            'cycles_completed': self.learning_stats['cycles_completed'],
            'experience_memory_size': len(self.experience_memory),
            'success_patterns_count': len(self.success_patterns),
            'failure_patterns_count': len(self.failure_patterns),
            
            # 🧠 Новые механизмы
            'exploration_rate': self.exploration_rate,
            'pattern_confidence': self.pattern_learning['pattern_confidence'],
            'consecutive_losses': self.loss_penalty['consecutive_losses'],
            'strategy_confidence': self.adaptive_strategy['strategy_confidence'],
            'current_performance': self.adaptive_strategy['current_performance'],
            'successful_patterns_stored': len(self.pattern_learning['successful_conditions']),
            'failure_patterns_stored': len(self.pattern_learning['failure_conditions'])
        }
    
    def save_state(self, filename: str = 'neural_network_state.json'):
        """Сохранение состояния нейросети с новыми механизмами - УЛУЧШЕННАЯ ВЕРСИЯ"""
        state = {
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'learning_rate': self.learning_rate,
            'experience_memory': self.experience_memory[-5000:],  # Последние 5000 опытов (увеличили)
            'success_patterns': self.success_patterns[-1000:],    # Последние 1000 успешных (увеличили)
            'failure_patterns': self.failure_patterns[-1000:],    # Последние 1000 неудачных (увеличили)
            'current_cycle': self.current_cycle,
            'total_trades': self.total_trades,
            'profitable_trades': self.profitable_trades,
            'weights': self.weights,
            'learning_stats': self.learning_stats,
            'exploration_rate': self.exploration_rate,
            
            # 🧠 Новые механизмы
            'pattern_learning': self.pattern_learning,
            'loss_penalty': self.loss_penalty,
            'adaptive_strategy': self.adaptive_strategy
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False, default=str)
    
    def get_state(self) -> Dict:
        """Получение состояния нейросети"""
        return {
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'learning_rate': self.learning_rate,
            'experience_memory_size': len(self.experience_memory),
            'success_patterns_count': len(self.success_patterns),
            'failure_patterns_count': len(self.failure_patterns),
            'current_cycle': self.current_cycle,
            'total_trades': self.total_trades,
            'profitable_trades': self.profitable_trades,
            'learning_stats': self.learning_stats,
            'exploration_rate': self.exploration_rate,
            
            # 🧠 Новые механизмы
            'pattern_learning': self.pattern_learning,
            'loss_penalty': self.loss_penalty,
            'adaptive_strategy': self.adaptive_strategy
        }
    
    def load_state(self, state: Dict):
        """Загрузка состояния нейросети с новыми механизмами"""
        if 'initial_capital' in state:
            self.initial_capital = state['initial_capital']
        if 'current_capital' in state:
            self.current_capital = state['current_capital']
        if 'learning_rate' in state:
            self.learning_rate = state['learning_rate']
        if 'experience_memory' in state:
            self.experience_memory = state['experience_memory']
        if 'success_patterns' in state:
            self.success_patterns = state['success_patterns']
        if 'failure_patterns' in state:
            self.failure_patterns = state['failure_patterns']
        if 'current_cycle' in state:
            self.current_cycle = state['current_cycle']
        if 'total_trades' in state:
            self.total_trades = state['total_trades']
        if 'profitable_trades' in state:
            self.profitable_trades = state['profitable_trades']
        if 'weights' in state:
            self.weights = state['weights']
        if 'learning_stats' in state:
            self.learning_stats = state['learning_stats']
        if 'exploration_rate' in state:
            self.exploration_rate = state['exploration_rate']
        
        # 🧠 Новые механизмы
        if 'pattern_learning' in state:
            self.pattern_learning = state['pattern_learning']
        if 'loss_penalty' in state:
            self.loss_penalty = state['loss_penalty']
        if 'adaptive_strategy' in state:
            self.adaptive_strategy = state['adaptive_strategy']
    
    def _get_pattern_based_decision(self, market_data: Dict) -> Optional[Dict]:
        """Получает решение на основе изученных паттернов"""
        if not self.pattern_learning['successful_conditions']:
            return None
        
        # Анализируем текущие условия рынка
        current_conditions = self._extract_market_conditions(market_data)
        
        # Ищем похожие успешные паттерны
        best_pattern = None
        best_similarity = 0.0
        
        for pattern in self.pattern_learning['successful_conditions'][-50:]:  # Последние 50 успешных
            similarity = self._calculate_pattern_similarity(current_conditions, pattern)
            if similarity > best_similarity and similarity > 0.7:  # Минимум 70% схожести
                best_similarity = similarity
                best_pattern = pattern
        
        if best_pattern:
            self.pattern_learning['pattern_confidence'] = best_similarity
            return best_pattern['decision']
        
        return None
    
    def _extract_market_conditions(self, market_data: Dict) -> Dict:
        """Извлекает условия рынка для анализа паттернов"""
        return {
            'price_level': market_data.get('close', 0),
            'volume_level': market_data.get('volume', 0),
            'hour_of_day': market_data.get('hour_of_day', 12),
            'day_of_week': market_data.get('day_of_week', 1),
            'price_change': market_data.get('price_change', 0),
            'volume_change': market_data.get('volume_change', 0)
        }
    
    def _calculate_pattern_similarity(self, current: Dict, pattern: Dict) -> float:
        """Вычисляет схожесть текущих условий с паттерном"""
        if not pattern.get('conditions'):
            return 0.0
        
        similarities = []
        pattern_conditions = pattern['conditions']
        
        for key in current:
            if key in pattern_conditions:
                # Нормализуем значения для сравнения
                current_val = float(current[key])
                pattern_val = float(pattern_conditions[key])
                
                # Простое сравнение (можно улучшить)
                if pattern_val != 0:
                    similarity = 1.0 - abs(current_val - pattern_val) / abs(pattern_val)
                    similarities.append(max(0.0, similarity))
        
        return float(np.mean(similarities)) if similarities else 0.0
    
    def _adjust_exploration_for_losses(self) -> float:
        """Корректирует exploration rate на основе штрафов за убытки"""
        base_exploration = self.exploration_rate
        
        # Увеличиваем exploration при частых убытках
        if self.loss_penalty['consecutive_losses'] >= self.loss_penalty['max_consecutive_losses']:
            penalty_multiplier = 1.5  # Больше случайности при плохих результатах
        elif self.loss_penalty['consecutive_losses'] >= self.loss_penalty['recovery_threshold']:
            penalty_multiplier = 1.2  # Умеренно больше случайности
        else:
            penalty_multiplier = 1.0  # Нормальный уровень
        
        adjusted_exploration = min(1.0, base_exploration * penalty_multiplier)
        return adjusted_exploration
    
    def _get_adaptive_decision(self, market_data: Dict, pattern_decision: Optional[Dict]) -> Dict:
        """Получает адаптивное решение на основе текущей производительности"""
        
        # Если есть успешный паттерн, используем его с адаптацией
        if pattern_decision and self.pattern_learning['pattern_confidence'] > 0.7:
            decision = pattern_decision.copy()
            
            # Адаптируем размер позиции на основе уверенности
            confidence_factor = self.pattern_learning['pattern_confidence']
            decision['position_size'] *= confidence_factor
            
            # Адаптируем плечо на основе производительности
            if self.adaptive_strategy['current_performance'] > 0.6:
                decision['leverage'] = min(decision['leverage'] + 1, 20)
            elif self.adaptive_strategy['current_performance'] < 0.4:
                decision['leverage'] = max(decision['leverage'] - 1, 1)
            
            decision['confidence'] = confidence_factor
            return decision
        
        # Иначе используем стандартную логику с адаптацией
        decision = {
            'action': self._decide_action(market_data),
            'position_size': self._decide_position_size(),
            'leverage': self._decide_leverage(),
            'stop_loss': self._decide_stop_loss(),
            'take_profit': self._decide_take_profit(),
            'timeframe': self._decide_timeframe(),
            'confidence': self._calculate_confidence(market_data)
        }
        
        # Адаптируем на основе производительности
        self._adapt_decision_parameters(decision)
        
        return decision
    
    def _adapt_decision_parameters(self, decision: Dict):
        """Адаптирует параметры решения на основе производительности"""
        performance = self.adaptive_strategy['current_performance']
        
        if performance > 0.6:  # Хорошая производительность
            # Увеличиваем размер позиции и плечо
            decision['position_size'] *= 1.1
            decision['leverage'] = min(decision['leverage'] + 1, 20)
        elif performance < 0.4:  # Плохая производительность
            # Уменьшаем размер позиции и плечо
            decision['position_size'] *= 0.9
            decision['leverage'] = max(decision['leverage'] - 1, 1) 