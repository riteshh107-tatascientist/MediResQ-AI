import numpy as np
import pandas as pd
import pytest
from datetime import date, timedelta
from sqlalchemy import text

from mediresq import auth, datagen, forecasting as F, db, inventory as inv
from mediresq.db import Batch, Medicine, Recommendation, AuditLog, StockMovement
from mediresq.engine import Series, assess_all, assess_series, build_snapshot, project
from conftest import ASOF


# ---------------------------------------------------------------- data ---------------------------------------------
def test_dataset_reproducible_and_valid():
    a, b = datagen.generate(ASOF, history_days=60), datagen.generate(ASOF, history_days=60)
    assert a["consumption"] == b["consumption"] and datagen.validate_tables(a) == []
    assert len(a["facilities"]) == 8 and len(a["suppliers"]) == 7 and 15 <= len(a["medicines"]) <= 25


def test_database_referential_integrity(dbs):
    with db.get_engine().connect() as c:
        assert c.execute(text("PRAGMA foreign_key_check")).fetchall() == []
        assert c.execute(text("select count(*) from batches where quantity<0")).scalar() == 0


# ---------------------------------------------------------------- inventory CRUD -----------------------------------
def test_inventory_crud(s):
    m = inv.add_medicine(s, "t", dict(code="TST1", name="Test Medicine", category="Test", unit="tab", unit_cost=2.5, criticality=2))
    assert s.get(Medicine, m.id).name == "Test Medicine"
    inv.update_medicine(s, "t", m.id, dict(unit_cost=3.0))
    assert s.get(Medicine, m.id).unit_cost == 3.0
    with pytest.raises(ValueError):
        inv.add_medicine(s, "t", dict(code="TST1", name="Dup", category="x", unit="u", unit_cost=1, criticality=1))
    with pytest.raises(Exception):
        inv.add_medicine(s, "t", dict(code="TST2", name="Neg", category="x", unit="u", unit_cost=-1, criticality=1))
    assert inv.delete_medicine(s, "t", m.id) == "deleted"
    existing = s.query(Medicine).first()
    assert "deactivated" in inv.delete_medicine(s, "t", existing.id)  # has history -> soft delete
    existing.active = True; s.commit()


def test_batch_validation_and_adjustment(s):
    b0 = s.query(Batch).filter(Batch.quantity > 10).first()
    with pytest.raises(Exception):
        inv.add_batch(s, "t", dict(medicine_id=b0.medicine_id, facility_id=b0.facility_id, batch_no="X-1", mfg_date=ASOF, expiry_date=ASOF - timedelta(days=1), quantity=5))
    nb = inv.add_batch(s, "t", dict(medicine_id=b0.medicine_id, facility_id=b0.facility_id, batch_no="TEST-NEW", mfg_date=ASOF, expiry_date=ASOF + timedelta(days=400), quantity=50))
    inv.adjust_batch(s, "t", nb.id, -20, "Write-off")
    assert s.get(Batch, nb.id).quantity == 30
    with pytest.raises(ValueError):
        inv.adjust_batch(s, "t", nb.id, -999)
    assert s.query(StockMovement).filter_by(batch_id=nb.id).count() == 2
    inv.delete_batch(s, "t", nb.id)


# ---------------------------------------------------------------- forecasting --------------------------------------
def test_metrics_exact():
    a, p = np.array([10., 0, 20, 10]), np.array([12., 2, 18, 8])
    m = F.metrics(a, p)
    assert m["mae"] == pytest.approx(2.0) and m["rmse"] == pytest.approx(2.0) and m["wape"] == pytest.approx(8 / 40)
    assert np.isnan(F.metrics(np.zeros(3), np.ones(3))["wape"])  # all-zero actuals handled


def test_clean_series_missing_zero_outlier():
    idx = pd.date_range("2026-01-01", periods=100)
    v = np.tile([5., 6, 5, 4, 6, 3, 0], 15)[:100].astype(float); v[40] = 500
    raw = pd.Series(v, index=idx).drop(idx[50])
    c, rep = F.clean_series(raw, date(2026, 4, 11))
    assert len(c) == 100 and rep["missing_imputed"] == 1 and rep["outliers_capped"] >= 1 and c.max() < 500 and (c == 0).sum() >= 10


def test_backtest_is_chronological_and_baselines_correct():
    idx = pd.date_range("2026-01-01", periods=120)
    s = pd.Series(np.arange(120, dtype=float) % 7 + 10, index=idx)
    bt = F.backtest(s, 28, ["Moving Average", "Seasonal Naive"])
    train = s.iloc[:-28]
    assert bt["Moving Average"]["pred"][0] == pytest.approx(train.values[-7:].mean())
    assert bt["Seasonal Naive"]["wape"] == pytest.approx(0.0, abs=1e-9)  # perfectly weekly-periodic series
    assert F.pick_best(bt) == "Seasonal Naive"


