"""Build/refresh priors from historical simulation. Run once at setup and monthly thereafter."""
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from config import SETUPS, FUTURES, SWING_UNIVERSE, VIX_REGIMES
from data import daily, daily_many, intraday_5m
from setups import backtest_swing, backtest_futures
from learn import load_state, save_state, set_priors, regime_for, log_change, DATA
from risk import futures_cost_r, stock_cost_r


def net_r(o, kind, spec=None):
    """Apply the cost model to a simulated outcome so priors are net of costs."""
    if o["status"] in ("not_triggered", "gap_cancelled"):
        return 0.0
    sd = abs(o["entry"] - o["stop"])
    if kind == "futures_day":
        return o["r"] - futures_cost_r(spec, sd)
    # assume a typical 1%-risk position for cost purposes (shares sized on ~$5,500 capital)
    shares = max(1, int(55 / sd))
    return o["r"] - stock_cost_r(o["entry"], sd, shares)


def main():
    state = load_state()
    vix = daily("^VIX", "6y")["Close"]
    report = {}

    # ---- swing setups
    dd = daily_many(SWING_UNIVERSE, "6y")
    for sid, p in SETUPS.items():
        if p["kind"] != "swing" or p.get("discretionary"):
            continue
        outs = backtest_swing(sid, dd, vix)
        # keep the gross exit paths of tail setups: options.py prices option structures along them
        if p.get("tier") == "tail":
            state.setdefault("path_samples", {})[sid] = [
                {"r": round(float(o["r"]), 3), "d": int(o["days"]), "s": o["status"], "date": o["date"]}
                for o in outs if o["status"] not in ("not_triggered", "gap_cancelled")][-600:]
        for o in outs:
            o["r"] = net_r(o, "swing")
        set_priors(state, sid, "all", outs)
        for lo, hi, name in VIX_REGIMES:
            set_priors(state, sid, name, [o for o in outs if lo <= o["vix"] < hi])
        trig = [o for o in outs if o["status"] not in ("not_triggered", "gap_cancelled")]
        oos = [o for o in trig if o["date"] >= "2025-01-01"]; ins = [o for o in trig if o["date"] < "2025-01-01"]
        report[sid] = {"signals": len(outs), "triggered": len(trig),
                       "in_sample": {"n": len(ins), "avg_r_net": sum(o["r"] for o in ins) / max(1, len(ins))},
                       "out_of_sample_2025plus": {"n": len(oos), "avg_r_net": sum(o["r"] for o in oos) / max(1, len(oos))},
                       "tier": p.get("tier", "base"),
                       "hit_rate": sum(1 for o in trig if o["r"] > 0) / max(1, len(trig)),
                       "avg_r_net": sum(o["r"] for o in trig) / max(1, len(trig)),
                       "span": f"{min(o['date'] for o in outs)} to {max(o['date'] for o in outs)}" if outs else "n/a"}

    # ---- futures day setup (only ~60 days of 5m history available free)
    outs_all = []
    for sym, spec in FUTURES.items():
        df5 = intraday_5m(sym, "60d")
        dfd = daily(sym, "2y")
        if len(df5) and len(dfd):
            outs = backtest_futures(df5, dfd, spec, vix)
            for o in outs:
                o["r"] = net_r(o, "futures_day", spec)
            outs_all += outs
    set_priors(state, "FUT_PDR_BREAKOUT", "all", outs_all)
    for lo, hi, name in VIX_REGIMES:
        set_priors(state, "FUT_PDR_BREAKOUT", name, [o for o in outs_all if lo <= o["vix"] < hi])
    trig = [o for o in outs_all if o["status"] not in ("not_triggered", "gap_cancelled")]
    report["FUT_PDR_BREAKOUT"] = {"signals": len(outs_all), "triggered": len(trig),
                                  "hit_rate": sum(1 for o in trig if o["r"] > 0) / max(1, len(trig)),
                                  "avg_r_net": sum(o["r"] for o in trig) / max(1, len(trig)),
                                  "span": f"{min(o['date'] for o in outs_all)} to {max(o['date'] for o in outs_all)}" if outs_all else "n/a",
                                  "caveat": "Only ~60 days of intraday history available; low-confidence prior."}

    state["calibrated_on"] = str(date.today())
    state["calibration_report"] = report
    log_change(state, "ALL", "all", "priors recalibrated",
               "Historical simulation re-run on latest data (swing: ~6y daily; futures: ~60d intraday).")
    save_state(state)
    with open(os.path.join(DATA, "backtest_samples.json"), "w") as f:
        json.dump({"futures": outs_all[-300:]}, f, default=str)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
