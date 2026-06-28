import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from src.dashboard import build_dashboard, tax_year_start
from tests.sample_data import payload


class DashboardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dashboard = build_dashboard(
            json.dumps(payload()),
            now=datetime(2026, 6, 28, 15, 0, tzinfo=ZoneInfo("Europe/London")),
        )

    def test_summary_and_details(self):
        self.assertEqual(self.dashboard["schemaVersion"], 2)
        self.assertEqual(
            self.dashboard["summary"], {"bookings": 21, "cancelled": 1, "drivers": 4}
        )
        self.assertEqual(
            self.dashboard["bookings"][0]["driverEmail"], "amelia@example.com"
        )
        self.assertEqual(self.dashboard["drivers"][0]["phone"], "07111 111111")

    def test_earnings_are_precomputed_for_every_period(self):
        earnings = self.dashboard["earnings"]
        self.assertEqual(earnings["bookings"], 21)
        self.assertEqual(
            set(earnings["periods"]), {"day", "week", "month", "quarter", "year"}
        )
        self.assertAlmostEqual(
            sum(point["value"] for point in earnings["periods"]["day"]),
            earnings["total"],
        )

    def test_occupancy_is_bounded_and_has_all_windows(self):
        occupancy = self.dashboard["occupancy"]
        self.assertEqual(occupancy["windows"], [7, 14, 30, 90])
        values = [row["7"] for row in occupancy["minutes"] if row["7"] is not None]
        self.assertTrue(values)
        self.assertTrue(all(0 <= value <= 1 for value in values))

    def test_driver_highlights(self):
        highlights = self.dashboard["driverHighlights"]
        self.assertEqual(highlights["busiestWeekday"], "Friday")
        self.assertEqual(highlights["longestStay"]["hours"], 19)
        self.assertGreater(highlights["repeatRate"], 0.5)

    def test_uk_tax_year(self):
        self.assertEqual(str(tax_year_start(datetime(2026, 4, 5).date())), "2025-04-06")
        self.assertEqual(str(tax_year_start(datetime(2026, 4, 6).date())), "2026-04-06")

    def test_empty_payload(self):
        empty = build_dashboard(
            '{"fetchedAt":"2026-06-28T12:00:00Z","total":0,"items":[]}'
        )
        self.assertEqual(
            empty["summary"], {"bookings": 0, "cancelled": 0, "drivers": 0}
        )
        self.assertEqual(empty["occupancy"]["minutes"], [])
        self.assertEqual(empty["driverHighlights"], {})


if __name__ == "__main__":
    unittest.main()
