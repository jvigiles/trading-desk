"""Daily run: score open cards -> update learning state -> generate today's cards -> write JSON for the app.

Usage: python3 run_daily.py [--date YYYY-MM-DD]
Outputs (data/): cards.json (all cards), today.json (today's view), metrics.json, state.json
Optional input: data/analyst_notes.json  {"date": "...", "market_context": "...", "cards": {card_id: {"note":..., "veto": bool}}}
"""
import argparse
import json
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import config as C
from data import daily, daily_many, intraday_5m, eurusd, vix_level, rth_sessions
from setups import (swing_features, swing_signal, simulate_swing, futures_levels, futures_candidate,
                    simulate_futures_session)
from risk import size_futures, size_stock
from learn import load_state, save_state, posterior, record_outcome, regime_for, DATA
import execution
import supabase_io

CARDS_PATH = os.path.join(DATA, "cards.json")
TODAY_PATH = os.path.join(DATA, "today.json")
METRICS_PATH = os.path.join(DATA, "metrics.json")
NOTES_PATH = os.path.join(DATA, "analyst_notes.json")
OPEN_STATUSES = {"pending", "open"}
DONE_STATUSES = {"target", "stopped", "expired", "not_triggered", "gap_cancelled", "vetoed"}


def load_json(p, default):
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return default


