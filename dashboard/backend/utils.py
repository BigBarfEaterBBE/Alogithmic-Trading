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
    df["time"] = pd.to_datetime(df["time"],format="mixed",utc=True)

    # round timestamps to nearest minute
    df["time"] = df["time"].dt.floor("min")

    df = df.drop_duplicates(subset=["time", "strategy"], keep="last")

    return df.to_dict(orient="records")

def get_trades_data():
    df = pd.read_csv(TRADES_FILE)

    df = df.fillna("")

    # normalize
    df["qty"] = pd.to_numeric(df.get("qty", df.get("shares", 0)), errors="coerce").fillna(0)
    df["price"] = pd.to_numeric(df.get("price", 0), errors="coerce").fillna(0)

    # track positiions per strategy + ticker
    positions = {}
    realized_pnls = []
    df["time"] = pd.to_datetime(df["time"],format="mixed",utc=True)
    df = df.sort_values("time")
    for _, row in df.iterrows():
        ticker = row.get("ticker") or row.get("symbol")
        strategy = row.get("strategy", "")
        side = str(row.get("side") or row.get("action") or "").upper()
        qty = float((row["qty"] or 0))
        price = float(row['price'] or 0)

        key = (strategy, ticker)
        if key not in positions:
            positions[key] = {
                "shares": 0,
                "avg_cost":0
            }
        pos = positions[key]
        realized = None
        if side in ["BUY", "ADD"]:
            total_cost = (
                pos["shares"] * pos["avg_cost"]
            ) + (qty * price)

            pos["shares"] += qty

            if pos["shares"] > 0:
                pos["avg_cost"] = total_cost / pos["shares"]
        elif side in ["SELL", "PARTIAL_SELL", "PARTIAL SELL"]:
            if pos['avg_cost'] is not None:
                realized = round((price - pos['avg_cost']) * qty, 2)
            else:
                realized = 0
            pos["shares"] -= qty
            if pos["shares"] <= 0:
                pos["shares"] = 0
                pos['avg_cost'] = 0
        realized_pnls.append(round(realized,2) if realized is not None else None)
    df['realized_pnl'] = realized_pnls
    df = df.astype(object)
    df = df.where(pd.notnull(df), None)
    records = df.to_dict(orient="records")
    for row in records:
        for key, value in row.items():
            if pd.isna(value):
                row[key] = None
    return records
    
def combine_positions(pb_positions, mr_positions):
    result = []
    all_positions = [
        ("PB", pb_positions),
        ("MR", mr_positions)
    ]
    # Get unique tickers
    tickers = list({
        pos.symbol
        for _, positions in all_positions
        for pos in positions
    })

    # batch requests
    all_price_data = get_price_change_data(tickers) or {}
    all_charts = get_mini_charts(tickers) or {}

    # form return answer
    for strategy, positions in all_positions:
        for pos in positions:
            ticker = pos.symbol
            shares = float(pos.qty)
            avg_cost = float(pos.avg_entry_price)
            market_value = float(pos.market_value)
            unrealized_pl = float(pos.unrealized_pl)
            pnl_percent = (
                unrealized_pl / (shares * avg_cost)
                if shares * avg_cost > 0
                else 0
            )

            price_data = all_price_data.get(
                ticker,
                {
                    "change_percent": 0,
                    "change_dollars": 0,
                    "current_price": 0
                }
            )
            chart = all_charts.get(ticker, [])

            result.append({
                "ticker": ticker,
                "strategy": strategy,
                "shares": round(shares, 2),
                "avg_cost": round(avg_cost, 2),
                "market_value": round(market_value ,2),
                "pnl": round(unrealized_pl, 2),
                "pnl_percent": round(pnl_percent * 100,2),
                "current_price": price_data["current_price"],
                "day_change_percent": price_data["change_percent"],
                "day_change_dollars": price_data["change_dollars"],
                "logo": f"https://assets.parqet.com/logos/symbol/{ticker}?format=png",
                "chart": chart
            })
    return result

def get_mini_charts(tickers):
    try:
        end = datetime.utcnow()
        start = end - timedelta(days = 3)
        request = StockBarsRequest(
            symbol_or_symbols=tickers,
            timeframe = TimeFrame(1, TimeFrameUnit.Hour),
            start = start,
            end = end,
            feed="iex"
        )
        bars = data_client.get_stock_bars(request)
        charts = {}
        for ticker in tickers:
            if ticker not in bars.data:
                charts[ticker] = []
                continue
            prices = [bar.close for bar in bars.data[ticker]]
            if not prices:
                charts[ticker] = []
                continue
            base = prices[0]
            charts[ticker] = [
                round((p/base) * 100,2)
                for p in prices
            ]
        return charts
    except Exception as e:
        print(f"CHART ERROR {ticker}: {e}")
        return {}

