import pandas as pd
import streamlit as st
from datetime import datetime
from mediresq import ui
from mediresq.alerts import refresh_alerts
from mediresq.auth import audit
from mediresq.db import Alert, session_scope

u = ui.require_login(title="Alert Center", sub="Critical stock, predicted stockouts, expiry, supplier delays, shipment disruption, overstock, unfulfilled demand."); ui.sidebar_user()
c = ui.ctx(); snap, asof = c["snap"], c["asof"]
if ui.role_can("ack_alert") and st.button("Refresh alerts from current data"):
    with session_scope() as s: n = refresh_alerts(s, asof)
    st.success(f"{n} alert conditions evaluated.")
with session_scope() as s:
    al = pd.DataFrame([dict(id=a.id, severity=a.severity, type=a.type, status=a.status, message=a.message, reason=a.reason, action=a.recommended_action, updated=a.updated_at) for a in s.query(Alert).all()])
op = al[al.status.isin(["Open", "Acknowledged"])]
ui.kpi_row([(sv, f"{int((op.severity == sv).sum())}", "open / acknowledged", {"Critical": "bad", "High": "warn", "Medium": "info", "Low": "good"}[sv]) for sv in ["Critical", "High", "Medium", "Low"]])
st.write("")
a, b, d = st.columns(3)
ty = a.multiselect("Type", sorted(al.type.unique())); sv = b.multiselect("Severity", ["Critical", "High", "Medium", "Low"], default=["Critical", "High"]); stt = d.multiselect("Status", ["Open", "Acknowledged", "Resolved", "Auto-Closed"], default=["Open", "Acknowledged"])
x = al[al.severity.isin(sv) & al.status.isin(stt)]
if ty: x = x[x.type.isin(ty)]
x = x.assign(o=x.severity.map({"Critical": 0, "High": 1, "Medium": 2, "Low": 3})).sort_values(["o", "updated"], ascending=[True, False]).drop(columns="o")
ui.show_df(x.drop(columns=["id"]), height=380)
if ui.role_can("ack_alert") and not x.empty:
    ui.section("Take action")
    lab = {r.id: f"[{r.severity}] {r.message}" for r in x.head(100).itertuples()}
    sel = st.selectbox("Alert", list(lab), format_func=lambda i: lab[i]); r = x[x.id == sel].iloc[0]
    st.info(f"**Reason:** {r.reason}\n\n**Recommended action:** {r.action}")
    c1, c2, _ = st.columns([1, 1, 3])
    for col, (lbl, st_) in zip((c1, c2), [("Acknowledge", "Acknowledged"), ("Resolve", "Resolved")]):
        if col.button(lbl, key=lbl):
            with session_scope() as s:
                a_ = s.get(Alert, int(sel)); a_.status, a_.updated_at = st_, datetime.now(); audit(s, u["username"], "ALERT_" + st_.upper(), "alert", sel)
            ui.invalidate(); ui.flash(f"Alert {lbl.lower()}d.")
