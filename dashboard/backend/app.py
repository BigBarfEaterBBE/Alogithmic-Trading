from flask import Flask, jsonify, send_from_directory
from utils import get_equity_data, get_trades_data, combine_positions, get_analytics_data, get_allocation_data, get_kpis, get_portfolio_monitor

from alpaca.trading.client import TradingClient

import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
sys.path.append(PROJECT_ROOT)

import confidential
PB_API_KEY = confidential.PB_API_KEY
PB_SECRET_KEY = confidential.PB_SECRET
MR_API_KEY = confidential.MR_API_KEY
MR_SECRET_KEY = confidential.MR_SECRET

pb_client = TradingClient(
    PB_API_KEY,
    PB_SECRET_KEY,
    paper=True
)

mr_client = TradingClient(
    MR_API_KEY,
    MR_SECRET_KEY,
    paper=True
)

app = Flask(__name__, static_folder="../frontend")

@app.route("/api/equity")
def equity():
    return jsonify(get_equity_data())

@app.route("/api/trades")
def trades():
    return jsonify(get_trades_data())

@app.route("/api/positions")
def positions():
    pb_positions = pb_client.get_all_positions()
    mr_positions = mr_client.get_all_positions()
    return jsonify(combine_positions(pb_positions, mr_positions))


@app.route("/api/prices")
def prices():
    pb_positions = pb_client.get_all_positions()
    mr_positions = mr_client.get_all_positions()

    return jsonify(
        combine_positions(
            pb_positions, mr_positions
        )
    )

@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)

@app.route("/api/analytics")
def analytics():
    return jsonify(get_analytics_data())

@app.route("/api/kpis")
def kpis():
    return jsonify(get_kpis())

@app.route("/api/portfolio-monitor")
def portfolio_monitor():
    return jsonify(get_portfolio_monitor())

@app.route("/api/ticker-bar")
def ticker_bar():
    pb_positions = pb_client.get_all_positions()
    mr_positions = mr_client.get_all_positions()
    positions = combine_positions(pb_positions, mr_positions)
    merged = {}
    for pos in positions:
        ticker = pos["ticker"]
        if ticker not in merged:
            merged[ticker] = {
                "ticker": ticker,
                "shares": 0,
                "market_value": 0,
                "pnl": 0,
                "cost_basis": 0,
                "weighted_day_change": 0,
                "day_change_dollars": 0,
                "chart": pos["chart"],
                "logo": pos["logo"]
            }

        shares = float(pos["shares"])
        avg_cost = float(pos["avg_cost"])
        merged[ticker]["shares"] += shares
        merged[ticker]["market_value"] += float(pos["market_value"])
        merged[ticker]["pnl"] += float(pos["pnl"])
        merged[ticker]["cost_basis"] += avg_cost * shares
        merged[ticker]["weighted_day_change"] += (float(pos["day_change_percent"]) * float(pos["market_value"]))
        merged[ticker]["day_change_dollars"] += float(
            pos["day_change_dollars"]
        )
    result = []
    for ticker, pos in merged.items():
        pnl_percent = (pos["pnl"] / pos["cost_basis"] * 100 if pos["cost_basis"] > 0 else 0)
        day_change_percent = (
            pos["weighted_day_change"] / pos["market_value"] if pos["market_value"] > 0 else 0
        )
        result.append({
            **pos, "pnl_percent": round(pnl_percent,2), "day_change_percent": round(day_change_percent,2)
        })
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)

