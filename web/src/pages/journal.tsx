import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Skeleton } from "@/components/ui/skeleton";
import { TradeCard, useExecutions } from "@/components/cards";
import { EmptyState, SectionTitle } from "./today";
import type { Card } from "@/lib/types";
import { cn } from "@/lib/utils";

type Filter = "all" | "recommended" | "executed" | "skipped" | "open" | "closed";

export default function Journal() {
  const { data: cards, isLoading } = useQuery<Card[]>({ queryKey: ["/api/cards"] });
  const { data: execs } = useExecutions();
  const [filter, setFilter] = useState<Filter>("all");
  const byCard = useMemo(() => new Map((execs ?? []).map((e) => [e.cardId, e])), [execs]);

  const list = useMemo(() => {
    const all = [...(cards ?? [])].sort((a, b) => (a.session_date < b.session_date ? 1 : a.session_date > b.session_date ? -1 : a.id.localeCompare(b.id)));
    switch (filter) {
      case "recommended": return all.filter((c) => c.recommended);
      case "executed": return all.filter((c) => byCard.get(c.id)?.decision === "executed");
      case "skipped": return all.filter((c) => byCard.get(c.id)?.decision === "skipped");
      case "open": return all.filter((c) => c.status === "pending" || c.status === "open");
      case "closed": return all.filter((c) => ["target", "stopped", "expired"].includes(c.status));
      default: return all;
    }
  }, [cards, filter, byCard]);

  const groups = useMemo(() => {
    const m = new Map<string, Card[]>();
    for (const c of list) m.set(c.session_date, [...(m.get(c.session_date) ?? []), c]);
    return Array.from(m.entries());
  }, [list]);

  if (isLoading) return <div className="space-y-3 p-4"><Skeleton className="h-8 w-full" /><Skeleton className="h-28 w-full rounded-xl" /><Skeleton className="h-28 w-full rounded-xl" /></div>;

  const tabs: { k: Filter; l: string }[] = [
    { k: "all", l: "All" }, { k: "recommended", l: "Recommended" }, { k: "executed", l: "Executed" }, { k: "skipped", l: "Skipped" }, { k: "open", l: "Open" }, { k: "closed", l: "Closed" },
  ];

  return (
    <div className="space-y-4 p-4">
      <h1 className="text-lg font-semibold">Journal</h1>
      <div className="-mx-4 overflow-x-auto px-4">
        <div className="flex w-max gap-1 rounded-lg bg-muted p-1">
          {tabs.map((t) => (
            <button key={t.k} type="button" onClick={() => setFilter(t.k)} data-testid={`filter-${t.k}`}
              className={cn("rounded-md px-3 py-1.5 text-sm transition-colors", filter === t.k ? "bg-background font-medium shadow-sm" : "text-muted-foreground")}>{t.l}</button>
          ))}
        </div>
      </div>
      {groups.length === 0 ? (
        <EmptyState title="Nothing here yet" body="Cards appear after each morning run. Closed cards are scored automatically the next morning." />
      ) : (
        groups.map(([date, cs]) => (
          <section key={date}>
            <SectionTitle title={new Date(date + "T12:00:00").toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", month: "short" })} count={cs.length} />
            <div className="space-y-3">{cs.map((c) => <TradeCard key={c.id} card={c} execution={byCard.get(c.id)} compact />)}</div>
          </section>
        ))
      )}
    </div>
  );
}
