export type Levels = {
  side: "long" | "short";
  entry_type: "stop" | "limit";
  entry: number;
  stop: number;
  target: number;
  horizon_days?: number;
  trigger_days?: number;
};

export type Card = {
  id: string;
  created_at: string;
  session_date: string;
  signal_date: string;
  kind: "futures_day" | "swing" | "option_swing";
  setup_id: string;
  setup_name: string;
  instrument: { symbol: string; name: string; type: string; currency: string; point_value?: number; tick?: number; multiplier?: number; underlying_type?: string };
  structure?: StructureId;
  risk_class?: RiskClass;
  model_based?: boolean;
  option?: OptionDetail;
  alternatives?: AlternativeRow[];
  data_symbol: string;
  side: "long" | "short";
  entry_type: "stop" | "limit";
  levels: Levels;
  size: {
    units: number;
    unit_label: string;
    risk_usd: number;
    risk_eur: number;
    cost_r: number;
    notional_usd: number;
    block_reason: string | null;
    risk_usd_1unit: number;
    risk_pct_of_capital?: number;
    notional_pct_of_capital?: number;
    tier?: string;
  };
  regime: string;
  prob_success: number;
  expectancy_r: number;
  expected_win_r: number;
  expected_loss_r: number;
  evidence: { prior_n: number; live_n: number; regime_used: string; setup_status: string };
  expected_gain_usd: number;
  expected_loss_usd: number;
  recommended: boolean;
  shadow_reason: string | null;
  rationale: string[];
  invalidation: string[];
  analyst: { note: string | null; veto: boolean };
  status: "pending" | "open" | "target" | "stopped" | "expired" | "not_triggered" | "gap_cancelled" | "vetoed";
  outcome: null | {
    scored_at: string;
    fill: number | null;
    exit_price: number | null;
    fill_time: string | null;
    exit_time: string | null;
    days: number | null;
    r_gross: number;
    r_net: number;
    pnl_usd: number;
    pnl_eur: number;
    hit: boolean | null;
    brier: number | null;
  };
  valid_until_et?: string;
  levels_meta?: Record<string, unknown>;
  tier: "base" | "tail";
  rank: number | null;
  signals: string[];
  execution?: ExecutionPlan;
};

export type StructureId = "shares" | "long_call" | "long_put" | "debit_spread" | "leveraged_etf" | "micro_futures" | "cfd";
export type RiskClass = "defined" | "stop_based" | "open_ended";

export type OptionDetail = {
  structure: StructureId; label: string; expiry: string; dte: number; right: "C" | "P";
  long_strike: number; short_strike: number | null; long_contract: string; short_contract: string | null;
  long_iv: number; long_delta: number;
  quote: { long_bid: number; long_ask: number; short_bid: number | null; short_ask: number | null; open_interest: number };
  debit_per_share: number; premium_usd: number; max_loss_usd: number; max_gain_usd: number | null; breakeven: number;
  premium_pct_of_capital: number; n_paths: number; p_win: number; win_r: number; loss_r: number; expectancy_r: number; cost_r: number;
  scenarios_usd: { at_target: number; at_stop: number; flat_at_time_exit: number };
  payoff_ratio_at_target: number | null;
};

export type AlternativeRow = {
  structure: StructureId; label: string; risk_class: RiskClass;
  capital_usd: number | null; max_loss_usd: number | null; max_loss_note?: string | null; gain_at_target_usd: number | null;
  p_win: number | null; expectancy_r: number | null; evidence?: string | null; permission?: string | null;
  generated: boolean; detail?: string | null; fits_budget?: boolean | null; chosen?: boolean | null; note?: string | null;
};

export type StructureCfg = { label: string; risk_class: RiskClass; generated: boolean; permission: string; note: string };
export type OptionsBudget = { max_premium_pct: number; max_total_premium_pct: number; max_open: number; min_rr: number; max_premium_eur: number };

export type ExecutionPlan = {
  instrument: { ibkr_symbol: string; contract: string; exchange: string; description: string; search_hint: string };
  order: {
    action: "BUY" | "SELL"; quantity: number; order_type: "STP" | "LMT"; entry_price: number; time_in_force: string;
    attached: { role: "stop_loss" | "take_profit"; action: "BUY" | "SELL"; order_type: "STP" | "LMT"; price: number }[];
    oca: boolean;
    condition?: string;
    legs?: { action: "BUY" | "SELL"; right: string; strike: number; expiry: string }[];
  };
  capital: { notional_usd: number; notional_pct_of_capital: number; risk_usd: number; risk_pct_of_capital: number; tier: string; margin_note?: string };
  risk_reward: { stop_distance: number; target_distance: number; ratio: number | null; max_planned_loss_usd: number; planned_gain_usd: number | null; est_costs_usd: number;
    scenarios_usd?: { at_target: number; at_stop: number; flat_at_time_exit: number }; max_gain_usd?: number | null; breakeven?: number | null };
  steps_tws: string[];
  steps_mobile: string[];
  paper_note: string;
  pre_checks: string[];
};

