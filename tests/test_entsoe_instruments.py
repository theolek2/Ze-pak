import unittest
from datetime import datetime, timezone

from sources.entsoe.entsoe_source import (
    INSTRUMENTS,
    _parse_aggregated_generation_rows,
    _parse_generation_forecast_rows,
    _parse_imbalance_rows,
    _select_files,
)


class EntsoeFileSelectionTests(unittest.TestCase):
    LOG = [
        {"file_name": "2026_07_ImbalancePrices_17.1.G_r3.1", "max_update_time": "2026-08-01T10:00:00"},
        {"file_name": "2026_08_ImbalancePrices_17.1.G_r3.1", "max_update_time": "2026-09-01T10:00:00"},
    ]

    def test_defaults_to_enabled_instruments(self):
        enabled = [key for key, cfg in INSTRUMENTS.items() if cfg.get("enabled")]
        self.assertIn("energy_prices", enabled)
        self.assertIn("imbalance_prices", enabled)

    def test_imbalance_instrument_uses_exact_folder(self):
        self.assertEqual(INSTRUMENTS["imbalance_prices"]["folder"], "ImbalancePrices_17.1.G_r3.1")
        self.assertEqual(INSTRUMENTS["imbalance_prices"]["resource"], "imbalance_prices")

    def test_selects_all_matches_in_update_order(self):
        selected = _select_files(self.LOG, "ImbalancePrices_17.1.G_r3.1")
        self.assertEqual(
            [item["filename"] for item in selected],
            [
                "2026_07_ImbalancePrices_17.1.G_r3.1.csv",
                "2026_08_ImbalancePrices_17.1.G_r3.1.csv",
            ],
        )

    def test_latest_only_returns_newest_file(self):
        selected = _select_files(self.LOG, "ImbalancePrices_17.1.G_r3.1", latest_only=True)
        self.assertEqual(
            [item["filename"] for item in selected],
            ["2026_08_ImbalancePrices_17.1.G_r3.1.csv"],
        )

    def test_missing_selected_file_fails(self):
        with self.assertRaises(RuntimeError):
            _select_files(self.LOG, "ImbalancePrices_17.1.G_r3.1", selected_files=["missing.csv"])


class ImbalanceParserTests(unittest.TestCase):
    SAMPLE = (
        "DateTime(UTC)\tResolutionCode\tAreaCode\tAreaDisplayName\tAreaTypeCode\t"
        "AreaMapCode\tPositiveImbalancePrice[Currency/MWh]\t"
        "PositiveScarcity[Currency/MWh]\tPositiveIncentive[Currency/MWh]\t"
        "PositiveFinancialNeutrality[Currency/MWh] \t"
        "NegativeImbalancePrice[Currency/MWh]\t"
        "NegativeScarcity[Currency/MWh]\tNegativeIncentive[Currency/MWh]\t"
        "NegativeFinancialNeutrality[Currency/MWh]\tCurrency\tStatus\tUpdateTime(UTC)\n"
        "2026-09-01 00:00:00\tPT60M\t10YAL-KESH-----5\tAlbania (AL)\tSCA\tAL\t"
        "69.90\t\t\t\t90.78\t\t\t\tEUR\t\t\n"
    )

    def test_parser_keeps_grain_and_utc(self):
        (row,) = list(_parse_imbalance_rows(self.SAMPLE))
        self.assertEqual(
            row["datetime"], datetime(2026, 9, 1, tzinfo=timezone.utc)
        )
        self.assertEqual(row["area_map_code"], "AL")
        self.assertEqual(row["positive_imbalance_price"], "69.90")
        self.assertEqual(row["negative_imbalance_price"], "90.78")
        self.assertIsNone(row["update_time"])
        self.assertEqual(row["currency"], "EUR")


class GenerationForecastParserTests(unittest.TestCase):
    SAMPLE = (
        "DateTime(UTC)\tResolutionCode\tAreaCode\tAreaDisplayName\tAreaTypeCode\t"
        "AreaMapCode\tProductionType\tDayAheadGenerationForecast[MW]\t"
        "IntradayGenerationForecast[MW]\tCurrentGenerationForecast[MW]\tUpdateTime(UTC)\n"
        "2026-09-01 00:00:00\tPT60M\t10YAL-KESH-----5\tAlbania (AL)\tBZN/CTA/CTY\tAL\t"
        "Solar\t0.58\t0.58\t0.58\t2026-09-03 18:20:19\n"
    )

    def test_parser_keeps_grain_and_utc(self):
        (row,) = list(_parse_generation_forecast_rows(self.SAMPLE))
        self.assertEqual(
            row["datetime"], datetime(2026, 9, 1, tzinfo=timezone.utc)
        )
        self.assertEqual(row["area_map_code"], "AL")
        self.assertEqual(row["production_type"], "Solar")
        self.assertEqual(row["day_ahead_generation_forecast_mw"], "0.58")
        self.assertEqual(
            row["update_time"],
            datetime(2026, 9, 3, 18, 20, 19, tzinfo=timezone.utc),
        )


class AggregatedGenerationParserTests(unittest.TestCase):
    SAMPLE = (
        "DateTime(UTC)\tResolutionCode\tAreaCode\tAreaDisplayName\tAreaTypeCode\t"
        "AreaMapCode\tProductionType\tActualGenerationOutput[MW]\t"
        "ActualConsumption[MW]\tUpdateTime(UTC)\n"
        "2026-09-01 00:00:00\tPT60M\t10YAL-KESH-----5\tAlbania (AL)\tBZN/CTA/CTY\tAL\t"
        "Fossil Oil\t0\t\t2026-09-03 03:20:03\n"
    )

    def test_parser_keeps_grain_and_utc(self):
        (row,) = list(_parse_aggregated_generation_rows(self.SAMPLE))
        self.assertEqual(
            row["datetime"], datetime(2026, 9, 1, tzinfo=timezone.utc)
        )
        self.assertEqual(row["area_map_code"], "AL")
        self.assertEqual(row["production_type"], "Fossil Oil")
        self.assertEqual(row["actual_generation_output_mw"], "0")
        self.assertEqual(
            row["update_time"],
            datetime(2026, 9, 3, 3, 20, 3, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()
