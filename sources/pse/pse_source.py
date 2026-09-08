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

ENTITIES = {
    "zmb": {"endpoint": "zmb", "incremental": "publication_ts_utc"},
    "cor": {"endpoint": "cor", "incremental": "publication_ts_utc"},
    # przykłady encji z drugą strategią (filtr publication_ts_utc na nich timeoutuje):
    # "poeb_rbb": {"endpoint": "poeb-rbb", "incremental": "business_date"},
    # "pomb_rbn": {"endpoint": "pomb-rbn", "incremental": "business_date"},
}

# domyślny lookback dni dla strategii "business_date" (bez jawnie podanych dat)
DEFAULT_LOOKBACK_DAYS = 3


def _last_days(n):
    today = date.today()
    return [(today - timedelta(days=i)).isoformat() for i in range(n)]


def _make_resource(entity_name, cfg):
    endpoint = cfg["endpoint"]
    incremental = cfg.get("incremental", "publication_ts_utc")

    @dlt.resource(name=entity_name, write_disposition="append")
    def gen(seed=False, incremental_start=None, dates=None):
        state = dlt.current.resource_state()

        if seed:
            state["last_publication_ts_utc"] = utc_now_str()
            return

        # 1) jawnie podane daty (--date / --from-date) -> pobierz te doby
        if dates:
            for d in dates:
                for row in fetch(endpoint, filter=f"business_date eq '{d}'"):
                    yield row
            return

        # 2) incremental wg strategii encji
        if incremental == "business_date":
            for d in _last_days(DEFAULT_LOOKBACK_DAYS):
                for row in fetch(endpoint, filter=f"business_date eq '{d}'"):
                    yield row
        else:  # "publication_ts_utc"
            last_ts = incremental_start or state.get("last_publication_ts_utc")
            if not last_ts:
                return  # brak baseline -> nic nie pobieramy (ochrona przed pełną historią)
            max_ts = last_ts
            try:
                for row in fetch(endpoint, filter=f"publication_ts_utc gt '{last_ts}'"):
                    yield row
                    ts = row.get("publication_ts_utc")
                    if ts and ts > max_ts:
                        max_ts = ts
            except Exception as e:
                print(f"  [pse:{entity_name}] błąd, pomijam: {type(e).__name__}", file=sys.stderr)
            state["last_publication_ts_utc"] = max_ts

    return gen


@dlt.source(name="pse")
def pse_source(seed: bool = False, incremental_start: str = None, dates: list = None):
    for entity_name, cfg in ENTITIES.items():
        yield _make_resource(entity_name, cfg)(
            seed=seed, incremental_start=incremental_start, dates=dates
        )
