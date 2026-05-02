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

# LOAD API INFO
import confidential
API_KEY = confidential.ALPACA_API_KEY
SECRET_KEY = confidential.ALPACA_SECRET

# INITIALIZING TRADING CLIENT
trade_client = TradingClient(api_key = API_KEY, secret_key=SECRET_KEY, paper=True)

# INTIALIZING MARKET DATA CLIENT
stock_data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

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

    df['buy_signal'] = (df['pct_change'] <= -3) | (df['rsi'] < 30)

    return df

def get_position(ticker):
    try:
        pos = trade_client.get_open_position(ticker)
        return float(pos.qty), float(pos.avg_entry_price)
    except:
        return 0,0

def buy_stock(ticker, amount):
    order = MarketOrderRequest(symbol=ticker, notional=amount, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
    trade_client.submit_order(order)

def sell_stock(ticker):
    try:
        pos = trade_client.get_open_position(ticker)

        order = MarketOrderRequest(symbol=ticker, qty=float(pos.qty), side=OrderSide.SELL, time_in_force=TimeInForce.DAY)
        trade_client.submit_order(order)
    except:
        pass

# MAIN TRADING LOGIC
tickers = ["NVDA", "GOOGL", "SPY", "DIA", "QQQ"]
risk_percent = 0.05

account = trade_client.get_account()
balance = float(account.cash)

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
        print(f"{ticker} BUY at {current_price}")
    
    # SCALE IN
    elif shares > 0:
        drop = (current_price - avg_entry) / avg_entry

        if drop <= -0.02:
            trade_amount = balance * risk_percent
            buy_stock(ticker, trade_amount)

            print(f"{ticker} ADD at {current_price}")
    
    # SELL
    if shares > 0:
        change = (current_price - avg_entry) / avg_entry
        
        if change >= 0.04 or change <= -0.3:
            sell_stock(ticker)

            print(f"{ticker} SELL at {current_price}")
