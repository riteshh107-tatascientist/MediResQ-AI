"""Auto-generate docs that must reflect real data: DATA_DICTIONARY.md, MODEL_EVALUATION.md, TEST_REPORT.md.
Usage: python scripts/make_docs.py   (run after setup_demo.py and `pytest --junitxml=data/junit.xml`)"""
import sys, xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402
from mediresq import db, forecasting as F  # noqa: E402

DESC = {"facilities": "Warehouses and hospitals (synthetic names; coordinates are city-level approximations).", "medicines": "Essential-medicine master data (synthetic costs and demand parameters).",
        "suppliers": "Synthetic supplier master.", "inventory_policy": "Editable min/max stock per medicine x facility.", "batches": "Batch-level stock with manufacturing/expiry dates and status.",
        "consumption": "Historical daily consumption per medicine x hospital (synthetic).", "purchase_orders": "Purchase orders incl. promised vs actual delivery.", "shipments": "Shipments (supplier->facility, facility->facility), delay days, status.",
        "stock_movements": "Receipts, issues, transfers, adjustments, write-offs.", "disruption_events": "Disruption events - all labelled simulated.", "forecasts": "Stored 30-day forecasts with empirical 10-90% range.",
        "model_metrics": "Hold-out MAE/RMSE/WAPE per model and series.", "alerts": "Generated alerts with reason, action and status.", "recommendations": "Recovery-plan actions with approval state.",
        "audit_log": "Append-only audit trail.", "users": "Users with PBKDF2-SHA256 password hashes and role.", "app_meta": "Dataset reference date and label."}
out = ["# Data Dictionary\n", "All data is **synthetic** and reproducible (`python scripts/setup_demo.py`, seed 42). No patient-identifiable data exists anywhere. Generated from the SQLAlchemy models.\n"]
for t in db.Base.metadata.sorted_tables:
    out.append(f"\n## `{t.name}`\n{DESC.get(t.name, '')}\n\n| Column | Type | Nullable | Key / constraint |\n|---|---|---|---|")
    for c in t.columns:
        k = "PK" if c.primary_key else ("FK -> " + list(c.foreign_keys)[0].target_fullname if c.foreign_keys else ("unique" if c.unique else ""))
        out.append(f"| {c.name} | {c.type} | {'yes' if c.nullable else 'no'} | {k} |")
    cons = [str(x.sqltext) for x in t.constraints if x.__class__.__name__ == "CheckConstraint"]
    if cons:
        out.append("\nCheck constraints: " + "; ".join(f"`{c}`" for c in cons))
(ROOT / "docs" / "DATA_DICTIONARY.md").write_text("\n".join(out) + "\n", encoding="utf-8")

with db.session_scope() as s:
    mt = F.metric_table(s)
g = F.model_summary(mt)
md = ["# Model Evaluation\n\nNumbers below are **read from the stored hold-out backtests** of the shipped demo database (synthetic data). Nothing is hand-entered.\n",
      "\n## Protocol\n- Series: 22 medicines x 5 hospitals = 110 daily-demand series; warehouse demand = sum of child hospitals.\n- Cleaning: full daily index; missing days -> same-weekday median of +-4 weeks; true zeros preserved; outliers winsorised at median + 6 MAD (robust).\n- **Chronological split**: train on all but the last 28 days; forecast the 28-day hold-out multi-step (recursive for ML models); no shuffling, no look-ahead.\n- Models: Moving Average (7 d), Seasonal Naive (weekly), Holt-Winters additive (period 7), Random Forest, Gradient Boosting (lag / rolling / weekday / annual-seasonality features).\n- Selection: lowest WAPE per series (RMSE tie-break; simpler baselines win ties). The selected model is refit on all data and forecasts 30 days.\n- Uncertainty: empirical 10th/90th percentile of the selected model's hold-out residuals (not a calibrated predictive interval).\n",
      "\n## Aggregate comparison (mean over 110 series; series_won = times selected)\n\n", g.to_markdown(index=False, floatfmt=".3f")]
best_base = g[g.model.isin(["Moving Average", "Seasonal Naive"])].WAPE.min(); chosen = mt[mt.selected].WAPE.mean()
md.append(f"\n\nBest single baseline mean WAPE: **{best_base:.1%}**. Mean WAPE of the per-series selected model: **{chosen:.1%}**. Selection is made on the same hold-out, so the latter is optimistic; rolling-origin evaluation is the natural next step.")
md.append("\n\n## Limitations\n- Synthetic Poisson-based demand has a known generating process; real demand is noisier and may favour other models.\n- One 28-day hold-out per series; no rolling-origin cross-validation.\n- The stockout probability is a normal approximation and is **not** empirically calibrated; risk scores are heuristics.\n- Do not quote these metrics as real-world accuracy.\n")
(ROOT / "docs" / "MODEL_EVALUATION.md").write_text("".join(md), encoding="utf-8")

