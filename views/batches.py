import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import date
from mediresq import ui, inventory as inv
from mediresq.db import Batch, session_scope
from mediresq.expiry import fefo_order, safe_transfers

u = ui.require_login(title="Batch & Expiry Intelligence", sub="Batch-level inventory, FEFO, expiry buckets, wastage risk and safe transfers. Expired / quarantined batches are never recommended."); ui.sidebar_user()
c = ui.ctx(); snap, bt, asof = c["snap"], c["bt"], c["asof"]
live = bt[bt.status == "Available"]
ui.kpi_row([("Expired on record", f"{int((bt.bucket == 'Expired').sum())}", f"\u20b9{bt[bt.bucket == 'Expired'].value.sum():,.0f}", "bad"), ("Expiring \u2264 30 d", f"{int((live.bucket == '1-30 d').sum())}", f"\u20b9{live[live.bucket == '1-30 d'].value.sum():,.0f}", "warn"),
            ("31-60 d", f"{int((live.bucket == '31-60 d').sum())}", f"\u20b9{live[live.bucket == '31-60 d'].value.sum():,.0f}", "warn"), ("61-90 d", f"{int((live.bucket == '61-90 d').sum())}", f"\u20b9{live[live.bucket == '61-90 d'].value.sum():,.0f}", "info"),
            ("Wastage risk (FEFO)", f"\u20b9{bt.wastage_risk_value.sum():,.0f}", "stock unlikely to be consumed before expiry", "warn")])
t1, t2, t3, t4 = st.tabs(["Batch inventory", "FEFO recommendation", "Wastage risk & safe transfers", "Manage batches"])
with t1:
    a, b = st.columns(2)
    bk = a.multiselect("Expiry bucket", ["Expired", "1-30 d", "31-60 d", "61-90 d", ">90 d", "Quarantined"], default=["Expired", "1-30 d", "31-60 d", "61-90 d"])
    fc = b.multiselect("Facility", sorted(bt.facility.unique()))
    d = bt[bt.bucket.isin(bk)]
    if fc: d = d[d.facility.isin(fc)]
    ui.show_df(d[["medicine", "facility", "batch_no", "mfg_date", "expiry_date", "days_to_expiry", "quantity", "value", "bucket", "status", "wastage_risk_qty"]], height=380)
    fig = px.bar(bt.groupby(["bucket", "facility"]).value.sum().reset_index(), x="facility", y="value", color="bucket", title="Expiry exposure by facility (INR)",
                 color_discrete_map={"Expired": "#dc2626", "1-30 d": "#f59e0b", "31-60 d": "#fbbf24", "61-90 d": "#60a5fa", ">90 d": "#10b981", "Quarantined": "#94a3b8"})
    st.plotly_chart(ui.style_fig(fig, 340), **ui.W)
with t2:
    a, b = st.columns(2)
    mname = a.selectbox("Medicine", sorted({m["name"] for m in snap.med.values()})); fname = b.selectbox("Facility", sorted({f["name"] for f in snap.fac.values()}))
    mid = next(m["id"] for m in snap.med.values() if m["name"] == mname); fid = next(f["id"] for f in snap.fac.values() if f["name"] == fname)
    with session_scope() as s:
        fe = fefo_order(s, mid, fid, asof)
    if fe.empty: st.info("No issuable (available, unexpired) batches here.")
    else:
        ui.note("Issue in this order (First-Expired-First-Out). Expired and quarantined batches are excluded.")
        ui.show_df(fe)
with t3:
    st.caption("A batch is 'at wastage risk' when forecast consumption at its location (FEFO) cannot use it before expiry.")
    st_ = safe_transfers(snap, bt)
    if st_.empty: st.success("No safe transfer candidates found.")
    else:
        ui.kpi_row([("Transferable batches", f"{len(st_)}", "", "info"), ("Value that can be saved", f"\u20b9{st_.value_saved.sum():,.0f}", "", "good"), ("Est. transfer cost", f"\u20b9{st_.est_cost.sum():,.0f}", "", "info")])
        st.write(""); ui.show_df(st_, height=340)
    ui.show_df(bt[bt.wastage_risk_qty > 0][["medicine", "facility", "batch_no", "days_to_expiry", "quantity", "wastage_risk_qty", "wastage_risk_value"]].sort_values("wastage_risk_value", ascending=False).head(30))
with t4:
    if not ui.role_can("inventory_edit"): st.info("Read-only for your role.")
    else:
        a, b = st.columns(2)
        with a.form("addb", clear_on_submit=True):
            st.markdown("**Receive new batch**")
            m = st.selectbox("Medicine", list(snap.med), format_func=lambda i: snap.med[i]["name"]); f = st.selectbox("Facility", list(snap.fac), format_func=lambda i: snap.fac[i]["name"])
            no = st.text_input("Batch no"); mf = st.date_input("Manufacturing date", asof); ex = st.date_input("Expiry date", asof.replace(year=asof.year + 2)); q = st.number_input("Quantity", 1, 10**7, 100)
            if st.form_submit_button("Add batch", type="primary"):
                try:
                    with session_scope() as s: inv.add_batch(s, u["username"], dict(medicine_id=m, facility_id=f, batch_no=no, mfg_date=mf, expiry_date=ex, quantity=q))
                    ui.invalidate(); ui.flash("Batch added.")
                except Exception as e: st.error(str(e))
        with b.form("adjb"):
            st.markdown("**Adjust / quarantine / delete**")
            lab = {r.batch_id: f"{r.batch_no} | {r.medicine[:22]} | {r.facility[:18]} | qty {r.quantity}" for r in bt.itertuples()}
            bid = st.selectbox("Batch", list(lab), format_func=lambda i: lab[i]); dlt = st.number_input("Quantity change (+/-)", -10**6, 10**6, 0)
            act = st.radio("Action", ["Adjust quantity", "Write-off (negative)", "Quarantine", "Release from quarantine", "Delete batch"])
            if st.form_submit_button("Apply", type="primary"):
                try:
                    with session_scope() as s:
                        if act == "Adjust quantity": inv.adjust_batch(s, u["username"], int(bid), int(dlt))
                        elif act.startswith("Write-off"): inv.adjust_batch(s, u["username"], int(bid), -abs(int(dlt)), "Write-off")
                        elif act == "Quarantine": inv.set_batch_status(s, u["username"], int(bid), "Quarantined")
                        elif act.startswith("Release"): inv.set_batch_status(s, u["username"], int(bid), "Available")
                        else:
                            if not ui.role_can("inventory_delete"): raise PermissionError("Your role cannot delete batches")
                            inv.delete_batch(s, u["username"], int(bid))
                    ui.invalidate(); ui.flash("Done.")
                except Exception as e: st.error(str(e))
