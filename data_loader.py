"""
📊 Загрузчик сырых данных для автономной нейросети
Загружает исторические данные без технических индикаторов
"""

import pandas as pd
import numpy as np
import zipfile
import os
import random
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

class RawDataLoader:
    """Загрузчик сырых данных для обучения нейросети"""
    
    def __init__(self, data_path: str = '.venv/data/historical'):
        self.data_path = data_path
        self.available_data = []
        self.symbols = []
        self.timeframes = []
        
        # Сканируем доступные данные при инициализации
        self._scan_available_data()
    
    def _scan_available_data(self):
        """Рекурсивно сканирует все ZIP-файлы в подпапках таймфреймов и монет"""
        if not os.path.exists(self.data_path):
            print(f"⚠️ Папка данных не найдена: {self.data_path}")
            return
        
        print(f"🔍 Сканирование данных в: {self.data_path}")
        
        for timeframe_folder in os.listdir(self.data_path):
            timeframe_path = os.path.join(self.data_path, timeframe_folder)
            if not os.path.isdir(timeframe_path):
                continue
            timeframe = timeframe_folder
            for symbol_folder in os.listdir(timeframe_path):
                symbol_path = os.path.join(timeframe_path, symbol_folder)
                if not os.path.isdir(symbol_path):
                    continue
                symbol = symbol_folder
                for filename in os.listdir(symbol_path):
                    if filename.endswith('.zip'):
                        file_path = os.path.join(symbol_path, filename)
                        self.available_data.append({
                            'symbol': symbol,
                            'timeframe': timeframe,
                            'file_path': file_path,
                            'filename': filename
                        })
                        if symbol not in self.symbols:
                            self.symbols.append(symbol)
                        if timeframe not in self.timeframes:
                            self.timeframes.append(timeframe)
        print(f"📊 Найдено {len(self.available_data)} файлов данных")
        print(f"💰 Символы: {len(self.symbols)}")
        print(f"⏰ Таймфреймы: {len(self.timeframes)}")
    
    def scan_available_data(self) -> List[Dict]:
        """Возвращает список доступных данных"""
        return self.available_data
    
    def get_all_symbols(self) -> List[str]:
        """Возвращает список всех доступных символов"""
        return self.symbols
    
    def get_all_timeframes(self) -> List[str]:
        """Возвращает список всех доступных таймфреймов"""
        return self.timeframes
    
    def get_market_data_sample(self, symbol: str, timeframe: str, sample_size: int = 100) -> Optional[Dict]:
        """Получает образец рыночных данных для символа и таймфрейма"""
        
        # Ищем соответствующий файл
        target_file = None
        for data_file in self.available_data:
            if data_file['symbol'] == symbol and data_file['timeframe'] == timeframe:
                target_file = data_file
                break
        
        if not target_file:
            print(f"❌ Данные не найдены для {symbol}_{timeframe}")
            return None
        
        try:
            # Загружаем данные из ZIP файла
            with zipfile.ZipFile(target_file['file_path'], 'r') as zip_file:
                # Получаем имя CSV файла внутри ZIP
                csv_filename = zip_file.namelist()[0]
                
                with zip_file.open(csv_filename) as csv_file:
                    df = pd.read_csv(csv_file)
            
            # Проверяем наличие необходимых колонок
            required_columns = ['open_time', 'open', 'high', 'low', 'close', 'volume']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                print(f"❌ Отсутствуют колонки в {symbol}_{timeframe}: {missing_columns}")
                return None
            
            # Берем случайную выборку
            if len(df) > sample_size:
                df_sample = df.sample(n=sample_size)
            else:
                df_sample = df
            
            # Берем последнюю строку как текущие данные
            latest_data = df_sample.iloc[-1]
            
            # Преобразуем timestamp в час дня
            try:
                timestamp = pd.to_datetime(latest_data['open_time'], unit='ms')
                hour_of_day = timestamp.hour
            except:
                hour_of_day = random.randint(0, 23)
            
            # Возвращаем сырые данные (без индикаторов!)
            market_data = {
                'symbol': symbol,
                'timeframe': timeframe,
                'open': float(latest_data['open']),
                'high': float(latest_data['high']),
                'low': float(latest_data['low']),
                'close': float(latest_data['close']),
                'volume': float(latest_data['volume']),
                'hour_of_day': hour_of_day,
                'timestamp': latest_data['open_time']
            }
            
            return market_data
            
        except Exception as e:
            print(f"❌ Ошибка загрузки данных {symbol}_{timeframe}: {e}")
            return None
    
    def get_historical_data(self, symbol: str, timeframe: str, limit: int = 1000) -> Optional[pd.DataFrame]:
        """Получает исторические данные для анализа"""
        
        # Ищем соответствующий файл
        target_file = None
        for data_file in self.available_data:
            if data_file['symbol'] == symbol and data_file['timeframe'] == timeframe:
                target_file = data_file
                break
        
        if not target_file:
            return None
        
        try:
            # Загружаем данные из ZIP файла
            with zipfile.ZipFile(target_file['file_path'], 'r') as zip_file:
                csv_filename = zip_file.namelist()[0]
                
                with zip_file.open(csv_filename) as csv_file:
                    df = pd.read_csv(csv_file)
            
            # Ограничиваем количество строк
            if len(df) > limit:
                df = df.tail(limit)
            
            return df
            
        except Exception as e:
            print(f"❌ Ошибка загрузки исторических данных {symbol}_{timeframe}: {e}")
            return None
    
    def get_data_statistics(self) -> Dict:
        """Возвращает статистику доступных данных"""
        stats = {
            'total_files': len(self.available_data),
            'symbols_count': len(self.symbols),
            'timeframes_count': len(self.timeframes),
            'symbols': self.symbols,
            'timeframes': self.timeframes,
            'data_files': self.available_data
        }
        
        return stats 