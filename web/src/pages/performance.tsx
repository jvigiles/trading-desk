import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, BarChart, Bar, ReferenceLine } from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import { Stat, useExecutions } from "@/components/cards";
import { EmptyState, SectionTitle } from "./today";
import type { Card, Metrics, Summary } from "@/lib/types";
import { Term } from "@/components/term";
import { fmtEur, fmtNum, fmtPct, fmtR, setupShort, fmtDate } from "@/lib/format";

export default function Performance() {
  const { data: m, isLoading } = useQuery<Metrics | null>({ queryKey: ["/api/metrics"] });
  const { data: cards } = useQuery<Card[]>({ queryKey: ["/api/cards"] });
  const { data: execs } = useExecutions();

  const mine = useMemo(() => {
    const byId = new Map((cards ?? []).map((c) => [c.id, c]));
    const ex = (execs ?? []).filter((e) => e.decision === "executed");
    const closed = ex.filter((e) => e.pnlEur !== null);
    const sysClosed = ex.map((e) => byId.get(e.cardId)).filter((c): c is Card => !!c && !!c.outcome && ["target", "stopped", "expired"].includes(c.status));
    const skipped = (execs ?? []).filter((e) => e.decision === "skipped").map((e) => byId.get(e.cardId)).filter((c): c is Card => !!c && !!c.outcome && ["target", "stopped", "expired"].includes(c.status));
    return {
      executed: ex.length,
      closedWithPnl: closed.length,
      pnlEur: closed.reduce((s, e) => s + (e.pnlEur ?? 0), 0),
      wins: closed.filter((e) => (e.pnlEur ?? 0) > 0).length,
      sysOnExecuted: sysClosed.reduce((s, c) => s + c.outcome!.r_net, 0),
      sysOnExecutedN: sysClosed.length,
      skippedR: skipped.reduce((s, c) => s + c.outcome!.r_net, 0),
      skippedN: skipped.length,
    };
  }, [cards, execs]);

  const d = m?.decisions;
  if (isLoading) return <div className="space-y-3 p-4"><Skeleton className="h-24 w-full rounded-xl" /><Skeleton className="h-48 w-full rounded-xl" /></div>;
  if (!m) return <div className="p-4"><EmptyState title="No metrics yet" body="Metrics are computed after the first scored cards." /></div>;

  const curve = m.equity_curve.map((p, i) => ({ ...p, i: i + 1, label: fmtDate(p.date) }));

  return (
    <div className="space-y-5 p-4">
      <h1 className="text-lg font-semibold">Performance</h1>

      <section>
        <SectionTitle title="System · recommended cards" hint="What the engine would have earned if every recommended card had been executed at its own levels." />
        <SummaryGrid s={m.recommended} />
      </section>

      <section className="rounded-xl border border-card-border bg-card p-4">
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold">Equity curve, recommended (R)</h2>
          <span className="mono text-xs text-muted-foreground">{curve.length} closed</span>
        </div>
        {curve.length < 2 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Appears after two closed recommended cards.</p>
        ) : (
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={curve} margin={{ left: -18, right: 4, top: 8, bottom: 0 }}>
                <defs>
                  <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} minTickGap={24} />
                <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} />
                <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeOpacity={0.5} />
                <Tooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }} formatter={(v: number, k: string) => [k === "cum_r" ? fmtR(v) : fmtEur(v, 2), k === "cum_r" ? "Cum. R" : "Cum. €"]} />
                <Area type="monotone" dataKey="cum_r" stroke="hsl(var(--primary))" fill="url(#eq)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      <section>
        <SectionTitle title="You · executed vs skipped" hint={<>Your own record from the decisions you saved, compared with the system on the same cards. This is where <Term k="bias">decision biases</Term> show up.</>} />
        <div className="grid grid-cols-3 gap-3 rounded-xl border border-card-border bg-card p-4">
          <Stat label="Executed" value={mine.executed} sub={`${mine.closedWithPnl} with P&L entered`} />
          <Stat label="Your P&L" value={fmtEur(mine.pnlEur, 0)} tone={mine.pnlEur > 0 ? "pos" : mine.pnlEur < 0 ? "neg" : undefined} sub={mine.closedWithPnl ? `${mine.wins}/${mine.closedWithPnl} winners` : "enter fills to track"} />
          <Stat label="System on same cards" value={fmtR(mine.sysOnExecutedN ? mine.sysOnExecuted : null)} sub={`${mine.sysOnExecutedN} scored`} />
          <Stat label="Skipped cards" value={mine.skippedN} sub="scored by system" />
          <Stat label="R you avoided" value={fmtR(mine.skippedN ? -mine.skippedR : null)} tone={mine.skippedN ? (mine.skippedR < 0 ? "pos" : "neg") : undefined} sub="positive = good skips" />
          {d && <Stat label={<Term k="adherence">Entry adherence</Term>} value={fmtPct(d.entry_adherence_rate)} sub="fills within 0.25R of plan" />}
        </div>
        {d && (
          <div className="mt-3 rounded-xl border border-card-border bg-card p-4 text-sm">
            <div className="flex items-baseline justify-between"><h3 className="font-semibold">Decision review</h3><span className="mono text-xs text-muted-foreground">{d.executed_count + d.skipped_count} decided · {d.undecided_recommended} undecided</span></div>
            <div className="mt-2 grid grid-cols-3 gap-3">
              <Stat label="Missed (skipped winners)" value={fmtR(d.skipped_winners_r)} tone={d.skipped_winners_r > 0 ? "neg" : undefined} sub="R left on the table" />
              <Stat label="Avoided (skipped losers)" value={fmtR(-d.skipped_losers_r)} tone={d.skipped_losers_r < 0 ? "pos" : undefined} sub="R saved by skipping" />
              <Stat label="Net effect of skipping" value={fmtR(d.net_r_of_skipping)} tone={d.net_r_of_skipping > 0 ? "pos" : d.net_r_of_skipping < 0 ? "neg" : undefined} sub="positive = skips helped" />
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-muted-foreground">
              <div>Skip rate base / tail: <span className="mono text-foreground">{fmtPct(d.skip_rate_by_tier.base)} / {fmtPct(d.skip_rate_by_tier.tail)}</span></div>
              <div>Long / short: <span className="mono text-foreground">{fmtPct(d.skip_rate_by_side.long)} / {fmtPct(d.skip_rate_by_side.short)}</span></div>
              <div>Day / swing: <span className="mono text-foreground">{fmtPct(d.skip_rate_by_kind.futures_day)} / {fmtPct(d.skip_rate_by_kind.swing)}</span></div>
            </div>
            {(d.skipped_total_rows ?? 0) > 0 && (
              <div className="mt-3 border-t border-border/60 pt-3" data-testid="skipped-breakdown">
                <div className="flex items-baseline justify-between"><h4 className="text-xs font-semibold">Skipped trades and hypothetical outcomes</h4><span className="mono text-xs text-muted-foreground">{d.skipped_user_count ?? 0} by you · {d.skipped_auto_count ?? 0} <Term k="auto_skip">auto</Term></span></div>
                <div className="mt-2 grid grid-cols-2 gap-3">
                  <Stat label="Skipped by you" value={fmtR(d.skipped_user?.avg_r ?? null)} sub={`avg R · n=${d.skipped_user?.n ?? 0} scored · ${fmtEur(d.skipped_user?.pnl_eur ?? 0)}`} />
                  <Stat label="Auto-skipped" value={fmtR(d.skipped_auto?.avg_r ?? null)} sub={`avg R · n=${d.skipped_auto?.n ?? 0} scored · ${fmtEur(d.skipped_auto?.pnl_eur ?? 0)}`} />
                </div>
                {d.skipped_reasons && Object.keys(d.skipped_reasons).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">{Object.entries(d.skipped_reasons).map(([r, n]) => <span key={r} className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">{r} · {n}</span>)}</div>
                )}
                {(d.missed_opportunities?.length ?? 0) > 0 && (
                  <div className="mt-2"><div className="text-xs text-muted-foreground">Would have won</div>
                    <ul className="mt-1 space-y-1">{d.missed_opportunities!.slice(0, 5).map((r) => <li key={r.id} className="flex items-baseline justify-between gap-2 text-xs"><span className="truncate"><span className="mono font-medium">{r.symbol}</span> {r.name ? <span className="text-muted-foreground">{r.name} · </span> : null}<span className="text-muted-foreground">{fmtDate(r.session_date)} · {r.source === "auto" ? "auto" : "you"}</span></span><span className="mono shrink-0 text-emerald-600 dark:text-emerald-400">{fmtR(r.r_net)} · {fmtEur(r.pnl_eur)}</span></li>)}</ul></div>
                )}
                {(d.avoided_losses?.length ?? 0) > 0 && (
                  <div className="mt-2"><div className="text-xs text-muted-foreground">Would have lost</div>
                    <ul className="mt-1 space-y-1">{d.avoided_losses!.slice(0, 5).map((r) => <li key={r.id} className="flex items-baseline justify-between gap-2 text-xs"><span className="truncate"><span className="mono font-medium">{r.symbol}</span> {r.name ? <span className="text-muted-foreground">{r.name} · </span> : null}<span className="text-muted-foreground">{fmtDate(r.session_date)} · {r.source === "auto" ? "auto" : "you"}</span></span><span className="mono shrink-0 text-rose-600 dark:text-rose-400">{fmtR(r.r_net)} · {fmtEur(r.pnl_eur)}</span></li>)}</ul></div>
                )}
                <p className="mt-2 text-[11px] text-muted-foreground">Hypothetical: scored by the system at the card's own levels as if the trade had been taken at planned size.</p>
              </div>
            )}
            <ul className="mt-3 space-y-1.5">
              {d.bias_flags.map((b, i) => (
                <li key={i} className={`flex gap-2 rounded-md px-2 py-1.5 text-xs ${b.flag === "insufficient_data" ? "bg-muted/60 text-muted-foreground" : "border border-amber-500/40 bg-amber-500/5"}`} data-testid={`bias-${b.flag}`}>
                  <span className="mono shrink-0 uppercase">{b.flag.replace(/_/g, " ")}</span><span>{b.text}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {m.by_tier && (
        <section>
          <SectionTitle title="By tier" hint={<><Term k="base_tier">Base</Term> and <Term k="tail_tier">tail</Term> trades are judged separately: tail trades are expected to lose often and win big.</>} />
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(m.by_tier).map(([t, v]) => (
              <div key={t} className="rounded-xl border border-card-border bg-card p-3">
                <div className="mb-1 text-xs font-semibold uppercase text-muted-foreground">{t} · recommended</div>
                <div className="grid grid-cols-2 gap-2">
                  <Stat label="Closed" value={v.recommended.n} />
                  <Stat label="Hit" value={fmtPct(v.recommended.hit_rate)} />
                  <Stat label="Avg R" value={fmtR(v.recommended.avg_r)} tone={v.recommended.avg_r === null ? undefined : v.recommended.avg_r > 0 ? "pos" : "neg"} />
                  <Stat label="Tracked avg" value={fmtR(v.all_tracked.avg_r)} sub={`n=${v.all_tracked.n}`} />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {m.by_structure && Object.keys(m.by_structure).length > 0 && (
        <section>
          <SectionTitle title="By structure" hint={<>Shares, <Term k="defined_risk">defined-risk</Term> option structures and margined futures judged separately. R = stop distance for shares and futures, premium for options.</>} />
          <div className="overflow-hidden rounded-xl border border-card-border bg-card">
            <table className="w-full text-xs">
              <thead className="bg-muted/60 text-left text-muted-foreground"><tr><th className="px-3 py-1.5 font-medium">Structure</th><th className="px-2 py-1.5 font-medium">Risk</th><th className="px-2 py-1.5 text-right font-medium">Rec. n</th><th className="px-2 py-1.5 text-right font-medium">Avg R</th><th className="px-2 py-1.5 text-right font-medium">Tracked n</th><th className="px-3 py-1.5 text-right font-medium">Avg R</th></tr></thead>
              <tbody>
                {Object.entries(m.by_structure).map(([k, v]) => (
                  <tr key={k} className="border-t border-border/60" data-testid={`structure-${k}`}>
                    <td className="px-3 py-1.5 font-medium">{v.label}</td>
                    <td className="px-2 py-1.5 text-muted-foreground">{v.risk_class === "defined" ? "Defined" : v.risk_class === "open_ended" ? "Can exceed stake" : "Stop-based"}</td>
                    <td className="mono px-2 py-1.5 text-right">{v.recommended.n}</td>
                    <td className="mono px-2 py-1.5 text-right">{fmtR(v.recommended.avg_r)}</td>
                    <td className="mono px-2 py-1.5 text-right">{v.all_tracked.n}</td>
                    <td className="mono px-3 py-1.5 text-right">{fmtR(v.all_tracked.avg_r)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section>
        <SectionTitle title="By setup" hint="Recommended vs. everything tracked (including shadow)." />
        <div className="overflow-x-auto rounded-xl border border-card-border bg-card">
          <table className="w-full min-w-[420px] text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr className="border-b border-border"><th className="px-3 py-2 text-left font-medium">Setup</th><th className="px-2 py-2 text-right font-medium">Rec. n</th><th className="px-2 py-2 text-right font-medium">Hit</th><th className="px-2 py-2 text-right font-medium">Avg R</th><th className="px-2 py-2 text-right font-medium">Tracked n</th><th className="px-3 py-2 text-right font-medium">Avg R</th></tr>
            </thead>
            <tbody>
              {Object.entries(m.by_setup).map(([sid, v]) => (
                <tr key={sid} className="border-b border-border/60 last:border-0">
                  <td className="px-3 py-2">{setupShort[sid] ?? sid}</td>
                  <td className="mono px-2 py-2 text-right">{v.recommended.n}</td>
                  <td className="mono px-2 py-2 text-right">{fmtPct(v.recommended.hit_rate)}</td>
                  <td className="mono px-2 py-2 text-right">{fmtR(v.recommended.avg_r)}</td>
                  <td className="mono px-2 py-2 text-right text-muted-foreground">{v.all_tracked.n}</td>
                  <td className="mono px-3 py-2 text-right text-muted-foreground">{fmtR(v.all_tracked.avg_r)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {(m.predicted_vs_realised?.length ?? 0) > 0 && (
        <section>
          <SectionTitle title="Predicted vs realised" hint="Per setup: what the engine said would happen vs. what did (live, scored cards). Large gaps trigger a re-calibration." />
          <div className="overflow-x-auto rounded-xl border border-card-border bg-card">
            <table className="w-full min-w-[420px] text-sm">
              <thead className="text-xs text-muted-foreground"><tr className="border-b border-border"><th className="px-3 py-2 text-left font-medium">Setup</th><th className="px-2 py-2 text-right font-medium">n</th><th className="px-2 py-2 text-right font-medium">P pred.</th><th className="px-2 py-2 text-right font-medium">P obs.</th><th className="px-2 py-2 text-right font-medium">R pred.</th><th className="px-3 py-2 text-right font-medium">R obs.</th></tr></thead>
              <tbody>{m.predicted_vs_realised!.map((r) => (
                <tr key={r.setup_id} className="border-b border-border/60 last:border-0"><td className="px-3 py-2">{setupShort[r.setup_id] ?? r.setup_id}</td><td className="mono px-2 py-2 text-right">{r.n}</td><td className="mono px-2 py-2 text-right">{fmtPct(r.predicted_p)}</td><td className="mono px-2 py-2 text-right">{fmtPct(r.observed_p)}</td><td className="mono px-2 py-2 text-right">{fmtR(r.predicted_r)}</td><td className="mono px-3 py-2 text-right">{fmtR(r.observed_r)}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </section>
      )}

      {(m.signal_combos?.length ?? 0) > 0 && (
        <section>
          <SectionTitle title="Signal combinations" hint="Which signal mixes actually paid. Used to refine selection, only after enough samples." />
          <div className="overflow-x-auto rounded-xl border border-card-border bg-card">
            <table className="w-full min-w-[420px] text-sm">
              <thead className="text-xs text-muted-foreground"><tr className="border-b border-border"><th className="px-3 py-2 text-left font-medium">Signals</th><th className="px-2 py-2 text-right font-medium">n</th><th className="px-2 py-2 text-right font-medium">Hit</th><th className="px-3 py-2 text-right font-medium">Avg R</th></tr></thead>
              <tbody>{m.signal_combos!.map((r) => (
                <tr key={r.combo} className="border-b border-border/60 last:border-0"><td className="mono px-3 py-2 text-xs">{r.combo}</td><td className="mono px-2 py-2 text-right">{r.n}</td><td className="mono px-2 py-2 text-right">{fmtPct(r.hit_rate)}</td><td className="mono px-3 py-2 text-right">{fmtR(r.avg_r)}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </section>
      )}

      <section className="rounded-xl border border-card-border bg-card p-4">
        <h2 className="text-sm font-semibold">Calibration</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">Stated probability vs. observed hit rate across all tracked cards. Bars at the line mean the probabilities are honest.</p>
        {m.calibration.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Appears after the first scored cards.</p>
        ) : (
          <div className="mt-2 h-40">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={m.calibration} margin={{ left: -18, right: 4, top: 8, bottom: 0 }}>
                <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="bin" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                <Tooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }} formatter={(v: number, k: string) => [fmtPct(v), k]} />
                <Bar dataKey="predicted" fill="hsl(var(--chart-5))" radius={3} />
                <Bar dataKey="observed" fill="hsl(var(--primary))" radius={3} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        {m.recommended.brier !== null && (
          <p className="mt-2 text-xs text-muted-foreground">Brier score {fmtNum(m.recommended.brier, 3)} vs. {fmtNum(m.recommended.base_rate_brier ?? null, 3)} for a constant base-rate forecast (lower is better).</p>
        )}
      </section>
    </div>
  );
}

function SummaryGrid({ s }: { s: Summary }) {
  return (
    <div className="grid grid-cols-3 gap-3 rounded-xl border border-card-border bg-card p-4">
      <Stat label="Closed" value={s.n} />
      <Stat label="Hit rate" value={fmtPct(s.hit_rate)} />
      <Stat label="Avg R" value={fmtR(s.avg_r)} tone={s.avg_r === null ? undefined : s.avg_r > 0 ? "pos" : "neg"} />
      <Stat label="Total R" value={fmtR(s.sum_r)} tone={s.sum_r > 0 ? "pos" : s.sum_r < 0 ? "neg" : undefined} />
      <Stat label="P&L (modelled)" value={fmtEur(s.pnl_eur)} tone={s.pnl_eur > 0 ? "pos" : s.pnl_eur < 0 ? "neg" : undefined} />
      <Stat label="Max drawdown" value={fmtR(-s.max_dd_r)} />
    </div>
  );
}