export type TierCfg = { label: string; risk_pct: number; max_open: number; max_total_risk_pct: number; min_rr: number; description: string };

export type TodayView = {
  run_at: string;
  session_date: string;
  fx_eurusd: number;
  vix: number;
  regime: string;
  capital_eur: number;
  capital_usd: number;
  blackout: string | null;
  upcoming_events: { date: string; event: string }[];
  market_context: string | null;
  recommended: Card[];
  shadow: Card[];
  open_positions: Card[];
  scored_today: string[];
  limits: {
    risk_per_trade_pct: number;
    risk_per_trade_fut_pct: number;
    max_daily_loss_eur: number;
    max_weekly_loss_eur: number;
    min_expectancy_r: number;
    pdt_intraday_stock_trades_per_week: number | null;
    max_total_open_risk_pct?: number;
    max_correlated_positions?: number;
  };
  tiers?: Record<"base" | "tail", TierCfg>;
  pdt_applies?: boolean;
  structures?: Record<string, StructureCfg>;
  options_budget?: OptionsBudget;
  _updated_at?: string;
};

export type Summary = {
  n: number;
  hit_rate: number | null;
  avg_r: number | null;
  sum_r: number;
  pnl_eur: number;
  brier: number | null;
  base_rate_brier?: number;
  profit_factor: number | null;
  max_dd_r: number;
  avg_days?: number | null;
};

export type Decisions = {
  executed: Summary; skipped: Summary;
  executed_count: number; skipped_count: number; undecided_recommended: number;
  skipped_auto_count?: number; skipped_user_count?: number; skipped_auto?: Summary; skipped_user?: Summary;
  skipped_total_rows?: number; skipped_reasons?: Record<string, number>;
  missed_opportunities?: SkippedRow[]; avoided_losses?: SkippedRow[];
  own_pnl_eur: number; system_pnl_same_cards_eur: number; n_with_own_pnl: number;
  execution_slippage_eur: number | null;
  skipped_winners_r: number; skipped_losers_r: number; net_r_of_skipping: number;
  entry_adherence_rate: number | null;
  skip_rate_by_tier: Record<string, number | null>;
  skip_rate_by_side: Record<string, number | null>;
  skip_rate_by_kind: Record<string, number | null>;
  bias_flags: { flag: string; text: string }[];
};

export type SkippedRow = { id: string; symbol: string; name?: string; setup_id: string; session_date: string; r_net: number; pnl_eur: number; source: string; reason?: string | null; status: string };

export type Metrics = {
  generated_at: string;
  recommended: Summary;
  all_tracked: Summary;
  by_setup: Record<string, { tier?: string; recommended: Summary; all_tracked: Summary }>;
  by_tier?: Record<string, { recommended: Summary; all_tracked: Summary }>;
  by_regime?: Record<string, Summary>;
  by_kind?: Record<string, Summary>;
  by_structure?: Record<string, { label: string; risk_class: RiskClass; recommended: Summary; all_tracked: Summary }>;
  signal_combos?: ({ combo: string } & Summary)[];
  predicted_vs_realised?: { setup_id: string; n: number; predicted_p: number; observed_p: number; predicted_r: number; observed_r: number }[];
  decisions?: Decisions;
  equity_curve: { date: string; cum_r: number; cum_eur: number; id: string; tier?: string }[];
  calibration: { bin: string; n: number; observed: number; predicted: number }[];
  fx_eurusd: number;
  capital_eur: number;
  counts: { total_cards: number; open: number; recommended_total: number };
};

export type SetupState = {
  prior_n: number;
  prior_p: number;
  prior_win_r: number;
  prior_loss_r: number;
  prior_trigger_rate?: number;
  prior_signals?: number;
  live_n: number;
  live_hits: number;
  live_wins: number;
  live_losses: number;
  live_win_r_sum: number;
  live_loss_r_sum: number;
  live_r_sum: number;
  status: "active" | "probation" | "suspended";
};

export type EngineState = {
  version: number;
  calibrated_on: string | null;
  setups: Record<string, Record<string, SetupState>>;
  changelog: { date: string; setup: string; regime: string; change: string; reason: string }[];
  calibration_report?: Record<string, { signals: number; triggered: number; hit_rate: number; avg_r_net: number; span: string; caveat?: string; tier?: string; in_sample?: { n: number; avg_r_net: number }; out_of_sample_2025plus?: { n: number; avg_r_net: number } }>;
  _updated_at?: string;
};

export type Execution = {
  id: number;
  cardId: string;
  decision: "executed" | "skipped";
  fillPrice: number | null;
  exitPrice: number | null;
  units: number | null;
  pnlEur: number | null;
  note: string | null;
  updatedAt: string;
  source?: "user" | "auto";
  reason?: string | null;
};
