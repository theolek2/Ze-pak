#!/usr/bin/env python3
r"""
Orchestrator pipeline'ów dlt: ENTSO-E + PSE -> DuckDB (energy.duckdb).

Użycie:
  .venv\Scripts\python.exe run_pipeline.py                    # pobierz zmiany (entsoe + pse)
  .venv\Scripts\python.exe run_pipeline.py --seed             # baseline (bez pobierania) obu źródeł
  .venv\Scripts\python.exe run_pipeline.py --pse-only         # tylko PSE
  .venv\Scripts\python.exe run_pipeline.py --pse-only --date 2026-09-08       # PSE: jedna doba
  .venv\Scripts\python.exe run_pipeline.py --pse-only --from-date 2026-09-06  # PSE: od daty do dziś
  .venv\Scripts\python.exe run_pipeline.py --pse-only --backfill-days 2       # PSE: wstecz N dni
"""

import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone

import dlt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
sys.path.insert(0, PROJECT_ROOT)

from sources.entsoe.entsoe_source import energy_prices
from sources.pse.pse_source import pse_source

DUCKDB_PATH = os.path.join(PROJECT_ROOT, "energy.duckdb")


def _dest():
    return dlt.destinations.duckdb(DUCKDB_PATH)


def run_entsoe(seed):
    pipeline = dlt.pipeline(
        pipeline_name="entsoe", destination=_dest(), dataset_name="raw"
    )
    pipeline.run(energy_prices(seed=seed))


def run_pse(seed, incremental_start, dates):
    pipeline = dlt.pipeline(
        pipeline_name="pse", destination=_dest(), dataset_name="raw_pse"
    )
    pipeline.run(pse_source(seed=seed, incremental_start=incremental_start, dates=dates))


def _dates_from_range(from_date):
    today = date.today()
    days = []
    d = from_date
    while d <= today:
        days.append(d.isoformat())
        d += timedelta(days=1)
    return days


def main():
    parser = argparse.ArgumentParser(description="Orchestrator dlt (ENTSO-E + PSE) -> DuckDB")
    parser.add_argument("--seed", action="store_true", help="baseline (bez pobierania)")
    parser.add_argument("--backfill-days", type=int, default=None,
                        help="PSE: rekordy opublikowane w ciągu ostatnich N dni")
    parser.add_argument("--date", default=None,
                        help="PSE: pobierz jedną dobę handlową (YYYY-MM-DD)")
    parser.add_argument("--from-date", default=None,
                        help="PSE: pobierz od doby do dziś (YYYY-MM-DD)")
    parser.add_argument("--entsoe-only", action="store_true", help="tylko entsoe")
    parser.add_argument("--pse-only", action="store_true", help="tylko pse")
    args = parser.parse_args()

    incremental_start = None
    if args.backfill_days:
        start = datetime.now(timezone.utc) - timedelta(days=args.backfill_days)
        incremental_start = start.strftime("%Y-%m-%d %H:%M:%S")

    dates = None
    if args.date:
        dates = [args.date]
    elif args.from_date:
        dates = _dates_from_range(datetime.strptime(args.from_date, "%Y-%m-%d").date())

    if not args.pse_only:
        print("=== ENTSO-E ===", flush=True)
        run_entsoe(seed=args.seed)
    if not args.entsoe_only:
        print("=== PSE ===", flush=True)
        run_pse(seed=args.seed, incremental_start=incremental_start, dates=dates)


if __name__ == "__main__":
    main()
