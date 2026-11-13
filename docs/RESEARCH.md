# Research Foundation, Assumptions & Differentiation

## Source list (starting references from the project brief)
| Source | Used for |
|---|---|
| SAP Integrated Business Planning — features (sap.com/products/scm/integrated-business-planning/features.html) | Vocabulary of demand / inventory / response & supply planning, scenario simulation |
| SAP Help Portal — SAP IBP (help.sap.com/docs/sap_integrated_business_planning) | Concept alignment only |
| WHO — Medicines supply (who.int … medicines-supply) | Context: availability and supply of essential medicines |
| NHSRC India — *Assessment of IT-enabled Supply Chain Management of Medicines* (PDF, 2025) | Context: IT-enabled medicine supply chain management in India |

**Transparency:** this build environment had no reliable access to read these documents in full. They are cited as the *starting references named in the brief*; no statistic, quotation or finding from them is reproduced here, and none should be attributed to them on the basis of this repository. Before presenting, read them and add page-level citations. The methods below are standard, textbook inventory and forecasting techniques and are described as such.

## Domain concepts implemented
- **Safety stock / reorder point:** `ROP = lead-time demand + z·σ_d·√L`, z = 1.28/1.65/2.05 for routine/important/life-saving items. σ_d is the forecast RMSE from the hold-out.
- **Inventory position:** on-hand usable + on-order; **days of inventory** = usable / average daily demand.
- **FEFO:** issue the earliest-expiring, non-expired, non-quarantined batch first; wastage risk = stock that forecast consumption cannot use before expiry.
- **Forecasting:** moving average, seasonal naive, Holt-Winters, Random Forest, Gradient Boosting with chronological hold-out; WAPE chosen because it is stable under zero-demand days.
- **Supplier reliability:** on-time rate, fill rate, delay severity, lead-time variability → transparent score.
- **Multi-location optimisation:** lateral transshipment as a mixed-integer programme (OR-Tools/SCIP): transport + fixed trip + penalised unmet demand, with reserve, shelf-life, capacity, cold-chain and timing constraints.
- **What-if simulation:** perturb a copy of the network state; compare baseline, disrupted and recovered.

## Assumptions (all synthetic / illustrative)
Demand is generated from Poisson noise with weekly and annual seasonality, rare surges and data-entry outliers; ~0.3% of days are missing. Supplier delays follow on-time probability + exponential delay. Unit costs, transport rates (₹0.015/unit-km, ×1.8 cold chain), ₹600 trip cost, 15% expedite premium are assumptions. Facility names, locations and suppliers are fictional.

## Limitations
Single-echelon demand forecasting per hospital; no price/budget constraints; no lot-size or vehicle-routing detail; no expiry-aware ordering; stockout probability not calibrated; real data would need cleaning, unit normalisation and consent/governance.

## Differentiation
Most student projects stop at a dashboard or a forecast. MediResQ connects **forecast → batch-aware risk → disruption → optimiser → human approval → audit** in one explainable workflow, keeps heuristics and probabilities clearly separate, and labels every simulated number.
