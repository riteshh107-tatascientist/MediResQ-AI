import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import timedelta
from mediresq import config, forecasting as F, ui
from mediresq.db import Consumption, Facility, ForecastResult, ModelMetric, session_scope

u = ui.require_login(title="AI Demand Forecasting", sub="Five models, chronological hold-out backtest, MAE / RMSE / WAPE. Metrics are computed, never invented."); ui.sidebar_user()
c = ui.ctx(); snap, asof = c["snap"], c["asof"]
hosp = {f["id"]: f for f in snap.fac.values() if f["type"] == "Hospital"}
a, b, h = st.columns([1.2, 1.4, .8])
fid = a.selectbox("Hospital", list(hosp), format_func=lambda i: hosp[i]["name"])
mid = b.selectbox("Medicine", list(snap.med), format_func=lambda i: snap.med[i]["name"])
hz = h.radio("Horizon", [7, 14, 30], index=2, horizontal=True)
with session_scope() as s:
    raw = F.load_series(s, mid, fid, asof)
    clean, rep = F.clean_series(raw, asof)
    fc = pd.DataFrame([(r.date, r.yhat, r.lo, r.hi, r.model) for r in s.query(ForecastResult).filter_by(medicine_id=mid, facility_id=fid).order_by(ForecastResult.date)], columns=["date", "yhat", "lo", "hi", "model"])
    mt = pd.DataFrame([(m.model, m.mae, m.rmse, m.wape, m.selected) for m in s.query(ModelMetric).filter_by(medicine_id=mid, facility_id=fid)], columns=["Model", "MAE", "RMSE", "WAPE", "Selected"])
    allm = F.metric_table(s)
if fc.empty:
    st.warning("No forecasts stored yet. Use the button below to run them."); fcd = fc
else:
    fcd = fc.head(hz)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Selected model", fc.model.iloc[0]); k2.metric(f"Forecast total ({hz} d)", f"{fcd.yhat.sum():,.0f}"); k3.metric("Avg / day", f"{fcd.yhat.mean():,.1f}"); k4.metric("Range (10-90%)", f"{fcd.lo.sum():,.0f} - {fcd.hi.sum():,.0f}")
    hist = clean.iloc[-90:]
    fig = go.Figure()
    fig.add_scatter(x=hist.index, y=hist.values, name="History (cleaned)", line=dict(color=ui.NAVY, width=2))
    fig.add_scatter(x=pd.to_datetime(fcd.date), y=fcd.hi, line=dict(width=0), showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=pd.to_datetime(fcd.date), y=fcd.lo, fill="tonexty", fillcolor="rgba(34,211,238,.22)", line=dict(width=0), name="Empirical 10-90% range")
    fig.add_scatter(x=pd.to_datetime(fcd.date), y=fcd.yhat, name="Forecast", line=dict(color=ui.CYAN, width=3, dash="dash"))
    st.plotly_chart(ui.style_fig(fig.update_layout(title=f"{snap.med[mid]['name']} @ {hosp[fid]['name']}"), 360), **ui.W)
st.markdown(f"**7 / 14 / 30-day forecast totals:** " + " | ".join(f"{n}d: {fc.head(n).yhat.sum():,.0f}" for n in (7, 14, 30)) if not fc.empty else "")
t1, t2, t3, t4 = st.tabs(["Model comparison", "Network-wide evaluation", "Seasonality & data quality", "Run / explain"])
with t1:
    if not mt.empty:
        base = mt[mt.Model.isin(["Moving Average", "Seasonal Naive"])].WAPE.min(); sel = mt[mt.Selected].iloc[0]
        ui.show_df(mt.sort_values("WAPE").style.format({"MAE": "{:.2f}", "RMSE": "{:.2f}", "WAPE": "{:.1%}"}).apply(lambda r: ["background-color:#d1fae5" if r.Selected else "" for _ in r], axis=1))
        st.caption(f"Hold-out = last 28 days (chronological split; no shuffling). Selected = lowest WAPE (baselines win ties). Best baseline WAPE {base:.1%} vs selected {sel.WAPE:.1%}. Intervals use the selected model's hold-out residual quantiles.")
with t2:
    if not allm.empty:
        g = F.model_summary(allm)
        ui.show_df(g.style.format({"MAE": "{:.2f}", "RMSE": "{:.2f}", "WAPE": "{:.1%}"}))
        st.plotly_chart(ui.style_fig(px.bar(g, x="model", y="WAPE", title="Mean WAPE by model across all 110 hospital series (lower is better)", color="model"), 320, False), **ui.W)
        st.caption("WAPE = sum|error| / sum(actual). Zero-demand days are handled because WAPE aggregates over the window rather than dividing per day.")
with t3:
    sa = F.seasonality_analysis(clean)
    d = pd.DataFrame({"Day": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "Index": [sa["dow_index"][i] for i in range(7)]})
    x, y = st.columns(2)
    x.plotly_chart(ui.style_fig(px.bar(d, x="Day", y="Index", title="Day-of-week seasonality index (1.0 = average)"), 300, False), **ui.W)
    mo = pd.DataFrame({"Month": list(sa["month_index"]), "Index": list(sa["month_index"].values())})
    y.plotly_chart(ui.style_fig(px.line(mo, x="Month", y="Index", markers=True, title="Monthly seasonality index"), 300, False), **ui.W)
    ui.kpi_row([("Days in history", f"{rep['days']}", "", "info"), ("Missing days imputed", f"{rep['missing_imputed']}", "same-weekday median", "info"), ("True zero-demand days", f"{rep['zero_days']}", "kept as zeros", "info"), ("Outliers winsorised", f"{rep['outliers_capped']}", f"cap = {rep['outlier_cap']:.0f}/day (median+6 MAD)", "warn")])
with t4:
    path = config.MODEL_DIR / f"m{mid}_f{fid}.joblib"
    if path.exists():
        m = joblib.load(path)
        if hasattr(m, "feature_importances_"):
            names = ["lag1", "lag2", "lag3", "lag7", "lag14", "mean7", "mean28", "weekday", "annual_sin", "annual_cos"]
            st.plotly_chart(ui.style_fig(px.bar(pd.DataFrame({"feature": names, "importance": m.feature_importances_}).sort_values("importance"), x="importance", y="feature", orientation="h", title="Explainability: feature importance of the selected ML model"), 320, False), **ui.W)
    else:
        st.caption("A statistical/baseline model was selected for this series - no ML feature importance to show.")
    if ui.role_can("run_forecast"):
        fast = st.checkbox("Fast mode (baselines + Holt-Winters only)")
        if st.button("Re-run all forecasts & backtests", type="primary"):
            bar = st.progress(0.0, "Backtesting 110 series...")
            with session_scope() as s:
                F.run_all(s, asof, models=["Moving Average", "Seasonal Naive", "Exponential Smoothing"] if fast else None, progress=lambda p: bar.progress(min(p, 1.0)))
                from mediresq.alerts import refresh_alerts
            with session_scope() as s: refresh_alerts(s, asof)
            ui.invalidate(); ui.flash("Forecasts and alerts refreshed.")
