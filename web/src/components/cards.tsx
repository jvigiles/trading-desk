import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, Check, ChevronRight, Info, ShieldAlert, Smartphone, Monitor, X } from "lucide-react";
import { Term } from "@/components/term";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { queryClient } from "@/lib/queryClient";
import { deleteExecution, upsertExecution } from "@/lib/supabase";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import type { AlternativeRow, Card, Execution, ExecutionPlan, RiskClass, TodayView } from "@/lib/types";
import { fmtEur, fmtPct, fmtPrice, fmtR, fmtUsd, statusLabel, statusTone, fmtDate, fmtDateTime, fmtNum } from "@/lib/format";

/* ------------------------------------------------------------------ small atoms */
export function Pill({ tone = "muted", children, className }: { tone?: "pos" | "neg" | "neutral" | "muted" | "accent"; children: React.ReactNode; className?: string }) {
  const map = {
    pos: "bg-emerald-500/12 text-emerald-700 dark:text-emerald-300 border-emerald-500/25",
    neg: "bg-rose-500/12 text-rose-700 dark:text-rose-300 border-rose-500/25",
    neutral: "bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/25",
    muted: "bg-muted text-muted-foreground border-border",
    accent: "bg-primary/12 text-primary border-primary/30",
  };
  return <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium", map[tone], className)}>{children}</span>;
}

