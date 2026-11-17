from __future__ import annotations

import pandas as pd


def add_indicators(candles: pd.DataFrame) -> pd.DataFrame:
    df = candles.copy()
    df["ema_fast"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=50, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, float("nan"))
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def get_signal(df: pd.DataFrame) -> str:
    if len(df) < 55:
        return "WAIT"
    prev, last = df.iloc[-2], df.iloc[-1]
    required = ["ema_fast", "ema_slow", "rsi"]
    if any(pd.isna(last[k]) for k in required) or any(pd.isna(prev[k]) for k in required):
        return "WAIT"

    crossed_up = prev["ema_fast"] <= prev["ema_slow"] and last["ema_fast"] > last["ema_slow"]
    crossed_down = prev["ema_fast"] >= prev["ema_slow"] and last["ema_fast"] < last["ema_slow"]

    if crossed_up and 50 <= last["rsi"] <= 70:
        return "BUY"
    if crossed_down:
        return "SELL"
    return "HOLD"
