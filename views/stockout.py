import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from mediresq import ui
from mediresq.engine import project

ui.require_login(title="Stockout Early Warning", sub="Day-by-day FEFO projection with a visible reason for every alert."); ui.sidebar_user()
c = ui.ctx(); snap, ass = c["snap"], c["ass"]
ui.note("<b>Two different numbers:</b> the <b>risk score</b> (0-100) is a transparent <i>heuristic</i> built from days-to-stockout vs lead time, criticality and facility priority. "
        "The <b>stockout probability</b> is a <i>model-based</i> estimate (normal approximation from forecast error) - it is not empirically calibrated against historical outcomes.")
a, b, d = st.columns(3)
lv = a.multiselect("Risk level", ["Critical", "High", "Medium", "Low"], default=["Critical", "High"]); ft = b.selectbox("Location type", ["All", "Hospital", "Warehouse"]); only = d.checkbox("Only projected stockouts", True)
x = ass.copy()
x = x[x.risk_level.isin(lv)]
if ft != "All": x = x[x.fac_type == ft]
if only: x = x[x.stockout_day.notna()]
x = x.sort_values("risk_score", ascending=False)
ui.kpi_row([("Critical", f"{int((ass.risk_level == 'Critical').sum())}", "", "bad"), ("High", f"{int((ass.risk_level == 'High').sum())}", "", "warn"), ("Stockout \u2264 7 d", f"{int((ass.stockout_day <= 7).sum())}", "", "warn"), ("Needs reorder", f"{int((ass.reorder_qty > 0).sum())}", "reorder qty > 0", "info")])
st.write("")
show = x[["medicine", "facility", "risk_level", "risk_score", "usable", "days_of_inventory", "stockout_day", "shortage_date", "p_stockout_model", "reorder_qty", "reason"]]
ui.show_df(show, height=360)
if not x.empty:
    ui.section("Explain an alert")
    lab = {i: f"{r.medicine} @ {r.facility} ({r.risk_level})" for i, r in x.head(60).iterrows()}
    sel = st.selectbox("Select", list(lab), format_func=lambda i: lab[i]); r = x.loc[sel]
    k = st.columns(6)
    for col, (t, v) in zip(k, [("Days of inventory", r.days_of_inventory), ("Lead time (d)", r.lead_time), ("Lead-time demand", r.lt_demand), ("Safety stock", r.safety_stock), ("Reorder point", r.reorder_point), ("Reorder qty", r.reorder_qty)]):
        col.metric(t, f"{v:,.1f}" if isinstance(v, float) else f"{v:,}")
    st.info(f"**Why:** {r.reason}  \n**Heuristic risk score:** {r.risk_score} ({r.risk_level}) &nbsp;|&nbsp; **Model-based stockout probability before next replenishment:** {r.p_stockout_model:.0%}")
    ser = snap.series[(int(r.med_id), int(r.fac_id))]
    pr = project(ser); pn = project(type(ser)(**{**ser.__dict__, "inbound": []}))
    fig = go.Figure()
    fig.add_bar(x=list(range(30)), y=ser.forecast, name="Forecast demand", marker_color="rgba(34,211,238,.45)")
    fig.add_scatter(x=list(range(30)), y=pr["inv"], name="Projected stock (with scheduled inbound)", line=dict(color=ui.NAVY, width=3))
    fig.add_scatter(x=list(range(30)), y=pn["inv"], name="Projected stock (no inbound)", line=dict(color="#dc2626", dash="dot"))
    for i in ser.inbound: fig.add_vline(x=i["arr"], line_dash="dash", line_color="#10b981", annotation_text=f"inbound {i['qty']:,}")
    fig.add_vline(x=min(ser.lead, 29), line_color="#f59e0b", annotation_text="lead time")
    st.plotly_chart(ui.style_fig(fig.update_layout(title="30-day FEFO inventory projection", xaxis_title="Days from today", yaxis_title="Units"), 360), **ui.W)