def get_price_change_data(symbols):
    try:
        end = datetime.utcnow()
        start = end - timedelta(days = 1)
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame(15, TimeFrameUnit.Minute),
            start=start,
            end=end,
            feed="iex"
        )
        bars = data_client.get_stock_bars(request)
        result = {}
        if isinstance(symbols, str):
            symbols = [symbols]
        for symbol in symbols:
            data = bars.data.get(symbol, [])
            prices = [b.close for b in data]
            if len(prices) < 2:
                result[symbol] = {
                    "change_percent": 0,
                    "change_dollars": 0,
                    "current_price": prices[-1] if prices else 0
                }
                continue
            first = prices[0]
            last = prices[-1]
            result[symbol] = {
                "change_percent": round(((last-first) / first) * 100,2),
                "change_dollars": round(last-first, 2),
                "current_price": round(last, 2)
            }
        return result
    except Exception as e:
        print(f"PRICE ERROR {symbol}: {e}")
        return []

def get_analytics_data():
    print("USING UPDATED ANALYTICS FUNCTION")
    strategy_map = {
        "PB": "PULLBACK_TREND",
        "MR": "MEAN_REVERSION"
    }
    reverse_strategy_map = {
        "PULLBACK_TREND": "PB",
        "MEAN_REVERSION": "MR"
    }
    equity_df = pd.read_csv(EQUITY_FILE)

    equity_df["time"] = pd.to_datetime(equity_df["time"],format="mixed",utc=True)
    equity_df = equity_df.sort_values("time")

    pivot = equity_df.pivot_table(
        index='time',
        columns='strategy',
        values='equity',
        aggfunc='last'
    )

    pivot = pivot.ffill().fillna(0)
    drawdown_data = {}
    if "MR" in pivot.columns and "PB" in pivot.columns:
        total_equity = pivot["MR"] + pivot["PB"]
    else:
        total_equity = pivot.sum(axis=1)
    running_peak = total_equity.cummax()
    drawdown = ((total_equity - running_peak) / running_peak * 100).fillna(0)
    drawdown_data["ALL"] = {
        "labels": [
            t.strftime("%Y-%m-%d %H:%M")
            for t in total_equity.index
        ],
        "values": drawdown.round(2).tolist()
    }
    for strategy in ["PB", "MR"]:
        if strategy not in pivot.columns:
            drawdown_data[strategy] = {
                "labels": [],
                "values": []
            }
            continue
        equity = pivot[strategy]
        peak = equity.cummax()
        dd = ((equity-peak) / peak * 100).fillna(0)
        drawdown_data[strategy] = {
            "labels": [
                t.strftime("%Y-%m-%d %H:%M")
                for t in equity.index
            ],
            "values": dd.round(2).tolist()
        }
    trades = get_trades_data()
    trade_durations = {
        "ALL": [],
        "PB": [],
        "MR": []
    }
    lots = {}
    for trade in trades:
        ticker = trade.get("ticker") or trade.get("symbol")
        strategy = trade.get("strategy","")
        side = str(
            trade.get("side")
            or trade.get("action")
            or ""
        ).upper()
        qty = float(trade.get("qty") or trade.get("shares") or 0)
        trade_time = pd.to_datetime(trade["time"], format="mixed",utc=True)
        key = (strategy, ticker)
        if side in ["BUY", "ADD"]:
            lots.setdefault(key, []).append({
                "qty": qty,
                "time": trade_time
            })
        elif side in [
            "SELL",
            "PARTIAL_SELL",
            "PARTIAL SELL"
        ]:
            remaining = qty
            while (
                remaining > 0
                and key in lots
                and lots[key]
            ):
                lot = lots[key][0]
                matched_qty = min(remaining, lot["qty"])
                duration_hours = (trade_time - lot["time"]).total_seconds() / 3600
                trade_durations["ALL"].append({
                    "duration": duration_hours,
                    "qty": matched_qty
                })
                short_strategy = reverse_strategy_map.get(
                    strategy, strategy
                )
                if short_strategy in trade_durations:
                    trade_durations[short_strategy].append({
                        "duration": duration_hours,
                        "qty": matched_qty
                    })

                lot["qty"] -= matched_qty
                remaining -= matched_qty
                
                if lot["qty"] <= 0:
                    lots[key].pop(0)
    trade_returns = {
        "ALL": [],
        "PB": [],
        "MR": []
    }
    for trade in trades:
        pnl = trade.get("realized_pnl")
        if pnl is None:
            continue
        pnl = float(pnl)
        trade_returns["ALL"].append(pnl)
        short_strategy = reverse_strategy_map.get(
            trade.get("strategy"),
            trade.get("strategy")
        )
        if short_strategy in trade_returns:
            trade_returns[short_strategy].append(pnl)
    strategy_map = {
        "PB": "PULLBACK_TREND",
        "MR": "MEAN_REVERSION"
    }
    strategy_stats = []
    for strategy in pivot.columns:
        print("PIVOT COLUMNS", pivot.columns.tolist())
        print("TRADE STRATEGIES:", set(t.get("strategy") for t in trades))
        trade_strategy = strategy_map.get(strategy, strategy)
        strategy_trades = [
            t for t in trades
            if t.get("strategy") == trade_strategy
            and t.get("realized_pnl") is not None
        ]
        pnls = [
            float(t["realized_pnl"])
            for t in strategy_trades
        ]
        trade_count = len(pnls)
        if trade_count > 0:
            wins = len([
                p for p in pnls
                if p > 0
            ])
            win_rate = (
                wins / trade_count * 100
            )
            avg_trade = (sum(pnls) / trade_count)
        else:
            win_rate = 0
            avg_trade = 0
        strategy_equity = pivot.get(strategy)
        if strategy_equity is not None:
            peak = strategy_equity.cummax()
            strategy_dd = (
                (strategy_equity - peak) / peak*100
            )
            max_dd = abs(strategy_dd.min())
            return_pct = (
                (
                    strategy_equity.iloc[-1] - strategy_equity.iloc[0]
                )/ strategy_equity.iloc[0] * 100
                if strategy_equity.iloc[0] != 0
                else 0
            )
        else:
            max_dd = 0
            return_pct = 0
        strategy_stats.append({
            "name": strategy,
            "return_pct": round(return_pct, 2),
            "win_rate": round(win_rate,1),
            "trades": trade_count,
            "avg_trade": round(avg_trade,2),
            "max_drawdown": round(max_dd,2)
        })
        
    duration_response = {}
    avg_duration_response = {}
    for key, values in trade_durations.items():
        duration_response[key] = [
            round(d["duration"],2)
            for d in values
        ]
        if values:
            total_qty = sum(d["qty"] for d in values)
            avg_duration_response[key] = round(
                sum(d["duration"] * d["qty"] for d in values) / total_qty,2
            )
        else:
            avg_duration_response[key] = 0
    allocation_data = get_allocation_data()
    pb_symbols = {
        pos.symbol
        for pos in pb_client.get_all_positions()
    }
    mr_symbols = {
        pos.symbol
        for pos in mr_client.get_all_positions()
    }

    allocation_response = {
        "ALL": allocation_data["allocation"],
        "PB": [
            p for p in allocation_data["allocation"]
            if p["ticker"] in pb_symbols
        ],
        "MR": [
            p for p in allocation_data["allocation"]
            if p["ticker"] in mr_symbols
        ]
    }
    return {
        "drawdown": drawdown_data,
        "trade_returns": trade_returns,
        "allocation": allocation_response,
        "trade_durations": duration_response,
        "avg_trade_duration": avg_duration_response,
        "strategy_stats": strategy_stats
    }

