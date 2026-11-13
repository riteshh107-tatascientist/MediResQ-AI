# Design Thinking Documentation

> Everything about users and pains below is a **hypothesis** until validated. No real interviews were conducted for this prototype.

## 1. Empathy
See `EMPATHY_MAP.md`.

## 2. Stakeholder analysis
| Stakeholder | Interest | Influence | Needs from the system |
|---|---|---|---|
| Hospital pharmacist / store manager | Never run out; avoid expiry | High (daily) | Early warnings, batch/FEFO guidance |
| Supply-chain / procurement manager | Right stock, right cost | High | Recovery plan, supplier insight, approval workflow |
| Warehouse manager | Accurate stock, efficient dispatch | Medium | Transfer lists, expiry exposure |
| Clinicians | Medicines available at point of care | Medium | Fewer interruptions (indirect) |
| Hospital administration / health department | Cost, compliance, resilience | High | KPIs, audit trail |
| Suppliers / carriers | Predictable orders | Medium | Clear, timely demand signals |
| IT / data governance | Security, integration | Medium | RBAC, audit, PostgreSQL/SAP-ready design |
| Patients | Continuity of treatment | Indirect | Not users; no patient data is processed |

## 3. User pain points (hypotheses)
1. Shortages discovered late. 2. Surplus/near-expiry stock invisible across sites. 3. Supplier delays are tracked informally. 4. Manual, undocumented transfers. 5. Procurement decisions lack explanation. 6. Disruptions are hard to simulate before they happen.

## 4. Problem validation approach (proposed)
Interview 8–12 pharmacists/store managers/procurement staff (2–3 institutions): current stockout frequency, how they learn of delays, transfer practice, data availability. Observe a stock-check session. Review 3 months of anonymised stock/consumption extracts (no patient data). Success criteria to confirm: shortage discovery lead time, % lines with <7 days cover, wastage value, manual transfer time.

## 5. Problem statement
Healthcare supply teams lack an integrated, explainable early-warning and recovery capability across forecasting, batch expiry, supplier reliability and inter-facility stock, so shortages and expiry waste are detected too late and fixed with costly ad-hoc actions.

## 6. How Might We
*How might we predict medicine shortages early, explain them, and recommend the cheapest safe recovery — while keeping a human in control?*

## 7. Ideation & solution selection
Ideas: static dashboard · alert-only system · forecasting-only tool · ERP plug-in · **forecast + risk + optimiser + approval platform** · crowd-sourced stock sharing. Scored on feasibility (hackathon), impact, explainability, demo-ability → the integrated platform was selected; ERP plug-in kept as roadmap.

## 8. Prototype workflow
Data → forecast → risk → disruption → optimise → recommend → approve → audit (see `DEMO_WORKFLOW.md`).

## 9. Testing strategy
Automated: 55 pytest tests (see `TEST_REPORT.md`). Proposed user testing: task-based sessions (find the critical item, explain why, approve a transfer) with 5 target users; measure task time, errors, System Usability Scale; iterate on explanations and thresholds.

## 10. Business impact (hypotheses to be measured, not claims)
Fewer stockout days for critical medicines, lower expiry wastage, fewer emergency purchases, faster decisions with an audit trail. Quantification requires real data; the in-app simulations are illustrative only.
