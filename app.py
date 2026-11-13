"""MediResQ AI - entry point. Run:  python -m streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="MediResQ AI | SAP Hackfest 2026", page_icon="\U0001F48A", layout="wide", initial_sidebar_state="expanded")

PAGES = [
    ("Overview", [("views/home.py", "Home", "\U0001F3E0"), ("views/dashboard.py", "Executive Dashboard", "\U0001F4CA")]),
    ("Inventory", [("views/inventory.py", "Medicine Inventory", "\U0001F4E6"), ("views/batches.py", "Batch & Expiry", "\u23F3")]),
    ("Intelligence", [("views/forecasting.py", "Demand Forecasting", "\U0001F4C8"), ("views/stockout.py", "Stockout Early Warning", "\U0001F6A8"),
                      ("views/suppliers.py", "Supplier Intelligence", "\U0001F3ED"), ("views/logistics.py", "Logistics & Disruptions", "\U0001F69A")]),
    ("Recovery", [("views/optimizer.py", "Redistribution Optimizer", "\U0001F9EE"), ("views/planner.py", "AI Recovery Planner", "\U0001F9ED"), ("views/simulator.py", "What-If Simulator", "\U0001F9EA")]),
    ("Governance", [("views/alerts.py", "Alert Center", "\U0001F514"), ("views/approvals.py", "Approvals & Audit", "\u2705"), ("views/analytics.py", "Advanced Analytics", "\U0001F52C"),
                    ("views/assistant.py", "Intelligence Assistant", "\U0001F4AC"), ("views/admin.py", "Admin & Data", "\u2699\uFE0F")]),
]
nav = {sec: [st.Page(p, title=t, icon=i, default=(p == "views/home.py")) for p, t, i in items] for sec, items in PAGES}
pg = st.navigation(nav)
pg.run()
