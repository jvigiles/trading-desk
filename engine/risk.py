"""Deterministic risk engine: sizing, cost model, hard limits. No model output can override this."""
import math
from config import (CAPITAL_EUR, RISK_PER_TRADE_PCT, RISK_PER_TRADE_FUT_PCT, MAX_LEVERAGE, TIERS,
                    FUT_COMMISSION_PER_SIDE, FUT_SLIPPAGE_TICKS, STOCK_COMMISSION_MIN,
                    STOCK_COMMISSION_PER_SHARE, STOCK_SPREAD_PCT)


def capital_usd(fx: float, capital_eur: float = CAPITAL_EUR) -> float:
    return capital_eur * fx


def futures_cost_r(spec: dict, stop_dist: float) -> float:
    """Round-trip cost expressed in R (fraction of the stop distance in USD)."""
    cost = 2 * FUT_COMMISSION_PER_SIDE + 2 * FUT_SLIPPAGE_TICKS * spec["tick"] * spec["point_value"]
    return cost / (stop_dist * spec["point_value"])


def size_futures(spec: dict, cand: dict, fx: float, capital_eur: float = CAPITAL_EUR):
    stop_dist = abs(cand["entry"] - cand["stop"])
    risk_usd_1 = stop_dist * spec["point_value"]
    budget = capital_usd(fx, capital_eur) * RISK_PER_TRADE_FUT_PCT
    contracts = math.floor(budget / risk_usd_1)
    reason = None
    if contracts < 1:
        reason = (f"One {spec['ibkr']} contract risks ${risk_usd_1:.0f} at the stop, above the "
                  f"{RISK_PER_TRADE_FUT_PCT*100:.1f}% limit (${budget:.0f}). No trade.")
    contracts = max(0, min(contracts, 2))
    return {"units": contracts, "unit_label": "contract(s)", "risk_usd": contracts * risk_usd_1,
            "risk_eur": contracts * risk_usd_1 / fx, "cost_r": futures_cost_r(spec, stop_dist),
            "notional_usd": contracts * cand["entry"] * spec["point_value"], "block_reason": reason,
            "risk_pct_of_capital": contracts * risk_usd_1 / capital_usd(fx, capital_eur),
            "notional_pct_of_capital": contracts * cand["entry"] * spec["point_value"] / capital_usd(fx, capital_eur),
            "tier": "base"}


def stock_cost_r(entry: float, stop_dist: float, shares: int) -> float:
    comm = 2 * max(STOCK_COMMISSION_MIN, STOCK_COMMISSION_PER_SHARE * shares)
    spread = 2 * STOCK_SPREAD_PCT * entry * shares
    return (comm + spread) / (stop_dist * shares) if shares else 9.9


def size_stock(cand: dict, fx: float, capital_eur: float = CAPITAL_EUR, tier: str = "base"):
    stop_dist = abs(cand["entry"] - cand["stop"])
    cap = capital_usd(fx, capital_eur)
    risk_pct = TIERS.get(tier, TIERS["base"])["risk_pct"]
    budget = cap * risk_pct
    shares = math.floor(budget / stop_dist)
    max_by_notional = math.floor(cap * MAX_LEVERAGE / cand["entry"])
    shares = min(shares, max_by_notional)
    reason = None
    if shares < 1:
        reason = "Even one share exceeds the per-trade risk or notional limit. No trade."
    return {"units": max(0, shares), "unit_label": "share(s)", "risk_usd": shares * stop_dist,
            "risk_eur": shares * stop_dist / fx, "cost_r": stock_cost_r(cand["entry"], stop_dist, shares),
            "notional_usd": shares * cand["entry"], "block_reason": reason,
            "risk_pct_of_capital": shares * stop_dist / cap, "notional_pct_of_capital": shares * cand["entry"] / cap,
            "tier": tier}
