"""
🧠 Анализатор базы знаний эволюционного агента
Анализирует миллионы параметров и находит паттерны успеха/ошибок
"""

import json
import os
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime
import numpy as np
from collections import defaultdict, Counter

class KnowledgeAnalyzer:
    """
    Анализатор базы знаний для поиска паттернов в миллионах параметров
    """
    
    def __init__(self, data_dir: str = "learning_data"):
        self.data_dir = data_dir
        self.knowledge_base = {}
        self.individuals_data = []
        self.trades_df = None
        self.errors_df = None
        
    def load_knowledge_base(self, filename: Optional[str] = None):
        """Загружает базу знаний из файла"""
        if filename is None:
            # Ищем самый свежий файл базы знаний
            files = [f for f in os.listdir(self.data_dir) if f.startswith("knowledge_base_")]
            if not files:
                raise FileNotFoundError("Файлы базы знаний не найдены")
            filename = max(files)  # Самый свежий файл
        
        filepath = os.path.join(self.data_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            self.knowledge_base = json.load(f)
        
        print(f"✅ База знаний загружена: {filename}")
        return self.knowledge_base
    
    def load_individuals_data(self, timestamp: Optional[str] = None):
        """Загружает данные всех индивидов"""
        files = [f for f in os.listdir(self.data_dir) if f.startswith("individual_")]
        
        if timestamp:
            files = [f for f in files if timestamp in f]
        
        self.individuals_data = []
        for filename in files:
            filepath = os.path.join(self.data_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    individual_data = json.load(f)
                    self.individuals_data.append(individual_data)
            except Exception as e:
                print(f"⚠️ Ошибка загрузки {filename}: {e}")
        
        print(f"✅ Загружено {len(self.individuals_data)} индивидов")
        return self.individuals_data
    
    def create_trades_dataframe(self):
        """Создает DataFrame со всеми сделками"""
        all_trades = []
        
        for individual in self.individuals_data:
            individual_id = individual['individual_id']
            for trade in individual['trade_history']:
                trade['individual_id'] = individual_id
                all_trades.append(trade)
        
        if all_trades:
            self.trades_df = pd.DataFrame(all_trades)
            # Конвертируем timestamp в datetime
            self.trades_df['timestamp'] = pd.to_datetime(self.trades_df['timestamp'])
            print(f"✅ Создан DataFrame с {len(self.trades_df)} сделками")
        else:
            self.trades_df = pd.DataFrame()
            print("⚠️ Нет данных о сделках")
        
        return self.trades_df
    
    def create_errors_dataframe(self):
        """Создает DataFrame со всеми ошибками"""
        all_errors = []
        
        for individual in self.individuals_data:
            individual_id = individual['individual_id']
            for error in individual['error_history']:
                error['individual_id'] = individual_id
                all_errors.append(error)
        
        if all_errors:
            self.errors_df = pd.DataFrame(all_errors)
            self.errors_df['timestamp'] = pd.to_datetime(self.errors_df['timestamp'])
            print(f"✅ Создан DataFrame с {len(self.errors_df)} ошибками")
        else:
            self.errors_df = pd.DataFrame()
            print("⚠️ Нет данных об ошибках")
        
        return self.errors_df
    
    def analyze_successful_patterns(self) -> Dict[str, Any]:
        """Анализирует успешные паттерны"""
        if self.trades_df is None or self.trades_df.empty:
            return {}
        
        # Анализ по символам
        symbol_analysis = self.trades_df.groupby('symbol').agg({
            'win': ['count', 'mean'],
            'pnl': ['mean', 'std'],
            'pnl_pct': ['mean', 'std']
        }).round(4)
        
        # Анализ по таймфреймам
        timeframe_analysis = self.trades_df.groupby('timeframe').agg({
            'win': ['count', 'mean'],
            'pnl': ['mean', 'std']
        }).round(4)
        
        # Анализ по направлениям
        direction_analysis = self.trades_df.groupby('direction').agg({
            'win': ['count', 'mean'],
            'pnl': ['mean', 'std']
        }).round(4)
        
        # Анализ по плечу
        leverage_analysis = self.trades_df.groupby('leverage').agg({
            'win': ['count', 'mean'],
            'pnl': ['mean', 'std']
        }).round(4)
        
        # Топ-10 самых прибыльных сделок
        top_trades = self.trades_df.nlargest(10, 'pnl')[['symbol', 'direction', 'pnl', 'pnl_pct', 'leverage', 'timestamp']]
        
        # Топ-10 самых убыточных сделок
        worst_trades = self.trades_df.nsmallest(10, 'pnl')[['symbol', 'direction', 'pnl', 'pnl_pct', 'leverage', 'timestamp']]
        
        return {
            'symbol_analysis': symbol_analysis,
            'timeframe_analysis': timeframe_analysis,
            'direction_analysis': direction_analysis,
            'leverage_analysis': leverage_analysis,
            'top_trades': top_trades,
            'worst_trades': worst_trades,
            'total_trades': len(self.trades_df),
            'winrate': (self.trades_df['win'].sum() / len(self.trades_df) * 100).round(2),
            'avg_pnl': self.trades_df['pnl'].mean().round(4),
            'total_pnl': self.trades_df['pnl'].sum().round(4)
        }
    
    def analyze_error_patterns(self) -> Dict[str, Any]:
        """Анализирует паттерны ошибок"""
        if self.errors_df is None or self.errors_df.empty:
            return {}
        
        # Анализ по типам ошибок
        error_types = self.errors_df['error_type'].value_counts()
        
        # Анализ по символам с ошибками
        symbol_errors = self.errors_df['symbol'].value_counts()
        
        # Анализ по таймфреймам с ошибками
        timeframe_errors = self.errors_df['timeframe'].value_counts()
        
        # Частые сообщения об ошибках
        error_messages = self.errors_df['error_message'].value_counts().head(10)
        
        return {
            'error_types': error_types,
            'symbol_errors': symbol_errors,
            'timeframe_errors': timeframe_errors,
            'error_messages': error_messages,
            'total_errors': len(self.errors_df)
        }
    
    def analyze_parameter_evolution(self) -> Dict[str, Any]:
        """Анализирует эволюцию параметров"""
        if not self.individuals_data:
            return {}
        
        # Собираем все параметры
        all_params = []
        for individual in self.individuals_data:
            for trade in individual['trade_history']:
                params = trade.get('params', {})
                params['individual_id'] = individual['individual_id']
                params['win'] = trade['win']
                params['pnl'] = trade['pnl']
                params['timestamp'] = trade['timestamp']
                all_params.append(params)
        
        if not all_params:
            return {}
        
        params_df = pd.DataFrame(all_params)
        params_df['timestamp'] = pd.to_datetime(params_df['timestamp'])
        
        # Анализ по параметрам
        leverage_winrate = params_df.groupby('leverage')['win'].agg(['count', 'mean']).round(4)
        position_size_winrate = params_df.groupby('position_size')['win'].agg(['count', 'mean']).round(4)
        budget_frac_winrate = params_df.groupby('budget_frac')['win'].agg(['count', 'mean']).round(4)
        
        # Лучшие комбинации параметров
        best_combinations = params_df.groupby(['leverage', 'position_size', 'budget_frac']).agg({
            'win': ['count', 'mean'],
            'pnl': ['mean', 'sum']
        }).round(4)
        
        # Сортируем по winrate
        best_combinations = best_combinations.sort_values(('win', 'mean'), ascending=False)
        
        return {
            'leverage_winrate': leverage_winrate,
            'position_size_winrate': position_size_winrate,
            'budget_frac_winrate': budget_frac_winrate,
            'best_combinations': best_combinations.head(20)
        }
    
    def find_optimal_parameters(self) -> Dict[str, Any]:
        """Находит оптимальные параметры на основе анализа"""
        if self.trades_df is None or self.trades_df.empty:
            return {}
        
        # Группируем по параметрам и находим лучшие
        params_df = pd.DataFrame([
            {
                'leverage': trade.get('params', {}).get('leverage'),
                'position_size': trade.get('params', {}).get('position_size'),
                'budget_frac': trade.get('params', {}).get('budget_frac'),
                'win': trade['win'],
                'pnl': trade['pnl']
            }
            for trade in self.trades_df.to_dict('records')
            if trade.get('params')
        ])
        
        if params_df.empty:
            return {}
        
        # Находим лучшие комбинации (минимум 10 сделок)
        combinations = params_df.groupby(['leverage', 'position_size', 'budget_frac']).agg({
            'win': ['count', 'mean'],
            'pnl': ['mean', 'sum']
        }).round(4)
        
        # Фильтруем по количеству сделок
        combinations = combinations[combinations[('win', 'count')] >= 10]
        
        # Сортируем по winrate и прибыли
        combinations = combinations.sort_values([
            ('win', 'mean'), 
            ('pnl', 'sum')
        ], ascending=[False, False])
        
        best_params = combinations.head(5)
        
        return {
            'best_parameters': best_params,
            'recommendations': self._generate_recommendations(best_params)
        }
    
    def _generate_recommendations(self, best_params) -> List[str]:
        """Генерирует рекомендации на основе лучших параметров"""
        recommendations = []
        
        if best_params.empty:
            return ["Недостаточно данных для рекомендаций"]
        
        # Анализируем лучшие параметры
        best_leverage = best_params.index.get_level_values('leverage').mode()[0]
        best_position_size = best_params.index.get_level_values('position_size').mean()
        best_budget_frac = best_params.index.get_level_values('budget_frac').mean()
        
        recommendations.append(f"Рекомендуемое плечо: {best_leverage}x")
        recommendations.append(f"Рекомендуемый размер позиции: {best_position_size*100:.1f}%")
        recommendations.append(f"Рекомендуемая доля бюджета: {best_budget_frac*100:.1f}%")
        
        # Анализ по символам
        if self.trades_df is not None and not self.trades_df.empty:
            best_symbols = self.trades_df.groupby('symbol')['win'].mean().nlargest(3)
            recommendations.append(f"Лучшие символы: {', '.join(best_symbols.index)}")
        
        # Анализ по таймфреймам
        if self.trades_df is not None and not self.trades_df.empty:
            best_timeframes = self.trades_df.groupby('timeframe')['win'].mean().nlargest(3)
            recommendations.append(f"Лучшие таймфреймы: {', '.join(best_timeframes.index)}")
        
        return recommendations
    
    def generate_full_report(self) -> str:
        """Генерирует полный отчет анализа"""
        report = []
        report.append("=" * 80)
        report.append("🧠 ПОЛНЫЙ ОТЧЕТ АНАЛИЗА БАЗЫ ЗНАНИЙ")
        report.append("=" * 80)
        report.append(f"📅 Дата анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Статистика данных
        report.append("📊 СТАТИСТИКА ДАННЫХ:")
        report.append(f"   • Индивидов: {len(self.individuals_data)}")
        if self.trades_df is not None:
            report.append(f"   • Сделок: {len(self.trades_df)}")
        if self.errors_df is not None:
            report.append(f"   • Ошибок: {len(self.errors_df)}")
        report.append("")
        
        # Анализ успешных паттернов
        success_patterns = self.analyze_successful_patterns()
        if success_patterns:
            report.append("✅ АНАЛИЗ УСПЕШНЫХ ПАТТЕРНОВ:")
            report.append(f"   • Общий winrate: {success_patterns['winrate']}%")
            report.append(f"   • Средний PnL: {success_patterns['avg_pnl']:.4f}")
            report.append(f"   • Общий PnL: {success_patterns['total_pnl']:.4f}")
            report.append("")
        
        # Анализ ошибок
        error_patterns = self.analyze_error_patterns()
        if error_patterns:
            report.append("❌ АНАЛИЗ ОШИБОК:")
            report.append(f"   • Всего ошибок: {error_patterns['total_errors']}")
            if 'error_types' in error_patterns:
                report.append("   • Типы ошибок:")
                for error_type, count in error_patterns['error_types'].head(5).items():
                    report.append(f"     - {error_type}: {count}")
            report.append("")
        
        # Оптимальные параметры
        optimal_params = self.find_optimal_parameters()
        if optimal_params and 'recommendations' in optimal_params:
            report.append("🎯 РЕКОМЕНДАЦИИ:")
            for rec in optimal_params['recommendations']:
                report.append(f"   • {rec}")
            report.append("")
        
        report.append("=" * 80)
        return "\n".join(report)
    
    def save_analysis_report(self, filename: str = None):
        """Сохраняет отчет анализа в файл"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.data_dir, f"analysis_report_{timestamp}.txt")
        
        report = self.generate_full_report()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"📄 Отчет сохранен: {filename}")
        return filename 

    def save_trade(self, trade_data):
        """Сохраняет сделку в файл trades_YYYY-MM-DD.json с ротацией по размеру"""
        date_str = datetime.now().strftime('%Y-%m-%d')
        base_name = f"trades_{date_str}.json"
        file_path = os.path.join('learning_data', base_name)
        part = 1
        while os.path.exists(file_path) and os.path.getsize(file_path) > 10*1024*1024:
            part += 1
            file_path = os.path.join('learning_data', f"trades_{date_str}_part{part}.json")
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(trade_data, ensure_ascii=False) + '\n')
    def save_error(self, error_data):
        """Сохраняет ошибку в файл errors_YYYY-MM-DD.json с ротацией по размеру"""
        date_str = datetime.now().strftime('%Y-%m-%d')
        base_name = f"errors_{date_str}.json"
        file_path = os.path.join('learning_data', base_name)
        part = 1
        while os.path.exists(file_path) and os.path.getsize(file_path) > 10*1024*1024:
            part += 1
            file_path = os.path.join('learning_data', f"errors_{date_str}_part{part}.json")
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(error_data, ensure_ascii=False) + '\n')
    def load_all_trades(self):
        """Загружает все сделки из всех файлов trades_*.json"""
        trades = []
        for fname in os.listdir('learning_data'):
            if fname.startswith('trades_') and fname.endswith('.json'):
                with open(os.path.join('learning_data', fname), 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            trades.append(json.loads(line))
                        except:
                            pass
        return trades
    def load_all_errors(self):
        """Загружает все ошибки из всех файлов errors_*.json"""
        errors = []
        for fname in os.listdir('learning_data'):
            if fname.startswith('errors_') and fname.endswith('.json'):
                with open(os.path.join('learning_data', fname), 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            errors.append(json.loads(line))
                        except:
                            pass
        return errors 

    def get_learning_statistics(self) -> dict:
        """Возвращает краткую статистику обучения для отображения в UI и отчетах"""
        stats = {
            'generation': None,
            'total_trades': 0,
            'total_errors': 0,
            'avg_winrate': 0.0,
            'best_winrate': 0.0,
            'knowledge_base_size': 0
        }
        # Поколения (если есть индивиды)
        if self.individuals_data:
            generations = [ind.get('generation', 0) for ind in self.individuals_data]
            stats['generation'] = max(generations) if generations else None
        # Сделки
        if self.trades_df is not None and not self.trades_df.empty:
            stats['total_trades'] = len(self.trades_df)
            winrates = self.trades_df.groupby('individual_id')['win'].mean().apply(lambda x: x * 100)
            stats['avg_winrate'] = float(winrates.mean()) if not winrates.empty else 0.0
            stats['best_winrate'] = float(winrates.max()) if not winrates.empty else 0.0
        # Ошибки
        if self.errors_df is not None and not self.errors_df.empty:
            stats['total_errors'] = len(self.errors_df)
        # Размер базы знаний
        stats['knowledge_base_size'] = len(self.knowledge_base) if self.knowledge_base else 0
        return stats

    def analyze_trade_result(self, trade_data: dict) -> str:
        """Анализирует результат сделки и возвращает краткий текстовый вывод для UI"""
        pnl = trade_data.get('pnl', 0)
        pnl_pct = trade_data.get('pnl_pct', 0)
        win = trade_data.get('win', False)
        symbol = trade_data.get('symbol', '')
        leverage = trade_data.get('leverage', '')
        direction = trade_data.get('direction', '')
        msg = f"{symbol} {direction} x{leverage}: "
        if win:
            msg += f"✅ Профит {pnl:+.2f} ({pnl_pct*100:.2f}%)"
            if pnl_pct > 0.04:
                msg += " — Отличная сделка!"
            elif pnl_pct > 0.02:
                msg += " — Хороший результат."
            else:
                msg += " — Профит, но можно лучше."
        else:
            msg += f"❌ Убыток {pnl:+.2f} ({pnl_pct*100:.2f}%)"
            if pnl_pct < -0.04:
                msg += " — Крупная просадка, стоит пересмотреть стратегию."
            elif pnl_pct < -0.02:
                msg += " — Умеренный убыток, анализируй вход."
            else:
                msg += " — Мелкий минус, не критично."
        return msg 