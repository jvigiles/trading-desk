"""Supabase I/O for the engine (REST, no extra dependencies).

Env: SUPABASE_URL, SUPABASE_ANON_KEY, ENGINE_SECRET  (from engine/.env locally or CI secrets).
All writes go through the `engine_write` RPC which checks ENGINE_SECRET server-side; the anon key
alone cannot write snapshots. Executions are read through `engine_read_executions`.
"""
import json
import os
import urllib.request
import urllib.error


def _load_env():
    p = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_ANON_KEY")
SECRET = os.environ.get("ENGINE_SECRET")


def enabled() -> bool:
    return bool(URL and KEY and SECRET)


def _rpc(name: str, body: dict):
    req = urllib.request.Request(
        f"{URL}/rest/v1/rpc/{name}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"supabase rpc {name} failed {e.code}: {e.read().decode()[:300]}")


def write_snapshot(key: str, payload) -> None:
    _rpc("engine_write", {"p_secret": SECRET, "p_key": key, "p_payload": payload})


def read_executions() -> list:
    rows = _rpc("engine_read_executions", {"p_secret": SECRET}) or []
    # normalise to the camelCase shape the app and metrics use
    return [{"cardId": r["card_id"], "decision": r["decision"], "fillPrice": r.get("fill_price"),
             "exitPrice": r.get("exit_price"), "units": r.get("units"), "pnlEur": r.get("pnl_eur"),
             "note": r.get("note"), "updatedAt": r.get("updated_at"), "source": r.get("source") or "user",
             "reason": r.get("reason")} for r in rows]


def upsert_executions(rows: list) -> int:
    """Insert decision rows that do not exist yet (never overwrites a user's decision)."""
    return _rpc("engine_insert_executions", {"p_secret": SECRET, "p_rows": rows}) or 0


def read_refresh_requests() -> list:
    return _rpc("engine_read_refresh_requests", {"p_secret": SECRET}) or []


def read_snapshot(key: str):
    """Returns {"key","payload","updated_at"} or None."""
    return _rpc("engine_read_snapshot", {"p_secret": SECRET, "p_key": key})


def hydrate(data_dir: str, keys=("cards", "state", "analyst_notes")) -> list:
    """Make Supabase the source of truth: pull each snapshot into data/<key>.json when the local file is
    missing or older than the snapshot (GitHub Actions runners start with an empty data/ directory)."""
    import datetime as _dt
    pulled = []
    if not enabled():
        return pulled
    os.makedirs(data_dir, exist_ok=True)
    for key in keys:
        try:
            snap = read_snapshot(key)
        except Exception as e:  # network hiccup: keep local copy
            print(f"hydrate {key}: {e}")
            continue
        if not snap or snap.get("payload") is None:
            continue
        path = os.path.join(data_dir, f"{key}.json")
        remote_ts = _dt.datetime.fromisoformat(snap["updated_at"].replace("Z", "+00:00")).timestamp()
        local_ts = os.path.getmtime(path) if os.path.exists(path) else 0
        if remote_ts > local_ts + 1:
            with open(path, "w") as f:
                json.dump(snap["payload"], f, indent=2)
            os.utime(path, (remote_ts, remote_ts))
            pulled.append(key)
    return pulled


def mark_refresh_done() -> int:
    return _rpc("engine_mark_refresh_done", {"p_secret": SECRET}) or 0
