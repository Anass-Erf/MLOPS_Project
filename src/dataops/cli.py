"""Small explicit commands for the optional DataOps pathway."""

import argparse
import json
import os
import subprocess

import duckdb

from src.dataops.contract import quality
from src.dataops.dbt_runner import run_dbt
from src.dataops.settings import database, workspace
from src.utils.config import ROOT, load_config


def run_ml(stage: str) -> None:
    python = os.environ.get("CWS_ML_PYTHON", str(ROOT / ".venv/bin/python"))
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MPLBACKEND="Agg")
    subprocess.run([python, "-m", "src.dataops.ml_bridge", stage], env=env, cwd=ROOT, check=True)


def inspect_database() -> None:
    with duckdb.connect(str(database()), read_only=True) as con:
        print(
            con.sql(
                "select table_schema, table_name from information_schema.tables "
                "where table_schema not in ('information_schema', 'pg_catalog') "
                "order by 1, 2"
            )
            .df()
            .to_string(index=False)
        )
        print(
            con.sql(
                "select site_id, count(*) as days, min(observed_on) as first_date, "
                "max(observed_on) as last_date from raw.raw_weather group by site_id"
            )
            .df()
            .to_string(index=False)
        )
        print(
            con.sql(
                "select site_id, observed_on, t2m, snapshot_id, snapshot_sha256 "
                "from raw.raw_weather order by site_id, observed_on limit 5"
            )
            .df()
            .to_string(index=False)
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["dbt", "quality", "inspect", "features", "train", "evaluate", "demo"]
    )
    parser.add_argument(
        "--dbt-command", default="build", choices=["debug", "parse", "run", "test", "build", "docs"]
    )
    args = parser.parse_args()
    cfg = load_config()
    if args.command == "dbt":
        run_dbt(args.dbt_command, cfg, database())
    elif args.command == "quality":
        run_dbt("test", cfg, database())
        print(json.dumps(quality(cfg, database(), workspace() / "weather.csv"), indent=2))
    elif args.command == "inspect":
        inspect_database()
    elif args.command == "demo":
        from dagster import DagsterInstance

        from src.dataops.definitions import defs

        # Persistent instance makes this CLI run visible in make dagster.
        with DagsterInstance.get() as instance:
            result = defs.resolve_job_def("dataops_demo").execute_in_process(instance=instance)
            if not result.success:
                raise RuntimeError("DataOps demo failed")
    else:
        run_ml(args.command)


if __name__ == "__main__":
    main()
