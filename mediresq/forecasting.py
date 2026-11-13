"""Demand forecasting: baselines + statistical + ML models with chronological backtesting."""
from __future__ import annotations
import warnings
from datetime import date, timedelta

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor

from . import config
from .db import Consumption, Facility, ForecastResult, Medicine, ModelMetric

warnings.filterwarnings("ignore")
MODELS = ["Moving Average", "Seasonal Naive", "Exponential Smoothing", "Random Forest", "Gradient Boosting"]
SIMPLE = {"Moving Average": 0, "Seasonal Naive": 1, "Exponential Smoothing": 2, "Random Forest": 3, "Gradient Boosting": 4}


# ----------------------------------------------------------------------------------- data preparation ---
def clean_series(raw: pd.Series, asof: date) -> tuple[pd.Series, dict]:
    """Full daily index; missing days imputed (same-weekday median of neighbours); true zeros kept;
    outliers winsorised with a robust (median/MAD) rule. Returns cleaned series and a quality report."""
    idx = pd.date_range(raw.index.min(), pd.Timestamp(asof) - pd.Timedelta(days=1), freq="D")
    s = raw.reindex(idx)
    missing = s.isna()
    if missing.any():
        for ts in s.index[missing]:
            nb = [ts + pd.Timedelta(days=7 * k) for k in (-4, -3, -2, -1, 1, 2, 3, 4)]
            vals = s.reindex(nb).dropna()
            s.loc[ts] = float(vals.median()) if len(vals) else float(s.median())
    med = s.median()
    mad = (s - med).abs().median() * 1.4826
    cap = med + 6 * mad if mad > 0 else s.quantile(0.995) * 1.5 + 1
    cap = max(cap, s.quantile(0.99))
    outl = s > cap
    rep = {"days": len(s), "missing_imputed": int(missing.sum()), "zero_days": int((s == 0).sum()),
           "outliers_capped": int(outl.sum()), "outlier_cap": float(cap)}
    return s.clip(upper=cap), rep


def load_series(session, med_id: int, fac_id: int, asof: date) -> pd.Series:
    rows = session.query(Consumption.date, Consumption.quantity).filter_by(medicine_id=med_id, facility_id=fac_id).order_by(Consumption.date).all()
    s = pd.Series({pd.Timestamp(d): float(q) for d, q in rows}, dtype=float)
    return s


# ------------------------------------------------------------------------------------------- models ---
def _feat_row(hist: list[float], d: pd.Timestamp) -> list[float]:
    h = np.asarray(hist)
    lag = lambda k: h[-k] if len(h) >= k else h[0]
    return [lag(1), lag(2), lag(3), lag(7), lag(14), h[-7:].mean(), h[-28:].mean(), d.weekday(),
            np.sin(2 * np.pi * d.dayofyear / 365.25), np.cos(2 * np.pi * d.dayofyear / 365.25)]


def _ml_fit(train: pd.Series, kind: str):
    vals = train.values.tolist()
    X, y = [], []
    for i in range(28, len(vals)):
        X.append(_feat_row(vals[:i], train.index[i])); y.append(vals[i])
    if kind == "Random Forest":
        m = RandomForestRegressor(n_estimators=40, max_depth=8, min_samples_leaf=3, random_state=config.SEED, n_jobs=1)
    else:
        m = GradientBoostingRegressor(n_estimators=80, max_depth=3, learning_rate=0.06, subsample=0.8, random_state=config.SEED)
    m.fit(np.array(X), np.array(y))
    return m


def _ml_predict(m, train: pd.Series, h: int) -> np.ndarray:
    hist = train.values.tolist()
    out = []
    for k in range(h):
        d = train.index[-1] + pd.Timedelta(days=k + 1)
        p = max(float(m.predict(np.array([_feat_row(hist, d)]))[0]), 0.0)
        out.append(p); hist.append(p)
    return np.array(out)


def forecast_model(train: pd.Series, name: str, h: int):
    """Return (prediction array, fitted model or None)."""
    if name == "Moving Average":
        return np.repeat(train.values[-7:].mean(), h), None
    if name == "Seasonal Naive":
        last = train.values[-7:]
        return np.array([last[k % 7] for k in range(h)]), None
    if name == "Exponential Smoothing":
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            fit = ExponentialSmoothing(train.values + 0.01, trend=None, seasonal="add", seasonal_periods=7, initialization_method="estimated").fit()
            return np.maximum(fit.forecast(h) - 0.01, 0), None
        except Exception:
            return np.repeat(train.values[-14:].mean(), h), None
    m = _ml_fit(train, name)
    return _ml_predict(m, train, h), m


# -------------------------------------------------------------------------------------------- metrics ---
def metrics(actual: np.ndarray, pred: np.ndarray) -> dict:
    e = actual - pred
    tot = float(np.abs(actual).sum())
    return {"mae": float(np.mean(np.abs(e))), "rmse": float(np.sqrt(np.mean(e ** 2))), "wape": float(np.abs(e).sum() / tot) if tot > 0 else float("nan")}


