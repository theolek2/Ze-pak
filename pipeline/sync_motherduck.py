#!/usr/bin/env python3
"""Synchronizacja kanonicznych tabel analitycznych DuckDB -> MotherDuck.

Tryby:
  - domyślnie: incremental append (dokłada tylko nowe wiersze wg max(ts)),
    z oknem overlap (domyślnie 2 doby) na spóźnione dane;
  - --force: pełna kopia (bootstrap / naprawa);
  - --dry-run: tylko lokalne sygnatury, bez połączenia z MotherDuck.

Token (`MOTHERDUCK_TOKEN`) pochodzi ze środowiska uruchomieniowego.
Skrypt nie zapisuje go nigdzie i nie przyjmuje sekretów jako argumentów.

Uruchomienie w pętli 30-min odbywa się przez pipeline/run_loop.py.
"""

from __future__ import annotations

import argparse
import os
import sys

import duckdb

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DB_PATH = os.path.join(PROJECT_ROOT, "energy.duckdb")

# Tylko gotowe fakty i wymiary; staging techniczny nie trafia do BI.
CANONICAL_TABLES = [
    "dim_area",
    "fct_energy_prices",
    "fct_entsoe_imbalance_prices",
    "fct_entsoe_generation_forecasts",
    "fct_entsoe_aggregated_generation",
    "fct_pse_zmb",
    "fct_pse_cor",
]

# Podzial na zrodla (segregacja ENTSO-E vs PSE).
SOURCE_GROUPS = {
    "entsoe": [
        "dim_area",
        "fct_energy_prices",
        "fct_entsoe_imbalance_prices",
        "fct_entsoe_generation_forecasts",
        "fct_entsoe_aggregated_generation",
    ],
    "pse": [
        "fct_pse_zmb",
        "fct_pse_cor",
    ],
}

# Kolumny watermaku; None = maly slownik (full replace jest tani).
TIMESTAMP_COLUMNS = {
    "dim_area": None,
    "fct_energy_prices": "datetime",
    "fct_entsoe_imbalance_prices": "datetime",
    "fct_entsoe_generation_forecasts": "datetime",
    "fct_entsoe_aggregated_generation": "datetime",
    "fct_pse_zmb": "dtime_utc",
    "fct_pse_cor": "dtime_utc",
}

WATERMARK_TABLE = "_sync_watermark"
DEFAULT_OVERLAP_DAYS = 2


def fail(message: str, code: int = 2) -> int:
    print(message, file=sys.stderr)
    return code


def _resolve_local_catalog(connection) -> str:
    """Znajdź katalog lokalnego pliku (odporne na ATTACH 'md:')."""
    try:
        rows = connection.execute("pragma database_list").fetchall()
        # wiersze: (seq, name, file)
        for row in rows:
            name = row[1] if len(row) > 1 else ""
            file = row[2] if len(row) > 2 else ""
            if file and os.path.abspath(file) == os.path.abspath(LOCAL_DB_PATH):
                return name
        for row in rows:
            name = row[1] if len(row) > 1 else ""
            file = row[2] if len(row) > 2 else ""
            if file and file.endswith("energy.duckdb"):
                return name
    except Exception:
        pass
    return "energy"


def _table_exists(connection, catalog: str, schema: str, table: str) -> bool:
    try:
        connection.execute(
            f'select 1 from "{catalog}"."{schema}"."{table}" limit 0'
        ).fetchall()
        return True
    except Exception:
        return False


def _max_ts(connection, catalog: str, schema: str, table: str, column: str):
    row = connection.execute(
        f'select max("{column}") from "{catalog}"."{schema}"."{table}"'
    ).fetchone()
    return row[0] if row else None


def table_signature(connection, catalog: str, schema: str, table: str):
    """Lekka sygnatura (count, max(ts)) do logów i dry-run. None gdy brak tabeli."""
    if not _table_exists(connection, catalog, schema, table):
        return None
    try:
        count = connection.execute(
            f'select count(*) from "{catalog}"."{schema}"."{table}"'
        ).fetchone()[0]
    except Exception:
        return None

    timestamp_column = TIMESTAMP_COLUMNS.get(table)
    if timestamp_column is None:
        return (count, None)

    try:
        max_value = _max_ts(connection, catalog, schema, table, timestamp_column)
    except Exception:
        return (count, None)
    return (count, str(max_value))


