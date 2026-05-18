import pandas as pd
import os

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

def get_positions():
    df = pd.read_csv(TRADES_FILE)
    df = df.fillna("")
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
            positions[ticker] -= qty
        elif action == "PARTIAL_SELL":
            positions[ticker] -= qty
        
        # prevent negative drift
        if positions[ticker] < 0:
            positions[ticker] =0
    # convert to list
    result = [
        {"ticker": t, "shares": s}
        for t, s in positions.items() if s > 0
    ]

    return result

def get_positions_with_cost():
    df = pd.read_csv(TRADES_FILE)
    df = df.fillna("")
    positions = {}
    for _, row in df.iterrows():
        ticker = row['ticker']
        action = row['action']
        qty = float(row['qty'])
        price = float(row["price"]) if "price" in row else 0

        if ticker not in positions:
            positions[ticker[ticker]] = {
                "shares": 0,
                "cost": 0
            }
        if action in ["BUY", "ADD"]:
            positions[ticker]["cost"] += qty * price
            positions[ticker]["shares"] += qty
        elif action in ["SELL", "PARTIAL_SELL"]:
            #reduce shares only (avg-cost )
            if positions[ticker]["shares"] > 0:
