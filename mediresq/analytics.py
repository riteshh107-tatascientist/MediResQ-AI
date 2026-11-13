"""Dashboard KPIs, resilience indicator and advanced analytics - all computed from database records."""
from __future__ import annotations
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .db import Alert, Batch, Consumption, DisruptionEvent, Facility, Medicine, ModelMetric, Recommendation, Shipment
from .engine import Snapshot
from .suppliers import supplier_stats


def resilience_index(snap: Snapshot, ass: pd.DataFrame, sup: pd.DataFrame, bt: pd.DataFrame, ships: pd.DataFrame) -> dict:
    w = ass.criticality.map({1: 1, 2: 2, 3: 3})
    ok = (~ass.risk_level.isin(["High", "Critical"])).astype(float)
    coverage = float((ok * w).sum() / w.sum())
    otd = float(sup.on_time_rate.mean())
    crit = ass[ass.criticality == 3]
    crit_exp = float(crit.risk_level.isin(["High", "Critical"]).mean()) if len(crit) else 0.0
    tot_val = float(ass.inventory_value.sum()) or 1.0
    exp_val = float(bt[(bt.status == "Available") & (bt.days_to_expiry <= 60)].value.sum()) if not bt.empty else 0.0
    ship_ok = float((ships.delay_days == 0).mean()) if len(ships) else 1.0
    comp = dict(coverage_health=coverage, supplier_on_time=otd, critical_protection=1 - crit_exp, expiry_health=1 - min(2 * exp_val / tot_val, 1), shipment_reliability=ship_ok)
    idx = 100 * (0.35 * comp["coverage_health"] + 0.25 * comp["supplier_on_time"] + 0.20 * comp["critical_protection"] + 0.10 * comp["expiry_health"] + 0.10 * comp["shipment_reliability"])
    return dict(index=idx, components=comp)


def dashboard_kpis(session, snap: Snapshot, ass: pd.DataFrame, bt: pd.DataFrame) -> dict:
    sup = supplier_stats(session, snap.asof)
    ships = pd.DataFrame([dict(delay_days=s.delay_days, status=s.status) for s in session.query(Shipment).filter(Shipment.status.in_(["In Transit", "Delayed"]))])
    res = resilience_index(snap, ass, sup, bt, ships)
    return dict(
        medicines=session.query(Medicine).filter_by(active=True).count(),
        facilities=session.query(Facility).filter_by(type="Hospital", active=True).count(),
        warehouses=session.query(Facility).filter_by(type="Warehouse", active=True).count(),
        inventory_value=float(ass.inventory_value.sum()),
        critical_alerts=session.query(Alert).filter(Alert.severity == "Critical", Alert.status.in_(["Open", "Acknowledged"])).count(),
        predicted_stockouts=int(((ass.stockout_day.notna()) & (ass.stockout_day <= 14)).sum()),
        near_expiry=int(((bt.status == "Available") & (bt.days_to_expiry > 0) & (bt.days_to_expiry <= 90)).sum()) if not bt.empty else 0,
        expired_batches=int((bt.bucket == "Expired").sum()) if not bt.empty else 0,
        supplier_risks=int((sup.risk == "High").sum()),
        pending=session.query(Recommendation).filter_by(status="Pending").count(),
        resilience=res)


def advanced_metrics(session, snap: Snapshot, ass: pd.DataFrame, bt: pd.DataFrame) -> dict:
    asof = snap.asof
    mt = session.query(ModelMetric).all()
    sel = [m for m in mt if m.selected]
    base = {}
    for m in mt:
        base.setdefault(m.model, []).append(m.wape)
    hosp = ass[ass.fac_type == "Hospital"]
    sup = supplier_stats(session, asof)
    cons = pd.DataFrame(session.query(Consumption.medicine_id, Consumption.quantity).filter(Consumption.date >= asof - timedelta(days=365)).all(), columns=["m", "q"])
    cost = {m.id: m.unit_cost for m in session.query(Medicine)}
    ann_val = float((cons.q * cons.m.map(cost)).sum()) if not cons.empty else 0.0
    hosp_val = float(hosp.inventory_value.sum()) or 1.0
    ev = session.query(DisruptionEvent).filter(DisruptionEvent.detected_date.isnot(None)).all()
    det = [(e.detected_date - e.start_date).days for e in ev]
    plan = session.query(Recommendation).filter(Recommendation.status != "Superseded").order_by(Recommendation.id.desc()).first()
    plan_cost = float(sum(r.est_cost for r in session.query(Recommendation).filter_by(plan_id=plan.plan_id))) if plan else 0.0
    wastage = float(bt[bt.bucket == "Expired"].value.sum()) if not bt.empty else 0.0
    risk_w = float(bt.wastage_risk_value.sum()) if "wastage_risk_value" in bt else 0.0
    return dict(
        forecast_wape_selected=float(np.mean([m.wape for m in sel])) if sel else float("nan"),
        forecast_mae_selected=float(np.mean([m.mae for m in sel])) if sel else float("nan"),
        forecast_rmse_selected=float(np.mean([m.rmse for m in sel])) if sel else float("nan"),
        baseline_wape={k: float(np.mean(v)) for k, v in base.items()},
        stockout_risk_series=int(((hosp.stockout_day.notna()) & (hosp.stockout_day <= 14)).sum()),
        stock_availability=float((hosp.usable > 0).mean()),
        demand_fulfilment_14d=float(hosp.fulfilment_14d.mean()),
        inventory_turnover=ann_val / hosp_val,
        expired_value=wastage, wastage_risk_value=risk_w,
        supplier_otd=float(sup.on_time_rate.mean()), lead_time_variability=float(sup.lead_std.mean()),
        recovery_plan_cost=plan_cost, detection_time_days=float(np.mean(det)) if det else float("nan"), detection_events=len(det))


def facility_risk(ass: pd.DataFrame) -> pd.DataFrame:
    g = ass.groupby("facility").agg(series=("med_id", "count"), critical=("risk_level", lambda x: int((x == "Critical").sum())), high=("risk_level", lambda x: int((x == "High").sum())),
                                    avg_risk=("risk_score", "mean"), inventory_value=("inventory_value", "sum")).reset_index()
    g["exposure_score"] = g.critical * 3 + g.high * 1.5 + g.avg_risk / 10
    return g.sort_values("exposure_score", ascending=False)
