"""UI validation and HTTP helpers; no model or feature-engineering imports."""

import json
from pathlib import Path
from typing import get_args

import pandas as pd
import requests
from pydantic import ValidationError

from src.api.schemas import PredictionRequest, PredictionResponse

EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "example_request.json"
CROPS = get_args(PredictionRequest.model_fields["crop"].annotation)
SITES = get_args(PredictionRequest.model_fields["site_id"].annotation)


class UIError(ValueError):
    """A short error suitable for display to a user."""


def validation_message(errors: list[dict]) -> str:
    messages = []
    for error in errors[:3]:
        location = ".".join(str(part) for part in error.get("loc", []) if part != "body")
        if error.get("type") == "missing":
            messages.append(f"Missing required field: {location}")
        else:
            message = error.get("msg", "Invalid value").removeprefix("Value error, ")
            messages.append(f"{location}: {message}" if location else message)
    return "; ".join(messages)


def validate_request(payload: object) -> dict:
    try:
        return PredictionRequest.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise UIError(validation_message(exc.errors())) from exc


def parse_request(contents: str | bytes) -> dict:
    try:
        payload = json.loads(contents)
    except (ValueError, UnicodeError) as exc:
        raise UIError("Invalid JSON. Upload a UTF-8 JSON prediction request.") from exc
    return validate_request(payload)


def load_example(path: Path = EXAMPLE_PATH) -> dict:
    try:
        return parse_request(path.read_bytes())
    except OSError as exc:
        raise UIError(
            "Cannot read artifacts/example_request.json. Restore the example artifact."
        ) from exc


def history_frame(payload: dict) -> pd.DataFrame:
    frame = pd.DataFrame(payload["history"])
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def request_from_frame(crop: str, site_id: str, frame: pd.DataFrame) -> dict:
    return validate_request({"crop": crop, "site_id": site_id, "history": frame.to_dict("records")})


def api_json(base_url: str, endpoint: str, payload: dict | None = None) -> object:
    try:
        url = f"{base_url.rstrip('/')}/{endpoint}"
        if payload is None:
            response = requests.get(url, timeout=(2, 3))
        else:
            response = requests.post(url, json=payload, timeout=(3, 30))
    except requests.Timeout as exc:
        raise UIError("The API timed out. Check that it is running, then try again.") from exc
    except requests.RequestException as exc:
        raise UIError("Cannot connect to the API. Start it with make api, then retry.") from exc
    if response.status_code == 503:
        raise UIError("The API is running but its production model is unavailable. Check API logs.")
    if response.status_code == 422:
        try:
            detail = response.json()["detail"]
            message = validation_message(detail) if isinstance(detail, list) else str(detail)
        except (ValueError, KeyError, TypeError, AttributeError):
            message = "Check the weather values, dates and required history length."
        raise UIError(f"The API rejected this request: {message}")
    if not response.ok:
        raise UIError(f"The API returned HTTP {response.status_code}. Check API logs and retry.")
    try:
        return response.json()
    except ValueError as exc:
        raise UIError("Unexpected API response: expected JSON.") from exc


def check_health(base_url: str) -> dict:
    health = api_json(base_url, "health")
    if not isinstance(health, dict) or health.get("status") != "ok":
        raise UIError("Unexpected health response. Check the configured API address.")
    return health


def predict(base_url: str, payload: dict) -> PredictionResponse:
    response = api_json(base_url, "predict", validate_request(payload))
    try:
        return PredictionResponse.model_validate(response)
    except ValidationError as exc:
        raise UIError("Unexpected prediction response: missing or invalid result fields.") from exc
