import pandas as pd
import streamlit as st
from mediresq import ui
from mediresq.approvals import audit_table, decide
from mediresq.db import Recommendation, session_scope

u = ui.require_login(title="Approval & Audit Center", sub="Human-in-the-loop: approve, reject or modify every recommendation. All decisions are time-stamped and audited."); ui.sidebar_user()
c = ui.ctx(); snap = c["snap"]
with session_scope() as s:
    recs = pd.DataFrame([dict(id=r.id, rank=r.priority, plan=r.plan_id, kind=r.kind, medicine=snap.med[r.medicine_id]["name"], source=r.source_name, destination=snap.fac[r.dest_id]["name"] if r.dest_id else "-", quantity=r.quantity,
                              approved_qty=r.approved_qty, cost=r.est_cost, eta_days=r.eta_days, status=r.status, decided_by=r.decided_by, decided_at=r.decided_at, comment=r.comment, reasoning=r.reasoning) for r in s.query(Recommendation).order_by(Recommendation.id.desc())])
t1, t2, t3 = st.tabs(["Pending decisions", "Decision history", "Audit log"])
with t1:
    pend = recs[recs.status == "Pending"].sort_values("rank") if not recs.empty else recs
    if pend.empty: st.success("No pending recommendations.")
    else:
        ui.show_df(pend.drop(columns=["id", "reasoning", "approved_qty", "decided_by", "decided_at", "comment", "status"]), height=250)
        lab = {r.id: f"#{r.rank} {r.kind}: {r.medicine} \u2192 {r.destination} ({r.quantity:,})" for r in pend.itertuples()}
        sel = st.selectbox("Recommendation", list(lab), format_func=lambda i: lab[i]); r = pend[pend.id == sel].iloc[0]
        st.info(f"**Reasoning:** {r.reasoning}\n\nSource: {r.source} \u00b7 cost \u20b9{r.cost:,.0f} \u00b7 ETA {r.eta_days:.1f} d")
        if not ui.role_can("approve"): st.warning("Your role cannot decide on recommendations (view only).")
        else:
            with st.form("dec"):
                cm = st.text_area("Comment (required when rejecting)", max_chars=500); nq = st.number_input("Modified quantity (for Modify)", 0, 10**7, int(r.quantity))
                b1, b2, b3 = st.columns(3)
                chosen = "Approve" if b1.form_submit_button("Approve", type="primary") else "Reject" if b2.form_submit_button("Reject") else "Modify" if b3.form_submit_button("Modify & approve") else None
            if chosen:
                try:
                    with session_scope() as s: decide(s, int(sel), u["username"], u["role"], chosen, cm, int(nq))
                    ui.invalidate(); ui.flash(f"Recommendation {chosen.lower()}d and logged.")
                except Exception as e: st.error(str(e))
            st.caption("Approval records the decision only - MediResQ is decision support and does not move stock or place orders itself.")
with t2:
    h = recs[recs.status.isin(["Approved", "Rejected", "Modified"])] if not recs.empty else recs
    ui.show_df(h.drop(columns=["id", "reasoning"]) if not h.empty else h, height=380)
with t3:
    with session_scope() as s: au = audit_table(s)
    ui.show_df(au, height=420); st.download_button("Download audit log (CSV)", au.to_csv(index=False).encode(), "audit_log.csv", "text/csv")
