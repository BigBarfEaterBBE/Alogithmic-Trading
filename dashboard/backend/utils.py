import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EQUITY_FILE = os.path.join(BASE_DIR, "equity.csv")
TRADES_FILE = os.path.join(BASE_DIR, "trades.csv")

def get_equity_data():
    df = pd.read_csv(EQUITY_FILE)
    # keep only necessary columns (for now)
    df = df[["time", "equity"]]
    #remove duplicates
    df = df.drop_duplicates(subset=["time"])

    return df.to_dict(orient="records")

def get_trades_data():
    df = pd.read_csv(TRADES_FILE)

    df = df.fillna("")

    return df.to_dict(orient="records")

def get_positions():
    df = pd.read_csv(TRADES_FILE)
    positions = {}
    for _, row in df.iterrows():
        ticker = row['ticker']
        action = row['action']
        qty = float(row['qty'])

        if ticker not in positions:
            positions[ticker] = 0
        
        if action in ['BUY', 'ADD']:
            positions[ticker] += qty
        elif action == "SELL":
            positions[ticker] = 0
        elif action == "PARTIAL_SELL":
            positions[ticker] -= qty
    # convert to list
    result = [
        {"ticker": t, "shares": s}
        for t, s in positions.items() if s > 0
    ]

    return result