export function Stat({ label, value, sub, tone, className }: { label: React.ReactNode; value: React.ReactNode; sub?: React.ReactNode; tone?: "pos" | "neg"; className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn("mono text-base font-semibold leading-tight", tone === "pos" && "text-emerald-600 dark:text-emerald-400", tone === "neg" && "text-rose-600 dark:text-rose-400")}>{value}</div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

export const RISK_CLASS_LABEL: Record<RiskClass, string> = { defined: "Defined risk", stop_based: "Stop-based", open_ended: "Loss can exceed stake" };
export function RiskClassPill({ rc }: { rc?: RiskClass }) {
  if (!rc) return null;
  return <Pill tone={rc === "defined" ? "pos" : rc === "open_ended" ? "neg" : "muted"}><Term k={rc === "defined" ? "defined_risk" : rc === "open_ended" ? "open_ended" : "stop_loss"}>{RISK_CLASS_LABEL[rc]}</Term></Pill>;
}
export function riskClassOf(card: Card): RiskClass {
  return card.risk_class ?? (card.kind === "futures_day" ? "open_ended" : "stop_based");
}
export function kindLabel(card: Card) {
  return card.kind === "futures_day" ? "Day" : card.kind === "option_swing" ? "Option" : "Swing";
}
export function ExecutionPill({ execution }: { execution?: Execution }) {
  if (!execution) return null;
  if (execution.decision === "executed") return <Pill tone="pos">You executed</Pill>;
  if (execution.source === "auto") return <Pill tone="muted"><Term k="auto_skip">Auto-skipped</Term></Pill>;
  return <Pill tone="muted">You skipped</Pill>;
}

export function useExecutions() {
  return useQuery<Execution[]>({ queryKey: ["/api/executions"] });
}

/* ------------------------------------------------------------------ trade card */
export function TradeCard({ card, execution, compact = false }: { card: Card; execution?: Execution; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const long = card.side === "long";
  const done = card.outcome && ["target", "stopped", "expired"].includes(card.status);
  const unitsText = card.size.units > 0 ? `${card.size.units} ${card.size.unit_label.startsWith("share") ? "sh" : card.size.unit_label.replace("contract(s)", "ctr")}` : "0 (blocked)";

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-testid={`card-trade-${card.id}`}
        className={cn(
          "w-full rounded-xl border bg-card p-4 text-left transition-colors hover:bg-accent/50 active:bg-accent",
          card.recommended ? "border-primary/40" : "border-card-border",
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              {card.recommended && card.rank && <span className="mono flex h-5 min-w-5 items-center justify-center rounded bg-primary/15 px-1 text-xs font-semibold text-primary" data-testid={`rank-${card.id}`}>#{card.rank}</span>}
              <span className="mono text-base font-semibold">{card.instrument.symbol}</span>
              <Pill tone={long ? "pos" : "neg"}>
                {long ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                {long ? "Long" : "Short"}
              </Pill>
              <Pill tone={card.kind === "futures_day" ? "accent" : "neutral"}>{kindLabel(card)}</Pill>
              <Pill tone={card.tier === "tail" ? "accent" : "muted"}>{card.tier === "tail" ? "Tail" : "Base"}</Pill>
              <ExecutionPill execution={execution} />
            </div>
            <div className="mt-0.5 text-sm font-medium leading-tight" data-testid={`name-${card.id}`}>{card.instrument.name}{card.option ? ` · ${card.option.label.toLowerCase()} ${fmtDate(card.option.expiry)} ${card.option.long_strike}${card.option.short_strike ? `/${card.option.short_strike}` : ""}${card.option.right === "C" ? " C" : " P"}` : ""}</div>
            <div className="mt-0.5 truncate text-xs text-muted-foreground">{card.setup_name}</div>
          </div>
          <div className="shrink-0 text-right">
            {done ? (
              <>
                <div className={cn("mono text-base font-semibold", card.outcome!.r_net > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400")}>{fmtR(card.outcome!.r_net)}</div>
                <div className="text-xs text-muted-foreground">{fmtEur(card.outcome!.pnl_eur)}</div>
              </>
            ) : (
              <>
                <div className="mono text-base font-semibold">{fmtPct(card.prob_success)}</div>
                <div className="text-xs text-muted-foreground">{fmtR(card.expectancy_r)} exp.</div>
              </>
            )}
          </div>
        </div>

        {!compact && !card.option && (
          <div className="mt-3 grid grid-cols-4 gap-2 border-t border-border/60 pt-3">
            <Stat label={card.entry_type === "stop" ? "Entry (stop)" : "Entry (limit)"} value={fmtPrice(card.levels.entry, card)} />
            <Stat label="Stop" value={fmtPrice(card.levels.stop, card)} />
            <Stat label="Target" value={fmtPrice(card.levels.target, card)} />
            <Stat label="Size" value={unitsText} sub={card.size.units > 0 ? `risk ${fmtEur(card.size.risk_eur)}` : undefined} />
          </div>
        )}
        {!compact && card.option && (
          <div className="mt-3 grid grid-cols-4 gap-2 border-t border-border/60 pt-3">
            <Stat label="Trigger" value={fmtPrice(card.levels.entry, card)} />
            <Stat label="Premium = max loss" value={fmtUsd(card.option.premium_usd)} tone="neg" />
            <Stat label="At target" value={fmtUsd(card.option.scenarios_usd.at_target, 0, true)} tone="pos" />
            <Stat label="Size" value={unitsText} sub={card.size.units > 0 ? `${fmtNum(card.option.premium_pct_of_capital * 100, 1)}% of capital` : undefined} />
          </div>
        )}

        <div className="mt-3 flex items-center justify-between gap-2">
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
            <StatusPill status={card.status} />
            <RiskClassPill rc={riskClassOf(card)} />
            {card.analyst.veto && <Pill tone="neg"><ShieldAlert className="h-3 w-3" />Vetoed</Pill>}
            {!card.recommended && !card.analyst.veto && <Pill tone="muted">Shadow</Pill>}
            <span className="whitespace-nowrap">{card.kind === "futures_day" ? `Session ${fmtDate(card.session_date)}` : `Signal ${fmtDate(card.signal_date)}`}</span>
          </div>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        </div>
      </button>
      <CardDetail card={card} execution={execution} open={open} onOpenChange={setOpen} />
    </>
  );
}

export function StatusPill({ status }: { status: Card["status"] }) {
  return <Pill tone={statusTone(status)}>{statusLabel[status]}</Pill>;
}

/* ------------------------------------------------------------------ detail sheet */
function CardDetail({ card, execution, open, onOpenChange }: { card: Card; execution?: Execution; open: boolean; onOpenChange: (v: boolean) => void }) {
  const long = card.side === "long";
  const { data: todayFx } = useQuery<TodayView | null>({ queryKey: ["/api/today"] });
  const fx = todayFx?.fx_eurusd ?? 1.1;
  const riskPts = Math.abs(card.levels.entry - card.levels.stop);
  const rewardPts = Math.abs(card.levels.target - card.levels.entry);
  const done = card.outcome && ["target", "stopped", "expired"].includes(card.status);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="max-h-[92dvh] overflow-y-auto rounded-t-2xl px-4 pb-8 sm:mx-auto sm:max-w-lg">
        <SheetHeader className="text-left">
          <SheetTitle className="flex flex-wrap items-baseline gap-x-2 gap-y-0">
            <span className="mono">{card.instrument.symbol}</span>
            <span className="text-sm font-normal text-muted-foreground">{card.instrument.name}</span>
          </SheetTitle>
          <SheetDescription>
            {card.option ? `${card.option.label} on ${card.instrument.symbol}` : long ? "Long" : "Short"} · {card.setup_name} · {card.kind === "futures_day" ? `session ${fmtDate(card.session_date)}` : `signal ${fmtDate(card.signal_date)}, hold up to ${card.levels.horizon_days} sessions`}
          </SheetDescription>
          <div className="flex flex-wrap gap-1 pt-1"><RiskClassPill rc={riskClassOf(card)} /><Pill tone="muted">{STRUCTURE_LABEL[card.structure ?? (card.kind === "futures_day" ? "micro_futures" : "shares")]}</Pill>{card.model_based && <Pill tone="neutral">Model-based estimate</Pill>}</div>
        </SheetHeader>

        {!card.recommended && (
          <div className="mt-4 rounded-lg border border-border bg-muted/50 p-3 text-sm">
            <div className="flex items-center gap-2 font-medium"><Info className="h-4 w-4" />Not recommended, tracked in shadow</div>
            <p className="mt-1 text-muted-foreground">{card.shadow_reason}</p>
          </div>
        )}
        {card.analyst.note && (
          <div className="mt-4 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
            <div className="font-medium">Analyst note</div>
            <p className="mt-1 text-muted-foreground">{card.analyst.note}</p>
          </div>
        )}

        {card.option && <OptionBlock card={card} fx={fx} />}

        {!card.option && <section className="mt-5">
          <h3 className="text-sm font-semibold">Order plan <span className="ml-1 font-normal text-muted-foreground">· <Term k={card.tier === "tail" ? "tail_tier" : "base_tier"}>{card.tier === "tail" ? "Tail trade" : "Base trade"}</Term></span></h3>
          <div className="mt-2 grid grid-cols-3 gap-3 rounded-lg border border-border p-3">
            <Stat label={<Term k={card.entry_type === "stop" ? "stp" : "lmt"}>{card.entry_type === "stop" ? (long ? "Buy stop" : "Sell stop") : (long ? "Buy limit" : "Sell limit")}</Term>} value={fmtPrice(card.levels.entry, card)} />
            <Stat label={<Term k="stop_loss">Stop loss</Term>} value={fmtPrice(card.levels.stop, card)} sub={`${fmtPrice(riskPts, card)} away`} />
            <Stat label={<Term k="target">Take profit</Term>} value={fmtPrice(card.levels.target, card)} sub={`${fmtPrice(rewardPts, card)} away`} />
            <Stat label={<Term k="notional">Size</Term>} value={card.size.units > 0 ? `${card.size.units} ${card.size.unit_label}` : "0"} sub={card.size.units > 0 ? `≈ ${fmtUsd(card.size.notional_usd)} (${fmtNum((card.size.notional_pct_of_capital ?? 0) * 100, 0)}% of capital)` : "blocked"} />
            <Stat label={<Term k="risk_pct">Risk at stop</Term>} value={fmtEur(card.size.units > 0 ? card.size.risk_eur : card.size.risk_usd_1unit / fx)} sub={card.size.units > 0 ? `${fmtUsd(card.size.risk_usd)} · ${fmtNum((card.size.risk_pct_of_capital ?? 0) * 100, 2)}% of capital` : "per 1 unit"} />
            <Stat label={<Term k="rr">Reward : risk</Term>} value={`${(rewardPts / riskPts).toFixed(1)} : 1`} sub={<><Term k="slippage">costs</Term> ≈ {fmtR(-card.size.cost_r)}</>} />
          </div>
          {card.size.block_reason && <p className="mt-2 text-xs text-rose-600 dark:text-rose-400">{card.size.block_reason}</p>}
          <p className="mt-2 text-xs text-muted-foreground">
            Place as a <Term k="bracket">bracket order</Term>: parent {card.entry_type} order with attached stop-loss and take-profit (<Term k="oca">OCA</Term>). <Term k="tif">{card.kind === "futures_day" ? "Day order" : "GTC"}</Term>{card.kind === "futures_day" ? ", flat by 21:55 CET." : " for the entry window, then cancel if unfilled."}
          </p>
          {riskClassOf(card) === "open_ended" && <p className="mt-1 text-xs text-rose-600 dark:text-rose-400">Futures are margined: a gap through the stop can lose more than the planned risk, and in theory more than the margin posted.</p>}
        </section>}

        {card.alternatives && card.alternatives.length > 0 && <AlternativesTable rows={card.alternatives} current={card.structure ?? "shares"} />}

        {card.execution && <ExecutionGuide plan={card.execution} card={card} />}

        <section className="mt-5">
          <h3 className="text-sm font-semibold">Expectation</h3>
          <div className="mt-2 grid grid-cols-3 gap-3 rounded-lg border border-border p-3">
            <Stat label={<Term k="p_win">P(win)</Term>} value={fmtPct(card.prob_success)} sub={`${card.evidence.prior_n} hist. + ${card.evidence.live_n} live`} />
            <Stat label={<Term k="expectancy">Expectancy</Term>} value={fmtR(card.expectancy_r)} sub="after costs" tone={card.expectancy_r >= 0 ? "pos" : "neg"} />
            <Stat label={<Term k="regime">Regime</Term>} value={card.regime.replace("_", " ")} sub={`calibrated on ${card.evidence.regime_used.replace("_", " ")}`} />
            <Stat label="If win" value={fmtUsd(card.expected_gain_usd)} sub={fmtR(card.expected_win_r)} tone="pos" />
            <Stat label="If loss" value={fmtUsd(card.expected_loss_usd)} sub={fmtR(card.expected_loss_r)} tone="neg" />
            <Stat label="Setup status" value={card.evidence.setup_status} />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">Probabilities are posterior estimates: a historical simulation prior that live outcomes gradually overrule. They are not guarantees and the futures prior rests on only ~60 days of intraday data.</p>
        </section>

        <section className="mt-5">
          <h3 className="text-sm font-semibold">Why</h3>
          {card.signals?.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{card.signals.map((sg) => <span key={sg} className="mono rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">{sg}</span>)}</div>}
          <ul className="mt-2 space-y-1.5 text-sm text-muted-foreground">
            {card.rationale.map((r, i) => <li key={i} className="flex gap-2"><span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-foreground/50" />{r}</li>)}
          </ul>
        </section>

        <section className="mt-5">
          <h3 className="text-sm font-semibold">Cancel or skip if</h3>
          <ul className="mt-2 space-y-1.5 text-sm text-muted-foreground">
            {card.invalidation.map((r, i) => <li key={i} className="flex gap-2"><X className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-500" />{r}</li>)}
          </ul>
        </section>

        {card.outcome && (
          <section className="mt-5">
            <h3 className="text-sm font-semibold">System outcome</h3>
            <div className="mt-2 grid grid-cols-3 gap-3 rounded-lg border border-border p-3">
              <Stat label="Result" value={statusLabel[card.status]} />
              <Stat label="Net" value={fmtR(card.outcome.r_net)} tone={card.outcome.r_net > 0 ? "pos" : card.outcome.r_net < 0 ? "neg" : undefined} sub={done ? fmtEur(card.outcome.pnl_eur) : undefined} />
              <Stat label="Fill → exit" value={`${fmtPrice(card.outcome.fill, card)} → ${fmtPrice(card.outcome.exit_price, card)}`} sub={card.outcome.exit_time ? fmtDateTime(card.outcome.exit_time) : undefined} />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">Scored automatically from market data with the card's own levels (stop assumed first when stop and target share a bar). This is the system's record, independent of what you did.</p>
          </section>
        )}

        <Separator className="my-5" />
        <DecisionBar card={card} execution={execution} />
        <Button variant="outline" className="mt-5 w-full" onClick={() => onOpenChange(false)} data-testid="button-close-detail">Close</Button>
      </SheetContent>
    </Sheet>
  );
}

/* ------------------------------------------------------------------ IBKR execution guide */
function ExecutionGuide({ plan, card }: { plan: ExecutionPlan; card: Card }) {
  const o = plan.order;
  return (
    <section className="mt-5" data-testid="section-execution">
      <h3 className="text-sm font-semibold">Execute in IBKR</h3>
      <div className="mt-2 rounded-lg border border-border p-3 text-sm">
        <div className="mono text-xs text-muted-foreground">{plan.instrument.description}</div>
        <div className="mt-1 text-xs text-muted-foreground">{plan.instrument.search_hint}</div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
          <Field k="Action" v={o.action} />
          <Field k="Quantity" v={String(o.quantity)} />
          <Field k={<Term k={o.order_type === "STP" ? "stp" : "lmt"}>Order type</Term>} v={o.order_type} />
          <Field k={<Term k="tif">Time in force</Term>} v={o.time_in_force} />
          <Field k={o.order_type === "STP" ? "Stop price" : card.option ? "Limit (net debit / share)" : "Limit price"} v={card.option ? o.entry_price.toFixed(2) : fmtPrice(o.entry_price, card)} />
          {o.legs?.map((l) => <Field key={`${l.action}${l.strike}`} k={`${l.action === "BUY" ? "Buy" : "Sell"} leg`} v={`${l.strike} ${l.right} ${fmtDate(l.expiry)}`} />)}
          {o.attached.map((a) => <Field key={a.role} k={a.role === "stop_loss" ? "Stop-loss (STP)" : "Profit taker (LMT)"} v={`${a.action} ${fmtPrice(a.price, card)}`} />)}
          <Field k={<Term k="smart">Exchange</Term>} v={plan.instrument.exchange.split(" ")[0]} />
        </div>
        {o.condition && <p className="mt-2 text-xs font-medium">{o.condition}</p>}
        {plan.capital.margin_note && <p className="mt-1 text-xs text-muted-foreground">{plan.capital.margin_note}</p>}
        <div className="mt-3 grid grid-cols-3 gap-2 border-t border-border/60 pt-3">
          <Stat label="Max planned loss" value={fmtUsd(plan.risk_reward.max_planned_loss_usd)} tone="neg" sub={`${plan.capital.risk_pct_of_capital}% of capital`} />
          <Stat label={card.option ? "Modelled gain at target" : "Planned gain"} value={fmtUsd(plan.risk_reward.planned_gain_usd)} tone="pos" sub={plan.risk_reward.ratio != null ? `${plan.risk_reward.ratio} : 1` : undefined} />
          <Stat label="Est. costs" value={fmtUsd(plan.risk_reward.est_costs_usd)} sub="commission + slippage" />
        </div>
      </div>
      <Accordion type="single" collapsible className="mt-2 rounded-lg border border-border px-3">
        <AccordionItem value="pre" className="border-border/60">
          <AccordionTrigger className="py-2.5 text-sm hover:no-underline">Before you place it</AccordionTrigger>
          <AccordionContent><ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">{plan.pre_checks.map((t, i) => <li key={i}>{t}</li>)}</ol></AccordionContent>
        </AccordionItem>
        <AccordionItem value="tws" className="border-border/60">
          <AccordionTrigger className="py-2.5 text-sm hover:no-underline" data-testid="acc-tws"><span className="flex items-center gap-2"><Monitor className="h-4 w-4" />Trader Workstation / Desktop</span></AccordionTrigger>
          <AccordionContent><ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">{plan.steps_tws.map((t, i) => <li key={i}>{t}</li>)}</ol></AccordionContent>
        </AccordionItem>
        <AccordionItem value="mobile" className="border-0">
          <AccordionTrigger className="py-2.5 text-sm hover:no-underline" data-testid="acc-mobile"><span className="flex items-center gap-2"><Smartphone className="h-4 w-4" />IBKR Mobile</span></AccordionTrigger>
          <AccordionContent><ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">{plan.steps_mobile.map((t, i) => <li key={i}>{t}</li>)}</ol></AccordionContent>
        </AccordionItem>
      </Accordion>
      <p className="mt-2 text-xs text-muted-foreground"><Term k="paper">Paper account</Term>: {plan.paper_note}</p>
    </section>
  );
}

export const STRUCTURE_LABEL: Record<string, string> = {
  shares: "Shares / ETF", long_call: "Long call", long_put: "Long put", debit_spread: "Debit spread",
  leveraged_etf: "Leveraged ETF", micro_futures: "Micro futures", cfd: "CFD",
};

/* ------------------------------------------------------------------ option structure block */
function OptionBlock({ card, fx }: { card: Card; fx: number }) {
  const o = card.option!;
  const sc = o.scenarios_usd;
  return (
    <section className="mt-5" data-testid="section-option">
      <h3 className="text-sm font-semibold">Option structure <span className="ml-1 font-normal text-muted-foreground">· <Term k="tail_tier">Tail trade</Term>, <Term k="defined_risk">defined risk</Term></span></h3>
      <div className="mt-2 rounded-lg border border-border p-3">
        <div className="mono text-xs">{o.long_contract}{o.short_contract ? ` / ${o.short_contract}` : ""}</div>
        <div className="mt-2 grid grid-cols-3 gap-3">
          <Stat label="Structure" value={o.label} sub={`${o.right === "C" ? "call" : "put"}${o.short_strike ? "s" : ""} ${o.long_strike}${o.short_strike ? ` / ${o.short_strike}` : ""}`} />
          <Stat label="Expiry" value={fmtDate(o.expiry)} sub={<><Term k="dte">{o.dte} DTE</Term></>} />
          <Stat label={<Term k="delta">Delta / IV</Term>} value={`${o.long_delta.toFixed(2)} / ${fmtNum(o.long_iv * 100, 0)}%`} sub={`OI ${o.quote.open_interest}`} />
          <Stat label="Underlying trigger" value={fmtPrice(card.levels.entry, card)} sub={`stop ${fmtPrice(card.levels.stop, card)} · target ${fmtPrice(card.levels.target, card)}`} />
          <Stat label={<Term k="premium">Premium = max loss</Term>} value={fmtUsd(o.premium_usd)} tone="neg" sub={`≈ ${fmtEur(o.premium_usd / fx)} · ${fmtNum(o.premium_pct_of_capital * 100, 1)}% of capital`} />
          <Stat label={<Term k="breakeven">Breakeven at expiry</Term>} value={fmtPrice(o.breakeven, card)} sub={o.max_gain_usd != null ? `max gain ${fmtUsd(o.max_gain_usd)}` : "gain not capped"} />
        </div>
        <div className="mt-3 border-t border-border/60 pt-3">
          <div className="text-xs text-muted-foreground">Modelled profit or loss of 1 contract, before commission and spread</div>
          <div className="mt-1 grid grid-cols-3 gap-3">
            <Stat label="Underlying at target" value={fmtUsd(sc.at_target, 0, true)} tone={sc.at_target >= 0 ? "pos" : "neg"} sub={o.payoff_ratio_at_target != null ? `${o.payoff_ratio_at_target.toFixed(1)}x premium` : undefined} />
            <Stat label="Underlying at stop" value={fmtUsd(sc.at_stop, 0, true)} tone={sc.at_stop >= 0 ? "pos" : "neg"} sub="sell, do not wait" />
            <Stat label="Flat at time exit" value={fmtUsd(sc.flat_at_time_exit, 0, true)} tone={sc.flat_at_time_exit >= 0 ? "pos" : "neg"} sub="time decay" />
          </div>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-3 border-t border-border/60 pt-3">
          <Stat label={<Term k="p_win">P(profit)</Term>} value={fmtPct(o.p_win)} sub={`${o.n_paths} modelled paths`} />
          <Stat label={<Term k="expectancy">Expectancy</Term>} value={fmtR(o.expectancy_r)} sub="per premium unit" tone={o.expectancy_r >= 0 ? "pos" : "neg"} />
          <Stat label="Costs" value={fmtR(-o.cost_r)} sub="commission + spread" />
        </div>
        {card.size.block_reason && <p className="mt-2 text-xs text-rose-600 dark:text-rose-400">{card.size.block_reason}</p>}
        <p className="mt-2 text-xs text-muted-foreground">Estimate, not a fact: the underlying's backtested exit paths are priced with Black-Scholes at today's <Term k="iv">implied volatility</Term>. No historical option prices were used, and implied volatility will move. The premium assumes you buy only once the underlying trades through the trigger.</p>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ alternatives compared */
function AlternativesTable({ rows, current }: { rows: AlternativeRow[]; current: string }) {
  return (
    <section className="mt-5" data-testid="section-alternatives">
      <h3 className="text-sm font-semibold">Ways to express this signal</h3>
      <p className="mt-1 text-xs text-muted-foreground">The engine compares the share position with defined-risk option structures and with leveraged instruments. The highlighted row is this card.</p>
      <div className="mt-2 divide-y divide-border/60 rounded-lg border border-border">
        {rows.map((r, i) => {
          const isCurrent = r.structure === current && r.chosen !== false;
          return (
            <div key={i} className={cn("p-3", isCurrent && "bg-primary/8")}>
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="text-sm font-medium">{r.label}</span>
                {r.detail && <span className="mono text-xs text-muted-foreground">{r.detail}</span>}
                <Pill tone={r.risk_class === "defined" ? "pos" : r.risk_class === "open_ended" ? "neg" : "muted"}>{RISK_CLASS_LABEL[r.risk_class]}</Pill>
                {isCurrent && <Pill tone="accent">This card</Pill>}
                {r.fits_budget === false && <Pill tone="neg">Over premium budget</Pill>}
                {r.generated === false && <Pill tone="muted">Not proposed</Pill>}
              </div>
              {r.capital_usd != null || r.max_loss_usd != null || r.max_loss_note ? (
                <div className="mt-2 grid grid-cols-4 gap-2">
                  <Stat label="Capital" value={r.capital_usd != null ? fmtUsd(r.capital_usd) : "–"} />
                  <Stat label="Max loss" value={r.max_loss_usd != null ? fmtUsd(r.max_loss_usd) : r.max_loss_note ?? "–"} tone="neg" />
                  <Stat label="At target" value={r.gain_at_target_usd != null ? fmtUsd(r.gain_at_target_usd, 0, true) : "–"} tone="pos" />
                  <Stat label="P(win) · exp." value={r.p_win != null ? fmtPct(r.p_win) : "–"} sub={r.expectancy_r != null ? fmtR(r.expectancy_r) : undefined} />
                </div>
              ) : null}
              {r.note && <p className="mt-2 text-xs text-muted-foreground">{r.note}</p>}
              {r.evidence && <p className="mt-1 text-[11px] text-muted-foreground">{r.evidence}</p>}
              {r.permission && <p className="mt-1 text-[11px] text-muted-foreground">IBKR permission: {r.permission}</p>}
            </div>
          );
        })}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">Exp. = expectancy per unit of risk (stop distance for shares, premium for options). Rows marked "not proposed" explain why the engine does not generate that instrument.</p>
    </section>
  );
}

function Field({ k, v }: { k: React.ReactNode; v: string }) {
  return (
    <div className="rounded-md bg-muted/60 px-2 py-1.5">
      <div className="text-[11px] text-muted-foreground">{k}</div>
      <div className="mono font-medium">{v}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ your decision */
function DecisionBar({ card, execution }: { card: Card; execution?: Execution }) {
  const { toast } = useToast();
  const { data: today } = useQuery<TodayView | null>({ queryKey: ["/api/today"] });
  const fx = today?.fx_eurusd ?? 1.1;
  const [fill, setFill] = useState(execution?.fillPrice?.toString() ?? "");
  const [exit, setExit] = useState(execution?.exitPrice?.toString() ?? "");
  const [units, setUnits] = useState(execution?.units?.toString() ?? (card.size.units || "").toString());
  const [note, setNote] = useState(execution?.note ?? "");

  const save = useMutation({
    mutationFn: async (decision: "executed" | "skipped") => {
      const f = parseFloat(fill), e = parseFloat(exit), u = parseFloat(units);
      let pnlEur: number | null = null;
      if (decision === "executed" && Number.isFinite(f) && Number.isFinite(e) && Number.isFinite(u)) {
        const mult = card.option ? 100 : (card.instrument.point_value ?? 1);
        const sign = card.option ? 1 : card.side === "long" ? 1 : -1; // option fill/exit are debits paid/received per share
        const pnlUsd = sign * (e - f) * mult * u - (card.kind === "futures_day" ? 2.48 * u : card.option ? 1.3 * u * (card.option.short_strike ? 2 : 1) : 2);
        pnlEur = Math.round((pnlUsd / fx) * 100) / 100;
      }
      const body = {
        decision,
        fillPrice: Number.isFinite(f) ? f : null,
        exitPrice: Number.isFinite(e) ? e : null,
        units: Number.isFinite(u) ? u : null,
        pnlEur,
        note: note || null,
      };
      await upsertExecution(card.id, body);
      return body;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/executions"] });
      toast({ title: "Saved", description: "Your decision is recorded in the journal." });
    },
    onError: (e: Error) => toast({ title: "Could not save", description: e.message, variant: "destructive" }),
  });
  const clear = useMutation({
    mutationFn: async () => deleteExecution(card.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["/api/executions"] }),
  });

  return (
    <section>
      <h3 className="text-sm font-semibold">Your decision</h3>
      <p className="mt-1 text-xs text-muted-foreground">Record what you actually did. Fill and exit are optional; add them when the trade closes so your personal P&L is exact.{card.option ? " For options enter the net debit paid and the net credit received per share." : ""}</p>
      {execution?.source === "auto" && <p className="mt-1 text-xs text-muted-foreground">Marked skipped automatically{execution.reason ? `: ${execution.reason}` : ""}. Saving a decision here overrides it.</p>}
      <div className="mt-3 grid grid-cols-3 gap-2">
        <label className="text-xs text-muted-foreground">Fill
          <Input inputMode="decimal" value={fill} onChange={(e) => setFill(e.target.value)} placeholder={fmtPrice(card.levels.entry, card)} className="mono mt-1" data-testid="input-fill" />
        </label>
        <label className="text-xs text-muted-foreground">Exit
          <Input inputMode="decimal" value={exit} onChange={(e) => setExit(e.target.value)} placeholder="–" className="mono mt-1" data-testid="input-exit" />
        </label>
        <label className="text-xs text-muted-foreground">Units
          <Input inputMode="decimal" value={units} onChange={(e) => setUnits(e.target.value)} className="mono mt-1" data-testid="input-units" />
        </label>
      </div>
      <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note (optional)" className="mt-2" data-testid="input-note" />
      <div className="mt-3 flex gap-2">
        <Button className="flex-1" onClick={() => save.mutate("executed")} disabled={save.isPending} data-testid="button-executed">
          <Check className="mr-1.5 h-4 w-4" />Executed
        </Button>
        <Button variant="secondary" className="flex-1" onClick={() => save.mutate("skipped")} disabled={save.isPending} data-testid="button-skipped">
          <X className="mr-1.5 h-4 w-4" />Skipped
        </Button>
        {execution && (
          <Button variant="ghost" onClick={() => clear.mutate()} data-testid="button-clear">Clear</Button>
        )}
      </div>
      {execution && <p className="mt-2 text-xs text-muted-foreground">Last saved {fmtDateTime(execution.updatedAt)}{execution.pnlEur !== null ? ` · your P&L ${fmtEur(execution.pnlEur, 2)}` : ""}</p>}
    </section>
  );
}

export { Badge };
