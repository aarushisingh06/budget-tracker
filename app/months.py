"""Helpers for working with calendar months."""

from datetime import date


def parse_month(raw, today=None):
    """Turn "YYYY-MM" into the first day of that month.

    Falls back to the current month when the value is missing or invalid.
    """
    today = today or date.today()
    try:
        year, month = (int(part) for part in str(raw).split("-"))
        return date(year, month, 1)
    except (ValueError, TypeError):
        return today.replace(day=1)


def shift_month(month_start, delta):
    """Move a month forward or back by `delta` months."""
    index = month_start.year * 12 + (month_start.month - 1) + delta
    return date(index // 12, index % 12 + 1, 1)


def month_bounds(month_start):
    """Return ISO dates (start inclusive, end exclusive) covering one month."""
    return month_start.isoformat(), shift_month(month_start, 1).isoformat()


def month_key(month_start):
    """Format a month for URLs, e.g. "2026-10"."""
    return month_start.strftime("%Y-%m")
