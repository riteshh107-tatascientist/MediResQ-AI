"""SQLAlchemy models + session helpers. Portable to PostgreSQL by changing MEDIRESQ_DB_URL."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer,
                        String, Text, UniqueConstraint, create_engine, event)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


class Facility(Base):
    __tablename__ = "facilities"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(20))  # Warehouse | Hospital
    city: Mapped[str] = mapped_column(String(60))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    priority: Mapped[int] = mapped_column(Integer, default=2)  # 1 low .. 3 high (hospital criticality)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    transfer_capacity: Mapped[int] = mapped_column(Integer, default=2000)  # max outbound units per plan
    has_cold_storage: Mapped[bool] = mapped_column(Boolean, default=True)
    size_factor: Mapped[float] = mapped_column(Float, default=1.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("type in ('Warehouse','Hospital')"), CheckConstraint("priority between 1 and 3"))


class Medicine(Base):
    __tablename__ = "medicines"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(60))
    unit: Mapped[str] = mapped_column(String(20))
    unit_cost: Mapped[float] = mapped_column(Float)  # INR, synthetic
    criticality: Mapped[int] = mapped_column(Integer, default=2)  # 1 routine .. 3 life-saving
    cold_chain: Mapped[bool] = mapped_column(Boolean, default=False)
    shelf_life_days: Mapped[int] = mapped_column(Integer, default=720)
    base_daily_demand: Mapped[float] = mapped_column(Float, default=10.0)  # synthetic generator parameter
    season: Mapped[str] = mapped_column(String(20), default="none")
    primary_supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("unit_cost >= 0"), CheckConstraint("criticality between 1 and 3"))


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(60))
    lat: Mapped[float] = mapped_column(Float, default=23.0)
    lon: Mapped[float] = mapped_column(Float, default=77.0)
    promised_lead_days: Mapped[int] = mapped_column(Integer, default=7)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class InventoryPolicy(Base):
    __tablename__ = "inventory_policy"
    id: Mapped[int] = mapped_column(primary_key=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    min_stock: Mapped[int] = mapped_column(Integer)
    max_stock: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("medicine_id", "facility_id"), CheckConstraint("min_stock >= 0"),
                      CheckConstraint("max_stock >= min_stock"))


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40))
    mfg_date: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="Available")  # Available | Quarantined
    __table_args__ = (CheckConstraint("quantity >= 0"), CheckConstraint("expiry_date > mfg_date"),
                      CheckConstraint("status in ('Available','Quarantined')"),
                      Index("ix_batch_med_fac", "medicine_id", "facility_id"))


class Consumption(Base):
    __tablename__ = "consumption"
    id: Mapped[int] = mapped_column(primary_key=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("medicine_id", "facility_id", "date"), CheckConstraint("quantity >= 0"),
                      Index("ix_cons_series", "medicine_id", "facility_id", "date"))


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    po_no: Mapped[str] = mapped_column(String(30), unique=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    order_date: Mapped[date] = mapped_column(Date)
    promised_date: Mapped[date] = mapped_column(Date)
    actual_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    delivered_qty: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="Open")  # Open | Delivered | Partial | Cancelled


class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[int] = mapped_column(primary_key=True)
    ship_no: Mapped[str] = mapped_column(String(30), unique=True)
    po_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    origin_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    origin_name: Mapped[str] = mapped_column(String(120))
    destination_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    dispatch_date: Mapped[date] = mapped_column(Date)
    expected_arrival: Mapped[date] = mapped_column(Date)
    actual_arrival: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="In Transit")  # In Transit | Delivered | Delayed | Cancelled
    delay_days: Mapped[int] = mapped_column(Integer, default=0)  # known/expected delay (days)
    transport_mode: Mapped[str] = mapped_column(String(20), default="Road")
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("batches.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(20))  # Receipt | Issue | Transfer In | Transfer Out | Adjustment | Write-off
    quantity: Mapped[int] = mapped_column(Integer)  # signed
    reference: Mapped[str] = mapped_column(String(60), default="")
    user: Mapped[str] = mapped_column(String(60), default="system")


class DisruptionEvent(Base):
    __tablename__ = "disruption_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    severity: Mapped[str] = mapped_column(String(10), default="Medium")
    detected_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)


class ForecastResult(Base):
    __tablename__ = "forecasts"
    id: Mapped[int] = mapped_column(primary_key=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    date: Mapped[date] = mapped_column(Date)
    yhat: Mapped[float] = mapped_column(Float)
    lo: Mapped[float] = mapped_column(Float)
    hi: Mapped[float] = mapped_column(Float)
    model: Mapped[str] = mapped_column(String(40))
    __table_args__ = (Index("ix_fc_series", "medicine_id", "facility_id"),)


class ModelMetric(Base):
    __tablename__ = "model_metrics"
    id: Mapped[int] = mapped_column(primary_key=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    model: Mapped[str] = mapped_column(String(40))
    mae: Mapped[float] = mapped_column(Float)
    rmse: Mapped[float] = mapped_column(Float)
    wape: Mapped[float] = mapped_column(Float)
    test_days: Mapped[int] = mapped_column(Integer)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True)
    type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10))  # Critical | High | Medium | Low
    medicine_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medicines.id"), nullable=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="Open")  # Open | Acknowledged | Resolved | Auto-Closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(30))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(30))  # Redistribution | Procurement | Expedite | Monitor
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"))
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    source_name: Mapped[str] = mapped_column(String(120), default="")
    dest_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    est_cost: Mapped[float] = mapped_column(Float, default=0.0)
    eta_days: Mapped[float] = mapped_column(Float, default=0.0)
    batches: Mapped[str] = mapped_column(Text, default="")
    reasoning: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="Pending")  # Pending | Approved | Rejected | Modified
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    decided_by: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    user: Mapped[str] = mapped_column(String(60))
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(40), default="")
    details: Mapped[str] = mapped_column(Text, default="")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True)
    full_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    __table_args__ = (CheckConstraint("role in ('Administrator','Supply Chain Manager','Warehouse Manager','Viewer')"),)


class Meta(Base):
    __tablename__ = "app_meta"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


_engine = None
_Session = None


def get_engine(url: str | None = None):
    global _engine, _Session
    url = url or (str(_engine.url.render_as_string(hide_password=False)) if _engine is not None else config.DB_URL)
    if _engine is None or _engine.url.render_as_string(hide_password=False) != url:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, future=True)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _fk(dbapi_con, _):  # enforce referential integrity in SQLite
                dbapi_con.execute("PRAGMA foreign_keys=ON")
        _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def set_engine(url: str):
    """Point the app at another database (used by tests)."""
    global _engine
    _engine = None
    return get_engine(url)


def init_db():
    Base.metadata.create_all(get_engine())


def drop_all():
    Base.metadata.drop_all(get_engine())


@contextmanager
def session_scope():
    get_engine()
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_asof(session) -> date:
    """Reference date of the loaded (synthetic) dataset - stored at seed time so a bundled DB stays self-consistent."""
    m = session.get(Meta, "asof")
    return date.fromisoformat(m.value) if m else config.as_of_date()


def set_meta(session, key: str, value: str):
    m = session.get(Meta, key)
    if m is None:
        session.add(Meta(key=key, value=value))
    else:
        m.value = value
