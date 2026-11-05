"""Defined-risk option structures for tail signals.

What this does
  * pulls the (delayed) option chain for the underlying via yfinance,
  * picks a long call/put (delta 0.30-0.55, 55-100 DTE) and a vertical debit spread with the short strike near
    the underlying target,
  * prices each structure along the *backtested exit distribution* of the underlying setup (runner paths stored in
    state["path_samples"]) with Black-Scholes at the contract's current implied volatility,
  * returns, per structure: premium (= maximum loss), payoff at the underlying target, P(win), expectancy in units
    of premium, costs, liquidity and capital requirement.

What this does NOT do
  * It is not a backtest of option prices. Free historical option data does not exist, so the payoff mapping is a
    model (constant implied volatility, no early exercise, no dividend jumps). Treat results as estimates.
"""
from __future__ import annotations

import math
from datetime import date, datetime

import yfinance as yf

import config as C

_CHAIN_CACHE: dict = {}


# ---------------------------------------------------------------- Black-Scholes helpers
def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(S: float, K: float, t_years: float, iv: float, right: str, r: float = None) -> float:
    r = C.OPTIONS["risk_free"] if r is None else r
    if t_years <= 0 or iv <= 0:
        return max(0.0, (S - K) if right == "C" else (K - S))
    d1 = (math.log(S / K) + (r + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    d2 = d1 - iv * math.sqrt(t_years)
    if right == "C":
        return S * _ncdf(d1) - K * math.exp(-r * t_years) * _ncdf(d2)
    return K * math.exp(-r * t_years) * _ncdf(-d2) - S * _ncdf(-d1)


def bs_delta(S: float, K: float, t_years: float, iv: float, right: str) -> float:
    if t_years <= 0 or iv <= 0:
        return 1.0 if (right == "C" and S > K) or (right == "P" and S < K) else 0.0
    d1 = (math.log(S / K) + (C.OPTIONS["risk_free"] + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    return _ncdf(d1) if right == "C" else _ncdf(d1) - 1.0


# ---------------------------------------------------------------- chain access
def _chain(symbol: str, today: date):
    """Return list of {expiry, dte, calls:[...], puts:[...]} for expiries within the DTE window."""
    key = (symbol, str(today))
    if key in _CHAIN_CACHE:
        return _CHAIN_CACHE[key]
    out = []
    try:
        tk = yf.Ticker(symbol)
        for e in tk.options:
            ed = date.fromisoformat(e)
            dte = (ed - today).days
            if dte < C.OPTIONS["dte_min"] or dte > C.OPTIONS["dte_max"]:
                continue
            ch = tk.option_chain(e)
            out.append({"expiry": e, "dte": dte,
                        "C": _rows(ch.calls), "P": _rows(ch.puts)})
    except Exception as ex:  # noqa - network / symbol without options
        print(f"option chain {symbol}: {ex}")
    _CHAIN_CACHE[key] = out
    return out


def _num(x, default=0.0):
    try:
        v = float(x)
        return default if math.isnan(v) else v
    except (TypeError, ValueError):
        return default


def _rows(df):
    rows = []
    for _, r in df.iterrows():
        bid, ask = _num(r.get("bid")), _num(r.get("ask"))
        if bid <= 0 or ask <= 0 or ask < bid:
            continue
        rows.append({"contract": r["contractSymbol"], "strike": _num(r["strike"]), "bid": bid, "ask": ask,
                     "mid": (bid + ask) / 2, "iv": _num(r.get("impliedVolatility")),
                     "oi": int(_num(r.get("openInterest"))), "volume": int(_num(r.get("volume")))})
    return rows


def _liquid(row) -> bool:
    spread = (row["ask"] - row["bid"]) / max(1e-9, row["mid"])
    return row["oi"] >= C.OPTIONS["min_open_interest"] and (spread <= C.OPTIONS["max_spread_pct"] or (row["ask"] - row["bid"]) <= 0.10)


# ---------------------------------------------------------------- structure pricing
def _value(struct: dict, S: float, t_years: float) -> float:
    """Mark a structure (per share, before multiplier) at underlying S with t_years left; IV held constant."""
    v = bs_price(S, struct["long"]["strike"], t_years, struct["long"]["iv"], struct["right"])
    if struct.get("short"):
        v -= bs_price(S, struct["short"]["strike"], t_years, struct["short"]["iv"], struct["right"])
    return max(0.0, v)


def _price_paths(struct: dict, cand: dict, paths: list, dte: int) -> dict:
    """Map the underlying's backtested exit paths onto the structure. Each path: {r, d, s}
    r = exit R of the underlying (per 1 stop distance), d = sessions held, s = status."""
    entry, stop = cand["entry"], cand["stop"]
    risk = abs(entry - stop)
    mult = 100
    legs = 2 if struct.get("short") else 1
    comm = max(1.0, legs * C.OPTIONS["commission_per_contract"])  # per side
    slip = struct["half_spread"]  # per share, per side
    prem = struct["debit"]  # per share, paid at ask-side mid
    cost_units = (2 * comm / mult + 2 * slip) / prem
    pnls = []
    for pth in paths:
        if pth["s"] in ("not_triggered", "gap_cancelled"):
            continue
        S_exit = entry + pth["r"] * risk if cand["side"] == "long" else entry - pth["r"] * risk
        cal_days = pth["d"] * 7 / 5
        t_left = max(0.0, (dte - cal_days) / 365.0)
        v = _value(struct, S_exit, t_left)
        pnls.append((v - prem) / prem - cost_units)
    if len(pnls) < C.OPTIONS["min_paths"]:
        return None
    wins = [x for x in pnls if x > 0]; losses = [x for x in pnls if x <= 0]
    # scenario table
    t_mid = max(0.0, (dte - cand["horizon_days"] * 7 / 5 / 2) / 365.0)
    t_end = max(0.0, (dte - cand["horizon_days"] * 7 / 5) / 365.0)
    scen = {
        "at_target": _value(struct, cand["target"], t_mid) * mult,
        "at_stop": _value(struct, cand["stop"], t_mid) * mult,
        "flat_at_time_exit": _value(struct, entry, t_end) * mult,
    }
    return {
        "n_paths": len(pnls),
        "p_win": len(wins) / len(pnls),
        "win_r": (sum(wins) / len(wins)) if wins else 0.0,
        "loss_r": (sum(losses) / len(losses)) if losses else -1.0,
        "expectancy_r": sum(pnls) / len(pnls),
        "cost_r": cost_units,
        "scenarios_usd": {k: round(v - prem * mult, 2) for k, v in scen.items()},
        "payoff_ratio_at_target": (scen["at_target"] - prem * mult) / (prem * mult) if prem else None,
    }


def evaluate(symbol: str, cand: dict, paths: list, today: date, capital_usd: float) -> dict | None:
    """Return the best defined-risk structure for the candidate plus the comparison table, or None."""
    if symbol not in C.OPTION_UNDERLYINGS or not paths:
        return None
    right = "C" if cand["side"] == "long" else "P"
    chains = _chain(symbol, today)
    if not chains:
        return None
    S = cand["entry"]  # structure is entered when the underlying trades through the trigger
    max_prem = capital_usd * C.OPTIONS["max_premium_pct"]
    structs = []
    for ch in chains:
        rows = [r for r in ch[right] if _liquid(r) and r["iv"] > 0.02]
        if not rows:
            continue
        t = ch["dte"] / 365.0
        for r in rows:
            r["delta"] = abs(bs_delta(S, r["strike"], t, r["iv"], right))
        longs = [r for r in rows if C.OPTIONS["delta_lo"] <= r["delta"] <= C.OPTIONS["delta_hi"]]
        if not longs:
            continue
        # long option: the liquid strike closest to delta 0.40
        lg = min(longs, key=lambda r: abs(r["delta"] - 0.40))
        hs = (lg["ask"] - lg["bid"]) / 2
        # Debit expected AT THE TRIGGER: the structure is bought only once the underlying trades through
        # cand["entry"], so the long leg is re-priced there with today's implied volatility, plus 40% of the
        # quoted half-spread (we assume a fill between mid and ask). Today's quote is kept for reference only.
        lg_at = bs_price(S, lg["strike"], t, lg["iv"], right)
        structs.append({"structure": "long_call" if right == "C" else "long_put", "expiry": ch["expiry"], "dte": ch["dte"],
                        "right": right, "long": lg, "short": None, "debit": lg_at + 0.4 * hs,
                        "half_spread": hs})
        # debit spread: short strike nearest the underlying target
        shorts = [r for r in rows if (r["strike"] > lg["strike"] if right == "C" else r["strike"] < lg["strike"])]
        if shorts:
            sh = min(shorts, key=lambda r: abs(r["strike"] - cand["target"]))
            sh_at = bs_price(S, sh["strike"], t, sh["iv"], right)
            debit = (lg_at - sh_at) + 0.4 * (hs + (sh["ask"] - sh["bid"]) / 2)
            if debit > 0.05:
                structs.append({"structure": "debit_spread", "expiry": ch["expiry"], "dte": ch["dte"], "right": right,
                                "long": lg, "short": sh, "debit": debit, "half_spread": hs + (sh["ask"] - sh["bid"]) / 2})
    if not structs:
        return None
    table = []
    for st in structs:
        pr = _price_paths(st, cand, paths, st["dte"])
        if not pr:
            continue
        prem_usd = st["debit"] * 100
        st_out = {
            "structure": st["structure"], "label": C.STRUCTURES[st["structure"]]["label"],
            "expiry": st["expiry"], "dte": st["dte"], "right": right,
            "long_strike": st["long"]["strike"], "short_strike": st["short"]["strike"] if st["short"] else None,
            "long_contract": st["long"]["contract"], "short_contract": st["short"]["contract"] if st["short"] else None,
            "long_iv": round(st["long"]["iv"], 3), "long_delta": round(st["long"]["delta"], 2),
            "quote": {"long_bid": st["long"]["bid"], "long_ask": st["long"]["ask"],
                      "short_bid": st["short"]["bid"] if st["short"] else None, "short_ask": st["short"]["ask"] if st["short"] else None,
                      "open_interest": min(st["long"]["oi"], st["short"]["oi"]) if st["short"] else st["long"]["oi"]},
            "debit_per_share": round(st["debit"], 2), "premium_usd": round(prem_usd, 2),
            "max_loss_usd": round(prem_usd, 2),
            "max_gain_usd": (round((st["short"]["strike"] - st["long"]["strike"]) * 100 - prem_usd, 2) if st["short"] and right == "C"
                             else round((st["long"]["strike"] - st["short"]["strike"]) * 100 - prem_usd, 2) if st["short"] else None),
            "breakeven": round(st["long"]["strike"] + st["debit"], 2) if right == "C" else round(st["long"]["strike"] - st["debit"], 2),
            "premium_pct_of_capital": prem_usd / capital_usd,
            "fits_budget": prem_usd <= max_prem,
            **pr,
        }
        table.append(st_out)
    if not table:
        return None
    # choose: within budget, payoff at target >= min_rr, highest expectancy; else best-by-expectancy flagged as over budget
    ok = [t for t in table if t["fits_budget"] and (t["payoff_ratio_at_target"] or 0) >= C.OPTIONS["min_rr"]]
    best = max(ok, key=lambda t: t["expectancy_r"]) if ok else max(table, key=lambda t: t["expectancy_r"])
    return {"chosen": best, "table": sorted(table, key=lambda t: -t["expectancy_r"]), "max_premium_usd": round(max_prem, 2),
            "chain_time": datetime.now().isoformat(timespec="minutes"), "model_note": (
                "Payoffs: runner exit paths (backtest) priced with Black-Scholes at today's implied volatility; "
                "no historical option prices were used.")}


# ---------------------------------------------------------------- scoring (mark to model / market)
def mark(card: dict, S_exit: float, days_held: int, today: date) -> dict:
    """Value the card's structure at the underlying exit price. Uses the live chain quote if the exit is today
    and the contract is still quoted, otherwise Black-Scholes at the entry IV."""
    o = card["option"]
    dte_left = (date.fromisoformat(o["expiry"]) - today).days
    live = None
    try:
        if dte_left > 0 and days_held is not None:
            for ch in _chain(card["data_symbol"], today) or []:
                if ch["expiry"] == o["expiry"]:
                    rows = {r["contract"]: r for r in ch[o["right"]]}
                    lg = rows.get(o["long_contract"]); sh = rows.get(o["short_contract"]) if o["short_contract"] else None
                    if lg and (sh or not o["short_contract"]):
                        live = lg["bid"] - (sh["ask"] if sh else 0.0)  # conservative: sell at bid, buy back at ask
    except Exception:
        live = None
    t_left = max(0.0, (o["dte"] - days_held * 7 / 5) / 365.0)
    struct = {"right": o["right"], "long": {"strike": o["long_strike"], "iv": o["long_iv"]},
              "short": {"strike": o["short_strike"], "iv": o.get("short_iv", o["long_iv"])} if o["short_strike"] else None}
    model = _value(struct, S_exit, t_left)
    value = live if live is not None else model
    return {"value_per_share": round(max(0.0, value), 2), "source": "chain_quote" if live is not None else "model"}
