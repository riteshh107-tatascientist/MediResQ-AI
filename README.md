# MediResQ AI
**Predict. Protect. Prevent Shortages.** — AI-powered essential medicine supply-chain resilience platform
SAP HACKFEST 2026 | WEST & CENTRAL REGION · **TIT BHOPAL | CSE (DATA SCIENCE)** · Developer: Ritesh Kumar Singh

> Independent Python prototype. **Not** affiliated with, endorsed by, or integrated with SAP. All data is **synthetic**. This is an inventory decision-support tool, **not** a clinical system; it stores no patient data.

## What it does
Forecasts medicine demand → projects stock day-by-day with FEFO batch logic → detects stockout / expiry / supplier / shipment risk (with reasons) → **optimises redistribution with OR-Tools** → builds a prioritised recovery plan → **a human approves, rejects or modifies** → everything is audited. A what-if simulator and a controlled policy simulation (static vs intelligent) are included, clearly labelled as simulated.

| Module | Page |
|---|---|
| Homepage (hero, workflow, problem/solution) | Home |
| KPIs, charts, resilience indicator | Executive Dashboard |
| Medicine CRUD, min/max policy, movements | Medicine Inventory |
| Batches, FEFO, 30/60/90-d expiry, wastage risk, safe transfers | Batch & Expiry |
| 5 models, chronological backtest, MAE/RMSE/WAPE, 7/14/30-day forecast | Demand Forecasting |
| Days-of-inventory, ROP, shortage date, risk with reasons | Stockout Early Warning |
| Lead time, delay frequency, fulfilment, reliability | Supplier Intelligence |
| Shipments, delays, simulated disruption injection | Logistics & Disruptions |
| OR-Tools MIP, constraints, infeasibility explanations | Redistribution Optimizer |
| Combined recovery plan | AI Recovery Planner |
| Baseline vs disrupted vs recovered | What-If Simulator |
| Alerts with reason/action/status | Alert Center |
| Approve/reject/modify, comments, audit | Approvals & Audit |
| Accuracy, turnover, wastage, policy simulation | Advanced Analytics |
| Data-grounded Q&A (no LLM) | Intelligence Assistant |
| Users, safe CSV upload, data quality, demo control | Admin & Data |

## Run on Windows (VS Code + PowerShell)
Requires Python 3.10+ (python.org, tick "Add to PATH"). Open the `MediResQ-AI` folder in VS Code → Terminal → PowerShell:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```
The ZIP already contains a ready demo database (`data/mediresq.db`), so the app opens instantly. If the database is missing it is generated automatically on first launch (~1–3 min). To rebuild manually: `python scripts/setup_demo.py --asof 2026-11-13`.

**If PowerShell blocks `Activate.ps1`** ("running scripts is disabled"): allow scripts for *this terminal session only* — no permanent security change:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.venv\Scripts\Activate.ps1
```
(Alternative without changing policy: `.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.venv\Scripts\python.exe -m streamlit run app.py`.)

### Demo logins (local, synthetic, demo only)
`admin_demo`, `manager_demo`, `warehouse_demo`, `viewer_demo` — password `Demo@2026!` (override with `MEDIRESQ_DEMO_PASSWORD` in `.env` before seeding). Roles: Administrator, Supply Chain Manager, Warehouse Manager, Viewer.

### Tests
```powershell
python -m pytest -q
```
See `docs/TEST_REPORT.md` (55 tests, results from an actual run) — including what was *not* verified.

## The demo scenario (built into the data)
A supplier delays shipments by **7 days**. *Hospital A* has ~3 days of Ceftriaxone left and is projected to stock out; other hospitals hold surplus and the warehouse is lean. The optimizer proposes the cheapest feasible, expiry-safe transfers (arrival before stockout), the planner adds procurement/expedite actions, and a manager approves. Walkthrough: `docs/DEMO_WORKFLOW.md`.

## Real photos (optional)
The homepage uses locally generated SVG illustrations (work offline, no hotlinking). To use real photography, put `hero.jpg`, `feature_inventory.jpg`, `feature_forecast.jpg`, `feature_logistics.jpg`, `feature_recovery.jpg` (png/webp also work) into `assets/images/` — they are picked up automatically. Use only images you have the licence for, and nothing that shows identifiable patients or implies a partner facility.

## Project layout
`app.py` (navigation) · `views/` (16 pages) · `mediresq/` (engine, forecasting, optimizer, planner, simulator, policy_sim, alerts, approvals, auth, ui, …) · `scripts/` · `tests/` · `docs/` · `data/` (CSV + SQLite) · `assets/images/`.
Database access is via SQLAlchemy — set `MEDIRESQ_DB_URL` for PostgreSQL later. FastAPI was deliberately not added: the Streamlit app calls the Python modules directly; a REST layer is listed as future work.

## Honesty notes
- Synthetic data; no real hospital partnerships, deployments or results are claimed.
- *Risk score* = transparent heuristic. *Stockout probability* = model-based normal approximation, **not empirically calibrated**.
- Simulation outputs are labelled SIMULATED and are not real outcomes. Cost parameters are illustrative assumptions.
- Troubleshooting: if fonts look different offline, the app falls back to system fonts; everything else works without internet.
