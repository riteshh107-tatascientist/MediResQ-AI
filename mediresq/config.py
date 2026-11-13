"""Central configuration. Values can be overridden with environment variables (.env)."""
from __future__ import annotations
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CSV_DIR = DATA_DIR / "csv"
ASSET_DIR = ROOT / "assets" / "images"
MODEL_DIR = DATA_DIR / "models"

try:  # optional .env support
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(ROOT / ".env")
except Exception:  # pragma: no cover
    pass

# SQLAlchemy URL - swap for postgresql+psycopg2://... for a future PostgreSQL migration.
DB_URL = os.getenv("MEDIRESQ_DB_URL", f"sqlite:///{(DATA_DIR / 'mediresq.db').as_posix()}")
SEED = int(os.getenv("MEDIRESQ_SEED", "42"))
HISTORY_DAYS = int(os.getenv("MEDIRESQ_HISTORY_DAYS", "365"))
DEMO_PASSWORD = os.getenv("MEDIRESQ_DEMO_PASSWORD", "Demo@2026!")
MAX_UPLOAD_MB = 5
HORIZON = 30  # forecast horizon in days


def as_of_date() -> date:
    """Reference 'today' for the synthetic dataset. Defaults to the real current date."""
    v = os.getenv("MEDIRESQ_ASOF")
    return date.fromisoformat(v) if v else date.today()


BRAND = {
    "eyebrow": "SAP HACKFEST 2026 | WEST & CENTRAL REGION",
    "title": "MediResQ AI",
    "tagline": "Predict. Protect. Prevent Shortages.",
    "subtitle": "AI-Powered Essential Medicine Supply Chain Resilience.",
    "description": "Intelligent forecasting, disruption detection and optimized medicine recovery.",
    "college": "TIT BHOPAL | CSE (DATA SCIENCE)",
}
ROLES = ["Administrator", "Supply Chain Manager", "Warehouse Manager", "Viewer"]
