from __future__ import annotations

import time
import ccxt
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src.engine import add_indicators, get_signal
from src.paper_broker import PaperBroker


st.set_page_config(page_title="Crypto AI Trader — Paper", page_icon="📈", layout="wide")
st.title("📈 Crypto AI Trader")
st.caption("Multi-coin market monitor · automated PAPER trading only · no private API keys")

with st.sidebar:
    st.header("Settings")
    exchange_id = st.selectbox("Public market-data exchange", ["kraken", "binance"], index=0)
    timeframe = st.selectbox("Candle timeframe", ["15m", "1h", "4h", "1d"], index=1)
    refresh_seconds = st.select_slider("Refresh interval (seconds)", options=[30, 60, 120, 300], value=60)
    st.divider()
    st.subheader("Paper risk controls")
    starting_aud = st.number_input("Starting paper balance (A$)", min_value=50.0, max_value=5000.0, value=500.0, step=50.0)
    allocation_pct = st.slider("Max allocation per position (%)", 2, 20, 10) / 100
    exposure_pct = st.slider("Max total invested (%)", 10, 80, 50) / 100
    stop_pct = st.slider("Stop loss (%)", 1, 10, 3) / 100
    take_pct = st.slider("Take profit (%)", 2, 20, 6) / 100
    fee_pct = st.number_input("Estimated fee per side (%)", min_value=0.0, max_value=2.0, value=0.26, step=0.01) / 100
    auto_paper = st.toggle("Enable automatic paper trading", value=False)
    st.caption("No real orders can be placed by this version.")

st_autorefresh(interval=refresh_seconds * 1000, key="market_refresh")

broker = PaperBroker(starting_aud=starting_aud)

@st.cache_resource
def make_exchange(exchange_name: str):
    klass = getattr(ccxt, exchange_name)
    return klass({"enableRateLimit": True, "timeout": 20000})

@st.cache_data(ttl=45, show_spinner=False)
def fetch_candles(exchange_name: str, symbol: str, tf: str):
    ex = make_exchange(exchange_name)
    rows = ex.fetch_ohlcv(symbol, timeframe=tf, limit=150)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df

@st.cache_data(ttl=300, show_spinner=False)
def available_symbols(exchange_name: str):
    ex = make_exchange(exchange_name)
    markets = ex.load_markets()
    wanted = ["BTC/AUD", "ETH/AUD", "SOL/AUD", "XRP/AUD"]
    return [s for s in wanted if s in markets and markets[s].get("spot", False)]

try:
    symbols = available_symbols(exchange_id)
except Exception as exc:
    st.error(f"Could not load exchange markets: {exc}")
    st.stop()

if not symbols:
    st.warning("The selected exchange did not return any of the configured AUD spot pairs. Try the other exchange.")
    st.stop()

market_rows = []
latest_prices = {}
frames = {}
signals = {}

with st.spinner("Fetching public market candles..."):
    for symbol in symbols:
        try:
            raw = fetch_candles(exchange_id, symbol, timeframe)
            if raw.empty:
                continue
            # Exclude the newest candle because it may still be forming.
            raw = raw.iloc[:-1].copy()
            if raw.empty:
                continue
            df = add_indicators(raw)
            frames[symbol] = df
            price = float(df.iloc[-1]["close"])
            latest_prices[symbol] = price
            signals[symbol] = get_signal(df)
            market_rows.append({
                "Pair": symbol,
                "Last price (AUD)": price,
                "RSI": round(float(df.iloc[-1]["rsi"]), 1) if pd.notna(df.iloc[-1]["rsi"]) else None,
                "EMA 20": round(float(df.iloc[-1]["ema_fast"]), 4),
                "EMA 50": round(float(df.iloc[-1]["ema_slow"]), 4),
                "Signal": signals[symbol],
                "Candle time (UTC)": str(df.iloc[-1]["timestamp"])
            })
        except Exception as exc:
            st.warning(f"{symbol}: data unavailable ({exc})")

if not latest_prices:
    st.error("No candle data was returned. Check your connection or try another exchange/timeframe.")
    st.stop()

# Automated simulated exits first, then entries. Each candle timestamp is processed once per pair.
if auto_paper:
    if "processed_candles" not in st.session_state:
        st.session_state.processed_candles = {}
    for symbol, df in frames.items():
        candle_key = str(df.iloc[-1]["timestamp"])
        if st.session_state.processed_candles.get(symbol) == candle_key:
            continue
        price = latest_prices[symbol]
        position = broker.positions().get(symbol)
        if position:
            if price <= position["stop"]:
                broker.sell(symbol, price, fee_pct, "Simulated stop loss")
            elif price >= position["take"]:
                broker.sell(symbol, price, fee_pct, "Simulated take profit")
            elif signals[symbol] == "SELL":
                broker.sell(symbol, price, fee_pct, "EMA trend exit")
        elif signals[symbol] == "BUY":
            broker.buy(symbol, price, allocation_pct, fee_pct, stop_pct, take_pct, exposure_pct, latest_prices)
        st.session_state.processed_candles[symbol] = candle_key

positions = broker.positions()
cash = broker.cash()
equity = broker.equity(latest_prices)
invested = sum(p["quantity"] * latest_prices.get(s, p["entry"]) for s, p in positions.items())
unrealised = sum(p["quantity"] * (latest_prices.get(s, p["entry"]) - p["entry"]) for s, p in positions.items())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Paper equity", f"A${equity:,.2f}", f"{equity-starting_aud:+,.2f} vs initial")
c2.metric("Available cash", f"A${cash:,.2f}")
c3.metric("Invested", f"A${invested:,.2f}")
c4.metric("Unrealised P/L", f"A${unrealised:+,.2f}")

st.subheader("Market signals")
if market_rows:
    st.dataframe(pd.DataFrame(market_rows), use_container_width=True, hide_index=True)

st.subheader("Open paper positions")
if positions:
    pos_rows = []
    for symbol, p in positions.items():
        px = latest_prices.get(symbol, p["entry"])
        pos_rows.append({
            "Pair": symbol, "Quantity": p["quantity"], "Entry (AUD)": p["entry"],
            "Last (AUD)": px, "P/L (AUD)": p["quantity"] * (px-p["entry"]),
            "Stop": p["stop"], "Take profit": p["take"]
        })
    st.dataframe(pd.DataFrame(pos_rows), use_container_width=True, hide_index=True)
else:
    st.info("No open paper positions.")

st.subheader("Recent simulated trades")
trade_rows = broker.trades(50)
if trade_rows:
    trades_df = pd.DataFrame(trade_rows, columns=["Time (UTC)", "Pair", "Side", "Quantity", "Price", "Fee", "Note"])
    st.dataframe(trades_df, use_container_width=True, hide_index=True)
else:
    st.info("No paper trades yet. Enable automatic paper trading to let the strategy simulate entries and exits.")

st.caption("Signals are based on the latest candle, which may still be forming. Automated actions are simulated only. This app is a prototype; refresh timing, data gaps, fees, spreads and fills can affect results.")
st.button("Refresh now")
time.sleep(0.1)
st.caption(f"Dashboard refresh interval: {refresh_seconds}s. Exchange: {exchange_id}.")
