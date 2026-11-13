"""Core decision engine: in-memory Snapshot of the network, FEFO inventory projection and stockout risk.
All what-if / optimisation modules operate on copies of a Snapshot, so scenarios never touch the database."""
from __future__ import annotations
import copy, math
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import config
from .db import get_asof, Batch, Facility, ForecastResult, InventoryPolicy, Medicine, ModelMetric, Consumption, Shipment
from .suppliers import supplier_stats

H = config.HORIZON
Z = {1: 1.28, 2: 1.65, 3: 2.05}  # service-level z by criticality (90 / 95 / 98 %)


@dataclass
class Series:
    med_id: int
    fac_id: int
    batches: list           # usable batches: dict(id,batch_no,qty,exp) exp = days from asof
    forecast: np.ndarray
    sigma: float
    avg_daily: float
    inbound: list = field(default_factory=list)  # dict(arr, qty, ship_id, supplier_id, origin_id)
    min_stock: int = 0
    max_stock: int = 0
    lead: float = 7.0
    expired_qty: int = 0
    quarantined_qty: int = 0

    @property
    def usable(self) -> int:
        return int(sum(b["qty"] for b in self.batches))


@dataclass
class Snapshot:
    asof: date
    fac: dict
    med: dict
    series: dict
    sup: pd.DataFrame
    blocked: set = field(default_factory=set)   # facilities unavailable as transfer sources
    labels: list = field(default_factory=list)  # scenario descriptions applied

    def copy(self) -> "Snapshot":
        return copy.deepcopy(self)

    def hospitals(self):
        return [f for f in self.fac.values() if f["type"] == "Hospital"]


def build_snapshot(session, asof: date | None = None) -> Snapshot:
    asof = asof or get_asof(session)
    fac = {f.id: dict(id=f.id, code=f.code, name=f.name, type=f.type, city=f.city, lat=f.lat, lon=f.lon, priority=f.priority, parent_id=f.parent_id,
                      cap=f.transfer_capacity, cold=f.has_cold_storage) for f in session.query(Facility).filter_by(active=True).all()}
    med = {m.id: dict(id=m.id, code=m.code, name=m.name, category=m.category, unit=m.unit, cost=m.unit_cost, crit=m.criticality, cold=m.cold_chain,
                      supplier=m.primary_supplier_id) for m in session.query(Medicine).filter_by(active=True).all()}
    sup = supplier_stats(session, asof)
    sup_idx = sup.set_index("supplier_id")
    pol = {(p.medicine_id, p.facility_id): (p.min_stock, p.max_stock) for p in session.query(InventoryPolicy).all()}
    fc = {}
    for r in session.query(ForecastResult).all():
        fc.setdefault((r.medicine_id, r.facility_id), {})[(r.date - asof).days] = r.yhat
    sig = {}
    for r in session.query(ModelMetric).filter_by(selected=True).all():
        sig[(r.medicine_id, r.facility_id)] = r.rmse
    # recent actual consumption (28d) for avg daily demand
    cutoff = asof - timedelta(days=28)
    cons = {}
    for mid, fid, q in session.query(Consumption.medicine_id, Consumption.facility_id, Consumption.quantity).filter(Consumption.date >= cutoff, Consumption.date < asof):
        cons.setdefault((mid, fid), []).append(q)
    batches = {}
    for b in session.query(Batch).all():
        batches.setdefault((b.medicine_id, b.facility_id), []).append(b)
    ships = session.query(Shipment).filter(Shipment.status.in_(["In Transit", "Delayed"]), Shipment.actual_arrival.is_(None)).all()
    hosp = [f for f in fac.values() if f["type"] == "Hospital"]
    series = {}
    for mid, m in med.items():
        for fid, f in fac.items():
            if f["type"] == "Hospital":
                avg = float(np.mean(cons.get((mid, fid), [0])))
                sg = sig.get((mid, fid), math.sqrt(max(avg, 0.1)))
            else:
                kids = [h["id"] for h in hosp if h["parent_id"] == fid]
                avg = float(sum(np.mean(cons.get((mid, k), [0])) for k in kids))
                sg = math.sqrt(sum(sig.get((mid, k), 1.0) ** 2 for k in kids))
            d = fc.get((mid, fid), {})
            arr = np.array([d.get(t, avg) for t in range(H)], float)
            usable, exp_q, qua_q = [], 0, 0
            for b in batches.get((mid, fid), []):
                e = (b.expiry_date - asof).days
                if b.status == "Quarantined":
                    qua_q += b.quantity
                elif e <= 0:
                    exp_q += b.quantity
                elif b.quantity > 0:
                    usable.append(dict(id=b.id, batch_no=b.batch_no, qty=b.quantity, exp=e))
            usable.sort(key=lambda x: x["exp"])
            mn, mx = pol.get((mid, fid), (0, 10 ** 6))
            lead = float(sup_idx.loc[m["supplier"], "avg_lead"]) + float(sup_idx.loc[m["supplier"], "active_delay_days"]) if m["supplier"] in sup_idx.index else 7.0
            inbound = []
            for s in ships:
                if s.medicine_id == mid and s.destination_id == fid:
                    inbound.append(dict(arr=max(0, (s.expected_arrival - asof).days + s.delay_days), qty=s.quantity, ship_id=s.id, supplier_id=s.supplier_id, origin_id=s.origin_id))
            series[(mid, fid)] = Series(mid, fid, usable, arr, float(sg), avg, inbound, mn, mx, lead, exp_q, qua_q)
    return Snapshot(asof, fac, med, series, sup)


