import unittest
from datetime import datetime, timedelta, timezone

from sources.common.datetime_utc import format_utc_api, parse_utc_datetime


class ParseUtcDatetimeTests(unittest.TestCase):
    def test_naive_declared_utc_becomes_utc(self):
        self.assertEqual(
            parse_utc_datetime(
                "2026-07-01 08:45:00", field="DateTime(UTC)", source="entsoe"
            ),
            datetime(2026, 7, 1, 8, 45, tzinfo=timezone.utc),
        )

    def test_pse_fractional_utc_string_is_preserved(self):
        self.assertEqual(
            parse_utc_datetime(
                "2026-09-08 05:58:42.265000",
                field="publication_ts_utc",
                source="pse",
            ),
            datetime(2026, 9, 8, 5, 58, 42, 265000, tzinfo=timezone.utc),
        )

    def test_explicit_utc_offset_is_normalized(self):
        self.assertEqual(
            parse_utc_datetime(
                "2026-07-01T08:45:00+00:00",
                field="dtime_utc",
                source="pse",
            ).utcoffset(),
            timedelta(0),
        )

    def test_optional_empty_returns_none(self):
        self.assertIsNone(
            parse_utc_datetime("", field="UpdateTime(UTC)", source="entsoe", required=False)
        )

    def test_required_empty_fails(self):
        with self.assertRaises(RuntimeError):
            parse_utc_datetime("", field="DateTime(UTC)", source="entsoe")

    def test_malformed_fails(self):
        for bad in ["2026-13-01 08:45:00", "2026-07-01", "not-a-date"]:
            with self.subTest(bad=bad):
                with self.assertRaises(RuntimeError):
                    parse_utc_datetime(bad, field="DateTime(UTC)", source="entsoe")

    def test_non_utc_offset_fails(self):
        with self.assertRaises(RuntimeError):
            parse_utc_datetime(
                "2026-07-01 08:45:00+02:00",
                field="DateTime(UTC)",
                source="entsoe",
            )

    def test_api_format_round_trip(self):
        value = datetime(2026, 9, 8, 5, 58, 42, 265000, tzinfo=timezone.utc)
        self.assertEqual(format_utc_api(value), "2026-09-08 05:58:42.265000")


if __name__ == "__main__":
    unittest.main()
