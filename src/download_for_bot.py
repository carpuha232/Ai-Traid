#!/usr/bin/env python3
"""
Финальный скрипт для скачивания исторических данных Binance для торгового бота
Скачивает данные с 1 июля 2024 по июнь 2025 года
"""

import os
import requests
import zipfile
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('download_bot_log.txt'),
        logging.StreamHandler()
    ]
)

# Топ-30 монет по капитализации (USDT пары)
TOP_30_COINS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT',
    'XRPUSDT', 'DOTUSDT', 'DOGEUSDT', 'AVAXUSDT', 'MATICUSDT',
    'LINKUSDT', 'UNIUSDT', 'LTCUSDT', 'BCHUSDT', 'XLMUSDT',
    'ATOMUSDT', 'ETCUSDT', 'FILUSDT', 'TRXUSDT', 'NEARUSDT',
    'ALGOUSDT', 'VETUSDT', 'ICPUSDT', 'FTMUSDT', 'MANAUSDT',
    'SANDUSDT', 'AXSUSDT', 'GALAUSDT', 'ROSEUSDT', 'CHZUSDT'
]

# Таймфреймы для скачивания
TIMEFRAMES = ['5m', '15m', '30m', '1h', '2h', '4h']

# Базовый URL для данных Binance
BASE_URL = "https://data.binance.vision/data/spot/monthly/klines"

def create_directories():
    """Создает необходимые директории для бота"""
    # Основная папка для данных бота
    base_dir = Path("trading_bot/data/historical")
    base_dir.mkdir(parents=True, exist_ok=True)
    
    # Создаем папки для каждого таймфрейма
    for timeframe in TIMEFRAMES:
        (base_dir / timeframe).mkdir(exist_ok=True)
    
    return base_dir

def check_file_exists(url):
    """Проверяет существование файла на сервере"""
    try:
        response = requests.head(url, timeout=10)
        return response.status_code == 200
    except:
        return False

def download_file(url, filepath):
    """Скачивает файл с обработкой ошибок"""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True
    except Exception as e:
        logging.error(f"Ошибка скачивания {url}: {e}")
        return False

def extract_zip(zip_path, extract_to):
    """Распаковывает ZIP файл"""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        return True
    except Exception as e:
        logging.error(f"Ошибка распаковки {zip_path}: {e}")
        return False

def process_csv_to_parquet(csv_path, parquet_path):
    """Конвертирует CSV в Parquet для быстрого чтения"""
    try:
        # Читаем CSV с правильными колонками
        columns = [
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ]
        
        df = pd.read_csv(csv_path, names=columns, header=None)
        
        # Проверяем и исправляем временные метки
        # Если временные метки слишком большие, делим на 1000
        if df['open_time'].max() > 1e12:  # Если больше 12 цифр
            df['open_time'] = df['open_time'] // 1000
            df['close_time'] = df['close_time'] // 1000
        
        # Конвертируем временные метки
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', errors='coerce')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms', errors='coerce')
        
        # Удаляем строки с некорректными датами
        df = df.dropna(subset=['open_time', 'close_time'])
        
        if len(df) == 0:
            logging.warning(f"Нет данных для {csv_path}")
            return False
        
        # Конвертируем числовые колонки
        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 
                          'quote_volume', 'taker_buy_base', 'taker_buy_quote']
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['trades'] = pd.to_numeric(df['trades'], errors='coerce')
        
        # Удаляем строки с NaN в важных колонках
        df = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
        
        if len(df) == 0:
            logging.warning(f"Нет валидных данных после очистки для {csv_path}")
            return False
        
        # Сохраняем в Parquet
        df.to_parquet(parquet_path, index=False)
        
        # Удаляем CSV файл для экономии места
        os.remove(csv_path)
        
        logging.info(f"✓ Обработано {len(df)} строк")
        return True
    except Exception as e:
        logging.error(f"Ошибка обработки {csv_path}: {e}")
        return False

def get_available_months():
    """Определяет доступные месяцы для скачивания"""
    available_months = []
    
    # 2024 год - с июля по декабрь
    for month in range(7, 13):  # Июль-декабрь 2024
        available_months.append((2024, month))
    
    # 2025 год - с января по июнь
    for month in range(1, 7):  # Январь-июнь 2025
        test_url = f"{BASE_URL}/BTCUSDT/1h/BTCUSDT-1h-2025-{month:02d}.zip"
        if check_file_exists(test_url):
            available_months.append((2025, month))
        else:
            logging.info(f"Файлы за {month}/2025 недоступны, останавливаемся")
            break
    
    return available_months

