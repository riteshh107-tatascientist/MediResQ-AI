"""Gemini-powered MediResQ Medicine Analyst. The model only EXPLAINS data that MediResQ computed (RAG-style grounding):
every question is answered from a compact context built from live database calculations. No clinical advice."""
from __future__ import annotations
import os
import re

import pandas as pd

from . import config
from .analytics import dashboard_kpis
from .assistant import answer as rule_answer
from .db import Recommendation, Shipment
from .suppliers import supplier_stats

MODELS = [m for m in [config.GEMINI_MODEL, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"] if m]
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM = """You are MediResQ AI, a medicine supply-chain analyst for hospital supply managers (SAP Hackfest 2026 prototype).
RULES
1. Use ONLY the DATA section. Never invent numbers, names or dates. If something is not in DATA, say "not available in the data".
2. You support inventory decisions only. Do NOT give clinical, dosing or treatment advice; if asked, say this tool is not clinical and to consult a pharmacist or doctor.
3. The data is a synthetic demo dataset. Risk score is a heuristic; stockout probability is model-based and not empirically calibrated - say so if you quote it.
4. Any transfer or purchase needs human approval (Approvals & Audit page). Never say an action was executed.
5. Reply in the same language the user writes (English / Hindi / Hinglish).
FORMAT (short, clear, markdown)
**Answer:** one or two sentences.
**Key numbers:** 3-6 bullets with units (use INR for money).
**Why:** one or two lines of reasoning from the data.
**Recommended action:** numbered steps (max 4).
"""


def api_key() -> str:
    try:
        import streamlit as st
        k = st.session_state.get("gemini_key") or ""
        if not k:
            try:
                k = st.secrets.get("GEMINI_API_KEY", "")
            except Exception:
                k = ""
    except Exception:
        k = ""
    return (k or os.getenv("GEMINI_API_KEY", "")).strip()


def _find(names, q: str):
    q = q.lower()
    out = []
    for i, n in names.items():
        toks = [t for t in re.split(r"[\s\-/(),]+", n.lower()) if len(t) > 3]
        if n.lower() in q or (toks and toks[0] in q):
            out.append(i)
    return out


def build_context(question: str, session, snap, ass: pd.DataFrame, bt: pd.DataFrame) -> tuple[str, str, pd.DataFrame | None]:
    """Returns (context text for the LLM, rule-based verified answer, optional table)."""
    asof = snap.asof
    k = dashboard_kpis(session, snap, ass, bt)
    L = [f"DATASET: synthetic, as of {asof}. Currency INR.",
         f"KPIS: medicines {k['medicines']}, hospitals {k['facilities']}, warehouses {k['warehouses']}, inventory value INR {k['inventory_value']:,.0f}, critical alerts {k['critical_alerts']}, "
         f"predicted stockouts<=14d {k['predicted_stockouts']}, near-expiry batches(<=90d) {k['near_expiry']}, expired batches {k['expired_batches']}, high-risk suppliers {k['supplier_risks']}, "
         f"pending approvals {k['pending']}, resilience index {k['resilience']['index']:.0f}/100 (heuristic)."]
    cols = ["medicine", "facility", "usable", "avg_daily", "days_of_inventory", "lead_time", "stockout_day", "risk_level", "risk_score", "p_stockout_model", "reorder_qty", "reason"]
    top = ass.sort_values("risk_score", ascending=False).head(12)[cols]
    L.append("TOP RISKS (heuristic score 0-100):\n" + top.to_csv(index=False))
    med_ids = _find({i: m["name"] for i, m in snap.med.items()}, question)
    fac_ids = _find({i: f["name"] for i, f in snap.fac.items()}, question)
    if med_ids:
        for mid in med_ids[:2]:
            d = ass[ass.med_id == mid][cols[:-1] + ["on_order", "safety_stock", "reorder_point", "shortage_date"]]
            L.append(f"MEDICINE DETAIL {snap.med[mid]['name']} (criticality {snap.med[mid]['crit']}/3, cold chain {snap.med[mid]['cold']}, unit cost INR {snap.med[mid]['cost']}):\n" + d.to_csv(index=False))
            b = bt[(bt.med_id == mid) & (bt.status == "Available")].sort_values("days_to_expiry").head(8)[["facility", "batch_no", "days_to_expiry", "quantity", "bucket", "wastage_risk_qty"]]
            L.append("BATCHES (earliest expiry first):\n" + b.to_csv(index=False))
            ser = [s for (m, f), s in snap.series.items() if m == mid and snap.fac[f]["type"] == "Hospital"]
            L.append(f"FORECAST next 7/14/30 days, all hospitals: {sum(s.forecast[:7].sum() for s in ser):,.0f} / {sum(s.forecast[:14].sum() for s in ser):,.0f} / {sum(s.forecast[:30].sum() for s in ser):,.0f} units")
    if fac_ids:
        for fid in fac_ids[:1]:
            d = ass[(ass.fac_id == fid)].sort_values("risk_score", ascending=False).head(8)[cols[:-1]]
            L.append(f"FACILITY DETAIL {snap.fac[fid]['name']}:\n" + d.to_csv(index=False))
    recs = session.query(Recommendation).filter_by(status="Pending").order_by(Recommendation.priority).limit(6).all()
    if recs:
        L.append("PENDING RECOMMENDATIONS:\n" + "\n".join(
            f"#{r.priority} {r.kind}: {r.quantity} units of {snap.med[r.medicine_id]['name']} from {r.source_name} to {snap.fac[r.dest_id]['name'] if r.dest_id else '-'}; cost INR {r.est_cost:,.0f}; ETA {r.eta_days:.1f} d; reason: {r.reasoning[:260]}" for r in recs))
    sp = supplier_stats(session, asof)[["supplier", "on_time_rate", "avg_delay_days", "fill_rate", "reliability", "risk", "active_delay_days"]].round(2)
    L.append("SUPPLIERS:\n" + sp.to_csv(index=False))
    sh = session.query(Shipment).filter(Shipment.status.in_(["In Transit", "Delayed"]), Shipment.delay_days > 0).all()
    if sh:
        L.append("DELAYED SHIPMENTS:\n" + "\n".join(f"{s.ship_no}: {s.quantity} x {snap.med[s.medicine_id]['name']} to {snap.fac[s.destination_id]['name']} delayed {s.delay_days} d" for s in sh))
    exp = bt[(bt.status == "Available") & (bt.days_to_expiry > 0) & (bt.days_to_expiry <= 30)].sort_values("days_to_expiry").head(8)[["medicine", "facility", "batch_no", "days_to_expiry", "quantity", "value"]]
    L.append("EXPIRING WITHIN 30 DAYS:\n" + exp.to_csv(index=False))
    text, df = rule_answer(question, session, snap, ass, bt)
    L.append("VERIFIED RULE-BASED ANSWER (computed from the database): " + re.sub(r"\s+", " ", text)[:700])
    return "\n\n".join(L)[:14000], text, df


def ask_gemini(question: str, context: str, history: list | None = None, key: str | None = None, timeout: int = 60) -> tuple[str | None, str | None]:
    """Returns (answer, error). Never raises; never logs the key."""
    import requests
    key = key or api_key()
    if not key:
        return None, "no_key"
    contents = []
    for q, a in (history or [])[-4:]:
        contents += [{"role": "user", "parts": [{"text": q[:500]}]}, {"role": "model", "parts": [{"text": a[:1500]}]}]
    contents.append({"role": "user", "parts": [{"text": f"DATA:\n{context}\n\nUSER QUESTION: {question[:600]}"}]})
    body = {"system_instruction": {"parts": [{"text": SYSTEM}]}, "contents": contents,
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1100}}
    last = "unknown error"
    for m in MODELS:
        try:
            r = requests.post(URL.format(model=m), json=body, headers={"x-goog-api-key": key, "Content-Type": "application/json"}, timeout=timeout)
        except Exception as e:  # network
            return None, f"Network error contacting Gemini: {type(e).__name__}"
        if r.status_code == 200:
            try:
                parts = r.json()["candidates"][0]["content"]["parts"]
                txt = "".join(p.get("text", "") for p in parts).strip()
                if txt:
                    return txt, None
                last = "Gemini returned an empty answer (possibly blocked by safety filters)."
            except Exception:
                last = "Unexpected response format from Gemini."
            continue
        msg = ""
        try:
            msg = r.json().get("error", {}).get("message", "")
        except Exception:
            pass
        if r.status_code in (400, 401, 403) and ("API key" in msg or "API_KEY" in msg or r.status_code in (401, 403)):
            return None, "Gemini rejected the API key (invalid, restricted or not enabled). Create a key at aistudio.google.com/apikey."
        if r.status_code == 429:
            return None, "Gemini quota/rate limit reached. Wait a minute and retry (free tier has limits)."
        last = f"{m}: HTTP {r.status_code} {msg[:120]}"
        if r.status_code not in (404, 400):
            break
    return None, last
