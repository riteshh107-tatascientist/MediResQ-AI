"""Streamlit smoke tests: every page must render without exceptions for each role."""
import glob, os
import pytest
from streamlit.testing.v1 import AppTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = sorted(glob.glob(os.path.join(ROOT, "views", "*.py")))


@pytest.mark.parametrize("path", PAGES, ids=[os.path.basename(p) for p in PAGES])
def test_page_renders_admin(path, dbs):
    import streamlit as st
    st.cache_resource.clear()
    at = AppTest.from_file(path, default_timeout=180)
    at.session_state["user"] = dict(id=1, username="admin_demo", name="Demo Administrator", role="Administrator")
    at.run()
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("name", ["dashboard", "inventory", "approvals", "admin"])
def test_viewer_role_is_restricted_but_renders(name, dbs):
    at = AppTest.from_file(os.path.join(ROOT, "views", f"{name}.py"), default_timeout=180)
    at.session_state["user"] = dict(id=4, username="viewer_demo", name="Demo Viewer", role="Viewer")
    at.run()
    assert not at.exception


def test_login_gate_when_anonymous(dbs):
    at = AppTest.from_file(os.path.join(ROOT, "views", "dashboard.py"), default_timeout=180)
    at.run()
    assert not at.exception and any("Sign in" in s.value for s in at.subheader)


def _app(name, role="Administrator", user="admin_demo"):
    at = AppTest.from_file(os.path.join(ROOT, "views", f"{name}.py"), default_timeout=240)
    at.session_state["user"] = dict(id=1, username=user, name="Demo", role=role)
    at.run()
    return at


def _btn(at, label):
    return next(b for b in at.button if b.label == label)


def test_simulator_run_button_interaction(dbs):
    at = _app("simulator")
    _btn(at, "Run simulation").click(); at.run()
    assert not at.exception and "sim" in at.session_state and len(at.session_state["sim"]["Baseline"]["detail"]) > 0


def test_planner_generate_interaction(dbs):
    at = _app("planner", "Supply Chain Manager", "manager_demo")
    _btn(at, "Generate / refresh recovery plan").click(); at.run()
    assert not at.exception and any("generated" in s.value for s in at.success)


def test_approval_interaction_and_viewer_blocked(dbs):
    at = _app("approvals", "Supply Chain Manager", "manager_demo")
    _btn(at, "Approve").click(); at.run()
    assert not at.exception and any("approved" in s.value.lower() for s in at.success)
    v = _app("approvals", "Viewer", "viewer_demo")
    assert not any(b.label == "Approve" for b in v.button)


def test_optimizer_page_creates_pending_plan(dbs):
    at = _app("optimizer", "Supply Chain Manager", "manager_demo")
    _btn(at, "Create recommendations from this plan (needs approval)").click(); at.run()
    assert not at.exception and any("created" in s.value for s in at.success)
