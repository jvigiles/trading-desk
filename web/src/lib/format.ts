import type { Card } from "./types";

export const fmtNum = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined || Number.isNaN(v) ? "–" : v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

export const fmtEur = (v: number | null | undefined, d = 0) =>
  v === null || v === undefined ? "–" : `${v < 0 ? "−" : ""}€${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })}`;

export const fmtUsd = (v: number | null | undefined, d = 0) =>
  v === null || v === undefined ? "–" : `${v < 0 ? "−" : ""}$${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })}`;

export const fmtPct = (v: number | null | undefined, d = 0) => (v === null || v === undefined ? "–" : `${(v * 100).toFixed(d)}%`);

export const fmtR = (v: number | null | undefined, d = 2) => {
  if (v === null || v === undefined) return "–";
  const r = Math.round(v * 10 ** d) / 10 ** d;
  return `${r > 0 ? "+" : r < 0 ? "−" : ""}${Math.abs(r).toFixed(d)}R`;
};

export const fmtPrice = (v: number | null | undefined, card?: Card) => {
  if (v === null || v === undefined) return "–";
  const tick = card?.instrument.tick;
  const d = tick && tick < 1 ? Math.max(2, String(tick).split(".")[1]?.length ?? 2) : 2;
  return v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
};

export const fmtDate = (iso: string | null | undefined) => {
  if (!iso) return "–";
  const d = new Date(iso.length === 10 ? iso + "T12:00:00" : iso);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
};

export const fmtDateTime = (iso: string | null | undefined) => {
  if (!iso) return "–";
  const d = new Date(iso);
  return d.toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Zurich" }) + " CET";
};

export const statusLabel: Record<Card["status"], string> = {
  pending: "Waiting for trigger",
  open: "In position",
  target: "Target hit",
  stopped: "Stopped out",
  expired: "Time exit",
  not_triggered: "Not triggered",
  gap_cancelled: "Cancelled (gap)",
  vetoed: "Vetoed",
};

export const statusTone = (s: Card["status"]): "pos" | "neg" | "neutral" | "muted" => {
  if (s === "target") return "pos";
  if (s === "stopped") return "neg";
  if (s === "expired") return "neutral";
  if (s === "pending" || s === "open") return "neutral";
  return "muted";
};

export const regimeLabel = (r: string) => r.replace("_vol", " volatility").replace("_", " ");

export const setupShort: Record<string, string> = {
  FUT_PDR_BREAKOUT: "Futures range breakout",
  SWING_PULLBACK: "Swing pullback",
  SWING_BREAKOUT: "Swing breakout",
  SWING_BREAKOUT_RUNNER: "Breakout runner (tail)",
  EVENT_SCOUT: "Event scout (tail)",
};
