from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "taipower_ami"
sys.path.insert(0, str(MODULE_DIR))

from api import (  # noqa: E402
    AmiCredentials,
    AmiProtocolError,
    TaipowerWebClient,
    _roc_year,
    parse_comparison_payload,
    parse_fifteen_payload,
    parse_period_payload,
)


def success_payload(**values):
    return {"msgCode": "AMI0000", "message": "取得成功", **values}


class PayloadParsingTests(unittest.TestCase):
    def test_missing_fifteen_minute_zero_is_not_real_energy(self):
        rows = parse_fifteen_payload(
            success_payload(
                listAMIBase15MinData=[
                    {"time": "13:45", "power": 0.25, "isMssingData": 0},
                    {"time": "14:00", "power": 0.0, "isMssingData": 1},
                ]
            )
        )

        self.assertEqual(rows[0].energy_kwh, 0.25)
        self.assertFalse(rows[0].missing)
        self.assertIsNone(rows[1].energy_kwh)
        self.assertTrue(rows[1].missing)

    def test_official_empty_history_shape_is_valid_but_not_zero(self):
        rows = parse_fifteen_payload(
            {"msgCode": "AMIXXXX", "listAMIBase15MinData": []}
        )

        self.assertEqual(rows, [])

    def test_empty_history_code_requires_the_expected_empty_row_list(self):
        with self.assertRaises(AmiProtocolError):
            parse_fifteen_payload(
                {"msgCode": "AMIXXXX", "listAMIBase15MinData": [{"time": "x"}]}
            )

    def test_period_columns_keep_tariff_meanings(self):
        row = parse_period_payload(
            success_payload(
                listAMIBase4PeriodData=[
                    {
                        "chartUnit": "1日",
                        "chartCol1": 1.0,
                        "chartCol2": 2.0,
                        "chartCol3": 3.0,
                        "chartCol4": 4.0,
                        "chartCol5": 10.0,
                        "isMssingData": 1,
                    }
                ]
            )
        )[0]

        self.assertEqual(row.off_peak_kwh, 1.0)
        self.assertEqual(row.semi_peak_kwh, 2.0)
        self.assertEqual(row.saturday_semi_peak_kwh, 3.0)
        self.assertEqual(row.peak_kwh, 4.0)
        self.assertEqual(row.total_kwh, 10.0)
        self.assertTrue(row.incomplete)

    def test_comparison_columns_are_dates(self):
        row = parse_comparison_payload(
            success_payload(
                listAMIBase4PeriodData=[
                    {"chartUnit": "0時", "chartCol1": 0.5, "chartCol2": 0.75}
                ]
            )
        )[0]

        self.assertEqual(row.first_day_kwh, 0.5)
        self.assertEqual(row.second_day_kwh, 0.75)

    def test_rejects_non_finite_or_negative_numbers(self):
        for value in ("nan", "inf", -0.1):
            with self.subTest(value=value), self.assertRaises(AmiProtocolError):
                parse_period_payload(
                    success_payload(
                        listAMIBase4PeriodData=[{"chartUnit": "x", "chartCol5": value}]
                    )
                )

    def test_gregorian_to_roc_year(self):
        self.assertEqual(_roc_year(2026), 115)


class RecordingClient(TaipowerWebClient):
    def __init__(self):
        super().__init__(
            AmiCredentials(
                session_value="session_value_123",
                enkey="enkey_value_123",
                imported_at="2026-08-28T00:00:00+08:00",
            )
        )
        self.calls = []

    def _get(self, endpoint, params):
        self.calls.append((endpoint, params))
        if endpoint == "fifteenlist":
            return success_payload(listAMIBase15MinData=[])
        return success_payload(listAMIBase4PeriodData=[])


class EndpointContractTests(unittest.TestCase):
    def test_snapshot_calls_only_the_five_expected_read_only_endpoints(self):
        client = RecordingClient()

        snapshot = client.fetch_snapshot(date(2026, 8, 28))

        self.assertEqual(snapshot.target_day, date(2026, 8, 28))
        self.assertEqual(
            [endpoint for endpoint, _params in client.calls],
            [
                "fifteenlist",
                "daylist",
                "monthlist",
                "yearlist",
                "dayanddayalist",
            ],
        )
        self.assertEqual(client.calls[2][1], {"yyymm": "115-08"})
        self.assertEqual(client.calls[3][1], {"year": "115"})
        self.assertEqual(
            client.calls[4][1],
            {"day1": "2026-08-27", "day2": "2026-08-28"},
        )


if __name__ == "__main__":
    unittest.main()
