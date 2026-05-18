from flask import Flask, jsonify, send_from_directory
from utils import get_equity_data, get_trades_data, combine_positions

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

# MOCK ENDPOINT DATA FOR NOW
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

if __name__ == "__main__":
    app.run(debug=True)