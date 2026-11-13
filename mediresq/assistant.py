"""MediResQ Intelligence Assistant: rule-based intent routing over REAL application data (no LLM, no invented answers)."""
from __future__ import annotations
import re
from datetime import date

import pandas as pd

from .analytics import dashboard_kpis, facility_risk
from .db import Alert, Medicine, ModelMetric, Recommendation, Shipment
from .engine import Snapshot
from .suppliers import supplier_stats

HELP = ["Which medicines have critical stock?", "Which facility is at greatest risk?", "What batches expire next month?", "Which supplier has the highest delay?",
        "Explain the latest recovery recommendation", "Which shipments are delayed?", "How many approvals are pending?", "What is the forecast accuracy?",
        "What is the supply resilience score?", "What is the stock of Ceftriaxone?", "Which items are overstocked?"]


def _has(q, *words):
    return any(w in q for w in words)


def answer(question: str, session, snap: Snapshot, ass: pd.DataFrame, bt: pd.DataFrame) -> tuple[str, pd.DataFrame | None]:
    q = question.lower().strip()
    asof = snap.asof
    if not q:
        return "Ask me about stock, risk, expiry, suppliers, shipments, forecasts or recovery plans.", None
    # medicine-specific stock
    named = [m for m in snap.med.values() if m["name"].split()[0].lower() in q or m["code"].lower() in q.split()]
    if named and _has(q, "stock", "inventory", "how much", "available", "cover", "risk"):
        m = named[0]
        d = ass[ass.med_id == m["id"]][["facility", "usable", "days_of_inventory", "risk_level", "stockout_day", "reorder_qty"]]
        return f"**{m['name']}** - total usable stock **{int(d.usable.sum()):,} {m['unit']}s** across {len(d)} locations. Worst risk: **{ass[ass.med_id == m['id']].sort_values('risk_score').iloc[-1].risk_level}**.", d
    if _has(q, "resilien"):
        k = dashboard_kpis(session, snap, ass, bt)["resilience"]
        c = k["components"]
        return (f"The supply resilience indicator is **{k['index']:.0f}/100** (a heuristic composite, not a validated metric). Components: coverage health {c['coverage_health']:.0%}, supplier on-time {c['supplier_on_time']:.0%}, "
                f"critical-medicine protection {c['critical_protection']:.0%}, expiry health {c['expiry_health']:.0%}, shipment reliability {c['shipment_reliability']:.0%}."), None
    if _has(q, "critical") and _has(q, "stock", "medicine", "item"):
        d = ass[ass.risk_level == "Critical"].sort_values("risk_score", ascending=False)[["medicine", "facility", "usable", "days_of_inventory", "stockout_day", "risk_score", "reason"]]
        return (f"**{len(d)}** medicine-location pairs are at **Critical** risk (heuristic score >= 75)." if len(d) else "No medicine-location pair is currently Critical."), d.head(15)
    if _has(q, "facility", "hospital", "location") and _has(q, "risk", "greatest", "worst", "most"):
        f = facility_risk(ass[ass.fac_type == "Hospital"])
        top = f.iloc[0]
        return f"**{top.facility}** has the highest exposure: {int(top.critical)} Critical and {int(top.high)} High-risk medicines (mean risk score {top.avg_risk:.1f}).", f
    if _has(q, "expire", "expiry", "expiring", "batch"):
        days = 30 if _has(q, "next month", "30") else 60 if "60" in q else 90 if "90" in q else 30
        m = re.search(r"(\d+)\s*day", q)
        days = int(m.group(1)) if m else days
        d = bt[(bt.status == "Available") & (bt.days_to_expiry > 0) & (bt.days_to_expiry <= days)][["medicine", "facility", "batch_no", "expiry_date", "days_to_expiry", "quantity", "value"]]
        return f"**{len(d)}** batches (INR {d.value.sum():,.0f}) expire within {days} days.", d.head(25)
    if _has(q, "supplier", "vendor") and _has(q, "delay", "late", "reliab", "worst", "risk"):
        s = supplier_stats(session, asof).sort_values("avg_delay_days", ascending=False)
        t = s.iloc[0]
        return f"**{t.supplier}** has the highest average delay: {t.avg_delay_days:.1f} days per order (on-time rate {t.on_time_rate:.0%}, reliability {t.reliability:.0f}/100).", s[["supplier", "on_time_rate", "avg_delay_days", "fill_rate", "reliability", "risk"]]
    if _has(q, "shipment", "delayed", "transport"):
        rows = session.query(Shipment).filter(Shipment.status.in_(["In Transit", "Delayed"]), Shipment.delay_days > 0).all()
        d = pd.DataFrame([dict(shipment=s.ship_no, medicine=snap.med[s.medicine_id]["name"], destination=snap.fac[s.destination_id]["name"], quantity=s.quantity, delay_days=s.delay_days, expected=s.expected_arrival) for s in rows])
        return f"**{len(d)}** in-transit shipments are delayed.", d
    if _has(q, "recommend", "recovery", "plan", "explain"):
        r = session.query(Recommendation).filter(Recommendation.status == "Pending").order_by(Recommendation.priority).first()
        if not r:
            return "There are no pending recommendations. Generate a plan in the Recovery Planner.", None
        mname = snap.med[r.medicine_id]["name"]
        dest = snap.fac[r.dest_id]["name"] if r.dest_id else "-"
        return (f"**Top priority action ({r.plan_id} #{r.priority}): {r.kind}** of {r.quantity:,} units of **{mname}** to **{dest}** from {r.source_name}. Estimated cost INR {r.est_cost:,.0f}, ETA {r.eta_days:.1f} d.\n\n"
                f"**Why:** {r.reasoning}\n\nStatus: {r.status} - human approval is required before any action."), None
    if _has(q, "pending", "approval"):
        n = session.query(Recommendation).filter_by(status="Pending").count()
        return f"**{n}** recommendations are awaiting human approval.", None
    if _has(q, "accuracy", "forecast", "wape", "mae", "model"):
        mt = session.query(ModelMetric).all()
        d = pd.DataFrame([dict(model=m.model, wape=m.wape, mae=m.mae, rmse=m.rmse, selected=m.selected) for m in mt])
        if d.empty:
            return "No forecast evaluation exists yet - run forecasts first.", None
        g = d.groupby("model").agg(WAPE=("wape", "mean"), MAE=("mae", "mean"), RMSE=("rmse", "mean"), series_selected=("selected", "sum")).reset_index().sort_values("WAPE")
        return f"Best average WAPE on the chronological hold-out: **{g.iloc[0].model} ({g.iloc[0].WAPE:.1%})**. Metrics are computed from stored backtests.", g
    if _has(q, "overstock", "excess", "surplus"):
        d = ass[ass.overstock][["medicine", "facility", "usable", "days_of_inventory"]].sort_values("days_of_inventory", ascending=False)
        return f"**{len(d)}** locations exceed their maximum stock policy.", d.head(20)
    if _has(q, "inventory value", "stock value", "worth"):
        return f"Total usable inventory value is **INR {ass.inventory_value.sum():,.0f}** (synthetic unit costs).", None
    if _has(q, "alert"):
        n = session.query(Alert).filter(Alert.status == "Open").count()
        c = session.query(Alert).filter(Alert.status == "Open", Alert.severity == "Critical").count()
        return f"There are **{n}** open alerts, **{c}** of them Critical.", None
    return "I can answer questions from live application data. Try:\n\n" + "\n".join(f"- {h}" for h in HELP), None
