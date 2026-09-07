"""Hashes and stage receipts are the lightweight alternative to DVC."""

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from src.utils.config import ROOT, get_path


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_hash(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def source_hash() -> str:
    return object_hash(
        {str(p.relative_to(ROOT)): file_hash(p) for p in sorted((ROOT / "src").rglob("*.py"))}
    )


def receipt(cfg: dict, stage: str, inputs: list[Path], outputs: list[Path]) -> None:
    write_json(
        get_path(cfg, "artifacts") / "provenance" / f"{stage}.json",
        {
            "stage": stage,
            "utc": datetime.now(timezone.utc).isoformat(),
            "config_sha256": object_hash(cfg),
            "source_sha256": source_hash(),
            "python": platform.python_version(),
            "inputs": {str(p.relative_to(ROOT)): file_hash(p) for p in inputs},
            "outputs": {str(p.relative_to(ROOT)): file_hash(p) for p in outputs},
        },
    )
