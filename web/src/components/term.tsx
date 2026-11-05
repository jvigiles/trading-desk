import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { GLOSSARY } from "@/lib/glossary";
import { cn } from "@/lib/utils";

/** Inline glossary term: dotted underline, tap/click to see the definition and its effect on execution/risk. */
export function Term({ k, children, className }: { k: keyof typeof GLOSSARY | string; children?: React.ReactNode; className?: string }) {
  const t = GLOSSARY[k];
  if (!t) return <>{children}</>;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" className={cn("inline cursor-help border-b border-dotted border-muted-foreground/70 text-left hover:border-foreground", className)} data-testid={`term-${k}`}>
          {children ?? t.term}
        </button>
      </PopoverTrigger>
      <PopoverContent side="top" align="start" className="w-80 max-w-[calc(100vw-2rem)] space-y-2 text-sm">
        <div className="font-semibold">{t.term}</div>
        <p className="text-muted-foreground">{t.short}</p>
        {t.effect && <p><span className="font-medium">Effect: </span><span className="text-muted-foreground">{t.effect}</span></p>}
        {t.ibkr && <p className="mono text-xs text-muted-foreground">{t.ibkr}</p>}
      </PopoverContent>
    </Popover>
  );
}
