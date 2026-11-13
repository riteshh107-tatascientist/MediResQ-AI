# Demo Workflow (≈5 minutes)
Login as `manager_demo` / `Demo@2026!` (synthetic demo account).

1. **Home** — 20 s: problem → solution → workflow. Click *Enter Command Center*.
2. **Executive Dashboard** — 40 s: all KPIs are database-computed. Point at critical alerts, predicted stockouts, near-expiry value, resilience gauge (heuristic).
3. **Stockout Early Warning** — 45 s: filter *Critical*; open **Ceftriaxone 1g @ Hospital A**: ~3 days of stock, lead time long, supplier shipment delayed 7 days. Read the *Why*. Note: risk score = heuristic; probability = model-based, not calibrated.
4. **Logistics** — 20 s: the delayed shipment and the supplier-delay event (labelled SIMULATED).
5. **Redistribution Optimizer** — 60 s: OR-Tools transfers from surplus hospitals to Hospital A: FEFO batches, arrival before stockout, cost. Change *Transport cost multiplier* or block a facility to show re-optimisation and the infeasibility explanations.
6. **AI Recovery Planner** — 30 s: prioritised list (transfers + procurement from the most reliable alternate supplier + expedite). Nothing executes.
7. **Approvals & Audit** — 45 s: approve one, modify one, reject one (comment required); show the audit log.
8. **What-If Simulator** — 45 s: *Demo: 7-day supplier delay* or *Perfect storm* → Baseline / Disrupted / Recovered comparison.
9. **Advanced Analytics** — 30 s: forecast metrics, then run the static-vs-intelligent policy simulation (labelled simulated; note extra orders/expedite cost).
10. **Assistant** — 20 s: "Which facility is at greatest risk?" — answer comes from live queries.

Reset between runs: Admin & Data → Demo control → Re-seed.
