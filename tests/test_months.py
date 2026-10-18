import unittest
from datetime import date

from app.months import month_bounds, parse_month, shift_month


class MonthTests(unittest.TestCase):
    def test_parse_valid(self):
        self.assertEqual(parse_month("2026-10"), date(2026, 10, 1))

    def test_parse_invalid_falls_back_to_today(self):
        today = date(2026, 3, 17)
        for raw in [None, "", "nope", "2026-13", "2026"]:
            with self.subTest(raw=raw):
                self.assertEqual(parse_month(raw, today=today), date(2026, 3, 1))

    def test_shift_across_year_boundary(self):
        self.assertEqual(shift_month(date(2026, 12, 1), 1), date(2027, 1, 1))
        self.assertEqual(shift_month(date(2026, 1, 1), -1), date(2025, 12, 1))

    def test_bounds(self):
        self.assertEqual(month_bounds(date(2026, 2, 1)), ("2026-02-01", "2026-03-01"))
