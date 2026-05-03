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
API_KEY = confidential.ALPACA_API_KEY
SECRET_KEY = confidential.ALPACA_SECRET

# INITIALIZING TRADING CLIENT
trade_client = TradingClient(api_key = API_KEY, secret_key=SECRET_KEY, paper=True)

# INTIALIZING MARKET DATA CLIENT
stock_data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)


def log_trade(ticker, action, price, qty, profit=None):
    with open("trades.csv", mode="a", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            datetime.now(),
            ticker,
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

    df['buy_signal'] = ((df['pct_change'] <= -3) | (df['rsi'] < 30)) & (df['close'] > df['ma50'])

    return df

def get_position(ticker):
    try:
        pos = trade_client.get_open_position(ticker)
        return float(pos.qty), float(pos.avg_entry_price)
    except:
        return 0,0

def buy_stock(ticker, amount):
    amount = round(amount, 2)
    order = MarketOrderRequest(symbol=ticker, notional=amount, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
    trade_client.submit_order(order)

def sell_stock(ticker):
    try:
        pos = trade_client.get_open_position(ticker)

        order = MarketOrderRequest(symbol=ticker, qty=float(pos.qty), side=OrderSide.SELL, time_in_force=TimeInForce.DAY)
        trade_client.submit_order(order)
    except:
        pass

def log_equity():
    account = trade_client.get_account()

    equity = float(account.equity)
    cash = float(account.cash)

    with open("equity.csv", mode="a", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            datetime.now(),
            equity,
            cash
        ])

def sell_partial(ticker, fraction):
    try:
        pos = trade_client.get_open_position(ticker)
        qty = float(pos.qty)
        
        sell_qty = round(qty * fraction, 6)

        order = MarketOrderRequest(
            symbol=ticker,
            qty=sell_qty,
            side=OrderSide.SELL,
            time_in_force = TimeInForce.DAY
        )
        trade_client.submit_order(order)
    except:
        pass

# MAIN TRADING LOGIC
tickers = ["NVDA", "GOOGL", "SPY", "DIA", "QQQ"]
risk_percent = 0.05

account = trade_client.get_account()
balance = float(account.cash)

# ADD PARTIAL TRACKING
partial_taken = {ticker: False for ticker in tickers}

for ticker in tickers:
    df = get_data(ticker)
    df = add_indicators(df)

    row = df.iloc[-1] # ONLY the latest day
    current_price = row['close']

    shares, avg_entry = get_position(ticker)

    # BUY
    if row['buy_signal'] and shares == 0:
        trade_amount = balance * risk_percent
        buy_stock(ticker, trade_amount)
        partial_taken[ticker] = False
        log_trade(ticker, "BUY", current_price, trade_amount)
        print(f"{ticker} BUY at {current_price}")
    
    # SCALE IN
    elif shares > 0:
        drop = (current_price - avg_entry) / avg_entry

        if drop <= -0.02:
            trade_amount = balance * risk_percent
            buy_stock(ticker, trade_amount)
            log_trade(ticker, "ADD", current_price, trade_amount)
            print(f"{ticker} ADD at {current_price}")
    
    # SELL
    if shares > 0:
        atr = row['atr']

        # DYNAMIC STOP LOSS 
        stop_price = avg_entry - (atr*2)

        # Implementing partial profit levels
        tp1 = avg_entry * 1.02 # +2 %
        tp2 = avg_entry * 1.04 # +4 %

        # PARTIAL TAKE PROFIT
        if current_price >= tp1 and not partial_taken[ticker]:
            sell_partial(ticker, 0.5)

            partial_taken[ticker] = True

            log_trade(ticker, "PARTIAL SELL", current_price, shares * 0.5)
            print(f"{ticker} PARTIAL SELL at {current_price}")
        
        # FULL TAKE PROFIT
        elif current_price >= tp2:
            profit = (current_price - avg_entry) * shares

            sell_stock(ticker)

            partial_taken[ticker] = False

            log_trade(ticker, "SELL", current_price, shares, profit)

            print(f"{ticker} FULL SELL at {current_price} | Profit: {profit}")
        
        # STOP LOSS 
        elif current_price <= stop_price:
            profit = (current_price - avg_entry) * shares

            sell_stock(ticker)
            partial_taken[ticker] = False

            log_trade(ticker, "STOP LOSS", current_price, shares, profit)

            print(f"{ticker} STOP LOSS at {current_price} | Profit: {profit}")
    account = trade_client.get_account()
    balance = float(account.cash)
    log_equity()
