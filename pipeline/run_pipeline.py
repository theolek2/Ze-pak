#!/usr/bin/env python3
r"""
Pipeline dlt: ładuje dane ENTSO-E do DuckDB (energy.duckdb).

Pobiera tylko pliki zmienione od ostatniego uruchomienia (wg logu Export_log_r3.csv).

Użycie:
  .venv\Scripts\python.exe run_pipeline.py            # pobierz tylko zmienione pliki
  .venv\Scripts\python.exe run_pipeline.py --seed     # baseline: oznacz wszystkie jako pobrane (bez pobierania)
"""

import argparse
import os

import dlt

from entsoe_source import energy_prices

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

PIPELINE_NAME = "entsoe"
DATASET = "raw"
DUCKDB_PATH = os.path.join(PROJECT_ROOT, "energy.duckdb")


def run(seed=False):
    pipeline = dlt.pipeline(
        pipeline_name=PIPELINE_NAME,
        destination=dlt.destinations.duckdb(DUCKDB_PATH),
        dataset_name=DATASET,
    )
    info = pipeline.run(energy_prices(seed=seed))
    print(info)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline dlt ENTSO-E -> DuckDB")
    parser.add_argument("--seed", action="store_true",
                        help="baseline: oznacz wszystkie pliki jako pobrane bez pobierania")
    args = parser.parse_args()
    run(seed=args.seed)
