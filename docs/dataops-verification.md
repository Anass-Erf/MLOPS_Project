# DataOps implementation and verification — 17 September 2026

This is an additive implementation on `feature/dataops-pipeline`. It preserves
the old pipeline and the evaluated `v4-2771746c21f7` release. Local verification
is complete; remaining commits, publication and remote Actions execution are
external steps. Machine-readable results are in [dataops-evidence.json](dataops-evidence.json).

## A. Baseline before modification

- Read README, tracked repository tree, Makefile/configuration, Docker/Komodo
  guidance, collection/manifests, normalization, validation, features/proxy,
  training/evaluation/registry, API, UI, monitoring, tests and CI.
- Git was clean on `main`, at `85f9ace`.
- `make test lint`: **70 passed**, Ruff lint passed, **40 files** formatted.
- The first sandbox test run stalled in the existing TestClient setup, matching
  the documented sandbox limitation. A permitted host run passed in 4.13 seconds.
  This was an execution-environment restriction, not a failing baseline test.
- `scripts/verify_deployment_assets.py`: passed release checksum, feature
  contract, matching evaluation and genuine offline snapshots for all three sites.
- Saved example: **0.8685826307973173**, version **v4-2771746c21f7**, forecast
  **2022-11-16**, stress level **high**.
- Baseline API TestClient: root, health and prediction all HTTP 200. This response
  capture occurred after adding unused ingestion files, before modifying any
  application behavior; all serving files and artifacts remained unchanged.
- Compose configuration valid. No services for this Compose project were running
  at baseline. A remote Komodo deployment was not inspected.

## B. Files created

| File | Purpose |
|---|---|
| `requirements-dataops.txt` | Pinned optional dependencies in a separate environment |
| `requirements-dataops-lock.txt` | Independently tested transitive dependency constraints |
| `src/dataops/__init__.py` | Optional package with no application-startup hooks |
| `src/dataops/settings.py` | Separate generated paths and ML configuration |
| `src/dataops/dlt_pipeline.py` | Existing collector/normalizer reuse, provenance verification and real dlt load |
| `src/dataops/dbt_runner.py` | Real dbt CLI invocation, absolute database paths, configured coverage |
| `src/dataops/contract.py` | Shared validation, source equivalence, provenance and atomic CSV export |
| `src/dataops/cli.py` | Explicit commands, inspection and original-interpreter ML subprocesses |
| `src/dataops/ml_bridge.py` | Existing feature/training/evaluation functions with isolated tracking and stale-data guards |
| `src/dataops/definitions.py` | Dagster source, six assets, safe demo job and explicit training job |
| `configs/dagster.yaml` | Persistent local instance configuration; one queued run at a time |
| `dbt_project/dbt_project.yml` | dbt project, schemas, enforced model contracts and default source coverage |
| `dbt_project/profiles.yml` | Credential-free local DuckDB profile |
| `dbt_project/models/schema.yml` | Exact column/type contracts, source lineage, not-null and accepted-site tests |
| `dbt_project/models/staging/stg_weather.sql` | Strict canonical renaming and type/date casts |
| `dbt_project/models/marts/ml_weather.sql` | Canonical input projection for the existing ML pipeline |
| `dbt_project/tests/weather_rules.sql` | Existing weather bounds and temperature/soil ordering |
| `dbt_project/tests/unique_site_date.sql` | Composite observation uniqueness |
| `dbt_project/tests/complete_dates.sql` | Full site/date coverage, including entirely missing sites |
| `tests/dataops/test_dataops.py` | 21 optional integration, corruption, provenance and safety tests |
| `.github/workflows/dataops.yml` | Additional deterministic offline CI, separate from original workflow |
| `docs/dataops-verification.md` | This report |
| `docs/dataops-evidence.json` | Recorded API comparison, hashes, counts, metrics and Dagster runs |
| `docs/dataops-pull-request.md` | Honest current Git state, remaining commits and real PR instructions |
| `docs/dataops-pr-body.md` | Review-ready PR description for GitHub CLI or the web UI |

Generated databases, tool state, models and logs remain under the ignored
`artifacts/dataops/`. `.venv-dataops/` is also ignored.

## C. Existing files modified

- `.gitignore`: exclude only the new environment, generated DataOps state and dbt/dlt caches.
- `Makefile`: append optional commands and separate interpreter/instance settings.
  Every original target recipe remains unchanged.
- `README.md`: add the requested DataOps Pipeline architecture, rules, commands,
  lineage, demo and operating boundaries.

No changes to core requirements, scientific configuration, original Python pipeline,
API schema, Streamlit, monitoring implementation, production artifacts, Dockerfile,
Compose, existing CI, model metrics or Komodo settings.

## D. dlt