def get_allocation_data():
    pb_positions = pb_client.get_all_positions()
    mr_positions = mr_client.get_all_positions()

    allocation = {}
    strategy_totals = {
        "PB": 0,
        "MR": 0
    }
    for strategy, positions in [
        ("PB", pb_positions),
        ("MR", mr_positions)
    ]:
        for pos in positions:
            ticker = pos.symbol
            value = float(pos.market_value)
            strategy_totals[strategy] += value
            allocation[ticker] = (
                allocation.get(ticker, 0) + value
            )
    total_portfolio = sum(allocation.values())
    allocation_data = [
        {
            "ticker": ticker,
            "value": round(value,2),
            "percent": round(value / total_portfolio * 100, 2) if total_portfolio else 0
        }
        for ticker, value in allocation.items()
    ]
    allocation_data.sort(
        key = lambda x: x["value"],
        reverse = True
    )
    strategy_exposure = [
        {
            "strategy": strategy,
            "value": round(value,2),
            "percent": round(value / total_portfolio * 100, 2) if total_portfolio else 0
        }
        for strategy, value in strategy_totals.items()
    ]

    cash = (
        float(pb_client.get_account().cash) + float(mr_client.get_account().cash)
    )

    long_value = sum(
        value for value in allocation.values()
        if value > 0
    )

    short_value = abs(sum(
        value for value in allocation.values()
        if value < 0
    ))

    gross = long_value + short_value + cash

    exposure = {
        "long": round(long_value / gross * 100,2) if gross else 0,
        "short": round(short_value / gross * 100,2) if gross else 0,
        "cash": round(cash / gross * 100,2) if gross else 0
    }

    return {
        "allocation": allocation_data,
        "strategy_exposure": strategy_exposure,
        "total_value": round(total_portfolio, 2),
        "exposure": exposure
    }