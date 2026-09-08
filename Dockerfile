FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
WORKDIR /app
COPY requirements-api.txt requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt -c requirements-lock.txt \
    && useradd --create-home --uid 10001 appuser
COPY src ./src
COPY configs ./configs
COPY artifacts/example_request.json ./artifacts/example_request.json

FROM base AS ui
COPY requirements-ui.txt ./
RUN pip install --no-cache-dir -r requirements-ui.txt -c requirements-lock.txt
COPY ui ./ui
COPY data/raw/*.json ./data/raw/
RUN mkdir -p data/raw/ui_weather && chown appuser:appuser data/raw/ui_weather
USER appuser
EXPOSE 8501
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["python", "-m", "streamlit", "run", "ui/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--browser.gatherUsageStats=false"]

FROM base AS tracking
RUN pip install --no-cache-dir mlflow==3.1.1 -c requirements-lock.txt \
    && mkdir -p /mlflow/artifacts && chown -R appuser:appuser /mlflow
USER appuser
EXPOSE 5000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"
CMD ["python", "-m", "mlflow", "server", "--host", "0.0.0.0", "--port", "5000", "--backend-store-uri", "sqlite:////mlflow/mlflow.db", "--serve-artifacts", "--artifacts-destination", "/mlflow/artifacts"]

# Keep the API as the default target for existing docker build / make docker usage.
FROM base AS api
COPY models/production.json ./models/production.json
COPY models/v4-2771746c21f7 ./models/v4-2771746c21f7
COPY scripts/verify_deployment_assets.py ./scripts/verify_deployment_assets.py
RUN python scripts/verify_deployment_assets.py --model-only \
    && mkdir -p monitoring && chown appuser:appuser monitoring
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