def test_all_models_produce_nonnegative_forecasts():
    rng = np.random.default_rng(0)
    s = pd.Series(rng.poisson(8, 140).astype(float), index=pd.date_range("2026-01-01", periods=140))
    for name in F.MODELS:
        p, _ = F.forecast_model(s, name, 30)
        assert len(p) == 30 and (p >= 0).all(), name


def test_forecasts_persisted(s):
    from mediresq.db import ForecastResult, ModelMetric
    assert s.query(ForecastResult).count() == 22 * 8 * 30
    assert s.query(ModelMetric).filter_by(selected=True).count() == 22 * 5
    assert all(m.wape >= 0 for m in s.query(ModelMetric))


# ---------------------------------------------------------------- stockout -----------------------------------------
def _series(usable, daily, inbound=(), exp=400, lead=5.0):
    return Series(1, 1, [dict(id=1, batch_no="B", qty=usable, exp=exp)], np.full(30, float(daily)), 2.0, float(daily), [dict(arr=a, qty=q, ship_id=None, supplier_id=None, origin_id=None) for a, q in inbound], 20, 500, lead)


def test_projection_math():
    pr = project(_series(100, 10))
    assert pr["stockout_day"] == 10 and pr["unmet"] == pytest.approx(200) and pr["fulfilment"] == pytest.approx(100 / 300)
    assert project(_series(100, 10, [(5, 500)]))["stockout_day"] is None
    late = project(_series(100, 10, [(15, 500)]))
    assert late["stockout_day"] == 10 and late["unmet"] == pytest.approx(50)


def test_projection_expiry_wastage():
    pr = project(_series(100, 1, exp=10))  # only 10 consumed before expiry
    assert pr["wastage"] == pytest.approx(90)


def test_demo_scenario_detected(snap):
    ass = assess_all(snap)
    r = ass[(ass.medicine.str.startswith("Ceftriaxone")) & (ass.facility.str.startswith("Hospital A"))].iloc[0]
    assert r.risk_level == "Critical" and r.stockout_day is not None and r.stockout_day <= 5 and "stockout" in r.reason
    assert 0 <= r.p_stockout_model <= 1 and 0 <= r.risk_score <= 100
    assert (ass.reorder_point >= 0).all() and (ass.safety_stock >= 0).all()


def test_expired_and_quarantined_not_usable(snap, s):
    for (m, f), ser in snap.series.items():
        assert all(b["exp"] > 0 for b in ser.batches)
    qty_q = sum(b.quantity for b in s.query(Batch).filter_by(status="Quarantined"))
    assert qty_q == sum(x.quarantined_qty for x in snap.series.values())


# ---------------------------------------------------------------- expiry -------------------------------------------
def test_expiry_buckets_and_fefo(s, snap):
    from mediresq.expiry import batch_table, fefo_order
    bt = batch_table(s, ASOF, snap)
    assert set(bt.bucket) <= {"Expired", "1-30 d", "31-60 d", "61-90 d", ">90 d", "Quarantined"}
    assert (bt[bt.bucket == "Expired"].days_to_expiry <= 0).all() and (bt[bt.bucket == "1-30 d"].days_to_expiry.between(1, 30)).all()
    one = bt[(bt.status == "Available") & (bt.days_to_expiry > 0)].iloc[0]
    fe = fefo_order(s, int(one.med_id), int(one.fac_id), ASOF)
    assert fe.days_left.is_monotonic_increasing and (fe.days_left > 0).all()


# ---------------------------------------------------------------- suppliers ----------------------------------------
def test_supplier_stats(s):
    from mediresq.suppliers import supplier_stats
    t = supplier_stats(s, ASOF)
    assert len(t) == 7 and t.reliability.between(0, 100).all() and t.on_time_rate.between(0, 1).all() and (t.fill_rate <= 1).all()
    assert t[t.code == "S2"].active_delay_days.iloc[0] > 0


# ---------------------------------------------------------------- optimizer ----------------------------------------
def test_optimizer_demo_plan(snap):
    from mediresq.optimizer import optimize_redistribution
    res = optimize_redistribution(snap)
    tr = res["transfers"]
    assert res["status"] in ("OPTIMAL", "FEASIBLE (time limit)") and not tr.empty
    ctx = tr[(tr.medicine.str.startswith("Ceftriaxone")) & (tr.destination.str.startswith("Hospital A"))]
    assert ctx.quantity.sum() > 0 and ctx.before_stockout.all()
    for r in tr.itertuples():  # constraints
        assert r.src_id != r.dst_id and r.quantity > 0
        assert sum(b["qty"] for b in r.batches) == r.quantity
        assert all(b["expiry"] > str(ASOF) for b in r.batches)
    assert all(v <= snap.fac[i]["cap"] for i, v in tr.groupby("src_id").quantity.sum().items())
    needs = res["needs"]
    cov = tr.groupby(["med_id", "dst_id"]).quantity.sum()
    for k, v in cov.items():
        assert v <= needs[k]["need"]


