"""Money helpers.

All amounts are stored as integer cents. Floats are never used for money,
because binary floating point can't represent values like 0.10 exactly.
"""

from decimal import Decimal, InvalidOperation

MAX_AMOUNT = Decimal("1000000000")  # $1 billion: a sanity limit, not a business rule


class MoneyError(ValueError):
    """Raised when user input can't be turned into a valid amount."""


def parse_amount(raw, *, allow_zero=False):
    """Convert user input such as "1,234.50" or "$12" into integer cents."""
    if raw is None or not str(raw).strip():
        raise MoneyError("Enter an amount.")

    cleaned = str(raw).strip().replace(",", "")
    if cleaned.startswith("$"):
        cleaned = cleaned[1:]

    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise MoneyError(f"“{raw}” isn’t a number. Enter an amount like 42.50.") from None

    if not value.is_finite():
        raise MoneyError(f"“{raw}” isn’t a number. Enter an amount like 42.50.")
    if value < 0 or (value == 0 and not allow_zero):
        raise MoneyError("Enter an amount greater than zero.")
    if value.as_tuple().exponent < -2:
        raise MoneyError("Use at most two decimal places.")
    if value > MAX_AMOUNT:
        raise MoneyError("That amount is too large.")

    return int(value * 100)


def format_cents(cents):
    """Format integer cents for display, e.g. 123456 -> "$1,234.56"."""
    if cents is None:
        return ""
    sign = "−" if cents < 0 else ""
    dollars, remainder = divmod(abs(int(cents)), 100)
    return f"{sign}${dollars:,}.{remainder:02d}"


def cents_to_plain(cents):
    """Format cents without symbols or separators, e.g. 123456 -> "1234.56".

    Used to pre-fill form fields and for CSV export.
    """
    sign = "-" if cents < 0 else ""
    dollars, remainder = divmod(abs(int(cents)), 100)
    return f"{sign}{dollars}.{remainder:02d}"
