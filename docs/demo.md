# demonstration

For the existing evaluated release, run `docker compose up --build -d`; see
README → Komodo Deployment. No retraining is required. The steps below demonstrate
the optional full development lifecycle and will create new training runs.

1. Show README's architecture and `src/`. Explain modular scripts versus notebooks.
2. Open `docs/methodology.md` and config. Explain real weather, assumed soil/crop
   management, and **modeled rather than measured stress labels**.
3. Open a NASA snapshot/manifest. Run `make offline preprocess features` and inspect
   `artifacts/data_quality.json` and `artifacts/dataset_manifest.json`.
4. Open the EDA notebook. Explain training-only plots and retained valid extremes.
5. Run `make train`; explain chronological validation, baseline and selected refit.
6. Run `make mlflow` in another terminal. At http://localhost:5000 compare validation
   RMSE/MAE/R² and inspect run parameters, features, hashes, plots and model artifacts.
7. Show candidate alias, run `make evaluate promote reports`, then show production
   alias and `models/production.json`. Discuss the stronger persistence comparator.
8. Run `make example api`, open http://localhost:8000/docs, then `make demo-request`
   in another terminal. Submit `{}` in Swagger to demonstrate 422 validation.
9. Stop host API with Ctrl-C. Run `docker run --rm -p 8000:8000 --name
   crop-water-stress-api crop-water-stress-api` on one line and repeat the request.
   Rebuild first if you want a newly promoted model inside the image.
10. Run `make test lint`; show future-perturbation and inference-parity tests.
11. Show `.github/workflows/ci.yml`. On your published repository show a real Actions
    run if available; local checks do not prove GitHub execution.
12. Run `make monitor`, open both HTML reports, and distinguish genuine historical
    weather/proxy-label performance from simulated, unlabeled drift.

Useful conclusion: this is an auditable lifecycle with honest proxy-label limitations.
Field use requires measured labels and local calibration.

Troubleshooting:

* NASA down: `make offline` reuses verified real snapshots. The release includes snapshots for all three configured sites.
* Health 503: inspect API logs and verify the production pointer/model checksum;
  restore the evaluated release files and rebuild before considering new training.
* Port in use: stop the earlier API/container or map `-p 8001:8000` and update curl.
* Notebook kernel: activate `.venv` or select it in your notebook editor.
* Sandbox-only TestClient hang: use a normal local terminal; event-loop sockets may
  be restricted in the agent runtime. Do not remove tests to hide the problem.
* Relocated MLflow artifacts: preserve the recorded absolute paths or follow the
  history-migration guidance in README → Komodo Deployment.
