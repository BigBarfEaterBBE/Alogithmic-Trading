import pandas as pd

trades = pd.read_csv("trades.csv")

# Only completed trades
sells = trades[trades["action"] == "SELL"]

print("Total Profit:", sells["profit"].sum())
print("Win Rate:", (sells["profit"] > 0).mean())
print("Avg Profit:", sells['profit'].mean())

equity = pd.read_csv("equity.csv")
equity.plot(x="time", y="equity", title="Portfolio Growth")