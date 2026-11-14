import streamlit as st
from mediresq import config, ui
from mediresq.db import session_scope

ui.ensure_db(); ui.inject_css(); ui.sidebar_user()
ui.hero()
c1, c2, c3 = st.columns([1, 1.2, 1])
with c2:
    if st.button("Enter Command Center  \u2192", type="primary", **ui.W, key="enter"):
        st.switch_page("views/dashboard.py")
st.caption("Sign in with a local demo account on the next screen. All data is synthetic and clearly labelled.")

# --- live proof strip (real numbers from the database) -------------------------------------------------------
try:
    c = ui.ctx(); ass = c["ass"]; snap = c["snap"]
    hosp = ass[ass.fac_type == "Hospital"]
    ui.kpi_row([("Medicines tracked", f"{len(snap.med)}", "essential list (synthetic)", "info", "views/inventory.py"), ("Facilities", f"{len(snap.fac)}", "3 warehouses + 5 hospitals", "info", "views/logistics.py"),
                ("Demand series forecast", f"{len(hosp)}", "5 models backtested per series", "info", "views/forecasting.py"),
                ("Predicted stockouts (14 d)", f"{int(((hosp.stockout_day.notna()) & (hosp.stockout_day <= 14)).sum())}", "from live forecasts", "warn", "views/stockout.py"),
                ("Optimizer", "OR-Tools", "MIP / SCIP", "good", "views/optimizer.py")])
except Exception as e:  # keep the landing page alive even if data is unavailable
    st.info("Data is initialising. Open the dashboard to finish setup.")

ui.section("The real-world problem", "Why essential medicines run out - even when stock exists somewhere in the network")
a, b = st.columns(2)
with a:
    ui.nav_card("""<div class="mq-card mq-two mq-fade"><div class="mq-h4">Stockouts, expiry and blind spots</div>
<p>Healthcare networks juggle thousands of medicine lines across hospitals and warehouses. Demand shifts with seasons and outbreaks, suppliers deliver late or short,
and shipments get delayed. Planners often learn about a shortage <b>after</b> it happens, while surplus - or near-expiry stock - sits idle at another facility.</p>
<p>The result: patients' treatment is interrupted, emergency purchases cost more, and good stock is wasted.</p>
<span class="mq-chip">Late supplier deliveries</span><span class="mq-chip">Demand surges</span><span class="mq-chip">Expiry wastage</span><span class="mq-chip">Siloed inventory</span></div>""")
with b:
    ui.nav_card("""<div class="mq-card mq-two mq-fade"><div class="mq-h4">MediResQ AI: detect early, recover optimally</div>
<p>MediResQ forecasts demand per medicine and facility, projects stock day-by-day with <b>FEFO batch logic</b>, scores shortage risk with a visible reason, watches supplier and shipment disruption,
and uses a <b>mathematical optimizer</b> to propose the cheapest feasible redistribution - respecting expiry, reserves, cold chain and capacity.</p>
<p>Every action is a <b>recommendation</b>: a human approves, rejects or modifies it, and the decision is audited.</p>
<span class="mq-chip">Explainable alerts</span><span class="mq-chip">What-if simulation</span><span class="mq-chip">Human approval</span><span class="mq-chip">Full audit trail</span></div>""", "views/approvals.py")

ui.section("Four intelligence engines", "One connected platform")
feats = [("feature_inventory", "Medicine Inventory Intelligence", "Batch-level stock, FEFO issuing, 30/60/90-day expiry alerts, wastage risk and safe-transfer suggestions."),
         ("feature_forecast", "AI Demand Forecasting", "Moving average, seasonal naive, Holt-Winters, Random Forest and Gradient Boosting - chronologically backtested with MAE, RMSE and WAPE."),
         ("feature_logistics", "Supplier and Logistics Monitoring", "Lead-time variability, delay frequency, fulfilment rate, reliability scoring and live shipment disruption tracking."),
         ("feature_recovery", "Intelligent Inventory Recovery", "OR-Tools optimizer + recovery planner turns shortages into prioritised, costed transfer and procurement actions.")]
pages = {"feature_inventory": "views/batches.py", "feature_forecast": "views/forecasting.py", "feature_logistics": "views/suppliers.py", "feature_recovery": "views/optimizer.py"}
cols = st.columns(4)
for col, (img, t, d) in zip(cols, feats):
    with col:
        ui.nav_card(f"""<div class="mq-card mq-feat mq-fade"><img src="{ui.img_uri(img)}" alt="{ui.ALT[img]}" loading="lazy"/><div class="body"><div class="mq-h4">{t}</div><p>{d}</p></div></div>""", pages[img])

ui.section("How it works", "From signal to safe recovery")
steps = [("Demand Prediction", "Forecast 7/14/30 days"), ("Risk Detection", "Stockout, expiry, supplier & shipment risk"), ("Optimization", "OR-Tools redistribution plan"),
         ("Human Approval", "Approve / reject / modify"), ("Recovery", "Transfer or procure, audit-logged")]
flow_pages = ["views/forecasting.py", "views/stockout.py", "views/optimizer.py", "views/approvals.py", "views/planner.py"]
cols = st.columns(5)
for i, (col, (t, d)) in enumerate(zip(cols, steps)):
    with col:
        ui.nav_card(f'<div class="mq-step"><div class="n">{i + 1}</div><b>{t}</b><span>{d}</span></div>', flow_pages[i])

# --- live scenario teaser ------------------------------------------------------------------------------------------
try:
    from mediresq.db import Recommendation
    ui.section("Live demo scenario", "A 7-day supplier delay hits Ceftriaxone 1g - computed from the current dataset")
    r = ass[(ass.medicine.str.startswith("Ceftriaxone")) & (ass.fac_type == "Hospital")].sort_values("risk_score", ascending=False).iloc[0]
    with session_scope() as s:
        top = s.query(Recommendation).filter_by(status="Pending", kind="Redistribution", medicine_id=int(r.med_id)).order_by(Recommendation.priority).first()
        txt = f"Top recommendation: move <b>{top.quantity:,}</b> units from <b>{top.source_name}</b> (ETA {top.eta_days:.1f} d, est. INR {top.est_cost:,.0f})." if top else "Generate a plan in the Recovery Planner."
    st.markdown(ui.h(f"""<div class="mq-card"><b>{r.facility}</b> holds <b>{r.usable:,}</b> vials of {r.medicine} ({r.days_of_inventory} days of cover) while its supplier shipment is delayed.
    Projected stockout: <b>day {int(r.stockout_day) if r.stockout_day == r.stockout_day and r.stockout_day is not None else '-'}</b> &middot; risk <b>{r.risk_level}</b> (score {r.risk_score:.0f}). {txt}</div>"""), unsafe_allow_html=True)
except Exception:
    pass

ui.section("Built to be trusted")
st.markdown(ui.h("".join(f'<span class="mq-chip">{x}</span>' for x in ["Synthetic, reproducible data - clearly labelled", "No patient data", "Heuristic vs probability clearly separated", "Role-based access", "PBKDF2 password hashing",
    "Audit log on every decision", "SAP IBP-aligned concepts (no SAP integration claimed)", "Python - Streamlit - OR-Tools - scikit-learn - SQLite"])), unsafe_allow_html=True)
st.caption(f"{config.BRAND['title']} &middot; {config.BRAND['college']} &middot; Ritesh Kumar Singh &middot; Independent prototype - no official SAP endorsement, partnership or integration.")
