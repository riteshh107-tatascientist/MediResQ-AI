import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from mediresq import ui
from mediresq.simulator import Scenario, comparison_table, run_scenario

ui.require_login(title="What-If Scenario Simulator", sub="Baseline vs Disrupted vs Recovered - calculated on a copy of the live network; the database is never modified."); ui.sidebar_user()
c = ui.ctx(); snap = c["snap"]
ui.sim_banner()
presets = {"Custom": {}, "Demo: 7-day supplier delay": dict(d=7, sup=["Sanjeevani MedSupply (Synthetic)"]), "Demand surge +30%": dict(inc=30), "Warehouse disruption (Bhopal, 5 d)": dict(wh="Central Medical Warehouse - Bhopal", wd=5),
           "Perfect storm": dict(d=5, inc=20, tc=1.5)}
pre = st.selectbox("Scenario preset", list(presets)); P = presets[pre]
a, b, d = st.columns(3)
with a:
    delay = st.select_slider("Supplier delay (days)", [0, 1, 3, 5, 7, 10], P.get("d", 0)); sups = st.multiselect("Suppliers affected (empty = all)", list(snap.sup.supplier), P.get("sup", []))
with b:
    inc = st.select_slider("Demand increase", [0, 10, 20, 30, 50], P.get("inc", 0)); custom = st.number_input("Custom demand increase % (overrides if > 0)", 0, 200, 0)
    meds = st.multiselect("Medicines (empty = all)", [m["name"] for m in snap.med.values()])
with d:
    whs = ["None"] + [f["name"] for f in snap.fac.values() if f["type"] == "Warehouse"]; wh = st.selectbox("Warehouse disruption", whs, whs.index(P["wh"]) if "wh" in P else 0)
    wd = st.slider("Disruption days", 0, 10, P.get("wd", 0)); tc = st.slider("Transport cost x", 0.5, 3.0, float(P.get("tc", 1.0)), 0.1)
e, f, g, h = st.columns(4)
loss = e.slider("Inventory shortage (stock loss %)", 0, 60, 0); alt = f.checkbox("Alternative replenishment", False); altd = g.slider("Alt. arrival (days)", 1, 7, 3); hz = h.select_slider("Horizon (days)", [7, 14, 21, 30], 14)
if st.button("Run simulation", type="primary"):
    nm = {m["name"]: m["id"] for m in snap.med.values()}; sid = {r.supplier: r.supplier_id for r in snap.sup.itertuples()}; fid = {x["name"]: x["id"] for x in snap.fac.values()}
    sc = Scenario(supplier_delay_days=delay, supplier_ids=[sid[x] for x in sups] or None, demand_increase_pct=float(custom or inc), demand_medicine_ids=[nm[x] for x in meds] or None,
                  warehouse_id=fid.get(wh), warehouse_days=wd, transport_cost_mult=tc, stock_loss_pct=loss, alt_replenishment=alt, alt_days=altd, horizon=hz)
    with st.spinner("Simulating 3 scenarios + optimising recovery..."):
        st.session_state["sim"] = run_scenario(snap, sc)
res = st.session_state.get("sim")
if res:
    st.markdown("**Applied:** " + " \u00b7 ".join(res["description"]))
    tbl = comparison_table(res); ui.show_df(tbl)
    x, y = st.columns(2)
    x.plotly_chart(ui.style_fig(px.bar(tbl, x="Scenario", y="Demand fulfilment %", color="Scenario", title="Demand fulfilment (%)", color_discrete_sequence=["#0b6bcb", "#dc2626", "#10b981"], range_y=[max(0, tbl["Demand fulfilment %"].min() - 5), 100]), 320, False), **ui.W)
    y.plotly_chart(ui.style_fig(px.bar(tbl, x="Scenario", y=["Unmet demand value (INR)", "Recovery cost (INR)", "Expiry wastage (INR)"], barmode="group", title="Cost impact (INR)"), 320), **ui.W)
    fig = go.Figure()
    for k, col in [("Baseline", "#0b6bcb"), ("Disrupted", "#dc2626"), ("Recovered", "#10b981")]:
        fig.add_scatter(x=list(range(len(res[k]["curve"]))), y=res[k]["curve"], name=k, line=dict(color=col, width=3))
    st.plotly_chart(ui.style_fig(fig.update_layout(title="Total hospital inventory over time (units)", xaxis_title="Day"), 320), **ui.W)
    ui.section("Worst affected medicine-hospital pairs (disrupted, before recovery)")
    dd = res["Disrupted"]["detail"].sort_values("unmet", ascending=False).head(10)[["medicine", "facility", "stockout_day", "unmet"]]
    rr = res["Recovered"]["detail"].set_index(["med_id", "fac_id"])
    dd["unmet_after_recovery"] = [round(float(rr.loc[(m, f_), "unmet"]), 1) for m, f_ in res["Disrupted"]["detail"].sort_values("unmet", ascending=False).head(10)[["med_id", "fac_id"]].itertuples(index=False)]
    ui.show_df(dd)
    if not res["plan"]["transfers"].empty:
        with st.expander("Recovery transfers used in the 'Recovered' scenario"):
            ui.show_df(res["plan"]["transfers"][["medicine", "source", "destination", "quantity", "est_cost", "eta_days"]])
    if res["alt"]["units"]: st.caption(f"Alternative replenishment: {res['alt']['units']:,.0f} units, premium cost \u20b9{res['alt']['cost']:,.0f} (15% over unit cost, synthetic assumption).")
    st.caption("Recovered = disrupted state + optimised redistribution (+ alternative replenishment if enabled). No further reorders beyond already-scheduled inbound shipments are modelled.")
