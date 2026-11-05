import { useQuery } from "@tanstack/react-query";
import { SectionTitle } from "./today";
import type { TodayView } from "@/lib/types";
import { fmtEur } from "@/lib/format";

export default function Rules() {
  const { data } = useQuery<TodayView | null>({ queryKey: ["/api/today"] });
  const L = data?.limits;
  const T = data?.tiers;
  return (
    <div className="space-y-5 p-4">
      <h1 className="text-lg font-semibold">Rules and limits</h1>

      <section>
        <SectionTitle title="Hard limits (enforced in the engine)" />
        <Table rows={[
          ["Capital base", data ? fmtEur(data.capital_eur) : "€5,000"],
          ["Base trades", T?.base ? `${(T.base.risk_pct * 100).toFixed(1)}% of capital at risk per trade, max ${T.base.max_open} open, ${(T.base.max_total_risk_pct * 100).toFixed(1)}% total risk, reward:risk ≥ ${T.base.min_rr}` : "1.0% per trade, max 3 open"],
          ["Tail trades", T?.tail ? `${(T.tail.risk_pct * 100).toFixed(1)}% of capital at risk per trade, max ${T.tail.max_open} open, ${(T.tail.max_total_risk_pct * 100).toFixed(1)}% total risk, reward:risk ≥ ${T.tail.min_rr}` : "0.4% per trade, max 2 open"],
          ["Total open risk", L?.max_total_open_risk_pct ? `${(L.max_total_open_risk_pct * 100).toFixed(1)}% of capital across all open cards` : "3.5%"],
          ["Correlation cap", L?.max_correlated_positions ? `max ${L.max_correlated_positions} open positions in the same cluster (e.g. US large-cap indices)` : "max 2 per cluster"],
          ["Risk per futures day trade", L ? `${(L.risk_per_trade_fut_pct * 100).toFixed(1)}% (one micro contract is the smallest unit)` : "1.5%"],
          ["Daily loss stop", L ? `${fmtEur(L.max_daily_loss_eur)} realised → no new trades today` : "2%"],
          ["Weekly loss stop", L ? `${fmtEur(L.max_weekly_loss_eur)} realised → paper only until review` : "4%"],
          ["Recommendation threshold", L ? `expectancy ≥ +${L.min_expectancy_r.toFixed(2)}R after costs` : "+0.10R"],
          ["Leverage on swings", "none; notional ≤ capital"],
          ["Max cards per day", "2 futures + 2 swing"],
          ["Overnight futures", "never from a day card"],
          ["Macro blackout", "no futures day cards on NFP, CPI, FOMC days"],
          ["PDT (US stocks)", L && L.pdt_intraday_stock_trades_per_week != null ? `≤ ${L.pdt_intraday_stock_trades_per_week} intraday stock round trips per rolling week` : "not applicable: account confirmed as not subject to US pattern-day-trader rules"],
          ["Quota", "none. Zero recommendations is a valid day; nothing is generated to fill a slot."],
        ]} />
      </section>

      <section>
        <SectionTitle title="Daily routine (CET)" />
        <Table rows={[
          ["≈ 07:30", "Morning run: yesterday's cards scored, learning state updated, today's cards published. News review and analyst notes follow."],
          ["≈ 14:30", "Midday refresh before the US open: levels re-checked, pending refresh requests served."],
          ["Before 15:30", "Read cards, decide, stage bracket orders in IBKR (futures and swing)."],
          ["15:30–21:00", "Futures triggers allowed. Cancel if the session opened through the level."],
          ["21:55", "Flat on any futures day card. Record fill/exit in the card."],
          ["Weekly", "Sunday: review Performance and Learning; adjust nothing by hand unless a rule says so."],
        ]} />
      </section>

      <section>
        <SectionTitle title="What the probabilities mean" />
        <p className="text-sm text-muted-foreground">
          P(win) is the posterior probability that the trade closes with a positive net R at the card's own levels, combining a historical simulation (2021–2026 daily data for swing setups, roughly 60 days of 5-minute data for futures) with live outcomes. Expectancy is P(win) × average win − P(loss) × average loss, after commissions and an assumed slippage. These are estimates, not guarantees; the futures prior in particular is weak and the setup currently shows negative expectancy, which is why it stays in shadow.
        </p>
      </section>

      <section>
        <SectionTitle title="Income expectations" />
        <p className="text-sm text-muted-foreground">
          There is no daily or weekly income target in this app on purpose. At 1% risk per trade and the historical expectancies, a good month is in the low single-digit percent of capital and losing months are normal. Withdraw only realised profit above the high-water mark, and only at month end.
        </p>
      </section>

      <section>
        <SectionTitle title="Disclaimer" />
        <p className="text-xs text-muted-foreground">
          This is a personal decision-support tool, not investment advice and not connected to your broker. You place every order yourself and remain responsible for it. Data comes from free delayed feeds and may contain errors; verify levels against IBKR before trading. Past simulation results do not predict live results.
        </p>
      </section>
    </div>
  );
}

function Table({ rows }: { rows: [string, string][] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-card-border bg-card">
      {rows.map(([k, v]) => (
        <div key={k} className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-3 border-b border-border/60 px-4 py-2.5 text-sm last:border-0">
          <div className="text-muted-foreground">{k}</div>
          <div className="min-w-0 [overflow-wrap:anywhere]">{v}</div>
        </div>
      ))}
    </div>
  );
}