# ------------------------------------------------------------------------------------- projection ---
def project(s: Series, horizon: int = H, demand_mult: float = 1.0) -> dict:
    """Daily FEFO simulation of one series: arrivals -> expiry write-off -> demand served (earliest expiry first)."""
    bl = [[b["qty"], b["exp"]] for b in s.batches]
    arrivals = {}
    for i in s.inbound:
        arrivals[i["arr"]] = arrivals.get(i["arr"], 0) + i["qty"]
    inv, served_tot, unmet_tot, waste, stock_day, unmet_days = [], 0.0, 0.0, 0.0, None, 0
    for t in range(horizon):
        if t in arrivals:
            bl.append([arrivals[t], t + 365]); bl.sort(key=lambda x: x[1])
        for b in bl:
            if b[1] <= t and b[0] > 0:
                waste += b[0]; b[0] = 0
        need = s.forecast[t] * demand_mult
        for b in bl:
            if need <= 0:
                break
            take = min(b[0], need); b[0] -= take; need -= take; served_tot += take
        if need > 1e-6:
            unmet_tot += need; unmet_days += 1
            if stock_day is None:
                stock_day = t
        inv.append(sum(b[0] for b in bl))
    dem = float(s.forecast[:horizon].sum() * demand_mult)
    return dict(inv=np.array(inv), unmet=unmet_tot, demand=dem, served=served_tot, stockout_day=stock_day, unmet_days=unmet_days,
                wastage=waste, fulfilment=(served_tot / dem if dem > 0 else 1.0))


