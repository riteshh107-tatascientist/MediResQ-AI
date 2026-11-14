# Test Report

Generated 2026-11-14 00:53 by `pytest` (parsed from `data/junit.xml`).

**Total: 59 | Passed: 59 | Failed: 0** | Runtime: 26.519 s


| Test case | Expected result | Actual result | Pass/Fail |
|---|---|---|---|
| `test_core::test_dataset_reproducible_and_valid` | Same seed gives identical data; validation finds no orphans; 8 facilities, 7 suppliers, 15-25 medicines | Executed successfully | PASS |
| `test_core::test_database_referential_integrity` | PRAGMA foreign_key_check empty; no negative quantities | Executed successfully | PASS |
| `test_core::test_inventory_crud` | Create/update/delete medicine; duplicate code and negative cost rejected; referenced medicine is deactivated, not deleted | Executed successfully | PASS |
| `test_core::test_batch_validation_and_adjustment` | Expiry<=mfg rejected; adjustments logged as movements; negative stock refused | Executed successfully | PASS |
| `test_core::test_metrics_exact` | MAE=2, RMSE=2, WAPE=0.2 on a hand-computed example; all-zero actuals handled | Executed successfully | PASS |
| `test_core::test_clean_series_missing_zero_outlier` | Missing day imputed, zeros kept, outlier capped | Executed successfully | PASS |
| `test_core::test_backtest_is_chronological_and_baselines_correct` | Moving-average prediction equals mean of last 7 TRAIN days; seasonal naive exact on periodic series | Executed successfully | PASS |
| `test_core::test_all_models_produce_nonnegative_forecasts` | All 5 models return 30 non-negative values | Executed successfully | PASS |
| `test_core::test_forecasts_persisted` | 30-day forecasts for 176 series; metrics stored per series and model | Executed successfully | PASS |
| `test_core::test_projection_math` | Stockout day, unmet units and fulfilment match hand calculation; inbound timing respected | Executed successfully | PASS |
| `test_core::test_projection_expiry_wastage` | Units that cannot be consumed before expiry are counted as wastage | Executed successfully | PASS |
| `test_core::test_demo_scenario_detected` | Ceftriaxone @ Hospital A is Critical with stockout <= 5 days and a stated reason | Executed successfully | PASS |
| `test_core::test_expired_and_quarantined_not_usable` | Expired/quarantined units never counted as usable | Executed successfully | PASS |
| `test_core::test_expiry_buckets_and_fefo` | Bucket boundaries correct; FEFO order ascending and excludes expired | Executed successfully | PASS |
| `test_core::test_supplier_stats` | 7 suppliers, reliability 0-100, rates in [0,1], active delay on S2 | Executed successfully | PASS |
| `test_core::test_optimizer_demo_plan` | Feasible transfers to Hospital A before stockout; batches unexpired; capacity and need respected | Executed successfully | PASS |
| `test_core::test_optimizer_respects_cold_chain` | Cold-chain medicines only between cold-capable facilities | Executed successfully | PASS |
| `test_core::test_optimizer_infeasibility_explained` | With all sources blocked: zero transfers and a written explanation per case | Executed successfully | PASS |
| `test_core::test_optimizer_higher_cost_never_cheaper` | Doubling transport cost does not reduce plan cost | Executed successfully | PASS |
| `test_core::test_simulator_three_scenarios_and_db_untouched` | Disrupted <= baseline fulfilment; recovered >= disrupted; database untouched | Executed successfully | PASS |
| `test_core::test_simulator_noop_equals_baseline` | No perturbation => disrupted equals baseline | Executed successfully | PASS |
| `test_core::test_shipment_delay_shifts_arrival` | Supplier delay shifts affected inbound arrivals by exactly N days | Executed successfully | PASS |
| `test_core::test_plan_requires_human_approval_and_workflow` | Plans start Pending; viewer denied; reject needs comment; approve/reject/modify audited; double decision refused | Executed successfully | PASS |
| `test_core::test_dashboard_kpis_match_database` | KPI counts and inventory value equal independent DB recomputation | Executed successfully | PASS |
| `test_core::test_alerts_have_reason_and_action` | Every alert has reason + action; all 7 alert types present | Executed successfully | PASS |
| `test_core::test_policy_simulation_runs` | Both policies simulated; fill rates within [0,1] | Executed successfully | PASS |
| `test_core::test_password_hashing_and_auth` | Salted PBKDF2 hash; wrong password rejected; demo login works; policy enforced | Executed successfully | PASS |
| `test_core::test_role_permissions` | Role matrix enforced | Executed successfully | PASS |
| `test_core::test_csv_upload_validation` | Valid file accepted; bad columns/codes/negatives/formula-injection/oversize rejected | Executed successfully | PASS |
| `test_core::test_assistant_answers_from_data` | Answers match database values; unknown question returns help | Executed successfully | PASS |
| `test_core::test_llm_context_is_grounded_and_safe` | Behaves as specified | Executed successfully | PASS |
| `test_core::test_gemini_success_fallback_and_errors` | Behaves as specified | Executed successfully | PASS |
| `test_core::test_demo_password_sync_fixes_login` | Behaves as specified | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[admin.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[alerts.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[analytics.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[approvals.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[assistant.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[batches.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[dashboard.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[forecasting.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[home.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[inventory.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[logistics.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[optimizer.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[planner.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[simulator.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[stockout.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_page_renders_admin[suppliers.py]` | Page renders with no exception | Executed successfully | PASS |
| `test_pages::test_viewer_role_is_restricted_but_renders[dashboard]` | Restricted role renders without exception | Executed successfully | PASS |
| `test_pages::test_viewer_role_is_restricted_but_renders[inventory]` | Restricted role renders without exception | Executed successfully | PASS |
| `test_pages::test_viewer_role_is_restricted_but_renders[approvals]` | Restricted role renders without exception | Executed successfully | PASS |
| `test_pages::test_viewer_role_is_restricted_but_renders[admin]` | Restricted role renders without exception | Executed successfully | PASS |
| `test_pages::test_login_gate_when_anonymous` | Anonymous user sees sign-in | Executed successfully | PASS |
| `test_pages::test_simulator_run_button_interaction` | Behaves as specified | Executed successfully | PASS |
| `test_pages::test_planner_generate_interaction` | Behaves as specified | Executed successfully | PASS |
| `test_pages::test_approval_interaction_and_viewer_blocked` | Behaves as specified | Executed successfully | PASS |
| `test_pages::test_optimizer_page_creates_pending_plan` | Behaves as specified | Executed successfully | PASS |
| `test_pages::test_one_click_demo_login_and_ai_page_fallback` | Behaves as specified | Executed successfully | PASS |

## Coverage map
Inventory CRUD, batch/expiry, forecasting, stockout, supplier analysis, shipment disruption, redistribution optimisation, scenario simulation, approval workflow, dashboard calculations, security and upload validation, assistant, and a Streamlit page-render smoke test for all 16 pages (admin role) plus viewer-role and login-gate checks.


## Known limitations / what was NOT verified
- **Browser verification (manual, headless Chromium, dark theme):** home, dashboard, optimizer and AI pages were loaded and screenshotted; card hover, card click navigation, one-click demo login, session persistence across pages and the header light-sweep were observed working. These browser checks are not part of the automated suite. Light theme and mobile layouts were not re-checked in a browser after the final CSS change.
- **Gemini live call NOT verified:** the build sandbox has no access to Google's API, so the HTTP layer is tested with mocked responses (success, invalid key, quota, model fallback, no key). Please test with your own key.
- Tests ran on Python 3.12 with current package versions; Python 3.10 compatibility is by construction (no 3.11+ syntax) but was not executed.
- Tests use a reduced 150-day synthetic history and fast models; the shipped demo DB uses 365 days and all 5 models.
- Forecast/policy results are on synthetic data and say nothing about real-world accuracy.
- Transport costs, trip costs and expedite premiums are illustrative assumptions.
- No load/performance or multi-user concurrency testing (SQLite, single-user demo).

## Re-run locally
```powershell
python -m pytest -q
```
