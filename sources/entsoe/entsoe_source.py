#!/usr/bin/env python3
r"""
Źródło dlt dla ENTSO-E Energy Prices (12.1.D).

Czyta API przez wspólny entsoe_client, pobiera tylko pliki zmienione (wg logu)
i yield'uje wiersze jako dict (dlt nadaje typy i zapisuje do DuckDB).
"""

import csv
import io

import dlt

from ..common.datetime_utc import parse_utc_datetime
from .entsoe_client import (
    TokenManager,
    fetch_export_log,
    filename_to_folder,
    normalize_filename,
    download_file_content,
)

TIMESTAMP_COLUMNS = {
    "datetime": {"data_type": "timestamp", "timezone": True},
    "update_time": {"data_type": "timestamp", "timezone": True},
}

IMBALANCE_PRICE_FIELDS = (
    "PositiveImbalancePrice[Currency/MWh]",
    "PositiveScarcity[Currency/MWh]",
    "PositiveIncentive[Currency/MWh]",
    "PositiveFinancialNeutrality[Currency/MWh] ",
    "NegativeImbalancePrice[Currency/MWh]",
    "NegativeScarcity[Currency/MWh]",
    "NegativeIncentive[Currency/MWh]",
    "NegativeFinancialNeutrality[Currency/MWh]",
)


def _text(row, name):
    return (row.get(name) or "").strip()


def _parse_energy_rows(text):
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    for r in reader:
        yield {
            "datetime": parse_utc_datetime(
                r.get("DateTime(UTC)"),
                field="DateTime(UTC)",
                source="entsoe",
            ),
            "resolution_code": _text(r, "ResolutionCode"),
            "area_code": _text(r, "AreaCode"),
            "area_name": _text(r, "AreaDisplayName"),
            "area_type_code": _text(r, "AreaTypeCode"),
            "area_map_code": _text(r, "AreaMapCode"),
            "contract_type": _text(r, "ContractType"),
            "price": _text(r, "Price[Currency/MWh]"),
            "currency": _text(r, "Currency"),
            "update_time": parse_utc_datetime(
                r.get("UpdateTime(UTC)"),
                field="UpdateTime(UTC)",
                source="entsoe",
                required=False,
            ),
        }


def _parse_imbalance_rows(text):
    field_map = {
        "PositiveImbalancePrice[Currency/MWh]": "positive_imbalance_price",
        "PositiveScarcity[Currency/MWh]": "positive_scarcity_price",
        "PositiveIncentive[Currency/MWh]": "positive_incentive_price",
        "PositiveFinancialNeutrality[Currency/MWh] ": "positive_financial_neutrality_price",
        "NegativeImbalancePrice[Currency/MWh]": "negative_imbalance_price",
        "NegativeScarcity[Currency/MWh]": "negative_scarcity_price",
        "NegativeIncentive[Currency/MWh]": "negative_incentive_price",
        "NegativeFinancialNeutrality[Currency/MWh]": "negative_financial_neutrality_price",
    }
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    for r in reader:
        row = {
            "datetime": parse_utc_datetime(
                r.get("DateTime(UTC)"),
                field="DateTime(UTC)",
                source="entsoe",
            ),
            "resolution_code": _text(r, "ResolutionCode"),
            "area_code": _text(r, "AreaCode"),
            "area_name": _text(r, "AreaDisplayName"),
            "area_type_code": _text(r, "AreaTypeCode"),
            "area_map_code": _text(r, "AreaMapCode"),
            "currency": _text(r, "Currency"),
            "status": _text(r, "Status"),
            "update_time": parse_utc_datetime(
                r.get("UpdateTime(UTC)"),
                field="UpdateTime(UTC)",
                source="entsoe",
                required=False,
            ),
        }
        for source_field, target_field in field_map.items():
            row[target_field] = _text(r, source_field)
        yield row


def _parse_generation_forecast_rows(text):
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    for r in reader:
        yield {
            "datetime": parse_utc_datetime(
                r.get("DateTime(UTC)"),
                field="DateTime(UTC)",
                source="entsoe",
            ),
            "resolution_code": _text(r, "ResolutionCode"),
            "area_code": _text(r, "AreaCode"),
            "area_name": _text(r, "AreaDisplayName"),
            "area_type_code": _text(r, "AreaTypeCode"),
            "area_map_code": _text(r, "AreaMapCode"),
            "production_type": _text(r, "ProductionType"),
            "day_ahead_generation_forecast_mw": _text(
                r, "DayAheadGenerationForecast[MW]"
            ),
            "intraday_generation_forecast_mw": _text(
                r, "IntradayGenerationForecast[MW]"
            ),
            "current_generation_forecast_mw": _text(
                r, "CurrentGenerationForecast[MW]"
            ),
            "update_time": parse_utc_datetime(
                r.get("UpdateTime(UTC)"),
                field="UpdateTime(UTC)",
                source="entsoe",
                required=False,
            ),
        }


