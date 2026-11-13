"""What-if scenario simulator. Operates on Snapshot copies: baseline vs disrupted vs recovered. ALL OUTPUT IS SIMULATED."""
from __future__ import annotations
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .engine import H, Snapshot, project
from .optimizer import Params, apply_transfers, optimize_redistribution

PREMIUM = 0.15  # emergency procurement premium over unit cost (synthetic assumption)


@dataclass
class Scenario:
    supplier_delay_days: int = 0
    supplier_ids: list | None = None          # None = all suppliers
    demand_increase_pct: float = 0.0
    demand_medicine_ids: list | None = None   # None = all medicines
    warehouse_id: int | None = None
    warehouse_days: int = 0
    transport_cost_mult: float = 1.0
    stock_loss_pct: float = 0.0
    loss_facility_ids: list | None = None
    loss_medicine_ids: list | None = None
    alt_replenishment: bool = False
    alt_days: int = 3
    alt_cover_days: int = 14
    horizon: int = 14

    def describe(self) -> list[str]:
        d = []
        if self.supplier_delay_days: d.append(f"Supplier delay +{self.supplier_delay_days} d ({'all suppliers' if not self.supplier_ids else len(self.supplier_ids)} supplier(s))")
        if self.demand_increase_pct: d.append(f"Demand +{self.demand_increase_pct:.0f}%")
        if self.warehouse_id and self.warehouse_days: d.append(f"Warehouse disruption {self.warehouse_days} d")
        if self.transport_cost_mult != 1: d.append(f"Transport cost x{self.transport_cost_mult:.2f}")
        if self.stock_loss_pct: d.append(f"Inventory shortage -{self.stock_loss_pct:.0f}% stock")
        if self.alt_replenishment: d.append(f"Alternative replenishment in {self.alt_days} d")
        return d or ["No perturbation"]


def apply_disruption(base: Snapshot, sc: Scenario) -> Snapshot:
    s = base.copy()
    for k, ser in s.series.items():
        m = s.med[ser.med_id]
        if sc.supplier_delay_days and (sc.supplier_ids is None or m["supplier"] in sc.supplier_ids):
            ser.lead += sc.supplier_delay_days
        for i in ser.inbound:
            if sc.supplier_delay_days and i.get("supplier_id") and (sc.supplier_ids is None or i["supplier_id"] in sc.supplier_ids):
                i["arr"] += sc.supplier_delay_days
            if sc.warehouse_id and sc.warehouse_days and (i.get("origin_id") == sc.warehouse_id or ser.fac_id == sc.warehouse_id):
                i["arr"] += sc.warehouse_days
        if sc.demand_increase_pct and (sc.demand_medicine_ids is None or ser.med_id in sc.demand_medicine_ids):
            ser.forecast = ser.forecast * (1 + sc.demand_increase_pct / 100); ser.avg_daily *= (1 + sc.demand_increase_pct / 100)
        if sc.stock_loss_pct and (sc.loss_facility_ids is None or ser.fac_id in sc.loss_facility_ids) and (sc.loss_medicine_ids is None or ser.med_id in sc.loss_medicine_ids):
            for b in ser.batches:
                b["qty"] = int(b["qty"] * (1 - sc.stock_loss_pct / 100))
            ser.batches = [b for b in ser.batches if b["qty"] > 0]
    if sc.warehouse_id and sc.warehouse_days:
        s.blocked.add(sc.warehouse_id)
    return s


def _metrics(snap: Snapshot, horizon=14) -> tuple[dict, pd.DataFrame, np.ndarray]:
    rows, curve = [], np.zeros(horizon)
    for (m, f), ser in snap.series.items():
        if snap.fac[f]["type"] != "Hospital":
            continue
        pr = project(ser, horizon)
        med = snap.med[m]
        curve += pr["inv"]
        rows.append(dict(med_id=m, fac_id=f, medicine=med["name"], facility=snap.fac[f]["name"], criticality=med["crit"], demand=pr["demand"], served=pr["served"],
                         unmet=pr["unmet"], stockout_day=pr["stockout_day"], stockout_days=pr["unmet_days"], wastage_value=pr["wastage"] * med["cost"],
                         end_inventory=float(pr["inv"][-1]), end_value=float(pr["inv"][-1]) * med["cost"], fulfilment=pr["fulfilment"]))
    df = pd.DataFrame(rows)
    dem, srv = df.demand.sum(), df.served.sum()
    agg = dict(fulfilment=float(srv / dem) if dem else 1.0, series_at_risk=int((df.unmet > 0.5).sum()), stockout_days=int(df.stockout_days.sum()),
               unmet_units=float(df.unmet.sum()), critical_unmet=float(df[df.criticality == 3].unmet.sum()),
               unmet_value=float((df.unmet * df.med_id.map(lambda x: snap.med[x]["cost"])).sum()), wastage_value=float(df.wastage_value.sum()), end_value=float(df.end_value.sum()))
    return agg, df, curve


def run_scenario(base: Snapshot, sc: Scenario) -> dict:
    disrupted = apply_disruption(base, sc)
    p = Params(horizon=sc.horizon, cost_multiplier=sc.transport_cost_mult, blocked=set(disrupted.blocked))
    plan = optimize_redistribution(disrupted, p)
    recovered = apply_transfers(disrupted, plan["transfers"])
    alt_cost = alt_units = 0.0
    if sc.alt_replenishment:
        for (m, f), ser in recovered.series.items():
            if recovered.fac[f]["type"] != "Hospital":
                continue
            pr = project(ser, sc.horizon)
            if pr["unmet"] > 0.5:
                q = int(np.ceil(ser.avg_daily * sc.alt_cover_days + pr["unmet"]))
                ser.inbound.append(dict(arr=sc.alt_days, qty=q, ship_id=None, supplier_id=None, origin_id=None))
                alt_cost += q * recovered.med[m]["cost"] * PREMIUM; alt_units += q
    out = {}
    for name, snap in [("Baseline", base), ("Disrupted", disrupted), ("Recovered", recovered)]:
        agg, df, curve = _metrics(snap, sc.horizon)
        out[name] = dict(metrics=agg, detail=df, curve=curve)
    out["Recovered"]["metrics"]["recovery_cost"] = plan["total_cost"] + alt_cost
    out["Disrupted"]["metrics"]["recovery_cost"] = 0.0
    out["Baseline"]["metrics"]["recovery_cost"] = 0.0
    out["plan"] = plan
    out["alt"] = dict(cost=alt_cost, units=alt_units)
    out["description"] = sc.describe()
    return out


def comparison_table(res: dict) -> pd.DataFrame:
    rows = []
    for k in ["Baseline", "Disrupted", "Recovered"]:
        m = res[k]["metrics"]
        rows.append({"Scenario": k, "Demand fulfilment %": round(m["fulfilment"] * 100, 2), "Series at stockout risk": m["series_at_risk"], "Stockout days": m["stockout_days"],
                     "Unmet units": round(m["unmet_units"]), "Critical-medicine unmet units": round(m["critical_unmet"]), "Unmet demand value (INR)": round(m["unmet_value"]),
                     "Expiry wastage (INR)": round(m["wastage_value"]), "Recovery cost (INR)": round(m["recovery_cost"])})
    return pd.DataFrame(rows)