def download_bot_data():
    """Основная функция скачивания данных для бота"""
    base_dir = create_directories()
    
    logging.info(f"Начинаем скачивание данных для торгового бота")
    logging.info(f"Период: 1 июля 2024 - июнь 2025")
    logging.info(f"Монеты: {len(TOP_30_COINS)}")
    logging.info(f"Таймфреймы: {TIMEFRAMES}")
    
    # Получаем список доступных месяцев
    available_months = get_available_months()
    logging.info(f"Доступных месяцев: {len(available_months)}")
    logging.info(f"Месяцы: {available_months}")
    
    total_files = len(TOP_30_COINS) * len(TIMEFRAMES) * len(available_months)
    downloaded_files = 0
    
    for coin in TOP_30_COINS:
        logging.info(f"Обрабатываем {coin}...")
        
        for timeframe in TIMEFRAMES:
            timeframe_dir = base_dir / timeframe
            coin_dir = timeframe_dir / coin
            coin_dir.mkdir(exist_ok=True)
            
            for year, month in available_months:
                month_str = f"{month:02d}"
                
                # Формируем URL для скачивания
                filename = f"{coin}-{timeframe}-{year}-{month_str}.zip"
                url = f"{BASE_URL}/{coin}/{timeframe}/{filename}"
                
                zip_path = coin_dir / filename
                csv_filename = f"{coin}-{timeframe}-{year}-{month_str}.csv"
                csv_path = coin_dir / csv_filename
                parquet_filename = f"{coin}-{timeframe}-{year}-{month_str}.parquet"
                parquet_path = coin_dir / parquet_filename
                
                # Пропускаем если файл уже существует
                if parquet_path.exists():
                    logging.info(f"Файл {parquet_filename} уже существует, пропускаем")
                    downloaded_files += 1
                    continue
                
                # Проверяем доступность файла
                if not check_file_exists(url):
                    logging.warning(f"Файл {filename} недоступен, пропускаем")
                    continue
                
                # Скачиваем ZIP файл
                logging.info(f"Скачиваем {filename}...")
                if download_file(url, zip_path):
                    # Распаковываем
                    if extract_zip(zip_path, coin_dir):
                        # Конвертируем в Parquet
                        if process_csv_to_parquet(csv_path, parquet_path):
                            # Удаляем ZIP файл
                            os.remove(zip_path)
                            downloaded_files += 1
                            logging.info(f"✓ Успешно обработан {filename}")
                        else:
                            logging.error(f"✗ Ошибка конвертации {filename}")
                    else:
                        logging.error(f"✗ Ошибка распаковки {filename}")
                else:
                    logging.error(f"✗ Ошибка скачивания {filename}")
                
                # Небольшая пауза между запросами
                time.sleep(0.5)
        
        logging.info(f"Завершена обработка {coin}")
    
    logging.info(f"Скачивание завершено! Обработано файлов: {downloaded_files}/{total_files}")

def create_data_summary():
    """Создает сводку по скачанным данным"""
    base_dir = Path("trading_bot/data/historical")
    summary = []
    
    for timeframe in TIMEFRAMES:
        timeframe_dir = base_dir / timeframe
        if not timeframe_dir.exists():
            continue
            
        for coin_dir in timeframe_dir.iterdir():
            if coin_dir.is_dir():
                parquet_files = list(coin_dir.glob("*.parquet"))
                if parquet_files:
                    try:
                        # Читаем все файлы для подсчета общего количества строк
                        total_rows = 0
                        min_date = None
                        max_date = None
                        
                        for f in parquet_files:
                            df = pd.read_parquet(f)
                            total_rows += len(df)
                            if min_date is None or df['open_time'].min() < min_date:
                                min_date = df['open_time'].min()
                            if max_date is None or df['open_time'].max() > max_date:
                                max_date = df['open_time'].max()
                        
                        summary.append({
                            'coin': coin_dir.name,
                            'timeframe': timeframe,
                            'files_count': len(parquet_files),
                            'total_rows': total_rows,
                            'date_range': f"{min_date.date() if min_date else 'N/A'} - {max_date.date() if max_date else 'N/A'}"
                        })
                    except Exception as e:
                        logging.error(f"Ошибка чтения {coin_dir}: {e}")
    
    # Сохраняем сводку
    if summary:
        summary_df = pd.DataFrame(summary)
        summary_df.to_csv("trading_bot/data/data_summary.csv", index=False)
        logging.info("Сводка сохранена в trading_bot/data/data_summary.csv")
        
        # Выводим статистику
        print("\n=== СТАТИСТИКА СКАЧАННЫХ ДАННЫХ ===")
        print(f"Период: 1 июля 2024 - июнь 2025")
        print(f"Всего монет: {summary_df['coin'].nunique()}")
        print(f"Всего таймфреймов: {summary_df['timeframe'].nunique()}")
        print(f"Всего файлов: {summary_df['files_count'].sum()}")
        print(f"Всего строк данных: {summary_df['total_rows'].sum():,}")
        print(f"Данные сохранены в: trading_bot/data/historical/")