def test_optimizer_respects_cold_chain(snap):
    from mediresq.optimizer import optimize_redistribution
    tr = optimize_redistribution(snap)["transfers"]
    for r in tr.itertuples():
        if snap.med[r.med_id]["cold"]:
            assert snap.fac[r.dst_id]["cold"] and snap.fac[r.src_id]["cold"]


def test_optimizer_infeasibility_explained(snap):
    from mediresq.optimizer import Params, optimize_redistribution
    res = optimize_redistribution(snap, Params(blocked=set(snap.fac)))  # every source blocked
    assert res["transfers"].empty and res["total_units"] == 0
    assert not res["unmet"].empty and (res["unmet"].remaining == res["unmet"].need).all()
    assert all(isinstance(x, str) and len(x) > 10 for x in res["unmet"].explanation)


def test_optimizer_higher_cost_never_cheaper(snap):
    from mediresq.optimizer import Params, optimize_redistribution
    a = optimize_redistribution(snap, Params(cost_multiplier=1.0))["total_cost"]
    b = optimize_redistribution(snap, Params(cost_multiplier=2.0))["total_cost"]
    assert b >= a * 0.99


# ---------------------------------------------------------------- scenarios ----------------------------------------
def test_simulator_three_scenarios_and_db_untouched(snap, s):
    from mediresq.simulator import Scenario, run_scenario, comparison_table
    before = s.query(Batch).count(), sum(b.quantity for b in s.query(Batch))
    r = run_scenario(snap, Scenario(supplier_delay_days=7, demand_increase_pct=20))
    m = {k: r[k]["metrics"] for k in ("Baseline", "Disrupted", "Recovered")}
    assert m["Disrupted"]["fulfilment"] <= m["Baseline"]["fulfilment"] + 1e-9
    assert m["Recovered"]["fulfilment"] >= m["Disrupted"]["fulfilment"] and m["Recovered"]["recovery_cost"] >= 0
    assert len(comparison_table(r)) == 3
    assert (s.query(Batch).count(), sum(b.quantity for b in s.query(Batch))) == before


def test_simulator_noop_equals_baseline(snap):
    from mediresq.simulator import Scenario, run_scenario
    r = run_scenario(snap, Scenario())
    assert r["Baseline"]["metrics"]["fulfilment"] == pytest.approx(r["Disrupted"]["metrics"]["fulfilment"])


def test_shipment_delay_shifts_arrival(snap):
    from mediresq.simulator import Scenario, apply_disruption
    sid = int(snap.sup[snap.sup.code == "S2"].supplier_id.iloc[0])
    d = apply_disruption(snap, Scenario(supplier_delay_days=4, supplier_ids=[sid]))
    shifted = [(a, b) for k in snap.series for a, b in zip(snap.series[k].inbound, d.series[k].inbound) if a.get("supplier_id") == sid]
    assert shifted and all(b["arr"] == a["arr"] + 4 for a, b in shifted)


