"""Configuration for the daily recommendation engine.

Everything here is a deliberate, inspectable assumption. Values marked
VERIFY should be checked against your live IBKR account before relying on them.
"""
from datetime import date

# ----------------------------------------------------------------- capital & risk
CAPITAL_EUR = 5000.0
RISK_PER_TRADE_PCT = 0.010         # 1.0% of capital at the stop (swing)
RISK_PER_TRADE_FUT_PCT = 0.015     # 1.5% allowed for one micro contract (smallest unit)
MAX_DAILY_LOSS_PCT = 0.02          # stop trading for the day
MAX_WEEKLY_LOSS_PCT = 0.04         # stop trading for the week
MAX_CARDS_PER_DAY = 4
MAX_FUTURES_CARDS = 2
MAX_SWING_CARDS = 2
MAX_LEVERAGE = 1.0                 # no margin for stock/ETF swings in year one
MIN_EXPECTANCY_R = 0.10            # card recommended only if expectancy after costs >= 0.10R
PDT_APPLIES = False                # user confirmed account is not under US pattern-day-trader rules (2026-11-05)
PDT_INTRADAY_STOCK_TRADES_PER_WEEK = None if not PDT_APPLIES else 3

# ----------------------------------------------------------------- two-tier allocation
# BASE: majority of risk budget, setups with multi-year evidence. TAIL: small size, high payoff asymmetry.
TIERS = {
    "base": {"label": "Base trade", "risk_pct": 0.010, "max_open": 3, "max_total_risk_pct": 0.030,
              "min_rr": 1.5, "description": "Core allocation. Setups with the strongest evidence; 1% of capital at risk per trade, max 3 open, 3% total open risk."},
    "tail": {"label": "Tail trade", "risk_pct": 0.004, "max_open": 2, "max_total_risk_pct": 0.008,
              "min_rr": 3.0, "description": "Asymmetric bets: low hit rate, large winners. 0.4% of capital at risk per trade, max 2 open, 0.8% total. A single failure costs under one-half percent of capital."},
}
MAX_TOTAL_OPEN_RISK_PCT = 0.035     # base + tail combined
MAX_CORRELATED_POSITIONS = 2        # per correlation cluster (see CLUSTERS)
CLUSTERS = {
    "us_index": ["SPY", "QQQ", "IWM", "DIA", "ES=F", "NQ=F", "XLK", "SMH"],
    "mega_tech": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "NFLX", "XLK", "SMH", "QQQ", "NQ=F"],
    "metals": ["GLD", "SLV", "GC=F"],
    "rates": ["TLT"],
    "energy": ["XLE", "XOM"],
    "financials": ["XLF", "JPM", "BRK-B", "V"],
    "health": ["XLV", "UNH", "LLY"],
    "consumer": ["COST", "WMT"],
}

# ----------------------------------------------------------------- costs (USD)
FUT_COMMISSION_PER_SIDE = 1.24     # IBKR Pro micro: $0.25 comm + CME/NFA fees (VERIFY)
STOCK_COMMISSION_MIN = 1.00        # IBKR fixed: $0.005/share, min $1 per order (VERIFY)
STOCK_COMMISSION_PER_SHARE = 0.005
STOCK_SPREAD_PCT = 0.0002          # 2 bp assumed half-spread+slippage per side
FUT_SLIPPAGE_TICKS = 1             # per side

# ----------------------------------------------------------------- universes
FUTURES = {
    # yfinance data symbol -> IBKR micro contract to trade
    "ES=F": {"ibkr": "MES", "name": "Micro E-mini S&P 500", "point_value": 5.0, "tick": 0.25,
              "overnight_margin_usd": 2900, "note": "Data from ES=F (identical prices)."},
    "NQ=F": {"ibkr": "MNQ", "name": "Micro E-mini Nasdaq-100", "point_value": 2.0, "tick": 0.25,
              "overnight_margin_usd": 4200, "note": "Data from NQ=F (identical prices)."},
    "GC=F": {"ibkr": "MGC", "name": "Micro Gold", "point_value": 10.0, "tick": 0.10,
              "overnight_margin_usd": 1900, "note": "Data from GC=F (identical prices)."},
}

SWING_UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "TLT", "XLE", "XLF", "XLK", "XLV", "SMH",
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "XOM",
    "UNH", "LLY", "COST", "NFLX", "AMD", "BRK-B", "V", "WMT",
]

# ----------------------------------------------------------------- sessions (US/Eastern)
RTH_OPEN = "09:30"
RTH_CLOSE = "16:00"
FUT_TRIGGER_LAST = "15:00"   # no new triggers after this
FUT_FLAT_BY = "15:55"        # flat before IBKR intraday-margin cutoff (15:15 CT = 16:15 ET)

