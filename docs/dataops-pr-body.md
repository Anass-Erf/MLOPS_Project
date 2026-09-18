The application lacked the required DataOps demonstration. This adds a separate
dlt → DuckDB → dbt → contract → Dagster pathway that reproduces the original
weather and feature CSVs exactly. Explicit ML stages reuse the existing functions
with isolated model/MLflow outputs. Serving startup, production promotion and
the existing Docker/Komodo configuration retain their behavior.

Validation:

- Original 70 tests and lint/format pass; 21 optional tests pass.
- Two dbt models and 35 data tests pass. Corrupted copies fail the expected checks.
- Both Dagster jobs execute, including isolated training and frozen evaluation.
- Existing training/evaluation/monitoring commands pass in an isolated project copy.
- All three Docker services build and become healthy.
- Real manual and automatic Streamlit predictions match the unchanged API example.
- Dagster UI/GraphQL exposes assets and successful persistent run history.

See `docs/dataops-verification.md` for file inventory, evidence and limitations,
and README → DataOps Pipeline for the short offline demonstration. Training and
promotion are excluded from the default demo job. The additional CI workflow
runs entirely from committed NASA snapshots without live collection or training.
