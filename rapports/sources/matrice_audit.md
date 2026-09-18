# Matrice de vérification du rapport

État audité : 0f3bc50, 17 septembre 2026.

| Exigence | État | Preuve | Observation |
|---|---|---|---|
| dlt | Oui | src/dataops/dlt_pipeline.py | Ingestion réelle, instantanés vérifiés, remplacement |
| DuckDB | Oui | artifacts/dataops/crop_water_stress.duckdb | Trois relations métier et tables dlt |
| dbt | Oui | dbt_project | Deux modèles, contrats, 35 tests de données |
| Dagster | Oui | src/dataops/definitions.py | Source externe, six assets, deux jobs |
| Data Contract | Oui | src/dataops/contract.py | Schéma, bornes, couverture, égalité source |
| MLflow | Oui | src/models/train.py; models/production.json | Tracking, registre, candidat/production |
| API/UI | Oui | src/api; ui | FastAPI et client Streamlit |
| Docker | Oui | Dockerfile; docker-compose.yml | api, ui, mlflow; Dagster local |
| CI | Oui |  .github/workflows | Deux workflows; pas de build Docker ni CD |
| Monitoring | Oui | monitoring/drift.py | PSI, KS, qualité, performances si labels |
| Agile | Reconstruction | git log | Trois phases proposées; réunions non documentées |
| Git/GitHub | Oui | git log; git branch -avv | 0f3bc50, branche distante suivie |
| Pull Requests | Aucune observée | API GitHub, sources/verification_github.json | Liste vide tous états confondus au 17 septembre 2026 |
| Komodo distant | Non vérifié | README; docs/deployment-verification.md | Procédure présente; pas de capture Komodo ni preuve distante |
