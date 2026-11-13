import pandas as pd
import streamlit as st
from datetime import date
from mediresq import ui, inventory as inv
from mediresq.db import Facility, InventoryPolicy, Medicine, StockMovement, Supplier, session_scope

u = ui.require_login(title="Medicine Inventory Management", sub="Stock monitoring, policies, CRUD and inventory movements."); ui.sidebar_user()
c = ui.ctx(); ass = c["ass"]
t1, t2, t3, t4 = st.tabs(["Stock monitor", "Medicine master (CRUD)", "Min / Max policy", "Movements"])
with t1:
    f1, f2, f3, f4 = st.columns(4)
    fac = f1.multiselect("Facility", sorted(ass.facility.unique())); q = f2.text_input("Search medicine"); rl = f3.multiselect("Risk level", ["Critical", "High", "Medium", "Low"])
    only = f4.selectbox("Flag", ["All", "Below minimum", "Overstock"])
    d = ass.copy()
    if fac: d = d[d.facility.isin(fac)]
    if q: d = d[d.medicine.str.contains(q, case=False)]
    if rl: d = d[d.risk_level.isin(rl)]
    if only == "Below minimum": d = d[d.below_min]
    if only == "Overstock": d = d[d.overstock]
    ui.kpi_row([("Rows", f"{len(d):,}", "medicine x facility", "info"), ("Usable value", f"\u20b9{d.inventory_value.sum() / 1e5:,.1f} L", "synthetic unit cost", "info"),
                ("Below minimum", f"{int(d.below_min.sum())}", "", "warn"), ("Overstock", f"{int(d.overstock.sum())}", "", "info")])
    st.write("")
    ui.show_df(inv.stock_overview(d).sort_values("days_of_inventory"), height=470)
    st.download_button("Download CSV", d.to_csv(index=False).encode(), "inventory_snapshot.csv", "text/csv")
with t2:
    with session_scope() as s:
        meds = pd.DataFrame([dict(id=m.id, code=m.code, name=m.name, category=m.category, unit=m.unit, unit_cost=m.unit_cost, criticality=m.criticality, cold_chain=m.cold_chain,
                                  shelf_life_days=m.shelf_life_days, active=m.active) for m in s.query(Medicine).all()])
        sups = {x.id: x.name for x in s.query(Supplier)}
    ui.show_df(meds.drop(columns=["id"]), height=280)
    if not ui.role_can("inventory_edit"):
        st.info("Read-only: your role cannot edit inventory.")
    else:
        cA, cB = st.columns(2)
        with cA.form("add_med", clear_on_submit=True):
            st.markdown("**Add medicine**")
            code = st.text_input("Code"); name = st.text_input("Name"); cat = st.text_input("Category", "General"); unit = st.text_input("Unit", "tablet")
            cost = st.number_input("Unit cost (INR)", 0.0, 100000.0, 1.0); crit = st.select_slider("Criticality (3 = life-saving)", [1, 2, 3], 2)
            cold = st.checkbox("Cold chain"); shelf = st.number_input("Shelf life (days)", 30, 3650, 720)
            sp = st.selectbox("Primary supplier", list(sups), format_func=lambda i: sups[i])
            if st.form_submit_button("Add medicine", type="primary"):
                try:
                    with session_scope() as s:
                        inv.add_medicine(s, u["username"], dict(code=code, name=name, category=cat, unit=unit, unit_cost=cost, criticality=crit, cold_chain=cold, shelf_life_days=shelf, primary_supplier_id=sp))
                    ui.invalidate(); ui.flash("Medicine added.")
                except Exception as e:
                    st.error(str(e))
        with cB.form("edit_med"):
            st.markdown("**Edit / delete medicine**")
            mid = st.selectbox("Medicine", meds.id.tolist(), format_func=lambda i: meds.set_index("id").loc[i, "name"])
            row = meds.set_index("id").loc[mid]
            nn = st.text_input("Name", row["name"]); nc = st.number_input("Unit cost (INR)", 0.0, 100000.0, float(row.unit_cost)); ncr = st.select_slider("Criticality", [1, 2, 3], int(row.criticality))
            b1, b2 = st.columns(2)
            if b1.form_submit_button("Save changes", type="primary"):
                try:
                    with session_scope() as s: inv.update_medicine(s, u["username"], int(mid), dict(name=nn, unit_cost=nc, criticality=ncr))
                    ui.invalidate(); ui.flash("Updated.")
                except Exception as e: st.error(str(e))
            if b2.form_submit_button("Delete"):
                if not ui.role_can("inventory_delete"): st.error("Your role cannot delete records.")
                else:
                    with session_scope() as s: msg = inv.delete_medicine(s, u["username"], int(mid))
                    ui.invalidate(); ui.flash(f"Medicine {msg}.")
with t3:
    with session_scope() as s:
        pol = pd.DataFrame([dict(medicine=m.name, facility=f.name, mid=m.id, fid=f.id, min_stock=p.min_stock, max_stock=p.max_stock) for p, m, f in
                            s.query(InventoryPolicy, Medicine, Facility).join(Medicine, Medicine.id == InventoryPolicy.medicine_id).join(Facility, Facility.id == InventoryPolicy.facility_id)])
    m = ass[["med_id", "fac_id", "safety_stock", "reorder_point", "avg_daily"]]
    pol = pol.merge(m, left_on=["mid", "fid"], right_on=["med_id", "fac_id"])
    ui.show_df(pol[["medicine", "facility", "min_stock", "max_stock", "avg_daily", "safety_stock", "reorder_point"]], height=300)
    st.caption("Safety stock and reorder point are computed from forecast demand, forecast error and supplier lead time; min/max are editable policy values.")
    if ui.role_can("inventory_edit"):
        with st.form("pol"):
            ms = st.selectbox("Medicine", sorted(pol.medicine.unique())); fs = st.selectbox("Facility", sorted(pol.facility.unique()))
            mn = st.number_input("Min stock", 0, 10**7, 0); mx = st.number_input("Max stock", 0, 10**7, 1000)
            if st.form_submit_button("Update policy", type="primary"):
                r = pol[(pol.medicine == ms) & (pol.facility == fs)].iloc[0]
                try:
                    with session_scope() as s: inv.set_policy(s, u["username"], int(r.mid), int(r.fid), int(mn), int(mx))
                    ui.invalidate(); ui.flash("Policy updated.")
                except Exception as e: st.error(str(e))
with t4:
    with session_scope() as s:
        mv = pd.DataFrame([dict(date=x.date, medicine=m.name, facility=f.name, type=x.type, quantity=x.quantity, reference=x.reference, user=x.user) for x, m, f in
                           s.query(StockMovement, Medicine, Facility).join(Medicine, Medicine.id == StockMovement.medicine_id).join(Facility, Facility.id == StockMovement.facility_id).order_by(StockMovement.id.desc()).limit(500)])
    ui.show_df(mv, height=420)