The existing collector verifies cached snapshot hashes. Additional checks compare
each manifest's source endpoint and complete request metadata to configuration.
`normalize_payload` supplies the original units and NASA fill-value handling.
All 10,407 records pass existing weather/coverage validation before dlt writes
`raw.raw_weather` with replace semantics. Repeated loads remain at 10,407 rows.
Raw JSON/manifests remain unchanged. Offline is default; `--live` allows the
existing collector to download missing configured snapshots.

## E. DuckDB

Database: `artifacts/dataops/crop_water_stress.duckdb`.

- `raw.raw_weather`: site/date, seven NASA variables in project units, configured
  coordinates/soil, source, snapshot filename/SHA-256, UTC ingestion timestamp,
  dlt load identifiers.
- `weather_staging.stg_weather`: canonical names/types plus provenance.
- `weather_analytics.ml_weather`: original 13-column canonical weather format.
- dlt manages `_dlt_loads`, `_dlt_pipeline_state`, `_dlt_version` in `raw`.

Each site has 3,469 daily observations, 2015-01-01 through 2024-06-30.
`make dataops-inspect` lists tables, coverage and five source rows.

## F. dbt

`stg_weather` strictly casts dates, floating-point measurements and provenance;
`ml_weather` projects the columns expected by the existing feature builder.
No weather filtering, deduplication, interpolation, target changes or SQL temporal
feature engineering occurs. Enforced contracts check model column names/types.
**35 data tests** pass: 30 not-null checks, two accepted-site checks, composite
uniqueness, complete date coverage and physical-rule consistency.

Actual `dbt debug`, `build`, `run`, `test` and `docs generate` were exercised through
the wrappers. Corrupting a disposable database caused the expected not-null,
accepted-site, uniqueness, coverage and physical-rule tests to fail.

## G. Data contract

The Python contract enforces exact canonical columns/order, numeric weather,
non-null values, valid dates, uniqueness, all configured sites, consecutive full
coverage, original weather bounds, temperature ordering, exact coordinates/soil
and existing soil rules. It independently verifies immutable source bytes and
compares every transformed canonical value and staging provenance row against
those sources. Only passing data gets an atomic CSV export and approval hash.
ML rejects changed approved weather and features built from older weather.

All thresholds reuse the existing project: humidity 0–100, precipitation 0–1000,
wind 0–75, radiation 0–50, mean temperature −60–60, max −60–65 and min −70–60,
in the project's established units. These are existing validation bounds, not
new agronomic recommendations.

## H. Dagster

```text
nasa_snapshots (external)
  → ingest_weather → dbt_transform → data_quality → build_features
  → train_model → evaluate_model
```

- `dataops_demo`: first four executable stages only; successful in 19.25 seconds.
- `train_evaluate_explicit`: train/evaluate previously generated features; successful
  in approximately 70 seconds. Uses an isolated experiment/registry and SQLite
  store, even with a production tracking URI in the caller's environment.
- No schedule, sensor, startup training or promotion asset.
- Training configuration defaults to disabled for generic asset materialization.
- `make dagster`: local UI at `http://127.0.0.1:3000`.
- HTTP and GraphQL verified seven assets and both successful persistent runs.

dbt exposes the SQL portion of lineage. README documents the later manual release
boundary leading to the existing MLflow/production lifecycle, FastAPI and Streamlit.
DataOps evaluation does not imply that its candidate has been deployed.

## I. New Make commands only

| Command | Action |
|---|---|
| `dataops-install` | Create/install/check separate optional environment |
| `dataops-ingest` | Verified offline dlt ingestion |
| `dataops-dbt` | dbt build with schema and data tests |
| `dataops-quality` | dbt test plus Python contract and CSV export |
| `dataops-inspect` | Table/coverage/provenance inspection |
| `dataops-dbt-docs` | Generate dbt catalog/manifest/docs |
| `dataops`, `dataops-demo` | Persistent Dagster demo through features |
| `dagster` | Start local Dagster UI and daemon |
| `dataops-train` | Explicit isolated original ML training |
| `dataops-evaluate` | Explicit isolated frozen evaluation |
| `dataops-test` | Optional test suite without importing core test fixtures |
| `dataops-dagster-home` | Internal helper to prepare persistent instance settings |

## J. Docker and Komodo

No Dockerfile or Compose changes, no new mandatory service or profile, no changed
ports/volumes/service names. All three targets built and ran healthy in the isolated
local project `cws-dataops-check`. Verification bindings were loopback 28000/28501/25000;
these are command-time overrides only. API image build-time release verification passed.
The original configuration remains valid for Komodo; the remote host was not redeployed.
Local Dagster requires only port 3000 and no Compose changes.

