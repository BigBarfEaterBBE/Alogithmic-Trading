from datetime import datetime, timedelta
from datetime import time as dt_time
from zoneinfo import ZoneInfo
import time
import csv
import pandas as pd
import ta

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

import confidential

MB_API_KEY = confidential.MB_API_KEY
MB_SECRET_KEY = confidential.MB_SECRET

TIMEZONE = ZoneInfo("America/New_York")

def load_watchlist():
    with open("dashboard/watchlist,csv") as f:
        return [line.strip() for line in f]
TICKERS = load_watchlist()

RISK_PERCENT = 0.03
MIN_TRADE_SIZE = 100

mb_client = TradingClient(
    api_key = MB_API_KEY,
    secret_key=MB_SECRET_KEY,
    paper=True
)
stock_data_client = StockHistoricalDataClient(MB_API_KEY,MB_SECRET_KEY,raw_data=False)

data_map = {}

partial_taken = {ticker: False for ticker in TICKERS}
scale_level = {ticker: 0 for ticker in TICKERS}

highest_price = {ticker: 0 for ticker in TICKERS}
last_trade_time = {ticker: None for ticker in TICKERS}

def now():
    return datetime.now(TIMEZONE)

def get_account_safe(client, retries=3, delay=5):
    for attempt in range(retries):
        try:
            return client.get_account()
        except Exception as e:
            print(f"Account fetch failed (attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries -1 :
                time.sleep(delay)
            else:
                raise

def get_market_status():
    current_time = now()
    current_time = current_time.time()

    open_time = dt_time(9,30)
    close_time = dt_time(16,0)

    if current_time < open_time:
        return "before_open"
    elif open_time <= current_time <= close_time:
        return "open"
    else:
        return "after_close"


def sleep_until_open():
    current_time = now()
    open_dt = current_time.replace(hour = 9, minute = 30, second = 0, microsecond=0)

    sleep_seconds = (open_dt - current_time).total_seconds()
    print(f"Market opens in {sleep_seconds/60:.1f} minutes... sleeping")
    time.sleep(max(sleep_seconds, 0))
 
def log_trade(ticker, action, price, shares, strategy, notional=None, profit=None):
    with open("dashboard/trades.csv", mode="a", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            datetime.now(),
            ticker,
            strategy,
            action,
            round(price, 4),
            round(shares, 6),
            round(notional, 2) if notional is not None else None,
            round(profit, 2) if profit is not None else None
        ])
def log_equity(client, name):
    account = get_account_safe(client)

    equity = float(account.equity)
    cash = float(account.cash)

    with open("dashboard/equity.csv", mode="a", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            datetime.now(),
            name,
            equity,
            cash
        ])

# INDICATORS
def add_indicators(df):
    df["rsi"] = ta.momentum.RSIIndicator(
        df["close"],
        window = 14
    ).rsi()
    df["atr"] = ta.volatility.AverageTrueRange(
        high = df["high"],
        low = df["low"],
        close = df["close"],
        window = 14
    ).average_true_range()
    df["high_78"] = (
        df["high"].rolling(78).max()
    )
    df["vol_avg"] = (df["volume"].rolling(20).mean())
    df["volume_ratio"] = (df["volume"] / df["vol_avg"])
    df["ma50"] = (df["close"].rolling(50).mean())
    df["breakout_signal"] = (
        (df["close"] > df["high_78"].shift(1))
        &
        (df["volume_ratio"] > 2)
        &
        (df["rsi"] > 60)
        &
        (df["close"] > df["ma50"])
    )
    return df

# DATA
def get_data(ticker):
    """
    Gets data for a stock from the past 60 days
    """
    current_time = now()

    req = StockBarsRequest(symbol_or_symbols=[ticker],
                           timeframe=TimeFrame(amount=5,unit=TimeFrameUnit.Minute), 
                           start=current_time-timedelta(days=5),
                           feed=DataFeed.IEX
    )

    bars_df = stock_data_client.get_stock_bars(req).df
    
    # Fix MultiIndex
    df= bars_df.xs(ticker)
    return df

def get_position(client, ticker):
    try:
        pos = client.get_open_position(ticker)
        return float(pos.qty), float(pos.avg_entry_price)
    except:
        return 0,0

