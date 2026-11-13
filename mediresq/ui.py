"""Shared Streamlit UI: design system (CSS), hero header, cards, auth gate, cached data context."""
from __future__ import annotations
import base64
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import config
from .auth import authenticate, can
from .db import get_asof, init_db, session_scope

NAVY, BLUE, CYAN, SKY = "#0a1f44", "#0b6bcb", "#22d3ee", "#7dd3fc"
SEV_COLORS = {"Critical": "#dc2626", "High": "#f59e0b", "Medium": "#0b6bcb", "Low": "#10b981"}
SEQ = ["#0b6bcb", "#22d3ee", "#0a1f44", "#60a5fa", "#10b981", "#f59e0b", "#a78bfa", "#94a3b8"]
_VERSION = [0]


def _ver() -> tuple:
    try:
        return tuple(int(x) for x in st.__version__.split(".")[:2])
    except Exception:
        return (1, 0)


# Streamlit >= 1.52 prefers width="stretch"; older versions use **W
W = {"width": "stretch"} if _ver() >= (1, 52) else {"use_container_width": True}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Sora:wght@600;700;800&display=swap');
html, body, [class*="css"], .stApp { font-family: 'Inter', 'Segoe UI', system-ui, sans-serif; }
.block-container { padding-top: 1.2rem; max-width: 1280px; }
[data-testid="stSidebar"] { background: linear-gradient(180deg,#06142f 0%,#0a2a5e 100%); }
[data-testid="stSidebar"] * { color: #e2ecfb; }
[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"] { border-radius: 10px; margin: 1px 6px; }
[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"][aria-current="page"] { background: rgba(34,211,238,.16); border-left: 3px solid #22d3ee; }
[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"]:hover { background: rgba(125,211,252,.12); }
.mq-hero { position: relative; overflow: hidden; border-radius: 18px; border: 1px solid rgba(56,189,248,.38);
  background: linear-gradient(120deg,#06142f 0%,#0a2a5e 55%,#0b4a8f 100%);
  box-shadow: 0 0 0 1px rgba(34,211,238,.08), 0 14px 40px rgba(6,20,47,.30), 0 0 40px rgba(34,211,238,.14); margin-bottom: 18px; }
.mq-hero::after { content:""; position:absolute; top:-25%; bottom:-25%; left:0; width:16%; pointer-events:none; z-index:1;
  background: linear-gradient(100deg, transparent 0%, rgba(34,211,238,.10) 25%, rgba(140,240,255,.50) 50%, rgba(34,211,238,.10) 75%, transparent 100%);
  transform: translateX(-170%) skewX(-18deg); animation: mq-sweep 6s cubic-bezier(.45,.05,.35,1) infinite; filter: blur(1.5px); }
.mq-hero::before { content:""; position:absolute; top:0; bottom:0; left:0; width:2px; pointer-events:none; z-index:1;
  background: linear-gradient(180deg, transparent, #a5f3fc 20%, #ffffff 50%, #a5f3fc 80%, transparent);
  box-shadow: 0 0 14px 3px rgba(34,211,238,.75); animation: mq-line 6s cubic-bezier(.45,.05,.35,1) infinite; }
@keyframes mq-sweep { 0% { transform: translateX(-170%) skewX(-18deg); } 62%,100% { transform: translateX(680%) skewX(-18deg); } }
@keyframes mq-line { 0% { left: -1%; } 62%,100% { left: 101%; } }
@media (prefers-reduced-motion: reduce) { .mq-hero::before, .mq-hero::after { animation: none !important; opacity: 0 !important; } .mq-fade { animation: none !important; } }
.mq-hero-in { position: relative; z-index: 2; display: grid; grid-template-columns: 1.15fr 1fr; gap: 24px; align-items: center; padding: 34px 38px; }
.mq-hero.compact .mq-hero-in { grid-template-columns: 1fr; padding: 18px 28px; }
.mq-eyebrow { font-size: .78rem; letter-spacing: .16em; font-weight: 600; color: #7dd3fc; text-transform: uppercase; }
.mq-title { font-family: 'Sora','Inter',sans-serif; font-weight: 800; font-size: 4.1rem; line-height: 1.02; color: #fff; margin: 6px 0 4px; letter-spacing: -.02em;
  text-shadow: 0 0 28px rgba(34,211,238,.35); }
.mq-hero.compact .mq-title { font-size: 2.1rem; margin: 2px 0; }
.mq-tag { font-size: 1.35rem; font-weight: 600; color: #bae6fd; margin: 2px 0 6px; }
.mq-hero.compact .mq-tag { font-size: .95rem; }
.mq-sub { color: #cfe3fb; font-size: 1.02rem; margin: 0 0 4px; }
.mq-desc { color: #93b4dc; font-size: .92rem; margin: 0 0 14px; }
.mq-college { display: inline-block; margin-top: 4px; padding: 5px 14px; border-radius: 999px; font-size: .78rem; font-weight: 700; letter-spacing: .12em; color: #06142f;
  background: linear-gradient(90deg,#7dd3fc,#22d3ee); }
.mq-hero-img { border-radius: 14px; overflow: hidden; border: 1px solid rgba(125,211,252,.35); box-shadow: 0 12px 30px rgba(0,0,0,.35); }
.mq-hero-img img { width: 100%; display: block; }
.mq-card { background: #fff; border: 1px solid #e3ebf6; border-radius: 14px; padding: 16px 18px; box-shadow: 0 1px 2px rgba(10,31,68,.04), 0 6px 18px rgba(10,31,68,.05); height: 100%; }
.mq-kpi .lab { font-size: .72rem; text-transform: uppercase; letter-spacing: .09em; color: #5b6f8f; font-weight: 600; }
.mq-kpi .val { font-family: 'Sora',sans-serif; font-size: 1.85rem; font-weight: 700; color: #0a1f44; line-height: 1.15; }
.mq-kpi .sub { font-size: .78rem; color: #6b7f9e; }
.mq-kpi.bad { border-left: 4px solid #dc2626; } .mq-kpi.warn { border-left: 4px solid #f59e0b; } .mq-kpi.good { border-left: 4px solid #10b981; } .mq-kpi.info { border-left: 4px solid #0b6bcb; }
.mq-sec { font-family: 'Sora',sans-serif; font-size: 1.35rem; font-weight: 700; color: #0a1f44; margin: 26px 0 4px; }
.mq-sec-sub { color: #5b6f8f; margin-bottom: 12px; }
.mq-badge { display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: .74rem; font-weight: 700; color:#fff; }
.mq-sim { background:#fff7e6; border:1px solid #fcd34d; color:#92400e; padding:8px 12px; border-radius:10px; font-size:.85rem; margin-bottom:10px; }
.mq-note { background:#eef6ff; border:1px solid #bfdbfe; color:#1e3a8a; padding:8px 12px; border-radius:10px; font-size:.85rem; margin-bottom:10px; }
.mq-feat { padding: 0; overflow: hidden; }
.mq-feat img { width: 100%; display:block; }
.mq-feat .body { padding: 14px 16px 16px; }
.mq-feat h4 { margin: 0 0 4px; color: #0a1f44; font-family: 'Sora',sans-serif; }
.mq-feat p { margin: 0; color: #4b5f80; font-size: .9rem; }
.mq-flow { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }
.mq-step { position: relative; background: linear-gradient(160deg,#0a2a5e,#0b4a8f); color:#fff; border-radius: 14px; padding: 16px 14px; text-align:center; min-height: 128px; }
.mq-step .n { width: 28px; height: 28px; border-radius: 50%; background:#22d3ee; color:#06142f; font-weight:800; display:flex; align-items:center; justify-content:center; margin: 0 auto 8px; }
.mq-step b { display:block; font-size: 1rem; } .mq-step span { font-size: .8rem; color:#bcd6f5; }
.mq-step:not(:last-child)::after { content:"\\279C"; position:absolute; right:-14px; top:42%; color:#0b6bcb; font-size:1.3rem; z-index:3; }
.mq-chip { display:inline-block; background:#eaf3ff; color:#0b4a8f; border:1px solid #c9defa; padding: 3px 11px; border-radius: 999px; font-size:.8rem; margin: 2px 3px 2px 0; font-weight:600; }
.mq-fade { animation: mq-in .6s ease both; } @keyframes mq-in { from { opacity:0; transform: translateY(8px);} to {opacity:1; transform:none;} }
div.stButton > button[kind="primary"], div.stButton > button[data-testid="stBaseButton-primary"] { background: linear-gradient(90deg,#0b6bcb,#0891b2); border: 0; font-weight: 700; border-radius: 12px; padding: .7rem 1.2rem;
  box-shadow: 0 8px 22px rgba(11,107,203,.35); transition: transform .15s ease, box-shadow .15s ease; }
div.stButton > button[kind="primary"]:hover, div.stButton > button[data-testid="stBaseButton-primary"]:hover { transform: translateY(-1px); box-shadow: 0 12px 26px rgba(11,107,203,.45); }
@media (max-width: 900px) { .mq-hero-in { grid-template-columns: 1fr; } .mq-title { font-size: 2.8rem; } .mq-flow { grid-template-columns: 1fr; } .mq-step:not(:last-child)::after { display:none; } }
</style>
"""


def h(html: str) -> str:
    """Strip indentation so Markdown never treats HTML as a code block."""
    return "\n".join(l.strip() for l in html.strip().splitlines())


def inject_css():
    st.markdown(h(CSS), unsafe_allow_html=True)


def img_uri(name: str) -> str:
    """Prefer a real photo (jpg/png/webp) in assets/images; fall back to the bundled SVG illustration."""
    for ext, mime in (("jpg", "image/jpeg"), ("jpeg", "image/jpeg"), ("png", "image/png"), ("webp", "image/webp")):
        p = config.ASSET_DIR / f"{name}.{ext}"
        if p.exists():
            return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()
    p = config.ASSET_DIR / f"{name}.svg"
    if p.exists():
        return "data:image/svg+xml;base64," + base64.b64encode(p.read_bytes()).decode()
    return ""


ALT = {"hero": "Modern pharmaceutical warehouse with shelving, delivery trucks and a connected supply-chain network (illustration)",
       "feature_inventory": "Medicine inventory shelves with batch expiry labels (illustration)", "feature_forecast": "Demand forecast chart with confidence band (illustration)",
       "feature_logistics": "Logistics network map with a delayed shipment (illustration)", "feature_recovery": "Redistribution network between warehouse and hospitals (illustration)"}


def hero(compact: bool = False):
    b = config.BRAND
    img = "" if compact else f'<div class="mq-hero-img"><img src="{img_uri("hero")}" alt="{ALT["hero"]}" loading="eager"/></div>'
    st.markdown(h(f"""
    <div class="mq-hero {'compact' if compact else ''}" role="banner"><div class="mq-hero-in">
      <div>
        <div class="mq-eyebrow">{b['eyebrow']}</div>
        <div class="mq-title">{b['title']}</div>
        <div class="mq-tag">{b['tagline']}</div>
        {'' if compact else f'<div class="mq-sub">{b["subtitle"]}</div><div class="mq-desc">{b["description"]}</div>'}
        <span class="mq-college">{b['college']}</span>
      </div>{img}
    </div></div>"""), unsafe_allow_html=True)


def kpi(label: str, value: str, sub: str = "", tone: str = "info") -> str:
    return f'<div class="mq-card mq-kpi {tone}"><div class="lab">{label}</div><div class="val">{value}</div><div class="sub">{sub}</div></div>'


def kpi_row(items: list[tuple]):
    cols = st.columns(len(items))
    for c, it in zip(cols, items):
        c.markdown(h(kpi(*it)), unsafe_allow_html=True)


def badge(text: str) -> str:
    return f'<span class="mq-badge" style="background:{SEV_COLORS.get(text, "#64748b")}">{text}</span>'


def section(title: str, sub: str = ""):
    st.markdown(f'<div class="mq-sec">{title}</div>' + (f'<div class="mq-sec-sub">{sub}</div>' if sub else ""), unsafe_allow_html=True)


def sim_banner(text="SIMULATED - results come from a model on synthetic data and are not real hospital outcomes."):
    st.markdown(f'<div class="mq-sim">&#9888; {text}</div>', unsafe_allow_html=True)


def note(text: str):
    st.markdown(f'<div class="mq-note">{text}</div>', unsafe_allow_html=True)


def style_fig(fig: go.Figure, height=340, legend=True) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", colorway=SEQ,
                      font=dict(family="Inter, Segoe UI, sans-serif", color=NAVY, size=12), title_font=dict(size=15, color=NAVY), showlegend=legend,
                      legend=dict(orientation="h", y=-0.2), hoverlabel=dict(bgcolor=NAVY, font_color="#fff"))
    fig.update_xaxes(gridcolor="#e8eef8", zeroline=False); fig.update_yaxes(gridcolor="#e8eef8", zeroline=False)
    return fig


def show_df(df, height=None, hide=None, **kw):
    """Display a DataFrame or pandas Styler; compatible across Streamlit versions."""
    d = df
    if hide and hasattr(df, "drop"):
        d = df.drop(columns=hide, errors="ignore")
    args = dict(hide_index=True, **W, **kw)
    if height:
        args["height"] = height
    st.dataframe(d, **args)


# --------------------------------------------------------------------------------------- data / auth ---
@st.cache_resource(show_spinner=False)
def ensure_db() -> bool:
    """Create + seed the database on first launch if it is missing (bundled demo DB normally exists)."""
    from sqlalchemy import inspect
    from .db import get_engine
    eng = get_engine()
    need = "users" not in inspect(eng).get_table_names()
    if not need:
        with session_scope() as s:
            from .db import Facility
            need = s.query(Facility).count() == 0
    if need:
        from . import seed
        with st.spinner("First launch: generating synthetic dataset, training forecasting models and optimising... (about 2-4 minutes)"):
            seed.seed()
    return True


def invalidate():
    _VERSION[0] += 1


@st.cache_resource(show_spinner="Computing network intelligence...", max_entries=3)
def _ctx(version: int):
    from .engine import assess_all, build_snapshot
    from .expiry import batch_table
    with session_scope() as s:
        snap = build_snapshot(s)
        ass = assess_all(snap)
        bt = batch_table(s, snap.asof, snap)
    return dict(snap=snap, ass=ass, bt=bt, asof=snap.asof)


def ctx() -> dict:
    ensure_db()
    return _ctx(_VERSION[0])


def user() -> dict | None:
    return st.session_state.get("user")


def role_can(action: str) -> bool:
    u = user()
    return bool(u) and can(u["role"], action)


def login_form():
    inject_css(); hero(compact=True)
    c1, c2, c3 = st.columns([1, 1.3, 1])
    with c2:
        st.markdown('<div class="mq-card">', unsafe_allow_html=True)
        st.subheader("Sign in")
        fails = st.session_state.get("fails", 0)
        with st.form("login"):
            u = st.text_input("Username", max_chars=40)
            p = st.text_input("Password", type="password", max_chars=100)
            go_ = st.form_submit_button("Sign in", type="primary", **W)
        if go_:
            if fails >= 5:
                st.error("Too many failed attempts in this session. Refresh the page to retry.")
            else:
                with session_scope() as s:
                    usr = authenticate(s, u, p)
                    rec = dict(id=usr.id, username=usr.username, name=usr.full_name, role=usr.role) if usr else None
                if rec:
                    st.session_state["user"] = rec; st.session_state["fails"] = 0; st.rerun()
                st.session_state["fails"] = fails + 1
                st.error("Invalid username or password.")
        with st.expander("Local demo accounts (synthetic - for the hackathon demo only)"):
            st.code("admin_demo / manager_demo / warehouse_demo / viewer_demo\nPassword: " + config.DEMO_PASSWORD)
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


def flash(msg: str):
    """Show a success message on the next run (survives st.rerun())."""
    st.session_state["_flash"] = msg
    st.rerun()


def require_login(action: str | None = None, title: str = "", sub: str = ""):
    """Call at the top of every protected page. Renders compact hero + page title; stops if not logged in / not permitted."""
    ensure_db()
    inject_css()
    if not user():
        login_form()
    hero(compact=True)
    if title:
        st.markdown(f'<div class="mq-sec" style="margin-top:4px">{title}</div><div class="mq-sec-sub">{sub}</div>', unsafe_allow_html=True)
    msg = st.session_state.pop("_flash", None)
    if msg:
        st.success(msg)
    if action and not role_can(action):
        st.warning(f"Your role ({user()['role']}) is not permitted to use this page.")
        st.stop()
    return user()


def sidebar_user():
    u = user()
    with st.sidebar:
        st.markdown(f"**{config.BRAND['title']}**  \n<span style='font-size:.75rem;color:#93b4dc'>{config.BRAND['college']}</span>", unsafe_allow_html=True)
        if u:
            st.markdown(f"<div style='font-size:.85rem;margin:8px 0'>Signed in as <b>{u['name']}</b><br/><span style='color:#7dd3fc'>{u['role']}</span></div>", unsafe_allow_html=True)
            if st.button("Sign out", **W):
                from .auth import audit
                with session_scope() as s:
                    audit(s, u["username"], "LOGOUT", "user", u["id"])
                st.session_state.pop("user", None); st.rerun()
        try:
            with session_scope() as s:
                st.caption(f"Synthetic dataset as of {get_asof(s)}")
        except Exception:
            pass
        st.caption("Independent prototype - not affiliated with or endorsed by SAP. Decision support only; not a clinical system.")
