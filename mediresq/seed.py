"""Database seeding: synthetic dataset -> DB, demo accounts, forecasts, alerts, demo recovery plan."""
from __future__ import annotations
from datetime import date

from sqlalchemy import insert

from . import config, datagen
from .auth import create_user, audit
from .db import (Batch, set_meta, Consumption, DisruptionEvent, Facility, InventoryPolicy, Medicine, PurchaseOrder, Shipment, StockMovement,
                 Supplier, drop_all, init_db, session_scope)

DEMO_USERS = [("admin_demo", "Demo Administrator", "Administrator"), ("manager_demo", "Demo Supply Chain Manager", "Supply Chain Manager"),
              ("warehouse_demo", "Demo Warehouse Manager", "Warehouse Manager"), ("viewer_demo", "Demo Viewer", "Viewer")]
ORDER = [(Facility, "facilities"), (Supplier, "suppliers"), (Medicine, "medicines"), (InventoryPolicy, "inventory_policy"), (Batch, "batches"),
         (Consumption, "consumption"), (PurchaseOrder, "purchase_orders"), (Shipment, "shipments"), (StockMovement, "stock_movements"),
         (DisruptionEvent, "disruption_events")]


def seed(asof: date | None = None, run_forecasts: bool = True, fast: bool = False, write_csv: bool = True, progress=None, history_days=None) -> dict:
    """Rebuild the database from scratch. fast=True limits forecasting to the three cheap models (used in tests)."""
    from . import forecasting, alerts, planner
    asof = asof or config.as_of_date()
    T = datagen.generate(asof, history_days=history_days)
    issues = datagen.validate_tables(T)
    if issues:
        raise RuntimeError(f"Synthetic data validation failed: {issues}")
    if write_csv:
        datagen.write_csvs(T)
    drop_all(); init_db()
    with session_scope() as s:
        for model, key in ORDER:
            rows = T[key]
            for i in range(0, len(rows), 5000):
                s.execute(insert(model), rows[i:i + 5000])
        for u, n, r in DEMO_USERS:
            create_user(s, u, n, config.DEMO_PASSWORD, r)
        set_meta(s, "asof", asof.isoformat()); set_meta(s, "dataset", "SYNTHETIC")
        audit(s, "system", "SEED", "database", "", f"Synthetic dataset generated as of {asof}")
    info = {k: len(v) for k, v in T.items() if not k.startswith("_")}
    if run_forecasts:
        with session_scope() as s:
            models = ["Moving Average", "Seasonal Naive", "Exponential Smoothing"] if fast else None
            forecasting.run_all(s, asof, models=models, progress=progress)
        with session_scope() as s:
            alerts.refresh_alerts(s, asof)
            planner.generate_plan(s, asof, created_by="system (demo seed)")
    return info