jx = ROOT / "data" / "junit.xml"
if jx.exists():
    root = ET.parse(jx).getroot(); suite = root if root.tag == "testsuite" else root.find("testsuite")
    EXP = {"dataset_reproducible": "Same seed gives identical data; validation finds no orphans; 8 facilities, 7 suppliers, 15-25 medicines", "referential_integrity": "PRAGMA foreign_key_check empty; no negative quantities",
           "inventory_crud": "Create/update/delete medicine; duplicate code and negative cost rejected; referenced medicine is deactivated, not deleted", "batch_validation": "Expiry<=mfg rejected; adjustments logged as movements; negative stock refused",
           "metrics_exact": "MAE=2, RMSE=2, WAPE=0.2 on a hand-computed example; all-zero actuals handled", "clean_series": "Missing day imputed, zeros kept, outlier capped", "backtest_is_chronological": "Moving-average prediction equals mean of last 7 TRAIN days; seasonal naive exact on periodic series",
           "all_models_produce": "All 5 models return 30 non-negative values", "forecasts_persisted": "30-day forecasts for 176 series; metrics stored per series and model", "projection_math": "Stockout day, unmet units and fulfilment match hand calculation; inbound timing respected",
           "projection_expiry": "Units that cannot be consumed before expiry are counted as wastage", "demo_scenario_detected": "Ceftriaxone @ Hospital A is Critical with stockout <= 5 days and a stated reason", "expired_and_quarantined": "Expired/quarantined units never counted as usable",
           "expiry_buckets": "Bucket boundaries correct; FEFO order ascending and excludes expired", "supplier_stats": "7 suppliers, reliability 0-100, rates in [0,1], active delay on S2", "optimizer_demo_plan": "Feasible transfers to Hospital A before stockout; batches unexpired; capacity and need respected",
           "optimizer_respects_cold_chain": "Cold-chain medicines only between cold-capable facilities", "optimizer_infeasibility": "With all sources blocked: zero transfers and a written explanation per case", "optimizer_higher_cost": "Doubling transport cost does not reduce plan cost",
           "simulator_three_scenarios": "Disrupted <= baseline fulfilment; recovered >= disrupted; database untouched", "simulator_noop": "No perturbation => disrupted equals baseline", "shipment_delay_shifts": "Supplier delay shifts affected inbound arrivals by exactly N days",
           "plan_requires_human": "Plans start Pending; viewer denied; reject needs comment; approve/reject/modify audited; double decision refused", "dashboard_kpis_match": "KPI counts and inventory value equal independent DB recomputation", "alerts_have_reason": "Every alert has reason + action; all 7 alert types present",
           "policy_simulation": "Both policies simulated; fill rates within [0,1]", "password_hashing": "Salted PBKDF2 hash; wrong password rejected; demo login works; policy enforced", "role_permissions": "Role matrix enforced", "csv_upload": "Valid file accepted; bad columns/codes/negatives/formula-injection/oversize rejected",
           "assistant_answers": "Answers match database values; unknown question returns help", "page_renders_admin": "Page renders with no exception", "viewer_role": "Restricted role renders without exception", "login_gate": "Anonymous user sees sign-in"}
    rows, p, f = [], 0, 0
    for tc in suite.iter("testcase"):
        ok = tc.find("failure") is None and tc.find("error") is None; p += ok; f += (not ok)
        name = tc.get("name"); exp = next((v for k, v in EXP.items() if k in name), "Behaves as specified")
        rows.append(f"| `{tc.get('classname').split('.')[-1]}::{name}` | {exp} | {'Executed successfully' if ok else 'FAILED'} | {'PASS' if ok else 'FAIL'} |")
    rep = [f"# Test Report\n\nGenerated {datetime.now():%Y-%m-%d %H:%M} by `pytest` (parsed from `data/junit.xml`).\n\n**Total: {p + f} | Passed: {p} | Failed: {f}** | Runtime: {suite.get('time')} s\n\n",
           "| Test case | Expected result | Actual result | Pass/Fail |\n|---|---|---|---|", *rows,
           "\n## Coverage map\nInventory CRUD, batch/expiry, forecasting, stockout, supplier analysis, shipment disruption, redistribution optimisation, scenario simulation, approval workflow, dashboard calculations, security and upload validation, assistant, and a Streamlit page-render smoke test for all 16 pages (admin role) plus viewer-role and login-gate checks.\n",
           "\n## Known limitations / what was NOT verified\n- **Browser verification (manual, headless Chromium, dark theme):** home, dashboard, optimizer and AI pages were loaded and screenshotted; card hover, card click navigation, one-click demo login, session persistence across pages and the header light-sweep were observed working. These browser checks are not part of the automated suite. Light theme and mobile layouts were not re-checked in a browser after the final CSS change.\n- **Gemini live call NOT verified:** the build sandbox has no access to Google's API, so the HTTP layer is tested with mocked responses (success, invalid key, quota, model fallback, no key). Please test with your own key.\n- Tests ran on Python 3.12 with current package versions; Python 3.10 compatibility is by construction (no 3.11+ syntax) but was not executed.\n- Tests use a reduced 150-day synthetic history and fast models; the shipped demo DB uses 365 days and all 5 models.\n- Forecast/policy results are on synthetic data and say nothing about real-world accuracy.\n- Transport costs, trip costs and expedite premiums are illustrative assumptions.\n- No load/performance or multi-user concurrency testing (SQLite, single-user demo).\n\n## Re-run locally\n```powershell\npython -m pytest -q\n```\n"]
    (ROOT / "docs" / "TEST_REPORT.md").write_text("\n".join(rep), encoding="utf-8")
print("docs generated")
