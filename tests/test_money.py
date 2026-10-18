import unittest

from app.money import MoneyError, cents_to_plain, format_cents, parse_amount


class ParseAmountTests(unittest.TestCase):
    def test_valid_inputs(self):
        cases = {
            "12.34": 1234,
            "5": 500,
            "0.1": 10,
            "$1,000": 100000,
            " 42.50 ": 4250,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_amount(raw), expected)

    def test_avoids_float_rounding_errors(self):
        # 0.1 + 0.2 != 0.3 in floating point; integer cents don't have that problem.
        self.assertEqual(parse_amount("0.10") + parse_amount("0.20"), parse_amount("0.30"))

    def test_invalid_inputs(self):
        for raw in ["", "   ", None, "abc", "-5", "0", "1.234", "NaN", "Infinity", "2000000000"]:
            with self.subTest(raw=raw):
                with self.assertRaises(MoneyError):
                    parse_amount(raw)

    def test_zero_allowed_when_requested(self):
        self.assertEqual(parse_amount("0", allow_zero=True), 0)


class FormatTests(unittest.TestCase):
    def test_format_cents(self):
        self.assertEqual(format_cents(0), "$0.00")
        self.assertEqual(format_cents(123456), "$1,234.56")
        self.assertEqual(format_cents(-50), "−$0.50")

    def test_cents_to_plain(self):
        self.assertEqual(cents_to_plain(123456), "1234.56")
        self.assertEqual(cents_to_plain(5), "0.05")
