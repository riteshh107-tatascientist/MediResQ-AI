"""Batch & expiry intelligence: buckets, FEFO order, wastage risk, safe transfer candidates."""
from __future__ import annotations
from datetime import date

import pandas as pd

from .db import Batch, Facility, Medicine
from .engine import Snapshot
from .optimizer import lane


def batch_table(session, asof: date, snap: Snapshot | None = None) -> pd.DataFrame:
    meds = {m.id: m for m in session.query(Medicine).all()}
    facs = {f.id: f for f in session.query(Facility).all()}
    rows = []
    for b in session.query(Batch).filter(Batch.quantity > 0).all():
        d = (b.expiry_date - asof).days
        m = meds[b.medicine_id]
        bucket = "Quarantined" if b.status == "Quarantined" else "Expired" if d <= 0 else "1-30 d" if d <= 30 else "31-60 d" if d <= 60 else "61-90 d" if d <= 90 else ">90 d"
        rows.append(dict(batch_id=b.id, med_id=b.medicine_id, fac_id=b.facility_id, medicine=m.name, facility=facs[b.facility_id].name, batch_no=b.batch_no,
                         mfg_date=b.mfg_date, expiry_date=b.expiry_date, days_to_expiry=d, quantity=b.quantity, status=b.status, bucket=bucket,
                         value=b.quantity * m.unit_cost, unit_cost=m.unit_cost))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["wastage_risk_qty"] = 0
    if snap is not None:  # FEFO cumulative consumption vs stock expiring
        for (m, f), g in df[(df.status == "Available") & (df.days_to_expiry > 0)].groupby(["med_id", "fac_id"]):
            ser = snap.series.get((m, f))
            if ser is None:
                continue
            cum = 0
            for i, r in g.sort_values("days_to_expiry").iterrows():
                cum += r.quantity
                df.loc[i, "wastage_risk_qty"] = int(max(0, min(r.quantity, cum - ser.avg_daily * r.days_to_expiry)))
    df["wastage_risk_value"] = df.wastage_risk_qty * df.unit_cost
    return df.sort_values("days_to_expiry").reset_index(drop=True)


def fefo_order(session, med_id: int, fac_id: int, asof: date) -> pd.DataFrame:
    """Issue order for a medicine at a facility. Expired and quarantined batches are never recommended."""
    q = session.query(Batch).filter(Batch.medicine_id == med_id, Batch.facility_id == fac_id, Batch.quantity > 0, Batch.status == "Available",
                                    Batch.expiry_date > asof).order_by(Batch.expiry_date).all()
    return pd.DataFrame([dict(rank=i + 1, batch_no=b.batch_no, expiry_date=b.expiry_date, days_left=(b.expiry_date - asof).days, quantity=b.quantity) for i, b in enumerate(q)])


def safe_transfers(snap: Snapshot, bt: pd.DataFrame, min_days_left: int = 20) -> pd.DataFrame:
    """For batches at wastage risk, find a facility that can consume them before expiry (cold-chain compatible, ample remaining life)."""
    out = []
    for r in bt[(bt.wastage_risk_qty > 0) & (bt.status == "Available") & (bt.days_to_expiry >= min_days_left)].itertuples():
        med = snap.med[r.med_id]
        best = None
        for (m, f), s in snap.series.items():
            if m != r.med_id or f == r.fac_id or snap.fac[f]["type"] != "Hospital" or (med["cold"] and not snap.fac[f]["cold"]):
                continue
            ln = lane(snap, r.fac_id, f, med["cold"])
            life = r.days_to_expiry - ln["arr"]
            cap = int(s.avg_daily * max(life - 5, 0) - s.usable)
            if cap > 0 and (best is None or cap > best[1]):
                best = (f, cap, ln)
        if best:
            q = int(min(r.wastage_risk_qty, best[1]))
            out.append(dict(medicine=r.medicine, batch_no=r.batch_no, from_facility=r.facility, to_facility=snap.fac[best[0]]["name"], quantity=q, expiry_date=r.expiry_date,
                            days_to_expiry=r.days_to_expiry, value_saved=q * r.unit_cost, eta_days=round(best[2]["eta"], 1), est_cost=round(best[2]["unit"] * q + best[2]["fixed"], 0)))
    return pd.DataFrame(out)
