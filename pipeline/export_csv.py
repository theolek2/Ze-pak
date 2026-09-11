#!/usr/bin/env python3
"""Eksport martow analytics -> CSV per instrument x rok (do analizy w Pythonie).

Uzycie:
  python pipeline/export_csv.py --years 2025 2026
  python pipeline/export_csv.py --years 2025 2026 --tables fct_energy_prices
  python pipeline/export_csv.py --out export

Wynik: export/<tabela>_<rok>.csv (z naglowkiem).
Odczyt read-only - bezpieczny rownolegle z dzialajacym pipelinem.
"""

from __future__ import annotations

import argparse
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DB_PATH = os.path.join(PROJECT_ROOT, "energy.duckdb")

TABLES = [
    "fct_energy_prices",
    "fct_entsoe_imbalance_prices",
    "fct_entsoe_generation_forecasts",
    "fct_entsoe_aggregated_generation",
]
TIME_COL = "datetime"  # wszystkie 4 fakty maja kolumne datetime (UTC)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Eksport analytics -> CSV per rok.")
    ap.add_argument("--years", nargs="+", default=["2025", "2026"])
    ap.add_argument("--tables", nargs="*", default=TABLES)
    ap.add_argument("--out", default=os.path.join(PROJECT_ROOT, "export"))
    args = ap.parse_args(argv)

    unknown = sorted(set(args.tables) - set(TABLES))
    if unknown:
        print(f"Nieznane tabele: {', '.join(unknown)}", file=sys.stderr)
        return 2

    import duckdb

    os.makedirs(args.out, exist_ok=True)
    con = duckdb.connect(LOCAL_DB_PATH, read_only=True)
    try:
        con.execute("SET TimeZone='UTC'")
        for table in args.tables:
            exists = con.execute(
                "select count(*) from information_schema.tables "
                "where table_schema='analytics' and table_name=?",
                [table],
            ).fetchone()[0]
            if not exists:
                print(f"[SKIP] analytics.{table} nie istnieje (backfill w toku?)")
                continue
            for year in args.years:
                path = os.path.join(args.out, f"{table}_{year}.csv")
                con.execute(
                    f"COPY (SELECT * FROM analytics.\"{table}\" "
                    f"WHERE \"{TIME_COL}\" >= '{year}-01-01' "
                    f"AND \"{TIME_COL}\" < '{int(year) + 1}-01-01' "
                    f"ORDER BY \"{TIME_COL}\") "
                    f"TO '{path}' (HEADER, DELIMITER ',')"
                )
                n = con.execute(
                    f"SELECT COUNT(*) FROM analytics.\"{table}\" "
                    f"WHERE \"{TIME_COL}\" >= '{year}-01-01' "
                    f"AND \"{TIME_COL}\" < '{int(year) + 1}-01-01'"
                ).fetchone()[0]
                print(f"[OK] {os.path.basename(path)}: {n} wierszy")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
