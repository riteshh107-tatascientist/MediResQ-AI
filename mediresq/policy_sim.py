"""Controlled Monte-Carlo comparison of a STATIC (s,S) policy vs the INTELLIGENT policy (adaptive reorder point with
supplier lead-time variability, criticality-based service level, lateral transfers and expedited replenishment).
Replays historical (synthetic) demand with injected random supplier delays and demand surges; both policies face
identical random draws (common random numbers). ALL RESULTS ARE SIMULATED - not real hospital outcomes."""
from __future__ import annotations
from datetime import date

import numpy as np
import pandas as pd

from .db import Consumption, Facility, Medicine
from .suppliers import supplier_stats

ZC = {1: 1.28, 2: 1.65, 3: 2.05}
EXPEDITE_PREMIUM = 0.15


def _prep(session, asof: date):
    hosp = list(session.query(Facility).filter_by(type="Hospital").order_by(Facility.id))
    meds = session.query(Medicine).order_by(Medicine.id).all()
    rows = session.query(Consumption.medicine_id, Consumption.facility_id, Consumption.date, Consumption.quantity).all()
    df = pd.DataFrame(rows, columns=["m", "f", "d", "q"]); df["d"] = pd.to_datetime(df["d"])
    piv = df.pivot_table(index="d", columns=["m", "f"], values="q", aggfunc="sum").sort_index().fillna(0)
    return hosp, meds, piv, supplier_stats(session, asof).set_index("supplier_id")


def run_policy_comparison(session, asof: date, sim_days: int = 90, n_runs: int = 10, seed: int = 7) -> dict:
    hosp, meds, piv, sup = _prep(session, asof)
    hist, test = piv.iloc[:-sim_days], piv.iloc[-sim_days:]
    nh, T = len(hosp), sim_days
    pols = ["Static policy", "Intelligent policy"]
    out = []
    for run in range(n_runs):
        rng = np.random.default_rng(seed + run)
        tot = {p: dict(dem=0.0, srv=0.0, so=0, inv=0.0, orders=0, transfers=0, expedites=0, prem=0.0, cd=0.0, cs=0.0) for p in pols}
        for m in meds:
            cols = [(m.id, h.id) for h in hosp]
            Dh, Dt = hist[cols].values.astype(float), test[cols].values.astype(float)
            surge = np.ones_like(Dt)
            for t in np.where(rng.random(T) < 0.02)[0]:
                surge[t:t + 7] *= rng.uniform(1.4, 2.0)
            D = np.round(Dt * surge)
            s = sup.loc[m.primary_supplier_id]
            late = rng.random((T, nh)) > s.on_time_rate
            extra = np.maximum(1, np.rint(rng.exponential(max(s.avg_delay_late, 1), (T, nh))))
            Ld = (int(s.promised_lead) + late * extra + (rng.random((T, nh)) < 0.03) * 7).astype(int)
            full = np.vstack([Dh, D])
            base = Dh[-90:].mean(0)
            for pol in pols:
                P = tot[pol]
                inv = np.maximum(Dh[-60:].mean(0) * 12, 1.0)
                buf = np.zeros((T + 60, nh))
                for t in range(T):
                    inv = inv + buf[t]
                    srv = np.minimum(inv, D[t]); inv = inv - srv
                    P["dem"] += D[t].sum(); P["srv"] += srv.sum(); P["so"] += int(((D[t] - srv) > 0.5).sum()); P["inv"] += inv.sum() * m.unit_cost
                    if m.criticality == 3:
                        P["cd"] += D[t].sum(); P["cs"] += srv.sum()
                    past = full[len(Dh) + t - 28: len(Dh) + t]          # only data known before day t+1 (no leakage)
                    if pol == "Static policy":
                        avg = base; rop = avg * s.promised_lead + avg * 3; up_to = avg * 30
                    else:
                        w = np.exp(np.linspace(-2, 0, len(past)))[:, None]
                        avg = (past * w).sum(0) / w.sum(); sd = past.std(0)
                        L = s.avg_lead + (s.active_delay_days or 0)
                        rop = avg * L + ZC[m.criticality] * np.sqrt(L * sd ** 2 + (avg * s.lead_std) ** 2); up_to = rop + avg * 14
                        for j in range(nh):  # lateral transfer: <2 d cover and a peer holds >25 d
                            if avg[j] > 0.3 and inv[j] < 2 * avg[j]:
                                peers = [k for k in range(nh) if k != j and avg[k] > 0.1 and inv[k] > 25 * avg[k]]
                                if peers:
                                    k = max(peers, key=lambda x: inv[x] / avg[x]); q = min(inv[k] - 20 * avg[k], 5 * avg[j] + 1)
                                    if q > 0:
                                        inv[k] -= q; buf[t + 1, j] += q; P["transfers"] += 1
                        for j in range(nh):  # expedite if imminent stockout and nothing arriving within 2 days
                            if avg[j] > 0.3 and inv[j] + buf[t + 1:t + 3, j].sum() < 1.5 * avg[j]:
                                q = avg[j] * 7; buf[t + 2, j] += q; P["expedites"] += 1; P["prem"] += q * m.unit_cost * EXPEDITE_PREMIUM
                    on_order = buf[t + 1:].sum(0)
                    for j in np.where(inv + on_order < rop)[0]:
                        q = max(up_to[j] - inv[j] - on_order[j], 1); buf[t + Ld[t, j], j] += q; P["orders"] += 1
        for pol, v in tot.items():
            out.append(dict(policy=pol, run=run, fill_rate=v["srv"] / v["dem"], critical_fill_rate=v["cs"] / max(v["cd"], 1), stockout_days=v["so"],
                            avg_inventory_value=v["inv"] / T, orders=v["orders"], transfers=v["transfers"], expedites=v["expedites"], expedite_premium=v["prem"]))
    runs = pd.DataFrame(out)
    summ = runs.groupby("policy").agg(fill_rate=("fill_rate", "mean"), fill_sd=("fill_rate", "std"), critical_fill_rate=("critical_fill_rate", "mean"),
                                      stockout_days=("stockout_days", "mean"), avg_inventory_value=("avg_inventory_value", "mean"), orders=("orders", "mean"),
                                      transfers=("transfers", "mean"), expedites=("expedites", "mean"), expedite_premium=("expedite_premium", "mean")).reset_index()
    return dict(summary=summ, runs=runs, sim_days=T, n_runs=n_runs)