def backtest(series: pd.Series, test_days: int = 28, models: list[str] | None = None) -> dict:
    """Chronological split: train on all but last `test_days`, evaluate multi-step forecast on the hold-out."""
    models = models or MODELS
    train, test = series.iloc[:-test_days], series.iloc[-test_days:]
    res = {}
    for name in models:
        pred, _ = forecast_model(train, name, test_days)
        res[name] = {**metrics(test.values, pred), "pred": pred, "resid": test.values - pred}
    return res


def pick_best(bt: dict) -> str:
    """Lowest WAPE (RMSE tie-break). Baselines win ties against ML models, avoiding needless complexity."""
    def key(n):
        w = bt[n]["wape"]
        return (np.inf if np.isnan(w) else round(w, 4), bt[n]["rmse"], SIMPLE[n])
    return min(bt, key=key)


def seasonality_analysis(series: pd.Series) -> dict:
    dow = series.groupby(series.index.dayofweek).mean()
    mon = series.groupby(series.index.month).mean()
    return {"dow_index": (dow / dow.mean()).round(3).to_dict(), "month_index": (mon / mon.mean()).round(3).to_dict()}


def run_all(session, asof: date, models: list[str] | None = None, test_days: int = 28, horizon: int = config.HORIZON, progress=None) -> pd.DataFrame:
    """Backtest + forecast every hospital series, persist forecasts/metrics, aggregate to warehouses."""
    models = models or MODELS
    config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    session.query(ForecastResult).delete(); session.query(ModelMetric).delete()
    facs = {f.id: f for f in session.query(Facility).all()}
    hospitals = [f for f in facs.values() if f.type == "Hospital"]
    meds = session.query(Medicine).all()
    fdates = [asof + timedelta(days=k) for k in range(horizon)]
    store: dict[tuple, tuple] = {}
    n = 0
    for m in meds:
        for h in hospitals:
            raw = load_series(session, m.id, h.id, asof)
            s, _ = clean_series(raw, asof)
            bt = backtest(s, test_days, models)
            best = pick_best(bt)
            for nm, r in bt.items():
                session.add(ModelMetric(medicine_id=m.id, facility_id=h.id, model=nm, mae=r["mae"], rmse=r["rmse"],
                                        wape=0.0 if np.isnan(r["wape"]) else r["wape"], test_days=test_days, selected=(nm == best)))
            pred, fitted = forecast_model(s, best, horizon)
            q10, q90 = np.percentile(bt[best]["resid"], [10, 90])
            lo, hi = np.maximum(pred + min(q10, 0), 0), pred + max(q90, 0)
            if fitted is not None:
                joblib.dump(fitted, config.MODEL_DIR / f"m{m.id}_f{h.id}.joblib")
            for d, a, b, c in zip(fdates, pred, lo, hi):
                session.add(ForecastResult(medicine_id=m.id, facility_id=h.id, date=d, yhat=float(a), lo=float(b), hi=float(c), model=best))
            store[(m.id, h.id)] = (pred, lo, hi)
            n += 1
            if progress:
                progress(n / (len(meds) * len(hospitals)))
    for w in [f for f in facs.values() if f.type == "Warehouse"]:
        kids = [h.id for h in hospitals if h.parent_id == w.id]
        for m in meds:
            p = sum(store[(m.id, k)][0] for k in kids); l = sum(store[(m.id, k)][1] for k in kids); u = sum(store[(m.id, k)][2] for k in kids)
            for d, a, b, c in zip(fdates, p, l, u):
                session.add(ForecastResult(medicine_id=m.id, facility_id=w.id, date=d, yhat=float(a), lo=float(b), hi=float(c), model="Aggregated (child facilities)"))
    session.commit()
    return metric_table(session)


def metric_table(session) -> pd.DataFrame:
    rows = session.query(ModelMetric, Medicine.name, Facility.name).join(Medicine, Medicine.id == ModelMetric.medicine_id).join(Facility, Facility.id == ModelMetric.facility_id).all()
    return pd.DataFrame([dict(medicine=mn, facility=fn, medicine_id=m.medicine_id, facility_id=m.facility_id, model=m.model, MAE=m.mae, RMSE=m.rmse,
                              WAPE=m.wape, selected=m.selected) for m, mn, fn in rows])


def model_summary(mt: pd.DataFrame) -> pd.DataFrame:
    """Aggregate comparison across all series (micro-averaged MAE/RMSE; mean WAPE) - honest, from stored backtests."""
    if mt.empty:
        return mt
    g = mt.groupby("model").agg(MAE=("MAE", "mean"), RMSE=("RMSE", "mean"), WAPE=("WAPE", "mean"), series_won=("selected", "sum")).reset_index()
    return g.sort_values("WAPE")
