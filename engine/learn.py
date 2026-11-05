"""Learning loop: Bayesian update of each setup's hit rate and payoff from completed cards.

State file: data/state.json
  setups[setup_id][regime] = {prior_n, prior_p, prior_win_r, prior_loss_r, live_n, live_hits,
                              live_win_r_sum, live_loss_r_sum, live_r_sum, status}
  changelog = [{date, setup, regime, change, reason}]
Probability used on a card = posterior mean of a Beta(prior_strength*p0, prior_strength*(1-p0))
updated with live hits/misses. Payoffs are shrunk toward the prior the same way.
"""
import json
import os
from datetime import date
from config import (PRIOR_STRENGTH, MIN_LIVE_FOR_SUSPEND, SUSPEND_EXPECTANCY_R,
                    PROBATION_EXPECTANCY_R, VIX_REGIMES, SETUPS)

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA, "state.json")


def regime_for(vix: float) -> str:
    for lo, hi, name in VIX_REGIMES:
        if lo <= vix < hi:
            return name
    return "mid_vol"


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return {"version": 1, "setups": {}, "changelog": [], "calibrated_on": None}


def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def _blank(prior):
    return {**prior, "live_n": 0, "live_hits": 0, "live_win_r_sum": 0.0, "live_loss_r_sum": 0.0,
            "live_wins": 0, "live_losses": 0, "live_r_sum": 0.0, "status": "active"}


def set_priors(state, setup_id: str, regime: str, outcomes: list):
    """Priors from backtest outcomes (triggered trades only)."""
    trig = [o for o in outcomes if o["status"] not in ("not_triggered", "gap_cancelled")]
    if len(trig) < 15:
        return
    wins = [o["r"] for o in trig if o["r"] > 0]
    losses = [o["r"] for o in trig if o["r"] <= 0]
    prior = {
        "prior_n": len(trig),
        "prior_p": len(wins) / len(trig),
        "prior_win_r": (sum(wins) / len(wins)) if wins else 0.0,
        "prior_loss_r": (sum(losses) / len(losses)) if losses else -1.0,
        "prior_trigger_rate": len(trig) / len(outcomes),
        "prior_signals": len(outcomes),
    }
    cur = state["setups"].setdefault(setup_id, {}).get(regime)
    if cur:
        cur.update(prior)
    else:
        state["setups"][setup_id][regime] = _blank(prior)


def posterior(state, setup_id: str, regime: str):
    bucket = state["setups"].get(setup_id, {})
    s = bucket.get(regime)
    used = regime
    if not s or s["prior_n"] < 50:
        s = bucket.get("all"); used = "all"
    if not s and SETUPS.get(setup_id, {}).get("prior"):
        # discretionary setup without backtest: configured sceptical prior, live record only
        pr = SETUPS[setup_id]["prior"]
        state["setups"].setdefault(setup_id, {})["all"] = _blank({"prior_n": pr["n"], "prior_p": pr["p"],
            "prior_win_r": pr["win_r"], "prior_loss_r": pr["loss_r"], "prior_trigger_rate": None, "prior_signals": 0})
        s = state["setups"][setup_id]["all"]; used = "all"
    if not s:
        return None
    a0 = PRIOR_STRENGTH * s["prior_p"]
    b0 = PRIOR_STRENGTH * (1 - s["prior_p"])
    p = (a0 + s["live_hits"]) / (PRIOR_STRENGTH + s["live_n"])
    # shrink payoffs toward prior with the same pseudo-count
    win_r = ((PRIOR_STRENGTH * s["prior_win_r"] + s["live_win_r_sum"]) /
             (PRIOR_STRENGTH + s["live_wins"]))
    loss_r = ((PRIOR_STRENGTH * s["prior_loss_r"] + s["live_loss_r_sum"]) /
              (PRIOR_STRENGTH + s["live_losses"]))
    exp_r = p * win_r + (1 - p) * loss_r
    return {"p": p, "win_r": win_r, "loss_r": loss_r, "expectancy_r": exp_r,
            "live_n": s["live_n"], "prior_n": s["prior_n"], "status": s["status"],
            "regime_used": used}


def record_outcome(state, card: dict):
    """Update live counts from a completed card (status in target/stopped/expired)."""
    setup_id, regime = card["setup_id"], card.get("regime", "all")
    r = card["outcome"]["r_net"]
    for key in {regime, "all"}:
        s = state["setups"].setdefault(setup_id, {}).get(key)
        if not s:
            continue
        s["live_n"] += 1
        s["live_r_sum"] += r
        if r > 0:
            s["live_hits"] += 1; s["live_wins"] += 1; s["live_win_r_sum"] += r
        else:
            s["live_losses"] += 1; s["live_loss_r_sum"] += r
    review_status(state, setup_id, regime)


def review_status(state, setup_id: str, regime: str):
    today = str(date.today())
    for key in {regime, "all"}:
        s = state["setups"].get(setup_id, {}).get(key)
        if not s:
            continue
        post = posterior(state, setup_id, key)
        old = s["status"]
        new = old
        if s["live_n"] >= MIN_LIVE_FOR_SUSPEND and post["expectancy_r"] < SUSPEND_EXPECTANCY_R:
            new = "suspended"
        elif s["live_n"] >= 15 and post["expectancy_r"] < PROBATION_EXPECTANCY_R:
            new = "probation"
        elif old in ("probation", "suspended") and post["expectancy_r"] >= PROBATION_EXPECTANCY_R:
            new = "active"
        if new != old:
            s["status"] = new
            state["changelog"].append({
                "date": today, "setup": setup_id, "regime": key, "change": f"{old} -> {new}",
                "reason": (f"Posterior expectancy {post['expectancy_r']:+.2f}R after {s['live_n']} live "
                           f"outcomes (hit rate {post['p']:.0%})."),
            })


def log_change(state, setup, regime, change, reason):
    state["changelog"].append({"date": str(date.today()), "setup": setup, "regime": regime,
                               "change": change, "reason": reason})
