# Model Evaluation

Numbers below are **read from the stored hold-out backtests** of the shipped demo database (synthetic data). Nothing is hand-entered.

## Protocol
- Series: 22 medicines x 5 hospitals = 110 daily-demand series; warehouse demand = sum of child hospitals.
- Cleaning: full daily index; missing days -> same-weekday median of +-4 weeks; true zeros preserved; outliers winsorised at median + 6 MAD (robust).
- **Chronological split**: train on all but the last 28 days; forecast the 28-day hold-out multi-step (recursive for ML models); no shuffling, no look-ahead.
- Models: Moving Average (7 d), Seasonal Naive (weekly), Holt-Winters additive (period 7), Random Forest, Gradient Boosting (lag / rolling / weekday / annual-seasonality features).
- Selection: lowest WAPE per series (RMSE tie-break; simpler baselines win ties). The selected model is refit on all data and forecasts 30 days.
- Uncertainty: empirical 10th/90th percentile of the selected model's hold-out residuals (not a calibrated predictive interval).

## Aggregate comparison (mean over 110 series; series_won = times selected)

| model                 |    MAE |   RMSE |   WAPE |   series_won |
|:----------------------|-------:|-------:|-------:|-------------:|
| Gradient Boosting     | 11.189 | 15.633 |  0.208 |           28 |
| Random Forest         | 11.347 | 15.504 |  0.209 |           26 |
| Exponential Smoothing | 12.694 | 16.437 |  0.218 |           43 |
| Moving Average        | 13.925 | 18.763 |  0.253 |            8 |
| Seasonal Naive        | 12.774 | 17.694 |  0.272 |            5 |

Best single baseline mean WAPE: **25.3%**. Mean WAPE of the per-series selected model: **18.8%**. Selection is made on the same hold-out, so the latter is optimistic; rolling-origin evaluation is the natural next step.

## Limitations
- Synthetic Poisson-based demand has a known generating process; real demand is noisier and may favour other models.
- One 28-day hold-out per series; no rolling-origin cross-validation.
- The stockout probability is a normal approximation and is **not** empirically calibrated; risk scores are heuristics.
- Do not quote these metrics as real-world accuracy.
