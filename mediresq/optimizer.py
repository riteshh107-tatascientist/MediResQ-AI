"""Inventory redistribution optimiser (OR-Tools MIP, SCIP backend).

Decision: how many units of each medicine to move from surplus sources (hospitals/warehouses) to hospitals facing
projected shortages, minimising  transport + fixed trip cost + penalised unmet critical demand.
Constraints: stock above a protected reserve, expiry/shelf-life after arrival, source transfer capacity, cold-chain
compatibility, arrival before the next scheduled inbound delivery, blocked (disrupted) facilities."""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd
from ortools.linear_solver import pywraplp

from .datagen import _haversine
from .engine import H, Series, Snapshot, apply_removal, assess_series, project

FIXED_TRIP_COST = 600.0       # INR per used lane (one vehicle trip), synthetic assumption
VAR_COST = 0.015              # INR per unit-km, synthetic assumption
COLD_MULT = 1.8
CRIT_W = {1: 1.0, 2: 2.5, 3: 5.0}
PRIO_W = {1: 1.0, 2: 1.3, 3: 1.6}


@dataclass
class Params:
    horizon: int = 14
    min_shelf_days: int = 30
    cost_multiplier: float = 1.0
    demand_mult: float = 1.0
    buffer_pct: float = 0.10
    blocked: set = field(default_factory=set)
    time_limit_s: int = 20


def lane(snap: Snapshot, a: int, b: int, cold: bool, mult: float = 1.0) -> dict:
    fa, fb = snap.fac[a], snap.fac[b]
    km = _haversine((fa["lat"], fa["lon"]), (fb["lat"], fb["lon"]))
    eta = 0.5 + km / 350.0
    return dict(km=km, eta=eta, arr=int(math.ceil(eta)), unit=VAR_COST * km * (COLD_MULT if cold else 1) * mult,
                fixed=FIXED_TRIP_COST * (1.5 if cold else 1) * mult)


def compute_needs(snap: Snapshot, p: Params) -> dict:
    """Unmet units (projected, no recovery) at hospitals, plus a small safety buffer."""
    needs = {}
    for (m, f), s in snap.series.items():
        if snap.fac[f]["type"] != "Hospital":
            continue
        pr = project(s, horizon=p.horizon, demand_mult=p.demand_mult)
        if pr["unmet"] > 0.5:
            nxt = min([i["arr"] for i in s.inbound if i["arr"] > 0] or [p.horizon])
            need = int(math.ceil(pr["unmet"] * (1 + p.buffer_pct) + s.avg_daily * p.demand_mult))
            needs[(m, f)] = dict(need=need, unmet=pr["unmet"], stockout_day=pr["stockout_day"], deadline=min(nxt, p.horizon), avg=s.avg_daily * p.demand_mult)
    return needs


def _sources(snap: Snapshot, m: int, d: int, p: Params):
    med, out = snap.med[m], {}
    for (mm, f), s in snap.series.items():
        if mm != m or f == d or f in p.blocked:
            continue
        fa = snap.fac[f]
        if med["cold"] and not fa["cold"]:
            continue
        a = assess_series(snap, s, p.demand_mult)
        reserve = max(s.min_stock, a["reorder_point"], float(s.forecast[:p.horizon].sum() * p.demand_mult))
        out[f] = dict(series=s, reserve=reserve, surplus=max(0, s.usable - reserve), usable=s.usable)
    return out


