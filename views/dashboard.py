import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import timedelta
from mediresq import ui
from mediresq.analytics import dashboard_kpis, facility_risk
from mediresq.db import Alert, AuditLog, Consumption, Facility, ForecastResult, session_scope
from mediresq.suppliers import supplier_stats

ui.require_login(title="Executive Dashboard", sub="Live supply-resilience picture computed from database records (synthetic dataset)."); ui.sidebar_user()
c = ui.ctx(); snap, ass, bt, asof = c["snap"], c["ass"], c["bt"], c["asof"]
with session_scope() as s:
    k = dashboard_kpis(s, snap, ass, bt)
    sup = supplier_stats(s, asof)
    hid = [f.id for f in s.query(Facility).filter_by(type="Hospital")]
    cons = pd.DataFrame(s.query(Consumption.date, Consumption.quantity).filter(Consumption.facility_id.in_(hid), Consumption.date >= asof - timedelta(days=90)).all(), columns=["date", "q"])
    fc = pd.DataFrame(s.query(ForecastResult.date, ForecastResult.yhat, ForecastResult.lo, ForecastResult.hi).filter(ForecastResult.facility_id.in_(hid)).all(), columns=["date", "yhat", "lo", "hi"])
    alerts = pd.DataFrame([dict(severity=a.severity, type=a.type, message=a.message, status=a.status, updated=a.updated_at) for a in s.query(Alert).filter(Alert.status == "Open").order_by(Alert.updated_at.desc()).limit(200)])
    acts = pd.DataFrame([dict(time=a.ts, user=a.user, action=a.action, details=a.details[:90]) for a in s.query(AuditLog).order_by(AuditLog.ts.desc()).limit(8)])
ui.kpi_row([("Total medicines", f"{k['medicines']}", "active lines", "info", "views/inventory.py"), ("Hospitals / facilities", f"{k['facilities']}", "demand points", "info", "views/logistics.py"), ("Warehouses", f"{k['warehouses']}", "supply nodes", "info", "views/logistics.py"),
            ("Inventory value", f"\u20b9{k['inventory_value'] / 1e5:,.1f} L", "usable stock, synthetic costs", "info", "views/inventory.py"), ("Critical stock alerts", f"{k['critical_alerts']}", "open, severity Critical", "bad" if k["critical_alerts"] else "good", "views/alerts.py")])
st.write("")
ui.kpi_row([("Predicted stockouts", f"{k['predicted_stockouts']}", "within 14 days", "warn", "views/stockout.py"), ("Near-expiry batches", f"{k['near_expiry']}", f"1-90 d \u00b7 {k['expired_batches']} already expired", "warn", "views/batches.py"),
            ("Supplier risks", f"{k['supplier_risks']}", "high-risk suppliers", "bad" if k["supplier_risks"] else "good", "views/suppliers.py"), ("Pending decisions", f"{k['pending']}", "awaiting human approval", "info", "views/approvals.py"),
            ("Supply resilience", f"{k['resilience']['index']:.0f}/100", "heuristic composite index", "good" if k["resilience"]["index"] >= 75 else "warn", "views/analytics.py")])
st.write("")
a, b = st.columns([1.6, 1])
with a:
    d = cons.groupby("date").q.sum().reset_index()
    d["date"] = pd.to_datetime(d["date"])
    f = fc.groupby("date")[["yhat", "lo", "hi"]].sum().reset_index(); f["date"] = pd.to_datetime(f["date"])
    fig = go.Figure()
    fig.add_scatter(x=d.date, y=d.q, name="Actual demand", line=dict(color=ui.NAVY, width=2))
    fig.add_scatter(x=f.date, y=f.hi, line=dict(width=0), showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=f.date, y=f.lo, fill="tonexty", fillcolor="rgba(34,211,238,.2)", line=dict(width=0), name="Forecast range (empirical 10-90%)")
    fig.add_scatter(x=f.date, y=f.yhat, name="Forecast", line=dict(color=ui.CYAN, width=2.5, dash="dash"))
    st.plotly_chart(ui.style_fig(fig.update_layout(title="Medicine demand trend - all hospitals (units/day)"), 340), **ui.W)
with b:
    g = go.Figure(go.Indicator(mode="gauge+number", value=k["resilience"]["index"], number={"suffix": "/100"}, title={"text": "Supply Resilience Indicator"},
                               gauge=dict(axis=dict(range=[0, 100]), bar=dict(color=ui.BLUE), steps=[dict(range=[0, 50], color="#fee2e2"), dict(range=[50, 75], color="#fef3c7"), dict(range=[75, 100], color="#d1fae5")])))
    st.plotly_chart(ui.style_fig(g, 250, False), **ui.W)
    comp = k["resilience"]["components"]
    st.caption("Heuristic: 35% coverage health, 25% supplier on-time, 20% critical-medicine protection, 10% expiry health, 10% shipment reliability. " +
               " | ".join(f"{n.replace('_', ' ')} {v:.0%}" for n, v in comp.items()))
r1, r2, r3 = st.columns(3)
fr = ass[ass.fac_type == "Hospital"].groupby(["facility", "risk_level"]).size().reset_index(name="n")
r1.plotly_chart(ui.style_fig(px.bar(fr, x="facility", y="n", color="risk_level", color_discrete_map=ui.SEV_COLORS, title="Stockout risk by facility", category_orders={"risk_level": ["Critical", "High", "Medium", "Low"]}), 330), **ui.W)
ev = bt[bt.status == "Available"].groupby("bucket").value.sum().reindex(["Expired", "1-30 d", "31-60 d", "61-90 d", ">90 d"]).fillna(0).reset_index()
r2.plotly_chart(ui.style_fig(px.bar(ev, x="bucket", y="value", title="Expiry exposure (INR value)", color="bucket", color_discrete_sequence=["#dc2626", "#f59e0b", "#fbbf24", "#60a5fa", "#10b981"]), 330, False), **ui.W)
r3.plotly_chart(ui.style_fig(px.bar(sup.sort_values("reliability"), x="reliability", y="supplier", orientation="h", title="Supplier reliability score", color="risk", color_discrete_map=ui.SEV_COLORS), 330), **ui.W)
r4, r5 = st.columns(2)
fv = ass.groupby(["facility", "fac_type"]).agg(value=("inventory_value", "sum"), doi=("days_of_inventory", "median")).reset_index()
r4.plotly_chart(ui.style_fig(px.bar(fv, x="facility", y="value", color="fac_type", title="Facility-level inventory value (INR)", color_discrete_sequence=[ui.BLUE, ui.CYAN]), 330), **ui.W)
av = ass[ass.fac_type == "Hospital"].groupby("facility").days_of_inventory.median().reset_index()
r5.plotly_chart(ui.style_fig(px.bar(av, x="facility", y="days_of_inventory", title="Inventory availability - median days of cover (hospitals)", color_discrete_sequence=[ui.NAVY]), 330, False), **ui.W)
ui.section("Alerts & recent activity")
x, y = st.columns([1.4, 1])
with x:
    if not alerts.empty:
        alerts["order"] = alerts.severity.map({"Critical": 0, "High": 1, "Medium": 2, "Low": 3})
        ui.show_df(alerts.sort_values(["order", "updated"], ascending=[True, False]).head(12), hide=["order", "status"], height=320)
with y:
    ui.show_df(acts, height=320)
ui.section("Facility exposure ranking")
ui.show_df(facility_risk(ass[ass.fac_type == "Hospital"]))