def next_session(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def fmt_eur(x):
    return round(float(x), 2)


# ---------------------------------------------------------------- scoring of existing cards
def score_cards(cards, run_date: date, fx: float):
    """Update status/outcome for open cards using fresh market data."""
    changed = []
    fut_cache, day_cache = {}, {}
    for card in cards:
        if card["status"] not in OPEN_STATUSES:
            continue
        sd = date.fromisoformat(card["session_date"])
        if card["kind"] == "futures_day":
            if run_date <= sd:
                continue  # session not finished
            sym = card["data_symbol"]
            if sym not in fut_cache:
                fut_cache[sym] = rth_sessions(intraday_5m(sym, "60d"))
            sess = fut_cache[sym].get(sd)
            if sess is None or len(sess) < 50:
                continue
            res = simulate_futures_session(sess, card["levels"])
        else:
            sym = card["data_symbol"]
            if sym not in day_cache:
                day_cache[sym] = daily(sym, "1y")
            df = day_cache[sym]
            if not len(df):
                continue
            sig = pd.Timestamp(card["signal_date"])
            if sig not in df.index:
                continue
            i = df.index.get_loc(sig)
            res = simulate_swing(df, i, card["levels"])
            if res is None:
                # still in progress: work out whether it has been triggered
                part = _swing_partial(df, i, card["levels"])
                if part != card["status"]:
                    card["status"] = part; changed.append(card)
                continue
        _apply_outcome(card, res, fx)
        changed.append(card)
    return changed


def _swing_partial(df, i, lv):
    n = len(df)
    for j in range(i + 1, min(n, i + 1 + lv["trigger_days"])):
        if lv["entry_type"] == "limit" and df["Low"].iloc[j] <= lv["entry"]:
            return "open"
        if lv["entry_type"] == "stop" and df["High"].iloc[j] >= lv["entry"]:
            return "open"
    return "pending"


def _apply_outcome(card, res, fx):
    status = res["status"]
    card["status"] = status
    r_gross = float(res.get("r", 0.0) or 0.0)
    triggered = status in ("target", "stopped", "expired")
    r_net = r_gross - card["size"]["cost_r"] if triggered else 0.0
    risk_usd = card["size"]["risk_usd"] if card["size"]["units"] > 0 else card["size"]["risk_usd_1unit"]
    pnl_usd = r_net * risk_usd if triggered else 0.0
    card["outcome"] = {
        "scored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fill": res.get("fill"), "exit_price": res.get("exit_price"),
        "fill_time": res.get("fill_time"), "exit_time": res.get("exit_time"),
        "days": res.get("days"), "r_gross": round(r_gross, 3), "r_net": round(r_net, 3),
        "pnl_usd": round(pnl_usd, 2), "pnl_eur": round(pnl_usd / fx, 2),
        "hit": bool(r_net > 0) if triggered else None,
        "brier": round((card["prob_success"] - (1 if r_net > 0 else 0)) ** 2, 4) if triggered else None,
    }


# ---------------------------------------------------------------- generation
def make_card(kind, setup_id, data_symbol, instrument, cand, size, post, regime, session_date,
              signal_date, rationale, invalidation, extra=None):
    exp_net = post["expectancy_r"]
    risk_usd = size["risk_usd"] if size["units"] > 0 else size["risk_usd_1unit"]
    return {
        "id": f"{session_date}-{instrument['symbol']}-{setup_id}".replace("=", "").lower(),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session_date": str(session_date), "signal_date": str(signal_date),
        "kind": kind, "setup_id": setup_id, "setup_name": C.SETUPS[setup_id]["name"],
        "instrument": instrument, "data_symbol": data_symbol,
        "side": cand["side"], "entry_type": cand["entry_type"],
        "levels": cand,
        "size": size, "regime": regime,
        "prob_success": round(post["p"], 3), "expectancy_r": round(exp_net, 3),
        "expected_win_r": round(post["win_r"], 2), "expected_loss_r": round(post["loss_r"], 2),
        "evidence": {"prior_n": post["prior_n"], "live_n": post["live_n"], "regime_used": post["regime_used"],
                     "setup_status": post["status"]},
        "expected_gain_usd": round(post["win_r"] * risk_usd, 2),
        "expected_loss_usd": round(post["loss_r"] * risk_usd, 2),
        "recommended": False, "shadow_reason": None,
        "rationale": rationale, "invalidation": invalidation,
        "analyst": {"note": None, "veto": False},
        "tier": C.SETUPS[setup_id].get("tier", "base"), "rank": None, "signals": [],
        "status": "pending", "outcome": None, **(extra or {}),
    }


def gate(card, post, blackout_note):
    """Decide recommended vs shadow. Returns reason string if shadow."""
    if post["status"] == "suspended":
        return "Setup suspended by the learning loop (negative live expectancy)."
    if post["expectancy_r"] < C.MIN_EXPECTANCY_R:
        return (f"Expectancy {post['expectancy_r']:+.2f}R is below the {C.MIN_EXPECTANCY_R:.2f}R threshold "
                f"(based on {post['prior_n']} historical + {post['live_n']} live outcomes). Tracked for learning only.")
    if card["size"]["units"] < 1:
        return card["size"]["block_reason"]
    lv = card["levels"]; rr = abs(lv["target"] - lv["entry"]) / max(1e-9, abs(lv["entry"] - lv["stop"]))
    min_rr = C.TIERS[card["tier"]]["min_rr"]
    if rr < min_rr - 1e-6:
        return f"Reward:risk {rr:.2f} is below the {min_rr:.1f} minimum for {card['tier']} trades."
    if card["kind"] == "futures_day" and blackout_note:
        return f"Macro blackout: {blackout_note}. Futures day trades are not issued on tier-1 release days."
    return None


def generate(cards, state, session_date: date, fx: float, vix: float):
    regime = regime_for(vix)
    blackout = C.MACRO_EVENTS.get(session_date)
    existing = {c["id"] for c in cards}
    new = []

    # ---- futures day candidates
    for sym, spec in C.FUTURES.items():
        df5, dfd = intraday_5m(sym, "60d"), daily(sym, "2y")
        if not len(df5) or not len(dfd):
            continue
        lv = futures_levels(df5, dfd, session_date, spec)
        if not lv:
            continue
        cand = futures_candidate(lv, spec)
        post = posterior(state, "FUT_PDR_BREAKOUT", regime) or posterior(state, "FUT_PDR_BREAKOUT", "all")
        if not post:
            continue
        size = size_futures(spec, cand, fx)
        size["risk_usd_1unit"] = abs(cand["entry"] - cand["stop"]) * spec["point_value"]
        inst = {"symbol": spec["ibkr"], "name": spec["name"], "type": "futures", "currency": "USD",
                "point_value": spec["point_value"], "tick": spec["tick"]}
        rationale = [
            f"Prior RTH session ({lv['prev_session']}): high {lv['pdh']:.2f}, low {lv['pdl']:.2f}; "
            f"10-session average range {lv['avg_range']:.1f} points.",
            f"Daily trend filter: last close {lv['last_close']:.2f} vs 20-day average {lv['sma20']:.2f} -> {lv['trend']}trend, "
            f"so only the {cand['side']} breakout is considered.",
            f"Stop {abs(cand['entry']-cand['stop']):.2f} pts (20% of avg range), target {abs(cand['target']-cand['entry']):.2f} pts (40%).",
            f"VIX {vix:.1f} -> {regime.replace('_', ' ')} regime.",
        ]
        invalidation = [
            "Session opens beyond the entry level (gap through): cancel the order, do not chase.",
            f"Not triggered by {C.FUT_TRIGGER_LAST} ET (21:00 CET): cancel.",
            f"Still open at {C.FUT_FLAT_BY} ET (21:55 CET): close at market. Never hold a day card overnight.",
            "Daily loss limit (2% of capital) already reached: skip.",
        ]
        card = make_card("futures_day", "FUT_PDR_BREAKOUT", sym, inst, cand, size, post, regime,
                         session_date, session_date, rationale, invalidation,
                         {"levels_meta": lv, "valid_until_et": f"{session_date} {C.FUT_FLAT_BY}"})
        card["signals"] = ["prior_day_range", f"trend_{lv['trend']}", regime]
        if card["id"] in existing:
            continue
        reason = gate(card, post, blackout)
        card["recommended"] = reason is None
        card["shadow_reason"] = reason
        new.append(card)

    # ---- swing candidates from the last completed close
    dd = daily_many(C.SWING_UNIVERSE, "2y")
    for sym, df in dd.items():
        f = swing_features(df)
        last = f.iloc[-1]
        signal_date = f.index[-1].date()
        if signal_date >= session_date:
            # yfinance may include a partial current bar; use the previous completed one
            f = f.iloc[:-1]; last = f.iloc[-1]; signal_date = f.index[-1].date()
        prev_hi20 = f["hi20"].iloc[-2]
        for sid in ("SWING_PULLBACK", "SWING_BREAKOUT", "SWING_BREAKOUT_RUNNER"):
            cand = swing_signal(sid, last, prev_hi20)
            if not cand:
                continue
            post = posterior(state, sid, regime) or posterior(state, sid, "all")
            if not post:
                continue
            tier = C.SETUPS[sid].get("tier", "base")
            size = size_stock(cand, fx, tier=tier)
            size["risk_usd_1unit"] = cand["entry"] - cand["stop"]
            inst = {"symbol": sym, "name": sym, "type": "etf" if sym in C.SWING_UNIVERSE[:12] else "stock",
                    "currency": "USD"}
            a = float(last["atr14"])
            rationale = [
                f"Signal at {signal_date} close {last['Close']:.2f}: " + (
                    f"RSI(2) {last['rsi2']:.1f} (<10) with price above the 50-day ({last['sma50']:.2f}) and 200-day ({last['sma200']:.2f}) averages."
                    if sid == "SWING_PULLBACK" else
                    f"new 20-day high on volume {last['Volume']/last['vol20']:.1f}x the 20-day average, above the 50-day average ({last['sma50']:.2f})."),
                f"ATR(14) {a:.2f}: stop {C.SETUPS[sid]['stop_atr']} ATR, target {C.SETUPS[sid]['target_atr']} ATR, "
                f"time exit after {cand['horizon_days']} sessions.",
                f"VIX {vix:.1f} -> {regime.replace('_', ' ')} regime.",
            ]
            invalidation = [
                (f"Not filled within {cand['trigger_days']} session(s): cancel." ),
                "Opens more than half the stop distance beyond the entry: cancel, do not chase." if cand["entry_type"] == "stop" else
                "Opens below the stop level: cancel.",
                f"Earnings or company-specific event before exit: reduce size or skip (check the calendar)." if inst["type"] == "stock" else
                "Tier-1 macro release during the hold is acceptable for swing cards but widen expectations for gaps.",
            ]
            card = make_card("swing", sid, sym, inst, cand, size, post, regime, session_date, signal_date,
                             rationale, invalidation)
            card["signals"] = (["rsi2_oversold", "above_sma50", "above_sma200"] if sid == "SWING_PULLBACK"
                               else ["20d_high", "volume_1.5x", "above_sma50"]) + [regime]
            if card["id"] in existing:
                continue
            reason = gate(card, post, None)
            if blackout and reason is None:
                card["analyst"]["note"] = f"Note: {blackout} falls on the entry day."
            card["recommended"] = reason is None
            card["shadow_reason"] = reason
            new.append(card)

    # ---- discretionary proposals from the analyst review (EVENT_SCOUT)
    new += event_proposals(cards, state, session_date, fx, vix, regime, existing)

    allocate(new, cards, session_date)
    return new


def cluster_of(sym):
    return [k for k, v in C.CLUSTERS.items() if sym in v]


def allocate(new, cards, session_date):
    """Rank candidates and apply tier caps, correlation caps and aggregate open-risk caps.
    Ranking key: expectancy after costs, then probability, then reward:risk."""
    def rr(c):
        lv = c["levels"]; return abs(lv["target"] - lv["entry"]) / max(1e-9, abs(lv["entry"] - lv["stop"]))
    new.sort(key=lambda c: (not c["recommended"], -c["expectancy_r"], -c["prob_success"], -rr(c)))
    for i, c in enumerate(new, 1):
        c["rank"] = i
    # positions already open from earlier sessions count against caps
    open_prev = [c for c in cards if c["status"] in OPEN_STATUSES and c["recommended"]
                 and c["session_date"] != str(session_date)]
    open_by_tier = {"base": 0, "tail": 0}
    risk_by_tier = {"base": 0.0, "tail": 0.0}
    cluster_count = {}
    for c in open_prev:
        open_by_tier[c["tier"]] += 1
        risk_by_tier[c["tier"]] += c["size"].get("risk_pct_of_capital", 0)
        for k in cluster_of(c["data_symbol"]):
            cluster_count[k] = cluster_count.get(k, 0) + 1
    fut_n = swing_n = 0
    symbols_taken = set()
    for c in new:
        if not c["recommended"]:
            continue
        t = c["tier"]; tier_cfg = C.TIERS[t]
        reason = None
        if c["kind"] == "futures_day" and fut_n >= C.MAX_FUTURES_CARDS:
            reason = "Daily futures card cap reached."
        elif c["kind"] == "swing" and swing_n >= C.MAX_SWING_CARDS + 1:
            reason = "Daily swing card cap reached."
        elif open_by_tier[t] >= tier_cfg["max_open"]:
            reason = f"{tier_cfg['label']} cap: {tier_cfg['max_open']} open positions already."
        elif risk_by_tier[t] + c["size"].get("risk_pct_of_capital", 0) > tier_cfg["max_total_risk_pct"] + 1e-9:
            reason = f"{tier_cfg['label']} risk budget ({tier_cfg['max_total_risk_pct']*100:.1f}% of capital) would be exceeded."
        elif sum(risk_by_tier.values()) + c["size"].get("risk_pct_of_capital", 0) > C.MAX_TOTAL_OPEN_RISK_PCT + 1e-9:
            reason = f"Total open risk cap ({C.MAX_TOTAL_OPEN_RISK_PCT*100:.1f}% of capital) would be exceeded."
        elif c["data_symbol"] in symbols_taken:
            reason = "Same instrument already recommended today in another tier (avoid doubling exposure)."
        else:
            for k in cluster_of(c["data_symbol"]):
                if cluster_count.get(k, 0) >= C.MAX_CORRELATED_POSITIONS:
                    reason = f"Correlation cap: already {C.MAX_CORRELATED_POSITIONS} positions in the '{k}' cluster."
                    break
        if reason:
            c["recommended"] = False
            c["shadow_reason"] = reason + " Lower-ranked candidate tracked in shadow only."
            continue
        open_by_tier[t] += 1; risk_by_tier[t] += c["size"].get("risk_pct_of_capital", 0)
        symbols_taken.add(c["data_symbol"])
        for k in cluster_of(c["data_symbol"]):
            cluster_count[k] = cluster_count.get(k, 0) + 1
        if c["kind"] == "futures_day": fut_n += 1
        else: swing_n += 1
    for c in new:
        c["execution"] = execution.build(c)


def event_proposals(cards, state, session_date, fx, vix, regime, existing):
    """Turn analyst proposals (data/analyst_notes.json -> "proposals") into EVENT_SCOUT cards.
    Each proposal: {symbol, name, type, side, entry, entry_type, stop, target, thesis:[...], signals:[...],
    trigger_days, horizon_days, tier?}. These never bypass the gate: EVENT_SCOUT has a sceptical prior,
    so they stay in shadow until live results justify promotion."""
    notes = load_json(NOTES_PATH, {})
    if notes.get("date") != str(session_date):
        return []
    out = []
    for pr in notes.get("proposals", []):
        try:
            sid = "EVENT_SCOUT"
            cand = {"side": pr.get("side", "long"), "entry_type": pr.get("entry_type", "limit"),
                    "entry": float(pr["entry"]), "stop": float(pr["stop"]), "target": float(pr["target"]),
                    "horizon_days": int(pr.get("horizon_days", C.SETUPS[sid]["horizon_days"])),
                    "trigger_days": int(pr.get("trigger_days", 1))}
            if cand["side"] == "long" and not (cand["stop"] < cand["entry"] < cand["target"]):
                continue
            if cand["side"] == "short" and not (cand["target"] < cand["entry"] < cand["stop"]):
                continue
            post = posterior(state, sid, regime)
            tier = pr.get("tier", "tail")
            size = size_stock(cand, fx, tier=tier)
            size["risk_usd_1unit"] = abs(cand["entry"] - cand["stop"])
            inst = {"symbol": pr["symbol"], "name": pr.get("name", pr["symbol"]), "type": pr.get("type", "stock"),
                    "currency": "USD"}
            card = make_card("swing", sid, pr["symbol"], inst, cand, size, post, regime, session_date,
                             session_date, pr.get("thesis", []), pr.get("invalidation", [
                                 f"Not filled within {cand['trigger_days']} session(s): cancel.",
                                 "Thesis event resolves against the position: close at market, do not wait for the stop."]))
            card["tier"] = tier
            card["signals"] = list(pr.get("signals", [])) + ["discretionary", regime]
            if card["id"] in existing:
                continue
            reason = gate(card, post, None)
            card["recommended"] = reason is None
            card["shadow_reason"] = reason
            out.append(card)
        except (KeyError, ValueError, TypeError) as e:
            print(f"skipping malformed proposal {pr}: {e}", file=sys.stderr)
    return out


def apply_analyst_notes(cards, session_date):
    notes = load_json(NOTES_PATH, {})
    if notes.get("date") != str(session_date):
        return None
    for c in cards:
        n = notes.get("cards", {}).get(c["id"])
        if n:
            c["analyst"]["note"] = n.get("note")
            if n.get("veto") and c["status"] == "pending":
                c["analyst"]["veto"] = True
                c["recommended"] = False
                c["shadow_reason"] = f"Analyst veto: {n.get('note')}"
    return notes.get("market_context")


# ---------------------------------------------------------------- metrics
def _summary(cs):
    if not cs:
        return {"n": 0, "hit_rate": None, "avg_r": None, "sum_r": 0, "pnl_eur": 0, "brier": None,
                "profit_factor": None, "max_dd_r": 0, "avg_days": None}
    rs = [c["outcome"]["r_net"] for c in cs]
    wins = sum(r for r in rs if r > 0); losses = -sum(r for r in rs if r <= 0)
    eq = np.cumsum(rs); dd = float((np.maximum.accumulate(eq) - eq).max()) if len(eq) else 0
    days = [c["outcome"]["days"] for c in cs if c["outcome"].get("days") is not None]
    return {"n": len(cs), "hit_rate": sum(1 for r in rs if r > 0) / len(rs),
            "avg_r": float(np.mean(rs)), "sum_r": float(np.sum(rs)),
            "pnl_eur": float(sum(c["outcome"]["pnl_eur"] for c in cs)),
            "brier": float(np.mean([c["outcome"]["brier"] for c in cs])),
            "base_rate_brier": float(np.mean([(np.mean([x > 0 for x in rs]) - (r > 0)) ** 2 for r in rs])),
            "profit_factor": (wins / losses) if losses else None, "max_dd_r": dd,
            "avg_days": float(np.mean(days)) if days else None}


def compute_metrics(cards, fx, executions=None):
    executions = executions or []
    ex_by = {e["cardId"]: e for e in executions}
    done = [c for c in cards if c["status"] in ("target", "stopped", "expired")]
    rec_done = [c for c in done if c["recommended"]]
    by_setup = {}
    for sid in C.SETUPS:
        by_setup[sid] = {"tier": C.SETUPS[sid].get("tier", "base"),
                         "recommended": _summary([c for c in rec_done if c["setup_id"] == sid]),
                         "all_tracked": _summary([c for c in done if c["setup_id"] == sid])}
    by_tier = {t: {"recommended": _summary([c for c in rec_done if c["tier"] == t]),
                   "all_tracked": _summary([c for c in done if c["tier"] == t])} for t in C.TIERS}
    by_regime = {r: _summary([c for c in done if c["regime"] == r]) for _, _, r in C.VIX_REGIMES}
    by_kind = {k: _summary([c for c in done if c["kind"] == k]) for k in ("futures_day", "swing")}
    # signal combinations (setup x regime x side) with n >= 5
    combos = {}
    for c in done:
        key = f"{c['setup_id']}|{c['regime']}|{c['side']}"
        combos.setdefault(key, []).append(c)
    signal_combos = sorted([{"combo": k, **_summary(v)} for k, v in combos.items() if len(v) >= 5],
                           key=lambda x: -(x["avg_r"] or 0))
    # predicted vs realised, by setup
    pred_vs_real = []
    for sid in C.SETUPS:
        cs = [c for c in done if c["setup_id"] == sid]
        if cs:
            pred_vs_real.append({"setup_id": sid, "n": len(cs),
                                 "predicted_p": float(np.mean([c["prob_success"] for c in cs])),
                                 "observed_p": float(np.mean([c["outcome"]["hit"] for c in cs])),
                                 "predicted_r": float(np.mean([c["expectancy_r"] for c in cs])),
                                 "observed_r": float(np.mean([c["outcome"]["r_net"] for c in cs]))})
    curve = []
    cum_r = 0.0; cum_eur = 0.0
    for c in sorted(rec_done, key=lambda c: c["outcome"]["exit_time"] or c["session_date"]):
        cum_r += c["outcome"]["r_net"]; cum_eur += c["outcome"]["pnl_eur"]
        curve.append({"date": c["session_date"], "cum_r": round(cum_r, 3), "cum_eur": round(cum_eur, 2), "id": c["id"], "tier": c["tier"]})
    bins = {}
    for c in done:
        b = f"{int(c['prob_success']*10)*10}-{int(c['prob_success']*10)*10+10}%"
        bins.setdefault(b, {"n": 0, "hits": 0, "p_sum": 0.0})
        bins[b]["n"] += 1; bins[b]["hits"] += int(c["outcome"]["hit"]); bins[b]["p_sum"] += c["prob_success"]
    calib = [{"bin": k, "n": v["n"], "observed": v["hits"] / v["n"], "predicted": v["p_sum"] / v["n"]}
             for k, v in sorted(bins.items())]

    # ---- executed vs skipped (user decisions)
    executed = [c for c in done if ex_by.get(c["id"], {}).get("decision") == "executed"]
    skipped = [c for c in done if ex_by.get(c["id"], {}).get("decision") == "skipped"]
    undecided_rec = [c for c in rec_done if c["id"] not in ex_by]
    ex_with_pnl = [ex_by[c["id"]] for c in executed if ex_by[c["id"]].get("pnlEur") is not None]
    own_pnl = float(sum(e["pnlEur"] for e in ex_with_pnl))
    sys_pnl_same = float(sum(c["outcome"]["pnl_eur"] for c in executed if ex_by[c["id"]].get("pnlEur") is not None))
    # adherence: fill within 0.25R of the planned entry
    adher = []
    for c in executed:
        e = ex_by[c["id"]]
        if e.get("fillPrice") and c["outcome"].get("fill"):
            risk = abs(c["levels"]["entry"] - c["levels"]["stop"])
            adher.append(abs(e["fillPrice"] - c["levels"]["entry"]) / risk <= 0.25)
    decisions = {
        "executed": _summary(executed), "skipped": _summary(skipped),
        "executed_count": len(executed), "skipped_count": len(skipped), "undecided_recommended": len(undecided_rec),
        "own_pnl_eur": own_pnl, "system_pnl_same_cards_eur": sys_pnl_same, "n_with_own_pnl": len(ex_with_pnl),
        "execution_slippage_eur": own_pnl - sys_pnl_same if ex_with_pnl else None,
        "skipped_winners_r": float(sum(c["outcome"]["r_net"] for c in skipped if c["outcome"]["r_net"] > 0)),
        "skipped_losers_r": float(sum(c["outcome"]["r_net"] for c in skipped if c["outcome"]["r_net"] <= 0)),
        "net_r_of_skipping": float(-sum(c["outcome"]["r_net"] for c in skipped)),
        "entry_adherence_rate": (sum(adher) / len(adher)) if adher else None,
        "skip_rate_by_tier": {t: _rate([c for c in done if c["tier"] == t and c["id"] in ex_by], "skipped", ex_by) for t in C.TIERS},
        "skip_rate_by_side": {sd: _rate([c for c in done if c["side"] == sd and c["id"] in ex_by], "skipped", ex_by) for sd in ("long", "short")},
        "skip_rate_by_kind": {k: _rate([c for c in done if c["kind"] == k and c["id"] in ex_by], "skipped", ex_by) for k in ("futures_day", "swing")},
        "bias_flags": _bias_flags(executed, skipped, ex_by),
    }
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "recommended": _summary(rec_done), "all_tracked": _summary(done), "by_setup": by_setup,
            "by_tier": by_tier, "by_regime": by_regime, "by_kind": by_kind, "signal_combos": signal_combos,
            "predicted_vs_realised": pred_vs_real, "decisions": decisions,
            "equity_curve": curve, "calibration": calib, "fx_eurusd": fx,
            "capital_eur": C.CAPITAL_EUR, "counts": {"total_cards": len(cards),
            "open": sum(1 for c in cards if c["status"] in OPEN_STATUSES),
            "recommended_total": sum(1 for c in cards if c["recommended"])}}