def create_data_loader():
    """Создает загрузчик данных для бота"""
    loader_code = '''
import pandas as pd
from pathlib import Path
from typing import List, Optional
import logging

class HistoricalDataLoader:
    """Загрузчик исторических данных для торгового бота"""
    
    def __init__(self, data_path: str = "trading_bot/data/historical"):
        self.data_path = Path(data_path)
        self.logger = logging.getLogger(__name__)
    
    def get_coin_data(self, coin: str, timeframe: str, start_date: Optional[str] = None, 
                     end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Загружает данные для конкретной монеты и таймфрейма
        
        Args:
            coin: Название монеты (например, 'BTCUSDT')
            timeframe: Таймфрейм ('5m', '15m', '30m', '1h', '2h', '4h')
            start_date: Начальная дата в формате 'YYYY-MM-DD'
            end_date: Конечная дата в формате 'YYYY-MM-DD'
        
        Returns:
            DataFrame с историческими данными
        """
        coin_dir = self.data_path / timeframe / coin
        
        if not coin_dir.exists():
            self.logger.error(f"Директория {coin_dir} не существует")
            return pd.DataFrame()
        
        # Читаем все parquet файлы
        parquet_files = list(coin_dir.glob("*.parquet"))
        if not parquet_files:
            self.logger.error(f"Нет данных для {coin} {timeframe}")
            return pd.DataFrame()
        
        # Объединяем все файлы
        dfs = []
        for file in sorted(parquet_files):
            df = pd.read_parquet(file)
            dfs.append(df)
        
        if not dfs:
            return pd.DataFrame()
        
        # Объединяем все данные
        combined_df = pd.concat(dfs, ignore_index=True)
        combined_df = combined_df.sort_values('open_time').reset_index(drop=True)
        
        # Фильтруем по датам если указаны
        if start_date is not None:
            start_dt = pd.to_datetime(start_date)
            combined_df = combined_df[combined_df['open_time'] >= start_dt]
        if end_date is not None:
            end_dt = pd.to_datetime(end_date)
            combined_df = combined_df[combined_df['open_time'] <= end_dt]
        
        self.logger.info(f"Загружено {len(combined_df)} строк для {coin} {timeframe}")
        return combined_df
    
    def get_available_coins(self) -> List[str]:
        """Возвращает список доступных монет"""
        coins = []
        for timeframe_dir in self.data_path.iterdir():
            if timeframe_dir.is_dir():
                for coin_dir in timeframe_dir.iterdir():
                    if coin_dir.is_dir() and coin_dir.name not in coins:
                        coins.append(coin_dir.name)
        return sorted(coins)
    
    def get_available_timeframes(self) -> List[str]:
        """Возвращает список доступных таймфреймов"""
        timeframes = []
        for timeframe_dir in self.data_path.iterdir():
            if timeframe_dir.is_dir():
                timeframes.append(timeframe_dir.name)
        return sorted(timeframes)

# Пример использования:
if __name__ == "__main__":
    loader = HistoricalDataLoader()
    
    # Получаем данные BTCUSDT за последний месяц
    btc_data = loader.get_coin_data('BTCUSDT', '1h', start_date='2025-05-01')
    print(f"BTC данные: {len(btc_data)} строк")
    
    # Список доступных монет
    coins = loader.get_available_coins()
    print(f"Доступные монеты: {len(coins)}")
    
    # Список доступных таймфреймов
    timeframes = loader.get_available_timeframes()
    print(f"Доступные таймфреймы: {timeframes}")
'''
    
    # Создаем файл загрузчика
    loader_path = Path("trading_bot/data_loader.py")
    loader_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(loader_path, 'w', encoding='utf-8') as f:
        f.write(loader_code)
    
    logging.info(f"Создан загрузчик данных: {loader_path}")

if __name__ == "__main__":
    print("🚀 Начинаем скачивание исторических данных для торгового бота")
    print("📅 Период: 1 июля 2024 - июнь 2025")
    print("📁 Данные сохраняются в trading_bot/data/historical/")
    print("=" * 60)
    
    download_bot_data()
    create_data_summary()
    create_data_loader()
    
    print("\n✅ Скачивание завершено!")
    print("📁 Данные сохранены в папке 'trading_bot/data/historical/'")
    print("📊 Сводка сохранена в 'trading_bot/data/data_summary.csv'")
    print("🔧 Загрузчик создан: 'trading_bot/data_loader.py'")
    print("📝 Лог сохранен в 'download_bot_log.txt'")
    print("\n💡 Для использования данных в боте:")
    print("   from trading_bot.data_loader import HistoricalDataLoader")
    print("   loader = HistoricalDataLoader()")
    print("   data = loader.get_coin_data('BTCUSDT', '1h')") 