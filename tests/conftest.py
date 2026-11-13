import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mediresq import config, db, seed  # noqa: E402

ASOF = date(2026, 11, 13)


@pytest.fixture(scope="session")
def dbs(tmp_path_factory):
    """Isolated SQLite DB seeded with a reduced (150-day) synthetic history and fast models."""
    p = tmp_path_factory.mktemp("db") / "test.db"
    db.set_engine(f"sqlite:///{p.as_posix()}")
    seed.seed(asof=ASOF, fast=True, write_csv=False, history_days=150)
    yield p
    db.set_engine(config.DB_URL)


@pytest.fixture()
def s(dbs):
    with db.session_scope() as session:
        yield session


@pytest.fixture(scope="session")
def snap(dbs):
    from mediresq.engine import build_snapshot
    with db.session_scope() as session:
        return build_snapshot(session, ASOF)
