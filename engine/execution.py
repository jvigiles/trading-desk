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
    if card["kind"] == "option_swing":
        return build_option(card)
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


def build_option(card: dict) -> dict:
    """IBKR walkthrough for a defined-risk option structure (long call/put or vertical debit spread)."""
    inst, lv, size, o = card["instrument"], card["levels"], card["size"], card["option"]
    long_side = card["side"] == "long"
    right_word = "Call" if o["right"] == "C" else "Put"
    spread = bool(o.get("short_strike"))
    debit = o["debit_per_share"]
    prem = o["premium_usd"]
    exp = date.fromisoformat(o["expiry"]).strftime("%d %b %Y")
    strikes = f"{o['long_strike']:g}" + (f" / {o['short_strike']:g}" if spread else "")
    label = ("Bull call spread" if spread and o["right"] == "C" else "Bear put spread" if spread else f"Long {right_word.lower()}")
    description = (f"{inst['name']} ({inst['symbol']}) option: {label}, expiry {exp}, strike{'s' if spread else ''} {strikes}, "
                   f"1 contract = 100 shares, USD")
    contract_line = (f"Buy {o['long_contract']}" + (f" / Sell {o['short_contract']}" if spread else ""))
    instrument = {
        "ibkr_symbol": inst["symbol"], "contract": o["long_contract"] if not spread else f"{o['long_contract']} / {o['short_contract']}",
        "exchange": "SMART (US options)", "description": description,
        "search_hint": (f"Type {inst['symbol']} in the search box, choose 'Options' (not the stock), open the option chain, pick the "
                        f"{exp} expiry and the {strikes} {right_word.lower()}{'s' if spread else ''}. OCC contract: {contract_line}."),
    }
    order = {
        "action": "BUY", "quantity": 1, "order_type": "LMT", "entry_price": debit, "time_in_force": "DAY",
        "attached": [], "oca": False,
        "condition": f"Place only after {inst['symbol']} trades {'above' if long_side else 'below'} {lv['entry']:.2f} (the underlying trigger).",
        "legs": ([{"action": "BUY", "right": right_word, "strike": o["long_strike"], "expiry": o["expiry"]}] +
                 ([{"action": "SELL", "right": right_word, "strike": o["short_strike"], "expiry": o["expiry"]}] if spread else [])),
    }
    tws = [
        f"Wait for the trigger: {inst['symbol']} must trade {'above' if long_side else 'below'} {lv['entry']:.2f} during regular hours "
        f"(set a price alert in TWS: Alerts → New Alert → {inst['symbol']} last {'>' if long_side else '<'} {lv['entry']:.2f}).",
        f"Search '{inst['symbol']}' → Options → Option Chain. Select expiry {exp}.",
        (f"Use the Strategy Builder: Buy the {o['long_strike']:g} {right_word}, Sell the {o['short_strike']:g} {right_word} (same expiry). "
         f"The combo shows as a {label.lower()} with a net debit." if spread else
         f"Click the Ask of the {o['long_strike']:g} {right_word} to create a BUY order."),
        f"Order Type = LMT, Limit Price = {debit:.2f} (net debit per share; you pay up to ${prem:,.0f} plus commission), Quantity = 1, Time in Force = DAY.",
        f"If the ask is above {debit*1.15:.2f}, do not chase: cancel. The expected value is gone at a higher price.",
        "Preview → check 'Max loss' equals the debit (defined risk) → Transmit.",
        f"Management: there is no stop order. Sell the {'spread' if spread else 'option'} at market (or mid) when {inst['symbol']} trades at {lv['stop']:.2f} "
        f"(partial loss, modelled {o['scenarios_usd']['at_stop']:+,.0f} USD), when it reaches {lv['target']:.2f} "
        f"(modelled {o['scenarios_usd']['at_target']:+,.0f} USD), or after {lv['horizon_days']} sessions, whichever comes first.",
        "Set two alerts in TWS for the stop and target levels so you are notified. Never hold into the last two weeks before expiry.",
    ]
    mobile = [
        f"Set a price alert for {inst['symbol']} {'above' if long_side else 'below'} {lv['entry']:.2f} (Watchlist → tap symbol → Alerts).",
        f"When triggered: search '{inst['symbol']}' → Options → expiry {exp} → {right_word}s → strike {o['long_strike']:g}" +
        (f"; then use 'Add leg' / Strategy to SELL the {o['short_strike']:g} {right_word} (or place the two legs one after the other, buying first)." if spread else "."),
        f"Tap Buy → Order type Limit → Limit price {debit:.2f}{' (net debit)' if spread else ''} → Quantity 1 → Time in force Day → Review → Slide to submit.",
        f"Add alerts for {lv['stop']:.2f} and {lv['target']:.2f}. Sell the position when either prints or after {lv['horizon_days']} sessions.",
    ]
    risk_usd = prem
    return {
        "instrument": instrument,
        "order": order,
        "capital": {
            "notional_usd": round(prem, 2), "notional_pct_of_capital": round(100 * size.get("notional_pct_of_capital", 0), 1),
            "risk_usd": round(risk_usd, 2), "risk_pct_of_capital": round(100 * o["premium_pct_of_capital"], 2),
            "tier": "tail", "margin_note": "No margin: the debit is paid in full. Nothing further can be lost.",
        },
        "risk_reward": {
            "stop_distance": round(abs(lv["entry"] - lv["stop"]), 2), "target_distance": round(abs(lv["target"] - lv["entry"]), 2),
            "ratio": round(o["payoff_ratio_at_target"], 2) if o.get("payoff_ratio_at_target") is not None else None,
            "max_planned_loss_usd": round(-prem, 2),
            "planned_gain_usd": round(o["scenarios_usd"]["at_target"], 2),
            "est_costs_usd": round(o["cost_r"] * prem, 2),
            "scenarios_usd": o["scenarios_usd"], "max_gain_usd": o.get("max_gain_usd"), "breakeven": o.get("breakeven"),
        },
        "steps_tws": tws, "steps_mobile": mobile,
        "paper_note": ("Paper accounts fill option limit orders when the quote trades through the limit; option quotes are "
                       "delayed 15 minutes in this app, so check the live bid/ask in IBKR before placing the order."),
        "pre_checks": [
            "Confirm the account selector shows the PAPER account (badge 'Paper' / account id starting with DU).",
            f"Confirm US options trading permission is enabled{' at a level that allows spreads' if spread else ''} "
            "(Client Portal → Settings → Trading Permissions → Options → United States).",
            "Confirm you can afford to lose the whole premium: that is the defined maximum loss of this trade.",
            "Check the live bid/ask: this card was built from delayed quotes.",
        ],
    }
