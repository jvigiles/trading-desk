# Trading Desk

Personal decision-support app for a small Interactive Brokers account: a Python engine generates a short list of
rule-based trade cards (or none), tracks every card's outcome, learns from the results, and a static web app shows the
cards with an IBKR execution walkthrough, a glossary and a performance / decision review.

- `engine/` — Python. Scores open cards, updates the learning state, generates today's cards, publishes JSON snapshots to Supabase.
  Runs on GitHub Actions twice per weekday (`.github/workflows/engine.yml`) and on demand via "Run workflow".
- `web/` — Vite + React static app, deployed to GitHub Pages (`.github/workflows/pages.yml`). Reads snapshots from Supabase; login required.
- Storage: Supabase (free tier) — tables `snapshots`, `executions`, `refresh_requests`; writes from the engine go through
  secret-checked RPCs, the browser only has an anon key plus the user's login.

No market data, personal decisions or secrets are stored in this repository. Configuration lives in GitHub Secrets /
Variables and in `engine/.env` / `web/.env` locally (both git-ignored).

This is not investment advice. Every order is placed manually by the account owner.