def mirror_table(connection, database: str, table: str, local_catalog: str) -> None:
    """Pełna kopia (bootstrap / --force / mały dim_area)."""
    connection.execute(
        f"CREATE OR REPLACE TABLE {database}.analytics.{table} "
        f'AS SELECT * FROM "{local_catalog}".analytics."{table}"'
    )


def _ensure_watermark_table(connection, database: str) -> None:
    connection.execute(
        f"CREATE TABLE IF NOT EXISTS {database}.analytics.{WATERMARK_TABLE} ("
        "table_name VARCHAR PRIMARY KEY, "
        "remote_max VARCHAR, "
        "updated_at TIMESTAMPTZ DEFAULT now())"
    )


def _set_watermark(connection, database: str, table: str, remote_max) -> None:
    connection.execute(
        f"INSERT INTO {database}.analytics.{WATERMARK_TABLE} "
        "(table_name, remote_max, updated_at) VALUES (?, ?, now()) "
        "ON CONFLICT (table_name) DO UPDATE SET "
        "remote_max=excluded.remote_max, updated_at=now()",
        [table, str(remote_max)],
    )


def sync_table_incremental(
    connection,
    local_catalog: str,
    database: str,
    table: str,
    overlap_days: int = DEFAULT_OVERLAP_DAYS,
    force: bool = False,
) -> tuple[str, str]:
    """Dokłada tylko nowe wiersze. Zwraca (akcja, opis).

    Akcje: 'full-copy' | 'append' | 'skip' | 'replace-small'.
    """
    ts_col = TIMESTAMP_COLUMNS.get(table)

    # Mały słownik bez watermaku — pełne podmienienie jest tanie (~50 wierszy).
    if ts_col is None:
        if not _table_exists(connection, database, "analytics", table) or force:
            mirror_table(connection, database, table, local_catalog)
            return ("replace-small", "podmieniono slownik")
        local = table_signature(connection, local_catalog, "analytics", table)
        remote = table_signature(connection, database, "analytics", table)
        if local == remote and not force:
            return ("skip", f"bez zmian {local}")
        mirror_table(connection, database, table, local_catalog)
        return ("replace-small", f"podmieniono slownik {remote} -> {local}")

    if force or not _table_exists(connection, database, "analytics", table):
        mirror_table(connection, database, table, local_catalog)
        new_max = _max_ts(connection, local_catalog, "analytics", table, ts_col)
        _ensure_watermark_table(connection, database)
        _set_watermark(connection, database, table, new_max)
        return ("full-copy", f"bootstrap/force, max={new_max}")

    remote_max = _max_ts(connection, database, "analytics", table, ts_col)
    if remote_max is None:
        mirror_table(connection, database, table, local_catalog)
        new_max = _max_ts(connection, local_catalog, "analytics", table, ts_col)
        _ensure_watermark_table(connection, database)
        _set_watermark(connection, database, table, new_max)
        return ("full-copy", f"zdalny pusty, max={new_max}")

    # Ile lokalnie jest kandydatów powyżej okna overlap?
    overlap = max(int(overlap_days), 0)
    candidate = connection.execute(
        f'SELECT COUNT(*) FROM "{local_catalog}".analytics."{table}" '
        f'WHERE "{ts_col}" > CAST(? AS TIMESTAMPTZ) - INTERVAL (?) DAY',
        [str(remote_max), overlap],
    ).fetchone()[0]
    if candidate == 0:
        return ("skip", f"bez zmian, remote_max={remote_max}")

    # DELETE okna + INSERT (idempotentne na spóźnione dane).
    connection.execute(
        f'DELETE FROM {database}.analytics."{table}" '
        f'WHERE "{ts_col}" > CAST(? AS TIMESTAMPTZ) - INTERVAL (?) DAY',
        [str(remote_max), overlap],
    )
    connection.execute(
        f'INSERT INTO {database}.analytics."{table}" '
        f'SELECT * FROM "{local_catalog}".analytics."{table}" '
        f'WHERE "{ts_col}" > CAST(? AS TIMESTAMPTZ) - INTERVAL (?) DAY',
        [str(remote_max), overlap],
    )
    inserted = candidate
    new_max = _max_ts(connection, database, "analytics", table, ts_col)
    _ensure_watermark_table(connection, database)
    _set_watermark(connection, database, table, new_max)
    return ("append", f"doklejono ~{inserted} wierszy, remote_max={remote_max} -> {new_max}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Synchronizacja tabel analytics do MotherDuck "
        "(domyslnie incremental append)."
    )
    parser.add_argument(
        "--database",
        default="energy_lightdash_test",
        help="Docelowa baza MotherDuck.",
    )
    parser.add_argument(
        "--tables",
        nargs="*",
        default=CANONICAL_TABLES,
        help="Podzbior tabel kanonicznych do synchronizacji.",
    )
    parser.add_argument(
        "--source",
        choices=["entsoe", "pse"],
        default=None,
        help="Zawez do zrodla: entsoe albo pse (dziala z --tables).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pokaz lokalne sygnatury bez zapisu do MotherDuck (offline).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Pelna kopia zamiast append (bootstrap / naprawa).",
    )
    parser.add_argument(
        "--overlap-days",
        type=int,
        default=DEFAULT_OVERLAP_DAYS,
        help="Okno re-sync na spoznione dane (domyslnie 2 doby).",
    )
    args = parser.parse_args(argv)

    tables = list(args.tables)
    if args.source:
        tables = [t for t in tables if t in SOURCE_GROUPS[args.source]]
        if not tables:
            return fail(f"Zrodlo {args.source} nie ma tabel w wyborze --tables.")

    unknown = sorted(set(tables) - set(CANONICAL_TABLES))
    if unknown:
        return fail(f"Nieznane tabele: {', '.join(unknown)}.")

    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token and not args.dry_run:
        return fail(
            "Brak MOTHERDUCK_TOKEN w srodowisku. "
            "Synchronizacja przerwana bez zmian."
        )

    connection = duckdb.connect(LOCAL_DB_PATH)
    try:
        connection.execute("SET TimeZone='UTC'")
        local_catalog = _resolve_local_catalog(connection)

        if args.dry_run:
            for table in tables:
                local = table_signature(connection, local_catalog, "analytics", table)
                if local is None:
                    print(f"[dry-run] {table}: BRAK lokalnej tabeli")
                else:
                    mode = "full/slownik" if TIMESTAMP_COLUMNS.get(table) is None else (
                        f"append od max(local)={local[1]}, overlap={args.overlap_days}d"
                    )
                    print(f"[dry-run] {table}: local={local} -> {mode}")
            print("Dry run OK. Nic nie zapisano do MotherDuck.")
            return 0

        connection.execute("INSTALL motherduck")
        connection.execute("LOAD motherduck")
        connection.execute("ATTACH 'md:'")
        connection.execute(f"CREATE DATABASE IF NOT EXISTS {args.database}")
        connection.execute(
            f"CREATE SCHEMA IF NOT EXISTS {args.database}.analytics"
        )

        actions: list[str] = []
        for table in tables:
            local = table_signature(connection, local_catalog, "analytics", table)
            if local is None:
                return fail(f"Brak lokalnej tabeli analytics.{table}.")
            action, detail = sync_table_incremental(
                connection,
                local_catalog,
                args.database,
                table,
                overlap_days=args.overlap_days,
                force=args.force,
            )
            print(f"[{action}] {table}: {detail}", flush=True)
            actions.append(f"{table}={action}")

        print(f"Sync OK: {', '.join(actions)}.")
        return 0
    except Exception as exc:
        return fail(
            "Synchronizacja nie powiodla sie: "
            f"{type(exc).__name__}: {str(exc)[:300]}."
        )
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
