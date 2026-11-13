import pandas as pd
import streamlit as st
from mediresq import auth, config, datagen, ui
from mediresq.alerts import refresh_alerts
from mediresq.db import User, get_engine, session_scope
from mediresq.planner import generate_plan
from mediresq.uploads import import_rows, validate_csv

u = ui.require_login(title="Admin & Data", sub="Users, safe CSV upload, data-quality checks and demo control."); ui.sidebar_user()
c = ui.ctx(); asof = c["asof"]
t1, t2, t3, t4, t5 = st.tabs(["Demo guide", "Users", "CSV upload", "Data quality", "Demo control"])
with t1:
    st.markdown("""### 5-minute judge walkthrough
1. **Home** - problem, solution, workflow. Click *Enter Command Center* and sign in as `manager_demo`.
2. **Executive Dashboard** - all KPIs come from the database; note the critical alerts and resilience indicator.
3. **Stockout Early Warning** - open *Ceftriaxone @ Hospital A*: stock covers ~3 days, supplier shipment delayed 7 days. Read the *Why*.
4. **Redistribution Optimizer** - OR-Tools proposes the cheapest feasible transfers (FEFO batches, expiry-safe, reserve-protected). Change the cost multiplier or block a facility.
5. **What-If Simulator** - choose *Demo: 7-day supplier delay*; compare Baseline / Disrupted / Recovered.
6. **Approvals & Audit** - approve / modify / reject; see the audit entry.
7. **Advanced Analytics** - run the static-vs-intelligent policy simulation (labelled simulated).
8. **Assistant** - ask *Which facility is at greatest risk?*""")
with t2:
    if not ui.role_can("manage_users"): st.info("Administrator only.")
    else:
        with session_scope() as s:
            us = pd.DataFrame([dict(username=x.username, name=x.full_name, role=x.role, active=x.active, created=x.created_at) for x in s.query(User)])
        ui.show_df(us)
        with st.form("nu", clear_on_submit=True):
            a, b, d, e = st.columns(4); nu = a.text_input("Username"); nn = b.text_input("Full name"); npw = d.text_input("Password", type="password"); nr = e.selectbox("Role", config.ROLES)
            if st.form_submit_button("Create user", type="primary"):
                try:
                    with session_scope() as s:
                        auth.create_user(s, nu, nn, npw, nr); auth.audit(s, u["username"], "USER_CREATE", "user", nu, nr)
                    ui.flash("User created.")
                except Exception as ex: st.error(str(ex))
        with st.form("du"):
            who = st.selectbox("Deactivate / reactivate", us.username.tolist()); act = st.radio("Set", ["Deactivate", "Reactivate"], horizontal=True)
            if st.form_submit_button("Apply") and who != u["username"]:
                with session_scope() as s:
                    s.query(User).filter_by(username=who).update({"active": act == "Reactivate"}); auth.audit(s, u["username"], "USER_" + act.upper(), "user", who)
                ui.flash("Updated.")
with t3:
    if not ui.role_can("upload"): st.info("Administrator or Warehouse Manager only.")
    else:
        kind = st.selectbox("Upload type", ["consumption", "batches"]); st.caption("Required columns: " + ", ".join(__import__("mediresq.uploads", fromlist=["SPECS"]).SPECS[kind]) + f" (max {config.MAX_UPLOAD_MB} MB, dates YYYY-MM-DD).")
        f = st.file_uploader("CSV file", type=["csv"])
        if f is not None:
            with session_scope() as s:
                df, errs = validate_csv(f.getvalue(), kind, s)
            if errs: [st.error(e) for e in errs]
            else:
                st.success(f"Validation passed: {len(df)} rows."); ui.show_df(df.head(20))
                if st.button("Import validated rows", type="primary"):
                    with session_scope() as s: n = import_rows(s, df, kind, u["username"])
                    ui.invalidate(); st.success(f"{n} rows imported.")
with t4:
    from sqlalchemy import text
    eng = get_engine()
    with eng.connect() as con:
        fk = con.execute(text("PRAGMA foreign_key_check")).fetchall() if eng.url.get_backend_name() == "sqlite" else []
        counts = {t: con.execute(text(f"select count(*) from {t}")).scalar() for t in ["facilities", "suppliers", "medicines", "batches", "consumption", "purchase_orders", "shipments", "stock_movements", "forecasts", "alerts", "recommendations", "audit_log"]}
        neg = con.execute(text("select count(*) from batches where quantity<0")).scalar() + con.execute(text("select count(*) from consumption where quantity<0")).scalar()
    ui.kpi_row([("Foreign-key violations", f"{len(fk)}", "PRAGMA foreign_key_check", "good" if not fk else "bad"), ("Negative quantities", f"{neg}", "", "good" if not neg else "bad"), ("Tables checked", f"{len(counts)}", "", "info")])
    ui.show_df(pd.DataFrame(counts.items(), columns=["table", "rows"]))
with t5:
    if not ui.role_can("reset_demo"): st.info("Administrator only.")
    else:
        st.warning("Re-seeding deletes all data and regenerates the synthetic dataset, forecasts, alerts and a fresh recovery plan (about 2-4 minutes).")
        asof_in = st.date_input("Dataset reference date", asof); conf = st.checkbox("I understand this resets the demo database")
        if st.button("Re-seed demo database", type="primary", disabled=not conf):
            from mediresq import seed
            bar = st.progress(0.0, "Seeding...")
            seed.seed(asof=asof_in, progress=lambda p: bar.progress(min(p, 1.0)))
            st.session_state.pop("user", None); ui.invalidate(); st.cache_resource.clear(); ui.flash("Done - please sign in again.")
        if st.button("Refresh alerts + regenerate recovery plan"):
            with session_scope() as s: refresh_alerts(s, asof); generate_plan(s, asof, u["username"])
            ui.invalidate(); st.success("Refreshed.")
