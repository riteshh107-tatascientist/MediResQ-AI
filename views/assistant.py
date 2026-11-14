import streamlit as st
from mediresq import config, llm, ui
from mediresq.assistant import HELP
from mediresq.db import session_scope

ui.require_login(title="AI Medicine Analyst (Gemini)", sub="Ask in English / Hindi / Hinglish. Answers are grounded in live MediResQ calculations - the AI explains, it never invents numbers."); ui.sidebar_user()
c = ui.ctx(); snap, ass, bt = c["snap"], c["ass"], c["bt"]

with st.sidebar:
    with st.expander("Gemini API key", expanded=not llm.api_key()):
        st.text_input("Paste key (kept only in this browser session)", type="password", key="gemini_key", placeholder="AIza...")
        st.caption("Free key: aistudio.google.com/apikey. For deployment add `GEMINI_API_KEY` in Streamlit Secrets. Only synthetic demo data is sent to Gemini.")
key = llm.api_key()
if key:
    ui.note("<b>Gemini connected.</b> Each answer = MediResQ's verified calculations + Gemini's explanation. See <i>Data sent to Gemini</i> under every answer.")
else:
    st.warning("No Gemini API key found - using the built-in rule-based assistant (still answers from live data). Add a key in the sidebar or Secrets to get full AI explanations.")

hist = st.session_state.setdefault("chat", [])


def run(question: str):
    with session_scope() as s:
        ctx_text, rule_text, df = llm.build_context(question, s, snap, ass, bt)
    ans, err, src = None, None, "Rule-based (built-in)"
    if key:
        with st.spinner("Gemini is analysing the data..."):
            ans, err = llm.ask_gemini(question, ctx_text, [(h["q"], h["a"]) for h in hist if h["src"] == "Gemini"])
        if ans:
            src = "Gemini"
    if not ans:
        ans = rule_text + (f"\n\n> *Gemini unavailable: {err}*" if err and err != "no_key" else "")
    hist.append(dict(q=question, a=ans, src=src, df=df, ctx=ctx_text))


def render(h, expand_ctx=False):
    with st.chat_message("user"):
        st.write(h["q"])
    with st.chat_message("assistant"):
        st.markdown(h["a"])
        st.caption(f"Source: {h['src']} - synthetic demo data - decision support only, not clinical advice")
        if h["df"] is not None:
            ui.show_df(h["df"], height=240)
        with st.expander("Data sent to Gemini (transparency)", expanded=expand_ctx):
            st.code(h["ctx"][:6000], language="text")


t1, t2 = st.tabs(["AI Chat", "Medicine Analysis"])
with t1:
    qs = ["Which medicines have critical stock?", "Which facility is at greatest risk?", "What batches expire next month?", "Explain the latest recovery recommendation",
          "Which supplier is most unreliable and why?", "Ceftriaxone ka stock kaisa hai?", "Kaunsi medicine pehle order karni chahiye?", "Summarise today's supply risks for the director"]
    cols = st.columns(4)
    for i, q in enumerate(qs):
        if cols[i % 4].button(q, key=f"q{i}", **ui.W):
            st.session_state["pending_q"] = q
    q = st.chat_input("Ask about stock, risk, expiry, suppliers, shipments, forecasts or recovery plans...") or st.session_state.pop("pending_q", None)
    if q:
        run(q[:400])
    for h in hist[-6:]:
        render(h)
    if not hist:
        st.info("Click a question above or type your own.")
    if hist and st.button("Clear chat"):
        st.session_state["chat"] = []; st.rerun()
with t2:
    st.markdown("Pick a medicine to get a full AI supply analysis: stock by facility, forecast, expiry, supplier, risk and next actions.")
    a, b = st.columns([2, 1])
    mname = a.selectbox("Medicine", sorted(m["name"] for m in snap.med.values()), key="ana_med")
    if b.button("Generate AI analysis", type="primary", **ui.W):
        run(f"Give a complete supply analysis of {mname}: stock and days of cover at every facility, 7/14/30-day forecast demand, expiry/batch risk, supplier risk, "
            f"which facilities are at risk and the recommended actions.")
        st.session_state["show_last"] = True
    if st.session_state.get("show_last") and hist:
        render(hist[-1], expand_ctx=False)
