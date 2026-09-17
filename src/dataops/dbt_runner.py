"""Run the real dbt CLI with project-local paths and deterministic configuration."""

import json
import os
import subprocess
import sys
from pathlib import Path

from src.utils.config import ROOT


def run_dbt(command: str, cfg: dict, db: Path) -> None:
    allowed = {"debug", "parse", "run", "test", "build", "docs"}
    if command not in allowed:
        raise ValueError(f"Expected one of {sorted(allowed)}")
    env = dict(os.environ)
    env.update(
        CWS_DUCKDB_PATH=str(db),
        DBT_SEND_ANONYMOUS_USAGE_STATS="false",
        DBT_LOG_PATH=str(db.parent / "dbt_logs"),
        DBT_TARGET_PATH=str(db.parent / "dbt_target"),
    )
    args = [str(Path(sys.executable).parent / "dbt"), command]
    if command == "docs":
        args.append("generate")
    args.extend(
        [
            "--project-dir",
            str(ROOT / "dbt_project"),
            "--profiles-dir",
            str(ROOT / "dbt_project"),
            "--vars",
            json.dumps(
                {
                    "known_sites": [s["id"] for s in cfg["data"]["sites"]],
                    "weather_start": cfg["data"]["start"],
                    "weather_end": cfg["data"]["end"],
                }
            ),
        ]
    )
    subprocess.run(args, cwd=ROOT, env=env, check=True)