def optimize_redistribution(snap: Snapshot, p: Params | None = None) -> dict:
    p = p or Params()
    needs = compute_needs(snap, p)
    res = dict(transfers=pd.DataFrame(), unmet=pd.DataFrame(), status="NO_NEED", total_cost=0.0, total_units=0, total_need=sum(n["need"] for n in needs.values()),
               explanations=[], needs=needs)
    if not needs:
        res["explanations"].append("No hospital has a projected unmet demand within the planning horizon - no redistribution needed.")
        return res
    solver = pywraplp.Solver.CreateSolver("SCIP") or pywraplp.Solver.CreateSolver("CBC")
    solver.SetTimeLimit(p.time_limit_s * 1000)
    X, Y, U, meta = {}, {}, {}, {}
    cap_use: dict[int, list] = {}
    lane_use: dict[tuple, list] = {}
    diag: dict[tuple, list] = {}
    obj = solver.Objective()
    for (m, d), n in needs.items():
        med, fd = snap.med[m], snap.fac[d]
        diag[(m, d)] = []
        srcs = _sources(snap, m, d, p)
        if med["cold"] and not fd["cold"]:
            diag[(m, d)].append(f"{fd['name']} has no cold-chain storage, so this cold-chain medicine cannot be transferred there")
            srcs = {}
        pen = (med["cost"] * 8 + 100) * CRIT_W[med["crit"]] * PRIO_W[fd["priority"]] * p.cost_multiplier
        U[(m, d)] = solver.NumVar(0, n["need"], f"u_{m}_{d}")
        obj.SetCoefficient(U[(m, d)], pen)
        cover = []
        for f, sinfo in srcs.items():
            ln = lane(snap, f, d, med["cold"], p.cost_multiplier)
            if ln["arr"] > n["deadline"]:
                diag[(m, d)].append(f"{snap.fac[f]['name']}: arrival day {ln['arr']} is later than the next scheduled delivery/horizon (day {n['deadline']})")
                continue
            eligible = sum(b["qty"] for b in sinfo["series"].batches if b["exp"] >= ln["arr"] + p.min_shelf_days)
            avail = int(min(eligible, sinfo["surplus"]))
            if avail <= 0:
                why = "no surplus above protected reserve" if sinfo["surplus"] <= 0 else f"remaining shelf life < {p.min_shelf_days} d after arrival"
                diag[(m, d)].append(f"{snap.fac[f]['name']}: {why} (usable {sinfo['usable']:,}, reserve {sinfo['reserve']:,.0f})")
                continue
            x = solver.IntVar(0, min(avail, n["need"]), f"x_{m}_{f}_{d}")
            X[(m, f, d)] = x; meta[(m, f, d)] = (ln, avail)
            obj.SetCoefficient(x, ln["unit"]); cover.append(x)
            cap_use.setdefault(f, []).append(x)
            lane_use.setdefault((f, d), []).append((x, min(avail, n["need"])))
            # also ties to source/medicine availability (shared across destinations)
        solver.Add(sum(cover) + U[(m, d)] >= n["need"]) if cover else solver.Add(U[(m, d)] >= n["need"])
        solver.Add(sum(cover) <= n["need"]) if cover else None
    # shared source availability per (medicine, source)
    by_ms: dict[tuple, list] = {}
    for (m, f, d), x in X.items():
        by_ms.setdefault((m, f), []).append((x, meta[(m, f, d)][1]))
    for (m, f), lst in by_ms.items():
        solver.Add(sum(x for x, _ in lst) <= max(a for _, a in lst))
    for f, xs in cap_use.items():
        solver.Add(sum(xs) <= snap.fac[f]["cap"])
    for (f, d), lst in lane_use.items():
        y = solver.BoolVar(f"y_{f}_{d}"); Y[(f, d)] = y
        solver.Add(sum(x for x, _ in lst) <= max(1, sum(c for _, c in lst)) * y)
        obj.SetCoefficient(y, FIXED_TRIP_COST * p.cost_multiplier)
    obj.SetMinimization()
    st = solver.Solve()
    res["status"] = {pywraplp.Solver.OPTIMAL: "OPTIMAL", pywraplp.Solver.FEASIBLE: "FEASIBLE (time limit)"}.get(st, "NO_SOLUTION")
    rows, bl = [], {}
    if st in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        for (m, f, d), x in sorted(X.items(), key=lambda kv: (-snap.med[kv[0][0]]["crit"], kv[0])):
            q = int(round(x.solution_value()))
            if q <= 0:
                continue
            ln = meta[(m, f, d)][0]
            ser = snap.series[(m, f)]
            key = (m, f)
            bl.setdefault(key, [dict(b) for b in ser.batches])
            rem, used = q, []
            for b in bl[key]:
                if rem <= 0:
                    break
                if b["exp"] < ln["arr"] + p.min_shelf_days or b["qty"] <= 0:
                    continue
                t = min(b["qty"], rem); b["qty"] -= t; rem -= t
                used.append(dict(batch_id=b["id"], batch_no=b["batch_no"], qty=t, expiry=(snap.asof + timedelta(days=b["exp"])).isoformat()))
            n = needs[(m, d)]
            var_cost = ln["unit"] * q
            rows.append(dict(med_id=m, medicine=snap.med[m]["name"], src_id=f, source=snap.fac[f]["name"], dst_id=d, destination=snap.fac[d]["name"], quantity=q,
                             transport_cost=round(var_cost, 2), fixed_cost=round(ln["fixed"] if False else FIXED_TRIP_COST * p.cost_multiplier, 2),
                             distance_km=round(ln["km"], 1), eta_days=round(ln["eta"], 1), arrival_day=ln["arr"],
                             before_stockout=(n["stockout_day"] is None or ln["arr"] <= n["stockout_day"]),
                             batches=used, criticality=snap.med[m]["crit"], stockout_day=n["stockout_day"]))
    tr = pd.DataFrame(rows)
    if not tr.empty:  # allocate fixed trip cost to lanes once
        tr["lane_trips"] = tr.groupby(["src_id", "dst_id"])["quantity"].transform("count")
        tr["fixed_cost"] = (tr["fixed_cost"] / tr["lane_trips"]).round(2)
        tr["est_cost"] = (tr["transport_cost"] + tr["fixed_cost"]).round(2)
        tr["reasoning"] = tr.apply(lambda r: (
            f"{r.destination} is projected to run out of {r.medicine} on day {r.stockout_day}; {r.source} holds stock above its protected reserve. "
            f"FEFO batches shipped: {', '.join(b['batch_no'] + ' x' + str(b['qty']) + ' (exp ' + b['expiry'] + ')' for b in r.batches)}. "
            f"Arrival in ~{r.eta_days} d ({r.distance_km} km)" + (" - before the projected stockout." if r.before_stockout else " - AFTER the projected stockout (partial mitigation).")), axis=1)
    covered = {(m, d): 0 for (m, d) in needs}
    for r in rows:
        covered[(r["med_id"], r["dst_id"])] += r["quantity"]
    um = []
    for (m, d), n in needs.items():
        rem = max(0, n["need"] - covered[(m, d)])
        um.append(dict(med_id=m, medicine=snap.med[m]["name"], dst_id=d, destination=snap.fac[d]["name"], need=n["need"], covered=covered[(m, d)], remaining=rem,
                       explanation=("Fully covered by redistribution" if rem == 0 else "Not fully coverable: " + ("; ".join(diag[(m, d)]) or "insufficient eligible surplus")),
                       stockout_day=n["stockout_day"], criticality=snap.med[m]["crit"]))
    res.update(transfers=tr, unmet=pd.DataFrame(um), total_cost=float(tr["est_cost"].sum()) if not tr.empty else 0.0,
               total_units=int(tr["quantity"].sum()) if not tr.empty else 0)
    for (m, d), n in needs.items():
        if n["need"] - covered[(m, d)] > 0:
            res["explanations"].append(f"{snap.med[m]['name']} @ {snap.fac[d]['name']}: {n['need'] - covered[(m, d)]:,} units cannot be covered by redistribution. " + "; ".join(diag[(m, d)]))
    return res


def apply_transfers(snap: Snapshot, transfers: pd.DataFrame) -> Snapshot:
    """Apply a redistribution plan to a snapshot copy (used for 'recovered' scenarios)."""
    out = snap.copy()
    if transfers is None or transfers.empty:
        return out
    for r in transfers.itertuples():
        apply_removal(out.series[(r.med_id, r.src_id)], int(r.quantity))
        out.series[(r.med_id, r.dst_id)].inbound.append(dict(arr=int(r.arrival_day), qty=int(r.quantity), ship_id=None, supplier_id=None, origin_id=r.src_id))
    return out
