import { useQuery } from "@tanstack/react-query";
import { Skeleton } from "@/components/ui/skeleton";
import { Pill, Stat } from "@/components/cards";
import { EmptyState, SectionTitle } from "./today";
import type { EngineState, SetupState } from "@/lib/types";
import { fmtDate, fmtNum, fmtPct, fmtR, regimeLabel, setupShort } from "@/lib/format";
import { Term } from "@/components/term";

const PRIOR_STRENGTH = 40;

function posterior(s: SetupState) {
  const a0 = PRIOR_STRENGTH * s.prior_p, b0 = PRIOR_STRENGTH * (1 - s.prior_p);
  const p = (a0 + s.live_hits) / (a0 + b0 + s.live_n);
  const win = (PRIOR_STRENGTH * s.prior_win_r + s.live_win_r_sum) / (PRIOR_STRENGTH + s.live_wins);
  const loss = (PRIOR_STRENGTH * s.prior_loss_r + s.live_loss_r_sum) / (PRIOR_STRENGTH + s.live_losses);
  return { p, win, loss, exp: p * win + (1 - p) * loss, liveWeight: s.live_n / (PRIOR_STRENGTH + s.live_n) };
}

export default function Learning() {
  const { data: st, isLoading } = useQuery<EngineState | null>({ queryKey: ["/api/state"] });
  if (isLoading) return <div className="space-y-3 p-4"><Skeleton className="h-24 w-full rounded-xl" /><Skeleton className="h-48 w-full rounded-xl" /></div>;
  if (!st) return <div className="p-4"><EmptyState title="No learning state" body="Run the calibration first." /></div>;

  const order = ["all", "low_vol", "mid_vol", "high_vol"];
  const log = [...st.changelog].reverse();

  return (
    <div className="space-y-5 p-4">
      <header>
        <h1 className="text-lg font-semibold">Learning</h1>
        <p className="mt-0.5 text-xs text-muted-foreground">Priors calibrated {st.calibrated_on ? fmtDate(st.calibrated_on) : "–"}. Each live outcome shifts the posterior; after {PRIOR_STRENGTH} live trades the history and the live record carry equal weight.</p>
      </header>

      <section>
        <SectionTitle title="How it adapts" />
        <ol className="space-y-2 rounded-xl border border-card-border bg-card p-4 text-sm text-muted-foreground">
          <li className="flex gap-2"><span className="mono text-foreground">1</span>Every card, recommended or shadow, is scored from market data at its own levels the next morning.</li>
          <li className="flex gap-2"><span className="mono text-foreground">2</span>Hit rate and payoff per setup and volatility regime are updated as a Bayesian posterior (history is the prior, live results overrule it gradually).</li>
          <li className="flex gap-2"><span className="mono text-foreground">3</span>A setup is recommended only while its posterior expectancy after costs is at least +0.10R; below +0.10R after 15 live outcomes it goes on probation, below 0R after 30 it is suspended. Suspended setups keep running in shadow and are reinstated if they recover.</li>
          <li className="flex gap-2"><span className="mono text-foreground">4</span>Probabilities shown on cards are these posteriors, so the calibration chart tells you whether the system is honest about itself.</li>
          <li className="flex gap-2"><span className="mono text-foreground">5</span>Monthly, priors are re-estimated on fresh history and every change is logged below.</li>
          <li className="flex gap-2"><span className="mono text-foreground">6</span><span><Term k="oos">Overfitting guard</Term>: every setup must hold up on data it was not tuned on (2025 onward, shown as "out of sample" below) and on forward paper trading before its tier or size is changed. Rules are changed by hand, with a logged reason, never automatically from a short streak.</span></li>
        </ol>
      </section>

      {Object.entries(st.setups).map(([sid, regimes]) => (
        <section key={sid}>
          <SectionTitle title={setupShort[sid] ?? sid} />
          <div className="overflow-hidden rounded-xl border border-card-border bg-card">
            {order.filter((r) => regimes[r]).map((r) => {
              const s = regimes[r]; const po = posterior(s);
              return (
                <div key={r} className="border-b border-border/60 p-3 last:border-0">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{r === "all" ? "All regimes" : regimeLabel(r)}</span>
                    <Pill tone={s.status === "active" ? "pos" : s.status === "probation" ? "neutral" : "neg"}>{s.status}</Pill>
                    {s.prior_n < 50 && r !== "all" && <Pill tone="muted">too few, uses "all"</Pill>}
                    {s.status === "active" && po.exp < 0.1 && <Pill tone="muted">below +0.10R → shadow</Pill>}
                  </div>
                  <div className="grid grid-cols-4 gap-2">
                    <Stat label="P(win)" value={fmtPct(po.p)} sub={`prior ${fmtPct(s.prior_p)}`} />
                    <Stat label="Expectancy" value={fmtR(po.exp)} tone={po.exp >= 0.1 ? "pos" : po.exp <= -0.005 ? "neg" : undefined} sub="after costs" />
                    <Stat label="History" value={s.prior_n} sub="sim. trades" />
                    <Stat label="Live" value={s.live_n} sub={`${fmtNum(po.liveWeight * 100, 0)}% weight`} />
                  </div>
                </div>
              );
            })}
          </div>
          {st.calibration_report?.[sid]?.caveat && <p className="mt-1.5 text-xs text-muted-foreground">{st.calibration_report[sid].caveat}</p>}
          {st.calibration_report?.[sid] && <p className="mt-1 text-xs text-muted-foreground">Simulation span {st.calibration_report[sid].span}; {st.calibration_report[sid].signals} signals, {st.calibration_report[sid].triggered} filled.</p>}
          {st.calibration_report?.[sid]?.in_sample && st.calibration_report[sid].out_of_sample_2025plus && (
            <div className="mt-2 grid grid-cols-2 gap-2 rounded-lg border border-border bg-muted/30 p-2" data-testid={`oos-${sid}`}>
              <Stat label="In sample (to 2024)" value={fmtR(st.calibration_report[sid].in_sample!.avg_r_net)} sub={`n=${st.calibration_report[sid].in_sample!.n}`} />
              <Stat label={<Term k="oos">Out of sample (2025+)</Term>} value={fmtR(st.calibration_report[sid].out_of_sample_2025plus!.avg_r_net)} sub={`n=${st.calibration_report[sid].out_of_sample_2025plus!.n}`} tone={st.calibration_report[sid].out_of_sample_2025plus!.avg_r_net > 0 ? "pos" : "neg"} />
            </div>
          )}
        </section>
      ))}

      <section>
        <SectionTitle title="Event scout (discretionary)" hint={<><Term k="discretionary">Analyst-proposed</Term> tail trades from the morning news review. No backtest exists, so it starts from a deliberately conservative prior (P 40%, +1.6R / −1.05R) and is judged purely on its live record.</>} />
        {st.setups["EVENT_SCOUT"] ? null : <p className="rounded-xl border border-card-border bg-card p-3 text-sm text-muted-foreground">No event-scout card has been scored yet.</p>}
      </section>

      <section>
        <SectionTitle title="Change log" count={log.length} />
        {log.length === 0 ? <p className="text-sm text-muted-foreground">No changes yet.</p> : (
          <ul className="divide-y divide-border rounded-xl border border-card-border bg-card">
            {log.slice(0, 50).map((c, i) => (
              <li key={i} className="px-4 py-2.5 text-sm">
                <div className="flex items-center gap-2"><span className="mono text-xs text-muted-foreground">{fmtDate(c.date)}</span><span className="font-medium">{setupShort[c.setup] ?? c.setup}</span><span className="text-xs text-muted-foreground">{c.regime}</span></div>
                <div className="mt-0.5">{c.change}</div>
                <div className="text-xs text-muted-foreground">{c.reason}</div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
