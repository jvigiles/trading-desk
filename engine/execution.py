"""IBKR execution instructions generated per card.

Everything here is a template filled with the card's own numbers. Order types and field names follow
IBKR's Trader Workstation (TWS) and IBKR Mobile naming. Verify once in the paper account that the
fields match your interface version; IBKR changes layouts occasionally.
"""
from datetime import date

# CME micro futures: month codes and quarterly roll (H=Mar, M=Jun, U=Sep, Z=Dec). Index micros trade
# quarterly; Micro Gold (MGC) has monthly contracts but the most liquid are Feb/Apr/Jun/Aug/Oct/Dec.
_QUARTERLY = {3: "H", 6: "M", 9: "U", 12: "Z"}
_MGC_MONTHS = {2: "G", 4: "J", 6: "M", 8: "Q", 10: "V", 12: "Z"}


def front_month(symbol: str, d: date) -> str:
    """Return e.g. 'MESZ6' for the front quarterly contract (rolls ~8 days before the 3rd Friday)."""
    months = _MGC_MONTHS if symbol == "MGC" else _QUARTERLY
    y, m = d.year, d.month
    for _ in range(14):
        if m in months:
            # expiry: 3rd Friday of month m (index) / ~ end of month for gold; roll a week before
            third_fri = _third_friday(y, m)
            if d < third_fri.replace(day=max(1, third_fri.day - 8)) or m != d.month:
                return f"{symbol}{months[m]}{str(y)[-1]}"
        m += 1
        if m > 12:
            m = 1; y += 1
    return symbol


def _third_friday(y, m):
    d = date(y, m, 15)
    while d.weekday() != 4:
        d = d.replace(day=d.day + 1)
    return d


def _fmt(x, tick=None):
    if tick and tick >= 0.1:
        return f"{x:.2f}"
    return f"{x:.2f}"


