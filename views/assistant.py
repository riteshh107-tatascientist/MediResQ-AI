import streamlit as st
from mediresq import ui
from mediresq.assistant import HELP, answer
from mediresq.db import session_scope

ui.require_login(title="MediResQ Intelligence Assistant", sub="Answers come from live database queries and calculations - no LLM, nothing invented."); ui.sidebar_user()
c = ui.ctx(); snap, ass, bt = c["snap"], c["ass"], c["bt"]
hist = st.session_state.setdefault("chat", [])
cols = st.columns(3)
for i, q in enumerate(HELP[:6]):
    if cols[i % 3].button(q, key=f"q{i}", **ui.W):
        st.session_state["pending_q"] = q
q = st.chat_input("Ask about stock, risk, expiry, suppliers, shipments, forecasts or recovery plans...") or st.session_state.pop("pending_q", None)
if q:
    with session_scope() as s: txt, df = answer(q[:300], s, snap, ass, bt)
    hist.append((q, txt, df))
for q_, t_, d_ in hist[-8:]:
    with st.chat_message("user"): st.write(q_)
    with st.chat_message("assistant"):
        st.markdown(t_)
        if d_ is not None: ui.show_df(d_, height=260)
if not hist: st.info("Try one of the example questions above.")
