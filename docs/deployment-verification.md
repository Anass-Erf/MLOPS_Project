# Komodo deployment verification — 8 September 2026

Verified locally with Docker Compose v5.1.4 on Linux, using the isolated project
`cws-komodo-check` in `/tmp/cws-komodo-clean`. That build context was copied from
Git-tracked and nonignored new files, excluding the laptop virtualenv, ignored
models/data, and MLflow history. Final source fixes were synchronized and rebuilt.
No training, promotion, model metrics, or original artifact bytes were changed.
The changes have not been committed, pushed, or deployed to the remote Komodo server.

## Results

- `docker compose config --quiet`: passed.
- `docker compose -p cws-komodo-check down --remove-orphans`: passed.
- `docker compose -p cws-komodo-check build --no-cache`: all three targets passed;
  subsequent source corrections were rebuilt successfully.
- `docker compose -p cws-komodo-check up -d --wait --wait-timeout 180`: all three
  services healthy, both initially and after final container recreation.
- Host bindings tested on loopback ports 18000 (API), 18501 (UI), 15000 (MLflow)
  to avoid collisions. The deployment defaults remain 8000, 8501, and 5000.
- HTTP 200: API `/health`, `/docs`, UI `/_stcore/health`, MLflow `/` and `/health`.
- `/predict` with the existing example: `0.8685826307973173`, model
  `v4-2771746c21f7`, forecast `2022-11-16`, high stress; verified via both host
  bindings and Compose service DNS.
- Streamlit AppTest inside the UI image, using real HTTP to the API: Load Example
  and Predict Water Stress passed; Automatic Weather fetch and prediction passed.
- NASA outage simulated at the downloader boundary: genuine bundled snapshot
  fallback passed and matched the manual example exactly.
- Real NASA HTTP request from the UI container: 200, 30 days. The full automatic
  live retrieval created a checksum manifest in the cache and predicted the same
  result. No live request was needed for startup or the offline checks.
- Release checker: production checksum/feature contract, matching frozen evaluation,
  and verified offline snapshot coverage for all three sites passed.
- MLflow HTTP experiment creation, parameter logging, proxied artifact upload and
  download passed. This created only a deployment-smoke run, with no model training.
- After `down` without `-v` and `up`: eight API prediction events remained; the
  genuine live NASA snapshot remained and was reused offline; the MLflow run,
  parameter and exact artifact content remained readable.
- Final service logs showed successful startup; all three health checks passed.
- `make test`: **70 passed**, one upstream Starlette/AnyIO deprecation warning.
  Sandbox TestClient execution stalled; the normal permitted host run passed.
- Ruff lint and formatting passed for `src`, `tests`, `monitoring`, `ui`, `scripts`;
  `git diff --check` passed.

The slim MLflow image emits a nonfatal missing-Git warning when the smoke client
logs a run; the tracking server and artifact operations work. Streamlit AppTest
emits its usual bare-mode ScriptRunContext warning. Neither indicates a failed UI.

## Remaining external steps and limits

Commit and push every file below, including the newly nonignored release assets.
Then configure Komodo exactly as README → Komodo Deployment: repo
`Anass-Erf/MLOPS_Project`, branch `main`, run directory `.`, file
`docker-compose.yml`, Run Build enabled, Auto Pull disabled. Select the actual
server (`vh3` was given by the user, not discoverable in Git). No required environment
values or registry credentials are needed. Optional port/bind values are documented.

Remote server access, firewall reachability and its Komodo settings were not tested.
Builds need public Python-image/PyPI access. Future uncached weather requests depend
on NASA availability. The remote MLflow database begins empty unless old history
is explicitly migrated with its recorded absolute artifact paths preserved.
Local history was left untouched; deployment volumes retain data across redeploys.
The isolated verification containers are stopped after checking, with volumes retained.

## Complete changed/new file inventory

- `.dockerignore`
- `.env.example`
- `.github/workflows/ci.yml`
- `.gitignore`
- `Dockerfile`
- `README.md`
- `docker-compose.yml`
- `docs/demo.md`
- `src/models/common.py`
- `data/raw/marrakech_e61d787d44274b78.json`
- `data/raw/marrakech_e61d787d44274b78.manifest.json`
- `data/raw/meknes_fc310869bf3c7795.json`
- `data/raw/meknes_fc310869bf3c7795.manifest.json`
- `data/raw/settat_089aaa53dddeefc3.json`
- `data/raw/settat_089aaa53dddeefc3.manifest.json`
- `docs/deployment-verification.md`
- `models/production.json`
- `models/v4-2771746c21f7/metadata.json`
- `models/v4-2771746c21f7/model.joblib`
- `requirements-ui.txt`
- `scripts/smoke_ui.py`
- `scripts/verify_deployment_assets.py`
- `tests/test_tracking.py`