def _rate(cs, decision, ex_by):
    if not cs:
        return None
    return sum(1 for c in cs if ex_by[c["id"]]["decision"] == decision) / len(cs)


def _bias_flags(executed, skipped, ex_by):
    """Heuristic flags; each needs >= 10 decided cards to fire. They are prompts for review, not verdicts."""
    flags = []
    decided = executed + skipped
    if len(decided) < 10:
        return [{"flag": "insufficient_data", "text": f"{len(decided)} decided cards; bias checks start at 10."}]
    sk_r = [c["outcome"]["r_net"] for c in skipped]; ex_r = [c["outcome"]["r_net"] for c in executed]
    if sk_r and ex_r and np.mean(sk_r) > np.mean(ex_r) + 0.2:
        flags.append({"flag": "skipping_winners", "text": f"Skipped cards averaged {np.mean(sk_r):+.2f}R vs {np.mean(ex_r):+.2f}R executed. Your filter may be removing good trades."})
    if sk_r and ex_r and np.mean(ex_r) > np.mean(sk_r) + 0.2:
        flags.append({"flag": "good_filter", "text": f"Executed cards averaged {np.mean(ex_r):+.2f}R vs {np.mean(sk_r):+.2f}R skipped. Your selection added value so far."})
    shorts_sk = [c for c in skipped if c["side"] == "short"]; shorts_all = [c for c in decided if c["side"] == "short"]
    if len(shorts_all) >= 6 and len(shorts_sk) / len(shorts_all) > 0.8:
        flags.append({"flag": "long_bias", "text": "You skip more than 80% of short cards. Check whether that is a rule or a reflex."})
    tails_all = [c for c in decided if c["tier"] == "tail"]; tails_sk = [c for c in tails_all if ex_by[c["id"]]["decision"] == "skipped"]
    if len(tails_all) >= 6 and len(tails_sk) / len(tails_all) > 0.8:
        flags.append({"flag": "tail_aversion", "text": "You skip most tail trades. Their value comes from the few large winners, so selective skipping removes exactly those."})
    after_loss = 0; after_loss_sk = 0
    seq = sorted(decided, key=lambda c: c["session_date"])
    for prev, cur in zip(seq, seq[1:]):
        if ex_by[prev["id"]]["decision"] == "executed" and prev["outcome"]["r_net"] < 0:
            after_loss += 1; after_loss_sk += ex_by[cur["id"]]["decision"] == "skipped"
    if after_loss >= 5 and after_loss_sk / after_loss > 0.7:
        flags.append({"flag": "loss_aversion", "text": f"After a losing executed trade you skipped the next card {after_loss_sk}/{after_loss} times."})
    return flags or [{"flag": "none", "text": "No decision bias detected at the current sample size."}]


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="session date to generate for (default: next session from today)")
    ap.add_argument("--no-generate", action="store_true")
    args = ap.parse_args()
    today = date.today()
    session_date = date.fromisoformat(args.date) if args.date else next_session(today)

    pulled = supabase_io.hydrate(DATA)
    if pulled:
        print(f"hydrated from Supabase: {', '.join(pulled)}", file=sys.stderr)
    fx = eurusd(); vix = vix_level()
    cards = load_json(CARDS_PATH, [])
    state = load_state()
    for c in cards:  # backfill fields for cards created before the two-tier release
        c.setdefault("tier", C.SETUPS.get(c["setup_id"], {}).get("tier", "base"))
        c.setdefault("rank", None); c.setdefault("signals", [])
        c["size"].setdefault("tier", c["tier"])
        c["size"].setdefault("risk_pct_of_capital", (c["size"]["risk_usd"] / (C.CAPITAL_EUR * fx)) if c["size"]["units"] else 0)
        c["size"].setdefault("notional_pct_of_capital", c["size"]["notional_usd"] / (C.CAPITAL_EUR * fx))
        if "execution" not in c:
            c["execution"] = execution.build(c)

    # 1) score and learn
    changed = score_cards(cards, today, fx)
    for c in changed:
        if c["status"] in ("target", "stopped", "expired"):
            record_outcome(state, c)
    # 2) generate
    new = [] if args.no_generate else generate(cards, state, session_date, fx, vix)
    cards.extend(new)
    market_context = apply_analyst_notes(cards, session_date)
    # 3) persist
    save_state(state)
    with open(CARDS_PATH, "w") as f:
        json.dump(cards, f, indent=1, default=str)
    executions = []
    if supabase_io.enabled():
        try:
            executions = supabase_io.read_executions()
        except Exception as e:  # noqa
            print(f"warning: could not read executions from Supabase: {e}", file=sys.stderr)
    metrics = compute_metrics(cards, fx, executions)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=1, default=str)
    todays = [c for c in cards if c["session_date"] == str(session_date)]
    open_cards = [c for c in cards if c["status"] in OPEN_STATUSES and c["session_date"] != str(session_date)]
    blackout = C.MACRO_EVENTS.get(session_date)
    upcoming = [{"date": str(d), "event": e} for d, e in sorted(C.MACRO_EVENTS.items())
                if session_date <= d <= session_date + timedelta(days=10)]
    today_view = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session_date": str(session_date), "fx_eurusd": fx, "vix": vix, "regime": regime_for(vix),
        "capital_eur": C.CAPITAL_EUR, "capital_usd": round(C.CAPITAL_EUR * fx, 2),
        "blackout": blackout, "upcoming_events": upcoming, "market_context": market_context,
        "recommended": sorted([c for c in todays if c["recommended"]], key=lambda c: c["rank"] or 999),
        "shadow": sorted([c for c in todays if not c["recommended"]], key=lambda c: c["rank"] or 999),
        "tiers": C.TIERS, "pdt_applies": C.PDT_APPLIES,
        "open_positions": open_cards,
        "scored_today": [c["id"] for c in changed],
        "limits": {"risk_per_trade_pct": C.RISK_PER_TRADE_PCT, "risk_per_trade_fut_pct": C.RISK_PER_TRADE_FUT_PCT,
                   "max_daily_loss_eur": round(C.CAPITAL_EUR * C.MAX_DAILY_LOSS_PCT, 2),
                   "max_weekly_loss_eur": round(C.CAPITAL_EUR * C.MAX_WEEKLY_LOSS_PCT, 2),
                   "min_expectancy_r": C.MIN_EXPECTANCY_R, "pdt_intraday_stock_trades_per_week": C.PDT_INTRADAY_STOCK_TRADES_PER_WEEK,
                   "max_total_open_risk_pct": C.MAX_TOTAL_OPEN_RISK_PCT, "max_correlated_positions": C.MAX_CORRELATED_POSITIONS},
    }
    with open(TODAY_PATH, "w") as f:
        json.dump(today_view, f, indent=1, default=str)
    if supabase_io.enabled():
        try:
            notes = load_json(NOTES_PATH, None)
            for key, payload in (("today", today_view), ("cards", cards), ("metrics", metrics), ("state", state), ("analyst_notes", notes)):
                if payload is not None:
                    supabase_io.write_snapshot(key, json.loads(json.dumps(payload, default=str)))
            # mark served refresh requests
            try:
                supabase_io.mark_refresh_done()
            except Exception as e:  # noqa
                print(f"refresh_requests update skipped: {e}", file=sys.stderr)
            print("published to Supabase", file=sys.stderr)
        except Exception as e:  # noqa
            print(f"warning: Supabase publish failed: {e}", file=sys.stderr)
    print(json.dumps({"session_date": str(session_date), "scored": len(changed), "new_cards": len(new),
                      "recommended": len(today_view["recommended"]), "shadow": len(today_view["shadow"]),
                      "vix": vix, "fx": fx, "blackout": blackout}, indent=2))


if __name__ == "__main__":
    main()
