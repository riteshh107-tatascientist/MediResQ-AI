"""Supplier intelligence: lead time, delay frequency, fulfilment, reliability score (heuristic)."""
from __future__ import annotations
from datetime import date

import numpy as np
import pandas as pd

from .db import DisruptionEvent, PurchaseOrder, Supplier


def supplier_stats(session, asof: date) -> pd.DataFrame:
    sups = {s.id: s for s in session.query(Supplier).all()}
    pos = session.query(PurchaseOrder).filter(PurchaseOrder.actual_date.isnot(None)).all()
    rows = []
    events = session.query(DisruptionEvent).filter(DisruptionEvent.supplier_id.isnot(None), DisruptionEvent.type == "Supplier Delay").all()
    for sid, s in sups.items():
        p = [x for x in pos if x.supplier_id == sid]
        if p:
            delay = np.array([(x.actual_date - x.promised_date).days for x in p], float)
            lead = np.array([(x.actual_date - x.order_date).days for x in p], float)
            otd = float((delay <= 0).mean())
            fill = float(sum(x.delivered_qty for x in p) / max(sum(x.quantity for x in p), 1))
            late = delay[delay > 0]
            avg_delay_all = float(np.clip(delay, 0, None).mean())
            rel = 100 * (0.45 * otd + 0.30 * fill + 0.25 * (1 - min(avg_delay_all / max(s.promised_lead_days, 1), 1)))
            row = dict(promised_lead=s.promised_lead_days, n_orders=len(p), on_time_rate=otd, delay_freq=1 - otd,
                       avg_delay_late=float(late.mean()) if len(late) else 0.0, avg_delay_days=avg_delay_all, avg_lead=float(lead.mean()),
                       lead_std=float(lead.std(ddof=0)), lead_cv=float(lead.std(ddof=0) / max(lead.mean(), 1)), fill_rate=fill, reliability=rel)
        else:
            row = dict(promised_lead=s.promised_lead_days, n_orders=0, on_time_rate=np.nan, delay_freq=np.nan, avg_delay_late=0.0, avg_delay_days=0.0,
                       avg_lead=float(s.promised_lead_days), lead_std=0.0, lead_cv=0.0, fill_rate=np.nan, reliability=np.nan)
        active = [e for e in events if e.supplier_id == sid and (e.end_date is None or e.end_date >= asof) and e.start_date <= asof]
        row["active_delay_days"] = int(max([(e.end_date - asof).days for e in active if e.end_date] or [0])) if active else 0
        row.update(supplier_id=sid, code=s.code, supplier=s.name, city=s.city)
        row["risk"] = "Unrated" if np.isnan(row["reliability"]) else ("High" if row["reliability"] < 75 or row["active_delay_days"] > 0 else "Medium" if row["reliability"] < 88 else "Low")
        rows.append(row)
    return pd.DataFrame(rows).sort_values("reliability").reset_index(drop=True)
