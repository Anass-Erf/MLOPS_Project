"""FastAPI with explicit readiness, validated requests and local monitoring events."""

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.schemas import PredictionRequest, PredictionResponse
from src.models.predict import Predictor
from src.utils.config import get_path, load_config, resolve
from src.utils.logger import get_logger

LOG = get_logger(__name__)


def create_app(model_path: Path | None = None, event_path: Path | None = None) -> FastAPI:
    cfg = load_config()
    pointer = model_path or resolve(
        os.environ.get("CWS_MODEL_PATH", str(get_path(cfg, "models") / "production.json"))
    )
    events = event_path or resolve(
        os.environ.get("CWS_MONITOR_LOG", str(get_path(cfg, "monitoring") / "events.jsonl"))
    )

    def record(event: dict):
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        try:
            events.parent.mkdir(parents=True, exist_ok=True)
            with events.open("a") as handle:
                handle.write(json.dumps(event, default=str, allow_nan=False) + "\n")
        except OSError:
            LOG.exception("Failed to write monitoring event")

    @asynccontextmanager
    async def lifespan(app):
        app.state.predictor = None
        try:
            app.state.predictor = Predictor(pointer)
            LOG.info("Loaded %s", app.state.predictor.metadata["model_version"])
        except Exception:
            LOG.exception("Model unavailable; health will return 503")
        yield

    app = FastAPI(
        title="Prédiction du stress hydrique des cultures",
        version="0.1.0",
        description="Next-day wheat stress proxy for configured Moroccan sites. "
        "Supply 30 days of weather; soil scenario is attached to the site.",
        lifespan=lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        # Do not log malformed raw bodies or echo nonfinite input values.
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        record({"event": "invalid_input", "path": request.url.path, "errors": errors})
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.get("/")
    def information():
        return {
            "name": app.title,
            "docs": "/docs",
            "target": "next_day_1_minus_Ks_proxy",
            "history_days": 30,
            "crop": "wheat",
            "labels": "modeled, not field measured",
        }

    @app.get("/health")
    def health():
        predictor = app.state.predictor
        if predictor is None:
            raise HTTPException(
                status_code=503, detail="Model unavailable; run training and promotion"
            )
        return {"status": "ok", "model_version": predictor.metadata["model_version"]}

    @app.post("/predict", response_model=PredictionResponse)
    def predict(payload: PredictionRequest):
        if app.state.predictor is None:
            raise HTTPException(status_code=503, detail="Model unavailable")
        try:
            response, features = app.state.predictor.predict(payload)
        except ValueError as exc:
            record({"event": "invalid_input", "reason": str(exc)})
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        record(
            {
                "event": "prediction",
                "request_id": str(uuid4()),
                "site_id": payload.site_id,
                **response,
                "features": features.iloc[0].to_dict(),
            }
        )
        return PredictionResponse(**response)

    return app


app = create_app()
