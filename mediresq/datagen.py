"""Reproducible SYNTHETIC dataset generator. All data is artificial - no real hospital, supplier or patient data."""
from __future__ import annotations
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import config

FACILITIES = [  # code, name, type, city, lat, lon, priority, parent code, capacity, cold, size
    ("W1", "Central Medical Warehouse - Bhopal", "Warehouse", "Bhopal", 23.2599, 77.4126, 2, None, 6000, True, 1.0),
    ("W2", "Regional Warehouse - Indore", "Warehouse", "Indore", 22.7196, 75.8577, 2, None, 5000, True, 1.0),
    ("W3", "Regional Warehouse - Jabalpur", "Warehouse", "Jabalpur", 23.1815, 79.9864, 2, None, 4000, True, 1.0),
    ("H1", "Hospital A - Bhopal Referral Hospital", "Hospital", "Bhopal", 23.2300, 77.4400, 3, "W1", 900, True, 1.6),
    ("H2", "Hospital B - Sehore District Hospital", "Hospital", "Sehore", 23.2000, 77.0850, 2, "W1", 700, True, 1.0),
    ("H3", "Hospital C - Raisen Civil Hospital", "Hospital", "Raisen", 23.3300, 77.7900, 1, "W1", 600, False, 0.7),
    ("H4", "Hospital D - Dewas District Hospital", "Hospital", "Dewas", 22.9676, 76.0534, 2, "W2", 800, True, 1.1),
    ("H5", "Hospital E - Katni Community Health Centre", "Hospital", "Katni", 23.8343, 80.3944, 2, "W3", 500, False, 0.8),
]
SUPPLIERS = [  # code, name, city, lat, lon, promised lead, on-time prob, mean delay days, fill rate
    ("S1", "Arogya Pharma Distributors (Synthetic)", "Bhopal", 23.26, 77.41, 5, 0.92, 1.5, 0.98),
    ("S2", "Sanjeevani MedSupply (Synthetic)", "Pithampur", 22.61, 75.69, 7, 0.78, 3.5, 0.93),
    ("S3", "Bharat LifeCare Logistics (Synthetic)", "Nagpur", 21.15, 79.09, 6, 0.88, 2.0, 0.96),
    ("S4", "MedLine Formulations (Synthetic)", "Ahmedabad", 23.02, 72.57, 8, 0.70, 4.0, 0.90),
    ("S5", "Nirmal Healthcare Traders (Synthetic)", "Bhopal", 23.24, 77.40, 4, 0.95, 1.0, 0.99),
    ("S6", "Vedic Pharma Wholesale (Synthetic)", "Jaipur", 26.91, 75.79, 9, 0.82, 3.0, 0.94),
    ("S7", "CityCure Biologics (Synthetic)", "Hyderabad", 17.38, 78.48, 6, 0.90, 2.0, 0.97),
]
MEDICINES = [  # code, name, category, unit, cost INR, crit, cold, shelf days, base daily demand (size 1), season, supplier idx
    ("PAR500", "Paracetamol 500mg Tablet", "Analgesic", "tablet", 0.6, 1, False, 1095, 220, "monsoon", 1),
    ("IBU400", "Ibuprofen 400mg Tablet", "Analgesic", "tablet", 0.9, 1, False, 1095, 90, "none", 1),
    ("AMX500", "Amoxicillin 500mg Capsule", "Antibiotic", "capsule", 3.2, 2, False, 730, 120, "monsoon", 3),
    ("AZI500", "Azithromycin 500mg Tablet", "Antibiotic", "tablet", 14.0, 2, False, 730, 45, "monsoon", 3),
    ("CTX1G", "Ceftriaxone 1g Injection", "Antibiotic", "vial", 38.0, 3, False, 720, 40, "none", 2),
    ("MET500", "Metformin 500mg Tablet", "Antidiabetic", "tablet", 0.8, 2, False, 1095, 160, "none", 5),
    ("INSR40", "Insulin Regular 40IU/ml Vial", "Antidiabetic", "vial", 135.0, 3, True, 540, 12, "none", 7),
    ("AML5", "Amlodipine 5mg Tablet", "Cardiovascular", "tablet", 0.7, 2, False, 1095, 140, "winter", 5),
    ("ATO10", "Atorvastatin 10mg Tablet", "Cardiovascular", "tablet", 2.0, 1, False, 1095, 90, "none", 5),
    ("ADR1", "Adrenaline 1mg/ml Injection", "Emergency", "ampoule", 22.0, 3, False, 720, 8, "none", 2),
    ("OXY10", "Oxytocin 10IU Injection", "Maternal Health", "ampoule", 18.0, 3, True, 540, 15, "none", 7),
    ("ORS", "ORS Sachet", "Rehydration", "sachet", 8.0, 2, False, 1095, 90, "monsoon", 1),
    ("NS500", "Normal Saline 0.9% 500ml", "IV Fluid", "bottle", 28.0, 3, False, 730, 70, "none", 6),
    ("RL500", "Ringer Lactate 500ml", "IV Fluid", "bottle", 32.0, 3, False, 730, 45, "none", 6),
    ("SAL100", "Salbutamol Inhaler 100mcg", "Respiratory", "inhaler", 95.0, 2, False, 730, 14, "winter", 4),
    ("OME20", "Omeprazole 20mg Capsule", "Gastro", "capsule", 1.4, 1, False, 1095, 130, "none", 4),
    ("ONDI4", "Ondansetron 4mg Injection", "Gastro", "ampoule", 12.0, 2, False, 730, 20, "none", 2),
    ("DIC75", "Diclofenac 75mg Injection", "Analgesic", "ampoule", 9.0, 1, False, 730, 28, "none", 4),
    ("TT05", "Tetanus Toxoid Vaccine", "Vaccine", "vial", 28.0, 3, True, 540, 10, "none", 7),
    ("ASV10", "Anti-Snake Venom 10ml", "Antidote", "vial", 850.0, 3, True, 540, 1.5, "monsoon", 7),
    ("HEP5K", "Heparin 5000IU Injection", "Anticoagulant", "vial", 45.0, 3, False, 730, 6, "none", 3),
    ("CET10", "Cetirizine 10mg Tablet", "Antihistamine", "tablet", 0.5, 1, False, 1095, 75, "summer", 6),
]
SEASON_PEAK_DOY = {"monsoon": 227, "winter": 10, "summer": 140}
DEMO = {"medicine": "CTX1G", "short": "H1", "surplus": "H3", "supplier": "S2", "delay_days": 7}


