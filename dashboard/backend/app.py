from flask import Flask, jsonify, send_from_directory
from utils import get_equity_data, get_trades_data, get_positions

app = Flask(__name__, static_folder="../frontend")

@app.route("/api/equity")
def equity():
    return jsonify(get_equity_data())

@app.route("/api/trades")
def trades():
    return jsonify(get_trades_data())

@app.route("/api/positions")
def positions():
    return jsonify(get_positions())

@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)

if __name__ == "__main__":
    app.run(debug=True)