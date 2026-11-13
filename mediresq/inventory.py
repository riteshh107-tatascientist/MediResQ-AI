"""Inventory CRUD with Pydantic validation, stock movements and audit logging."""
from __future__ import annotations
from datetime import date

import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator

from .auth import audit
from .db import Batch, Consumption, Facility, InventoryPolicy, Medicine, PurchaseOrder, Shipment, StockMovement


class MedicineIn(BaseModel):
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=60)
    unit: str = Field(min_length=1, max_length=20)
    unit_cost: float = Field(ge=0, le=1_000_000)
    criticality: int = Field(ge=1, le=3)
    cold_chain: bool = False
    shelf_life_days: int = Field(default=720, ge=30, le=3650)
    primary_supplier_id: int | None = None


class BatchIn(BaseModel):
    medicine_id: int
    facility_id: int
    batch_no: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_\-/.]+$")
    mfg_date: date
    expiry_date: date
    quantity: int = Field(ge=1, le=10_000_000)
    status: str = "Available"

    @model_validator(mode="after")
    def _dates(self):
        if self.expiry_date <= self.mfg_date:
            raise ValueError("Expiry date must be after manufacturing date")
        if self.status not in ("Available", "Quarantined"):
            raise ValueError("Invalid status")
        return self


def add_medicine(session, user: str, data: dict) -> Medicine:
    v = MedicineIn(**data)
    if session.query(Medicine).filter_by(code=v.code).first():
        raise ValueError("Medicine code already exists")
    m = Medicine(**v.model_dump(), base_daily_demand=0.0, season="none")
    session.add(m); session.flush()
    for f in session.query(Facility).all():
        session.add(InventoryPolicy(medicine_id=m.id, facility_id=f.id, min_stock=0, max_stock=1000))
    audit(session, user, "CREATE", "medicine", m.id, f"{m.code} {m.name}")
    session.commit()
    return m


def update_medicine(session, user: str, med_id: int, data: dict) -> Medicine:
    m = session.get(Medicine, med_id)
    if not m:
        raise ValueError("Medicine not found")
    merged = {**dict(code=m.code, name=m.name, category=m.category, unit=m.unit, unit_cost=m.unit_cost, criticality=m.criticality, cold_chain=m.cold_chain,
                     shelf_life_days=m.shelf_life_days, primary_supplier_id=m.primary_supplier_id), **data}
    v = MedicineIn(**merged)
    if v.code != m.code and session.query(Medicine).filter_by(code=v.code).first():
        raise ValueError("Medicine code already exists")
    before = f"{m.name}|cost {m.unit_cost}|crit {m.criticality}"
    for k, val in v.model_dump().items():
        setattr(m, k, val)
    audit(session, user, "UPDATE", "medicine", m.id, f"{before} -> {m.name}|cost {m.unit_cost}|crit {m.criticality}")
    session.commit()
    return m


def delete_medicine(session, user: str, med_id: int) -> str:
    """Hard-delete when unreferenced; otherwise deactivate (preserves history & referential integrity)."""
    m = session.get(Medicine, med_id)
    if not m:
        raise ValueError("Medicine not found")
    refs = sum(session.query(t).filter_by(medicine_id=med_id).count() for t in (Batch, Consumption, PurchaseOrder, Shipment, StockMovement))
    if refs:
        m.active = False
        audit(session, user, "DEACTIVATE", "medicine", med_id, f"{m.code}: referenced by {refs} records")
        session.commit()
        return "deactivated (has history)"
    session.query(InventoryPolicy).filter_by(medicine_id=med_id).delete()
    audit(session, user, "DELETE", "medicine", med_id, m.code)
    session.delete(m); session.commit()
    return "deleted"


def add_batch(session, user: str, data: dict) -> Batch:
    v = BatchIn(**data)
    b = Batch(**v.model_dump(), supplier_id=session.get(Medicine, v.medicine_id).primary_supplier_id)
    session.add(b); session.flush()
    session.add(StockMovement(date=date.today(), medicine_id=v.medicine_id, facility_id=v.facility_id, batch_id=b.id, type="Receipt", quantity=v.quantity, reference=v.batch_no, user=user))
    audit(session, user, "CREATE", "batch", b.id, f"{v.batch_no} qty {v.quantity}")
    session.commit()
    return b


def adjust_batch(session, user: str, batch_id: int, delta: int, mtype: str = "Adjustment", reference: str = "") -> Batch:
    b = session.get(Batch, batch_id)
    if not b:
        raise ValueError("Batch not found")
    if b.quantity + delta < 0:
        raise ValueError("Adjustment would make stock negative")
    b.quantity += delta
    session.add(StockMovement(date=date.today(), medicine_id=b.medicine_id, facility_id=b.facility_id, batch_id=b.id, type=mtype, quantity=delta, reference=reference[:60], user=user))
    audit(session, user, "STOCK_" + mtype.upper().replace(" ", "_"), "batch", b.id, f"delta {delta}")
    session.commit()
    return b


def set_batch_status(session, user: str, batch_id: int, status: str):
    if status not in ("Available", "Quarantined"):
        raise ValueError("Invalid status")
    b = session.get(Batch, batch_id); b.status = status
    audit(session, user, "BATCH_STATUS", "batch", batch_id, status); session.commit()


def delete_batch(session, user: str, batch_id: int):
    b = session.get(Batch, batch_id)
    if not b:
        raise ValueError("Batch not found")
    session.query(StockMovement).filter_by(batch_id=batch_id).update({"batch_id": None})
    audit(session, user, "DELETE", "batch", batch_id, b.batch_no)
    session.delete(b); session.commit()


def set_policy(session, user: str, med_id: int, fac_id: int, min_stock: int, max_stock: int):
    if min_stock < 0 or max_stock < min_stock:
        raise ValueError("Require 0 <= min <= max")
    p = session.query(InventoryPolicy).filter_by(medicine_id=med_id, facility_id=fac_id).first()
    if p is None:
        p = InventoryPolicy(medicine_id=med_id, facility_id=fac_id, min_stock=min_stock, max_stock=max_stock); session.add(p)
    p.min_stock, p.max_stock = min_stock, max_stock
    audit(session, user, "POLICY", "inventory_policy", f"{med_id}/{fac_id}", f"min {min_stock} max {max_stock}")
    session.commit()


def stock_overview(ass: pd.DataFrame) -> pd.DataFrame:
    cols = ["medicine", "facility", "usable", "avg_daily", "days_of_inventory", "safety_stock", "reorder_point", "below_min", "overstock", "inventory_value", "risk_level"]
    return ass[cols]
