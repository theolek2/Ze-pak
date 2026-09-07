#!/usr/bin/env python3
r"""
Źródło dlt dla ENTSO-E Energy Prices (12.1.D).

Czyta API przez wspólny entsoe_client, pobiera tylko pliki zmienione (wg logu)
i yield'uje wiersze jako dict (dlt nadaje typy i zapisuje do DuckDB).
"""

import csv
import io

import dlt

from entsoe_client import (
    TokenManager,
    fetch_export_log,
    filename_to_folder,
    normalize_filename,
    download_file_content,
)

TARGET = "EnergyPrices_12.1.D_r3.1"


def _parse_rows(text):
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    for r in reader:
        yield {
            "datetime": (r.get("DateTime(UTC)") or "").strip(),
            "resolution_code": (r.get("ResolutionCode") or "").strip(),
            "area_code": (r.get("AreaCode") or "").strip(),
            "area_name": (r.get("AreaDisplayName") or "").strip(),
            "area_type_code": (r.get("AreaTypeCode") or "").strip(),
            "area_map_code": (r.get("AreaMapCode") or "").strip(),
            "contract_type": (r.get("ContractType") or "").strip(),
            "price": (r.get("Price[Currency/MWh]") or "").strip(),
            "currency": (r.get("Currency") or "").strip(),
            "update_time": (r.get("UpdateTime(UTC)") or "").strip(),
        }


@dlt.resource(name="energy_prices", write_disposition="append")
def energy_prices(
    entsoe_username: str = dlt.secrets["entsoe_username"],
    entsoe_password: str = dlt.secrets["entsoe_password"],
    seed: bool = False,
):
    tm = TokenManager(entsoe_username, entsoe_password)
    log = fetch_export_log(tm)

    state = dlt.current.resource_state()
    seen = state.setdefault("files", {})

    files = [r for r in log if filename_to_folder(r["file_name"]) == TARGET]

    for r in files:
        fname = normalize_filename(r["file_name"])
        updated = r["max_update_time"]
        if seed:
            seen[fname] = updated
            continue
        if seen.get(fname) == updated:
            continue
        text = download_file_content(tm, TARGET, fname)
        for row in _parse_rows(text):
            yield row
        seen[fname] = updated
