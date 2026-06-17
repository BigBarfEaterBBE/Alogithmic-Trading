import requests

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import DataFeed

import confidential
from datetime import datetime, timedelta

stock_client = StockHistoricalDataClient(confidential.MB_API_KEY, confidential.MB_SECRET, raw_data=False)

def get_most_active_stocks(limit=20):
    url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
    params = {
        "scrIds": "most_actives",
        "count": 20
    }
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, params=params, headers=headers, timeout=10)
    data = response.json()
    quotes = data["finance"]["result"][0]["quotes"]
    tickers = []
    for stock in quotes:
        symbol = stock["symbol"]
        # skip ETFs
        if "." in symbol:
            continue
        price = stock.get("regularMarketPrice", 0)
        volume = stock.get("regularMarketVolume", 0)
        if price < 5:
            continue
        if volume < 1_000_000:
            continue
        tickers.append(symbol)
    print(tickers)
    return tickers

def score_stock(ticker):
    req = StockBarsRequest(symbol_or_symbols=[ticker],timeframe=TimeFrame(amount=5,unit=TimeFrameUnit.Minute),start=datetime.now()-timedelta(days=5),feed=DataFeed.IEX)
    bars = stock_client.get_stock_bars(req).df
    df = bars.xs(ticker)
    if len(df) < 50:
        return None
    price = df["close"].iloc[-1]
    high20 = df["high"].rolling(20).max().iloc[-1]
    vol_ratio = (df["volume"].iloc[-1] / df["volume"].rolling(20).mean().iloc[-1])
    return20 = (price / df["close"].iloc[-20]) - 1
    ma50 = df["close"].rolling(50).mean().iloc[-1]
    ma_strength = (price / ma50 - 1)
    breakout_strength = price / high20
    score = (return20 * 100 + vol_ratio*10 + ma_strength * 100 + breakout_strength * 20)
    return score

def get_ranked_watchlist(limit=10):
    most_active = get_most_active_stocks(30)
    rankings = []
    for ticker in most_active:
        try:
            score = score_stock(ticker)
            if score is not None:
                rankings.append((ticker,score))
        except Exception as e:
            print(f"{ticker}: {e}")
    rankings.sort(key=lambda x: x[1], reverse=True)
    watchlist = [ticker for ticker, score in rankings[:limit]]
    print("\nRanked Watchlist:")
    for ticker, score in rankings[:limit]:
        print(f"{ticker}: {score:.2f}")
    return watchlist

if __name__ == "__main__":
    get_most_active_stocks()