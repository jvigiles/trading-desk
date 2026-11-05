"""Market data access (yfinance). Daily bars for trend/ATR, 5-minute bars for futures sessions."""
import json
import os
import time
import pandas as pd
import numpy as np
import yfinance as yf

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _flat(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.rename(columns=str.title)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])


def daily(symbol: str, period: str = "6y") -> pd.DataFrame:
    for attempt in range(3):
        try:
            df = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=True)
            if len(df):
                df = _flat(df)
                df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
                return df
        except Exception as e:  # pragma: no cover
            time.sleep(2 * (attempt + 1))
    return pd.DataFrame()


def intraday_5m(symbol: str, period: str = "60d") -> pd.DataFrame:
    """5-minute bars, index in US/Eastern."""
    for attempt in range(3):
        try:
            df = yf.Ticker(symbol).history(period=period, interval="5m", auto_adjust=True)
            if len(df):
                df = _flat(df)
                df.index = pd.to_datetime(df.index).tz_convert("America/New_York")
                return df
        except Exception:
            time.sleep(2 * (attempt + 1))
    return pd.DataFrame()


def daily_many(symbols, period="6y"):
    out = {}
    for s in symbols:
        d = daily(s, period)
        if len(d) > 250:
            out[s] = d
    return out


def eurusd() -> float:
    d = daily("EURUSD=X", "1mo")
    return float(d["Close"].iloc[-1]) if len(d) else 1.08


def vix_level() -> float:
    d = daily("^VIX", "1mo")
    return float(d["Close"].iloc[-1]) if len(d) else 20.0


# ------------------------------------------------------------------ indicators
def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def rsi(series: pd.Series, n: int = 2) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0).rolling(n).mean()
    down = (-delta.clip(upper=0)).rolling(n).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def rth_sessions(df5: pd.DataFrame):
    """Split 5m bars into regular-trading-hours sessions keyed by ET date."""
    rth = df5.between_time("09:30", "15:59")
    return {d: g for d, g in rth.groupby(rth.index.date)}
