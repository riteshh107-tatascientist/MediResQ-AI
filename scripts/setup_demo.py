"""Build the demo database: synthetic data -> CSV -> DB -> forecasts (5 models) -> alerts -> recovery plan.
Usage:  python scripts/setup_demo.py [--asof YYYY-MM-DD] [--fast]"""
import argparse, sys, time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mediresq import seed  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--asof", default=None); ap.add_argument("--fast", action="store_true", help="skip Random Forest / Gradient Boosting")
a = ap.parse_args()
t = time.time()
info = seed.seed(asof=date.fromisoformat(a.asof) if a.asof else None, fast=a.fast, progress=lambda p: print(f"\rforecasting {p:4.0%}", end="", flush=True))
print("\nSeeded:", info, f"in {time.time() - t:.0f}s")
