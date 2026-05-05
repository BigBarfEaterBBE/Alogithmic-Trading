# IMPORT LIBRARIES
import os
from datetime import datetime, timedelta
from datetime import time as dt_time
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

import time

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


def market_open():
    now = datetime.now(ZoneInfo("America/New_York")).time()
    return dt_time(9,30) <= now <= dt_time(16,0)

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
                           timeframe=TimeFrame(amount=5,unit=TimeFrameUnit.Minute), 
                           start=now-timedelta(days=5)
    )

    bars_df = stock_data_client.get_stock_bars(req).df
    
    # Fix MultiIndex
    df= bars_df.xs(ticker)
    return df

def add_indicators(df):
    df['pct_change'] = df['close'].pct_change() * 100

    # calculate ATR ( average true range ) indicator of market volatility
    df['atr'] = ta.volatility.AverageTrueRange(
        high=df['high'],
        low=df['low'],
        close=df['close'],
        window=14
    ).average_true_range()

    df['vwap'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
    df['vwap_dev'] = (df['close'] - df['vwap']) / df['vwap']

    df['drop_3'] = df['close'].pct_change(3)

    df['vol_avg'] = df['volume'].rolling(20).mean()
    df['vol_spike'] = df['volume'] > df['vol_avg'] * 1.5

    df['pb_signal'] = (
        ((df['drop_3'] <= -0.015) # large drop (-1.5% in 15 min candle)
        | (df['vwap_dev'] <= -0.01)
        | (df['pct_change'] <= -1.5) )
        & df['vol_spike'] # shows increase in volume -> panic selling
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


# ADD PARTIAL TRACKING
partial_taken_mr = {ticker: False for ticker in tickers}
partial_taken_pb = {ticker: False for ticker in tickers}

# PREVENT DUPE TRADES ON SAME CANDLE
last_trade_time = {ticker: None for ticker in tickers}

# DATA
data_map = {}
for ticker in tickers:
    df = add_indicators(get_data(ticker))
    data_map[ticker] = df
    df = data_map[ticker]

def update_data(ticker, df):
    last_time = df.index[-1]
    now = datetime.now(ZoneInfo("America/New_York"))
    req = StockBarsRequest(
        symbol_or_symbols=[ticker],
        timeframe=TimeFrame(amount=5, unit=TimeFrameUnit.Minute),
        start=last_time+timedelta(minutes=5)
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


while True:
    if not market_open():
        time.sleep(300)
        continue
    else:
        mr_balance = float(mr_client.get_account().cash)
        pb_balance = float(pb_client.get_account().cash)

        for ticker in tickers:
            data_map[ticker] = update_data(ticker, data_map[ticker])
            df = data_map[ticker]
            current_time = df.index[-1]

            if last_trade_time[ticker] == current_time:
                continue
            if len(df) < 30:
                print("not enough data")
                continue

            row = df.iloc[-1]
            price = row['close']

            shares, avg_entry = get_position(pb_client, ticker)
            pb_balance = float(pb_client.get_account().cash)

            # BUY
            if shares == 0 and row['pb_signal']:
                trade_amount = pb_balance * risk_percent
                buy_stock(pb_client, ticker, trade_amount)
                shares, avg_entry = get_position(pb_client, ticker)
                last_trade_time[ticker] = current_time
                partial_taken_pb[ticker] = False
                log_trade(ticker, "BUY", price, trade_amount, "PULLBACK_TREND")
                print(f"{ticker} PB BUY at {price}")
            
            # SCALE
            elif shares > 0:
                drop = (price- avg_entry) / avg_entry
                if drop <= -0.06:
                    trade_amount = pb_balance * risk_percent * 2
                    buy_stock(pb_client, ticker, trade_amount)
                    last_trade_time[ticker] = current_time
                    shares, avg_entry = get_position(pb_client, ticker)
                    log_trade(ticker, "ADD", price, trade_amount, "PULLBACK_TREND")
                elif drop <= -0.04:
                    trade_amount = pb_balance * risk_percent * 1.5
                    buy_stock(pb_client, ticker, trade_amount)
                    last_trade_time[ticker] = current_time
                    shares, avg_entry = get_position(pb_client, ticker)
                    log_trade(ticker, "ADD", price, trade_amount, "PULLBACK_TREND")
                elif drop <= -0.02:
                    trade_amount = pb_balance * risk_percent
                    buy_stock(pb_client, ticker, trade_amount)
                    last_trade_time[ticker] = current_time
                    shares, avg_entry = get_position(pb_client, ticker)
                    log_trade(ticker, "ADD", price, trade_amount, "PULLBACK_TREND")
            pb_balance = float(pb_client.get_account().cash)
            # SELL
            if shares > 0:
                atr = row['atr']
                tp1 = avg_entry * 1.02
                tp2 = avg_entry * 1.04

                if price >= tp2:
                    profit = (price - avg_entry) * shares
                    sell_stock(pb_client, ticker)
                    shares, avg_entry = get_position(pb_client, ticker)
                    log_trade(ticker, "SELL", price, shares, "PULLBACK_TREND", profit)

                elif price >= tp1 and not partial_taken_pb[ticker]:
                    sell_partial(pb_client, ticker, 0.5)
                    shares, avg_entry = get_position(pb_client, ticker)
                    partial_taken_pb[ticker] = True
                    log_trade(ticker, "PARTIAL SELL", price, shares * 0.5, "PULLBACK_TREND")
        print("Sleeping...")
        time.sleep(120) # 2 minutes