import pandas as pd
from pathlib import Path
from typing import List, Optional
import logging

class HistoricalDataLoader:
    """Загрузчик исторических данных для торгового бота"""
    
    def __init__(self, data_path: Optional[str] = None):
        if data_path is None:
            # Пробуем разные пути к данным
            possible_paths = [
                "data/historical",  # Если запускаем из trading_bot/
                "trading_bot/data/historical",  # Если запускаем из корневой папки
                "../data/historical"  # Альтернативный путь
            ]
            
            for path in possible_paths:
                if Path(path).exists():
                    self.data_path = Path(path)
                    break
            else:
                # Если ни один путь не найден, используем первый по умолчанию
                self.data_path = Path("data/historical")
        else:
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