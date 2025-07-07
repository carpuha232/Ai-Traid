import requests

symbols = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT',
    'DOGEUSDT', 'DOTUSDT', 'LTCUSDT', 'BCHUSDT', 'LINKUSDT',
    'EOSUSDT', 'TRXUSDT', 'XLMUSDT', 'VETUSDT', 'FILUSDT',
    'ATOMUSDT', 'NEARUSDT', 'FTMUSDT', 'ALGOUSDT', 'AVAXUSDT',
    'SHIBUSDT', 'MANAUSDT', 'SANDUSDT', 'CAKEUSDT', 'AAVEUSDT',
    'GALAUSDT', 'AXSUSDT', 'UNIUSDT', 'SOLUSDT', 'MATICUSDT'
]

base_url = "https://api.binance.com/api/v3/ticker/price"

for symbol in symbols:
    try:
        resp = requests.get(base_url, params={"symbol": symbol}, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        print(f"{symbol}: {data['price']}")
    except Exception as e:
        print(f"{symbol}: Ошибка - {e}") 