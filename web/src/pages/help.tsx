import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Input } from "@/components/ui/input";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { SectionTitle } from "./today";
import Rules from "./rules";
import { GLOSSARY, GROUP_LABEL, type Term } from "@/lib/glossary";
import type { TodayView } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function Help() {
  const [tab, setTab] = useState<"glossary" | "rules" | "ibkr">("glossary");
  return (
    <div className="space-y-4 p-4">
      <h1 className="text-lg font-semibold">Help</h1>
      <div className="flex w-max gap-1 rounded-lg bg-muted p-1">
        {([["glossary", "Glossary"], ["rules", "Rules & limits"], ["ibkr", "IBKR basics"]] as const).map(([k, l]) => (
          <button key={k} type="button" onClick={() => setTab(k)} data-testid={`help-tab-${k}`}
            className={cn("rounded-md px-3 py-1.5 text-sm transition-colors", tab === k ? "bg-background font-medium shadow-sm" : "text-muted-foreground")}>{l}</button>
        ))}
      </div>
      {tab === "glossary" && <Glossary />}
      {tab === "rules" && <div className="-m-4"><Rules /></div>}
      {tab === "ibkr" && <IbkrBasics />}
    </div>
  );
}

function Glossary() {
  const [q, setQ] = useState("");
  const groups = useMemo(() => {
    const out: Record<string, [string, Term][]> = {};
    for (const [k, t] of Object.entries(GLOSSARY)) {
      const hay = `${t.term} ${t.short} ${t.effect ?? ""} ${t.ibkr ?? ""}`.toLowerCase();
      if (q && !hay.includes(q.toLowerCase())) continue;
      (out[t.group] ??= []).push([k, t]);
    }
    return out;
  }, [q]);
  return (
    <div className="space-y-4">
      <Input placeholder="Search terms (e.g. bracket, R, expectancy)" value={q} onChange={(e) => setQ(e.target.value)} data-testid="input-glossary-search" />
      {Object.keys(groups).length === 0 && <p className="text-sm text-muted-foreground">No term matches.</p>}
      {(Object.keys(GROUP_LABEL) as Term["group"][]).filter((g) => groups[g]).map((g) => (
        <section key={g}>
          <SectionTitle title={GROUP_LABEL[g]} count={groups[g].length} />
          <Accordion type="multiple" className="rounded-xl border border-card-border bg-card px-3">
            {groups[g].map(([k, t]) => (
              <AccordionItem key={k} value={k} className="border-border/60">
                <AccordionTrigger className="py-2.5 text-left text-sm hover:no-underline" data-testid={`glossary-${k}`}>{t.term}</AccordionTrigger>
                <AccordionContent className="space-y-1.5 text-sm text-muted-foreground">
                  <p>{t.short}</p>
                  {t.effect && <p><span className="font-medium text-foreground">Effect: </span>{t.effect}</p>}
                  {t.ibkr && <p className="mono text-xs">{t.ibkr}</p>}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </section>
      ))}
    </div>
  );
}

function IbkrBasics() {
  const { data } = useQuery<TodayView | null>({ queryKey: ["/api/today"] });
  return (
    <div className="space-y-4 text-sm">
      <section>
        <SectionTitle title="Before the first paper trade" />
        <ol className="list-decimal space-y-1.5 rounded-xl border border-card-border bg-card p-4 pl-8 text-muted-foreground">
          <li>Log in to IBKR Mobile or TWS and switch to the <span className="text-foreground">paper account</span> (account id starts with DU; the app shows a "Paper" badge). Client Portal: top-right account menu → Paper.</li>
          <li>Account Settings → Trading Permissions: enable United States stocks/ETFs and US futures (CME) if you want the micro-futures cards. Permissions take a day to activate.</li>
          <li>Settings → Trading → Order presets: set default Time in Force to DAY and turn off "Outside RTH" by default.</li>
          <li>Enable price alerts or set phone alarms for the 21:55 CET futures flat time and for swing time exits.</li>
          <li>Base currency EUR with USD positions: IBKR converts or borrows USD automatically; in paper this is invisible, live it costs a small FX spread.</li>
        </ol>
      </section>
      <section>
        <SectionTitle title="Reading a card" />
        <div className="space-y-2 rounded-xl border border-card-border bg-card p-4 text-muted-foreground">
          <p><span className="text-foreground">Rank</span> orders today's candidates by expectancy, then probability, then reward:risk. <span className="text-foreground">Base</span> and <span className="text-foreground">Tail</span> badges show the tier and therefore the size.</p>
          <p><span className="text-foreground">Order plan</span> gives the exact entry, stop and target. <span className="text-foreground">Execute in IBKR</span> expands into TWS and Mobile step lists with the fields pre-filled.</p>
          <p><span className="text-foreground">Cancel or skip if</span> lists the invalidation conditions; if any holds when you look at the card, do not place the order.</p>
          <p><span className="text-foreground">Your decision</span> records what you did. Skipped cards are still scored, so the Performance tab can compare your choices with the system.</p>
        </div>
      </section>
      <section>
        <SectionTitle title="Order types used here" />
        <div className="rounded-xl border border-card-border bg-card p-4 text-muted-foreground">
          <p>Only four building blocks: <span className="mono text-foreground">STP</span> entries for breakouts, <span className="mono text-foreground">LMT</span> entries for pullbacks, and a <span className="text-foreground">bracket</span> (stop-loss STP + profit-taker LMT, OCA) attached to every entry. No market orders except to flatten a futures day trade at 21:55 CET or to execute a time exit.</p>
          <p className="mt-2">Regulatory note: {data?.pdt_applies === false ? "your account is configured as not subject to the US pattern-day-trader rule; no weekly cap on intraday stock trades is applied." : "pattern-day-trader limits apply."}</p>
        </div>
      </section>
    </div>
  );
}
