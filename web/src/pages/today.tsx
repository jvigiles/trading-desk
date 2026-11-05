import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { CalendarClock, Clock, Info, RefreshCw } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { TradeCard, Stat, Pill, useExecutions } from "@/components/cards";
import { Term } from "@/components/term";
import { useToast } from "@/hooks/use-toast";
import { requestRefresh } from "@/lib/supabase";
import type { TodayView } from "@/lib/types";
import { fmtDate, fmtDateTime, fmtEur, fmtNum, regimeLabel } from "@/lib/format";

export default function Today() {
  const { data, isLoading, error } = useQuery<TodayView | null>({ queryKey: ["/api/today"] });
  const { data: execs } = useExecutions();
  const byCard = new Map((execs ?? []).map((e) => [e.cardId, e]));

  if (isLoading) return <PageSkeleton />;
  if (error || !data) {
    return (
      <div className="p-4">
        <EmptyState title="No run yet" body="The morning run has not produced a view for today. It runs on trading days before the US open." />
      </div>
    );
  }

  const recCount = data.recommended.length;
  const base = data.recommended.filter((c) => c.tier !== "tail");
  const tail = data.recommended.filter((c) => c.tier === "tail");
  const ageH = (Date.now() - new Date(data.run_at).getTime()) / 36e5;

  return (
    <div className="space-y-5 p-4">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold leading-tight">Session {fmtDate(data.session_date)}</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">Data as of {fmtDateTime(data.run_at)} · VIX {fmtNum(data.vix, 1)} · <Term k="regime">{regimeLabel(data.regime)}</Term></p>
        </div>
        <Pill tone={recCount ? "accent" : "muted"}>{recCount ? `${recCount} recommended` : "No trade today"}</Pill>
      </header>

      <RefreshBar ageH={ageH} />

      <section className="grid grid-cols-3 gap-3 rounded-xl border border-card-border bg-card p-4">
        <Stat label="Capital" value={fmtEur(data.capital_eur)} sub={`≈ $${fmtNum(data.capital_usd, 0)}`} />
        <Stat label="Daily loss stop" value={fmtEur(data.limits.max_daily_loss_eur)} sub="then stop for the day" />
        <Stat label="Weekly loss stop" value={fmtEur(data.limits.max_weekly_loss_eur)} sub="then paper only" />
      </section>

      {data.blackout && (
        <Notice icon={<CalendarClock className="h-4 w-4" />} title="Macro blackout today" body={`${data.blackout}. No futures day cards are issued; swing entries are flagged.`} />
      )}
      {data.market_context && <Notice icon={<Info className="h-4 w-4" />} title="Market context" body={data.market_context} />}

      {recCount === 0 && (
        <EmptyState
          title="No qualifying trade"
          body={`Nothing met the ${data.limits.min_expectancy_r.toFixed(2)}R expectancy threshold with an acceptable risk. Standing aside is a correct outcome, not a failure. Candidates below are tracked so the system keeps learning.`}
        />
      )}

      <section>
        <SectionTitle title="Base trades" count={base.length} hint={<>Core allocation: <Term k="base_tier">1% of capital at risk</Term> per trade, strongest evidence. Ranked by expectancy.</>} />
        {base.length === 0 ? <p className="text-sm text-muted-foreground">No base trade qualifies today.</p>
          : <div className="space-y-3">{base.map((c) => <TradeCard key={c.id} card={c} execution={byCard.get(c.id)} />)}</div>}
      </section>

      <section>
        <SectionTitle title="Tail trades" count={tail.length} hint={<>Asymmetric bets: <Term k="tail_tier">0.4% at risk</Term>, at least 3:1 reward to risk. Expect many small losses and few large winners.</>} />
        {tail.length === 0 ? <p className="text-sm text-muted-foreground">No tail trade qualifies today.</p>
          : <div className="space-y-3">{tail.map((c) => <TradeCard key={c.id} card={c} execution={byCard.get(c.id)} />)}</div>}
      </section>

      {data.open_positions.length > 0 && (
        <section>
          <SectionTitle title="Open from earlier sessions" count={data.open_positions.length} />
          <div className="space-y-3">{data.open_positions.map((c) => <TradeCard key={c.id} card={c} execution={byCard.get(c.id)} compact />)}</div>
        </section>
      )}

      <section>
        <SectionTitle title="Shadow candidates" count={data.shadow.length} hint="Signals fired but not recommended. Scored like real cards so setups can earn their way in." />
        {data.shadow.length === 0 ? (
          <p className="text-sm text-muted-foreground">No shadow candidates for this session.</p>
        ) : (
          <div className="space-y-3">{data.shadow.map((c) => <TradeCard key={c.id} card={c} execution={byCard.get(c.id)} compact />)}</div>
        )}
      </section>

      {data.upcoming_events.length > 0 && (
        <section>
          <SectionTitle title="Next 10 days" />
          <ul className="divide-y divide-border rounded-xl border border-card-border bg-card">
            {data.upcoming_events.map((e) => (
              <li key={e.date + e.event} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                <Clock className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="mono w-14 shrink-0 text-muted-foreground">{fmtDate(e.date)}</span>
                <span className="min-w-0 flex-1">{e.event}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function RefreshBar({ ageH }: { ageH: number }) {
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const stale = ageH > 20;
  async function ask() {
    setBusy(true);
    try {
      await requestRefresh("requested from app");
      toast({ title: "Refresh requested", description: "The engine picks requests up on its next run (07:30 / 14:30 CET on weekdays). For an immediate run, use 'Run workflow' in GitHub Actions or ask in the chat." });
    } catch (e) { toast({ title: "Could not request", description: (e as Error).message, variant: "destructive" }); }
    setBusy(false);
  }
  return (
    <div className={`flex items-center justify-between gap-3 rounded-xl border px-3 py-2 text-xs ${stale ? "border-amber-500/40 bg-amber-500/5" : "border-border bg-card"}`}>
      <span className="text-muted-foreground">{stale ? `Data is ${Math.round(ageH)} h old. Levels stay valid for the session they were issued for; check the date before trading.` : `Updated ${ageH < 1 ? `${Math.max(1, Math.round(ageH * 60))} min` : `${Math.round(ageH)} h`} ago.`}</span>
      <button type="button" onClick={ask} disabled={busy} className="flex shrink-0 items-center gap-1 rounded-md border border-border px-2 py-1 text-foreground hover:bg-accent disabled:opacity-50" data-testid="button-refresh">
        <RefreshCw className={`h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} /> Request refresh
      </button>
    </div>
  );
}

export function SectionTitle({ title, count, hint }: { title: string; count?: number; hint?: React.ReactNode }) {
  return (
    <div className="mb-2">
      <div className="flex items-baseline gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{title}</h2>
        {count !== undefined && <span className="mono text-xs text-muted-foreground">{count}</span>}
      </div>
      {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border p-5 text-center">
      <div className="text-sm font-medium">{title}</div>
      <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">{body}</p>
    </div>
  );
}

export function Notice({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="flex gap-3 rounded-xl border border-primary/30 bg-primary/5 p-3 text-sm">
      <div className="mt-0.5 text-primary">{icon}</div>
      <div><div className="font-medium">{title}</div><p className="text-muted-foreground">{body}</p></div>
    </div>
  );
}

function PageSkeleton() {
  return (
    <div className="space-y-4 p-4">
      <Skeleton className="h-6 w-40" />
      <Skeleton className="h-20 w-full rounded-xl" />
      <Skeleton className="h-36 w-full rounded-xl" />
      <Skeleton className="h-36 w-full rounded-xl" />
    </div>
  );
}
