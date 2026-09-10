#!/usr/bin/env python3
r"""
Źródło dlt dla PSE (Raporty OSP / Market Data).

Generyczne: każda encja = jeden @dlt.resource -> tabela raw_pse.<encja>.
Dwie strategie incremental (wybór per encja w ENTITIES):
  - "publication_ts_utc" -> $filter=publication_ts_utc gt '<last>'  (szybkie encje, domyślna)
  - "business_date"      -> pętla po dniach $filter=business_date eq '<dzien>'  (ciężkie oferty)

Dodanie kolejnej encji = jedna linia w ENTITIES. Nic nie jest zahardkodowane do jednej tabeli.
"""

import sys
from datetime import date, timedelta

import dlt

from .pse_client import fetch, utc_now_str
from ..common.datetime_utc import format_utc_api, parse_utc_datetime

ENTITIES = {
    "zmb": {
        "endpoint": "zmb",
        "incremental": "publication_ts_utc",
        "timestamp_columns": ["dtime_utc", "publication_ts_utc"],
    },
    "cor": {
        "endpoint": "cor",
        "incremental": "publication_ts_utc",
        "timestamp_columns": ["dtime_utc", "publication_ts_utc"],
    },
    # przykłady encji z drugą strategią (filtr publication_ts_utc na nich timeoutuje):
    # "poeb_rbb": {
    #     "endpoint": "poeb-rbb",
    #     "incremental": "business_date",
    #     "timestamp_columns": ["dtime_utc", "publication_ts_utc"],
    # },
    # "pomb_rbn": {
    #     "endpoint": "pomb-rbn",
    #     "incremental": "business_date",
    #     "timestamp_columns": ["dtime_utc", "publication_ts_utc"],
    # },
}

# domyślny lookback dni dla strategii "business_date" (bez jawnie podanych dat)
DEFAULT_LOOKBACK_DAYS = 3


def _last_days(n):
    today = date.today()
    return [(today - timedelta(days=i)).isoformat() for i in range(n)]


def _normalize_timestamps(row, endpoint, timestamp_columns):
    normalized = dict(row)
    for field in timestamp_columns:
        normalized[field] = parse_utc_datetime(
            normalized.get(field),
            field=field,
            source=f"pse/{endpoint}",
        )
    return normalized


def _last_publication_timestamp(row, endpoint):
    return parse_utc_datetime(
        row.get("publication_ts_utc"),
        field="publication_ts_utc",
        source=f"pse/{endpoint}",
    )


def _make_resource(entity_name, cfg):
    endpoint = cfg["endpoint"]
    incremental = cfg.get("incremental", "publication_ts_utc")
    timestamp_columns = cfg.get(
        "timestamp_columns", ["dtime_utc", "publication_ts_utc"]
    )
    columns = {
        field: {"data_type": "timestamp", "timezone": True}
        for field in timestamp_columns
    }

    @dlt.resource(name=entity_name, write_disposition="append", columns=columns)
    def gen(seed=False, incremental_start=None, dates=None):
        state = dlt.current.resource_state()

        if seed:
            state["last_publication_ts_utc"] = utc_now_str()
            return

        # 1) jawnie podane daty (--date / --from-date) -> pobierz te doby
        if dates:
            for d in dates:
                rows = list(fetch(endpoint, filter=f"business_date eq '{d}'"))
                for raw in rows:
                    yield _normalize_timestamps(raw, endpoint, timestamp_columns)
            return

        # 2) incremental wg strategii encji
        if incremental == "business_date":
            for d in _last_days(DEFAULT_LOOKBACK_DAYS):
                rows = list(fetch(endpoint, filter=f"business_date eq '{d}'"))
                for raw in rows:
                    yield _normalize_timestamps(raw, endpoint, timestamp_columns)
        else:  # "publication_ts_utc"
            last_raw = incremental_start or state.get("last_publication_ts_utc")
            if not last_raw:
                return  # brak baseline -> nic nie pobieramy (ochrona przed pełną historią)
            last_ts = parse_utc_datetime(
                last_raw,
                field="publication_ts_utc",
                source=f"pse/{endpoint}",
            )
            max_ts = last_ts
            try:
                rows = list(
                    fetch(
                        endpoint,
                        filter=f"publication_ts_utc gt '{format_utc_api(last_ts)}'",
                    )
                )
            except Exception as e:
                print(f"  [pse:{entity_name}] błąd, pomijam: {type(e).__name__}", file=sys.stderr)
                return
            for raw in rows:
                row = _normalize_timestamps(raw, endpoint, timestamp_columns)
                yield row
                publication = _last_publication_timestamp(row, endpoint)
                if publication > max_ts:
                    max_ts = publication
            state["last_publication_ts_utc"] = format_utc_api(max_ts)

    return gen


@dlt.source(name="pse")
def pse_source(seed: bool = False, incremental_start: str = None, dates: list = None):
    for entity_name, cfg in ENTITIES.items():
        yield _make_resource(entity_name, cfg)(
            seed=seed, incremental_start=incremental_start, dates=dates
        )
