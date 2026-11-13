import plotly.graph_objects as go
import streamlit as st
from mediresq import ui
from mediresq.db import session_scope
from mediresq.optimizer import Params, optimize_redistribution
from mediresq.planner import generate_plan

u = ui.require_login(title="Inventory Redistribution Optimizer", sub="OR-Tools mixed-integer model: minimise transport + fixed trip cost + penalised unmet critical demand."); ui.sidebar_user()
c = ui.ctx(); snap, asof = c["snap"], c["asof"]
with st.expander("Model, constraints & assumptions", expanded=False):
    st.markdown("""**Decision:** units of each medicine moved from a source (hospital/warehouse) to a hospital with projected unmet demand.  
**Constraints:** stock above a protected reserve (max of policy minimum, reorder point, 14-day forecast) \u00b7 batches must retain \u2265 min shelf-life after arrival (FEFO allocation, expired/quarantined excluded) \u00b7 source transfer capacity \u00b7 cold-chain compatibility \u00b7 arrival before the next scheduled delivery \u00b7 blocked/disrupted facilities.  
**Objective:** transport (\u20b90.015/unit-km, x1.8 cold chain) + \u20b9600 fixed cost per used lane + unmet-demand penalty weighted by medicine criticality, facility priority and unit cost. Costs are synthetic assumptions.""")
a, b, d, e = st.columns(4)
hz = a.select_slider("Planning horizon (days)", [7, 10, 14, 21, 30], 14); shelf = b.select_slider("Min shelf life after arrival (d)", [0, 15, 30, 45, 60, 90], 30)
cm = d.slider("Transport cost multiplier", 0.5, 3.0, 1.0, 0.1); blk = e.multiselect("Blocked facilities (disrupted)", [f["name"] for f in snap.fac.values()])
bid = {f["name"]: f["id"] for f in snap.fac.values()}
p = Params(horizon=hz, min_shelf_days=shelf, cost_multiplier=cm, blocked={bid[x] for x in blk})
res = optimize_redistribution(snap, p)
tr, um = res["transfers"], res["unmet"]
cov = 1 - (um.remaining.sum() / um.need.sum()) if not um.empty and um.need.sum() else 1.0
ui.kpi_row([("Solver status", res["status"], "OR-Tools SCIP", "good" if res["status"] in ("OPTIMAL", "NO_NEED") else "warn"), ("Shortage cases", f"{len(res['needs'])}", "medicine x hospital", "warn"), ("Units to move", f"{res['total_units']:,}", f"of {res['total_need']:,} needed", "info"),
            ("Need covered", f"{cov:.0%}", "by redistribution", "good" if cov >= .99 else "warn"), ("Plan cost", f"\u20b9{res['total_cost']:,.0f}", "transport + trips", "info")])
st.write("")
if tr.empty:
    st.success(res["explanations"][0]) if res["explanations"] else st.warning("No feasible redistribution found.")
else:
    ui.section("Recommended transfers")
    ui.show_df(tr[["medicine", "source", "destination", "quantity", "est_cost", "eta_days", "distance_km", "before_stockout", "reasoning"]], height=320)
    fig = go.Figure()
    for r in tr.itertuples():
        s_, d_ = snap.fac[r.src_id], snap.fac[r.dst_id]
        fig.add_annotation(x=d_["lon"], y=d_["lat"], ax=s_["lon"], ay=s_["lat"], xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=3, arrowwidth=2.5, arrowcolor=ui.BLUE)
    for t, col in [("Warehouse", ui.NAVY), ("Hospital", ui.CYAN)]:
        f = [x for x in snap.fac.values() if x["type"] == t]
        fig.add_scatter(x=[x["lon"] for x in f], y=[x["lat"] for x in f], mode="markers+text", text=[x["code"] for x in f], textposition="top center", name=t, marker=dict(size=18, color=col, line=dict(width=2, color="#fff")), hovertext=[x["name"] for x in f])
    st.plotly_chart(ui.style_fig(fig.update_layout(title="Recommended transfer flows", xaxis_title="Longitude", yaxis_title="Latitude"), 400), **ui.W)
if not um.empty:
    ui.section("Coverage & infeasibility explanations")
    ui.show_df(um[["medicine", "destination", "need", "covered", "remaining", "stockout_day", "explanation"]], height=260)
if ui.role_can("run_planner"):
    if st.button("Create recommendations from this plan (needs approval)", type="primary"):
        with session_scope() as s:
            pid = generate_plan(s, asof, u["username"], p)
        ui.invalidate(); st.success(f"{pid} created - review it in Approvals & Audit.")
