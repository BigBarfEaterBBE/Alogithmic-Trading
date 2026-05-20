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
        ((df['pct_change'] <= -1.5) | (df['rsi'] < 30))
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
    if amount < MIN_TRADE_SIZE:
        print(f"Skipping {ticker} amount too small")
        return None
    try:
        order = MarketOrderRequest(symbol=ticker, notional=amount, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
        submitted_order = client.submit_order(order)
        print(f"BUY submitted for {ticker}")
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
        print(f"SELL FAILED for {ticker}")
        return None

def log_equity(client, name):
    account = client.get_account()

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

def sell_partial(client, ticker, fraction):
    try:
        pos = client.get_open_position(ticker)
        qty = float(pos.qty)
        
        sell_qty = round(qty * fraction, 6)

        if sell_qty <= 0:
            print(f"Skipping partial sell for {ticker}")
            return None

        order = MarketOrderRequest(
            symbol=ticker,
            qty=sell_qty,
            side=OrderSide.SELL,
            time_in_force = TimeInForce.DAY
        )
        submitted_order = client.submit_order(order)
        print(f"PARTIAL SELL submitted for {ticker}")
        return submitted_order
    except Exception as e:
        print(f"PARTIAL SELL FAILED for {ticker}: {e}")
        return None

# MAIN TRADING LOGIC
tickers = ["NVDA", "GOOGL", "SPY", "DIA", "QQQ"]
risk_percent = 0.05

mr_balance = float(mr_client.get_account().cash)
pb_balance = float(pb_client.get_account().cash)

# ADD PARTIAL TRACKING
partial_taken_mr = {ticker: False for ticker in tickers}
scale_level_mr = {ticker: 0 for ticker in tickers}
MIN_TRADE_SIZE = 100

# DATA
data_map = {}

for ticker in tickers:
    df = add_indicators(get_data(ticker))
    data_map[ticker] = df

# MEAN REVERSION LOOP
for ticker in tickers:
    mr_balance = float(mr_client.get_account().cash)
    df = data_map[ticker]

    row = df.iloc[-1] # ONLY the latest day
    current_price = row['close']

    shares, avg_entry = get_position(mr_client, ticker)

    # BUY
    if shares == 0 and row['mr_signal']:
        trade_amount = mr_balance * risk_percent
        order = buy_stock(mr_client, ticker, trade_amount)
        if order:
            scale_level_mr[ticker] = 0
            partial_taken_mr[ticker] = False
            estimated_shares = trade_amount/current_price
            log_trade(ticker, "BUY", current_price, estimated_shares, "MEAN_REVERSION", notional=trade_amount)
            print(f"{ticker} MR BUY at {current_price}")
    
    # SCALE IN
    elif shares > 0:
        drop = (current_price - avg_entry) / avg_entry

        if drop <= -0.06 and scale_level_mr[ticker] < 3:
            trade_amount = max(mr_balance * risk_percent * 2, 100)
            order = buy_stock(mr_client, ticker, trade_amount)
            if order:
                scale_level_mr[ticker] = 3
                estimated_shares = trade_amount / current_price
                log_trade(ticker, "ADD", current_price, estimated_shares, "MEAN_REVERSION", notional=trade_amount)
                print(f"{ticker} ADD at {current_price}")
        elif drop <= -0.04 and scale_level_mr[ticker] < 2:
            trade_amount = max(mr_balance * risk_percent * 1.5, 100)
            order = buy_stock(mr_client, ticker, trade_amount)
            if order:
                scale_level_mr[ticker] = 2
                estimated_shares = trade_amount / current_price
                log_trade(ticker, "ADD", current_price, estimated_shares, "MEAN_REVERSION", notional=trade_amount)
                print(f"{ticker} ADD at {current_price}")
        elif drop <= -0.02 and scale_level_mr[ticker] < 1:
            trade_amount = max(mr_balance * risk_percent, 100)
            order = buy_stock(mr_client, ticker, trade_amount)
            if order:
                scale_level_mr[ticker] = 1
                estimated_shares = trade_amount / current_price
                log_trade(ticker, "ADD", current_price, estimated_shares, "MEAN_REVERSION", notional=trade_amount)
                print(f"{ticker} ADD at {current_price}")
    mr_balance = float(mr_client.get_account().cash)
    # SELL
    if shares > 0:
        atr = row['atr']

        # DYNAMIC STOP LOSS 
        stop_price = avg_entry - (atr*2)

        # Implementing partial profit levels
        tp1 = avg_entry * 1.04 # +2 %
        tp2 = avg_entry * 1.06 # +4 %
        
        # FULL TAKE PROFIT
        if current_price >= tp2:
            sell_qty = shares
            profit = (current_price - avg_entry) * sell_qty
            notional = sell_qty * current_price

            order = sell_stock(mr_client, ticker)
            if order:
                partial_taken_mr[ticker] = False
                scale_level_mr[ticker] = 0

                log_trade(ticker, "SELL", current_price, sell_qty, "MEAN_REVERSION", notional=notional, profit=profit)

                print(f"{ticker} FULL SELL at {current_price} | Profit: {profit}")

        # PARTIAL TAKE PROFIT
        elif current_price >= tp1 and not partial_taken_mr[ticker]:
            sell_qty = shares * 0.5
            profit = (current_price - avg_entry) * sell_qty
            notional = sell_qty * current_price
            order = sell_partial(mr_client, ticker, 0.5)
            if order:
                partial_taken_mr[ticker] = True

                log_trade(ticker, "PARTIAL SELL", current_price, sell_qty, "MEAN_REVERSION", notional=notional, profit=profit)
                print(f"{ticker} PARTIAL SELL at {current_price}")
        
        # STOP LOSS 
        elif current_price <= stop_price:
            profit = (current_price - avg_entry) * shares

            order = sell_stock(mr_client, ticker)
            if order:
                scale_level_mr[ticker] = 0
                partial_taken_mr[ticker] = False

                log_trade(ticker, "STOP LOSS", current_price, shares, "MEAN_REVERSION", profit)

                print(f"{ticker} STOP LOSS at {current_price} | Profit: {profit}")
    mr_balance = float(mr_client.get_account().cash)
    log_equity(mr_client, "MR")

