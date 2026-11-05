"""Setup definitions: signal generation for today and historical simulation for calibration.

All setups are explicit rules. A candidate is a dict with entry/stop/target levels; the risk
engine (risk.py) decides size and whether it can be issued at all.
"""
from datetime import date, timedelta
import numpy as np
import pandas as pd

from config import SETUPS, FUTURES, FUT_TRIGGER_LAST, FUT_FLAT_BY
from data import atr, rsi, rth_sessions


# ====================================================================== SWING
def swing_features(df: pd.DataFrame) -> pd.DataFrame:
    f = df.copy()
    f["sma50"] = f["Close"].rolling(50).mean()
    f["sma200"] = f["Close"].rolling(200).mean()
    f["sma20"] = f["Close"].rolling(20).mean()
    f["atr14"] = atr(f, 14)
    f["rsi2"] = rsi(f["Close"], 2)
    f["hi20"] = f["High"].rolling(20).max()
    f["vol20"] = f["Volume"].rolling(20).mean()
    f["ret5"] = f["Close"].pct_change(5)
    return f


def swing_signal(setup_id: str, row: pd.Series, prev_hi20: float):
    """Return candidate levels for a signal on the bar `row` (evaluated at its close) or None."""
    p = SETUPS[setup_id]
    c, a = row["Close"], row["atr14"]
    if not np.isfinite(a) or a <= 0:
        return None
    if setup_id == "SWING_PULLBACK":
        if row["Close"] > row["sma50"] > row["sma200"] and row["rsi2"] < p["rsi_max"]:
            entry = round(float(c), 2)
            return {"side": "long", "entry_type": "limit", "entry": entry,
                    "stop": round(entry - p["stop_atr"] * a, 2),
                    "target": round(entry + p["target_atr"] * a, 2),
                    "horizon_days": p["horizon_days"], "trigger_days": 1}
    if setup_id in ("SWING_BREAKOUT", "SWING_BREAKOUT_RUNNER"):
        if (row["Close"] >= prev_hi20 and row["Volume"] >= p["vol_mult"] * row["vol20"]
                and row["Close"] > row["sma50"]):
            entry = round(float(row["High"] + 0.1 * a), 2)
            return {"side": "long", "entry_type": "stop", "entry": entry,
                    "stop": round(entry - p["stop_atr"] * a, 2),
                    "target": round(entry + p["target_atr"] * a, 2),
                    "horizon_days": p["horizon_days"], "trigger_days": 2}
    return None


def simulate_swing(df: pd.DataFrame, i: int, cand: dict):
    """Simulate a swing candidate signalled at bar i using subsequent daily bars.
    Returns dict(status, r, days, exit_price) with r BEFORE costs, or None if data insufficient."""
    n = len(df)
    entry, stop, target = cand["entry"], cand["stop"], cand["target"]
    risk = entry - stop
    j = i + 1
    fill = None
    fill_idx = None
    while j < n and j <= i + cand["trigger_days"]:
        o, h, l = df["Open"].iloc[j], df["High"].iloc[j], df["Low"].iloc[j]
        if cand["entry_type"] == "limit" and l <= entry:
            fill = min(o, entry); fill_idx = j; break
        if cand["entry_type"] == "stop" and h >= entry:
            if o > entry + 0.5 * risk:   # gapped through the level: order must be cancelled
                return {"status": "gap_cancelled", "r": 0.0, "days": 0, "exit_price": None, "fill": None}
            fill = max(o, entry); fill_idx = j; break
        j += 1
    if fill is None:
        if j >= n:
            return None
        return {"status": "not_triggered", "r": 0.0, "days": 0, "exit_price": None, "fill": None}
    last = fill_idx + cand["horizon_days"] - 1
    if last >= n:
        return None
    for k in range(fill_idx, last + 1):
        h, l = df["High"].iloc[k], df["Low"].iloc[k]
        if l <= stop:
            return {"status": "stopped", "r": (stop - fill) / risk, "days": k - fill_idx + 1,
                    "exit_price": stop, "fill": fill}
        if h >= target:
            return {"status": "target", "r": (target - fill) / risk, "days": k - fill_idx + 1,
                    "exit_price": target, "fill": fill}
    c = df["Close"].iloc[last]
    return {"status": "expired", "r": (c - fill) / risk, "days": cand["horizon_days"],
            "exit_price": float(c), "fill": fill}


def backtest_swing(setup_id: str, daily_data: dict, vix_daily: pd.Series | None = None):
    """Historical simulation across the universe. Returns list of outcome dicts."""
    out = []
    for sym, df in daily_data.items():
        f = swing_features(df)
        for i in range(210, len(f) - 1):
            row = f.iloc[i]
            prev_hi20 = f["hi20"].iloc[i - 1]
            cand = swing_signal(setup_id, row, prev_hi20)
            if not cand:
                continue
            res = simulate_swing(df, i, cand)
            if res is None:
                continue
            vix = float(vix_daily.asof(f.index[i])) if vix_daily is not None else np.nan
            out.append({"symbol": sym, "date": str(f.index[i].date()), "vix": vix, **cand, **res})
    return out