# ----------------------------------------------------------------- macro blackout calendar
# Tier-1 US releases. Futures day cards are NOT issued on these dates; swing cards are flagged.
# Sources: BLS release schedule, Federal Reserve FOMC calendar (checked 2026-11-04).
MACRO_EVENTS = {
    date(2026, 11, 6): "US Employment Situation (NFP) 08:30 ET",
    date(2026, 11, 10): "US CPI (Oct) 08:30 ET",
    date(2026, 12, 4): "US Employment Situation (NFP) 08:30 ET",
    date(2026, 12, 9): "FOMC decision + projections 14:00 ET",
    date(2026, 12, 10): "US CPI (Nov) 08:30 ET",
    date(2027, 1, 8): "US Employment Situation (NFP) 08:30 ET",
    date(2027, 1, 13): "US CPI (Dec) 08:30 ET",
}

# ----------------------------------------------------------------- setups
SETUPS = {
    "FUT_PDR_BREAKOUT": {
        "name": "Futures prior-day range breakout",
        "kind": "futures_day",
        "description": "Stop-entry beyond the prior RTH session high (long, if above 20-day average) "
                       "or low (short, if below). Stop = 20% of the 10-day average RTH range, "
                       "target = 40%. Flat by 15:55 ET. No entries after 15:00 ET.",
        "stop_frac": 0.20, "target_frac": 0.40, "range_lookback": 10,
    },
    "SWING_PULLBACK": {
        "name": "Swing pullback in uptrend",
        "kind": "swing",
        "description": "Close above 50-day and 200-day averages, RSI(2) below 10. Buy limit at "
                       "yesterday's close, stop 2 ATR below, target 2 ATR above, time exit after 5 sessions.",
        "stop_atr": 2.0, "target_atr": 2.0, "horizon_days": 5, "rsi_max": 10,
    },
    "SWING_BREAKOUT": {
        "name": "Swing 20-day breakout with volume",
        "kind": "swing",
        "description": "Close at a 20-day high on volume 1.5x the 20-day average and above the 50-day "
                       "average. Buy stop just above the high, stop 1.5 ATR below, target 3 ATR above, "
                       "time exit after 10 sessions.",
        "stop_atr": 1.5, "target_atr": 3.0, "horizon_days": 10, "vol_mult": 1.5,
    },
    "SWING_BREAKOUT_RUNNER": {
        "name": "Breakout runner (tail)",
        "kind": "swing", "tier": "tail",
        "description": "Same 20-day breakout signal, but held for the trend: stop 1.5 ATR below, target "
                       "6 ATR above (4:1 reward to risk), time exit after 30 sessions. Low hit rate, "
                       "large winners. Backtest 2021-2026: +0.36R in-sample (n=249), +0.31R out-of-sample "
                       "2025-26 (n=120); most of the gain comes from trend drift at the time exit, not target hits.",
        "stop_atr": 1.5, "target_atr": 6.0, "horizon_days": 30, "vol_mult": 1.5,
    },
    "OPT_RUNNER": {
        "name": "Defined-risk option on breakout (tail)",
        "kind": "option_swing", "tier": "tail", "model_based": True, "structure_setup": True,
        "description": "Same 20-day breakout signal as the runner, expressed as a long call or a call debit spread "
                       "with 55-100 days to expiry. Maximum loss is the premium paid, known in advance. "
                       "Payoff is estimated by pricing the runner's backtested exit distribution (n>=100 paths) "
                       "with the Black-Scholes model at the current implied volatility; there is no historical "
                       "option price backtest, so it is model-based until its own live record exists.",
        "stop_atr": 1.5, "target_atr": 6.0, "horizon_days": 30, "vol_mult": 1.5,
    },
    "EVENT_SCOUT": {
        "name": "Event / news scout (discretionary)",
        "kind": "swing", "tier": "tail", "discretionary": True,
        "description": "Proposed by the morning analyst review from news, earnings, macro or momentum. "
                       "Has no backtest, so it starts with a sceptical prior and stays in shadow until its "
                       "own live record earns promotion (>= +0.10R posterior expectancy after costs).",
        "prior": {"p": 0.40, "win_r": 1.60, "loss_r": -1.05, "n": 0},
        "horizon_days": 10,
    },
}
for _sid, _s in SETUPS.items():
    _s.setdefault("tier", "base")