def _phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def assess_series(snap: Snapshot, s: Series, demand_mult: float = 1.0) -> dict:
    m, f = snap.med[s.med_id], snap.fac[s.fac_id]
    L = max(s.lead, 1.0)
    Lc = int(math.ceil(L))
    fc = s.forecast * demand_mult
    lt_demand = float(fc[:Lc].sum())
    z = Z[m["crit"]]
    safety = z * s.sigma * math.sqrt(L)
    rop = lt_demand + safety
    usable = s.usable
    inbound_lt = sum(i["qty"] for i in s.inbound if i["arr"] <= Lc)
    on_order = sum(i["qty"] for i in s.inbound)
    position = usable + on_order
    pr = project(s, demand_mult=demand_mult)
    so = pr["stockout_day"]
    pw = project(s, horizon=14, demand_mult=demand_mult)  # planning window: no further replenishment assumed
    doi = usable / s.avg_daily / max(demand_mult, 1e-9) if s.avg_daily > 0.01 else 999.0
    # model-based probability that demand before the next replenishment arrival exceeds usable stock (normal approx.;
    # NOT empirically calibrated). Next replenishment = earliest scheduled inbound, else the expected lead time.
    t_r = max(1, min([i["arr"] for i in s.inbound if i["arr"] > 0] + [Lc]))
    mu_r = float(fc[:t_r].sum())
    sd = max(s.sigma * math.sqrt(t_r), 1e-6)
    p_so = 1 - _phi((usable - mu_r) / sd)
    t_so = so if so is not None else H
    ratio = t_so / (L + 2)
    base = 100 * min(max((2 - ratio) / 1.5, 0), 1)
    score = min(base * {1: 0.85, 2: 1.0, 3: 1.15}[m["crit"]] + (5 if usable < s.min_stock and base > 0 else 0), 100)
    if f["type"] == "Hospital":
        score = min(score * (0.9 + 0.05 * f["priority"]), 100)
    level = "Critical" if score >= 75 else "High" if score >= 50 else "Medium" if score >= 25 else "Low"
    target = rop + 14 * s.avg_daily * demand_mult
    reorder_qty = max(0, int(math.ceil(target - position)))
    reasons = []
    if so is not None:
        reasons.append(f"projected stockout in {so} day(s) ({(snap.asof + timedelta(days=so)).isoformat()}) vs replenishment lead time {L:.1f} d")
    else:
        reasons.append(f"no stockout projected within {H} days")
    reasons.append(f"usable stock {usable:,} vs min {s.min_stock:,} / ROP {rop:,.0f}")
    if s.inbound:
        late = [i for i in s.inbound if i["arr"] > Lc]
        reasons.append(f"{on_order:,} units inbound" + (f" ({sum(i['qty'] for i in late):,} arriving after day {Lc})" if late else ""))
    if s.expired_qty or s.quarantined_qty:
        reasons.append(f"{s.expired_qty:,} expired / {s.quarantined_qty:,} quarantined excluded")
    next_exp = [b for b in s.batches if b["exp"] <= 30]
    if next_exp:
        reasons.append(f"{sum(b['qty'] for b in next_exp):,} units expire within 30 d")
    short_date = (snap.asof + timedelta(days=so)) if so is not None else None
    return dict(med_id=s.med_id, fac_id=s.fac_id, medicine=m["name"], facility=f["name"], fac_type=f["type"], criticality=m["crit"], usable=usable,
                avg_daily=round(s.avg_daily, 2), days_of_inventory=round(doi, 1), lead_time=round(L, 1), lt_demand=round(lt_demand, 1),
                safety_stock=round(safety, 1), reorder_point=round(rop, 1), on_order=on_order, inventory_position=position,
                reorder_qty=reorder_qty, stockout_day=so, shortage_date=short_date, unmet_14d=round(pw["unmet"], 1), fulfilment_14d=round(pw["fulfilment"], 4),
                p_stockout_model=round(p_so, 3), risk_score=round(score, 1), risk_level=level, reason="; ".join(reasons),
                below_min=usable < s.min_stock, overstock=usable > s.max_stock, inventory_value=usable * m["cost"])


def assess_all(snap: Snapshot, demand_mult: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame([assess_series(snap, s, demand_mult) for s in snap.series.values()])


# -------------------------------------------------------------------------------- snapshot mutators ---
def apply_removal(s: Series, qty: int) -> list:
    """Remove qty FEFO from series; returns [(batch dict, qty_taken)]."""
    taken, rem = [], qty
    for b in s.batches:
        if rem <= 0:
            break
        t = min(b["qty"], rem); b["qty"] -= t; rem -= t
        if t:
            taken.append((dict(b), t))
    s.batches = [b for b in s.batches if b["qty"] > 0]
    return taken
