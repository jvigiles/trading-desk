import { QueryClient, QueryFunction } from "@tanstack/react-query";
import { readExecutions, readSnapshot } from "./supabase";

/** Query keys mirror the old REST routes so pages stay unchanged:
 *  "/api/today" | "/api/cards" | "/api/metrics" | "/api/state" -> snapshots; "/api/executions" -> executions. */
const queryFn: QueryFunction = async ({ queryKey }) => {
  const key = String(queryKey[0]);
  if (key === "/api/executions") return readExecutions();
  const snapKey = key.replace("/api/", "");
  const snap = await readSnapshot<unknown>(snapKey);
  if (!snap) return null;
  const payload = snap.payload as Record<string, unknown> | unknown[];
  if (payload && !Array.isArray(payload) && typeof payload === "object") {
    return { ...(payload as Record<string, unknown>), _updated_at: snap.updated_at };
  }
  return payload;
};

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { queryFn, refetchInterval: false, refetchOnWindowFocus: true, staleTime: 60_000, retry: 1 },
    mutations: { retry: false },
  },
});
