"""AI Recovery Planner: combines forecasts, stockout risk, supplier reliability, shipment disruption and the optimiser
into a prioritised action plan. Nothing is executed - every action needs human approval."""
from __future__ import annotations
import json
import math
from datetime import date, datetime

from .db import Recommendation, Shipment
from .engine import assess_all, build_snapshot
from .optimizer import Params, optimize_redistribution

SEV = {"Critical": 3, "High": 2, "Medium": 1, "Low": 0}


def best_alternate_supplier(snap, avoid_id=None):
    s = snap.sup[(snap.sup.active_delay_days == 0) & snap.sup.reliability.notna()]
    if avoid_id is not None:
        s = s[s.supplier_id != avoid_id]
    return None if s.empty else s.sort_values(["reliability", "avg_lead"], ascending=[False, True]).iloc[0]


def build_plan(snap, params: Params | None = None, ass=None) -> dict:
    ass = ass if ass is not None else assess_all(snap, (params.demand_mult if params else 1.0))
    res = optimize_redistribution(snap, params)
    actions = []
    rl = ass.set_index(["med_id", "fac_id"])
    for r in res["transfers"].itertuples():
        risk = rl.loc[(r.med_id, r.dst_id)]
        actions.append(dict(kind="Redistribution", med_id=r.med_id, source_id=r.src_id, source_name=r.source, dest_id=r.dst_id, quantity=int(r.quantity),
                            est_cost=float(r.est_cost), eta_days=float(r.eta_days), batches=json.dumps(r.batches), reasoning=r.reasoning,
                            score=risk.risk_score + 10 * (1 if r.before_stockout else 0)))
    covered = {(r.med_id, r.dst_id): r.covered for r in res["unmet"].itertuples()} if not res["unmet"].empty else {}
    # residual / structural shortages -> procurement
    for r in ass[ass.risk_level.isin(["Critical", "High"])].itertuples():
        rem = res["needs"].get((r.med_id, r.fac_id))
        residual = (rem["need"] - covered.get((r.med_id, r.fac_id), 0)) if rem else 0
        if r.reorder_qty <= 0 and residual <= 0:
            continue
        mprim = snap.med[r.med_id]["supplier"]
        row = snap.sup[snap.sup.supplier_id == mprim]
        primary_bad = (not row.empty) and (row.iloc[0].active_delay_days > 0 or row.iloc[0].risk == "High")
        sup = best_alternate_supplier(snap, mprim if primary_bad else None) if primary_bad else row.iloc[0] if not row.empty else best_alternate_supplier(snap)
        if sup is None:
            continue
        qty = int(max(r.reorder_qty, residual))
        if qty <= 0 or r.on_order >= r.reorder_qty + residual and r.on_order > 0 and residual <= 0:
            continue
        cost = qty * snap.med[r.med_id]["cost"] * (1.10 if r.stockout_day is not None and r.stockout_day <= 7 else 1.0)
        why = (f"{r.reason}. Supplier {sup['supplier']} chosen: reliability {sup['reliability']:.0f}/100, avg lead {sup['avg_lead']:.1f} d"
               + (f" (primary supplier is delayed/high-risk, so an alternate is proposed)" if primary_bad else "") + f". Order covers lead-time demand + safety + 14-day cycle stock.")
        actions.append(dict(kind="Procurement", med_id=r.med_id, source_id=None, source_name=str(sup["supplier"]), dest_id=r.fac_id, quantity=qty, est_cost=float(cost),
                            eta_days=float(sup["avg_lead"]), batches="", reasoning=why, score=r.risk_score))
    delayed = {}
    for s in snap.series.values():
        for i in s.inbound:
            if i.get("ship_id"):
                delayed[i["ship_id"]] = s
    return dict(actions=actions, optimizer=res, assessment=ass)


def generate_plan(session, asof: date, created_by="system", params: Params | None = None, snap=None) -> str:
    snap = snap or build_snapshot(session, asof)
    plan = build_plan(snap, params)
    pid = "PLAN-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    # supersede stale pending items
    for r in session.query(Recommendation).filter_by(status="Pending").all():
        r.status = "Superseded"
    # expedite delayed shipments that feed at-risk series
    risky = {(r.med_id, r.fac_id): r for r in plan["assessment"].itertuples() if r.risk_level in ("Critical", "High")}
    for sh in session.query(Shipment).filter(Shipment.status == "Delayed", Shipment.delay_days > 0).all():
        k = (sh.medicine_id, sh.destination_id)
        if k in risky:
            r = risky[k]
            plan["actions"].append(dict(kind="Expedite", med_id=sh.medicine_id, source_id=None, source_name=sh.origin_name, dest_id=sh.destination_id, quantity=sh.quantity,
                                        est_cost=0.0, eta_days=float(sh.delay_days), batches="", reasoning=f"Shipment {sh.ship_no} is delayed {sh.delay_days} d while {r.facility} has risk score {r.risk_score}. Escalate with supplier/carrier to split-ship or expedite.",
                                        score=r.risk_score - 5))
    plan["actions"].sort(key=lambda a: -a["score"])
    for i, a in enumerate(plan["actions"], 1):
        d = {k: v for k, v in a.items() if k not in ("score", "med_id")}
        session.add(Recommendation(plan_id=pid, priority=i, medicine_id=a["med_id"], **d))
    session.commit()
    from .auth import audit
    audit(session, created_by, "PLAN_GENERATED", "recommendation", pid, f"{len(plan['actions'])} actions; optimiser status {plan['optimizer']['status']}")
    session.commit()
    return pid