def _parse_aggregated_generation_rows(text):
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    for r in reader:
        yield {
            "datetime": parse_utc_datetime(
                r.get("DateTime(UTC)"),
                field="DateTime(UTC)",
                source="entsoe",
            ),
            "resolution_code": _text(r, "ResolutionCode"),
            "area_code": _text(r, "AreaCode"),
            "area_name": _text(r, "AreaDisplayName"),
            "area_type_code": _text(r, "AreaTypeCode"),
            "area_map_code": _text(r, "AreaMapCode"),
            "production_type": _text(r, "ProductionType"),
            "actual_generation_output_mw": _text(r, "ActualGenerationOutput[MW]"),
            "actual_consumption_mw": _text(r, "ActualConsumption[MW]"),
            "update_time": parse_utc_datetime(
                r.get("UpdateTime(UTC)"),
                field="UpdateTime(UTC)",
                source="entsoe",
                required=False,
            ),
        }


INSTRUMENTS = {
    "energy_prices": {
        "folder": "EnergyPrices_12.1.D_r3.1",
        "resource": "energy_prices",
        "parse_rows": _parse_energy_rows,
        "columns": TIMESTAMP_COLUMNS,
        "enabled": True,
    },
    "imbalance_prices": {
        "folder": "ImbalancePrices_17.1.G_r3.1",
        "resource": "imbalance_prices",
        "parse_rows": _parse_imbalance_rows,
        "columns": TIMESTAMP_COLUMNS,
        "enabled": True,
    },
    "generation_forecasts": {
        "folder": "GenerationForecastsForWindAndSolar_14.1.D_r3",
        "resource": "generation_forecasts",
        "parse_rows": _parse_generation_forecast_rows,
        "columns": TIMESTAMP_COLUMNS,
        "enabled": True,
    },
    "aggregated_generation": {
        "folder": "AggregatedGenerationPerType_16.1.B_C_r3",
        "resource": "aggregated_generation",
        "parse_rows": _parse_aggregated_generation_rows,
        "columns": TIMESTAMP_COLUMNS,
        "enabled": True,
    },
}


def _updated_key(entry):
    try:
        return (
            0,
            parse_utc_datetime(
                entry.get("updated"),
                field="max_update_time",
                source="entsoe/log",
            ),
        )
    except RuntimeError:
        return (1, entry.get("filename", ""))


def _select_files(entries, folder, selected_files=None, latest_only=False,
                  years=None):
    matches = [
        {
            "filename": normalize_filename(entry["file_name"]),
            "updated": entry["max_update_time"],
        }
        for entry in entries
        if filename_to_folder(entry["file_name"]) == folder
    ]

    if years is not None:
        wanted_years = {str(y) for y in years}
        matches = [
            item for item in matches
            if item["filename"][:4] in wanted_years
        ]

    if selected_files is not None:
        wanted = set(selected_files)
        selected = [item for item in matches if item["filename"] in wanted]
        missing = sorted(wanted - {item["filename"] for item in selected})
        if missing:
            raise RuntimeError(
                f"entsoe: nie znaleziono wybranych plików: {', '.join(missing)}"
            )
        return selected

    matches.sort(key=_updated_key)
    if latest_only:
        return matches[-1:] if matches else []
    return matches


def _make_resource(cfg):
    @dlt.resource(
        name=cfg["resource"],
        write_disposition="append",
        columns=cfg["columns"],
    )
    def gen(
        entsoe_username: str = dlt.secrets["entsoe_username"],
        entsoe_password: str = dlt.secrets["entsoe_password"],
        seed: bool = False,
        selected_files=None,
        latest_only: bool = False,
        years=None,
        force: bool = False,
    ):
        tm = TokenManager(entsoe_username, entsoe_password)
        log = fetch_export_log(tm)

        state = dlt.current.resource_state()
        seen = state.setdefault("files", {})

        files = _select_files(
            log, cfg["folder"], selected_files=selected_files,
            latest_only=latest_only, years=years,
        )

        for item in files:
            if seed:
                seen[item["filename"]] = item["updated"]
                continue
            if not force and seen.get(item["filename"]) == item["updated"]:
                continue
            print(f"[entsoe:{cfg['resource']}] pobieram {item['filename']}",
                  flush=True)
            text = download_file_content(tm, cfg["folder"], item["filename"])
            for row in cfg["parse_rows"](text):
                yield row
            seen[item["filename"]] = item["updated"]

    return gen


@dlt.source(name="entsoe")
def entsoe_source(
    entsoe_username: str = dlt.secrets["entsoe_username"],
    entsoe_password: str = dlt.secrets["entsoe_password"],
    seed: bool = False,
    selected_instruments=None,
    selected_files=None,
    latest_only: bool = False,
    years=None,
    force: bool = False,
):
    if selected_instruments is None:
        selected = {
            key: cfg for key, cfg in INSTRUMENTS.items() if cfg.get("enabled")
        }
    else:
        unknown = sorted(set(selected_instruments) - set(INSTRUMENTS))
        if unknown:
            raise RuntimeError(
                "entsoe: nieznane instrumenty: " + ", ".join(unknown)
            )
        selected = {key: INSTRUMENTS[key] for key in selected_instruments}

    for config in selected.values():
        yield _make_resource(config)(
            entsoe_username=entsoe_username,
            entsoe_password=entsoe_password,
            seed=seed,
            selected_files=selected_files,
            latest_only=latest_only,
            years=years,
            force=force,
        )

