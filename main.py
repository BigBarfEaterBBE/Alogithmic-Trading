import time
from datetime import datetime
from pullback import (
    run_pullback_strategy,
    get_market_status,
    sleep_until_open
)
from scanner import get_ranked_watchlist

from momentum_breakout import (
    run_breakout_strategy
)

last_pb_run = 0
last_mb_run = 0
last_mb_candle = None
last_pb_candle = None
PB_INTERVAL = 15 * 60
MB_INTERVAL = 5 * 60
while True:
    status = get_market_status()
    if status == "before_open":
        tickers = get_ranked_watchlist(10)
        with open("dashboard/watchlist.csv", "w") as f:
            for ticker in tickers:
                f.write(f"{ticker}\n")
                
        sleep_until_open()
        continue
    if status == "after_close":
        print("Market closed")
        with open("dashboard/watchlist.csv", "w") as f:
            pass
        break
    current = datetime.now()
    mb_candle = current.replace(
        minute=(current.minute // 5) * 5,
        second = 0,
        microsecond=0
    )
    pb_candle = current.replace(
        minute=(current.minute // 15) * 15,
        second = 0,
        microsecond=0
    )
    if mb_candle != last_mb_candle:
        run_breakout_strategy()
        last_mb_candle = mb_candle
    if pb_candle != last_pb_candle:
        run_pullback_strategy()
        last_pb_candle = pb_candle
    time.sleep(15)
