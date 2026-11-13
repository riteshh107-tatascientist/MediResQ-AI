"""Safe CSV upload validation + import (consumption, batches)."""
from __future__ import annotations
import io
from datetime import date

import pandas as pd

from . import config
from .auth import audit
from .db import Batch, Consumption, Facility, Medicine

SPECS = {
    "consumption": ["medicine_code", "facility_code", "date", "quantity"],
    "batches": ["medicine_code", "facility_code", "batch_no", "mfg_date", "expiry_date", "quantity"],
}
DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def validate_csv(data: bytes, kind: str, session) -> tuple[pd.DataFrame, list[str]]:
    errs: list[str] = []
    if kind not in SPECS:
        return pd.DataFrame(), ["Unknown upload type"]
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        return pd.DataFrame(), [f"File exceeds {config.MAX_UPLOAD_MB} MB"]
    try:
        df = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False, nrows=200_000)
    except Exception:
        return pd.DataFrame(), ["File is not a valid CSV"]
    df.columns = [c.strip().lower() for c in df.columns]
    missing = [c for c in SPECS[kind] if c not in df.columns]
    if missing:
        return pd.DataFrame(), [f"Missing columns: {', '.join(missing)}"]
    df = df[SPECS[kind]].copy()
    for c in df.columns:
        df[c] = df[c].str.strip()
        bad = df[c].str.startswith(DANGEROUS) & ~df[c].str.match(r"^-?\d+(\.\d+)?$")
        if bad.any():
            errs.append(f"Column '{c}': {int(bad.sum())} cell(s) start with a formula character (possible CSV injection)")
    meds = {m.code: m.id for m in session.query(Medicine)}
    facs = {f.code: f.id for f in session.query(Facility)}
    df["medicine_id"] = df.medicine_code.map(meds); df["facility_id"] = df.facility_code.map(facs)
    if df.medicine_id.isna().any():
        errs.append(f"{int(df.medicine_id.isna().sum())} row(s) with unknown medicine_code")
    if df.facility_id.isna().any():
        errs.append(f"{int(df.facility_id.isna().sum())} row(s) with unknown facility_code")
    q = pd.to_numeric(df.quantity, errors="coerce")
    if q.isna().any() or (q < 0).any() or (q % 1 != 0).any():
        errs.append("quantity must be a non-negative integer in every row")
    df["quantity"] = q
    date_cols = ["date"] if kind == "consumption" else ["mfg_date", "expiry_date"]
    for c in date_cols:
        parsed = pd.to_datetime(df[c], errors="coerce", format="%Y-%m-%d")
        if parsed.isna().any():
            errs.append(f"{c}: {int(parsed.isna().sum())} invalid date(s) (use YYYY-MM-DD)")
        df[c] = parsed.dt.date
    if kind == "batches" and not errs and (df.expiry_date <= df.mfg_date).any():
        errs.append("expiry_date must be after mfg_date")
    if kind == "consumption" and not errs and df.duplicated(["medicine_code", "facility_code", "date"]).any():
        errs.append("Duplicate (medicine, facility, date) rows in file")
    return (df if not errs else pd.DataFrame()), errs


def import_rows(session, df: pd.DataFrame, kind: str, user: str) -> int:
    n = 0
    if kind == "consumption":
        have = {(r.medicine_id, r.facility_id, r.date) for r in session.query(Consumption.medicine_id, Consumption.facility_id, Consumption.date)}
        for r in df.itertuples():
            if (int(r.medicine_id), int(r.facility_id), r.date) in have:
                continue
            session.add(Consumption(medicine_id=int(r.medicine_id), facility_id=int(r.facility_id), date=r.date, quantity=int(r.quantity))); n += 1
    else:
        for r in df.itertuples():
            session.add(Batch(medicine_id=int(r.medicine_id), facility_id=int(r.facility_id), batch_no=r.batch_no[:40], mfg_date=r.mfg_date, expiry_date=r.expiry_date, quantity=int(r.quantity))); n += 1
    audit(session, user, "CSV_IMPORT", kind, "", f"{n} rows imported")
    session.commit()
    return n
