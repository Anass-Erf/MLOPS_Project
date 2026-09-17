PYTHON ?= .venv/bin/python
export MPLBACKEND = Agg
export OMP_NUM_THREADS = 1
export OPENBLAS_NUM_THREADS = 1
export MPLCONFIGDIR = /tmp/cws-matplotlib

.PHONY: install data offline preprocess features train evaluate promote pipeline reports notebooks test lint api ui docker mlflow monitor example demo-request

install:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

data:
	$(PYTHON) -m src.data.collect_data

offline:
	$(PYTHON) -m src.data.collect_data --offline

preprocess:
	$(PYTHON) -m src.data.preprocess

features:
	$(PYTHON) -m src.features.build_features

train:
	$(PYTHON) -m src.models.train

evaluate:
	$(PYTHON) -m src.models.evaluate

promote:
	$(PYTHON) -m src.models.registry

# Recursive calls make stage dependencies sequential even when invoked with make -j.
pipeline:
	$(MAKE) data
	$(MAKE) preprocess
	$(MAKE) features
	$(MAKE) train
	$(MAKE) evaluate
	$(MAKE) promote
	$(MAKE) reports
	$(MAKE) example
	$(MAKE) monitor

reports:
	$(PYTHON) -m src.reports

notebooks:
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/01_data_exploration.ipynb --ExecutePreprocessor.timeout=180
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/02_model_experiments.ipynb --ExecutePreprocessor.timeout=180

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check src tests monitoring ui
	$(PYTHON) -m ruff format --check src tests monitoring ui

api:
	$(PYTHON) -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000

ui:
	$(PYTHON) -m streamlit run ui/app.py --server.address localhost --server.port 8501 --browser.gatherUsageStats false

docker:
	docker build -t crop-water-stress-api .

mlflow:
	$(PYTHON) -m mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db --host 0.0.0.0 --port 5000

monitor:
	$(PYTHON) -m monitoring.drift

example:
	$(PYTHON) -m src.api.example_request

demo-request:
	curl --fail-with-body http://localhost:8000/predict -H 'Content-Type: application/json' --data-binary @artifacts/example_request.json

# Optional DataOps tools have a separate environment and generated state.
DATAOPS_PYTHON ?= .venv-dataops/bin/python
export CWS_ML_PYTHON ?= $(abspath $(PYTHON))
export DAGSTER_HOME ?= $(CURDIR)/artifacts/dataops/dagster
export RUNTIME__DLTHUB_TELEMETRY = false

.PHONY: dataops-install dataops-ingest dataops-dbt dataops-quality dataops-inspect dataops dataops-demo dataops-train dataops-evaluate dataops-test dataops-dbt-docs dagster dataops-dagster-home

dataops-install:
	python3 -m venv .venv-dataops
	$(DATAOPS_PYTHON) -m pip install -r requirements-dataops.txt
	$(DATAOPS_PYTHON) -m pip check

dataops-ingest:
	$(DATAOPS_PYTHON) -m src.dataops.dlt_pipeline

dataops-dbt:
	$(DATAOPS_PYTHON) -m src.dataops.cli dbt

dataops-quality:
	$(DATAOPS_PYTHON) -m src.dataops.cli quality

dataops-inspect:
	$(DATAOPS_PYTHON) -m src.dataops.cli inspect

dataops-dbt-docs:
	$(DATAOPS_PYTHON) -m src.dataops.cli dbt --dbt-command docs

dataops-dagster-home:
	mkdir -p "$(DAGSTER_HOME)"
	cp configs/dagster.yaml "$(DAGSTER_HOME)/dagster.yaml"

dataops dataops-demo: dataops-dagster-home
	$(DATAOPS_PYTHON) -m src.dataops.cli demo

dagster: dataops-dagster-home
	$(DATAOPS_PYTHON) -m dagster dev -m src.dataops.definitions -h 127.0.0.1 -p 3000

dataops-train:
	$(DATAOPS_PYTHON) -m src.dataops.cli train

dataops-evaluate:
	$(DATAOPS_PYTHON) -m src.dataops.cli evaluate

dataops-test:
	$(DATAOPS_PYTHON) -m pytest -q --confcutdir=tests/dataops tests/dataops
