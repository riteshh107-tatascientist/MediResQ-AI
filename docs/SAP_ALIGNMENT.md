# SAP Alignment (conceptual only)

**MediResQ AI is an independent Python prototype. It has no SAP integration, certification, partnership or endorsement.** The table maps its capabilities to SAP concepts for discussion only.

| SAP concept | MediResQ counterpart | Status |
|---|---|---|
| SAP IBP — Demand planning | Per-series forecasting with model comparison and error metrics | Conceptually similar; own implementation |
| SAP IBP — Inventory optimisation (safety stock, ROP) | Safety stock / ROP from forecast error, lead time, criticality-based service level | Conceptually similar |
| SAP IBP — Response & supply planning | Recovery planner + OR-Tools redistribution + procurement proposals | Conceptually similar; far simpler |
| Supply-chain visibility / control tower | Dashboard, alert centre, shipment monitoring | Prototype |
| Scenario simulation / what-if | What-if simulator (baseline / disrupted / recovered) | Prototype |
| SAP BTP (future integration layer) | `SQLAlchemy` DB abstraction + domain modules could be exposed as REST services on BTP | **Not implemented** |
| SAP S/4HANA (transactional system) | Approved recommendations could create purchase requisitions / stock transport orders | **Not implemented; roadmap** |

Roadmap (requires authorised SAP access): OData/CDS read of stock, batches and POs → map to the `batches`/`purchase_orders` schema; write-back of approved actions as purchase requisitions/STOs via BTP; compare MediResQ forecasts with IBP statistical forecasts.