# ----------------------------------------------------------------- trade structures (tail trades)
# How a signal can be expressed. risk_class: "defined" = maximum loss fixed at entry (premium / amount paid);
# "stop_based" = loss normally limited by the stop but a gap can exceed it; "open_ended" = loss can exceed the
# margin or stake posted. Permissions must be enabled in IBKR Client Portal -> Settings -> Trading Permissions.
STRUCTURES = {
    "shares": {"label": "Shares / ETF", "risk_class": "stop_based", "loss_can_exceed_stake": False,
               "permission": "Stocks (United States)", "generated": True,
               "note": "Loss is limited by the stop order; an overnight gap through the stop can make it larger. Never more than the amount invested."},
    "long_call": {"label": "Long call option", "risk_class": "defined", "loss_can_exceed_stake": False,
                  "permission": "Options (United States), level allowing long calls/puts", "generated": True,
                  "note": "Maximum loss = premium paid, fixed at entry. Time decay works against the position; a flat underlying loses money."},
    "long_put": {"label": "Long put option", "risk_class": "defined", "loss_can_exceed_stake": False,
                 "permission": "Options (United States), level allowing long calls/puts", "generated": True,
                 "note": "Maximum loss = premium paid. Used for short signals instead of selling shares short."},
    "debit_spread": {"label": "Vertical debit spread", "risk_class": "defined", "loss_can_exceed_stake": False,
                     "permission": "Options (United States), level allowing spreads", "generated": True,
                     "note": "Buy one option, sell a further-out-of-the-money one. Lower premium and lower maximum loss than the long option, but the gain is capped at the short strike."},
    "leveraged_etf": {"label": "Leveraged ETF (2x/3x)", "risk_class": "stop_based", "loss_can_exceed_stake": False,
                      "permission": "Complex or Leveraged Exchange Traded Products", "generated": False,
                      "note": "Evaluated, not generated: for the same euro risk it only reduces the capital tied up, while daily rebalancing and wider spreads lower the expected return. Shares or options are preferred."},
    "micro_futures": {"label": "Micro futures", "risk_class": "open_ended", "loss_can_exceed_stake": True,
                      "permission": "Futures (United States)", "generated": True,
                      "note": "Loss can exceed the margin posted if the market gaps through the stop. Day cards only, flat before the close."},
    "cfd": {"label": "CFD", "risk_class": "open_ended", "loss_can_exceed_stake": True,
            "permission": "CFDs (not available to US residents)", "generated": False,
            "note": "Evaluated, not generated: an IBKR share CFD mirrors the share price with ~20% margin and daily financing, so the share card already defines the trade; the CFD only adds leverage and open-ended loss."},
}
# Defined-risk (option) tail trades. The maximum loss is the premium, so the premium IS the risk budget.
# With EUR 5,000 capital one US option contract on a $50-$200 underlying costs 2-10% of capital; a 0.4% budget
# (EUR 20) buys nothing liquid. The cap below is therefore a deliberate, separate budget. REVIEW before live use.
OPTIONS = {
    "max_premium_pct": 0.03,         # max loss per defined-risk tail trade = 3% of capital (EUR 150)
    "max_total_premium_pct": 0.06,   # all open defined-risk tail trades together
    "max_open": 2,
    "min_rr": 3.0,                   # payoff at the underlying target vs premium
    "dte_min": 55, "dte_max": 100,   # horizon 30 sessions ~ 42 calendar days + buffer
    "delta_lo": 0.30, "delta_hi": 0.55,
    "max_spread_pct": 0.15,          # (ask-bid)/mid of the contract
    "min_open_interest": 200,
    "commission_per_contract": 0.65, # IBKR Pro US options, per contract per side (min $1 per order) (VERIFY)
    "risk_free": 0.04,
    "model_prior_strength": 20,      # model-based prior counts as 20 pseudo-observations (half of a backtested one)
    "min_paths": 100,                # minimum backtested underlying paths to price a structure
}
OPTION_UNDERLYINGS = ["SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "TLT", "XLE", "XLF", "XLK", "XLV", "SMH",
                      "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "XOM", "JPM"]
INSTRUMENT_NAMES = {
    "SPY": "SPDR S&P 500 ETF Trust", "QQQ": "Invesco QQQ Trust (Nasdaq-100)", "IWM": "iShares Russell 2000 ETF",
    "DIA": "SPDR Dow Jones Industrial Average ETF", "GLD": "SPDR Gold Shares", "SLV": "iShares Silver Trust",
    "TLT": "iShares 20+ Year Treasury Bond ETF", "XLE": "Energy Select Sector SPDR Fund",
    "XLF": "Financial Select Sector SPDR Fund", "XLK": "Technology Select Sector SPDR Fund",
    "XLV": "Health Care Select Sector SPDR Fund", "SMH": "VanEck Semiconductor ETF",
    "AAPL": "Apple Inc.", "MSFT": "Microsoft Corporation", "NVDA": "NVIDIA Corporation", "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc. Class A", "META": "Meta Platforms, Inc.", "TSLA": "Tesla, Inc.", "AVGO": "Broadcom Inc.",
    "JPM": "JPMorgan Chase & Co.", "XOM": "Exxon Mobil Corporation", "UNH": "UnitedHealth Group Incorporated",
    "LLY": "Eli Lilly and Company", "COST": "Costco Wholesale Corporation", "NFLX": "Netflix, Inc.",
    "AMD": "Advanced Micro Devices, Inc.", "BRK-B": "Berkshire Hathaway Inc. Class B", "V": "Visa Inc. Class A",
    "WMT": "Walmart Inc.",
    "MES": "Micro E-mini S&P 500 futures", "MNQ": "Micro E-mini Nasdaq-100 futures", "MGC": "Micro Gold futures",
}

# ----------------------------------------------------------------- learning
PRIOR_STRENGTH = 40          # backtest prior counts as 40 pseudo-observations
MIN_LIVE_FOR_SUSPEND = 30    # need >= 30 live outcomes before a setup can be suspended
SUSPEND_EXPECTANCY_R = 0.0   # suspend if posterior expectancy after costs < 0
PROBATION_EXPECTANCY_R = 0.10
VIX_REGIMES = [(0, 15, "low_vol"), (15, 25, "mid_vol"), (25, 999, "high_vol")]
