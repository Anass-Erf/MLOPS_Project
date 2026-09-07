FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
WORKDIR /app
COPY requirements-api.txt requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt -c requirements-lock.txt \
    && useradd --create-home --uid 10001 appuser
COPY src ./src
COPY configs ./configs
COPY models ./models
RUN test -f models/production.json \
    && mkdir -p monitoring && chown appuser:appuser monitoring
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