def _season_factor(kind: str, d: date) -> float:
    if kind == "none":
        return 1.0
    return 1 + 0.35 * math.cos(2 * math.pi * (d.timetuple().tm_yday - SEASON_PEAK_DOY[kind]) / 365)


def _haversine(a, b) -> float:
    r = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def generate(asof: date | None = None, seed: int | None = None, history_days: int | None = None) -> dict[str, list[dict]]:
    asof = asof or config.as_of_date()
    rng = np.random.default_rng(config.SEED if seed is None else seed)
    H = history_days or config.HISTORY_DAYS
    T: dict[str, list[dict]] = {}

    # ---- master data -------------------------------------------------------------------------------------
    fac_id = {f[0]: i + 1 for i, f in enumerate(FACILITIES)}
    T["facilities"] = [dict(id=fac_id[f[0]], code=f[0], name=f[1], type=f[2], city=f[3], lat=f[4], lon=f[5],
                            priority=f[6], parent_id=fac_id[f[7]] if f[7] else None, transfer_capacity=f[8],
                            has_cold_storage=f[9], size_factor=f[10], active=True) for f in FACILITIES]
    T["suppliers"] = [dict(id=i + 1, code=s[0], name=s[1], city=s[2], lat=s[3], lon=s[4], promised_lead_days=s[5], active=True)
                      for i, s in enumerate(SUPPLIERS)]
    T["medicines"] = [dict(id=i + 1, code=m[0], name=m[1], category=m[2], unit=m[3], unit_cost=m[4], criticality=m[5],
                           cold_chain=m[6], shelf_life_days=m[7], base_daily_demand=m[8], season=m[9],
                           primary_supplier_id=m[10], active=True) for i, m in enumerate(MEDICINES)]
    hospitals = [f for f in T["facilities"] if f["type"] == "Hospital"]
    warehouses = [f for f in T["facilities"] if f["type"] == "Warehouse"]
    med = {m["id"]: m for m in T["medicines"]}
    sup = {s["id"]: s for s in T["suppliers"]}
    sup_par = {s[0]: s for s in SUPPLIERS}

    # ---- consumption ----------------------------------------------------------------------------------------
    start = asof - timedelta(days=H)
    days = [start + timedelta(days=i) for i in range(H)]  # last day = asof - 1
    dow = np.array([1.1, 1.1, 1.1, 1.1, 1.05, 0.9, 0.7])
    cons, avg_daily = [], {}
    for m in T["medicines"]:
        sf = np.array([_season_factor(m["season"], d) for d in days])
        wf = np.array([dow[d.weekday()] for d in days])
        for h in hospitals:
            lam = m["base_daily_demand"] * h["size_factor"] * sf * wf * (1 + 0.08 * np.arange(H) / H)
            surge = np.ones(H)
            for t in np.where(rng.random(H) < 0.004)[0]:
                surge[t:t + int(rng.integers(3, 8))] *= rng.uniform(1.8, 2.6)
            q = rng.poisson(lam * surge).astype(float)
            for t in np.where(rng.random(H) < 0.003)[0]:  # data-entry style outliers
                q[t] = q[t] * rng.uniform(4, 6) + 5
            keep = rng.random(H) > 0.003  # ~0.3% days missing (no record)
            for t in range(H):
                if keep[t]:
                    cons.append(dict(medicine_id=m["id"], facility_id=h["id"], date=days[t], quantity=int(q[t])))
            avg_daily[(m["id"], h["id"])] = max(float(np.median(q[-56:])) * 0.5 + float(np.mean(q[-56:])) * 0.5, 0.05)
    for i, r in enumerate(cons):
        r["id"] = i + 1
    T["consumption"] = cons

    def avg_of(m_id, f):  # warehouse demand = children's
        if f["type"] == "Hospital":
            return avg_daily[(m_id, f["id"])]
        return sum(avg_daily[(m_id, h["id"])] for h in hospitals if h["parent_id"] == f["id"])

    # ---- batches / policy ------------------------------------------------------------------------------------
    batches, policy, stress = [], [], {}
    pairs = [(m["id"], h["id"]) for m in T["medicines"] for h in hospitals]
    for idx in rng.choice(len(pairs), size=6, replace=False):
        stress[pairs[idx]] = float(rng.uniform(3.5, 8.0))  # stress-tested low cover
    over = {pairs[i]: float(rng.uniform(75, 95)) for i in rng.choice(len(pairs), size=5, replace=False) if pairs[i] not in stress}
    fcode = {f["id"]: f["code"] for f in T["facilities"]}
    dm = DEMO["medicine"]
    dm_id = next(m["id"] for m in T["medicines"] if m["code"] == dm)
    # demo cover overrides (days of cover)
    demo_cover = {(dm_id, fac_id[DEMO["short"]]): 3.2, (dm_id, fac_id[DEMO["surplus"]]): 75.0, (dm_id, fac_id["W1"]): 6.5}
    bid = 0
    for m in T["medicines"]:
        for f in T["facilities"]:
            ad = avg_of(m["id"], f)
            key = (m["id"], f["id"])
            if f["type"] == "Hospital":
                cover = demo_cover.get(key) or stress.get(key) or over.get(key) or float(rng.uniform(18, 45))
            else:
                cover = demo_cover.get(key) or float(rng.uniform(45, 75))
            total = max(int(round(ad * cover)), 5)
            nb = int(rng.integers(2, 5))
            parts = np.maximum((rng.dirichlet(np.ones(nb)) * total).round().astype(int), 1)
            for j, qty in enumerate(parts):
                remaining = int(rng.uniform(40, 0.85 * m["shelf_life_days"]))
                status = "Available"
                if key in demo_cover:
                    remaining = int(rng.uniform(150, 0.8 * m["shelf_life_days"]))
                elif rng.random() < 0.07:
                    remaining = int(rng.integers(4, 88))  # near-expiry
                elif rng.random() < 0.012:
                    remaining = -int(rng.integers(5, 40))  # already expired (still on record)
                elif rng.random() < 0.012:
                    status = "Quarantined"
                exp = asof + timedelta(days=remaining)
                bid += 1
                batches.append(dict(id=bid, medicine_id=m["id"], facility_id=f["id"],
                                    supplier_id=m["primary_supplier_id"], batch_no=f"{m['code']}-{fcode[f['id']]}-{2025 + j}{bid:04d}",
                                    mfg_date=exp - timedelta(days=m["shelf_life_days"]), expiry_date=exp, quantity=int(qty), status=status))
            crit = m["criticality"]
            mn = int(math.ceil(ad * (3 + crit)))
            policy.append(dict(id=len(policy) + 1, medicine_id=m["id"], facility_id=f["id"], min_stock=mn, max_stock=max(int(math.ceil(ad * 45)), mn + 1)))
    T["batches"], T["inventory_policy"] = batches, policy

    # ---- purchase orders, shipments, movements ---------------------------------------------------------------
    pos, ships, moves = [], [], []
    def add_po(m, s_id, f_id, qty, odate, promised, actual, delivered, status):
        pos.append(dict(id=len(pos) + 1, po_no=f"PO-{len(pos) + 1:05d}", supplier_id=s_id, medicine_id=m["id"], facility_id=f_id,
                        quantity=qty, order_date=odate, promised_date=promised, actual_date=actual, delivered_qty=delivered, status=status))
        return pos[-1]
    for m in T["medicines"]:
        s = sup_par[SUPPLIERS[m["primary_supplier_id"] - 1][0]]
        _, _, _, _, _, lead, otd, md, fill = s
        t0 = start + timedelta(days=int(rng.integers(0, 20)))
        while t0 < asof - timedelta(days=lead + 6):
            dest = T["facilities"][int(rng.integers(0, 8))]
            nd = sum(avg_of(m["id"], dest) for _ in [0])
            qty = max(int(nd * rng.uniform(25, 50)), 10)
            promised = t0 + timedelta(days=lead)
            late = rng.random() > otd
            delay = int(max(1, round(rng.exponential(md)))) if late else int(rng.choice([0, 0, 0, -1]))
            actual = promised + timedelta(days=delay)
            if actual >= asof:
                actual = asof - timedelta(days=1)
            fr = 1.0 if rng.random() < fill else float(rng.uniform(0.6, 0.95))
            dq = int(qty * fr)
            po = add_po(m, m["primary_supplier_id"], dest["id"], qty, t0, promised, actual, dq, "Delivered" if dq >= qty else "Partial")
            ships.append(dict(id=len(ships) + 1, ship_no=f"SH-{len(ships) + 1:05d}", po_id=po["id"], supplier_id=m["primary_supplier_id"], origin_id=None,
                              origin_name=s[1], destination_id=dest["id"], medicine_id=m["id"], quantity=dq, dispatch_date=t0 + timedelta(days=1),
                              expected_arrival=promised, actual_arrival=actual, status="Delivered", delay_days=max(0, delay),
                              transport_mode="Road", is_simulated=True))
            moves.append(dict(date=actual, medicine_id=m["id"], facility_id=dest["id"], batch_id=None, type="Receipt", quantity=dq,
                              reference=po["po_no"], user="system"))
            t0 += timedelta(days=int(rng.integers(22, 40)))
    # open (in-transit) shipments
    def add_open(m_code, f_code, qty, exp_days, delay=0, origin=None, sup_code=None, mode="Road"):
        m = next(x for x in T["medicines"] if x["code"] == m_code)
        fid = fac_id[f_code]
        s_id = None if origin else next(i + 1 for i, s in enumerate(SUPPLIERS) if s[0] == sup_code)
        sp = SUPPLIERS[s_id - 1] if s_id else None
        po = add_po(m, s_id or m["primary_supplier_id"], fid, qty, asof - timedelta(days=5), asof + timedelta(days=exp_days), None, 0, "Open")
        ships.append(dict(id=len(ships) + 1, ship_no=f"SH-{len(ships) + 1:05d}", po_id=po["id"], supplier_id=s_id, origin_id=fac_id[origin] if origin else None,
                          origin_name=(next(f["name"] for f in T["facilities"] if f["code"] == origin) if origin else sp[1]),
                          destination_id=fid, medicine_id=m["id"], quantity=qty, dispatch_date=asof - timedelta(days=3),
                          expected_arrival=asof + timedelta(days=exp_days), actual_arrival=None,
                          status="Delayed" if delay else "In Transit", delay_days=delay, transport_mode=mode, is_simulated=True))
    d = DEMO["delay_days"]
    add_open("CTX1G", "H1", 1500, 2, delay=d, sup_code="S2")          # <-- demo: supplier delayed 7 days
    add_open("CTX1G", "W1", 4000, 4, delay=d, sup_code="S2")
    add_open("PAR500", "H2", 6000, 3, sup_code="S1")
    add_open("NS500", "H4", 1800, 2, sup_code="S6")
    add_open("INSR40", "H1", 300, 3, sup_code="S7", mode="Cold-chain truck")
    add_open("ADR1", "H5", 200, 5, delay=3, sup_code="S2")
    add_open("AMX500", "W2", 5000, 6, sup_code="S3")
    add_open("ORS", "H3", 2500, 1, origin="W1")
    add_open("OXY10", "H4", 400, 2, origin="W2", mode="Cold-chain truck")
    add_open("TT05", "W3", 600, 5, delay=2, sup_code="S7", mode="Cold-chain truck")
    for i, r in enumerate(moves):
        r["id"] = i + 1
    T["purchase_orders"], T["shipments"] = pos, ships

    # weekly issue summaries (last 8 weeks) + transfers
    cdf = pd.DataFrame(cons)
    cdf["date"] = pd.to_datetime(cdf["date"])
    recent = cdf[cdf["date"] >= pd.Timestamp(asof - timedelta(days=56))].copy()
    recent["wk"] = recent["date"].dt.to_period("W").dt.start_time
    for (mi, fi, wk), g in recent.groupby(["medicine_id", "facility_id", "wk"]):
        moves.append(dict(id=len(moves) + 1, date=(wk + pd.Timedelta(days=6)).date(), medicine_id=int(mi), facility_id=int(fi), batch_id=None,
                          type="Issue", quantity=-int(g["quantity"].sum()), reference="Weekly issue summary", user="system"))
    moves = [m for m in moves if m["date"] < asof + timedelta(days=1)]
    for i, r in enumerate(moves):
        r["id"] = i + 1
    T["stock_movements"] = moves

    # ---- disruption events ----------------------------------------------------------------------------------
    ev = []
    def add_ev(tp, desc, s=None, f=None, st=None, en=None, sev="Medium", det=0):
        ev.append(dict(id=len(ev) + 1, type=tp, description=desc, supplier_id=s, facility_id=f, start_date=st, end_date=en, severity=sev,
                       detected_date=(st + timedelta(days=det)) if det is not None else None, is_simulated=True))
    for _ in range(7):
        st = asof - timedelta(days=int(rng.integers(30, H - 10)))
        kind = str(rng.choice(["Supplier Delay", "Transport Disruption", "Demand Surge", "Warehouse Disruption", "Partial Delivery"]))
        add_ev(kind, f"[SIMULATED] Historical {kind.lower()} event for analytics baseline.", s=int(rng.integers(1, 8)) if "Supplier" in kind else None,
               f=int(rng.integers(1, 4)) if "Warehouse" in kind else None, st=st, en=st + timedelta(days=int(rng.integers(2, 9))),
               sev=str(rng.choice(["Low", "Medium", "High"])), det=int(rng.integers(0, 4)))
    add_ev("Supplier Delay", f"[SIMULATED] {SUPPLIERS[1][1]} reports a {d}-day production/transport delay on Ceftriaxone 1g and Adrenaline lots.",
           s=2, st=asof - timedelta(days=2), en=asof + timedelta(days=d), sev="High", det=1)
    T["disruption_events"] = ev

    # ---- users (hashes added at seed time) -------------------------------------------------------------------
    T["_meta"] = [dict(asof=asof.isoformat(), seed=config.SEED if seed is None else seed, history_days=H, demo=DEMO)]
    return T


