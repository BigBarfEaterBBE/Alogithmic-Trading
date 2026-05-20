import pandas as pd
import os
import sys

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.requests import StockBarsRequest
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

# def get_positions():
#     df = pd.read_csv(TRADES_FILE)
#     df = df.fillna("")
#     positions = {}
#     for _, row in df.iterrows():
#         ticker = row['ticker']
#         action = str(row["action"]).replace(" ", "_").strip().upper()
#         qty = float(row['qty'])

#         if ticker not in positions:
#             positions[ticker] = 0
        
#         if action in ['BUY', 'ADD']:
#             positions[ticker] += qty
#         elif action == "SELL":
#             positions[ticker] -= qty
#         elif action == "PARTIAL_SELL":
#             positions[ticker] -= qty
        
#         # prevent negative drift
#         if positions[ticker] < 0:
#             positions[ticker] =0
#     # convert to list
#     result = [
#         {"ticker": t, "shares": s}
#         for t, s in positions.items() if s > 0
#     ]

#     return result

# def get_positions_with_cost():
#     df = pd.read_csv(TRADES_FILE)
#     df = df.fillna("")
#     positions = {}
#     for _, row in df.iterrows():
#         ticker = row['ticker']
#         action = row['action']
#         qty = float(row['qty'])
#         price = float(row["price"]) if "price" in row else 0

#         if ticker not in positions:
#             positions[ticker] = {
#                 "shares": 0,
#                 "cost": 0
#             }
#         if action in ["BUY", "ADD"]:
#             positions[ticker]["cost"] += qty * price
#             positions[ticker]["shares"] += qty
#         elif action in ["SELL", "PARTIAL_SELL"]:
#             #reduce shares only (avg-cost )
#             if positions[ticker]["shares"] > 0:
#                 avg_cost = positions[ticker]["cost"] / positions[ticker]["shares"]
#                 positions[ticker]["shares"] -= qty
#                 positions[ticker]["cost"] -= qty * avg_cost
#         if positions[ticker]["shares"] < 0:
#             positions[ticker]["shares"] = 0
#             positions[ticker]["cost"] = 0
#     result = []
#     for t, v in positions.items():
#         if v["shares"] > 0:
#             result.append({
#                 "ticker": t,
#                 "shares": v["shares"],
#                 "avg_cost": v["cost"] / v["shares"] if v["shares"] > 0 else 0
#             })
#     return result

# def get_live_prices():
#     positions = get_positions_with_cost()
#     if not positions:
#         return []
#     tickers = [p["ticker"] for p in positions]
#     try:
#         quote_request = StockLatestQuoteRequest(symbol_or_symbols=tickers)
#         quotes = data_client.get_stock_latest_quote(quote_request)
#         result = []
#         for pos in positions:
#             ticker = pos["ticker"]
#             if ticker not in quotes:
#                 continue
#             quote = quotes[ticker]
#             current_price = quote.ask_price or quote.bid_price or avg_cost
#             shares = pos["shares"]
#             avg_cost = pos["avg_cost"]

#             market_value = shares * current_price
#             cost_basis = shares * avg_cost

#             pnl = market_value - cost_basis
#             pnl_percent = (
#                 (current_price - avg_cost) / avg_cost * 100
#                 if avg_cost > 0 else 0
#             )
#             result.append({
#                 "ticker": ticker,
#                 "shares": round(shares, 4),
#                 "avg_cost": round(avg_cost, 2),
#                 "current": round(current_price, 2),
#                 "market_value": round(market_value, 2),
#                 "pnl": round(pnl, 2),
#                 "pnl_percent": round(pnl_percent, 2)
#             })
#         return result
#     except Exception as e:
#         print(f"PRICE FETCH ERROR: {e}")
#         return []
    
def combine_positions(pb_positions, mr_positions):
    combined = {}
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

            if ticker not in combined:
                combined[ticker] = {
                    "ticker": ticker,
                    "shares": 0,
                    "cost_basis": 0,
                    "market_value": 0,
                    "pnl": 0,
                    "strategies": []
                }
            combined[ticker]["shares"] += shares
            combined[ticker]["cost_basis"] += shares * avg_cost
            combined[ticker]["market_value"] += market_value
            combined[ticker]["pnl"] += unrealized_pl

            combined[ticker]["strategies"].append({
                "strategy": strategy,
                "shares": shares
            })
    result = []
    for ticker, pos in combined.items():
        avg_cost = (
            pos["cost_basis"] / pos["shares"] if pos["shares"] > 0 else 0
        )
        pnl_percent = (
            pos["pnl"] / pos["cost_basis"] if pos["cost_basis"] > 0 else 0
        )
        result.append({
            "ticker": ticker,
            "shares": round(pos["shares"], 4),
            "avg_cost": round(avg_cost, 2),
            "market_value": round(pos["market_value"], 2),
            "pnl": round(pos["pnl"], 2),
            "pnl_percent": round(pnl_percent * 100,2),
            "logo": f"https://assets.parqet.com/logos/symbol/{ticker}?format=png",
            "chart": get_mini_chart(ticker),
            "strategies": pos["strategies"]
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