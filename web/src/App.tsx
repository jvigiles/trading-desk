import { useEffect, useState } from "react";
import { Switch, Route, Router, Link, useLocation } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import { QueryClientProvider } from "@tanstack/react-query";
import { BookOpen, Brain, LineChart, LogOut, Moon, ScrollText, Sun, Sunrise } from "lucide-react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import Login from "@/pages/login";
import { queryClient } from "./lib/queryClient";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import NotFound from "@/pages/not-found";
import Today from "@/pages/today";
import Journal from "@/pages/journal";
import Performance from "@/pages/performance";
import Learning from "@/pages/learning";
import Rules from "@/pages/rules";
import Help from "@/pages/help";

const NAV = [
  { href: "/", label: "Today", icon: Sunrise },
  { href: "/journal", label: "Journal", icon: BookOpen },
  { href: "/performance", label: "Performance", icon: LineChart },
  { href: "/learning", label: "Learning", icon: Brain },
  { href: "/help", label: "Help", icon: ScrollText },
];

function Shell() {
  const [loc] = useLocation();
  const [dark, setDark] = useState(() => (typeof window !== "undefined" ? window.matchMedia("(prefers-color-scheme: dark)").matches : true));
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-lg flex-col bg-background text-foreground md:max-w-2xl">
      <div className="sticky top-0 z-20 flex items-center justify-between border-b border-border bg-background/90 px-4 py-2.5 backdrop-blur">
        <div className="flex items-center gap-2">
          <span className="mono text-sm font-semibold tracking-tight">Trading Desk</span>
          <span className="text-xs text-muted-foreground">IBKR · manual execution</span>
        </div>
        <div className="flex items-center gap-1">
          <button type="button" onClick={() => setDark((d) => !d)} className="rounded-md p-1.5 text-muted-foreground hover:bg-accent" aria-label="Toggle theme" data-testid="button-theme">
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <button type="button" onClick={() => supabase.auth.signOut()} className="rounded-md p-1.5 text-muted-foreground hover:bg-accent" aria-label="Sign out" data-testid="button-logout">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>

      <main className="pb-safe flex-1">
        <Switch>
          <Route path="/" component={Today} />
          <Route path="/journal" component={Journal} />
          <Route path="/performance" component={Performance} />
          <Route path="/learning" component={Learning} />
          <Route path="/rules" component={Rules} />
          <Route path="/help" component={Help} />
          <Route component={NotFound} />
        </Switch>
      </main>

      <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-background/95 backdrop-blur">
        <div className="mx-auto grid max-w-lg grid-cols-5 md:max-w-2xl" style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}>
          {NAV.map((n) => {
            const active = loc === n.href;
            const Icon = n.icon;
            return (
              <Link key={n.href} href={n.href} data-testid={`nav-${n.label.toLowerCase()}`}
                className={cn("flex flex-col items-center gap-0.5 py-2 text-[11px] transition-colors", active ? "text-primary" : "text-muted-foreground hover:text-foreground")}>
                <Icon className="h-5 w-5" strokeWidth={active ? 2.2 : 1.8} />
                {n.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}

function Gate() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => { setSession(s); if (!s) queryClient.clear(); });
    return () => sub.subscription.unsubscribe();
  }, []);
  useEffect(() => {
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.classList.toggle("dark", dark);
  }, []);
  if (session === undefined) return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;
  if (!session) return <Login />;
  return <Shell />;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Router hook={useHashLocation}>
          <Gate />
        </Router>
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
