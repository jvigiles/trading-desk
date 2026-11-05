# Trading Desk – runbook

Paths: engine `engine/`, data `data/`, web app `app/` (built to `app/dist`, API on port 5000, deployed via deploy_website from `app/dist/public`).

## Weekday morning (automation, ~07:30 Europe/Berlin)
1. `bash engine/morning.sh` → scores open cards, updates `data/state.json`, writes `data/cards.json|today.json|metrics.json`, restarts the API if it is down.
2. Agent review (10 min max): check overnight news/macro for the instruments in `data/today.json` (recommended + shadow). Write `data/analyst_notes.json`:
   `{"date":"<session_date>","market_context":"<2 sentences>","cards":{"<card_id>":{"note":"...","veto":true|false}}}`
   Veto only for hard reasons (earnings today, halted, scheduled binary event, data looks wrong). Never add cards or change levels by hand.
3. `python3 engine/run_daily.py --no-generate` to apply the notes (ids dedupe; nothing is regenerated).
4. Redeploy `app/dist/public` with deploy_website (same project_path, keeps the URL) only if the frontend changed; the API serves fresh JSON without a redeploy.
5. Report in one short message: session date, scored outcomes (id → status, R), recommended count, vetoes, blackout. If nothing scored and nothing recommended, say so in one line.

## Monthly (first weekday)
`python3 engine/calibrate.py` then `python3 engine/run_daily.py --no-generate`; summarise changelog entries added to `data/state.json`.

## Rules the agent must not break
- Do not lower thresholds, widen the universe, or add setups because of a quiet period.
- Do not present estimates as facts; quote expectancy with its sample size.
- Never place or suggest placing orders outside the card levels.
