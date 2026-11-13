"""Alert Center: rule-based alert generation with reasons and recommended actions (idempotent upsert by key)."""
from __future__ import annotations
from datetime import date, datetime

import pandas as pd

from .db import Alert, Batch, Shipment
from .engine import assess_all, build_snapshot
from .suppliers import supplier_stats


def _collect(session, asof: date, snap=None, ass=None) -> list[dict]:
    snap = snap or build_snapshot(session, asof)
    ass = ass if ass is not None else assess_all(snap)
    out = []
    def add(type_, sev, key, msg, reason, action, m=None, f=None):
        out.append(dict(key=key, type=type_, severity=sev, medicine_id=m, facility_id=f, message=msg, reason=reason, recommended_action=action))
    for r in ass.itertuples():
        base = f"{r.medicine} @ {r.facility}"
        if r.risk_level in ("Critical",) or (r.below_min and r.risk_level in ("High",)):
            add("Critical Stock", "Critical" if r.risk_level == "Critical" else "High", f"CS|{r.med_id}|{r.fac_id}", f"Critical stock level: {base}",
                f"Risk score {r.risk_score} ({r.risk_level}, heuristic). {r.reason}", "Run the Recovery Planner; review transfer / procurement recommendations.", r.med_id, r.fac_id)
        if r.stockout_day is not None and r.stockout_day <= 14:
            sev = "Critical" if r.stockout_day <= r.lead_time and r.criticality >= 2 else "High" if r.stockout_day <= 14 and r.criticality >= 2 else "Medium"
            add("Predicted Stockout", sev, f"PS|{r.med_id}|{r.fac_id}", f"Predicted stockout in {r.stockout_day} d: {base}",
                f"Forecast demand exhausts usable stock on {r.shortage_date}; model-based stockout probability {r.p_stockout_model:.0%} (not empirically calibrated). {r.reason}",
                f"Reorder at least {r.reorder_qty:,} units or approve a transfer.", r.med_id, r.fac_id)
        if r.fac_type == "Hospital" and r.unmet_14d > 0.5:
            add("Unfulfilled Demand", "High" if r.criticality >= 2 else "Medium", f"UD|{r.med_id}|{r.fac_id}", f"Projected unmet demand {r.unmet_14d:,.0f} units: {base}",
                f"14-day projected fulfilment {r.fulfilment_14d:.0%} with currently scheduled inbound stock.", "Expedite inbound shipment or redistribute stock.", r.med_id, r.fac_id)
        if r.overstock and r.usable > 0:
            add("Overstock", "Low", f"OS|{r.med_id}|{r.fac_id}", f"Overstock: {base}", f"Usable stock {r.usable:,} exceeds policy maximum.", "Consider redistributing surplus to facilities with shortages.", r.med_id, r.fac_id)
    # expiry
    bt = pd.DataFrame([dict(m=b.medicine_id, f=b.facility_id, qty=b.quantity, exp=b.expiry_date, no=b.batch_no, st=b.status) for b in session.query(Batch).filter(Batch.quantity > 0)])
    if not bt.empty:
        bt["d"] = bt["exp"].apply(lambda e: (e - asof).days)
        for (m, f), g in bt[bt.st == "Available"].groupby(["m", "f"]):
            name = f"{snap.med[m]['name']} @ {snap.fac[f]['name']}"
            exp = g[g.d <= 0]
            if len(exp):
                add("Expiry Risk", "Critical", f"EX|{m}|{f}|expired", f"Expired inventory on record: {name}", f"{int(exp.qty.sum()):,} units in batches {', '.join(exp.no)} are past expiry (excluded from usable stock).", "Quarantine and write off; do not issue or transfer.", m, f)
            for lo, hi, sev, lab in [(1, 30, "High", "30"), (31, 60, "Medium", "60"), (61, 90, "Low", "90")]:
                x = g[(g.d >= lo) & (g.d <= hi)]
                if len(x):
                    val = int(x.qty.sum()) * snap.med[m]["cost"]
                    add("Expiry Risk", sev, f"EX|{m}|{f}|{lab}", f"{lab}-day expiry risk: {name}", f"{int(x.qty.sum()):,} units (INR {val:,.0f}) expire within {lab} days: {', '.join(x.no)}.", "Apply FEFO issuing; consider transfer to higher-demand facility.", m, f)
    # suppliers
    for r in supplier_stats(session, asof).itertuples():
        if r.active_delay_days > 0:
            add("Supplier Delay", "High", f"SD|{r.supplier_id}", f"Active supplier delay: {r.supplier}", f"Open disruption event; ~{r.active_delay_days} days of delay remaining. Historical on-time rate {r.on_time_rate:.0%}.", "Re-plan affected medicines; consider alternate supplier or transfers.")
        elif r.risk == "High":
            add("Supplier Delay", "Medium", f"SD|{r.supplier_id}", f"Low-reliability supplier: {r.supplier}", f"Reliability score {r.reliability:.0f}/100; on-time {r.on_time_rate:.0%}; avg delay {r.avg_delay_days:.1f} d.", "Increase safety stock for medicines sourced from this supplier.")
    ships = session.query(Shipment).filter(Shipment.status.in_(["In Transit", "Delayed"])).all()
    for s in ships:
        if s.delay_days > 0:
            add("Shipment Disruption", "High" if s.delay_days >= 5 else "Medium", f"SH|{s.id}", f"Shipment {s.ship_no} delayed {s.delay_days} d",
                f"{s.quantity:,} units of {snap.med[s.medicine_id]['name']} to {snap.fac[s.destination_id]['name']}; was due {s.expected_arrival}, now ~{s.expected_arrival.toordinal() + s.delay_days and date.fromordinal(s.expected_arrival.toordinal() + s.delay_days)}.",
                "Escalate with carrier/supplier; check destination stock cover.", s.medicine_id, s.destination_id)
    return out


def refresh_alerts(session, asof: date, snap=None, ass=None) -> int:
    now = datetime.now()
    new = _collect(session, asof, snap, ass)
    existing = {a.key: a for a in session.query(Alert).all()}
    seen = set()
    for a in new:
        seen.add(a["key"])
        e = existing.get(a["key"])
        if e is None:
            session.add(Alert(**a, status="Open", created_at=now, updated_at=now))
        else:
            for k in ("type", "severity", "message", "reason", "recommended_action"):
                setattr(e, k, a[k])
            if e.status == "Auto-Closed":
                e.status = "Open"
            e.updated_at = now
    for k, e in existing.items():
        if k not in seen and e.status in ("Open", "Acknowledged"):
            e.status, e.updated_at = "Auto-Closed", now
    session.commit()
    return len(new)
