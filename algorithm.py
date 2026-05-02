import yfinance as yf
import pandas as pd
import ta
import time


tickers = ["NVDA", "GOOGL", "SPY", "DIA", "QQQ"]

balance = 100000
risk_percent = 0.05

# Independently tracking each stock
positions = {
    ticker: {
        "shares": 0,
        "cost": 0,
    } for ticker in tickers
}

# Download stock data from past 3 months
for ticker in tickers: 
    data=yf.download(ticker, period="3mo", interval="15m")

    # Fix column data type
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    # Calculating Indicators (RSI)
    data['rsi'] = ta.momentum.RSIIndicator(data['Close'], window=14).rsi()
    data['pct_change'] = data['Close'].pct_change() * 100

    # Buy signal
    data['buy_signal'] = (data['pct_change'] <= -0.5) | (data['rsi'] < 30)

    for i in range(len(data)):
        row = data.iloc[i]
        current_price = row['Close']

        shares = positions[ticker]['shares']
        cost = positions[ticker]['cost']

        # BUY
        if row['buy_signal'] and shares == 0:
            trade_amount = balance * risk_percent
            buy_shares = trade_amount / current_price
            
            positions[ticker]['shares'] += buy_shares
            positions[ticker]['cost'] += buy_shares * current_price

            balance -= buy_shares * current_price

            print(f"{ticker} BUY at {current_price}")
        
        # SCALE IN
        elif shares > 0:
            avg_entry = cost / shares
            drop = (current_price - avg_entry) / avg_entry

            if drop <= -0.02 and balance > 0:
                trade_amount = balance * risk_percent
                buy_shares = trade_amount / current_price

                positions[ticker]['shares'] += buy_shares
                positions[ticker]['cost'] += buy_shares * current_price

                balance -= buy_shares * current_price

                print(f"{ticker} ADD at {current_price}")
        
        shares = positions[ticker]['shares']
        cost = positions[ticker]['cost']
        # SELL
        if shares > 0:
            avg_entry = cost / shares
            change = (current_price - avg_entry) / avg_entry

            if change >= 0.02 or change <= -0.3:
                balance += shares * current_price

                positions[ticker]["shares"] = 0
                positions[ticker]["cost"] = 0

                print(f"{ticker} SELL at {current_price}")
