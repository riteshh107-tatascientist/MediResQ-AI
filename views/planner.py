import pandas as pd
import plotly.express as px
import streamlit as st
from mediresq import ui
from mediresq.db import Recommendation, session_scope
from mediresq.planner import generate_plan

u = ui.require_login(title="AI Recovery Planner", sub="Forecasts + stockout risk + supplier reliability + shipment disruption + optimizer -> prioritised actions. Nothing executes without human approval."); ui.sidebar_user()
c = ui.ctx(); snap, asof = c["snap"], c["asof"]
st.markdown(ui.h("""<div class="mq-flow">""" + "".join(f'<div class="mq-step"><div class="n">{i + 1}</div><b>{t}</b><span>{d}</span></div>' for i, (t, d) in enumerate(
    [("Forecast", "demand per series"), ("Assess", "FEFO stockout risk"), ("Supplier & shipments", "reliability + delays"), ("Optimize", "OR-Tools transfers"), ("Approve", "human decision")])) + "</div>"), unsafe_allow_html=True)
st.write("")
if ui.role_can("run_planner"):
    if st.button("Generate / refresh recovery plan", type="primary"):
        with st.spinner("Optimising..."):
            with session_scope() as s: pid = generate_plan(s, asof, u["username"])
        ui.invalidate(); st.success(f"Plan {pid} generated. Previous pending actions were marked superseded.")
else:
    st.info("You can view plans; generating them requires the Supply Chain Manager or Administrator role.")
with session_scope() as s:
    last = s.query(Recommendation).filter(Recommendation.status != "Superseded").order_by(Recommendation.id.desc()).first()
    rows = s.query(Recommendation).filter_by(plan_id=last.plan_id).order_by(Recommendation.priority).all() if last else []
    df = pd.DataFrame([dict(rank=r.priority, kind=r.kind, medicine=snap.med[r.medicine_id]["name"], source=r.source_name, destination=snap.fac[r.dest_id]["name"] if r.dest_id else "-", quantity=r.quantity, cost=r.est_cost, eta_days=r.eta_days, status=r.status, reasoning=r.reasoning) for r in rows])
if df.empty:
    st.warning("No plan yet."); st.stop()
ui.kpi_row([("Plan", last.plan_id.replace("PLAN-", ""), "latest", "info"), ("Actions", f"{len(df)}", f"{(df.kind == 'Redistribution').sum()} transfers \u00b7 {(df.kind == 'Procurement').sum()} procurement \u00b7 {(df.kind == 'Expedite').sum()} expedite", "info"),
            ("Pending approval", f"{int((df.status == 'Pending').sum())}", "", "warn"), ("Total est. cost", f"\u20b9{df.cost.sum():,.0f}", "", "info")])
st.write("")
a, b = st.columns([1, 2])
a.plotly_chart(ui.style_fig(px.pie(df, names="kind", hole=.55, title="Action mix"), 300), **ui.W)
with b:
    ui.show_df(df.drop(columns=["reasoning"]), height=300)
ui.section("Prioritised actions with reasoning")
for r in df.head(15).itertuples():
    with st.expander(f"#{r.rank} \u00b7 {r.kind} \u00b7 {r.medicine} \u2192 {r.destination} \u00b7 {r.quantity:,} units \u00b7 {r.status}"):
        st.write(r.reasoning); st.caption(f"Source: {r.source} \u00b7 est. cost \u20b9{r.cost:,.0f} \u00b7 ETA {r.eta_days:.1f} d")
st.caption("Go to **Approvals & Audit** to approve, reject or modify these recommendations.")
