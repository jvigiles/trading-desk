# Trading Desk – runbook

Live app: https://jvigiles.github.io/trading-desk/ (GitHub Pages, hash routing, login via Supabase).
Repo: https://github.com/jvigiles/trading-desk (public; source only, no data, no secrets).
Storage: Supabase project `pguwtcksqnfpdoqspqlt` — tables `snapshots` (today/cards/metrics/state/analyst_notes),
`executions` (user decisions), `refresh_requests`. The engine is the only writer of snapshots (secret-checked RPCs).

Paths: engine `engine/`, local data cache `data/` (git-ignored; Supabase is the source of truth, `run_daily.py` pulls newer
snapshots before every run), web app `web/` (Vite, built by the `pages` workflow). `app/` is the retired Express app.

## Automatic runs (GitHub Actions, free)
- `engine` workflow: cron 06:30 and 13:30 UTC on weekdays (≈ 07:30 / 14:30 Berlin; GitHub may delay cron up to ~1 h),
  plus manual "Run workflow" (= forced refresh). Secrets: SUPABASE_URL, SUPABASE_ANON_KEY, ENGINE_SECRET.
- `pages` workflow: rebuilds and deploys the web app on every push touching `web/`. Variables: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY.
- Forced refresh by the user: GitHub → Actions → engine → Run workflow, or the "Request refresh" button in the app
  (writes to `refresh_requests`; served by the next run), or asking in the chat.

## Weekday morning (Perplexity automation, ~07:30 Europe/Berlin)
1. `bash engine/morning.sh` → hydrates from Supabase, scores open cards, updates learning state, generates today's cards, publishes.
2. Agent review (10 min max): overnight news/macro for the instruments in `data/today.json` (recommended + shadow). Write `data/analyst_notes.json`:
   ```json
   {"date":"<session_date>","market_context":"<2 sentences, with sources>",
    "cards":{"<card_id>":{"note":"...","veto":true|false}},
    "proposals":[{"symbol":"XYZ","name":"...","type":"stock|etf","side":"long|short","entry":0,"entry_type":"stop|limit",
                  "stop":0,"target":0,"thesis":["..."],"signals":["event:..."],"trigger_days":2,"horizon_days":10,"tier":"tail"}]}
   ```
   Veto only for hard reasons (earnings today, halted, scheduled binary event, data looks wrong). `proposals` is normally empty:
   only a specific, dated catalyst with a clearly asymmetric, fully specified setup qualifies (EVENT_SCOUT, tail tier, RR ≥ 3).
   Never add base cards or change levels by hand.
3. `python3 engine/run_daily.py --no-generate` to apply the notes and republish (ids dedupe; nothing is regenerated). This also
   marks pending refresh requests as done.
4. Check `gh run list -R jvigiles/trading-desk --limit 3` for failed overnight workflow runs; `curl -sI https://jvigiles.github.io/trading-desk/` should be 200.
5. Report in one short message: session date, scored outcomes (id → status, R), recommended count by tier, vetoes/proposals, blackout,
   undecided recommended cards. If nothing scored and nothing recommended, say so in one line.

## Monthly (first weekday)
`python3 engine/calibrate.py` then `python3 engine/run_daily.py --no-generate`; summarise changelog entries added to the state
(in-sample vs out-of-sample 2025+ per setup). Tier or size changes are manual decisions with a logged reason, never automatic.

## Deploying web changes
Edit `web/src`, `npm run build` locally to type-check, commit, `git push origin main`. The `pages` workflow deploys in ~1 min.
Never commit `engine/.env` or `web/.env`.

## Rules the agent must not break
- Do not lower thresholds, widen the universe, add setups or tail proposals because of a quiet period. Zero recommendations is a valid day.
- Do not present estimates as facts; quote expectancy with its sample size and the in-sample / out-of-sample split.
- Never place or suggest placing orders outside the card levels.
