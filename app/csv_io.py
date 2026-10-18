"""CSV import and export.

Format (one header row, then one row per transaction):

    date,description,category,amount
    2026-10-01,October rent,Rent,1450.00

Amounts are always positive; whether a row is income or spending comes from
its category.
"""

import csv
import io
from dataclasses import dataclass, field

from . import queries
from .forms import clean_basic_fields
from .money import cents_to_plain

HEADER = ["date", "description", "category", "amount"]
MAX_ROWS = 5000

# Spreadsheet apps treat cells starting with these characters as formulas,
# which an attacker can abuse ("CSV injection"). Prefixing with an apostrophe
# makes them display as plain text.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _neutralize(text):
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text


def _restore(text):
    if text.startswith("'") and text[1:2] and text[1:2] in FORMULA_PREFIXES:
        return text[1:]
    return text


def export_csv(rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADER)
    for row in rows:
        writer.writerow([
            row["occurred_on"],
            _neutralize(row["description"]),
            _neutralize(row["category"]),
            cents_to_plain(row["amount_cents"]),
        ])
    return buffer.getvalue()


@dataclass
class ImportResult:
    imported: int = 0
    errors: list[str] = field(default_factory=list)


def import_csv(db, raw_bytes):
    """Validate every row first; save nothing unless the whole file is valid."""
    result = ImportResult()

    try:
        text = raw_bytes.decode("utf-8-sig")  # handles the BOM Excel adds
    except UnicodeDecodeError:
        result.errors.append("The file isn’t UTF-8 text. Save it as “CSV UTF-8” and try again.")
        return result

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = [name.strip().lower() for name in (reader.fieldnames or [])]
    if fieldnames != HEADER:
        result.errors.append("The first row must be exactly: " + ",".join(HEADER))
        return result
    reader.fieldnames = fieldnames

    categories = queries.category_ids_by_name(db)
    pending = []

    for line_number, row in enumerate(reader, start=2):
        if len(pending) + len(result.errors) >= MAX_ROWS:
            result.errors.append(f"Files are limited to {MAX_ROWS} rows.")
            break
        if not any((value or "").strip() for value in row.values()):
            continue  # skip blank lines

        data, errors = clean_basic_fields(
            row.get("date"), _restore(row.get("description") or ""), row.get("amount")
        )
        category_name = _restore((row.get("category") or "").strip())
        category_id = categories.get(category_name.casefold())
        if category_id is None:
            errors["category"] = f"there’s no category called “{category_name}”"

        if errors:
            details = "; ".join(message.rstrip(".") for message in errors.values())
            result.errors.append(f"Row {line_number}: {details}.")
        else:
            data["category_id"] = category_id
            pending.append(data)

    if result.errors:
        return result
    if not pending:
        result.errors.append("The file has no transactions in it.")
        return result

    queries.insert_many(db, pending)
    result.imported = len(pending)
    return result
