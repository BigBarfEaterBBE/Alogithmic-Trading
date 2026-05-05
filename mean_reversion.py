# IMPORT LIBRARIES
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import ta

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

import csv
from datetime import datetime

# LOAD API INFO
import confidential
MR_API_KEY = confidential.MR_API_KEY
MR_SECRET_KEY = confidential.MR_SECRET
PB_API_KEY = confidential.PB_API_KEY
PB_SECRET_KEY = confidential.PB_SECRET


# INITIALIZING TRADING CLIENT
mr_client = TradingClient(api_key = MR_API_KEY, secret_key=MR_SECRET_KEY, paper=True)
pb_client = TradingClient(api_key = PB_API_KEY, secret_key=PB_SECRET_KEY, paper=True)

# INTIALIZING MARKET DATA CLIENT
stock_data_client = StockHistoricalDataClient(MR_API_KEY, MR_SECRET_KEY)


def log_trade(ticker, action, price, qty, strategy, profit=None):
    with open("trades.csv", mode="a", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            datetime.now(),
            ticker,
            strategy,
            action,
            price,
            qty,
            profit
        ])

def get_data(ticker):
    """
    Gets data for a stock from the past 60 days
    """
    now = datetime.now(ZoneInfo("America/New_York"))

    req = StockBarsRequest(symbol_or_symbols=[ticker],
                           timeframe=TimeFrame(amount=1,unit=TimeFrameUnit.Day), 
                           start=now-timedelta(days=60)
    )

    bars_df = stock_data_client.get_stock_bars(req).df
    
    # Fix MultiIndex
    df= bars_df.xs(ticker)
    return df

def add_indicators(df):
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['pct_change'] = df['close'].pct_change() * 100
    df['ma50'] = df['close'].rolling(50).mean()

    # calculate ATR ( average true range ) indicator of market volatility
    df['atr'] = ta.volatility.AverageTrueRange(
        high=df['high'],
        low=df['low'],
        close=df['close'],
        window=14
    ).average_true_range()

    # MEAN REVERSION BUY
    df['mr_signal'] = (
        ((df['pct_change'] <= -3) | (df['rsi'] < 30))
    )

    df['pb_signal'] = (
        (df['close'] > df['ma50']) # upward trend
        & (df['rsi'] < 40) # small dip
    )

    return df

def get_position(client, ticker):
    try:
        pos = client.get_open_position(ticker)
        return float(pos.qty), float(pos.avg_entry_price)
    except:
        return 0,0

def buy_stock(client, ticker, amount):
    amount = round(amount, 2)
    order = MarketOrderRequest(symbol=ticker, notional=amount, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
    client.submit_order(order)

def sell_stock(client,ticker):
    try:
        pos = client.get_open_position(ticker)

        order = MarketOrderRequest(symbol=ticker, qty=float(pos.qty), side=OrderSide.SELL, time_in_force=TimeInForce.DAY)
        client.submit_order(order)
    except:
        pass

def log_equity(client, name):
    account = client.get_account()

    equity = float(account.equity)
    cash = float(account.cash)

    with open("equity.csv", mode="a", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            datetime.now(),
            name,
            equity,
            cash
        ])

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
        client.submit_order(order)
    except:
        pass

# MAIN TRADING LOGIC
tickers = ["NVDA", "GOOGL", "SPY", "DIA", "QQQ"]
risk_percent = 0.05

mr_balance = float(mr_client.get_account().cash)
pb_balance = float(pb_client.get_account().cash)

# ADD PARTIAL TRACKING
partial_taken_mr = {ticker: False for ticker in tickers}
partial_taken_pb = {ticker: False for ticker in tickers}

# DATA
data_map = {}

for ticker in tickers:
    df = add_indicators(get_data(ticker))
    data_map[ticker] = df

# MEAN REVERSION LOOP
for ticker in tickers:
    df = data_map[ticker]

    row = df.iloc[-1] # ONLY the latest day
    current_price = row['close']

    shares, avg_entry = get_position(mr_client, ticker)

    # BUY
    if shares == 0 and row['mr_signal']:
        trade_amount = mr_balance * risk_percent
        buy_stock(mr_client, ticker, trade_amount)
        partial_taken_mr[ticker] = False
        log_trade(ticker, "BUY", current_price, trade_amount, "MEAN_REVERSION")
        print(f"{ticker} MR BUY at {current_price}")
    
    # SCALE IN
    elif shares > 0:
        drop = (current_price - avg_entry) / avg_entry

        if drop <= -0.02:
            trade_amount = mr_balance * risk_percent
            buy_stock(mr_client, ticker, trade_amount)
            log_trade(ticker, "ADD", current_price, trade_amount, "SCALE")
            print(f"{ticker} ADD at {current_price}")
    mr_balance = float(mr_client.get_account().cash)
    # SELL
    if shares > 0:
        atr = row['atr']

        # DYNAMIC STOP LOSS 
        stop_price = avg_entry - (atr*2)

        # Implementing partial profit levels
        tp1 = avg_entry * 1.02 # +2 %
        tp2 = avg_entry * 1.04 # +4 %
        
        # FULL TAKE PROFIT
        if current_price >= tp2:
            profit = (current_price - avg_entry) * shares

            sell_stock(mr_client, ticker)

            partial_taken_mr[ticker] = False

            log_trade(ticker, "SELL", current_price, shares, "MEAN_REVERSION", profit)

            print(f"{ticker} FULL SELL at {current_price} | Profit: {profit}")

        # PARTIAL TAKE PROFIT
        elif current_price >= tp1 and not partial_taken_mr[ticker]:
            sell_partial(mr_client, ticker, 0.5)

            partial_taken_mr[ticker] = True

            log_trade(ticker, "PARTIAL SELL", current_price, shares * 0.5, "MEAN_REVERSION")
            print(f"{ticker} PARTIAL SELL at {current_price}")
        
        # STOP LOSS 
        elif current_price <= stop_price:
            profit = (current_price - avg_entry) * shares

            sell_stock(mr_client, ticker)
            partial_taken_mr[ticker] = False

            log_trade(ticker, "STOP LOSS", current_price, shares, "MEAN_REVERSION", profit)

            print(f"{ticker} STOP LOSS at {current_price} | Profit: {profit}")
    mr_balance = float(mr_client.get_account().cash)
    log_equity(mr_client, "MR")