def build(card: dict) -> dict:
    """Return the execution block for a card."""
    inst, lv, size = card["instrument"], card["levels"], card["size"]
    side = card["side"]
    long = side == "long"
    units = size["units"]
    sd = date.fromisoformat(card["session_date"])

    if card["kind"] == "futures_day":
        contract = front_month(inst["symbol"], sd)
        entry_type = "STP" if lv["entry_type"] == "stop" else "LMT"
        action = "BUY" if long else "SELL"
        close_action = "SELL" if long else "BUY"
        instrument = {
            "ibkr_symbol": inst["symbol"], "contract": contract, "exchange": "CME",
            "description": f"{inst['name']} ({contract}), CME, USD, {inst['point_value']:g} USD per point, "
                           f"tick {inst['tick']}",
            "search_hint": f"Type {inst['symbol']} in the TWS/Mobile search box, choose Futures → CME, pick the {contract} contract.",
        }
        order = {
            "action": action, "quantity": units, "order_type": entry_type, "entry_price": lv["entry"],
            "time_in_force": "DAY",
            "attached": [
                {"role": "stop_loss", "action": close_action, "order_type": "STP", "price": lv["stop"]},
                {"role": "take_profit", "action": close_action, "order_type": "LMT", "price": lv["target"]},
            ],
            "oca": True,
        }
        tws = [
            f"Open the {contract} contract (search '{inst['symbol']}', Futures, CME).",
            f"Click {action}. Set Quantity = {units}, Order Type = {entry_type}, "
            f"{'Stop' if entry_type == 'STP' else 'Limit'} Price = {lv['entry']:.2f}, Time in Force = DAY.",
            "Click 'Advanced' (or the + next to the order) → 'Bracket' (Attach: Profit Taker + Stop Loss).",
            f"Profit Taker: {close_action} LMT at {lv['target']:.2f}. Stop Loss: {close_action} STP at {lv['stop']:.2f}. "
            "Both must be 'OCA' (one cancels the other) — Bracket does this automatically.",
            "Preview: check margin impact < 40% of account value, then Transmit.",
            f"If the market opens beyond {lv['entry']:.2f} before your order is live, do NOT place it (gap-through rule).",
            "Set a phone alarm for 21:50 CET. If the position is still open at 21:55 CET, close it at market (right-click position → Close).",
        ]
        mobile = [
            f"Search '{inst['symbol']}' → Futures → select {contract}.",
            f"Tap {action} → Order type {entry_type} → {'Stop' if entry_type == 'STP' else 'Limit'} price {lv['entry']:.2f} → Quantity {units} → Time in force Day.",
            f"Tap 'Add Profit Taker / Stop Loss' (bracket): Profit Taker LMT {lv['target']:.2f}, Stop Loss STP {lv['stop']:.2f}.",
            "Review → Slide to submit.",
            "Close at market by 21:55 CET if still open.",
        ]
        paper_note = ("In the paper account, fills on stop orders are simulated at the trigger price plus "
                      "a tick; real fills can be worse in fast markets.")
    else:
        entry_type = "STP" if lv["entry_type"] == "stop" else "LMT"
        action = "BUY" if long else "SELL"
        close_action = "SELL" if long else "BUY"
        instrument = {
            "ibkr_symbol": inst["symbol"], "contract": inst["symbol"], "exchange": "SMART (routes to NYSE/NASDAQ/ARCA)",
            "description": f"{inst.get('name', inst['symbol'])} — US {inst['type']}, USD, 1 share per unit",
            "search_hint": f"Type {inst['symbol']} in the search box and choose the US stock/ETF listing (SMART routing).",
        }
        horizon = lv.get("horizon_days")
        order = {
            "action": action, "quantity": units, "order_type": entry_type, "entry_price": lv["entry"],
            "time_in_force": "GTC" if lv.get("trigger_days", 1) > 1 else "DAY",
            "attached": [
                {"role": "stop_loss", "action": close_action, "order_type": "STP", "price": lv["stop"]},
                {"role": "take_profit", "action": close_action, "order_type": "LMT", "price": lv["target"]},
            ],
            "oca": True,
        }
        tif = order["time_in_force"]
        tws = [
            f"Open {inst['symbol']} (US {inst['type']}, SMART).",
            f"Click {action}. Quantity = {units}, Order Type = {entry_type}, "
            f"{'Stop' if entry_type == 'STP' else 'Limit'} Price = {lv['entry']:.2f}, Time in Force = {tif}"
            + (f" (valid {lv.get('trigger_days')} sessions; cancel manually if not filled)." if tif == "GTC" else "."),
            "Advanced → Bracket: attach Profit Taker and Stop Loss.",
            f"Profit Taker: {close_action} LMT {lv['target']:.2f}, GTC. Stop Loss: {close_action} STP {lv['stop']:.2f}, GTC.",
            "Tick 'Outside RTH' OFF for the stop (stops should only trigger in regular hours to avoid thin pre-market prints).",
            "Preview → Transmit.",
            f"Time exit: if still open after {horizon} sessions from fill, close at market near the close of that session "
            "and cancel the bracket.",
        ]
        mobile = [
            f"Search '{inst['symbol']}' → US {inst['type']}.",
            f"Tap {action} → Order type {entry_type} → price {lv['entry']:.2f} → Quantity {units} → Time in force {tif}.",
            f"Tap 'Add Profit Taker / Stop Loss': Profit Taker LMT {lv['target']:.2f}, Stop Loss STP {lv['stop']:.2f}.",
            "Review → Slide to submit.",
            f"Set a reminder for the time exit ({horizon} sessions after the fill).",
        ]
        paper_note = ("Paper accounts fill limit orders when the price trades through the level; a touch at exactly the "
                      "limit may not fill, so a missed fill in paper can differ from live.")

    risk_usd = size["risk_usd"] if units > 0 else size.get("risk_usd_1unit", 0)
    stop_dist = abs(lv["entry"] - lv["stop"]); tgt_dist = abs(lv["target"] - lv["entry"])
    return {
        "instrument": instrument,
        "order": order,
        "capital": {
            "notional_usd": round(size["notional_usd"], 2),
            "notional_pct_of_capital": round(100 * size.get("notional_pct_of_capital", 0), 1),
            "risk_usd": round(risk_usd, 2),
            "risk_pct_of_capital": round(100 * size.get("risk_pct_of_capital", 0), 2),
            "tier": size.get("tier", "base"),
        },
        "risk_reward": {
            "stop_distance": round(stop_dist, 2), "target_distance": round(tgt_dist, 2),
            "ratio": round(tgt_dist / stop_dist, 2) if stop_dist else None,
            "max_planned_loss_usd": round(-risk_usd, 2),
            "planned_gain_usd": round(risk_usd * tgt_dist / stop_dist, 2) if stop_dist else None,
            "est_costs_usd": round(size["cost_r"] * risk_usd, 2),
        },
        "steps_tws": tws,
        "steps_mobile": mobile,
        "paper_note": paper_note,
        "pre_checks": [
            "Confirm the account selector shows the PAPER account (badge 'Paper' / account id starting with DU).",
            "Confirm today's daily loss stop has not been hit (see Today → limits).",
            "Confirm the instrument's permissions are enabled in Account Settings → Trading Permissions "
            "(US stocks/ETFs; US futures for MES/MNQ/MGC).",
        ],
    }
