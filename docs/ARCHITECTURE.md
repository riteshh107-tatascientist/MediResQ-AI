# Architecture

```
Streamlit UI (app.py + views/*)  ──►  mediresq/ui.py (design system, auth gate, cached context)
        │
        ▼
  Domain modules (pure Python, unit-tested)
  ├─ datagen / seed      synthetic data → CSV → DB (+ validation, demo users)
  ├─ forecasting         clean → 5 models → hold-out metrics → stored forecasts
  ├─ engine              Snapshot (in-memory network state) · FEFO projection · stockout risk
  ├─ expiry / inventory  batch intelligence · CRUD with Pydantic validation
  ├─ suppliers           reliability stats
  ├─ optimizer           OR-Tools MIP (SCIP) redistribution
  ├─ planner             forecasts + risk + supplier + shipments + optimizer → actions
  ├─ simulator           what-if on Snapshot copies (never mutates the DB)
  ├─ policy_sim          Monte-Carlo static vs intelligent policy
  ├─ alerts / approvals / auth / uploads / analytics / assistant
        │
        ▼
  SQLAlchemy 2.0 ORM ──► SQLite (default) · PostgreSQL via MEDIRESQ_DB_URL
```
**Key design decisions**
- *Snapshot pattern*: one function loads the network (batches, forecasts, inbound shipments, policies, supplier stats) into plain dataclasses. Risk, optimizer, planner and simulator all operate on copies → what-if analysis cannot corrupt data and is easy to test.
- *Planning window*: unmet demand is evaluated over 14 days assuming only already-scheduled inbound stock (no hypothetical future reorders), so "unmet" means "needs action now".
- *Human-in-the-loop*: planner writes `Pending` recommendations; only roles with `approve` can decide; decisions are audited; the system never moves stock or places orders.
- *Security*: PBKDF2-SHA256 (200k iterations, per-user salt); role matrix in `auth.PERMS`; Pydantic validation; DB check/FK constraints (SQLite `PRAGMA foreign_keys=ON`); CSV upload size/column/type/formula-injection checks; secrets via `.env`.
- *Offline-first UI*: illustrations are local SVGs embedded as data URIs; only the optional Google Fonts import needs internet (system-font fallback).

## Data flow for the demo
`consumption` → `forecasting.run_all` → `forecasts`/`model_metrics` → `engine.build_snapshot` → `assess_all` → `alerts.refresh_alerts` & `planner.generate_plan` → `recommendations` (Pending) → `approvals.decide` → `audit_log`.