# ====================================================================== FUTURES DAY
def futures_levels(df5: pd.DataFrame, dfd: pd.DataFrame, for_day: date, spec: dict):
    """Levels for a session `for_day`, using the last completed RTH session before it."""
    sessions = rth_sessions(df5)
    prior_days = sorted(d for d in sessions if d < for_day)
    if len(prior_days) < SETUPS["FUT_PDR_BREAKOUT"]["range_lookback"] + 1:
        return None
    prev = sessions[prior_days[-1]]
    pdh, pdl = float(prev["High"].max()), float(prev["Low"].min())
    ranges = [float(sessions[d]["High"].max() - sessions[d]["Low"].min())
              for d in prior_days[-SETUPS["FUT_PDR_BREAKOUT"]["range_lookback"]:]]
    avg_range = float(np.mean(ranges))
    dclose = dfd["Close"]
    dd = dclose[dclose.index < pd.Timestamp(for_day)]
    if len(dd) < 25:
        return None
    sma20 = float(dd.rolling(20).mean().iloc[-1])
    last_close = float(dd.iloc[-1])
    trend = "up" if last_close > sma20 else "down"
    return {"pdh": pdh, "pdl": pdl, "avg_range": avg_range, "sma20": sma20,
            "last_close": last_close, "trend": trend, "prev_session": str(prior_days[-1])}


def futures_candidate(levels: dict, spec: dict):
    p = SETUPS["FUT_PDR_BREAKOUT"]
    tick = spec["tick"]
    stop_d = max(round(p["stop_frac"] * levels["avg_range"] / tick) * tick, 4 * tick)
    tgt_d = max(round(p["target_frac"] * levels["avg_range"] / tick) * tick, 8 * tick)
    if levels["trend"] == "up":
        entry = levels["pdh"] + 2 * tick
        return {"side": "long", "entry_type": "stop", "entry": round(entry, 2),
                "stop": round(entry - stop_d, 2), "target": round(entry + tgt_d, 2)}
    entry = levels["pdl"] - 2 * tick
    return {"side": "short", "entry_type": "stop", "entry": round(entry, 2),
            "stop": round(entry + stop_d, 2), "target": round(entry - tgt_d, 2)}


def simulate_futures_session(session: pd.DataFrame, cand: dict):
    """Simulate a day card on one RTH session of 5m bars. r BEFORE costs."""
    side = cand["side"]; entry, stop, target = cand["entry"], cand["stop"], cand["target"]
    risk = abs(entry - stop)
    trig = session.between_time("09:35", FUT_TRIGGER_LAST)   # let the opening bar finish first
    fill = None; fill_ts = None
    first = session.iloc[0]
    if (side == "long" and first["Open"] > entry) or (side == "short" and first["Open"] < entry):
        return {"status": "gap_cancelled", "r": 0.0, "exit_price": None, "fill": None,
                "fill_time": None, "exit_time": None}
    for ts, b in trig.iterrows():
        if side == "long" and b["High"] >= entry:
            if b["Open"] > entry + 0.25 * risk:
                return {"status": "gap_cancelled", "r": 0.0, "exit_price": None, "fill": None,
                        "fill_time": None, "exit_time": None}
            fill = max(b["Open"], entry); fill_ts = ts; break
        if side == "short" and b["Low"] <= entry:
            if b["Open"] < entry - 0.25 * risk:
                return {"status": "gap_cancelled", "r": 0.0, "exit_price": None, "fill": None,
                        "fill_time": None, "exit_time": None}
            fill = min(b["Open"], entry); fill_ts = ts; break
    if fill is None:
        return {"status": "not_triggered", "r": 0.0, "exit_price": None, "fill": None,
                "fill_time": None, "exit_time": None}
    after = session[(session.index >= fill_ts)].between_time("09:30", FUT_FLAT_BY)
    sign = 1 if side == "long" else -1
    for ts, b in after.iterrows():
        hit_stop = b["Low"] <= stop if side == "long" else b["High"] >= stop
        hit_tgt = b["High"] >= target if side == "long" else b["Low"] <= target
        if hit_stop:  # conservative: stop first when both in the same bar
            return {"status": "stopped", "r": sign * (stop - fill) / risk, "exit_price": stop,
                    "fill": fill, "fill_time": str(fill_ts), "exit_time": str(ts)}
        if hit_tgt:
            return {"status": "target", "r": sign * (target - fill) / risk, "exit_price": target,
                    "fill": fill, "fill_time": str(fill_ts), "exit_time": str(ts)}
    last = after.iloc[-1]
    return {"status": "expired", "r": sign * (float(last["Close"]) - fill) / risk,
            "exit_price": float(last["Close"]), "fill": fill, "fill_time": str(fill_ts),
            "exit_time": str(after.index[-1])}


def backtest_futures(df5: pd.DataFrame, dfd: pd.DataFrame, spec: dict, vix_daily=None):
    out = []
    sessions = rth_sessions(df5)
    for d in sorted(sessions):
        lv = futures_levels(df5, dfd, d, spec)
        if not lv:
            continue
        cand = futures_candidate(lv, spec)
        res = simulate_futures_session(sessions[d], cand)
        vix = float(vix_daily.asof(pd.Timestamp(d))) if vix_daily is not None else np.nan
        out.append({"symbol": spec["ibkr"], "date": str(d), "vix": vix, **cand, **res,
                    "avg_range": lv["avg_range"], "trend": lv["trend"]})
    return out
