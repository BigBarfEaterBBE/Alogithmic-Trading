import pandas as pd
import os
import sys

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.requests import StockBarsRequest
from alpaca.data.requests import StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from alpaca.trading.client import TradingClient

from datetime import datetime, timedelta

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
sys.path.append(PROJECT_ROOT)

import confidential
PB_API_KEY = confidential.PB_API_KEY
PB_SECRET_KEY = confidential.PB_SECRET
MR_API_KEY = confidential.MR_API_KEY
MR_SECRET_KEY = confidential.MR_SECRET

data_client = StockHistoricalDataClient(
    confidential.PB_API_KEY,
    confidential.PB_SECRET
)

pb_client = TradingClient(
    PB_API_KEY,
    PB_SECRET_KEY,
    paper=True
)

mr_client = TradingClient(
    MR_API_KEY,
    MR_SECRET_KEY,
    paper=True
)


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EQUITY_FILE = os.path.join(BASE_DIR, "equity.csv")
TRADES_FILE = os.path.join(BASE_DIR, "trades.csv")

def get_equity_data():
    df = pd.read_csv(EQUITY_FILE)
    # keep only necessary columns (for now)
    df = df[["time", "strategy", "equity"]]
    #remove duplicates
    df["time"] = pd.to_datetime(df["time"])

    # round timestamps to nearest minute
    df["time"] = df["time"].dt.floor("min")

    df = df.drop_duplicates(subset=["time", "strategy"], keep="last")

    return df.to_dict(orient="records")

def get_trades_data():
    df = pd.read_csv(TRADES_FILE)

    df = df.fillna("")

    return df.to_dict(orient="records")

    
def combine_positions(pb_positions, mr_positions):
    result = []
    all_positions = [
        ("PB", pb_positions),
        ("MR", mr_positions)
    ]

    for strategy, positions in all_positions:
        for pos in positions:
            ticker = pos.symbol
            shares = float(pos.qty)
            avg_cost = float(pos.avg_entry_price)
            market_value = float(pos.market_value)
            unrealized_pl = float(pos.unrealized_pl)
            pnl_percent = (
                unrealized_pl / (shares * avg_cost)
                if shares * avg_cost > 0 else 0
            )
            price_data = get_price_change_data(ticker)

            result.append({
                "ticker": ticker,
                "strategy": strategy,
                "shares": round(shares,4),
                "avg_cost": round(avg_cost, 2),
                "market_value": round(market_value, 2),
                "pnl": round(unrealized_pl, 2),
                "pnl_percent": round(pnl_percent * 100,2),
                "current_price": price_data["current_price"],
                "day_change_percent": price_data["change_percent"],
                "day_change_dollars": price_data["change_dollars"],
                "logo": f"https://assets.parqet.com/logos/symbol/{ticker}?format=png",
                "chart": get_mini_chart(ticker)
            })
    return result

def get_mini_chart(ticker):
    try:
        end = datetime.utcnow()
        start = end - timedelta(days = 7)
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe = TimeFrame(1, TimeFrameUnit.Hour),
            start = start,
            end = end,
            feed="iex"
        )
        bars = data_client.get_stock_bars(request)
        if ticker not in bars.data:
            return []
        prices = [bar.close for bar in bars.data[ticker]]
        if not prices:
            return []
        base = prices[0]
        normalized = [
            round((p / base) * 100, 2) for p in prices
        ]
        return normalized
    except Exception as e:
        print(f"CHART ERROR {ticker}: {e}")
        return []

def get_price_change_data(ticker):
    try:
        end = datetime.utcnow()
        start = end - timedelta(days = 1)
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame(15, TimeFrameUnit.Minute),
            start=start,
            end=end,
            feed="iex"
        )
        bars = data_client.get_stock_bars(request)
        if ticker not in bars.data:
            return {
                "change_percent": 0,
                "change_dollars": 0,
                "current_price": 0
            }
        prices = [bar.close for bar in bars.data[ticker]]
        if len(prices) < 2:
            return {
                "change_percent": 0,
                "change_dollars": 0,
                "current_price": prices[0] if prices else 0
            }
        first_price = prices[0]
        current_price = prices[-1]
        change_percent = ((current_price - first_price) / first_price) * 100
        change_dollars = current_price - first_price
        return {
            "change_percent": round(change_percent, 2),
            "change_dollars": round(change_dollars, 2),
            "current_price": round(current_price, 2)
        }
    except Exception as e:
        print(f"CHANGE ERROR {ticker}: {e}")
        return {
            "change_percent": 0,
            "change_dollars": 0,
            "current_price": 0
        }