def update_data(ticker, df):
    last_time = df.index[-1]
    current_time = now()
    req = StockBarsRequest(
        symbol_or_symbols=[ticker],
        timeframe=TimeFrame(amount=5, unit=TimeFrameUnit.Minute),
        start=last_time+timedelta(minutes=5),
        feed = DataFeed.IEX
    )

    new_bars = stock_data_client.get_stock_bars(req).df

    if new_bars.empty:
        return df
    new_df = new_bars.xs(ticker)
    # combine
    df=pd.concat([df,new_df])
    #remove dupe
    df=df[~df.index.duplicated(keep='last')]

    #recacl indicators
    df=add_indicators(df)

    df = df.tail(300) # keep last 300 candles
    return df

# TRADING

def buy_stock(client, ticker, amount):
    amount = round(amount, 2)
    if amount < MIN_TRADE_SIZE:
        print(f"Skipping {ticker}: amount too small (${amount})")
        return None
    
    try:
        order = MarketOrderRequest(symbol=ticker, notional=amount, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
        submitted_order = client.submit_order(order)
        print(f"{ticker} PB BUY at {amount}")
        return submitted_order
    except Exception as e:
        print(f"BUY FAILED for {ticker}: {e}")
        return None
    
    

def sell_stock(client,ticker):
    try:
        pos = client.get_open_position(ticker)

        order = MarketOrderRequest(symbol=ticker, qty=float(pos.qty), side=OrderSide.SELL, time_in_force=TimeInForce.DAY)
        submitted_order = client.submit_order(order)
        return submitted_order
    except Exception as e:
        print(f"SELL FAILED for {ticker}: {e}")
        return None

def sell_partial(client, ticker, fraction):
    try:
        pos = client.get_open_position(ticker)
        qty = float(pos.qty)
        
        sell_qty = round(qty * fraction, 6)

        order = MarketOrderRequest(
            symbol=ticker,
            qty=sell_qty,
            side=OrderSide.SELL,
            time_in_force = TimeInForce.DAY
        )
        submitted_order = client.submit_order(order)
        return submitted_order
    except Exception as e:
        print(f"SELL FAILED for {ticker}: {e}")
        return None

for ticker in TICKERS:
    data_map[ticker] = add_indicators(get_data(ticker))

#main trading loop
def run_breakout_strategy():
    print("Running Momentum Breakout")
    for ticker in TICKERS:
        account = mb_client.get_account()
        cash = float(account.cash)
        data_map[ticker] = update_data(
            ticker,
            data_map[ticker]
        )
        df = data_map[ticker]
        if len(df) < 50:
            continue
        row = df.iloc[-1]
        price = row["close"]
        shares, avg_entry = get_position(mb_client,ticker)
        if shares == 0 and row["breakout_signal"]:
            trade_amount = cash * RISK_PERCENT
            order = buy_stock(mb_client, ticker, trade_amount)
            if order:
                highest_price[ticker] = price
                scale_level[ticker] = 0
                partial_taken[ticker] = False
                print(f"{ticker} BREAKOUT BUY")
        elif shares > 0:
            highest_price[ticker] = max(highest_price[ticker], price)
            gain = (price - avg_entry) / avg_entry
            if gain >= 0.03 and scale_level[ticker] < 1:
                buy_stock(mb_client, ticker, cash * 0.02)
                scale_level[ticker] = 1
            elif gain >= 0.06 and scale_level[ticker] < 2:
                buy_stock(mb_client,ticker,cash*0.02)
                scale_level[ticker] = 2
            atr = row["atr"]
            trailing_stop = (highest_price[ticker] - (2*atr))
            if gain >= 0.1 and not partial_taken[ticker]:
                sell_partial(mb_client,ticker,0.5)
                partial_taken[ticker] = True
            elif price <= trailing_stop:
                profit = (price - avg_entry) * shares
                sell_stock(mb_client,ticker)
                scale_level[ticker] = 0
                partial_taken[ticker] = False
                highest_price[ticker] = 0
                print(f"{ticker} EXIT " f"Profit = {profit:.2f}")
    log_equity(mb_client, "MOMENTUM_BREAKOUT")