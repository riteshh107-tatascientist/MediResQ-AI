import pandas as pd
import plotly.express as px
import streamlit as st
from mediresq import ui
from mediresq.db import PurchaseOrder, Supplier, session_scope
from mediresq.suppliers import supplier_stats

ui.require_login(title="Supplier Intelligence", sub="Lead time, delay frequency, fulfilment and a transparent reliability score."); ui.sidebar_user()
c = ui.ctx(); asof = c["asof"]
with session_scope() as s:
    st_ = supplier_stats(s, asof)
    po = pd.DataFrame([dict(supplier_id=p.supplier_id, supplier=p.supplier_id, order=p.order_date, promised=p.promised_date, actual=p.actual_date, qty=p.quantity, delivered=p.delivered_qty) for p in s.query(PurchaseOrder).filter(PurchaseOrder.actual_date.isnot(None))])
    names = {x.id: x.name for x in s.query(Supplier)}
po["supplier"] = po.supplier_id.map(names)
po["lead"] = (pd.to_datetime(po.actual) - pd.to_datetime(po.order)).dt.days; po["delay"] = (pd.to_datetime(po.actual) - pd.to_datetime(po.promised)).dt.days
ui.kpi_row([("Suppliers", f"{len(st_)}", "synthetic", "info"), ("Mean on-time rate", f"{st_.on_time_rate.mean():.0%}", "actual <= promised", "info"), ("Mean fill rate", f"{st_.fill_rate.mean():.0%}", "delivered / ordered", "info"),
            ("High-risk suppliers", f"{int((st_.risk == 'High').sum())}", "", "bad" if (st_.risk == "High").any() else "good"), ("Active delay events", f"{int((st_.active_delay_days > 0).sum())}", "", "warn")])
st.write("")
ui.show_df(st_[["supplier", "city", "n_orders", "promised_lead", "avg_lead", "lead_std", "on_time_rate", "delay_freq", "avg_delay_late", "fill_rate", "reliability", "risk", "active_delay_days"]].style.format(
    {"avg_lead": "{:.1f}", "lead_std": "{:.2f}", "on_time_rate": "{:.0%}", "delay_freq": "{:.0%}", "avg_delay_late": "{:.1f}", "fill_rate": "{:.0%}", "reliability": "{:.0f}"}))
st.caption("Reliability score (heuristic) = 100 x (0.45 x on-time rate + 0.30 x fill rate + 0.25 x (1 - mean delay / promised lead, capped)). Risk: High if score < 75 or an active delay event exists; Medium if < 88.")
a, b = st.columns(2)
a.plotly_chart(ui.style_fig(px.scatter(st_, x="lead_cv", y="on_time_rate", size="n_orders", color="risk", text="code", color_discrete_map=ui.SEV_COLORS, title="Lead-time variability vs on-time rate"), 340), **ui.W)
b.plotly_chart(ui.style_fig(px.box(po, x="supplier", y="lead", title="Historical lead time (days)"), 340, False), **ui.W)
po["month"] = pd.to_datetime(po.actual).dt.to_period("M").astype(str)
m = po.assign(on_time=(po.delay <= 0)).groupby(["month"]).on_time.mean().reset_index()
st.plotly_chart(ui.style_fig(px.line(m, x="month", y="on_time", markers=True, title="Network on-time delivery rate by month"), 300, False), **ui.W)
