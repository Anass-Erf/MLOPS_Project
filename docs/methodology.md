# Scientific definition and decision record

## What is being predicted?

Water limitation reduces a crop's ability to meet atmospheric evaporative demand.
This project forecasts a **scenario-based stress proxy**, not plant water potential,
canopy-temperature CWSI, yield loss, or an observed irrigation requirement.
Forecast origin is the end of local solar day *t*. The label is end-of-day stress
on *t+1*. Tomorrow's realized weather is used only to compute the retrospective
label; it is never an input to the forecast.

The reference is [FAO-56, Chapter 8](https://www.fao.org/4/X0490E/x0490e0e.htm):

```
TAW = 1000 × (field_capacity − wilting_point) × root_depth_m
RAW = p × TAW
Ks(D) = clip((TAW − D) / ((1 − p) × TAW), 0, 1)
target[t] = 1 − Ks(D_end[t+1])
```

Water contents are m³/m³; depletion and available water are mm. `Ks=1` implies no
modeled limitation. The index `1-Ks` ranges from zero to one. A single-coefficient
water balance approximates evaporation and transpiration together; a dual-coefficient
model would represent those components more faithfully.

## Implemented scenario, with explicit assumptions

NASA provides weather only. **All soil and management parameters below are assumed,
not downloaded observations or calibrated Moroccan field measurements.** The three
points are scenario locations near cities, not verified wheat-field boundaries.

| Setting | Configured value | Reason / limitation |
|---|---|---|
| Crop | rainfed wheat | A single crop keeps the lifecycle explainable |
| Points | Meknes (33.89, −5.55), Settat (33.00, −7.62), Marrakech (31.63, −7.99) | Three Moroccan climate settings, not independent trials |
| Soil capacity / wilting point | 0.30/0.15, 0.28/0.14, 0.25/0.12 | Illustrative contrasting storage capacities, confounded with location |
| Root depth | 1.0 m, fixed | Conservative effective reservoir; ignores root growth |
| Sowing | November 15 | Fixed scenario date, not observed phenology |
| Stage duration | 20/40/70/50 days | Initial/development/mid/late scenario totaling 180 days |
| Crop coefficient | 0.30 → 1.15 → 0.30 | Simplified seasonal demand curve; not locally calibrated |
| Fallow coefficient | 0.25 | Approximate off-season evaporation, not a full bare-soil model |
| Rain infiltration | 80% | Fixed effective rainfall; remainder treated as loss |
| Initial depletion | 50% of TAW | Discard first 365 days as spin-up; uncertainty remains |
| Irrigation / capillary rise | zero | Rainfed, freely draining bucket |
| Baseline depletion fraction | 0.55 | Demand adjustment `clip(0.55 + 0.04*(5-ETc), 0.1, 0.8)` |

The implementation runs continuously through fallow periods and across year boundaries.
It never resets soil to a wet state at sowing. The chosen daily update is:

1. Apply effective rainfall to yesterday's depleted reservoir.
2. Drain water exceeding field capacity immediately.
3. Compute demand `ETc = Kc × ET0` and the demand-adjusted depletion fraction.
4. Limit actual ET by both water availability and the stress coefficient after rain.
5. Update bounded end-of-day depletion, then calculate the end-of-day stress proxy.

This ordering is our explicit numerical approximation. Water-conservation tests check
that rainfall, drainage, ET and storage changes balance. `artifacts/proxy_audit.csv`
records daily ET, drainage, depletion and modeled soil moisture for auditing; these
quantities are excluded from ML inputs. Initial-state, soil and crop-calendar
sensitivity should be evaluated before treating the scenario as agronomic evidence.

## Evapotranspiration and units

We implement the Hargreaves-Samani approximation from
[FAO-56, Chapter 3, equation 52](https://www.fao.org/4/X0490E/x0490e07.htm).
Extraterrestrial radiation is computed from latitude/day-of-year in MJ/m²/day,
then multiplied by **0.408** to obtain equivalent mm/day before entering:

```
ET0 = max(0, 0.0023 × (Tmean + 17.8) × sqrt(Tmax − Tmin) × Ra_mm)
```

This transparent approximation keeps the label generator small enough to audit.
It is uncalibrated locally; FAO recommends comparison with Penman-Monteith. We
download humidity, wind and solar radiation as ML covariates, but do not pretend
they enter this ET0 equation. Implementing Penman-Monteith with checked radiation,
pressure/elevation and humidity assumptions is a useful extension.

NASA AG radiation is normalized to MJ/m²/day. A kWh/m²/day response is multiplied
by 3.6; unknown units fail validation. Temperature is °C, rain mm/day, humidity %,
wind m/s at 2 m. Missing NASA fill values are detected, not imputed.

## Feature availability and leakage controls

| Feature family | Availability and rationale |
|---|---|
| Today's weather, range, approximate VPD | Available at day end; atmospheric drying conditions |
| Rain sums over 7 and 30 days | Recent replenishment of the soil reservoir |
| Seven-day mean temperature | Sustained thermal demand |
| Thirty-day precipitation minus ET0 | Recent balance of water supply and demand |
| Yesterday's precipitation | Antecedent wetting |
| Day-of-year sine/cosine; crop age and Kc | Known seasonal phase and scenario growth stage |
| Coordinates, soil FC/WP, root depth and TAW | Static location/storage context |

Exactly 30 ordered, consecutive observations are used by the API. A shared function
builds the same last-day row from the full batch or this short history. Rolling
windows include today, never tomorrow. Windows and lags are isolated by site.
Unit tests perturb future observations and verify past features and proxy states
remain unchanged. Seasonal features use a known calendar, not future measurements.

`stress_today`, modeled soil moisture, depletion and any target-day quantities are
**not model features**. They would make recovering this constructed label nearly
deterministic. Today's stress is retained solely for a separate persistence comparator.
That comparator has full historical simulator state; the ML model has bounded weather
history, so the comparison is informative but not an equal-information experiment.

## Validation design and model selection

Target dates through June 30, 2021 form training; July 1, 2021 through June 30, 2022
form validation; later dates through June 2024 form test. Only active-season origin
and target pairs survive. All sites follow the same cutoffs. This estimates temporal
transfer at known sites, **not geographic transfer**. Historical weather crossing a
split boundary is allowed because it would be available at forecast time.

Four predeclared configurations are compared: mean DummyRegressor, scaled Ridge,
Random Forest and histogram gradient boosting. The scaler fits inside the Ridge
pipeline. Gradient boosting has internal early stopping disabled, avoiding a hidden
random split. Each estimator clips predictions to [0,1] during both scoring and serving.
Select lowest validation RMSE; break ties by MAE then name. Refit that configuration
on training plus validation, freeze it, then evaluate test.

MAE is mean absolute index error; RMSE penalizes large errors; R² compares residual
variance with a mean predictor. MAPE is omitted because zero stress is valid and common.
No test tuning, random split, synthetic training observations or field-performance
claims are permitted. Scores are point estimates over autocorrelated daily rows;
blocked seasonal uncertainty intervals would be more appropriate than IID intervals.

## Data source investigation

* [NASA POWER daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/):
  public, credential-free daily weather from satellite/model products. The core
  ingestion saves original response metadata, URLs, units and checksums. Grid
  weather is not a sensor installed at a farm.
* [FAO-56](https://www.fao.org/4/X0490E/x0490e00.htm): a methodological reference
  for the proxy. We do not claim a downloaded FAO soil dataset.
* [FAO WaPOR data access](https://www.fao.org/in-action/remote-sensing-for-water-productivity/wapor-data-access/en):
  public remote-sensing products are promising for ET and water-productivity
  enrichment. Raster extraction, spatial alignment and product support need extra
  implementation, so they are not claimed as current training inputs.
* [Google Earth Engine authentication](https://developers.google.com/earth-engine/guides/auth):
  requires authentication and a configured project. It is not a core dependency.
  An optional future adapter can export dated NDVI/EVI/LST observations to
  `data/raw/earth_engine/`; it must retain acquisition dates and use causal as-of
  joins. A composite containing future days cannot be joined to an earlier forecast.

There is no bundled fabricated fallback dataset. Once snapshots are downloaded,
`--offline` reuses them with integrity checks. A clean machine without API access
must receive those archived snapshots and manifests from a prior genuine download.

## Lifecycle decisions

* Local SQLite-backed MLflow gives both tracking and registry without paid services.
  [Aliases](https://mlflow.org/docs/latest/ml/model-registry/workflow/) represent
  `candidate` and `production`; immutable local model files support the API without
  a running tracking server. Promotion is a separate command, not a test-score optimizer.
* Lightweight SHA-256 manifests and stage receipts replace DVC for this small dataset.
  They identify data/config/code changes and support audit/replay; they do **not**
  provide DVC remote storage or automatic dependency caching. See the README archive commands.
* Tests use clearly labeled artificial fixtures to exercise failure cases. Those
  fixtures never enter the scientific pipeline or reported experiments.
* Monitoring compares distributions with PSI and KS distance and checks missing/
  invalid values. Labels are required for performance alerts. The deliberately
  perturbed demonstration is unlabeled and not used to estimate real degradation.
* There is no automated cloud deployment. CI gates code quality, tests and app import;
  local Docker deployment completes the reproducible demonstration.