# ---------------------------------------------------------------- planner / approvals / audit ---------------------
def test_plan_requires_human_approval_and_workflow(s):
    from mediresq.approvals import decide
    pend = s.query(Recommendation).filter_by(status="Pending").order_by(Recommendation.priority).all()
    assert pend and all(r.decided_by is None for r in pend)
    a, b, c = pend[0], pend[1], pend[2]
    with pytest.raises(PermissionError):
        decide(s, a.id, "v", "Viewer", "Approve")
    with pytest.raises(ValueError):
        decide(s, b.id, "m", "Supply Chain Manager", "Reject", "")
    decide(s, a.id, "m", "Supply Chain Manager", "Approve", "ok")
    decide(s, b.id, "m", "Supply Chain Manager", "Reject", "not needed")
    decide(s, c.id, "m", "Supply Chain Manager", "Modify", "smaller", max(1, c.quantity // 2))
    s.expire_all()
    assert s.get(Recommendation, a.id).status == "Approved" and s.get(Recommendation, b.id).status == "Rejected"
    assert s.get(Recommendation, c.id).status == "Modified" and s.get(Recommendation, c.id).approved_qty == max(1, c.quantity // 2)
    with pytest.raises(ValueError):
        decide(s, a.id, "m", "Supply Chain Manager", "Approve")  # already decided
    assert s.query(AuditLog).filter(AuditLog.action.in_(["APPROVE", "REJECT", "MODIFY"])).count() >= 3


# ---------------------------------------------------------------- dashboard / analytics ---------------------------
def test_dashboard_kpis_match_database(s, snap):
    from mediresq.analytics import dashboard_kpis, advanced_metrics
    from mediresq.expiry import batch_table
    from mediresq.db import Facility, Alert
    ass = assess_all(snap); bt = batch_table(s, ASOF, snap)
    k = dashboard_kpis(s, snap, ass, bt)
    assert k["medicines"] == s.query(Medicine).filter_by(active=True).count() and k["facilities"] == 5 and k["warehouses"] == 3
    exp_val = sum(b.quantity * s.get(Medicine, b.medicine_id).unit_cost for b in s.query(Batch) if b.status == "Available" and (b.expiry_date - ASOF).days > 0)
    assert k["inventory_value"] == pytest.approx(exp_val, rel=1e-6)
    assert k["critical_alerts"] == s.query(Alert).filter(Alert.severity == "Critical", Alert.status.in_(["Open", "Acknowledged"])).count()
    assert 0 <= k["resilience"]["index"] <= 100
    m = advanced_metrics(s, snap, ass, bt)
    assert 0 <= m["forecast_wape_selected"] < 2 and m["inventory_turnover"] > 0


def test_alerts_have_reason_and_action(s):
    from mediresq.db import Alert
    al = s.query(Alert).all()
    assert al and all(a.reason and a.recommended_action and a.created_at for a in al)
    assert {"Critical Stock", "Predicted Stockout", "Expiry Risk", "Supplier Delay", "Shipment Disruption", "Overstock", "Unfulfilled Demand"} <= {a.type for a in al}


def test_policy_simulation_runs(s):
    from mediresq.policy_sim import run_policy_comparison
    r = run_policy_comparison(s, ASOF, sim_days=40, n_runs=2)
    assert set(r["summary"].policy) == {"Static policy", "Intelligent policy"} and r["summary"].fill_rate.between(0, 1).all()


# ---------------------------------------------------------------- security -----------------------------------------
def test_password_hashing_and_auth(s):
    h = auth.hash_password("Secret123"); assert h != "Secret123" and auth.verify_password("Secret123", h) and not auth.verify_password("secret123", h)
    assert auth.hash_password("Secret123") != h  # random salt
    assert auth.authenticate(s, "admin_demo", "wrong") is None
    assert auth.authenticate(s, "admin_demo", "Demo@2026!").role == "Administrator"
    assert auth.password_policy("abc") is not None and auth.password_policy("Strong123") is None


def test_role_permissions():
    assert auth.can("Administrator", "manage_users") and not auth.can("Viewer", "approve") and not auth.can("Warehouse Manager", "approve") and auth.can("Supply Chain Manager", "approve")
    assert auth.can("Warehouse Manager", "inventory_edit") and not auth.can("Viewer", "inventory_edit")


def test_csv_upload_validation(s):
    from mediresq.uploads import validate_csv
    ok = b"medicine_code,facility_code,date,quantity\nPAR500,H1,2027-01-01,10\n"
    assert validate_csv(ok, "consumption", s)[1] == []
    assert validate_csv(b"a,b\n1,2\n", "consumption", s)[1]
    assert validate_csv(b"medicine_code,facility_code,date,quantity\nNOPE,H1,2027-01-01,10\n", "consumption", s)[1]
    assert validate_csv(b"medicine_code,facility_code,date,quantity\nPAR500,H1,2027-01-01,-5\n", "consumption", s)[1]
    assert validate_csv(b"medicine_code,facility_code,date,quantity\n=cmd|' /C calc'!A0,H1,2027-01-01,5\n", "consumption", s)[1]
    assert validate_csv(b"x" * (6 * 1024 * 1024), "consumption", s)[1]


# ---------------------------------------------------------------- assistant ----------------------------------------
def test_assistant_answers_from_data(s, snap):
    from mediresq.assistant import answer
    from mediresq.expiry import batch_table
    ass = assess_all(snap); bt = batch_table(s, ASOF, snap)
    t, d = answer("Which medicines have critical stock?", s, snap, ass, bt)
    assert str(int((ass.risk_level == "Critical").sum())) in t
    t, d = answer("Which supplier has the highest delay?", s, snap, ass, bt); assert d is not None and len(d) == 7
    t, d = answer("what is the stock of ceftriaxone", s, snap, ass, bt); assert "Ceftriaxone" in t
    assert "Try" in answer("blah", s, snap, ass, bt)[0]
