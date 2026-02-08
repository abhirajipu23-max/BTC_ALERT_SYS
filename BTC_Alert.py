import pandas as pd
import talib
import requests
import time
from datetime import datetime, timedelta
import pytz
import os

from dotenv import load_dotenv
load_dotenv()

candle_url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=500"
BOT_TOKEN = os.getenv("BOT_TOKEN")
print(BOT_TOKEN)

CHAT_ID = os.getenv("CHAT_ID")
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

last_crossover_time = None
last_crossover_direction = None

def get_current_time_ist():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

def send_telegram_alert(message):
    requests.get(TELEGRAM_URL, params={"chat_id": CHAT_ID, "text": message})


def fetch_data():
    candle_data = requests.get(candle_url).json()
    df = pd.DataFrame(candle_data, columns=["time", "open", "high", "low", "close", "volume", "close_time",
                                            "quote_asset_volume", "num_trades", "taker_buy_base", "taker_buy_quote",
                                            "ignore"])
    df["time"] = pd.to_datetime(df["time"], unit="ms").dt.tz_localize("UTC").dt.tz_convert("Asia/Kolkata")
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
    df.set_index("time", inplace=True)
    return df


def find_rsi_ema_crossovers(df):
    df["RSI"] = talib.RSI(df["close"], timeperiod=14)
    df["RSI_EMA"] = df["RSI"].ewm(span=7, adjust=False).mean()

    crossovers = []

    for i in range(max(14, len(df) - 50), len(df) - 1):
        prev_rsi, prev_rsi_ema = df["RSI"].iloc[i - 1], df["RSI_EMA"].iloc[i - 1]
        curr_rsi, curr_rsi_ema = df["RSI"].iloc[i], df["RSI_EMA"].iloc[i]
        signal_price = df["close"].iloc[i]

        if prev_rsi < prev_rsi_ema and curr_rsi > curr_rsi_ema:
            if i + 1 < len(df):
                after_candle_price = df["high"].iloc[i + 1]
                price_difference = after_candle_price - signal_price
            else:
                price_difference = 0
            crossovers.append((df.index[i], signal_price, price_difference, "Bullish Crossover (Buy)"))

        elif prev_rsi > prev_rsi_ema and curr_rsi < curr_rsi_ema:
            if i + 1 < len(df):
                after_candle_price = df["low"].iloc[i + 1]
                price_difference = signal_price - after_candle_price
            else:
                price_difference = 0
            crossovers.append((df.index[i], signal_price, price_difference, "Bearish Crossover (Sell)"))

    return crossovers


def check_rsi_crossover(data):
    global last_crossover_time, last_crossover_direction
    crossovers = find_rsi_ema_crossovers(data)

    if not crossovers:
        return

    for crossover in crossovers:
        time_stamp, price, price_diff, direction = crossover
        # print(f"🕒 {time_stamp} | 💰 {price:.2f} | 🔄 {direction} | 🔀 Price Diff: {price_diff:.2f}")

    latest_time, latest_price, latest_price_diff, latest_direction = crossovers[-1]
    current_time = get_current_time_ist()

    if last_crossover_time and current_time < last_crossover_time + timedelta(minutes=5):
        return

    if latest_direction == last_crossover_direction:
        return

    last_crossover_time = current_time
    last_crossover_direction = latest_direction

    message = (f"**BTC TRADE Alert**\n"
               f"{latest_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
               f"Price: {latest_price:.2f}\n"
               f"Action: {latest_direction}\n"
               f"Price Diff: {latest_price_diff:.2f}")
    send_telegram_alert(message)


def run_bot():
    while True:
        try:
            check_rsi_crossover(fetch_data())
            time.sleep(10)
        except Exception as e:
            time.sleep(5)


run_bot()