The verification services are left running for inspection: Dagster at
`http://127.0.0.1:3000`, API at `http://127.0.0.1:28000`, Streamlit at
`http://127.0.0.1:28501`, and MLflow at `http://127.0.0.1:25000`. These are local
verification processes, not the remote deployment. Stop the verification containers
with `docker compose -p cws-dataops-check down` (no `-v`, so volumes are retained).

## K. CI

The original workflow is untouched. `dataops.yml` installs core and DataOps in
separate environments; runs offline integration/corruption tests; materializes the
Dagster demo; checks existing release assets; generates and uploads dbt/quality
evidence. No live NASA requests, training or promotion. These commands were tested
locally; remote GitHub Actions has not run for this unpublished work.

## L. Regression verification

| Check | Before | After |
|---|---|---|
| Existing tests | 70 passed | 70 passed; optional module skipped in core environment |
| Lint/format | Passed, 40 files | Passed, 49 files |
| Optional tests | Not present | 21 passed |
| API root / health / predict | HTTP 200 | HTTP 200, exact same bodies |
| Example score | 0.8685826307973173 | 0.8685826307973173 |
| Model / forecast | v4-2771746c21f7 / 2022-11-16 | Unchanged |
| Compose configuration | Valid; no project services running | Valid; all three builds and health checks passed |
| Manual UI / Load Example | Existing suite passed | Existing suite + real container HTTP smoke passed |
| Automatic UI / offline fallback | Existing suite passed | Real container HTTP smoke passed and matched manual prediction |

Additional evidence:

- Weather CSV SHA-256, both paths:
  `e8bb00c6cad31fb9fe1988b856f2937936240f6e2a4c7db2fb2f71472af8ee64`.
- Features CSV SHA-256, both paths:
  `67bc92ef38a7b2a8d132dce245f06a2249e9735b316203601424d6a1e567bbe8`.
- Features: 4,692 rows; train 3,081, validation 537, test 1,074.
- Existing `make offline preprocess features train evaluate monitor` passed in
  `/tmp/cws-dataops-compat`, an isolated project copy, using the original interpreter.
  This verified original commands without changing real candidate aliases or metrics.
- Dagster's isolated training selected gradient boosting; validation RMSE
  `0.17056424214821458`, test RMSE `0.18859124320752263`. All three validation/test
  metrics exactly match the original release. Registry candidate alias exists;
  no production alias exists in the demo registry. MLflow run status is FINISHED.
- MLflow UI/health, Streamlit health and Dagster UI returned HTTP 200.
- Existing production pointer/model, scientific config, snapshots and original
  metrics remain unchanged in Git. The original MLflow database/history was never
  used as the destination for DataOps or compatibility training.

## M. Git / PR

Branch: `feature/dataops-pipeline`. Commit created: `5583615` (verified ingestion).
The second Git write request was rejected, so subsequent stages remain uncommitted.
No history rewrite, force push, fabricated collaboration or merge occurred.
Follow [dataops-pull-request.md](dataops-pull-request.md) to review, create the
remaining logical commits, push, open a real PR to main, and obtain team review
and passing Actions before a maintainer merges it.

## N. Five-minute university demo

Install environments ahead of time. Show a NASA manifest (45 seconds), run
`make dataops-ingest dataops-inspect` sequentially (45 seconds), then
`make dataops-dbt dataops-quality` (one minute). Run `make dataops-demo` (under one
minute on the verified machine), launch `make dagster`, and show the asset graph,
successful run logs/materializations and isolated training job (remaining time).
Use the exact sequential commands in README; do not add `make -j` or run simultaneous
writers against the same database. The full small snapshots keep the existing
spin-up and chronological splits intact.

## O. Remaining limitations

- Git write rejection leaves publication and most commits pending. No remote PR,
  Actions result, team review or remote Komodo check is claimed.
- DuckDB is a local single-writer store. Dagster serializes UI runs; independently
  launched CLI commands must not overlap. This is a local university demo, not a
  distributed production scheduler.
- Installation/builds require PyPI/container-image access. Offline demonstrations
  require the committed genuine snapshots and installed dependencies.
- Live NASA collection is retained but was not called during this extension's
  deterministic verification.
- ML stages require the original application environment and a DataOps workspace
  inside the repository for existing relative-path provenance.
- Dagster/SQL lineage ends at evaluated demo candidates; production deployment
  remains an explicit separate release process, not an automatic edge.
- Dagster UI was checked through HTTP/GraphQL, not browser screenshot automation.
  Streamlit interactions were checked using its existing AppTest smoke script.
- Original upstream Starlette/AnyIO deprecation and normal Streamlit bare-mode
  warnings remain. The sandbox restricts TestClient and gRPC sockets, so host
  permission was needed for those checks and Docker access.
- Existing scientific limitations (modeled proxy, assumed soils, three sites,
  no field validation) remain unchanged.
