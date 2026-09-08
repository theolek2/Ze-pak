#!/usr/bin/env python3
r"""
Źródło dlt dla PSE (Tor A: zakup + dostawy + ceny bilansowania).

Konfiguracyjna lista encji -> jedna tabela raw_pse.<encja> na encję.
Incremental po publication_ts_utc (pobiera tylko nowe/korygowane rekordy).
Brak pełnej historii: start "na żywo" (--seed) albo wstecz o N dni (--backfill-days).

Uwaga: encje "oferty" (poeb-*, pomb-rbn, popmb-rmb, oeb-bpkdbo) są NIEAKTUALNE
(ostatnie dane ~2024) lub ciężkie (timeout) — wykluczone z MVP, patrz docs/pse_endpoints.md.
"""

import sys

import dlt

from .pse_client import fetch, utc_now_str

# nazwa tabeli -> endpoint API (myślniki w API, podkreślenia w tabeli)
# Tylko encje AKTUALNE (dane 2026) i działające bez timeoutów.
ENTITIES = {
    # dostawy energii bilansującej (USE - sprzedaż)
    "use_sprz_rbb": "use-sprz-rbb",
    "use_sprz_rbn": "use-sprz-rbn",
    # zakup mocy bilansującej (co kupiono / po ile)
    "mbp_tp": "mbp-tp",
    "cmbp_tp": "cmbp-tp",
    # zapotrzebowanie na moce bilansujące (RMB)
    "zmb": "zmb",
    # koszty bilansowania
    "kmb_kro_rozl": "kmb-kro-rozl",
    # ceny bilansowania
    "codn": "codn",
    "cor": "cor",
    "csdac_pln": "csdac-pln",
    "price_fcst": "price-fcst",
}


# type hints, żeby kolumny produktów zawsze się materializowały (nawet gdy NULL w danym oknie)
COLUMN_HINTS = {
    "mbp_tp": {c: {"data_type": "double"} for c in ["fcr_g", "fcr_d", "afrr_g", "afrr_d", "mfrrd_g", "mfrrd_d", "rr_g", "rr_d"]},
    "cmbp_tp": {c: {"data_type": "double"} for c in ["fcr_g", "fcr_d", "afrr_g", "afrr_d", "mfrrd_g", "mfrrd_d", "rr_g", "rr_d"]},
    "zmb": {c: {"data_type": "double"} for c in ["zmb_fcrg", "zmb_fcrd", "zmb_frrg", "zmb_frrd", "zmb_afrrg", "zmb_afrrd", "zmb_rrg", "zmb_rrd"]},
}


def _make_resource(entity_name, endpoint):
    @dlt.resource(name=entity_name, write_disposition="append",
                  columns=COLUMN_HINTS.get(entity_name))
    def gen(seed=False, incremental_start=None):
        state = dlt.current.resource_state()

        if seed:
            state["last_publication_ts_utc"] = utc_now_str()
            return

        last_ts = incremental_start or state.get("last_publication_ts_utc")
        if not last_ts:
            return  # brak baseline -> nie pobieramy nic (ochrona przed pełną historią)

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
def pse_source(seed: bool = False, incremental_start: str = None):
    for entity_name, endpoint in ENTITIES.items():
        yield _make_resource(entity_name, endpoint)(
            seed=seed, incremental_start=incremental_start
        )
