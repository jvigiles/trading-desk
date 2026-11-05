import { createClient } from "@supabase/supabase-js";

// Public (anon) key: safe to ship in the browser. All data access is gated by Row Level Security,
// which only allows signed-in users; signups are disabled in the Supabase project.
export const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string;
export const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
});

export type ExecutionRow = {
  card_id: string;
  decision: "executed" | "skipped";
  fill_price: number | null;
  exit_price: number | null;
  units: number | null;
  pnl_eur: number | null;
  note: string | null;
  updated_at: string;
  source?: "user" | "auto";
  reason?: string | null;
};

export async function readSnapshot<T>(key: string): Promise<{ payload: T; updated_at: string } | null> {
  const { data, error } = await supabase.from("snapshots").select("payload, updated_at").eq("key", key).maybeSingle();
  if (error) throw new Error(error.message);
  return (data as { payload: T; updated_at: string } | null) ?? null;
}

export async function readExecutions() {
  const { data, error } = await supabase.from("executions").select("*");
  if (error) throw new Error(error.message);
  return (data as ExecutionRow[]).map((r) => ({
    cardId: r.card_id, decision: r.decision, fillPrice: r.fill_price, exitPrice: r.exit_price,
    units: r.units, pnlEur: r.pnl_eur, note: r.note, updatedAt: r.updated_at, source: r.source ?? "user", reason: r.reason ?? null,
  }));
}

export async function upsertExecution(cardId: string, body: { decision: "executed" | "skipped"; fillPrice?: number | null; exitPrice?: number | null; units?: number | null; pnlEur?: number | null; note?: string | null }) {
  const { error } = await supabase.from("executions").upsert({
    card_id: cardId, decision: body.decision, fill_price: body.fillPrice ?? null, exit_price: body.exitPrice ?? null,
    units: body.units ?? null, pnl_eur: body.pnlEur ?? null, note: body.note ?? null, updated_at: new Date().toISOString(),
    source: "user", reason: null,
  });
  if (error) throw new Error(error.message);
}

export async function deleteExecution(cardId: string) {
  const { error } = await supabase.from("executions").delete().eq("card_id", cardId);
  if (error) throw new Error(error.message);
}

export async function requestRefresh(note: string) {
  const { error } = await supabase.from("refresh_requests").insert({ note });
  if (error) throw new Error(error.message);
}
