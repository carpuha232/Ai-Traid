# 🚀 Scalping Bot - AI-Powered Crypto Trading

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)](https://pypi.org/project/PySide6/)

**Автоматический торговый бот для скальпинга криптовалют на Binance Futures**

## ✨ Особенности

### 🧮 Математический анализ
- **Fibonacci Retracement** - уровни поддержки/сопротивления
- **Probability Theory** - расчёт P(up) и P(down)
- **Pi Ratio (φ = 3.14159)** - золотое сечение для точек входа
- **Order Book Analysis** - анализ стакана в реальном времени
- **Volume Analysis** - bull/bear pressure detection

### 🎯 Умный Risk Management
- **Kelly Criterion inspired** - оптимизация размера позиции
- **Dynamic Leverage** - 50-100x в зависимости от уверенности
- **Fixed Risk per Trade** - 1% от депозита на сделку
- **Stop Loss & Take Profit** - автоматические уровни
- **Risk:Reward 1:2** - математически прибыльное соотношение

### 💻 Modern GUI (PySide6)
- **Real-time данные** - WebSocket подключение к Binance
- **Signal Scanner** - поиск сигналов по 20 парам
- **Positions Monitor** - отслеживание открытых позиций
- **History & Statistics** - анализ закрытых сделок
- **One-click Controls** - управление ботом одной кнопкой

### 🛡️ Безопасность
- **Paper Trading** - тестирование без риска
- **Commission Simulation** - учёт комиссий биржи (0.02%/0.04%)
- **Slippage Model** - реалистичное исполнение ордеров
- **Liquidation Protection** - защита от ликвидации

## 📋 Требования

- Python 3.10+
- Binance API Key (для live trading)
- Windows/Linux/MacOS

## 🔧 Установка

```bash
# Клонировать репозиторий
git clone https://github.com/yourusername/scalping-bot.git
cd scalping-bot

# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt
```

## 🚀 Быстрый старт

### Paper Trading (Рекомендуется для начала)

```bash
# Просто запустить!
python main.py
```

### Live Trading

1. Создайте API ключи на [Binance](https://www.binance.com/en/my/settings/api-management)
2. Отредактируйте `config.json`:

```json
{
  "mode": "live",
  "binance": {
    "api_key": "your_api_key_here",
    "api_secret": "your_api_secret_here"
  }
}
```

3. Запустите бота:
```bash
python main.py
```

## ⚙️ Конфигурация

Основные параметры в `config.json`:

```json
{
  "mode": "paper_trading",  // "paper_trading" или "live"
  
  "account": {
    "starting_balance": 1000,  // Стартовый баланс ($)
    "leverage": 75,            // Плечо (50-100)
    "max_positions": 3         // Макс. позиций одновременно
  },
  
  "risk": {
    "base_risk_percent": 1.0,        // Риск на сделку (%)
    "take_profit_multiplier": 2.0    // Risk:Reward (1:2)
  },
  
  "signals": {
    "min_confidence": 60,  // Мин. уверенность сигнала (%)
    "pairs": [             // Торгуемые пары
      "BTCUSDT", "ETHUSDT", "BNBUSDT", ...
    ]
  }
}
```

## 📊 Как работает анализ

### 1. Order Book Imbalance
```python
bid_volume = sum(orderbook['bids'])
ask_volume = sum(orderbook['asks'])
imbalance = bid_volume / (bid_volume + ask_volume) * 100
# > 55% = LONG bias, < 45% = SHORT bias
```

### 2. Fibonacci Levels
```python
# Расчёт уровней на основе High/Low последних 100 свечей
levels = [0.236, 0.382, 0.5, 0.618, 0.786]
support = low + (high - low) * fib_level
resistance = high - (high - low) * fib_level
```

### 3. Probability Theory
```python
# Базовая вероятность + корректировки
P(up) = base_prob * (1 + bull_strength * 0.05)
P(down) = base_prob * (1 + bear_strength * 0.05)

# Открываем сделку только если P > 60%
```

### 4. Expected Value
```python
EV = P(win) × Profit - P(loss) × Loss
# Торгуем только если EV > 0
```

## 📈 Метрики производительности

Бот отслеживает:
- **Winrate** - процент прибыльных сделок
- **Average R:R** - среднее соотношение риск/прибыль
- **Max Drawdown** - максимальная просадка
- **Profit Factor** - отношение прибыли к убыткам
- **Sharpe Ratio** - доходность с учётом риска

## 🗂️ Структура проекта

```
scalping-bot/
├── main.py                 # Точка входа, главный бот
├── run_bot.py             # Лаунчер (обход проблем с путями)
├── config.json            # Конфигурация
├── requirements.txt       # Зависимости
│
├── core/                  # Ядро бота
│   ├── bot_core.py       # Основная логика
│   ├── signal_analyzer.py # Анализ сигналов (Fib, Pi, Probability)
│   ├── config_manager.py # Управление конфигом
│   └── live_trader.py    # Live торговля на Binance
│
├── binance_api/          # Интеграция с Binance
│   └── binance_client.py # WebSocket + REST API
│
├── simulation/           # Paper Trading
│   └── paper_trader.py  # Симуляция сделок
│
├── gui/                  # Графический интерфейс
│   ├── main_window.py   # Главное окно (PySide6)
│   ├── README.md        # Документация GUI
│   └── CHANGELOG.md     # История изменений
│
├── logs/                # Логи работы бота
└── results/             # Сохранённые сессии (JSON)
```

## 🔮 Roadmap

### ✅ V1.0 (Текущая версия)
- [x] Real-time данные с Binance WebSocket
- [x] Fibonacci + Probability + Pi анализ
- [x] Paper Trading симулятор
- [x] Modern GUI (PySide6)
- [x] Risk Management (Kelly inspired)

### 🚧 V2.0 (В разработке)
- [ ] **Backtesting Engine** - тестирование на истории
- [ ] **Hyperparameter Optimization** - автопоиск параметров
- [ ] **Walk-Forward Analysis** - валидация стратегии
- [ ] **Machine Learning** - повышение точности сигналов

### 🌟 V3.0 (Планируется)
- [ ] **Reinforcement Learning** - самообучающийся агент
- [ ] **Multi-timeframe Analysis** - анализ разных таймфреймов
- [ ] **Sentiment Analysis** - анализ новостей и соцсетей
- [ ] **Portfolio Management** - управление несколькими стратегиями

## ⚠️ Предупреждение

**Торговля криптовалютами сопряжена с высоким риском!**

- Используйте **только те деньги, которые готовы потерять**
- Начинайте с **Paper Trading** для изучения бота
- **Тестируйте стратегии** перед реальной торговлей
- Автор **не несёт ответственности** за ваши убытки

## 📄 Лицензия

MIT License - смотри [LICENSE](LICENSE)

## 🤝 Контрибьюция

Pull requests приветствуются! Для крупных изменений сначала откройте issue.

## 📞 Поддержка

- 🐛 **Баги**: [GitHub Issues](https://github.com/yourusername/scalping-bot/issues)
- 💬 **Вопросы**: [GitHub Discussions](https://github.com/yourusername/scalping-bot/discussions)
- 📧 **Email**: your.email@example.com

---

**⭐ Если проект полезен - поставьте звезду на GitHub!**

Made with ❤️ by crypto enthusiasts for crypto enthusiasts
