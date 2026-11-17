# Crypto AI Trader — paper-trading starter

A local Python dashboard for multi-coin crypto market monitoring and **automated paper trading**.

## What this first version does
- Pulls public OHLCV candles through CCXT (no exchange account or API key required).
- Monitors BTC/AUD, ETH/AUD, SOL/AUD and XRP/AUD where the chosen exchange lists them.
- Calculates EMA trend and RSI momentum signals.
- Runs a simple, explainable paper-trading strategy.
- Simulates fees, position sizing, stop-losses and take-profits.
- Persists the paper wallet and trade log in a local SQLite database.

## Important limitations
This is a research prototype, not a proven profitable strategy and not financial advice. It does **not** place real orders, use leverage, withdraw funds, or need private API credentials. Paper fills are simplified and may differ from real execution, spreads, slippage, liquidity and exchange rules. Do not treat backtest or paper results as evidence of future returns.

The “AI” part is deliberately not claimed yet: this first release is a transparent rule-based baseline. A later stage can compare machine-learning models against this baseline using walk-forward testing, out-of-sample data and realistic costs. ML should only be kept if it beats a simple benchmark after costs.

## Install (Python 3.10+ recommended)

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Open the local URL Streamlit prints (usually http://localhost:8501).

## Exchange choice
The default is Kraken public market data. You can switch to Binance in the sidebar. Exchange market availability and AUD pairs can change; the app checks each selected symbol and skips pairs the exchange does not list.

Kraken is a sensible first connector to test from Australia because it documents Australian operations, AUD pairs and REST/WebSocket APIs. Binance Australia also publishes API documentation and currently describes its AUSTRAC registration. Compare fees, supported AUD pairs, terms and account eligibility yourself before choosing a live venue.

## Paper-trading defaults
- Starting balance: A$500
- Maximum position size: 10% of current equity
- Maximum total invested: 50% of equity
- Stop loss: 3%
- Take profit: 6%
- Estimated round-trip costs are represented by a configurable fee per side (default 0.26%).
- Spot-only simulation; no shorting or leverage.

These are conservative software defaults for testing, not recommendations for investing.

## Strategy
- Buy: EMA 20 crosses above EMA 50 and RSI is between 50 and 70.
- Sell: EMA 20 crosses below EMA 50, or stop-loss / take-profit is hit.
- No trade if indicators are unavailable or the pair has no valid data.

This strategy is intentionally basic. It may lose money, overtrade in sideways markets, or perform poorly after fees.

## Files
- `app.py`: Streamlit dashboard and paper trading loop.
- `src/engine.py`: indicator and signal logic.
- `src/paper_broker.py`: SQLite-backed paper wallet and simulated orders.

## Next engineering milestones
1. Add proper historical backtesting with candle-by-candle fills, spread and slippage.
2. Add walk-forward validation and benchmark comparisons.
3. Add portfolio-level risk limits, circuit breakers and alerting.
4. Add an optional ML model only after a clean out-of-sample evaluation.
5. Consider a separately reviewed live-execution module only after extensive paper testing. Keep withdrawal permission disabled and use trade-only keys if live execution is ever separately approved.
