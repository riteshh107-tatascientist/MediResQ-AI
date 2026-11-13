import plotly.express as px
import streamlit as st
from mediresq import ui
from mediresq.analytics import advanced_metrics
from mediresq.db import session_scope
from mediresq.policy_sim import run_policy_comparison

ui.require_login(title="Advanced Analytics", sub="Forecast accuracy, availability, fulfilment, turnover, wastage, supplier performance and controlled policy simulation."); ui.sidebar_user()
c = ui.ctx(); snap, ass, bt, asof = c["snap"], c["ass"], c["bt"], c["asof"]
with session_scope() as s: m = advanced_metrics(s, snap, ass, bt)
ui.kpi_row([("Forecast WAPE (selected)", f"{m['forecast_wape_selected']:.1%}", "hold-out, mean of 110 series", "info"), ("MAE / RMSE", f"{m['forecast_mae_selected']:.1f} / {m['forecast_rmse_selected']:.1f}", "units/day", "info"),
            ("Stock availability", f"{m['stock_availability']:.0%}", "hospital series with usable stock", "good"), ("Demand fulfilment (14 d)", f"{m['demand_fulfilment_14d']:.1%}", "projected, scheduled inbound only", "info"), ("Stockout-risk series", f"{m['stockout_risk_series']}", "\u2264 14 days", "warn")])
st.write("")
ui.kpi_row([("Inventory turnover", f"{m['inventory_turnover']:.1f}x", "annual demand value / current hospital stock value", "info"), ("Expired stock on record", f"\u20b9{m['expired_value']:,.0f}", "", "bad"), ("Wastage risk", f"\u20b9{m['wastage_risk_value']:,.0f}", "FEFO consumption shortfall", "warn"),
            ("Supplier on-time", f"{m['supplier_otd']:.0%}", f"lead-time \u03c3 \u2248 {m['lead_time_variability']:.1f} d", "info"), ("Disruption detection", f"{m['detection_time_days']:.1f} d", f"mean over {m['detection_events']} simulated events", "info")])
st.caption(f"Latest recovery plan cost: \u20b9{m['recovery_plan_cost']:,.0f}. Forecast accuracy is reported as WAPE/MAE/RMSE; no accuracy % is claimed beyond what the backtests compute.")
b = m["baseline_wape"]
import pandas as pd
st.plotly_chart(ui.style_fig(px.bar(pd.DataFrame({"model": list(b), "WAPE": list(b.values())}).sort_values("WAPE"), x="model", y="WAPE", title="Mean WAPE by model (lower is better)", color="model"), 300, False), **ui.W)
ui.section("Controlled policy simulation: static vs intelligent")
ui.sim_banner("Monte-Carlo simulation on synthetic data. Both policies face identical random supplier delays and demand surges. Not real hospital outcomes.")
st.markdown("**Static policy:** fixed reorder point from 90-day average and promised lead time, order up to 30 days. **Intelligent policy:** adaptive reorder point (EWMA demand, supplier lead-time variability, criticality-based service level), lateral transfers between hospitals and expedited replenishment on imminent stockout.")
n = st.slider("Monte-Carlo runs", 3, 20, 8)
if st.button("Run policy simulation", type="primary"):
    with st.spinner("Simulating 90 days x 22 medicines x 5 hospitals..."):
        with session_scope() as s: st.session_state["pol"] = run_policy_comparison(s, asof, 90, n)
r = st.session_state.get("pol")
if r:
    sm = r["summary"].copy(); ui.show_df(sm.style.format({"fill_rate": "{:.2%}", "fill_sd": "{:.2%}", "critical_fill_rate": "{:.2%}", "stockout_days": "{:.0f}", "avg_inventory_value": "\u20b9{:,.0f}", "orders": "{:.0f}", "transfers": "{:.1f}", "expedites": "{:.0f}", "expedite_premium": "\u20b9{:,.0f}"}))
    x, y = st.columns(2)
    x.plotly_chart(ui.style_fig(px.box(r["runs"], x="policy", y="fill_rate", color="policy", points="all", title="Fill rate across Monte-Carlo runs"), 320, False), **ui.W)
    y.plotly_chart(ui.style_fig(px.box(r["runs"], x="policy", y="stockout_days", color="policy", points="all", title="Hospital-medicine stockout days"), 320, False), **ui.W)
    st.caption(f"{r['n_runs']} runs x {r['sim_days']} simulated days. Compare the inventory-value and cost columns too: the intelligent policy buys service with extra orders/expedites. Results depend on the synthetic generator's assumptions.")
