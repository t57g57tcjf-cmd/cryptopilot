from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone


class PaperBroker:
    def __init__(self, db_path: str = "paper_trader.sqlite3", starting_aud: float = 500.0):
        self.db_path = str(Path(db_path))
        self.starting_aud = float(starting_aud)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY CHECK (id=1),
                cash REAL NOT NULL
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                quantity REAL NOT NULL,
                entry_price REAL NOT NULL,
                stop_price REAL NOT NULL,
                take_price REAL NOT NULL
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                fee REAL NOT NULL,
                note TEXT NOT NULL
            )""")
            con.execute("INSERT OR IGNORE INTO account(id, cash) VALUES(1, ?)", (self.starting_aud,))

    def cash(self) -> float:
        with self._connect() as con:
            return float(con.execute("SELECT cash FROM account WHERE id=1").fetchone()[0])

    def positions(self) -> dict:
        with self._connect() as con:
            rows = con.execute("SELECT symbol, quantity, entry_price, stop_price, take_price FROM positions").fetchall()
        return {r[0]: {"quantity": r[1], "entry": r[2], "stop": r[3], "take": r[4]} for r in rows}

    def trades(self, limit: int = 100):
        with self._connect() as con:
            return con.execute(
                "SELECT timestamp, symbol, side, quantity, price, fee, note FROM trades ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()

    def equity(self, prices: dict) -> float:
        pos = self.positions()
        return self.cash() + sum(p["quantity"] * prices.get(s, p["entry"]) for s, p in pos.items())

    def buy(self, symbol: str, price: float, allocation: float, fee_rate: float,
            stop_pct: float, take_pct: float, max_total_exposure: float, prices: dict):
        if price <= 0 or not 0 < allocation <= 1:
            return False, "Invalid price or allocation."
        pos = self.positions()
        if symbol in pos:
            return False, "Already holding this pair."
        equity = self.equity(prices)
        invested = sum(p["quantity"] * prices.get(s, p["entry"]) for s, p in pos.items())
        budget = min(self.cash(), equity * allocation, max(0.0, equity * max_total_exposure - invested))
        if budget <= 1:
            return False, "Insufficient available paper cash or exposure limit reached."
        fee = budget * fee_rate
        quantity = (budget - fee) / price
        if quantity <= 0:
            return False, "Order size too small."
        with self._connect() as con:
            cash = float(con.execute("SELECT cash FROM account WHERE id=1").fetchone()[0])
            con.execute("UPDATE account SET cash=? WHERE id=1", (cash - budget,))
            con.execute(
                "INSERT INTO positions VALUES(?,?,?,?,?)",
                (symbol, quantity, price, price * (1 - stop_pct), price * (1 + take_pct))
            )
            con.execute(
                "INSERT INTO trades(timestamp,symbol,side,quantity,price,fee,note) VALUES(?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), symbol, "BUY", quantity, price, fee, "EMA/RSI entry")
            )
        return True, f"Paper BUY filled: {symbol}"

    def sell(self, symbol: str, price: float, fee_rate: float, note: str = "Signal exit"):
        pos = self.positions()
        if symbol not in pos or price <= 0:
            return False, "No open position or invalid price."
        p = pos[symbol]
        gross = p["quantity"] * price
        fee = gross * fee_rate
        proceeds = gross - fee
        with self._connect() as con:
            cash = float(con.execute("SELECT cash FROM account WHERE id=1").fetchone()[0])
            con.execute("UPDATE account SET cash=? WHERE id=1", (cash + proceeds,))
            con.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
            con.execute(
                "INSERT INTO trades(timestamp,symbol,side,quantity,price,fee,note) VALUES(?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), symbol, "SELL", p["quantity"], price, fee, note)
            )
        return True, f"Paper SELL filled: {symbol}"