def distance_km(f1: dict, f2: dict) -> float:
    return _haversine((f1["lat"], f1["lon"]), (f2["lat"], f2["lon"]))


def validate_tables(T: dict[str, list[dict]]) -> list[str]:
    """Referential-integrity and sanity checks on a generated dataset. Returns list of problems (empty = OK)."""
    issues = []
    ids = {k: {r["id"] for r in T[k]} for k in ["facilities", "medicines", "suppliers", "purchase_orders", "batches"]}
    fk = [("batches", "medicine_id", "medicines"), ("batches", "facility_id", "facilities"), ("consumption", "medicine_id", "medicines"),
          ("consumption", "facility_id", "facilities"), ("purchase_orders", "supplier_id", "suppliers"), ("purchase_orders", "medicine_id", "medicines"),
          ("purchase_orders", "facility_id", "facilities"), ("shipments", "po_id", "purchase_orders"), ("shipments", "destination_id", "facilities"),
          ("shipments", "medicine_id", "medicines"), ("inventory_policy", "medicine_id", "medicines"), ("inventory_policy", "facility_id", "facilities"),
          ("stock_movements", "medicine_id", "medicines"), ("stock_movements", "facility_id", "facilities")]
    for tbl, col, ref in fk:
        bad = sum(1 for r in T[tbl] if r[col] is not None and r[col] not in ids[ref])
        if bad:
            issues.append(f"{tbl}.{col}: {bad} orphan rows")
    if any(r["quantity"] < 0 for r in T["consumption"]):
        issues.append("negative consumption")
    if any(r["quantity"] < 0 for r in T["batches"]):
        issues.append("negative batch quantity")
    if any(r["expiry_date"] <= r["mfg_date"] for r in T["batches"]):
        issues.append("batch expiry <= manufacturing date")
    keys = [(r["medicine_id"], r["facility_id"], r["date"]) for r in T["consumption"]]
    if len(keys) != len(set(keys)):
        issues.append("duplicate consumption keys")
    if len({r["code"] for r in T["medicines"]}) != len(T["medicines"]):
        issues.append("duplicate medicine codes")
    return issues


def write_csvs(T: dict, out=None):
    out = out or config.CSV_DIR
    out.mkdir(parents=True, exist_ok=True)
    for k, rows in T.items():
        if not k.startswith("_"):
            pd.DataFrame(rows).to_csv(out / f"{k}.csv", index=False)
