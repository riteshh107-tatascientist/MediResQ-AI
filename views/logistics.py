import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import timedelta
from mediresq import ui
from mediresq.alerts import refresh_alerts
from mediresq.auth import audit
from mediresq.db import DisruptionEvent, Shipment, session_scope

u = ui.require_login(title="Logistics & Disruption Monitoring", sub="Shipments, delays and clearly-labelled simulated disruption events."); ui.sidebar_user()
c = ui.ctx(); snap, asof = c["snap"], c["asof"]
with session_scope() as s:
    sh = pd.DataFrame([dict(id=x.id, shipment=x.ship_no, origin=x.origin_name, destination=snap.fac[x.destination_id]["name"], dest_id=x.destination_id, medicine=snap.med[x.medicine_id]["name"], quantity=x.quantity,
                            dispatched=x.dispatch_date, expected=x.expected_arrival, actual=x.actual_arrival, status=x.status, delay_days=x.delay_days, mode=x.transport_mode, supplier_id=x.supplier_id, origin_id=x.origin_id) for x in s.query(Shipment).all()])
    ev = pd.DataFrame([dict(type=e.type, description=e.description, start=e.start_date, end=e.end_date, severity=e.severity, detected=e.detected_date, simulated=e.is_simulated) for e in s.query(DisruptionEvent).order_by(DisruptionEvent.start_date.desc())])
open_ = sh[sh.status.isin(["In Transit", "Delayed"])]
dl = sh[sh.status == "Delivered"].copy(); dl["late"] = (pd.to_datetime(dl.actual) - pd.to_datetime(dl.expected)).dt.days.clip(lower=0)
ui.kpi_row([("Open shipments", f"{len(open_)}", "in transit / delayed", "info"), ("Delayed now", f"{int((open_.delay_days > 0).sum())}", f"{open_[open_.delay_days > 0].quantity.sum():,} units", "warn"),
            ("Historical on-time", f"{(dl.late == 0).mean():.0%}", f"{len(dl)} delivered", "info"), ("Mean delay (late ones)", f"{dl[dl.late > 0].late.mean():.1f} d", "", "info"), ("Disruption events", f"{len(ev)}", "all simulated", "warn")])
t1, t2, t3 = st.tabs(["Shipments", "Network map", "Disruption events & simulation"])
with t1:
    ui.show_df(open_[["shipment", "origin", "destination", "medicine", "quantity", "expected", "delay_days", "status", "mode"]].sort_values("delay_days", ascending=False))
    with st.expander("Delivered shipment history"):
        ui.show_df(dl[["shipment", "origin", "destination", "medicine", "quantity", "expected", "actual", "late"]].sort_values("expected", ascending=False).head(200))
with t2:
    fig = go.Figure()
    for r in open_.itertuples():
        d = snap.fac[r.dest_id]
        o = snap.fac.get(r.origin_id) if r.origin_id == r.origin_id and r.origin_id else None
        if o is None: continue
        fig.add_scatter(x=[o["lon"], d["lon"]], y=[o["lat"], d["lat"]], mode="lines", line=dict(color="#dc2626" if r.delay_days else "#0b6bcb", width=2), showlegend=False, hoverinfo="skip")
    for t, col, sym in [("Warehouse", ui.NAVY, "square"), ("Hospital", ui.CYAN, "circle")]:
        f = [x for x in snap.fac.values() if x["type"] == t]
        fig.add_scatter(x=[x["lon"] for x in f], y=[x["lat"] for x in f], mode="markers+text", text=[x["code"] for x in f], textposition="top center", name=t, marker=dict(size=18, color=col, symbol=sym, line=dict(width=2, color="#fff")),
                        hovertext=[x["name"] for x in f])
    st.plotly_chart(ui.style_fig(fig.update_layout(title="Facility network (offline map: longitude / latitude)", xaxis_title="Longitude", yaxis_title="Latitude"), 460), **ui.W)
    st.caption("Red lines = delayed internal transfers. Supplier-origin shipments are listed in the table.")
with t3:
    ui.show_df(ev)
    ui.sim_banner("Injecting a disruption modifies the demo database (shipment delays) so every module reacts. All injected events are labelled SIMULATED. Use Admin > Demo control to reset.")
    if not ui.role_can("run_planner"): st.info("Only Administrators and Supply Chain Managers can inject simulated disruptions.")
    else:
        with st.form("inject"):
            kind = st.selectbox("Disruption type", ["Supplier delay", "Transport disruption", "Warehouse disruption", "Partial delivery", "Sudden demand surge (event only)"])
            days = st.slider("Delay (days)", 1, 10, 3); pct = st.slider("Partial delivery shortfall %", 10, 70, 30)
            sup = st.selectbox("Supplier (for supplier delay)", sorted(snap.sup.supplier)); wh = st.selectbox("Warehouse", [f["name"] for f in snap.fac.values() if f["type"] == "Warehouse"])
            if st.form_submit_button("Inject simulated disruption", type="primary"):
                n = 0
                with session_scope() as s:
                    q = s.query(Shipment).filter(Shipment.status.in_(["In Transit", "Delayed"]))
                    sid = int(snap.sup[snap.sup.supplier == sup].supplier_id.iloc[0]); wid = next(f["id"] for f in snap.fac.values() if f["name"] == wh)
                    for x in q.all():
                        hit = (kind == "Supplier delay" and x.supplier_id == sid) or (kind == "Transport disruption" and x.transport_mode.startswith("Road")) or (kind == "Warehouse disruption" and (x.origin_id == wid or x.destination_id == wid))
                        if hit: x.delay_days += days; x.status = "Delayed"; n += 1
                        if kind == "Partial delivery" and x.supplier_id == sid: x.quantity = int(x.quantity * (1 - pct / 100)); n += 1
                    s.add(DisruptionEvent(type=kind.split(" (")[0], description=f"[SIMULATED] {kind} injected by {u['username']} ({days} d / {pct}%) - {n} shipment(s) affected", supplier_id=sid if "Supplier" in kind or "Partial" in kind else None,
                                          facility_id=wid if "Warehouse" in kind else None, start_date=asof, end_date=asof + timedelta(days=days), severity="High", detected_date=asof, is_simulated=True))
                    audit(s, u["username"], "INJECT_DISRUPTION", "disruption_event", "", f"{kind}; affected {n}")
                with session_scope() as s: refresh_alerts(s, asof)
                ui.invalidate(); ui.flash(f"Simulated disruption injected; {n} shipment(s) affected.")
